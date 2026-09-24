"""
Source adapters. Every fetcher returns a list of rows sorted by date:
  value series : [(date_iso, value), ...]
  ohlc series  : [(date_iso, open, high, low, close, volume), ...]
Raise SourceError on any failure so the caller can try the next candidate.
"""
import csv
import io
import json
import re
import time
from datetime import date, datetime, timezone

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 25


class SourceError(Exception):
    pass


def _get(url, headers=None, params=None, retries=1, sleep=2.0):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers=h, params=params, timeout=TIMEOUT)
            if r.status_code == 200 and r.content:
                return r
            last = f"HTTP {r.status_code}: {r.text[:120]!r}"
        except requests.RequestException as e:  # noqa: PERF203
            last = repr(e)
        time.sleep(sleep * (i + 1))
    raise SourceError(f"{url} -> {last}")


DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")
QUARTER_RE = re.compile(r"^(\d{4})-?Q([1-4])$")
WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def norm_period(p):
    """Normalise a period string (YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qn, YYYY-Www) to an ISO date
    at the START of the period. Returns None if unparseable."""
    p = p.strip()
    m = DATE_RE.match(p)
    if m:
        y, mo, d = m.group(1), m.group(2) or "01", m.group(3) or "01"
        return f"{y}-{mo}-{d}"
    m = QUARTER_RE.match(p)
    if m:
        return f"{m.group(1)}-{int(m.group(2)) * 3 - 2:02d}-01"
    m = WEEK_RE.match(p)
    if m:
        try:
            return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1).isoformat()
        except ValueError:
            return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})T", p)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", p)
    if m:  # dd/mm/yyyy (Bundesbank downloads)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _num(s):
    if s is None:
        return None
    s = str(s).strip().replace(" ", "")
    if s in ("", ".", "NA", "NaN", "null", "-", "n/a", "..."):
        return None
    # Bundesbank/ECB csv can use comma decimals when lang=de; handle both.
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _clean_value_rows(rows):
    out = {}
    for d, v in rows:
        if d and v is not None and v == v:
            out[d] = v
    if not out:
        raise SourceError("no usable observations")
    return sorted(out.items())


# ---------------------------------------------------------------- FRED
def fred(key):
    r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": key})
    rows = []
    for rec in csv.reader(io.StringIO(r.text)):
        if len(rec) < 2:
            continue
        d = norm_period(rec[0])
        if d is None:
            continue
        rows.append((d, _num(rec[1])))
    return _clean_value_rows(rows)


def fred_inv(key):
    return [(d, 1.0 / v) for d, v in fred(key) if v]


def fred_pct(key):
    """Month-over-month % change of a FRED level series."""
    rows = fred(key)
    out = []
    for (d0, v0), (d1, v1) in zip(rows, rows[1:]):
        if v0:
            out.append((d1, round((v1 / v0 - 1.0) * 100.0, 4)))
    return out


def fred_yoy(key):
    rows = fred(key)
    by = dict(rows)
    out = []
    for d, v in rows:
        y, m, dd = d.split("-")
        prev = f"{int(y) - 1}-{m}-{dd}"
        if prev in by and by[prev]:
            out.append((d, round((v / by[prev] - 1.0) * 100.0, 4)))
    return out


# ---------------------------------------------------------------- Yahoo Finance
def yahoo(symbol, inverse=False):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol)}"
    r = _get(url, params={"range": "max", "interval": "1d", "includePrePost": "false", "events": "div,splits"},
             headers={"Accept": "application/json"})
    try:
        res = r.json()["chart"]["result"][0]
    except Exception as e:  # noqa: BLE001
        raise SourceError(f"yahoo bad json for {symbol}: {e}")
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    tzname = res.get("meta", {}).get("exchangeTimezoneName") or "UTC"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tzname)
    except Exception:  # noqa: BLE001
        tz = timezone.utc
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        v = (q.get("volume") or [None] * len(ts))[i]
        if c is None or o is None or h is None or l is None:
            continue
        d = datetime.fromtimestamp(t, tz).date().isoformat()
        if inverse:
            o, h, l, c = 1 / o, 1 / l, 1 / h, 1 / c
        rows.append((d, float(o), float(h), float(l), float(c), float(v or 0)))
    if len(rows) < 30:
        raise SourceError(f"yahoo returned {len(rows)} rows for {symbol}")
    rows.sort()
    return rows


def yahoo_inv(symbol):
    return yahoo(symbol, inverse=True)


