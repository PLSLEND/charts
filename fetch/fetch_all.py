#!/usr/bin/env python3
"""
Pulls every series in series_config.py, builds the constructed ratios, resolves and caches the
PulseChain / HEX pairs, and writes:

  data/manifest.json          catalog + metadata for the app
  data/status.json            per-series fetch status (source used, last date, errors)
  data/series/<ID>.json       {"id","kind","freq","bars":[[ts_ms, value] | [ts_ms,o,h,l,c,v], ...]}
  data/crypto/pools.json      resolved GeckoTerminal pools (+ candidates for review)
  data/crypto/<ID>_day.json   cached daily candles   (fallback when the browser can't reach GeckoTerminal)
  data/crypto/<ID>_4h.json    cached 4-hour candles

A failed fetch never deletes existing data: the previous file is kept and flagged as stale.
Never exits non-zero for a data problem; the workflow should commit whatever succeeded.
"""
import json
import math
from concurrent.futures import ThreadPoolExecutor
import re
import statistics
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sources as S  # noqa: E402
from series_config import CRYPTO, GROUP_ORDER, RATIOS, SERIES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SERIES_DIR = DATA / "series"
CRYPTO_DIR = DATA / "crypto"
MANUAL_DIR = DATA / "manual"
for d in (SERIES_DIR, CRYPTO_DIR, MANUAL_DIR):
    d.mkdir(parents=True, exist_ok=True)

NOW = datetime.now(timezone.utc)
ONLY = set(a for a in sys.argv[1:] if not a.startswith("--"))
SKIP_CRYPTO = "--no-crypto" in sys.argv
SKIP_MACRO = "--no-macro" in sys.argv
QUICK = "--quick" in sys.argv  # frequent light run: market quotes + newest on-chain candles only

SOURCE_LABEL = {
    "fred": "FRED (St. Louis Fed)", "fred_inv": "FRED (St. Louis Fed)", "fred_pct": "FRED (St. Louis Fed), MoM % computed",
    "fred_yoy": "FRED (St. Louis Fed), YoY % computed",
    "yahoo": "Yahoo Finance", "yahoo_inv": "Yahoo Finance (inverted)", "stooq": "Stooq",
    "ecb": "ECB Data Portal", "bbk": "Deutsche Bundesbank", "dbnomics": "DBnomics", "manual": "manual CSV",
    "pboc": "People's Bank of China (scraped)", "geckoterminal": "GeckoTerminal",
}
SOURCE_URL = {
    "fred": "https://fred.stlouisfed.org/series/{k}", "fred_inv": "https://fred.stlouisfed.org/series/{k}",
    "fred_pct": "https://fred.stlouisfed.org/series/{k}", "fred_yoy": "https://fred.stlouisfed.org/series/{k}",
    "yahoo": "https://finance.yahoo.com/quote/{k}", "yahoo_inv": "https://finance.yahoo.com/quote/{k}",
    "stooq": "https://stooq.com/q/d/?s={k}", "ecb": "https://data.ecb.europa.eu/data/datasets/{k}",
    "bbk": "https://www.bundesbank.de/en/statistics", "dbnomics": "https://db.nomics.world/{k}",
    "manual": "", "pboc": "http://www.pbc.gov.cn/en/3688247/index.html"
}


def log(*a):
    print(*a, flush=True)


def ts_ms(date_iso):
    y, m, d = (int(x) for x in date_iso.split("-"))
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def sig(v, n=8):
    """Round to n significant digits to keep JSON small."""
    if v is None or v == 0 or not math.isfinite(v):
        return v
    return float(f"{v:.{n}g}")


def auto_precision(values):
    vals = [abs(v) for v in values if v is not None and math.isfinite(v) and v != 0]
    if not vals:
        return 2
    med = statistics.median(vals[-500:])
    if med >= 1000:
        return 0
    if med >= 100:
        return 1
    if med >= 10:
        return 2
    if med >= 1:
        return 3
    if med >= 0.1:
        return 4
    if med >= 0.01:
        return 5
    if med >= 0.0001:
        return 7
    return 10


