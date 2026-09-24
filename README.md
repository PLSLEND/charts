# PLSLEND Charts

Free community chart room: PulseChain / HEX pairs next to the macro series that move them,
with the tools people miss most when a paid platform pulls the ladder up — trend lines, a
price-range ruler, trend-based Fibonacci extensions, SuperTrend (ATR 10, factor 2.8), RSI 14,
MACD 12/26/9, log scale, weekly/monthly aggregation, ratios and spreads.

Live: https://plslend.github.io/charts/ (to become `charts.plslend.com`)

No account, no tracking, no cookies. Drawings are stored in the visitor's own browser
(localStorage) and can be exported/imported as a file.

## How it works

```
fetch/                Python job (GitHub Actions, twice a day)
  series_config.py    the catalog: every series, its group, native frequency and source candidates
  sources.py          adapters: FRED, Yahoo Finance, Stooq, ECB Data Portal, Bundesbank, DBnomics, PBoC, GeckoTerminal
  fetch_all.py        pulls everything, builds ratios, caches on-chain candles, writes data/
  probe.py            diagnostics for hard-to-find series keys (workflow "Probe sources")
data/
  manifest.json       catalog + metadata read by the app
  status.json         what worked in the last run (also shown in the Actions job summary)
  series/<ID>.json    {"bars": [[timestamp_ms, value] | [timestamp_ms, o, h, l, c, v], ...]}
  crypto/             resolved GeckoTerminal pools + cached daily / 4h candles (fallback)
  manual/<ID>.csv     hand-maintained overrides for series without a free feed
index.html, app.js    the app (vanilla JS, no build step)
lib/klinecharts.min.js  KLineChart 10.x (Apache-2.0)
```

On-chain pairs load live from the GeckoTerminal public API in the browser; if that fails
(rate limit, outage) the cached copy from the last job run is used and the footer says so.

## Adding a series

Add an entry to `SERIES` in `fetch/series_config.py` with one or more `(source, key)`
candidates — the first that returns data wins and is recorded as the attribution. Ratios go in
`RATIOS` (`expr` over series ids). Pairs go in `CRYPTO` (symbol search + preferred quotes, or a
fixed pool address). Run the "Update data" workflow, check the job summary.

## Data sources and terms

FRED (St. Louis Fed), ECB Data Portal, Deutsche Bundesbank, DBnomics (ISM, Eurostat, IMF),
Yahoo Finance (unofficial), Stooq, GeckoTerminal. Quotes may be delayed. For information only —
not financial advice.

## Licence

Code: MIT. KLineChart: Apache-2.0 (see `lib/`). Data: each source's own terms.