# ---------------------------------------------------------------- Stooq
def stooq(symbol):
    r = _get("https://stooq.com/q/d/l/", params={"s": symbol, "i": "d"})
    txt = r.text
    if "Exceeded" in txt[:200] or "Date" not in txt[:200]:
        raise SourceError(f"stooq: {txt[:80]!r}")
    rows = []
    for rec in csv.DictReader(io.StringIO(txt)):
        d = norm_period(rec.get("Date", ""))
        o, h, l, c = (_num(rec.get(k)) for k in ("Open", "High", "Low", "Close"))
        v = _num(rec.get("Volume")) or 0.0
        if d and None not in (o, h, l, c):
            rows.append((d, o, h, l, c, v))
    if len(rows) < 30:
        raise SourceError(f"stooq returned {len(rows)} rows for {symbol}")
    rows.sort()
    return rows


# ---------------------------------------------------------------- SDMX-CSV helpers (ECB, Bundesbank)
def _parse_sdmx_csv(txt):
    """Parse SDMX-CSV (TIME_PERIOD/OBS_VALUE columns) or a plain 'date;value' style dump."""
    rows = []
    lines = txt.splitlines()
    # 1) SDMX-CSV with header
    for delim in (",", ";"):
        for i, line in enumerate(lines[:20]):
            if "TIME_PERIOD" in line and "OBS_VALUE" in line and delim in line:
                rdr = csv.DictReader(io.StringIO("\n".join(lines[i:])), delimiter=delim)
                for rec in rdr:
                    d = norm_period(rec.get("TIME_PERIOD", "") or "")
                    v = _num(rec.get("OBS_VALUE"))
                    if d:
                        rows.append((d, v))
                return rows
    # 2) generic: rows starting with a date
    for line in lines:
        parts = re.split(r"[;,\t]", line.strip())
        if len(parts) < 2:
            continue
        d = norm_period(parts[0].strip().strip('"'))
        if d is None:
            continue
        rows.append((d, _num(parts[1].strip().strip('"'))))
    return rows


def ecb(key):
    """key = FLOW/SERIES_KEY, optional ?startPeriod=... suffix."""
    flow, _, series = key.partition("/")
    series, _, extra = series.partition("?")
    params = {"format": "csvdata"}
    if extra:
        for kv in extra.split("&"):
            k, _, v = kv.partition("=")
            params[k] = v
    r = _get(f"https://data-api.ecb.europa.eu/service/data/{flow}/{series}", params=params,
             headers={"Accept": "text/csv"})
    return _clean_value_rows(_parse_sdmx_csv(r.text))


def bbk(key):
    """Bundesbank statistics REST API. key = FLOW/SERIES_KEY (e.g. BBSSY/D.REN.EUR.A620.000000WT0202.A)."""
    flow, _, series = key.partition("/")
    errors = []
    for url, headers, params in (
        (f"https://api.statistiken.bundesbank.de/rest/data/{flow}/{series}",
         {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}, {"detail": "dataonly"}),
        (f"https://api.statistiken.bundesbank.de/rest/download/{flow}/{series}",
         {"Accept": "text/csv"}, {"format": "csv", "lang": "en"}),
    ):
        try:
            r = _get(url, headers=headers, params=params, retries=0)
            return _clean_value_rows(_parse_sdmx_csv(r.text))
        except SourceError as e:
            errors.append(str(e)[:160])
    raise SourceError("bbk: " + " | ".join(errors))


# ---------------------------------------------------------------- DBnomics
def dbnomics(key):
    """key = PROVIDER/DATASET/SERIES_CODE"""
    r = _get(f"https://api.db.nomics.world/v22/series/{key}", params={"observations": "1", "format": "json"},
             headers={"Accept": "application/json"})
    try:
        docs = r.json()["series"]["docs"]
        doc = docs[0]
    except Exception as e:  # noqa: BLE001
        raise SourceError(f"dbnomics bad json for {key}: {e}")
    rows = []
    for p, v in zip(doc.get("period", []), doc.get("value", [])):
        d = norm_period(str(p))
        if d:
            rows.append((d, _num(v)))
    return _clean_value_rows(rows)


def dbnomics_search(query, limit=12):
    """Return a list of (series_id, name, last_period) for a free-text search (used for probing)."""
    r = _get("https://api.db.nomics.world/v22/search", params={"q": query, "limit": str(limit)},
             headers={"Accept": "application/json"})
    out = []
    try:
        for doc in r.json()["results"]["docs"]:
            out.append((f"{doc['provider_code']}/{doc['dataset_code']}", doc.get("dataset_name") or doc.get("name", ""), doc.get("nb_series", "")))
    except Exception:  # noqa: BLE001
        pass
    return out


# ---------------------------------------------------------------- manual CSV
def manual(key, manual_dir):
    p = manual_dir / f"{key}.csv"
    if not p.exists():
        raise SourceError(f"no manual file {p.name}")
    rows = []
    for rec in csv.reader(p.open(encoding="utf-8")):
        if len(rec) < 2:
            continue
        d = norm_period(rec[0])
        if d:
            rows.append((d, _num(rec[1])))
    return _clean_value_rows(rows)