def load_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def dump_json(p, obj, compact=True):
    txt = json.dumps(obj, separators=(",", ":") if compact else (",", ": "), ensure_ascii=False, indent=None if compact else 1)
    p.write_text(txt, encoding="utf-8")


def rows_to_bars(rows, kind):
    bars = []
    if kind == "ohlc":
        for d, o, h, l, c, v in rows:
            bars.append([ts_ms(d), sig(o), sig(h), sig(l), sig(c), sig(v, 6)])
    else:
        for d, v in rows:
            bars.append([ts_ms(d), sig(v)])
    return bars


def fetch_one(spec):
    """Try each candidate source; return (bars, source_name, key, error_list)."""
    errors = []
    best = None
    for cand in spec["sources"]:
        src, key = cand[0], cand[1]
        if len(cand) > 2:
            key = key  # name override handled by the caller via name_for()
        try:
            if src == "fred":
                rows = S.fred(key)
            elif src == "fred_inv":
                rows = S.fred_inv(key)
            elif src == "fred_pct":
                rows = S.fred_pct(key)
            elif src == "fred_yoy":
                rows = S.fred_yoy(key)
            elif src == "yahoo":
                rows = S.yahoo(key)
            elif src == "yahoo_inv":
                rows = S.yahoo_inv(key)
            elif src == "stooq":
                rows = S.stooq(key)
            elif src == "ecb":
                rows = S.ecb(key)
            elif src == "bbk":
                rows = S.bbk(key)
            elif src == "dbnomics":
                rows = S.dbnomics(key)
            elif src == "manual":
                rows = S.manual(key, MANUAL_DIR)
            elif src == "pboc":
                rows = S.pboc(key)
            else:
                raise S.SourceError(f"unknown source {src}")
            kind = spec["kind"]
            if kind == "ohlc" and len(rows[0]) == 2:
                # a value-only fallback (e.g. FRED SP500) for an OHLC series: synthesise flat candles
                rows = [(d, v, v, v, v, 0.0) for d, v in rows]
            bars = rows_to_bars(rows, kind)
            if len(bars) < 5:
                raise S.SourceError(f"{src}:{key} returned only {len(bars)} bars")
            if spec.get("deep"):
                bars = prepend_deep(spec, bars)
            if kind == "ohlc" and len(bars) < 2500:
                # a short history (e.g. Yahoo throttled to a few months): remember it, try the next source
                if best is None or len(bars) > len(best[0]):
                    best = (bars, src, key)
                errors.append(f"{src}:{key} -> only {len(bars)} bars, trying next source")
                continue
            return bars, src, key, errors
        except Exception as e:  # noqa: BLE001
            errors.append(f"{src}:{key} -> {str(e)[:200]}")
    if best is not None:
        return best[0], best[1], best[2], errors
    return None, None, None, errors


def name_for(spec, src, key):
    """Display name, overridden when the winning source candidate carries its own label."""
    for cand in spec.get("sources", []):
        if len(cand) > 2 and cand[0] == src and cand[1] == key:
            return cand[2]
    return spec["name"]


CLEAN_TOL = {"FX": 0.06, "Indices & commodities": 0.25, "Crypto majors": 0.5}


def clean_ohlc(bars, tol):
    """Drop bad days and clip bad wicks from an OHLC series (Yahoo's FX history has junk ticks).
    A bar's open/close is compared with the median close of the 10 surrounding bars: if open or close
    deviate more than `tol` the bar is dropped; if only high/low do, they are clipped to the body."""
    if not bars or len(bars[0]) < 5 or not tol:
        return bars
    closes = [b[4] for b in bars]
    out, dropped, clipped = [], 0, 0
    for i, b in enumerate(bars):
        window = closes[max(0, i - 5):i] + closes[i + 1:i + 6]
        if len(window) < 4:
            out.append(b)
            continue
        ref = statistics.median(window)
        if ref <= 0:
            out.append(b)
            continue
        t, o, h, l, c, v = b[:6]
        if abs(o / ref - 1) > tol or abs(c / ref - 1) > tol:
            dropped += 1
            continue
        hi, lo = max(o, c), min(o, c)
        if h > hi * (1 + tol) or l < lo * (1 - tol) or l <= 0:
            out.append([t, o, hi, lo, c, v])
            clipped += 1
        else:
            out.append(b)
    if dropped or clipped:
        log(f"     ~ cleaned: {dropped} bad bars dropped, {clipped} wicks clipped")
    return out


