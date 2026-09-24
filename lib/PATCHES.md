# Local patches to KLineChart 10.0.3 (lib/klinecharts.min.js)

Rebuilt from the package's `dist/umd/klinecharts.js` with two changes, then minified with terser:

1. `Event.prototype._zoomYAxis` — the price axis is scaled in the axis' *real* space
   (`realFrom/realTo/realRange`) instead of value space, so dragging a logarithmic axis zooms evenly
   and never pushes `from` below zero.
2. The vertical pan of a manually scaled price axis (pressed-move on the main pane) — same change:
   the shift is applied in real space and converted back with `realValueToValue`.

For the default linear axis both are identical to upstream behaviour.
