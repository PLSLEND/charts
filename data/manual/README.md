Manual overrides. Put a `<SERIES_ID>.csv` here with two columns `date,value`
(`YYYY-MM-DD` or `YYYY-MM`) and it is used as a data source for that series
(see `fetch/series_config.py` for the source order). Used for series without
a free machine-readable feed, e.g. the PBoC balance sheet (`CNCBBS.csv`).