def prepend_deep(spec, bars):
    """Extend a series backwards with an older feed (spec['deep'] = (source, key)) for dates before its first bar."""
    dsrc, dkey = spec["deep"]
    try:
        fn = {"fred": S.fred, "stooq": S.stooq, "yahoo": S.yahoo, "ecb": S.ecb, "dbnomics": S.dbnomics, "pinksheet": S.worldbank_pinksheet}[dsrc]
        rows = fn(dkey)
        first = bars[0][0]
        if len(rows[0]) == 2 and spec["kind"] == "ohlc":
            rows = [(d, v, v, v, v, 0.0) for d, v in rows]
        deep = [b for b in rows_to_bars(rows, spec["kind"]) if b[0] < first]
        if deep:
            log(f"     + {spec['id']}: {len(deep)} earlier bars from {dsrc}:{dkey}")
            return deep + bars
    except Exception as e:  # noqa: BLE001
        log(f"     ~ {spec['id']}: deep history {dsrc}:{dkey} unavailable: {str(e)[:120]}")
    return bars


def series_meta(spec, bars, src, key, stale, group=None):
    last = datetime.fromtimestamp(bars[-1][0] / 1000, timezone.utc).date().isoformat() if bars else None
    first = datetime.fromtimestamp(bars[0][0] / 1000, timezone.utc).date().isoformat() if bars else None
    closes = [b[4] if len(b) > 2 else b[1] for b in bars]
    return dict(
        id=spec["id"], name=name_for(spec, src, key), group=group or spec["group"], freq=spec["freq"], kind=spec["kind"],
        units=spec.get("units", ""), tv=spec.get("tv", ""), precision=auto_precision(closes),
        source=SOURCE_LABEL.get(src, src or "?"), source_key=key or "",
        source_url=(SOURCE_URL.get(src, "") or "").format(k=key or ""),
        first=first, last=last, n=len(bars), stale=stale, file=f"series/{spec['id']}.json",
    )


# ------------------------------------------------------------------ ratios
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[-+*/()]")

FREQ_RANK = {"4h": 0, "D": 1, "W": 2, "M": 3, "Q": 4}


def eval_expr(expr, env):
    """Tiny safe evaluator: identifiers from env, numbers, + - * / and parentheses."""
    tokens = TOKEN_RE.findall(expr)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def take():
        t = tokens[pos[0]]
        pos[0] += 1
        return t

    def atom():
        t = take()
        if t == "(":
            v = additive()
            take()
            return v
        if t == "-":
            return -atom()
        if re.match(r"^\d", t):
            return float(t)
        return env[t]

    def term():
        v = atom()
        while peek() in ("*", "/"):
            op = take()
            r = atom()
            v = v * r if op == "*" else (v / r if r != 0 else float("nan"))
        return v

    def additive():
        v = term()
        while peek() in ("+", "-"):
            op = take()
            r = term()
            v = v + r if op == "+" else v - r
        return v

    return additive()


