"""Planted-case tests for Brief > Pre-market scanner (Martin Luk's Premarket, Leader and Potent screeners): the screener
fields by hand, the snapshot reader, each filter at its edge, the sorts, the funnel, the three data modes (live
pre-market, after the open, last session), market caps from the file and from Massive (cached for the day), the EP gap
tiers, the demo snapshot, the stock list cache and grouped bars carrying the open.
Run: python test_luk.py"""
import math, os, shutil, tempfile, warnings
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import alpha_options_lab as L

PASS, FAIL = 0, []


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


today = date(2026, 11, 2)                                  # a Monday
idx = pd.bdate_range(end=pd.Timestamp(today) - pd.Timedelta(days=3), periods=80)    # through Friday Oct 30
names = ["AAA", "BBB", "CCC", "DDD", "EEE", "UPT"]
n = len(idx)
C = pd.DataFrame(100.0, index=idx, columns=names)
V = pd.DataFrame(1e6, index=idx, columns=names)
rng_ = pd.DataFrame(0.05, index=idx, columns=names)        # daily high/low range, as a share of the low
C["CCC"] = 50.0
V["BBB"] = 4e5                                             # fails the 500K average volume
V["CCC"] = 6e5                                             # 50 x 600K = $30M: fails price x volume
rng_["DDD"] = 0.02                                         # fails volatility 1W
C["UPT"] = np.linspace(60, 120, n)                         # a steady riser: over its 21 and 50-day EMAs
V["EEE"] = np.r_[np.full(n - 10, 1e6), np.full(10, 3e6)]
L_ = C / (1 + rng_ / 2) ** 0
H = C * (1 + rng_ / 2)
Lo = H / (1 + rng_)
O = C.shift(1).fillna(C)
O.iloc[-1, names.index("UPT")] = C["UPT"].iloc[-1] / 1.02     # closed 2% over its open on the last day
P = {"open": O, "high": H, "low": Lo, "close": C, "volume": V}

print("the screener fields")
F = L.lk_features(P, today, live=True)
a = F.loc["AAA"]
check("average volume over the last 10 sessions; price x volume = last close x last volume; 1W = last close x 5 sessions",
      abs(F.loc["EEE", "avg_vol10"] - 3e6) < 1 and abs(a["pxvol"] - 100 * 1e6) < 1e-3 and abs(a["pxvol_1w"] - 100 * 5e6) < 1e-3)
check("volatility 1W = the average daily high-low range of the last 5 sessions, % of the low; ADR% the same over 20",
      abs(a["vol_1w"] - 5.0) < 1e-9 and abs(a["adr20"] - 5.0) < 1e-9 and abs(F.loc["DDD", "vol_1w"] - 2.0) < 1e-9)
e = {s: C["UPT"].ewm(span=s, min_periods=s).mean().iloc[-1] for s in (9, 21, 50)}
u = F.loc["UPT"]
check("EMAs as pandas computes them; extension and the 9/21/50 spread", abs(u["ema21"] - e[21]) < 1e-9
      and abs(u["ext50"] - (C["UPT"].iloc[-1] / e[50] - 1)) < 1e-12
      and abs(u["ema_conv"] - (max(e.values()) - min(e.values())) / C["UPT"].iloc[-1] * 100) < 1e-9)
check("performance 1M = 21 sessions back; change from the open", abs(u["perf_1m"] - (C["UPT"].iloc[-1] / C["UPT"].iloc[-22] - 1)) < 1e-12
      and abs(u["chg_open"] - 0.02) < 1e-9)
Ft = L.lk_features({k: pd.concat([x, x.iloc[[-1]].set_axis([pd.Timestamp(today)])]) for k, x in P.items()}, today, live=True)
check("with a live snapshot, today's unfinished bar is left out", Ft.loc["AAA", "asof"] == idx[-1])
Fd = L.lk_features(P, today, live=False, drop_last=True)
check("drop_last steps back one session (what the scanner saw that morning)", Fd.loc["AAA", "asof"] == idx[-2])

