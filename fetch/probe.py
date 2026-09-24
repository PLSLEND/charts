#!/usr/bin/env python3
"""Diagnostics: searches DBnomics for series we may want, and tests candidate keys for the
harder sources (ECB, Bundesbank, PBoC). Run manually from the 'Probe sources' workflow."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sources as S  # noqa: E402

SEARCHES = [
    "Bundesbank total assets",
    "Deutsche Bundesbank balance sheet assets monthly",
    "Germany monetary aggregate M2 national contribution",
    "loans to euro area private sector adjusted MFI",
    "euro area industrial confidence indicator",
    "China monetary authority total assets",
    "PBoC balance sheet",
    "10-year treasury constant maturity",
    "Federal Reserve total assets H.4.1",
    "bank credit all commercial banks",
    "M1 money stock",
    "consumer price index all urban consumers all items",
    "median sales price of houses sold",
    "ICE BofA US high yield effective yield",
    "overnight bank funding rate",
    "treasury general account",
    "median CPI Cleveland",
    "overnight reverse repurchase agreements",
]

CANDIDATES = [
    ("bbk", "BBSSY/D.REN.EUR.A620.000000WT0202.A"),
    ("bbk", "BBSSY/D.REN.EUR.A620.000000WT1010.A"),
    ("bbk", "BBK01/WT0202"),
    ("bbk", "BBK01/OU0304"),
    ("bbk", "BBK01/OU0308"),
    ("bbk", "BBK01/OU0301"),
    ("bbk", "BBK01/TXI310"),
    ("ecb", "BSI/M.DE.N.R.T00.A.1.Z5.0000.Z01.E"),
    ("ecb", "BSI/M.DE.N.C.T00.A.1.Z5.0000.Z01.E"),
    ("ecb", "BSI/M.DE.N.V.M20.X.1.U2.2300.Z01.E"),
    ("ecb", "BSI/M.DE.Y.V.M20.X.1.U2.2300.Z01.E"),
    ("ecb", "BSI/M.U2.Y.U.A20T.A.1.U2.2200.Z01.E"),
    ("ecb", "BSI/M.U2.Y.U.A20T.A.1.U2.2250.Z01.E"),
    ("ecb", "BSI/M.IT.N.A.T00.A.1.Z5.0000.Z01.E"),
    ("ecb", "ILM/W.U2.C.T000000.Z5.Z01"),
    ("ecb", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y"),
    ("dbnomics", "ISM/pmi/pm"),
    ("dbnomics", "Eurostat/ei_bsin_m_r2/M.BAL.BS-ICI.SA.EA20"),
    ("dbnomics", "Eurostat/ei_bsin_m_r2/M.BAL.BS-ICI.SA.EA19"),
    ("dbnomics", "Eurostat/ei_bssi_m_r2/M.BAL.BS-ICI-BAL.SA.EA20"),
    ("dbnomics", "IMF/IFS/M.CN.FASAF_XDC"),
    ("pboc", "total_assets"),
]


def main():
    print("== DBnomics searches ==", flush=True)
    for q in SEARCHES:
        try:
            hits = S.dbnomics_search(q, limit=8)
            print(f"\n[{q}]")
            for h in hits:
                print("   ", h)
        except Exception as e:  # noqa: BLE001
            print(f"  search failed: {e}")
    print("\n== candidate keys ==", flush=True)
    for src, key in CANDIDATES:
        try:
            fn = getattr(S, src)
            rows = fn(key)
            print(f"  OK  {src:<9} {key:<48} n={len(rows):<6} first={rows[0]} last={rows[-1]}")
        except Exception as e:  # noqa: BLE001
            print(f"  --  {src:<9} {key:<48} {str(e)[:220]}")


if __name__ == "__main__":
    main()