def build_ratio(spec, loaded, metas):
    ids = [t for t in TOKEN_RE.findall(spec["expr"]) if re.match(r"^[A-Za-z_]", t)]
    comps = {}
    for i in ids:
        if i not in loaded:
            raise RuntimeError(f"component {i} missing")
        comps[i] = loaded[i]
    all_ohlc = all(metas[i]["kind"] == "ohlc" for i in ids)
    # frequency of the result = finest component frequency; dates = union of component dates
    freq = min((metas[i]["freq"] for i in ids), key=lambda f: FREQ_RANK.get(f, 9))
    dates = sorted({b[0] for i in ids for b in comps[i]["bars"]})
    ptr = {i: 0 for i in ids}
    cur = {i: None for i in ids}
    bars = []
    for t in dates:
        for i in ids:
            bl = comps[i]["bars"]
            while ptr[i] < len(bl) and bl[ptr[i]][0] <= t:
                cur[i] = bl[ptr[i]]
                ptr[i] += 1
        if any(cur[i] is None for i in ids):
            continue
        try:
            if all_ohlc:
                vals = []
                for fi in (1, 2, 3, 4):
                    vals.append(eval_expr(spec["expr"], {i: cur[i][fi] for i in ids}))
                o, h, l, c = vals
                hi, lo = max(o, h, l, c), min(o, h, l, c)
                if any(not math.isfinite(x) for x in vals):
                    continue
                bars.append([t, sig(o), sig(hi), sig(lo), sig(c), 0])
            else:
                v = eval_expr(spec["expr"], {i: (cur[i][4] if len(cur[i]) > 2 else cur[i][1]) for i in ids})
                if not math.isfinite(v):
                    continue
                bars.append([t, sig(v)])
        except (KeyError, ZeroDivisionError, TypeError):
            continue
    if len(bars) < 5:
        raise RuntimeError(f"only {len(bars)} bars")
    kind = "ohlc" if all_ohlc else "value"
    src = "computed from " + ", ".join(f"{i} ({metas[i].get('source', '?')})" for i in ids)
    return bars, kind, freq, src