# ---------------------------------------------------------------- PBoC (best effort)
def pboc(_key):
    """Best-effort scrape of the PBoC English site 'Balance Sheet of Monetary Authority'.
    Site structure changes every year; if it breaks, put data/manual/CNCBBS.csv in place."""
    base = "http://www.pbc.gov.cn"
    idx = _get(f"{base}/en/3688247/3688975/index.html", retries=0)
    links = re.findall(r'href="([^"]+)"[^>]*>([^<]*Balance Sheet of Monetary Authority[^<]*)<', idx.text, flags=re.I)
    if not links:
        # try the "Statistics" landing page which lists yearly data sets
        idx = _get(f"{base}/en/3688247/index.html", retries=0)
        links = re.findall(r'href="([^"]+)"[^>]*>([^<]*Monetary Authority[^<]*)<', idx.text, flags=re.I)
    if not links:
        raise SourceError("pboc: no 'Balance Sheet of Monetary Authority' link found")
    href = links[0][0]
    if href.startswith("/"):
        href = base + href
    page = _get(href, retries=0)
    # find the html table with 'Total Assets' row; header cells hold months like 2025.01
    months = re.findall(r"(20\d{2})[.\-/年](\d{1,2})", page.text)
    row = re.search(r"Total\s*Assets.*?</tr>", page.text, flags=re.I | re.S)
    if not row or not months:
        raise SourceError("pboc: table layout not recognised")
    nums = [_num(x) for x in re.findall(r">\s*([\d,\.]+)\s*<", row.group(0))]
    nums = [n for n in nums if n is not None]
    if len(nums) < 1:
        raise SourceError("pboc: no numbers in Total Assets row")
    seen, periods = set(), []
    for y, m in months:
        key = f"{y}-{int(m):02d}-01"
        if key not in seen:
            seen.add(key)
            periods.append(key)
    n = min(len(nums), len(periods))
    return _clean_value_rows(list(zip(periods[:n], nums[:n])))


# ---------------------------------------------------------------- GeckoTerminal
GT = "https://api.geckoterminal.com/api/v2"
_gt_last = [0.0]


def _gt_get(path, params=None):
    # free tier: 30 req/min -> keep >= 2.2 s between calls
    wait = 2.2 - (time.time() - _gt_last[0])
    if wait > 0:
        time.sleep(wait)
    r = _get(f"{GT}{path}", params=params, headers={"Accept": "application/json;version=20230302"}, retries=2, sleep=5)
    _gt_last[0] = time.time()
    return r.json()


def gt_search_pool(network, symbol, quotes, token=None):
    """Find the most liquid pool whose base token symbol matches (and token address, if given)."""
    js = _gt_get("/search/pools", params={"query": symbol, "network": network, "page": "1"})
    best, cands = None, []
    for p in js.get("data", []):
        a = p.get("attributes", {})
        name = a.get("name", "")
        base_sym, _, quote_sym = name.partition(" / ")
        base_sym = base_sym.strip()
        quote_sym = quote_sym.split(" ")[0].strip()
        rel = p.get("relationships", {})
        base_id = (rel.get("base_token", {}).get("data") or {}).get("id", "")
        base_addr = base_id.split("_", 1)[1].lower() if "_" in base_id else ""
        reserve = float(a.get("reserve_in_usd") or 0)
        cands.append((name, a.get("address"), reserve, base_addr))
        if base_sym.upper() != symbol.upper():
            continue
        if token and base_addr and base_addr != token.lower():
            continue
        score = reserve * (2.0 if quote_sym.upper() in [q.upper() for q in quotes] else 1.0)
        if best is None or score > best[0]:
            best = (score, dict(pool=a.get("address"), name=name, reserve_usd=reserve,
                                base_symbol=base_sym, quote_symbol=quote_sym, base_token=base_addr,
                                price_usd=_num(a.get("base_token_price_usd"))))
    return (best[1] if best else None), cands


def gt_ohlcv(network, pool, timeframe="day", aggregate=1, limit=1000, before=None, token="base"):
    params = {"aggregate": str(aggregate), "limit": str(limit), "currency": "usd", "token": token}
    if before:
        params["before_timestamp"] = str(int(before))
    js = _gt_get(f"/networks/{network}/pools/{pool}/ohlcv/{timeframe}", params=params)
    lst = js.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or []
    rows = []
    for t, o, h, l, c, v in lst:
        if None in (o, h, l, c):
            continue
        rows.append((int(t), float(o), float(h), float(l), float(c), float(v or 0)))
    rows.sort()
    return rows


def gt_ohlcv_history(network, pool, timeframe, aggregate, pages=1, token="base"):
    allrows, before = [], None
    for _ in range(pages):
        rows = gt_ohlcv(network, pool, timeframe, aggregate, before=before, token=token)
        if not rows:
            break
        allrows = rows + allrows
        before = rows[0][0] - 1
        if len(rows) < 1000:
            break
    # dedupe on timestamp
    seen, out = set(), []
    for r in allrows:
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r)
    out.sort()
    return out