print("the snapshot")
ms = lambda d, h, m: int(pd.Timestamp(datetime.combine(d, datetime.min.time()) + timedelta(hours=h, minutes=m))
                        .tz_localize("America/New_York").tz_convert("UTC").value // 10 ** 6)
snap = {"AAA": {"prevDay": {"c": 100.0}, "day": {"o": 0, "c": 0, "v": 0}, "min": {"c": 110.0, "t": ms(today, 8, 40), "av": 4e5}},
        "EEE": {"prevDay": {"c": 100.0}, "day": {"o": 0, "c": 0, "v": 0}, "min": {"c": 104.0, "t": ms(today, 8, 41), "av": 1e5}},
        "BBB": {"prevDay": {"c": 100.0}, "day": {"o": 0, "c": 0, "v": 0}, "min": {"c": 130.0, "t": ms(today, 8, 41), "av": 1e5}},
        "CCC": {"prevDay": {"c": 50.0}, "day": {"o": 0, "c": 0, "v": 0}, "min": {"c": 60.0, "t": ms(today, 8, 41), "av": 1e5}},
        "DDD": {"prevDay": {"c": 100.0}, "day": {"o": 0, "c": 0, "v": 0}, "min": {"c": 125.0, "t": ms(today, 8, 41), "av": 1e5}},
        "UPT": {"prevDay": {"c": 120.0}, "day": {"o": 0, "c": 121.0, "v": 0}, "min": {"c": 140.0, "t": ms(today - timedelta(days=3), 19, 59), "av": 9}},
        "ABCDW": {"prevDay": {"c": 10.0}, "day": {}, "min": {"c": 12.0, "t": ms(today, 8, 41)}},
        "ZERO": {"prevDay": {"c": 0}, "day": {}, "min": {"c": 12.0, "t": ms(today, 8, 41)}}}
Lv = L.lk_live(snap, today)
check("pre-market change from today's latest minute against the prior close; volume so far from the running total",
      abs(Lv.loc["AAA", "chg_now"] - 0.10) < 1e-12 and Lv.loc["AAA", "fresh"] and Lv.loc["AAA", "vol_today"] == 4e5)
check("a latest minute from an earlier session isn't a pre-market print (falls back to today's bar)", not Lv.loc["UPT", "fresh"]
      and Lv.loc["UPT", "last"] == 121.0)
check("warrants and units skipped, a missing prior close skipped", "ABCDW" not in Lv.index and "ZERO" not in Lv.index)

print("Premarket")
prm = dict(L.LK_DEFAULTS)
rows, fun = L.lk_scan(F, Lv, "premarket", prm, "pre-market")
check("each filter at its edge: only the names passing all of them, sorted by pre-market change, highest first",
      list(rows.index) == ["AAA", "EEE"], (list(rows.index), fun))
check("the funnel counts down filter by filter", [x[1] for x in fun] == [6, 5, 4, 3, 2], fun)
rows_a, _ = L.lk_scan(F, Lv, "premarket", prm, "pre-market", ascending=True)
check("weakest first reverses the sort", list(rows_a.index) == ["EEE", "AAA"])
check("pre-market volume against the 10-day average", abs(rows.loc["AAA", "pm_share"] - 0.4) < 1e-12)
prm2 = {**prm, "pxvol": 25.0, "avgvol": 300.0, "vol1w": 1.5}
rows2, _ = L.lk_scan(F, Lv, "premarket", prm2, "pre-market")
check("loosen the filters and the planted failures come back, in order", list(rows2.index) == ["BBB", "DDD", "CCC", "AAA", "EEE"],
      list(rows2.index))
Lv_s = Lv.copy()
Lv_s["open_live"] = [105.0, 103.0, 101.0, 55.0, 120.0, 121.0][:len(Lv_s)]
Lv_s["gap_open"] = Lv_s["open_live"] / Lv_s["prev_close_live"] - 1
rs, _ = L.lk_scan(F, Lv_s, "premarket", prm, "session")
check("after the open: sorted by the gap at the open (every name that opened counts, not just pre-market prints)",
      list(rs.index) == ["AAA", "EEE", "UPT"] and abs(rs.loc["AAA", "move"] - 0.05) < 1e-12, list(rs.index))
Fd2 = Fd.copy()
Fd2["next_open"] = O.iloc[-1]
Fd2.loc["EEE", "next_open"] = 108.0
rl, _ = L.lk_scan(Fd2, None, "premarket", prm, "last session")
check("no live data: the last session's open gap, on the fields as of the session before", rl.index[0] == "EEE"
      and abs(rl.loc["EEE", "move"] - 0.08) < 1e-12)

print("Leader and Potent")
rl_, fl_ = L.lk_scan(F, None, "leader", {**prm, "pxvol1w": 300.0}, "pre-market")
check("Leader: price x volume 1W over $300M, sorted by the month's performance", rl_.index[0] == "UPT"
      and "CCC" not in rl_.index and "BBB" not in rl_.index, (list(rl_.index), fl_))
rp, fp = L.lk_scan(F, None, "potent", prm, "pre-market")
check("Potent: over the 50-day EMA, at or over the 21, volatile and liquid, moving off the open: only the riser",
      list(rp.index) == ["UPT"], (list(rp.index), fp))
rp0, _ = L.lk_scan(F, None, "potent", {**prm, "band": 2.5}, "pre-market")
check("Potent: a 2% move off the open is inside a ±2.5% band", len(rp0) == 0)
Lv_p = pd.DataFrame({"prev_close_live": [120.0], "last": [126.0], "open_live": [121.0], "vol_today": [2e6], "fresh": [True],
                     "chg_now": [0.05], "gap_open": [121 / 120 - 1]}, index=["UPT"])
rps, _ = L.lk_scan(F, Lv_p, "potent", prm, "session")
check("Potent during the session: today's change, change from the open and dollar volume, live",
      list(rps.index) == ["UPT"] and abs(rps.loc["UPT", "chg"] - 0.05) < 1e-12 and abs(rps.loc["UPT", "chg_open"] - (126 / 121 - 1)) < 1e-12
      and abs(rps.loc["UPT", "pxvol"] - 126 * 2e6) < 1e-6)

print("market caps")
uni = pd.DataFrame({"ticker": ["AAA"], "name": ["A"], "industry": ["Semis"], "theme": [""], "last": [100.0], "mcap": [5e9]})
calls = []
real = L.fetch_overview
L.fetch_overview = lambda t, key: calls.append(t) or {"market_cap": {"EEE": 8e7, "UPT": 2e9}.get(t), "sic": "SEMICONDUCTORS"}
try:
    L._brief_store().pop("lk_caps", None)
    caps = L.lk_caps(["AAA", "EEE", "UPT"], uni, "massive", "KEY")
    check("caps from your file first, Massive for the rest", caps["AAA"]["src"] == "your file" and sorted(calls) == ["EEE", "UPT"]
          and caps["UPT"]["industry"] == "Semiconductors")
    L.lk_caps(["AAA", "EEE", "UPT"], uni, "massive", "KEY")
    check("looked-up caps are kept for the day (no new requests)", len(calls) == 2)
    tbl = pd.DataFrame({"move": [0.1, 0.05, 0.02, 0.01]}, index=["AAA", "EEE", "UPT", "QQQQ"])
    kept = L.lk_apply_caps(tbl, {**caps}, 100.0, 4)
    check("under $100M dropped, unknown kept and marked", list(kept.index) == ["AAA", "UPT", "QQQQ"]
          and kept.loc["QQQQ", "cap_src"] == "unknown")
finally:
    L.fetch_overview = real

print("EP gap tiers, demo snapshot")
t_ = L.lk_ep_gap(pd.Series([0.30, 0.16, 0.09, 0.05, -0.20]))
check("War Room tiers by the gap: STRONG 25%+, STANDARD 15%+, WATCH 8%+, nothing for gaps down",
      list(t_) == ["STRONG", "STANDARD", "WATCH", "", ""])
ds = L.lk_demo_snapshot(P, today)
dl = L.lk_live(ds, today)
check("the demo snapshot: every name printed this pre-market, priced off its last close", dl["fresh"].all() and len(dl) == len(names)
      and np.allclose(dl["prev_close_live"], C.iloc[-1].reindex(dl.index)))

print("the stock list and grouped bars")
tmp = tempfile.mkdtemp()
real_cache, real_cs, real_get = L.CACHE_DIR, L.common_stock_set, L.massive_get_all
try:
    L.CACHE_DIR = L.Path(tmp)
    n_calls = []
    L.common_stock_set = lambda key: n_calls.append("cs") or {"AAA", "BBB"}
    L.massive_get_all = lambda path, params, key, max_pages=1: n_calls.append(params.get("type")) or [{"ticker": "BABA"}]
    s1 = L.lk_stock_set("KEY")
    s2 = L.lk_stock_set("KEY")
    check("common stocks and ADRs, cached a week", s1 == {"AAA", "BBB", "BABA"} and s2 == s1 and n_calls == ["cs", "ADRC"], n_calls)
finally:
    L.CACHE_DIR, L.common_stock_set, L.massive_get_all = real_cache, real_cs, real_get
    shutil.rmtree(tmp, ignore_errors=True)
real_gd = L.grouped_day
try:
    def fake_gd(d, key):
        return pd.DataFrame({"ticker": ["AAA", "BBB"], "open": [10.0, 20.0], "high": [11.0, 21.0], "low": [9.0, 19.0],
                             "close": [10.5, 20.5], "volume": [1e6, 2e6]})
    L.grouped_day = fake_gd
    gp = L.grouped_panel(40, "KEY", only={"AAA"}, min_price=1.0, fetch=True)
    check("grouped bars carry the open now (the Potent screener needs it), filtered to the stock list",
          gp is not None and {"open", "close", "high", "low", "volume"} <= set(gp) and list(gp["open"].columns) == ["AAA"])
finally:
    L.grouped_day = real_gd

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