# ------------------------------------------------------------------ main
def main():
    status = {"updated": NOW.isoformat(timespec="seconds"), "series": {}, "crypto": {}}
    manifest_series = []
    loaded, metas = {}, {}

    if not SKIP_MACRO:
        log(f"== macro / TradFi series ({len(SERIES)}) ==")
        todo = [spec for spec in SERIES if not ONLY or spec["id"] in ONLY]
        if QUICK and not ONLY:
            todo = [spec for spec in todo if spec["sources"][0][0] in ("yahoo", "stooq")]
            log(f"   quick mode: {len(todo)} market series")
        t_all = time.time()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda sp: (sp, time.time(), fetch_one(sp)), todo))
        log(f"   fetched in {round(time.time() - t_all)}s")
        for spec, t0, (bars, src, key, errors) in results:
            sid = spec["id"]
            out = SERIES_DIR / f"{sid}.json"
            old = load_json(out)
            stale = False
            if bars is None:
                if old and old.get("bars"):
                    bars, src, key, stale = old["bars"], old.get("source_id", "?"), old.get("source_key", "?"), True
                    log(f"  !! {sid}: all sources failed, keeping previous data ({len(bars)} bars)")
                    for e in errors:
                        log(f"       {e[:220]}")
                else:
                    log(f"  XX {sid}: all sources failed, no data")
                    for e in errors:
                        log(f"       {e[:220]}")
                    status["series"][sid] = {"ok": False, "errors": errors}
                    continue
            if old and old.get("bars") and not stale and old.get("kind") == spec["kind"]:
                # keep history the source no longer serves (e.g. FRED's rolling 3-year window on ICE BofA data)
                merged = {b[0]: b for b in old["bars"]}
                for b in bars:
                    merged[b[0]] = b
                if len(merged) > len(bars):
                    log(f"     + {sid}: kept {len(merged) - len(bars)} older bars no longer served by the source")
                bars = [merged[t] for t in sorted(merged)]
            if spec["kind"] == "ohlc" and spec["group"] in CLEAN_TOL:
                bars = clean_ohlc(bars, CLEAN_TOL[spec["group"]])
            if spec.get("overlay"):
                # hand-maintained points win over the feed (e.g. PMI months a scraper misses)
                try:
                    ov = rows_to_bars(S.manual(spec["overlay"][1], MANUAL_DIR), spec["kind"])
                    merged = {b[0]: b for b in bars}
                    for b in ov:
                        merged[b[0]] = b
                    bars = [merged[t] for t in sorted(merged)]
                    log(f"     + {sid}: {len(ov)} manual points applied")
                except S.SourceError:
                    pass
            if spec.get("valid") and spec["kind"] == "value":
                lo_v, hi_v = spec["valid"]
                n0 = len(bars)
                bars = [b for b in bars if lo_v <= b[1] <= hi_v]
                if len(bars) != n0:
                    log(f"     ~ {sid}: dropped {n0 - len(bars)} readings outside {lo_v}-{hi_v}")
            obj = {"id": sid, "kind": spec["kind"], "freq": spec["freq"], "source_id": src, "source_key": key,
                   "updated": NOW.isoformat(timespec="seconds"), "bars": bars}
            dump_json(out, obj)
            meta = series_meta(spec, bars, src, key, stale)
            manifest_series.append(meta)
            loaded[sid], metas[sid] = obj, meta
            status["series"][sid] = {"ok": not stale, "source": f"{src}:{key}", "last": meta["last"], "n": len(bars),
                                     "errors": errors, "secs": round(time.time() - t0, 1)}
            log(f"  {'~~' if stale else 'ok'} {sid:<14} {src}:{key:<40} {len(bars):>6} bars  last {meta['last']}  {round(time.time()-t0,1)}s")

        log(f"== constructed series ({len(RATIOS)}) ==")
        old_manifest_series = {m["id"]: m for m in (load_json(DATA / "manifest.json") or {}).get("series", [])}
        for spec in RATIOS:
            sid = spec["id"]
            if ONLY and sid not in ONLY:
                continue
            out = SERIES_DIR / f"{sid}.json"
            try:
                # partial runs: components not fetched this time are taken from the files on disk
                for cid in [t for t in TOKEN_RE.findall(spec["expr"]) if re.match(r"^[A-Za-z_]", t)]:
                    if cid not in loaded:
                        prev = load_json(SERIES_DIR / f"{cid}.json")
                        if prev and prev.get("bars") and cid in old_manifest_series:
                            loaded[cid], metas[cid] = prev, old_manifest_series[cid]
                bars, kind, freq, src = build_ratio(spec, loaded, metas)
                obj = {"id": sid, "kind": kind, "freq": freq, "source_id": "computed", "source_key": spec["expr"],
                       "updated": NOW.isoformat(timespec="seconds"), "bars": bars}
                dump_json(out, obj)
                meta = series_meta(dict(spec, kind=kind, freq=freq, units=spec.get("units", "")), bars, "computed", spec["expr"], False)
                meta["source"] = src
                meta["source_url"] = ""
                manifest_series.append(meta)
                status["series"][sid] = {"ok": True, "source": spec["expr"], "last": meta["last"], "n": len(bars)}
                log(f"  ok {sid:<14} {spec['expr']:<36} {len(bars):>6} bars  last {meta['last']}")
            except Exception as e:  # noqa: BLE001
                old = load_json(out)
                if old and old.get("bars"):
                    meta = series_meta(dict(spec, kind=old["kind"], freq=old["freq"], units=spec.get("units", "")), old["bars"], "computed", spec["expr"], True)
                    manifest_series.append(meta)
                log(f"  XX {sid}: {e}")
                status["series"][sid] = {"ok": False, "errors": [str(e)]}

    # ------------------------------------------------------------ crypto
    crypto_manifest = []
    pools_path = CRYPTO_DIR / "pools.json"
    pools = load_json(pools_path) or {"resolved": {}, "candidates": {}}
    if not SKIP_CRYPTO:
        log(f"== PulseChain / HEX pairs ({len(CRYPTO)}) ==")
        for spec in CRYPTO:
            cid = spec["id"]
            if ONLY and cid not in ONLY:
                continue
            t0 = time.time()
            try:
                res = pools["resolved"].get(cid)
                if spec.get("pool") and (not res or res.get("pool") != spec["pool"].lower() or "side" not in res):
                    info = S.gt_pool_info(spec["network"], spec["pool"].lower())
                    want = (spec.get("token") or "").lower()
                    info["side"] = "quote" if want and info.get("quote_token") == want else "base"
                    res = info
                    pools["resolved"][cid] = res
                if not res or not res.get("pool"):
                    res, cands = S.gt_search_pool(spec["network"], spec["search"], spec.get("quotes", []), spec.get("token"), spec.get("quote_sym"))
                    pools["candidates"][cid] = [dict(name=n, pool=a, reserve_usd=round(r), base_token=b) for n, a, r, b in cands][:12]
                    if not res:
                        raise S.SourceError(f"no pool found for {spec['search']} on {spec['network']}; candidates: "
                                            + "; ".join(f"{n} ({round(r)}$)" for n, a, r, b in cands[:6]))
                    res["side"] = "base"
                    pools["resolved"][cid] = res
                side = res.get("side", "base")
                currency = spec.get("currency", "usd")
                day = S.gt_ohlcv_history(spec["network"], res["pool"], "day", 1, pages=1 if QUICK else 8, token=side, currency=currency)
                h4 = S.gt_ohlcv_history(spec["network"], res["pool"], "hour", 4, pages=1 if QUICK else 2, token=side, currency=currency)
                # deeper daily history (before GeckoTerminal's window) from an alternative feed, when configured
                deep_note = ""
                if QUICK:
                    prev_meta = next((c for c in (load_json(DATA / "manifest.json") or {}).get("crypto", []) if c["id"] == cid), None)
                    deep_note = (prev_meta or {}).get("deep_history", "")
                if spec.get("deep") and day and not QUICK:
                    dsrc, dkey = spec["deep"]
                    try:
                        first = day[0][0]
                        if dsrc == "cointrader":
                            drows, dlabel = S.cointrader_history(dkey), "CoinTrader.Pro (CoinMarketCap data, via hexchart.com)"
                        elif dsrc == "pulsex":
                            drows, dlabel = S.pulsex_history(**dkey), "PulseX pair day data (PulseChain subgraph, daily closes)"
                        else:
                            raise S.SourceError(f"unknown deep source {dsrc}")
                        deep = [r for r in drows if r[0] < first]
                        if deep:
                            day = deep + day
                            deep_note = f"{len(deep)} daily bars before {datetime.fromtimestamp(first, timezone.utc).date().isoformat()} from {dlabel}"
                            log(f"     + {cid}: {deep_note}")
                    except Exception as e:  # noqa: BLE001
                        log(f"     ~ {cid}: deep history unavailable: {str(e)[:120]}")
                for tf, rows in (("day", day), ("4h", h4)):
                    bars = [[t * 1000, sig(o), sig(h), sig(l), sig(c), sig(v, 6)] for t, o, h, l, c, v in rows]
                    prev = load_json(CRYPTO_DIR / f"{cid}_{tf}.json")
                    if prev and prev.get("bars") and prev.get("pool") == res["pool"]:
                        merged = {b[0]: b for b in prev["bars"]}
                        for b in bars:
                            merged[b[0]] = b
                        bars = [merged[t] for t in sorted(merged)]
                        if tf == "day":
                            day = [(b[0] // 1000, b[1], b[2], b[3], b[4], b[5]) for b in bars]
                        else:
                            h4 = [(b[0] // 1000, b[1], b[2], b[3], b[4], b[5]) for b in bars]
                    dump_json(CRYPTO_DIR / f"{cid}_{tf}.json", {"id": cid, "tf": tf, "pool": res["pool"], "network": spec["network"],
                                                                 "updated": NOW.isoformat(timespec="seconds"), "bars": bars})
                closes = [r[4] for r in day] or [1]
                last = datetime.fromtimestamp(day[-1][0], timezone.utc).date().isoformat() if day else None
                crypto_manifest.append(dict(
                    id=cid, name=spec["name"], group="PulseChain & HEX", network=spec["network"], pool=res["pool"], side=side, currency=currency,
                    units=spec.get("units", "USD"),
                    pool_name=res.get("name", ""), base_symbol=res.get("base_symbol", ""), quote_symbol=res.get("quote_symbol", ""),
                    deep_history=deep_note,
                    precision=auto_precision(closes), last=last, n_day=len(day), n_4h=len(h4),
                    source="GeckoTerminal", source_url=f"https://www.geckoterminal.com/{spec['network']}/pools/{res['pool']}",
                ))
                status["crypto"][cid] = {"ok": True, "pool": res["pool"], "name": res.get("name"), "n_day": len(day), "n_4h": len(h4),
                                         "secs": round(time.time() - t0, 1)}
                log(f"  ok {cid:<7} {res.get('name',''):<22} {res['pool']}  day {len(day):>4}  4h {len(h4):>4}  {round(time.time()-t0,1)}s")
            except Exception as e:  # noqa: BLE001
                log(f"  XX {cid}: {str(e)[:300]}")
                status["crypto"][cid] = {"ok": False, "errors": [str(e)[:400]]}
                # keep previously cached entry in the manifest if we have one
                old = load_json(CRYPTO_DIR / f"{cid}_day.json")
                if old and old.get("bars"):
                    closes = [b[4] for b in old["bars"]]
                    crypto_manifest.append(dict(id=cid, name=spec["name"], group="PulseChain & HEX", network=spec["network"],
                                                pool=old.get("pool"), pool_name="", base_symbol="", quote_symbol="",
                                                precision=auto_precision(closes),
                                                last=datetime.fromtimestamp(old["bars"][-1][0] / 1000, timezone.utc).date().isoformat(),
                                                n_day=len(old["bars"]), n_4h=0, source="GeckoTerminal (cached)", source_url="", stale=True))
        dump_json(pools_path, pools, compact=False)
    else:
        old_manifest = load_json(DATA / "manifest.json") or {}
        crypto_manifest = old_manifest.get("crypto", [])

    if ONLY or SKIP_MACRO or QUICK:
        # partial run: merge into the existing manifest instead of replacing it
        old_manifest = load_json(DATA / "manifest.json") or {}
        merged = {m["id"]: m for m in old_manifest.get("series", [])}
        for m in manifest_series:
            merged[m["id"]] = m
        manifest_series = list(merged.values())
        if (ONLY or QUICK) and not SKIP_CRYPTO:
            mergedc = {m["id"]: m for m in old_manifest.get("crypto", [])}
            for m in crypto_manifest:
                mergedc[m["id"]] = m
            crypto_manifest = list(mergedc.values())

    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    manifest_series.sort(key=lambda m: (order.get(m["group"], 99), [s["id"] for s in SERIES + RATIOS].index(m["id"]) if m["id"] in [s["id"] for s in SERIES + RATIOS] else 999))
    manifest = {
        "updated": NOW.isoformat(timespec="seconds"),
        "groups": GROUP_ORDER,
        "series": manifest_series,
        "crypto": crypto_manifest,
        "attribution": {
            "FRED": "Federal Reserve Bank of St. Louis, FRED — public domain / source terms apply",
            "ECB": "European Central Bank Data Portal — free reuse with attribution",
            "Bundesbank": "Deutsche Bundesbank statistics — free reuse with attribution",
            "DBnomics": "DBnomics aggregator (ISM, Eurostat, IMF) — source terms apply",
            "Yahoo Finance": "Unofficial feed; quotes may be delayed; for information only",
            "Stooq": "stooq.com — for information only",
            "GeckoTerminal": "GeckoTerminal public API (CoinGecko) — DEX on-chain data",
        },
    }
    dump_json(DATA / "manifest.json", manifest, compact=False)
    dump_json(DATA / "status.json", status, compact=False)

    ok = sum(1 for v in status["series"].values() if v.get("ok"))
    okc = sum(1 for v in status["crypto"].values() if v.get("ok"))
    log(f"== done: {ok}/{len(status['series'])} series ok, {okc}/{len(status['crypto'])} crypto ok ==")
    bad = [k for k, v in status["series"].items() if not v.get("ok")] + [k for k, v in status["crypto"].items() if not v.get("ok")]
    if bad:
        log("   needs attention: " + ", ".join(bad))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
