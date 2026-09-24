/* PLSLEND Charts — community chart room. Vanilla JS on KLineChart (Apache-2.0).
   Data: ./data/* written by the GitHub Actions job (see fetch/), GeckoTerminal live for on-chain pairs. */
(function () {
  'use strict';
  const kc = window.klinecharts;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const LS = 'plslend.charts.';
  const DATA = './data/';
  const GT = 'https://api.geckoterminal.com/api/v2';
  const DAY = 86400000;

  const C = {
    up: '#f4f2fa', down: '#3fa9ff', trendUp: '#a86bff', trendDown: '#ff3fd1', pink: '#ff3fd1', violet: '#8a4dff', blue: '#3fa9ff', accent: '#a86bff',
    text: '#e8e5f2', muted: '#8f8aa8', dim: '#5e5975', grid: '#1c1929', line: '#262238', panel: '#13111d', bg: '#0b0a12', warn: '#ffb347',
  };
  const FIB_LEVELS = [
    [0, '#8f8aa8'], [0.382, '#ffb347'], [0.5, '#f4f2fa'], [0.618, '#2ec4b6'], [1, '#8f8aa8'],
    [1.382, '#3fa9ff'], [1.618, '#8a4dff'], [2, '#a86bff'], [2.618, '#ff8ac2'], [3.618, '#ff3fd1'], [4.236, '#ffb347'],
  ];
  const TF_PERIOD = { '4h': { type: 'hour', span: 4 }, D: { type: 'day', span: 1 }, W: { type: 'week', span: 1 }, M: { type: 'month', span: 1 } };
  const FREQ_TFS = { '4h': ['4h', 'D', 'W', 'M'], D: ['D', 'W', 'M'], W: ['W', 'M'], M: ['M'], Q: ['M'] };
  const FREQ_LABEL = { '4h': '4-hour', D: 'daily', W: 'weekly', M: 'monthly', Q: 'quarterly' };

  // ------------------------------------------------------------------ state
  const st = {
    manifest: null, symbols: new Map(), current: null, tf: 'D', native: null, // native: KLineData[] at the series' own frequency
    chartType: null, log: false, ind: { st: true, rsi: false, macd: false }, stp: [10, 2.8], magnet: false, tool: 'cursor',
    drawingId: null, selectedId: null, suppress: false, cache: new Map(), custom: [], pools: [],
  };
  const pref = (k, d) => { try { const v = localStorage.getItem(LS + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
  const setPref = (k, v) => { try { localStorage.setItem(LS + k, JSON.stringify(v)); } catch (e) { /* private mode */ } };

  // ------------------------------------------------------------------ helpers
  const fmtNum = (v, p) => {
    if (v === null || v === undefined || !isFinite(v)) return '—';
    const a = Math.abs(v);
    if (a >= 1e9 && p <= 1) return (v / 1e9).toFixed(2) + 'B';
    if (a >= 1e6 && p <= 1) return (v / 1e6).toFixed(2) + 'M';
    return v.toLocaleString('en-US', { minimumFractionDigits: Math.min(p, 10), maximumFractionDigits: Math.min(p, 10) });
  };
  const fmtDate = (ts, tf) => {
    const d = new Date(ts);
    const iso = d.toISOString();
    if (tf === '4h') return iso.slice(0, 16).replace('T', ' ');
    if (tf === 'M') return iso.slice(0, 7);
    return iso.slice(0, 10);
  };
  const isoWeekStart = (ts) => { const d = new Date(ts); const day = (d.getUTCDay() + 6) % 7; d.setUTCHours(0, 0, 0, 0); return d.getTime() - day * DAY; };
  const monthStart = (ts) => { const d = new Date(ts); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1); };
  const toast = (msg, ms = 2200) => { const el = $('#overlaymsg'); el.textContent = msg; el.classList.add('show'); clearTimeout(toast.t); if (ms) toast.t = setTimeout(() => el.classList.remove('show'), ms); };
  const loading = (on) => $('#loading').classList.toggle('show', on);
  const autoPrecision = (vals) => {
    const a = vals.filter((v) => v && isFinite(v)).map(Math.abs).slice(-500).sort((x, y) => x - y);
    if (!a.length) return 2;
    const m = a[Math.floor(a.length / 2)];
    return m >= 1000 ? 0 : m >= 100 ? 1 : m >= 10 ? 2 : m >= 1 ? 3 : m >= 0.1 ? 4 : m >= 0.01 ? 5 : m >= 1e-4 ? 7 : 10;
  };

  function barsToKline(bars) {
    if (!bars || !bars.length) return [];
    if (bars[0].length === 2) return bars.map((b) => ({ timestamp: b[0], open: b[1], high: b[1], low: b[1], close: b[1], volume: 0 }));
    return bars.map((b) => ({ timestamp: b[0], open: b[1], high: b[2], low: b[3], close: b[4], volume: b[5] || 0 }));
  }
  function aggregate(data, tf) {
    const keyOf = tf === 'W' ? isoWeekStart : tf === 'M' ? monthStart : null;
    if (!keyOf) return data;
    const out = [];
    let cur = null;
    for (const d of data) {
      const k = keyOf(d.timestamp);
      if (!cur || cur.timestamp !== k) { cur = { timestamp: k, open: d.open, high: d.high, low: d.low, close: d.close, volume: d.volume || 0 }; out.push(cur); }
      else { cur.high = Math.max(cur.high, d.high); cur.low = Math.min(cur.low, d.low); cur.close = d.close; cur.volume += d.volume || 0; }
    }
    return out;
  }

  // ------------------------------------------------------------------ chart styles
  const STYLES = {
    grid: { horizontal: { color: C.grid, style: 'solid' }, vertical: { color: C.grid, style: 'solid' } },
    candle: {
      bar: { upColor: C.up, downColor: C.down, noChangeColor: C.muted, upBorderColor: C.up, downBorderColor: C.down, noChangeBorderColor: C.muted, upWickColor: C.up, downWickColor: C.down, noChangeWickColor: C.muted },
      area: { lineSize: 2, lineColor: C.accent, backgroundColor: [{ offset: 0, color: 'rgba(168,107,255,0.02)' }, { offset: 1, color: 'rgba(168,107,255,0.22)' }], point: { color: C.pink, rippleColor: 'rgba(255,63,209,0.3)', animation: false } },
      priceMark: { high: { color: C.muted }, low: { color: C.muted }, last: { upColor: C.up, downColor: C.down, noChangeColor: C.muted, text: { color: '#fff' } } },
      tooltip: {
        showRule: 'follow_cross', showType: 'standard',
        title: { color: C.muted, template: '{ticker} · {period}' },
        legend: { color: C.text, defaultValue: '—' },
        rect: { color: 'rgba(19,17,29,0.92)', borderColor: C.line },
      },
    },
    indicator: {
      lines: [{ color: C.accent, size: 1.5 }, { color: C.blue, size: 1 }, { color: C.pink, size: 1 }, { color: C.warn, size: 1 }, { color: C.up, size: 1 }],
      bars: [{ upColor: 'rgba(244,242,250,0.7)', downColor: 'rgba(63,169,255,0.7)', noChangeColor: C.muted }],
      tooltip: { title: { color: C.muted }, legend: { color: C.text } },
      lastValueMark: { show: false },
    },
    xAxis: { axisLine: { color: C.line }, tickLine: { color: C.line }, tickText: { color: C.muted } },
    yAxis: { axisLine: { color: C.line }, tickLine: { color: C.line }, tickText: { color: C.muted } },
    separator: { color: C.line, activeBackgroundColor: 'rgba(138,77,255,0.12)' },
    crosshair: {
      horizontal: { line: { color: C.dim }, text: { backgroundColor: C.violet, borderColor: C.violet, color: '#fff' } },
      vertical: { line: { color: C.dim }, text: { backgroundColor: C.violet, borderColor: C.violet, color: '#fff' } },
    },
    overlay: {
      point: { color: C.pink, borderColor: 'rgba(255,63,209,0.35)', activeColor: C.pink, activeBorderColor: 'rgba(255,63,209,0.35)' },
      line: { color: C.blue, size: 1.5 },
      text: { backgroundColor: C.violet, borderColor: C.violet, color: '#fff' },
      rect: { color: 'rgba(63,169,255,0.12)', borderColor: C.blue },
    },
  };

  // ------------------------------------------------------------------ indicators (TradingView-compatible maths)
  kc.registerIndicator({
    name: 'SUPERTREND', shortName: 'SuperTrend', series: 'price', precision: 2, calcParams: [10, 2.8], shouldOhlc: true,
    figures: [
      { key: 'up', title: 'Up: ', type: 'line', styles: () => ({ color: C.trendUp, size: 2 }) },
      { key: 'dn', title: 'Down: ', type: 'line', styles: () => ({ color: C.trendDown, size: 2 }) },
    ],
    calc: (list, ind) => {
      const [len, mult] = ind.calcParams;
      let atr = null, trSum = 0, prevUpper = null, prevLower = null, trend = 1, prevST = null, pc = null;
      return list.map((d, i) => {
        const tr = pc === null ? d.high - d.low : Math.max(d.high - d.low, Math.abs(d.high - pc), Math.abs(d.low - pc));
        if (i < len) { trSum += tr; if (i === len - 1) atr = trSum / len; }
        else atr = (atr * (len - 1) + tr) / len;
        const r = {};
        if (atr !== null) {
          const hl2 = (d.high + d.low) / 2;
          let upper = hl2 + mult * atr, lower = hl2 - mult * atr;
          if (prevLower !== null && !(lower > prevLower || pc < prevLower)) lower = prevLower;
          if (prevUpper !== null && !(upper < prevUpper || pc > prevUpper)) upper = prevUpper;
          if (prevST === null) trend = 1;
          else if (prevST === prevUpper) trend = d.close > upper ? 1 : -1;
          else trend = d.close < lower ? -1 : 1;
          const stv = trend === 1 ? lower : upper;
          if (trend === 1) r.up = stv; else r.dn = stv;
          r.trend = trend;
          prevUpper = upper; prevLower = lower; prevST = stv;
        }
        pc = d.close;
        return r;
      });
    },
  });
  kc.registerIndicator({
    name: 'RSI_TV', shortName: 'RSI', precision: 2, calcParams: [14], minValue: 0, maxValue: 100,
    figures: [
      { key: 'rsi', title: 'RSI: ', type: 'line' },
      { key: 'ob', title: '', type: 'line', styles: () => ({ color: 'rgba(143,138,168,0.45)', style: 'dashed', size: 1 }) },
      { key: 'mid', title: '', type: 'line', styles: () => ({ color: 'rgba(143,138,168,0.25)', style: 'dashed', size: 1 }) },
      { key: 'os', title: '', type: 'line', styles: () => ({ color: 'rgba(143,138,168,0.45)', style: 'dashed', size: 1 }) },
    ],
    calc: (list, ind) => {
      const len = ind.calcParams[0];
      let ag = 0, al = 0, gs = 0, ls = 0;
      return list.map((d, i) => {
        const r = { ob: 70, mid: 50, os: 30 };
        if (i === 0) return r;
        const ch = d.close - list[i - 1].close, g = Math.max(ch, 0), l = Math.max(-ch, 0);
        if (i <= len) { gs += g; ls += l; if (i === len) { ag = gs / len; al = ls / len; } }
        else { ag = (ag * (len - 1) + g) / len; al = (al * (len - 1) + l) / len; }
        if (i >= len) r.rsi = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
        return r;
      });
    },
  });
  kc.registerIndicator({
    name: 'MACD_TV', shortName: 'MACD', precision: 4, calcParams: [12, 26, 9],
    figures: [
      {
        key: 'hist', title: 'Hist: ', type: 'bar', baseValue: 0,
        styles: ({ data }) => {
          const p = data.prev && data.prev.hist, c = data.current && data.current.hist;
          const rising = p === undefined || p === null || c >= p;
          const color = c >= 0 ? (rising ? 'rgba(244,242,250,0.85)' : 'rgba(244,242,250,0.4)') : (rising ? 'rgba(63,169,255,0.45)' : 'rgba(63,169,255,0.9)');
          return { style: 'fill', color, borderColor: color };
        },
      },
      { key: 'macd', title: 'MACD: ', type: 'line', styles: () => ({ color: C.blue, size: 1.4 }) },
      { key: 'signal', title: 'Signal: ', type: 'line', styles: () => ({ color: C.warn, size: 1.2 }) },
    ],
    calc: (list, ind) => {
      const [f, s, sig] = ind.calcParams;
      let ef = null, es = null, esig = null;
      const kf = 2 / (f + 1), ks = 2 / (s + 1), ksig = 2 / (sig + 1);
      return list.map((d, i) => {
        ef = ef === null ? d.close : d.close * kf + ef * (1 - kf);
        es = es === null ? d.close : d.close * ks + es * (1 - ks);
        const r = {};
        if (i >= s - 1) {
          const macd = ef - es;
          esig = esig === null ? macd : macd * ksig + esig * (1 - ksig);
          if (i >= s + sig - 2) { r.macd = macd; r.signal = esig; r.hist = macd - esig; }
        }
        return r;
      });
    },
  });

  // ------------------------------------------------------------------ custom overlays
  const textStyle = (bg) => ({ backgroundColor: bg, borderColor: bg, color: '#fff', size: 12, paddingLeft: 6, paddingRight: 6, paddingTop: 3, paddingBottom: 3, borderRadius: 4 });
  kc.registerOverlay({
    name: 'priceRuler', totalStep: 3, needDefaultPointFigure: true, needDefaultXAxisFigure: true, needDefaultYAxisFigure: true,
    createPointFigures: ({ chart, overlay, coordinates }) => {
      if (coordinates.length < 2) return [];
      const [p0, p1] = overlay.points, [c0, c1] = coordinates;
      const dv = (p1.value || 0) - (p0.value || 0);
      const pct = p0.value ? (dv / Math.abs(p0.value)) * 100 : 0;
      const bs = chart.getBarSpace().bar || 1;
      const bars = Math.round(Math.abs(c1.x - c0.x) / bs);
      const days = Math.round(Math.abs((p1.timestamp || 0) - (p0.timestamp || 0)) / DAY);
      const up = dv >= 0, col = up ? C.trendUp : C.trendDown;
      const prec = (chart.getSymbol() || {}).pricePrecision ?? 2;
      const x = Math.min(c0.x, c1.x), y = Math.min(c0.y, c1.y), w = Math.abs(c1.x - c0.x), h = Math.abs(c1.y - c0.y);
      const tx = x + w / 2, ty = up ? y - 6 : y + h + 6, bl = up ? 'bottom' : 'top', dir = up ? -1 : 1;
      return [
        { type: 'rect', attrs: { x, y, width: w, height: h }, styles: { style: 'stroke_fill', color: up ? 'rgba(168,107,255,0.12)' : 'rgba(255,63,209,0.12)', borderColor: col, borderSize: 1 } },
        { type: 'text', ignoreEvent: true, attrs: { x: tx, y: ty, text: `${dv >= 0 ? '+' : ''}${fmtNum(dv, prec)}  (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`, align: 'center', baseline: bl }, styles: textStyle(col) },
        { type: 'text', ignoreEvent: true, attrs: { x: tx, y: ty + dir * 22, text: `${bars} bars · ${days} days`, align: 'center', baseline: bl }, styles: textStyle('rgba(19,17,29,0.9)') },
      ];
    },
  });
  kc.registerOverlay({
    name: 'fibExtension', totalStep: 4, needDefaultPointFigure: true, needDefaultXAxisFigure: false, needDefaultYAxisFigure: true,
    createPointFigures: ({ chart, overlay, coordinates, bounding, yAxis }) => {
      const pts = overlay.points, figs = [];
      const guide = { style: 'dashed', color: 'rgba(143,138,168,0.7)', size: 1 };
      if (coordinates.length >= 2) figs.push({ type: 'line', attrs: { coordinates: [coordinates[0], coordinates[1]] }, styles: guide });
      if (coordinates.length >= 3 && pts[0].value !== undefined && pts[1].value !== undefined && pts[2].value !== undefined) {
        figs.push({ type: 'line', attrs: { coordinates: [coordinates[1], coordinates[2]] }, styles: guide });
        const range = pts[1].value - pts[0].value, base = pts[2].value;
        const prec = (chart.getSymbol() || {}).pricePrecision ?? 2;
        const x0 = coordinates[2].x;
        for (const [lv, color] of FIB_LEVELS) {
          const v = base + range * lv;
          const y = yAxis ? yAxis.convertToPixel(v) : coordinates[2].y;
          if (!isFinite(y) || y < -50 || y > bounding.height + 50) continue;
          figs.push({ type: 'line', attrs: { coordinates: [{ x: x0, y }, { x: bounding.width, y }] }, styles: { color, size: 1 } });
          figs.push({ type: 'text', ignoreEvent: true, attrs: { x: x0 + 4, y: y - 2, text: `${lv} (${fmtNum(v, prec)})`, baseline: 'bottom' }, styles: { color, backgroundColor: 'transparent', borderSize: 0, size: 11, paddingLeft: 0, paddingRight: 0, paddingTop: 0, paddingBottom: 0 } });
        }
      }
      return figs;
    },
  });
  const PERSISTED = new Set(['segment', 'rayLine', 'horizontalStraightLine', 'priceRuler', 'fibExtension']);

  // ------------------------------------------------------------------ log axis (the built-in one mislabels prices < 1)
  const LOG_FLOOR = 1e-12;
  const toReal = (v) => Math.log10(Math.max(v, LOG_FLOOR));
  const toValue = (r) => Math.pow(10, r);
  kc.registerYAxis({
    name: 'logsafe',
    minSpan: () => 0.0001,
    valueToRealValue: toReal,
    realValueToDisplayValue: toValue,
    displayValueToRealValue: toReal,
    realValueToValue: toValue,
    createRange: ({ defaultRange }) => {
      const { from, to, range } = defaultRange;
      const realFrom = toReal(from), realTo = toReal(to);
      return { from, to, range, realFrom, realTo, realRange: realTo - realFrom, displayFrom: from, displayTo: to, displayRange: range };
    },
    createTicks: ({ range, bounding, defaultTicks }) => {
      const { realFrom, realTo, realRange } = range;
      if (!(realRange > 0) || !isFinite(realRange)) return defaultTicks;
      const prec = (st.current && st.current.precision) || 2;
      const mant = realRange > 4 ? [1] : realRange > 1.6 ? [1, 2, 5] : realRange > 0.6 ? [1, 1.5, 2, 3, 5, 7] : null;
      const ticks = [];
      if (mant) {
        for (let e = Math.floor(realFrom) - 1; e <= Math.ceil(realTo); e++) {
          for (const m of mant) {
            const v = m * Math.pow(10, e), r = toReal(v);
            if (r < realFrom || r > realTo) continue;
            ticks.push({ coord: bounding.height - ((r - realFrom) / realRange) * bounding.height, value: v, text: fmtNum(v, prec) });
          }
        }
      } else {
        const lo = toValue(realFrom), hi = toValue(realTo), n = 8;
        const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
        const step = [1, 2, 2.5, 5, 10].map((x) => x * mag).find((x) => x >= raw) || raw;
        for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
          const r = toReal(v);
          ticks.push({ coord: bounding.height - ((r - realFrom) / realRange) * bounding.height, value: v, text: fmtNum(v, prec) });
        }
      }
      return ticks.length ? ticks : defaultTicks;
    },
  });

  // ------------------------------------------------------------------ chart
  const chart = kc.init('chart', {
    timezone: 'UTC', locale: 'en-US', styles: STYLES, decimalFold: { threshold: 12 },
    formatter: { formatDate: ({ timestamp, type }) => fmtDate(timestamp, st.tf === '4h' ? '4h' : (type === 'xAxis' && st.tf === 'M' ? 'M' : 'D')) },
  });
  chart.setDataLoader({
    getBars: ({ type, period, callback }) => {
      if (type !== 'init' || !st.native) { callback([], false); return; }
      const tf = st.tf;
      const data = tf === '4h' ? st.native : aggregate(st.native, tf);
      callback(data, false);
      applyPanes();
      restoreDrawings();
      updateHeader(data);
    },
  });
  window.addEventListener('resize', () => chart.resize());
  window.PLSLENDCharts = { chart, state: st, version: '0.1.0' };

  function canLog() { return !!(st.native && st.native.length && st.native.every((d) => d.low > 0)); }
  function applyPanes() {
    const s = st.current;
    if (!s) return;
    const ct = st.chartType || (s.kind === 'ohlc' ? 'candle' : 'area');
    chart.setStyles({
      candle: {
        type: ct === 'area' ? 'area' : 'candle_solid',
        tooltip: { legend: { template: s.kind === 'ohlc' && ct === 'candle'
          ? [{ title: '', value: '{time}' }, { title: 'O', value: '{open}' }, { title: 'H', value: '{high}' }, { title: 'L', value: '{low}' }, { title: 'C', value: '{close}' }, { title: 'Vol', value: '{volume}' }]
          : [{ title: '', value: '{time}' }, { title: 'value', value: '{close}' }] } },
      },
    });
    $$('#ctype button').forEach((b) => b.classList.toggle('on', b.dataset.ct === ct));
    chart.overrideYAxis({ paneId: 'candle_pane', name: st.log && canLog() ? 'logsafe' : 'normal' });
    $('#logbtn').disabled = !canLog(); $('#logbtn').title = canLog() ? 'Logarithmic price scale' : 'Log scale needs all-positive values';
    $('#logbtn').classList.toggle('on', st.log);
    // indicators
    const have = (n) => chart.getIndicators({ name: n }).length > 0;
    if (st.ind.st && !have('SUPERTREND')) chart.createIndicator({ name: 'SUPERTREND', paneId: 'candle_pane', precision: s.precision, calcParams: st.stp.slice() }, true);
    if (!st.ind.st && have('SUPERTREND')) chart.removeIndicator({ name: 'SUPERTREND' });
    if (have('SUPERTREND')) chart.overrideIndicator({ name: 'SUPERTREND', precision: s.precision, calcParams: st.stp.slice() });
    $('#stparams').classList.toggle('show', st.ind.st); $('#stLen').value = st.stp[0]; $('#stMult').value = st.stp[1];
    if (st.ind.rsi && !have('RSI_TV')) { chart.createIndicator({ name: 'RSI_TV', paneId: 'pane_rsi' }); chart.setPaneOptions({ id: 'pane_rsi', height: 110, minHeight: 60 }); }
    if (!st.ind.rsi && have('RSI_TV')) chart.removeIndicator({ paneId: 'pane_rsi' });
    if (st.ind.macd && !have('MACD_TV')) { chart.createIndicator({ name: 'MACD_TV', paneId: 'pane_macd', precision: Math.min(s.precision + 2, 10) }); chart.setPaneOptions({ id: 'pane_macd', height: 120, minHeight: 60 }); }
    if (!st.ind.macd && have('MACD_TV')) chart.removeIndicator({ paneId: 'pane_macd' });
    if (have('MACD_TV')) chart.overrideIndicator({ name: 'MACD_TV', precision: Math.min(s.precision + 2, 10) });
    $('#ind-st').classList.toggle('on', st.ind.st); $('#ind-rsi').classList.toggle('on', st.ind.rsi); $('#ind-macd').classList.toggle('on', st.ind.macd);
  }

  // ------------------------------------------------------------------ drawings persistence
  const dkey = (id) => LS + 'draw.' + id;
  function saveDrawings() {
    if (st.suppress || !st.current) return;
    const ovs = chart.getOverlays().filter((o) => PERSISTED.has(o.name) && o.currentStep === -1 && o.points.length >= o.totalStep - 1);
    const data = ovs.map((o) => ({ name: o.name, paneId: o.paneId, points: o.points.map((p) => ({ timestamp: p.timestamp, value: p.value })), lock: !!o.lock }));
    try { if (data.length) localStorage.setItem(dkey(st.current.id), JSON.stringify({ v: 1, id: st.current.id, saved: Date.now(), overlays: data })); else localStorage.removeItem(dkey(st.current.id)); } catch (e) { /* ignore */ }
  }
  function overlayEvents() {
    return {
      onDrawEnd: () => { st.drawingId = null; setTool('cursor'); saveDrawings(); },
      onPressedMoveEnd: () => saveDrawings(),
      onSelected: (e) => { st.selectedId = e.overlay.id; },
      onDeselected: (e) => { if (st.selectedId === e.overlay.id) st.selectedId = null; },
      onRemoved: () => { if (!st.suppress) saveDrawings(); },
    };
  }
  function restoreDrawings() {
    if (!st.current) return;
    st.suppress = true;
    chart.removeOverlay();
    st.selectedId = null; st.drawingId = null;
    try {
      const raw = localStorage.getItem(dkey(st.current.id));
      if (raw) {
        const saved = JSON.parse(raw);
        for (const o of saved.overlays || []) {
          if (!PERSISTED.has(o.name)) continue;
          chart.createOverlay({ name: o.name, paneId: o.paneId || 'candle_pane', points: o.points, lock: !!o.lock, mode: 'normal', ...overlayEvents() });
        }
      }
    } catch (e) { console.warn('restore drawings failed', e); }
    st.suppress = false;
  }
  function setTool(tool) {
    if (st.drawingId) { st.suppress = true; chart.removeOverlay({ id: st.drawingId }); st.suppress = false; st.drawingId = null; }
    st.tool = tool;
    $$('#toolbar [data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === tool));
    if (tool !== 'cursor' && st.native) {
      const id = chart.createOverlay({ name: tool, paneId: 'candle_pane', mode: st.magnet ? 'weak_magnet' : 'normal', ...overlayEvents() });
      st.drawingId = Array.isArray(id) ? id[0] : id;
      toast({ segment: 'Trend line: click start, then end', rayLine: 'Ray: click start, then direction', horizontalStraightLine: 'Horizontal line: click a level', priceRuler: 'Ruler: click start, then end', fibExtension: 'Fib extension: click A, B, then C' }[tool] || '', 3000);
    }
  }
  function deleteSelected() {
    if (st.selectedId) { chart.removeOverlay({ id: st.selectedId }); st.selectedId = null; saveDrawings(); toast('Drawing deleted'); }
    else toast('Click a drawing first, then delete');
  }
  function deleteAll() {
    if (!st.current) return;
    if (!confirm(`Delete all drawings on ${st.current.id}?`)) return;
    chart.removeOverlay(); saveDrawings(); toast('All drawings on this symbol deleted');
  }
  function exportDrawings() {
    const out = { app: 'PLSLEND Charts', exported: new Date().toISOString(), drawings: {}, custom: st.custom, pools: st.pools };
    for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (k && k.startsWith(LS + 'draw.')) out.drawings[k.slice((LS + 'draw.').length)] = JSON.parse(localStorage.getItem(k)); }
    const blob = new Blob([JSON.stringify(out, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `plslend-charts-drawings-${new Date().toISOString().slice(0, 10)}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }
  function importDrawings(file) {
    const rd = new FileReader();
    rd.onload = () => {
      try {
        const js = JSON.parse(rd.result);
        let n = 0;
        for (const [id, v] of Object.entries(js.drawings || {})) { localStorage.setItem(dkey(id), JSON.stringify(v)); n += (v.overlays || []).length; }
        if (Array.isArray(js.custom)) { for (const c of js.custom) if (!st.custom.some((x) => x.id === c.id)) st.custom.push(c); setPref('custom', st.custom); }
        if (Array.isArray(js.pools)) { for (const p of js.pools) if (!st.pools.some((x) => x.id === p.id)) st.pools.push(p); setPref('pools', st.pools); }
        buildSymbols(); renderList(); restoreDrawings();
        toast(`Imported ${n} drawings`);
      } catch (e) { toast('Import failed: not a drawings file'); }
    };
    rd.readAsText(file);
  }

  // ------------------------------------------------------------------ data loading
  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return r.json();
  }
  const cacheGet = (k) => { const c = st.cache.get(k); return c && Date.now() - c.t < 5 * 60000 ? c.v : null; };
  const cacheSet = (k, v) => st.cache.set(k, { t: Date.now(), v });

  async function loadSeries(s) {
    const k = 'series:' + s.id;
    const c = cacheGet(k); if (c) return c;
    let data;
    if (s.custom) data = await computeCustom(s);
    else data = barsToKline((await fetchJSON(DATA + s.file + '?v=' + encodeURIComponent(st.manifest.updated || ''))).bars);
    cacheSet(k, data);
    return data;
  }
  async function gtOhlcv(network, pool, tf, pages, before, side) {
    // GeckoTerminal public API: ~6 months per daily page, 1000 bars per 4h page; 401 = end of the free window
    const path = tf === '4h' ? 'hour?aggregate=4' : 'day?aggregate=1';
    const rows = [];
    for (let p = 0; p < pages; p++) {
      const url = `${GT}/networks/${network}/pools/${pool}/ohlcv/${path}&limit=1000&currency=usd&token=${side || 'base'}${before ? '&before_timestamp=' + before : ''}`;
      const r = await fetch(url, { headers: { Accept: 'application/json;version=20230302' } });
      if (r.status === 401) break;
      if (r.status === 429) { await new Promise((res) => setTimeout(res, 2500)); p--; continue; }
      if (!r.ok) throw new Error('GeckoTerminal ' + r.status);
      const list = (((await r.json()).data || {}).attributes || {}).ohlcv_list || [];
      if (list.length < 2) break;
      rows.push(...list);
      before = Math.min(...list.map((x) => x[0])) - 1;
    }
    const seen = new Set(); const out = [];
    for (const [t, o, h, l, c, v] of rows.sort((a, b) => a[0] - b[0])) { if (!seen.has(t) && o != null) { seen.add(t); out.push({ timestamp: t * 1000, open: +o, high: +h, low: +l, close: +c, volume: +v || 0 }); } }
    return out;
  }
  function mergeBars(base, fresh) {
    if (!base.length) return fresh;
    if (!fresh.length) return base;
    const m = new Map(base.map((b) => [b.timestamp, b]));
    for (const b of fresh) m.set(b.timestamp, b);
    return Array.from(m.values()).sort((a, b) => a.timestamp - b.timestamp);
  }
  async function loadCrypto(s, tf) {
    const want = tf === '4h' ? '4h' : 'day';
    const k = `crypto:${s.id}:${want}`;
    const c = cacheGet(k); if (c) return c;
    // 1) cached history from the data job (instant, deep), 2) live newest page from GeckoTerminal merged on top
    let cached = [];
    if (!s.userPool) {
      try { cached = barsToKline((await fetchJSON(`${DATA}crypto/${s.id}_${want}.json?v=${encodeURIComponent(st.manifest.updated || '')}`)).bars); } catch (e) { cached = []; }
    }
    let live = [];
    try { live = await gtOhlcv(s.network, s.pool, want, cached.length ? 1 : (want === '4h' ? 3 : 8), null, s.side); } catch (e) { live = []; }
    s.live = live.length > 0;
    const data = mergeBars(cached, live);
    if (!data.length) throw new Error('no candles from GeckoTerminal' + (s.userPool ? '' : ' or cache'));
    cacheSet(k, data);
    return data;
  }
  async function computeCustom(s) {
    const A = st.symbols.get(s.a), B = st.symbols.get(s.b);
    if (!A || !B) throw new Error('missing component');
    const [da, db] = await Promise.all([A.crypto ? loadCrypto(A, 'D') : loadSeries(A), B.crypto ? loadCrypto(B, 'D') : loadSeries(B)]);
    const ts = Array.from(new Set([...da.map((x) => x.timestamp), ...db.map((x) => x.timestamp)])).sort((x, y) => x - y);
    let ia = 0, ib = 0, ca = null, cb = null; const out = [];
    const op = { '/': (x, y) => (y ? x / y : NaN), '-': (x, y) => x - y, '*': (x, y) => x * y, '+': (x, y) => x + y }[s.op];
    for (const t of ts) {
      while (ia < da.length && da[ia].timestamp <= t) ca = da[ia++];
      while (ib < db.length && db[ib].timestamp <= t) cb = db[ib++];
      if (!ca || !cb) continue;
      const v = op(ca.close, cb.close);
      if (isFinite(v)) out.push({ timestamp: t, open: v, high: v, low: v, close: v, volume: 0 });
    }
    return out;
  }

  // ------------------------------------------------------------------ symbols / UI
  function buildSymbols() {
    st.symbols.clear();
    const m = st.manifest;
    for (const c of m.crypto || []) st.symbols.set(c.id, { ...c, crypto: true, kind: 'ohlc', freq: '4h', group: c.group || 'PulseChain & HEX' });
    for (const p of st.pools) st.symbols.set(p.id, { ...p, crypto: true, userPool: true, kind: 'ohlc', freq: '4h', group: 'My pools', precision: p.precision || 6, source: 'GeckoTerminal', source_url: `https://www.geckoterminal.com/${p.network}/pools/${p.pool}` });
    for (const s of m.series || []) st.symbols.set(s.id, s);
    for (const c of st.custom) {
      const A = st.symbols.get(c.a), B = st.symbols.get(c.b);
      if (!A || !B) continue;
      const rank = { '4h': 0, D: 1, W: 2, M: 3, Q: 4 };
      const fa = A.crypto ? 'D' : A.freq, fb = B.crypto ? 'D' : B.freq;
      st.symbols.set(c.id, { id: c.id, name: `${A.id} ${c.op} ${B.id}`, group: 'My ratios', kind: 'value', custom: true, a: c.a, b: c.b, op: c.op,
        freq: rank[fa] <= rank[fb] ? fa : fb, precision: 4, source: `computed from ${A.id} (${A.source}) and ${B.id} (${B.source})`, source_url: '', last: A.last < B.last ? A.last : B.last });
    }
  }
  function renderList() {
    const q = ($('#search').value || '').trim().toLowerCase();
    const groups = ['My pools', 'My ratios', ...(st.manifest.groups || [])];
    const byGroup = new Map();
    for (const s of st.symbols.values()) {
      if (q && !(s.id.toLowerCase().includes(q) || (s.name || '').toLowerCase().includes(q))) continue;
      if (!byGroup.has(s.group)) byGroup.set(s.group, []);
      byGroup.get(s.group).push(s);
    }
    const order = [...groups, ...Array.from(byGroup.keys()).filter((g) => !groups.includes(g))];
    let html = '';
    for (const g of order) {
      const items = byGroup.get(g); if (!items || !items.length) continue;
      html += `<div class="grp">${g}</div>`;
      for (const s of items) {
        const tag = s.crypto ? '' : `<span class="freqtag">${s.freq}</span>`;
        const del = (s.custom || s.userPool) ? `<button class="del" data-del="${s.id}" title="Remove">×</button>` : '';
        html += `<div class="sym${st.current && st.current.id === s.id ? ' active' : ''}" data-id="${s.id}" title="${(s.name || '').replace(/"/g, '&quot;')}"><span class="sid">${s.id}</span><span class="sname">${s.name || ''}</span>${tag}${del}</div>`;
      }
    }
    $('#list').innerHTML = html || '<div class="grp">no matches</div>';
    // ratio builder options
    const opts = Array.from(st.symbols.values()).filter((s) => !s.custom).map((s) => `<option value="${s.id}">${s.id}</option>`).join('');
    for (const sel of ['#cA', '#cB']) { const el = $(sel); const v = el.value; el.innerHTML = opts; if (v) el.value = v; }
  }
  function updateTfButtons() {
    const s = st.current; if (!s) return;
    const allowed = s.crypto ? FREQ_TFS['4h'] : (FREQ_TFS[s.freq] || ['D', 'W', 'M']);
    $$('#tfs button').forEach((b) => { b.disabled = !allowed.includes(b.dataset.tf); b.classList.toggle('on', b.dataset.tf === st.tf); b.title = b.disabled ? `${FREQ_LABEL[s.freq] || s.freq} data — not available at this timeframe` : ''; });
  }
  function updateHeader(data) {
    const s = st.current; if (!s) return;
    $('#symhead .id').textContent = s.id;
    $('#symhead .name').textContent = s.name || '';
    const last = data[data.length - 1], prev = data[data.length - 2];
    if (last) {
      const units = s.units && s.units !== 'index' ? ' ' + s.units : '';
      $('#symhead .last').textContent = `${fmtNum(last.close, s.precision)}${units} · ${fmtDate(last.timestamp, st.tf)}`;
      const ch = prev ? last.close - prev.close : 0, pct = prev && prev.close ? (ch / Math.abs(prev.close)) * 100 : 0;
      const el = $('#symhead .chg'); el.textContent = prev ? `${ch >= 0 ? '+' : ''}${fmtNum(ch, s.precision)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)` : '';
      el.className = 'chg ' + (ch >= 0 ? 'up' : 'down');
    } else { $('#symhead .last').textContent = 'no data'; $('#symhead .chg').textContent = ''; }
    const freq = s.crypto ? (st.tf === '4h' ? '4-hour' : FREQ_LABEL[st.tf]) : `${FREQ_LABEL[s.freq]} data${st.tf !== s.freq && !(s.freq === 'Q' && st.tf === 'M') ? `, shown ${FREQ_LABEL[st.tf]}` : ''}`;
    const src = s.source_url ? `<a href="${s.source_url}" target="_blank" rel="noopener">${s.source}</a>` : s.source;
    const key = s.source_key && !s.custom ? ` <span class="disc">${s.source_key}</span>` : '';
    const stale = s.stale ? ' <span class="stale">⚠ last refresh failed, showing older data</span>' : '';
    const live = s.crypto ? (s.live === false ? ' <span class="stale">(cached copy — live feed unavailable)</span>' : ' (live)') : '';
    $('#status .src').innerHTML = `${freq} · source: ${src}${key}${live}${stale}${s.tv && s.tv !== '—' ? ` · <span class="disc">TV: ${s.tv}</span>` : ''}`;
    document.title = `${s.id} · PLSLEND Charts`;
  }

  async function selectSymbol(id, tf) {
    const s = st.symbols.get(id);
    if (!s) return;
    if (st.drawingId) setTool('cursor');
    st.current = s;
    const allowed = s.crypto ? FREQ_TFS['4h'] : (FREQ_TFS[s.freq] || ['D', 'W', 'M']);
    st.tf = allowed.includes(tf || st.tf) ? (tf || st.tf) : allowed[0];
    updateTfButtons(); renderList();
    location.hash = st.tf === 'D' ? s.id : `${s.id}:${st.tf}`;
    setPref('last', { id: s.id, tf: st.tf });
    loading(true);
    try {
      const data = s.crypto ? await loadCrypto(s, st.tf) : await loadSeries(s);
      if (st.current !== s) return; // user moved on
      if (s.custom || (s.crypto && !s.precision)) s.precision = autoPrecision(data.map((d) => d.close));
      st.native = data;
      const per = TF_PERIOD[st.tf];
      chart.setSymbol({ ticker: s.id, pricePrecision: s.precision, volumePrecision: 0 });
      chart.setPeriod(s.freq === 'Q' && st.tf === 'M' ? { type: 'month', span: 3 } : per);
    } catch (e) {
      console.error(e); st.native = []; chart.setSymbol({ ticker: s.id, pricePrecision: 2 }); chart.setPeriod(TF_PERIOD[st.tf]);
      toast(`Could not load ${s.id}: ${e.message}`, 5000);
    } finally { loading(false); }
  }
  function setTf(tf) {
    if (!st.current) return;
    st.tf = tf; updateTfButtons();
    location.hash = tf === 'D' ? st.current.id : `${st.current.id}:${tf}`;
    setPref('last', { id: st.current.id, tf });
    if (st.current.crypto) selectSymbol(st.current.id, tf);
    else chart.setPeriod(st.current.freq === 'Q' && tf === 'M' ? { type: 'month', span: 3 } : TF_PERIOD[tf]);
  }

  // ------------------------------------------------------------------ custom ratio / pool
  function addCustom() {
    const a = $('#cA').value, b = $('#cB').value, op = $('#cOp').value;
    if (!a || !b || a === b) { toast('Pick two different symbols'); return; }
    const id = `${a}${op}${b}`;
    if (!st.custom.some((c) => c.id === id)) { st.custom.push({ id, a, b, op }); setPref('custom', st.custom); }
    buildSymbols(); renderList(); selectSymbol(id);
  }
  async function addPool() {
    const network = $('#pNet').value; let addr = ($('#pAddr').value || '').trim();
    const m = addr.match(/0x[0-9a-fA-F]{40}/); if (!m) { toast('Paste a pool address (0x…) or a GeckoTerminal pool link'); return; }
    addr = m[0].toLowerCase();
    loading(true);
    try {
      const r = await fetch(`${GT}/networks/${network}/pools/${addr}`, { headers: { Accept: 'application/json;version=20230302' } });
      if (!r.ok) throw new Error('pool not found on GeckoTerminal');
      const a = (await r.json()).data.attributes;
      const STABLES = ['DAI', 'USDC', 'USDT', 'PDAI', 'PUSDC', 'PUSDT', 'USDL', 'PXDC', 'HEXDC', 'WETH', 'WPLS'];
      const [baseSym, quoteSym] = (a.name || '').split(' / ').map((x) => (x || '').split(' ')[0].trim());
      const side = STABLES.includes((baseSym || '').toUpperCase()) && quoteSym && !STABLES.includes(quoteSym.toUpperCase()) ? 'quote' : 'base';
      const sym = side === 'quote' ? quoteSym : baseSym;
      let id = (sym || 'POOL').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) || 'POOL';
      if (st.symbols.has(id)) id = `${id}_${addr.slice(2, 6)}`;
      const price = side === 'quote' ? +a.quote_token_price_usd : +a.base_token_price_usd;
      const p = { id, name: `${a.name} (${network})`, network, pool: addr, side, precision: autoPrecision([price || 1]) };
      st.pools.push(p); setPref('pools', st.pools);
      buildSymbols(); renderList(); $('#pAddr').value = ''; selectSymbol(id, '4h');
    } catch (e) { toast(e.message, 4000); } finally { loading(false); }
  }
  function removeCustom(id) {
    st.custom = st.custom.filter((c) => c.id !== id); st.pools = st.pools.filter((p) => p.id !== id);
    setPref('custom', st.custom); setPref('pools', st.pools);
    try { localStorage.removeItem(dkey(id)); } catch (e) { /* ignore */ }
    buildSymbols(); renderList();
    if (st.current && st.current.id === id) selectSymbol(st.symbols.keys().next().value);
  }

  // ------------------------------------------------------------------ wiring
  $('#tfs').addEventListener('click', (e) => { const b = e.target.closest('button'); if (b && !b.disabled) setTf(b.dataset.tf); });
  $('#ctype').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; st.chartType = b.dataset.ct; setPref('chartType', st.chartType); applyPanes(); });
  $('#logbtn').addEventListener('click', () => { st.log = !st.log; setPref('log', st.log); applyPanes(); });
  for (const [btn, key] of [['#ind-st', 'st'], ['#ind-rsi', 'rsi'], ['#ind-macd', 'macd']]) $(btn).addEventListener('click', () => { st.ind[key] = !st.ind[key]; setPref('ind', st.ind); applyPanes(); });
  $$('#toolbar [data-tool]').forEach((b) => b.addEventListener('click', () => setTool(b.dataset.tool === st.tool && b.dataset.tool !== 'cursor' ? 'cursor' : b.dataset.tool)));
  for (const id of ['#stLen', '#stMult']) $(id).addEventListener('change', () => {
    const len = Math.max(2, Math.round(+$('#stLen').value || 10)), mult = Math.max(0.1, +$('#stMult').value || 2.8);
    st.stp = [len, +mult.toFixed(2)]; setPref('stp', st.stp); applyPanes();
  });
  $('#magnet').addEventListener('click', () => { st.magnet = !st.magnet; $('#magnet').classList.toggle('on', st.magnet); setPref('magnet', st.magnet); });
  $('#delsel').addEventListener('click', deleteSelected);
  $('#delall').addEventListener('click', deleteAll);
  $('#exportbtn').addEventListener('click', exportDrawings);
  $('#importbtn').addEventListener('click', () => $('#importfile').click());
  $('#importfile').addEventListener('change', (e) => { if (e.target.files[0]) importDrawings(e.target.files[0]); e.target.value = ''; });
  $('#shotbtn').addEventListener('click', () => { const a = document.createElement('a'); a.href = chart.getConvertPictureUrl(true, 'png', C.bg); a.download = `${st.current ? st.current.id : 'chart'}-${st.tf}-${new Date().toISOString().slice(0, 10)}.png`; a.click(); });
  $('#search').addEventListener('input', renderList);
  $('#list').addEventListener('click', (e) => {
    const del = e.target.closest('[data-del]'); if (del) { removeCustom(del.dataset.del); return; }
    const row = e.target.closest('.sym'); if (row) { selectSymbol(row.dataset.id); $('#side').classList.remove('open'); }
  });
  $('#cAdd').addEventListener('click', addCustom);
  $('#pAdd').addEventListener('click', addPool);
  $('#pAddr').addEventListener('keydown', (e) => { if (e.key === 'Enter') addPool(); });
  $('#menubtn').addEventListener('click', () => $('#side').classList.toggle('open'));
  $('#aboutlink').addEventListener('click', (e) => { e.preventDefault(); $('#about').classList.add('show'); });
  $('#aboutclose').addEventListener('click', () => $('#about').classList.remove('show'));
  $('#about').addEventListener('click', (e) => { if (e.target.id === 'about') $('#about').classList.remove('show'); });
  document.addEventListener('keydown', (e) => {
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes((e.target.tagName || '').toUpperCase())) return;
    if (e.key === 'Escape') { if ($('#about').classList.contains('show')) $('#about').classList.remove('show'); else setTool('cursor'); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { if (st.selectedId) { e.preventDefault(); deleteSelected(); } }
  });
  window.addEventListener('hashchange', () => { const [id, tf] = decodeURIComponent(location.hash.slice(1)).split(':'); if (id && st.symbols.has(id) && (!st.current || st.current.id !== id || (tf && tf !== st.tf))) selectSymbol(id, tf); });

  // ------------------------------------------------------------------ boot
  (async function boot() {
    st.chartType = pref('chartType', null); st.log = pref('log', false); st.ind = { ...st.ind, ...pref('ind', {}) }; st.magnet = pref('magnet', false);
    st.custom = pref('custom', []); st.pools = pref('pools', []); st.stp = pref('stp', [10, 2.8]);
    $('#magnet').classList.toggle('on', st.magnet);
    setTool('cursor');
    loading(true);
    try {
      st.manifest = await fetchJSON(DATA + 'manifest.json?t=' + Date.now());
    } catch (e) {
      st.manifest = { updated: '', groups: [], series: [], crypto: [] };
      toast('Data manifest not found yet — the data job has not run', 6000);
    }
    buildSymbols(); renderList();
    const src = $('#aboutsources');
    src.innerHTML = Object.entries(st.manifest.attribution || {}).map(([k, v]) => `<li><b>${k}</b> — ${v}</li>`).join('') || '<li>no data loaded</li>';
    if (st.manifest.updated) $('#status .disc').textContent = `data refreshed ${st.manifest.updated.slice(0, 16).replace('T', ' ')} UTC · not financial advice · prices may be delayed`;
    const [hid, htf] = decodeURIComponent(location.hash.slice(1)).split(':');
    const last = pref('last', null);
    const first = (hid && st.symbols.has(hid)) ? hid : (last && st.symbols.has(last.id)) ? last.id : (st.symbols.has('pHEX') ? 'pHEX' : st.symbols.keys().next().value);
    loading(false);
    if (first) selectSymbol(first, (hid && htf) || (last && last.tf) || 'D');
  })();
})();
