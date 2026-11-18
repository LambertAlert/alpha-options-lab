#!/usr/bin/env python3
"""
odds_build.py
=============
Builds (or adds to) the Market odds study from the command line, so a big universe can run overnight without the
browser open. Same code as Options > Market odds' "Build the study" button; writes data/odds_study.parquet (merged:
the names and entry horizons built replace their old rows, the rest stay) and caches every Massive response in
data/odds_cache/, so a stopped run resumes and a rerun costs nothing for what's already fetched.

Run from the lab's folder (the key comes from MASSIVE_API_KEY / POLYGON_API_KEY or .streamlit/secrets.toml):

    python odds_build.py                          # the 30 liquid ETFs, 30-day entries, 2 years
    python odds_build.py --names list --n 100     # your universe file's first 100 names
    python odds_build.py --names SPY,QQQ,NVDA --dtes 14,30 --months 12
    python odds_build.py --offline                # rebuild from the cache only (no requests)

Exit codes: 0 ok, 2 key or plan refused (401/403), 3 nothing built.
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from datetime import timedelta

warnings.filterwarnings("ignore")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", default="etf", help="etf, list, or comma-separated tickers")
    ap.add_argument("--n", type=int, default=0, help="first N names (0 = all)")
    ap.add_argument("--dtes", default="30", help="entry horizons, days before expiry, e.g. 14,30")
    ap.add_argument("--months", type=int, default=24, help="months back (Options Starter keeps 24)")
    ap.add_argument("--workers", type=int, default=8, help="parallel option-bar downloads")
    ap.add_argument("--offline", action="store_true", help="use cached responses only")
    a = ap.parse_args(argv)

    import alpha_options_lab as L

    key = L._secret("MASSIVE_API_KEY") or L._secret("POLYGON_API_KEY")
    if not key and not a.offline:
        print("No Massive key: set MASSIVE_API_KEY or put it in .streamlit/secrets.toml.")
        return 2
    if a.names.lower() == "etf":
        names = list(L.OD_ETFS)
    elif a.names.lower() == "list":
        p = L.find_default_universe()
        if p is None:
            print("No universe file (Tickers.csv, sector_themes.csv or watchlist_input.csv) found.")
            return 3
        names = [t for t in L.read_universe(p.read_bytes(), p.name)["ticker"].dropna() if t not in L.OD_ETFS]
    else:
        names = [t for t in (L._clean_ticker(x) for x in a.names.split(",")) if t]
    names = list(dict.fromkeys(names))[: a.n or None]
    listed = set(names) if a.names.lower() == "list" else set()
    groups = {t: L.od_group(t, listed) for t in names}
    dtes = tuple(sorted({int(x) for x in a.dtes.split(",") if x.strip()}))
    end = L.last_completed_session()
    start = max(end - timedelta(days=int(a.months * 30.44)), end - timedelta(days=L.OD_DAYS))
    cfg = {"source": "massive", "fred_key": L._secret("FRED_API_KEY")}
    rate_fn, rate_txt = L.od_rate_fn(cfg, start)
    client = L.OdClient(key or "", offline=a.offline)
    print(f"{len(names)} names, entries {dtes} days before expiry, {start} to {end}; rate: {rate_txt}")
    t0 = time.time()

    def prog(f, text):
        print(f"[{f:5.1%}] {text}", flush=True)

    try:
        df, logs = L.od_build(client, names, groups, start, end, dtes, L.OD_KS, rate_fn, a.workers, prog)
    except L.PlanError as e:
        print(f"Massive refused the request ({e}): historical option bars need Options Starter or higher.")
        return 2
    for lg in logs:
        why = "; ".join(f"{k} {v}" for k, v in (lg.get("why") or {}).items())
        print(f"  {lg['ticker']:<6} {lg.get('expiries', 0):>3} expiries {lg.get('smiles', 0):>4} smiles "
              f"{lg.get('spreads', 0):>6} spreads  {lg.get('error', '') or why}")
    if not len(df):
        print("Nothing built.")
        return 3
    full = L.od_save(df)
    print(f"Saved {len(df):,} new spreads ({len(full):,} in the study, {full['ticker'].nunique()} names) to {L.OD_FILE} "
          f"in {time.time() - t0:.0f}s with {client.calls:,} requests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
