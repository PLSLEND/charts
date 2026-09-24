"""
Catalog of every series the chart app knows about.

Each entry:
  id        short symbol used in the app and as the file name
  name      display name
  group     sidebar group
  freq      native frequency: D (daily), W (weekly), M (monthly), Q (quarterly)
  kind      value  -> single value per period (line/area chart)
            ohlc   -> open/high/low/close(/volume) candles
  units     display units (informational)
  sources   ordered list of (source, key) candidates; the first that returns data wins.
            The winning source is recorded in the manifest so the app can attribute it.
  tv        the original TradingView symbol, for reference only

Sources:
  fred       https://fred.stlouisfed.org/graph/fredgraph.csv?id=KEY
  yahoo      Yahoo Finance chart API (unofficial)
  stooq      https://stooq.com/q/d/l/?s=KEY&i=d
  ecb        ECB Data Portal, KEY = FLOW/SERIES_KEY
  bbk        Bundesbank statistics API, KEY = FLOW/SERIES_KEY
  dbnomics   DBnomics, KEY = PROVIDER/DATASET/SERIES
  manual     data/manual/ID.csv (date,value) maintained by hand
  pboc       best-effort scrape of the PBoC "Balance Sheet of Monetary Authority"
"""

SERIES = [
    # ---------------- US rates, credit, Fed plumbing ----------------
    dict(id="US10Y", name="US 10Y Treasury yield", group="US rates & credit", freq="D", kind="value", units="%",
         tv="TVC:US10Y", sources=[("fred", "DGS10")]),
    dict(id="US02Y", name="US 2Y Treasury yield", group="US rates & credit", freq="D", kind="value", units="%",
         tv="TVC:US02Y", sources=[("fred", "DGS2")]),
    dict(id="HYOAS_EY", name="US High Yield effective yield (ICE BofA)", group="US rates & credit", freq="D", kind="value", units="%",
         tv="FRED:BAMLH0A0HYM2EY", sources=[("fred", "BAMLH0A0HYM2EY")]),
    dict(id="OBFR", name="Overnight Bank Funding Rate", group="US rates & credit", freq="D", kind="value", units="%",
         tv="FRED:OBFR", sources=[("fred", "OBFR")]),
    dict(id="TOTBKCR", name="US bank credit, all commercial banks", group="US rates & credit", freq="W", kind="value", units="USD bn",
         tv="FRED:TOTBKCR", sources=[("fred", "TOTBKCR")]),

    dict(id="USCBBS", name="Fed balance sheet — total assets (WALCL)", group="Central banks & money", freq="W", kind="value", units="USD mn",
         tv="ECONOMICS:USCBBS", sources=[("fred", "WALCL")]),
    dict(id="TGA", name="US Treasury General Account at the Fed", group="Central banks & money", freq="W", kind="value", units="USD mn",
         tv="FRED:TREASURY", sources=[("fred", "WTREGEN"), ("fred", "TREASURY")]),
    dict(id="RRP", name="Fed overnight reverse repo (RRP)", group="Central banks & money", freq="D", kind="value", units="USD bn",
         tv="—", sources=[("fred", "RRPONTSYD")]),
    dict(id="USM1", name="US money supply M1", group="Central banks & money", freq="M", kind="value", units="USD bn",
         tv="ECONOMICS:USM1", sources=[("fred", "M1SL")]),
    dict(id="USM2", name="US money supply M2", group="Central banks & money", freq="M", kind="value", units="USD bn",
         tv="—", sources=[("fred", "M2SL")]),
    dict(id="EUCBBS", name="ECB balance sheet — total assets", group="Central banks & money", freq="W", kind="value", units="EUR mn",
         tv="ECONOMICS:EUCBBS", sources=[("fred", "ECBASSETSW"), ("ecb", "ILM/W.U2.C.T000000.Z5.Z01")]),
    dict(id="DECBBS", name="Bundesbank balance sheet — total assets", group="Central banks & money", freq="M", kind="value", units="EUR bn",
         tv="ECONOMICS:DECBBS", sources=[("manual", "DECBBS")]),
    dict(id="CNCBBS", name="PBoC balance sheet — total assets", group="Central banks & money", freq="M", kind="value", units="CNY 100mn",
         tv="ECONOMICS:CNCBBS", sources=[("manual", "CNCBBS"), ("pboc", "total_assets")]),
    dict(id="DEM2", name="Germany money supply M2 (national contribution)", group="Central banks & money", freq="M", kind="value", units="EUR mn",
         tv="ECONOMICS:DEM2", sources=[
             ("bbk", "BBBS2/M.DB.Y.V.M20.X.1.U2.2300.Z01.E"), ("bbk", "BBBS2/M.DB.N.V.M20.X.1.U2.2300.Z01.E"),
             ("bbk", "BBBS2/M.DB.Y.V.M20.X.1.U6.2300.Z01.E"), ("bbk", "BBBS2/M.DB.N.V.M20.X.1.U6.2300.Z01.E"),
             ("dbnomics", "BUBA/BBBS2/M.DB.Y.V.M20.X.1.U2.2300.Z01.E"), ("dbnomics", "BUBA/BBBS2/M.DB.N.V.M20.X.1.U2.2300.Z01.E"),
             ("manual", "DEM2")]),
    dict(id="EULPS", name="Euro area loans to the private sector (MFIs, adjusted)", group="Central banks & money", freq="M", kind="value", units="EUR mn",
         tv="ECONOMICS:EULPS", sources=[
             ("ecb", "BSI/M.U2.Y.U.A20T.A.1.U2.2200.Z01.E"), ("ecb", "BSI/M.U2.N.U.A20T.A.1.U2.2200.Z01.E"),
             ("ecb", "BSI/M.U2.Y.U.A20.A.1.U2.2200.Z01.E"), ("ecb", "BSI/M.U2.N.U.A20.A.1.U2.2200.Z01.E"),
             ("ecb", "BSI/M.U2.Y.U.A20T.A.1.U2.2250.Z01.E", "Euro area MFI loans to households (adjusted)"),
             ("manual", "EULPS")]),
    dict(id="ITBBS", name="Italy banks (MFIs) balance sheet — total assets", group="Central banks & money", freq="M", kind="value", units="EUR mn",
         tv="ECONOMICS:ITBBS", sources=[
             ("ecb", "BSI/M.IT.N.A.T00.A.1.Z5.0000.Z01.E"), ("ecb", "BSI/M.IT.N.A.T00.A.1.Z5.0000.Z01.E?startPeriod=1999-01"),
             ("manual", "ITBBS")]),

    # ---------------- Inflation, activity ----------------
    dict(id="USCPIM", name="US median CPI YoY (Cleveland Fed)", group="Inflation & activity", freq="M", kind="value", units="%",
         tv="ECONOMICS:USCPIM", sources=[("fred", "MEDCPIM094SFRBCLE"), ("fred", "MEDCPIM158SFRBCLE")]),
    dict(id="USIRMM", name="US CPI inflation MoM", group="Inflation & activity", freq="M", kind="value", units="%",
         tv="ECONOMICS:USIRMM", sources=[("fred_pct", "CPIAUCSL")]),
    dict(id="USCPIYOY", name="US CPI inflation YoY", group="Inflation & activity", freq="M", kind="value", units="%",
         tv="—", sources=[("fred_yoy", "CPIAUCSL")]),
    dict(id="MSPUS", name="US median house sales price", group="Inflation & activity", freq="Q", kind="value", units="USD",
         tv="FRED:MSPUS", sources=[("fred", "MSPUS")]),
    dict(id="USBCOI", name="US ISM Manufacturing PMI", group="Inflation & activity", freq="M", kind="value", units="index",
         tv="ECONOMICS:USBCOI", sources=[("dbnomics", "ISM/pmi/pm"), ("manual", "USBCOI")]),
    dict(id="EUBCOI", name="Euro area industrial confidence (EC survey)", group="Inflation & activity", freq="M", kind="value", units="balance",
         tv="ECONOMICS:EUBCOI", sources=[
             ("dbnomics", "Eurostat/ei_bsin_m_r2/M.BS-ICI.SA.BAL.EA20"),
             ("dbnomics", "Eurostat/ei_bsin_m_r2/M.BS-ICI.NSA.BAL.EA20"),
             ("dbnomics", "Eurostat/ei_bsin_m_r2/M.BS-ICI.SA.BAL.EA19"),
             ("manual", "EUBCOI")]),

    # ---------------- Europe rates ----------------
    dict(id="DE02Y", name="Germany 2Y government bond yield", group="Europe rates", freq="D", kind="value", units="%",
         tv="TVC:DE02Y", sources=[
             ("bbk", "BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A"),
             ("dbnomics", "BUBA/BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A"),
             ("ecb", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y", "Euro area AAA 2Y spot yield (ECB curve)"), ("manual", "DE02Y")]),
    dict(id="DE10Y", name="Germany 10Y government bond yield", group="Europe rates", freq="D", kind="value", units="%",
         tv="—", sources=[
             ("bbk", "BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"),
             ("dbnomics", "BUBA/BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"),
             ("ecb", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "Euro area AAA 10Y spot yield (ECB curve)")]),

    # ---------------- Equity indices, commodities, FX (OHLC) ----------------
    dict(id="SPX", name="S&P 500", group="Indices & commodities", freq="D", kind="ohlc", units="index",
         tv="SPCFD:SPX", sources=[("yahoo", "^GSPC"), ("stooq", "^spx"), ("fred", "SP500")]),
    dict(id="NDX", name="Nasdaq 100", group="Indices & commodities", freq="D", kind="ohlc", units="index",
         tv="NASDAQ:NDX", sources=[("yahoo", "^NDX"), ("stooq", "^ndx")]),
    dict(id="RTY", name="Russell 2000", group="Indices & commodities", freq="D", kind="ohlc", units="index",
         tv="CAPITALCOM:RTY", sources=[("yahoo", "^RUT"), ("stooq", "^rut")]),
    dict(id="DAX", name="DAX 40", group="Indices & commodities", freq="D", kind="ohlc", units="index",
         tv="XETR:DAX", sources=[("yahoo", "^GDAXI"), ("stooq", "^dax")]),
    dict(id="NKY", name="Nikkei 225", group="Indices & commodities", freq="D", kind="ohlc", units="index",
         tv="PEPPERSTONE:JPN225", sources=[("yahoo", "^N225"), ("stooq", "^nkx"), ("fred", "NIKKEI225")]),
    dict(id="HSI", name="Hang Seng", group="Indices & commodities", freq="D", kind="ohlc", units="index",
         tv="HKEX:HSI1!", sources=[("yahoo", "^HSI"), ("stooq", "^hsi")]),
    dict(id="USOIL", name="WTI crude oil (front-month future)", group="Indices & commodities", freq="D", kind="ohlc", units="USD/bbl",
         tv="TVC:USOIL", sources=[("yahoo", "CL=F"), ("stooq", "cl.f"), ("fred", "DCOILWTICO")]),
    dict(id="GSG", name="iShares GSCI Commodity ETF (GSG)", group="Indices & commodities", freq="D", kind="ohlc", units="USD",
         tv="AMEX:GSG", sources=[("yahoo", "GSG"), ("stooq", "gsg.us")]),
    dict(id="QQQ", name="Invesco QQQ", group="Indices & commodities", freq="D", kind="ohlc", units="USD",
         tv="NASDAQ:QQQ", sources=[("yahoo", "QQQ"), ("stooq", "qqq.us")]),
    dict(id="CQQQ", name="Invesco China Technology ETF (CQQQ)", group="Indices & commodities", freq="D", kind="ohlc", units="USD",
         tv="AMEX:CQQQ", sources=[("yahoo", "CQQQ"), ("stooq", "cqqq.us")]),
    dict(id="JPYUSD", name="JPY/USD", group="FX", freq="D", kind="ohlc", units="USD",
         tv="FX_IDC:JPYUSD", sources=[("yahoo", "JPYUSD=X"), ("yahoo_inv", "JPY=X"), ("stooq", "jpyusd"), ("fred_inv", "DEXJPUS")]),
    dict(id="CNYUSD", name="CNY/USD", group="FX", freq="D", kind="ohlc", units="USD",
         tv="FX_IDC:CNYUSD", sources=[("yahoo", "CNYUSD=X"), ("yahoo_inv", "CNY=X"), ("stooq", "cnyusd"), ("fred_inv", "DEXCHUS")]),
    dict(id="EURUSD", name="EUR/USD", group="FX", freq="D", kind="ohlc", units="USD",
         tv="—", sources=[("yahoo", "EURUSD=X"), ("stooq", "eurusd"), ("fred", "DEXUSEU")]),
    dict(id="DXY", name="US Dollar Index", group="FX", freq="D", kind="ohlc", units="index",
         tv="—", sources=[("yahoo", "DX-Y.NYB"), ("stooq", "dx.f")]),
    dict(id="GOLD", name="Gold (COMEX front-month daily; World Bank monthly before 2000)", group="Indices & commodities", freq="D", kind="ohlc", units="USD/oz",
         tv="—", sources=[("yahoo", "GC=F"), ("stooq", "xauusd")], deep=("pinksheet", "Gold")),
    dict(id="BTC", name="Bitcoin (BTC/USD)", group="Crypto majors", freq="D", kind="ohlc", units="USD",
         tv="—", sources=[("yahoo", "BTC-USD"), ("stooq", "btc.v")]),
    dict(id="ETH", name="Ethereum (ETH/USD)", group="Crypto majors", freq="D", kind="ohlc", units="USD",
         tv="—", sources=[("yahoo", "ETH-USD"), ("stooq", "eth.v")]),
]

# Constructed series. expr uses series ids; ops: + - * /.  Components are aligned on the
# union of dates with forward-fill, evaluated only where every component has a value.
RATIOS = [
    dict(id="MSPUS_USCPIM", name="Median house price / median CPI YoY", group="Ratios & spreads",
         expr="MSPUS / USCPIM", tv="FRED:MSPUS/ECONOMICS:USCPIM"),
    dict(id="OBFR_USIRMM", name="OBFR / CPI MoM", group="Ratios & spreads",
         expr="OBFR / USIRMM", tv="FRED:OBFR/ECONOMICS:USIRMM"),
    dict(id="HY_MINUS_US10Y", name="HY yield − US 10Y (credit spread)", group="Ratios & spreads",
         expr="HYOAS_EY - US10Y", tv="FRED:BAMLH0A0HYM2EY-TVC:US10Y", units="pp"),
    dict(id="QQQ_CQQQ", name="QQQ / CQQQ (US tech vs China tech)", group="Ratios & spreads",
         expr="QQQ / CQQQ", tv="NASDAQ:QQQ/AMEX:CQQQ"),
    dict(id="US10Y_US02Y", name="US 10Y − 2Y (curve)", group="Ratios & spreads",
         expr="US10Y - US02Y", tv="—", units="pp"),
    dict(id="NETLIQ", name="Fed net liquidity (WALCL − TGA − RRP)", group="Ratios & spreads",
         expr="USCBBS / 1000 - TGA / 1000 - RRP", tv="—", units="USD bn"),
    dict(id="SPX_GOLD", name="S&P 500 / Gold", group="Ratios & spreads",
         expr="SPX / GOLD", tv="—"),
]

# PulseChain / HEX pairs, resolved on GeckoTerminal. Either a fixed pool address or a search
# (symbol + preferred quote tokens); the highest-liquidity matching pool wins.
CRYPTO = [
    dict(id="PLS", name="PulseChain — PLS (WPLS/DAI)", network="pulsechain", search="WPLS", quotes=["DAI", "USDC", "USDT", "WETH", "pDAI"],
         token="0xa1077a294dde1b09bb078844df40758a5d0f9a27", pool="0xe56043671df55de5cdf8459710433c10324de0ae"),
    dict(id="PLSX", name="PulseX — PLSX", network="pulsechain", search="PLSX", quotes=["WPLS", "DAI", "USDC"],
         token="0x95b303987a60c71504d99aa1b13b4da07b0790ab"),
    dict(id="pHEX", name="HEX on PulseChain (pHEX)", network="pulsechain", search="HEX", quotes=["WPLS", "DAI", "USDC"],
         token="0x2b591e99afe9f32eaa6214f7b7629768c40eeb39"),
    dict(id="eHEX", name="HEX on Ethereum (eHEX)", network="eth", search="HEX", quotes=["USDC", "WETH", "USDT", "DAI"],
         token="0x2b591e99afe9f32eaa6214f7b7629768c40eeb39", deep=("cointrader", "HEX:USD")),
    dict(id="INC", name="Incentive — INC", network="pulsechain", search="INC", quotes=["WPLS", "DAI", "PLSX"],
         token="0x2fa878ab3f87cc1c9737fc071108f904c0b0c95d"),
    dict(id="LOAN", name="Liquid Loans — LOAN", network="pulsechain", search="LOAN", quotes=["WPLS", "DAI", "USDL"]),
    dict(id="USDL", name="Liquid Loans — USDL", network="pulsechain", search="USDL", quotes=["WPLS", "DAI", "USDC"]),
    dict(id="EARN", name="POWERCITY EARN — EARN", network="pulsechain", search="EARN", quotes=["WPLS", "DAI", "PLSX"]),
    dict(id="PXDC", name="POWERCITY EARN — PXDC", network="pulsechain", search="PXDC", quotes=["WPLS", "DAI", "USDC", "PLSX"]),
    dict(id="FLEX", name="POWERCITY FLEX — FLEX", network="pulsechain", search="FLEX", quotes=["WPLS", "DAI", "HEX"]),
    dict(id="HEXDC", name="POWERCITY FLEX — HEXDC", network="pulsechain", search="HEXDC", quotes=["WPLS", "DAI", "HEX", "USDC"]),
    dict(id="PRINT", name="INC Printer — PRINT (verify)", network="pulsechain", search="PRINT", quotes=["WPLS", "DAI", "INC"]),
]

GROUP_ORDER = [
    "PulseChain & HEX", "Crypto majors", "US rates & credit", "Central banks & money", "Inflation & activity",
    "Europe rates", "Indices & commodities", "FX", "Ratios & spreads",
]
