"""Planted-case tests for Stocks > Scorecard and the Zanger additions: the log's cleaning (loose headers, bad rows, repeats,
a save and load), one trade measured by hand (R, entry and exit timing, MFE, capture, the plan from the same entry),
the four-way split adding up to the trade's R, the process grade's parts and the 2 x 2, cluster luck (a planted bad
order against a good one, the same ending equity), the card's scores, the example trades; Zanger's base breakout by
hand (with volume, without it, the 5% chase limit, a loose base, the stop) and the volume pace by hand.
Run: python test_scorecard.py"""
import os
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ["LAB_TRADE_LOG"] = os.path.join(tempfile.mkdtemp(prefix="tc_test_"), "trade_log.csv")
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


PLAN = L.sim_plan_of({})
print("The log")
raw = pd.DataFrame({"Symbol": ["abc", "ABC", "xyz", "", "bad", "late"], "Buy Date": ["2026-03-02", "2026-03-02", "2026-03-05", "2026-03-05", "2026-03-05", "2026-03-10"],
                    "Entry Price": [10.0, 10.0, 20.0, 5.0, -1.0, 9.0], "Stop": [9.0, 9.0, None, 4.0, 1.0, 8.0],
                    "Sell Date": ["2026-03-06", "2026-03-06", "2026-03-09", "2026-03-06", "2026-03-06", "2026-03-01"],
                    "Exit Price": [12.0, 12.0, 19.0, 6.0, 2.0, 9.5], "Qty": [100, 100, 50, 1, 1, 1]})
cl = L.tc_clean(raw)
check("loose headers are read; a repeat, a blank ticker, a bad price and an exit before the entry are dropped",
      list(cl.columns) == L.TC_COLS and cl["ticker"].tolist() == ["ABC", "XYZ"] and cl["shares"].tolist() == [100, 50], cl.to_dict("records"))
check("a missing stop stays missing", np.isnan(cl.loc[cl["ticker"] == "XYZ", "init_stop"].iloc[0]))
L.tc_save(cl)
back = L.tc_load()
check("saved and loaded back the same", back["ticker"].tolist() == ["ABC", "XYZ"] and back["entry_date"].iloc[0] == pd.Timestamp("2026-03-02")
      and not os.path.exists(str(L.TC_FILE)[:-4] + ".tmp"))

print("One trade by hand")
n = 400
idx = pd.bdate_range("2025-01-01", periods=n)
arr = {k: np.full(n, v) for k, v in (("open", 100.0), ("high", 101.0), ("low", 99.0), ("close", 100.0))}
e = 320
steps = [(100.0, 102.0, 99.5, 101.5), (101.5, 104.0, 101.0, 103.5), (103.5, 106.5, 103.0, 106.0), (106.0, 107.0, 104.0, 104.5)]
for k, (o_, h_, l_, c_) in enumerate(steps):
    arr["open"][e + k], arr["high"][e + k], arr["low"][e + k], arr["close"][e + k] = o_, h_, l_, c_
for k in range(e + 4, n):
    arr["open"][k], arr["high"][k], arr["low"][k], arr["close"][k] = 104.5, 105.0, 104.0, 104.5
P = {k: pd.DataFrame({"AAA": v, "BBB": v * 1.0}, index=idx) for k, v in arr.items()}
P["volume"] = pd.DataFrame({"AAA": np.full(n, 1e6), "BBB": np.full(n, 1e6)}, index=idx)
log = pd.DataFrame([{"ticker": "AAA", "entry_date": idx[e], "entry": 100.5, "init_stop": 99.5, "exit_date": idx[e + 2], "exit": 105.0, "shares": 100},
                    {"ticker": "BBB", "entry_date": idx[e], "entry": 101.0, "init_stop": np.nan, "exit_date": idx[e + 3], "exit": 97.0, "shares": 10},
                    {"ticker": "ZZZ", "entry_date": idx[e], "entry": 10.0, "init_stop": 9.0, "exit_date": idx[e + 1], "exit": 11.0, "shares": 1}])
M = L.tc_measure(P, log, PLAN, hold=20, cost_bp=10)
a = M[M["ticker"] == "AAA"].iloc[0]
cost = 2 * 10 / 1e4 * 100.5 / 1.0
check("R and the result in R after costs", abs(a["R"] - 1.0) < 1e-9 and abs(a["r"] - (4.5 - cost)) < 1e-9, (a["R"], a["r"]))
check("entry timing: bought 60% of the way down the day's range", abs(a["entry_eff"] - (102.0 - 100.5) / 2.5) < 1e-9, a["entry_eff"])
check("exit timing: sold 57% of the way up the exit day's range", abs(a["exit_eff"] - (105.0 - 103.0) / 3.5) < 1e-9, a["exit_eff"])
check("best open profit 6R, worst -1R, capture = R / MFE", abs(a["mfe_r"] - 6.0) < 1e-9 and abs(a["mae_r"] + 1.0) < 1e-9
      and abs(a["capture"] - a["r"] / 6.0) < 1e-9, (a["mfe_r"], a["mae_r"], a["capture"]))
check("3 sessions held, no chase, the stop held", a["hold"] == 3 and abs(a["chase"] - 0.005) < 1e-9 and not a["past_stop"])
check("the plan from the same entry: trims a third at 2R, then rides", np.isfinite(a["plan_r"]) and a["plan_r"] > 1.0, a["plan_r"])
b = M[M["ticker"] == "BBB"].iloc[0]
check("no logged stop: 1.5 ATR assumed and flagged", bool(b["stop_assumed"]) and abs(b["R"] - 1.5 * L._mc_atr(P["high"], P["low"], P["close"], 14)["BBB"].iloc[e - 1]) < 1e-9)
check("a loss past 1.2R is flagged", bool(b["past_stop"]) and b["r"] < -1.2, b["r"])
z = M[M["ticker"] == "ZZZ"].iloc[0]
check("a name outside the list is reported, not graded", not z["ok"] and "not in the loaded list" in z["why"])
check("the real opens are left as they were", float(P["open"]["AAA"].iloc[e]) == 100.0)

print("The split and the grade")
g = np.random.default_rng(4)
dts = pd.bdate_range("2025-06-02", periods=60)
T = pd.DataFrame({"ok": True, "ticker": [f"T{k % 9}" for k in range(60)], "exit_date": dts, "entry_date": dts, "r": g.normal(0.3, 1.5, 60),
                  "plan_r": g.normal(0.2, 1.5, 60), "spot_er": g.normal(0.1, 0.2, 60), "base": 0.05, "stop_assumed": False,
                  "risk_atr": g.uniform(0.5, 2.5, 60), "chase": g.uniform(0, 0.03, 60), "past_stop": False, "capture": g.uniform(0.2, 1, 60),
                  "hold": g.integers(1, 20, 60), "loc": "near", "trend": "s2", "spot_pct": g.uniform(0, 100, 60),
                  "entry_eff": g.uniform(0, 1, 60), "dollars": 0.0})
T["entry_v"], T["luck"], T["exit_v"] = T["spot_er"] - T["base"], T["plan_r"] - T["spot_er"], T["r"] - T["plan_r"]
check("baseline + entry + luck + exit = the trade's R", np.allclose(T[["base", "entry_v", "luck", "exit_v"]].sum(axis=1), T["r"]))
G = L.tc_grade(T)
check("process points stay within 0-100 and the parts add up", G["process"].between(0, 100).all()
      and np.allclose(G[["g_spot", "g_risk", "g_chase", "g_stop", "g_exit"]].sum(axis=1), G["process"]))
one = T.iloc[[0]].assign(spot_pct=100.0, capture=0.8, r=3.0)
bad = T.iloc[[0]].assign(loc="ext", stop_assumed=True, chase=0.09, past_stop=True, r=-2.0, hold=12, capture=np.nan)
g1, g0 = L.tc_grade(one).iloc[0], L.tc_grade(bad).iloc[0]
check("a clean trade on the best path: 100 points, an A", g1["process"] == 100 and g1["process_grade"] == "A" and g1["outcome_grade"] == "A")
check("extended, no stop, chased, past the stop, held 12 sessions: 5 points, an F", g0["process"] == 5 and g0["process_grade"] == "F"
      and g0["outcome_grade"] == "F", g0[["g_spot", "g_risk", "g_chase", "g_stop", "g_exit"]].to_dict())
q = L.tc_grade(pd.concat([one, bad, one.assign(r=-0.5, capture=np.nan, hold=2), bad.assign(r=1.0)]))["quadrant"].tolist()
check("the 2 x 2", q == ["Good decision, paid", "Poor decision, lost", "Good decision, lost (variance)", "Poor decision, paid (the dangerous kind)"], q)

print("Cluster luck")
r_bad = np.r_[np.full(20, -1.0), np.full(20, 2.0)]
r_good = np.array([2.0, -1.0] * 20)
cb, cg = L.tc_cluster(r_bad), L.tc_cluster(r_good)
check("the same trades end at the same equity in any order", abs(cb["final"] - cg["final"]) < 1e-9)
check("all the losers first: a 20-trade streak, a drawdown deeper than nearly every order", cb["streak"] == 20 and cb["dd_pct"] > 99, (cb["streak"], cb["dd_pct"]))
check("alternating: a 1-trade streak, shallower than nearly every order", cg["streak"] == 1 and cg["dd_pct"] < 1, (cg["streak"], cg["dd_pct"]))
check("drawdown by hand: 20 losses at 1% = 18.2%", abs(cb["dd"] - (1 - 0.99 ** 20)) < 1e-9)
check("the t is the mean over its standard error", abs(cb["t"] - r_bad.mean() / (r_bad.std(ddof=1) / np.sqrt(40))) < 1e-9)

print("The card")
K = pd.DataFrame({"ok": True, "r": [2.0, 3.0, -1.0, -1.0, -2.0], "entry_eff": [0.8, 0.6, 0.4, 0.2, 0.5], "capture": [0.5, 0.9, np.nan, np.nan, np.nan],
                  "past_stop": [False, False, False, False, True], "hold": [10, 12, 1, 2, 11], "spot_pct": [80.0, 60.0, 40.0, np.nan, 20.0],
                  "exit_v": [0.5, -0.2, 0.1, np.nan, -1.0]})
cd = L.tc_card(K).set_index("skill")["score"]
check("entry timing = mean entry timing", abs(cd["Entry timing"] - 50.0) < 1e-9)
check("capture = winners' median", abs(cd["Capture"] - 70.0) < 1e-9)
check("stop discipline = losers that held the stop", abs(cd["Stop discipline"] - 100 * 2 / 3) < 1e-9)
check("cut speed = chance a winner was held longer than a loser", abs(cd["Cut speed"] - 100 * 5 / 6) < 1e-9, cd["Cut speed"])
check("spot selection and exits against the plan", abs(cd["Spot selection"] - 50.0) < 1e-9 and abs(cd["Exits vs the plan"] - 50.0) < 1e-9)
check("the card's chart builds", L.tc_card_chart(L.tc_card(K)).to_dict() is not None and L.tc_card_chart(L.tc_card(K.iloc[0:0])) is None)

print("End to end on a panel")
g = np.random.default_rng(9)
nn, mm = 700, 40
ix = pd.bdate_range("2024-01-01", periods=nn)
cols = [f"N{i:02d}" for i in range(mm)]
Cc = 50 * np.exp(np.cumsum(g.normal(np.linspace(-0.0003, 0.0012, mm), 0.02, (nn, mm)), axis=0))
Oo = np.vstack([Cc[:1], Cc[:-1]]) * np.exp(g.normal(0, 0.004, Cc.shape))
Hh, Ll = np.maximum(Oo, Cc) * (1 + np.abs(g.normal(0, 0.008, Cc.shape))), np.minimum(Oo, Cc) * (1 - np.abs(g.normal(0, 0.008, Cc.shape)))
f = lambda x: pd.DataFrame(x, index=ix, columns=cols)
PP = {"open": f(Oo), "high": f(Hh), "low": f(Ll), "close": f(Cc), "volume": f(g.lognormal(14.5, 0.4, Cc.shape))}
ex = L.tc_examples(PP, 60)
check("60 example trades, each a valid row", len(ex) == 60 and (ex["exit_date"] >= ex["entry_date"]).all() and (ex["init_stop"] < ex["entry"]).all())
S = L.pk_states(PP, {})
days = ix[-400:]
Hf = L.pk_flows(S, L.pk_outcomes(PP, days, PLAN, 40), days)
pa, pr = L.pk_paths(Hf["D"], min_n=1, min_dates=1), L.pk_paths(Hf["D"], min_n=30)
base = L.pk_baseline(Hf["D"])
fin = Hf["D"][(Hf["D"]["out"] != "") & Hf["D"]["arr"]]
check("the baseline is every finished arrival, averaged by date", abs(base - fin.groupby("date")["r"].mean().mean()) < 1e-12)
Mx = L.tc_grade(L.tc_spots(L.tc_measure(PP, ex, PLAN, 40), S, pa, pr, base))
okm = Mx[Mx["ok"]]
full = okm.dropna(subset=["base", "entry_v", "luck", "exit_v"])
check("most example trades get a spot and a full split that adds up to R", len(full) > 30
      and np.allclose(full[["base", "entry_v", "luck", "exit_v"]].sum(axis=1), full["r"]), (len(okm), len(full)))
r0 = full.iloc[0]
key = [S[k].at[ix[int(r0["e"]) - 1], r0["ticker"]] for k in L.PK_KEYS]
row = pa[(pa[list(L.PK_KEYS)] == np.array(key, dtype=object)).all(axis=1)].iloc[0]
check("the spot is the plinko path at the close before the entry, with that path's record", abs(r0["spot_er"] - row["er_date"]) < 1e-12
      and r0["spot_n"] == row["trades"])
check("every measured example gets a process and an outcome grade", okm["process_grade"].isin(list("ABCDF")).all()
      and okm["outcome_grade"].isin(list("ABCDF")).all() and okm["quadrant"].ne("").all())

print("Zanger's base breakout")
n = 330
ix = pd.bdate_range("2025-01-01", periods=n)
c = np.r_[np.linspace(50, 100, 300), np.full(30, 100.0)]
c[300:] = 100 + np.tile([0.0, 0.6, -0.4, 0.3, -0.5], 6)          # a 15-session base about 1% deep under 101.1
h, lo, v = c + 0.5, c - 0.5, np.full(n, 1e6)
d = 320


def zg(close, vol, hi=None):
    cc, vv, hh = c.copy(), v.copy(), h.copy()
    cc[d], vv[d], hh[d] = close, vol, (hi if hi is not None else close + 0.3)
    fr = lambda x: pd.DataFrame({"X": x}, index=ix)
    return L.zg_signals(fr(hh), fr(lo), fr(cc), fr(vv))


line = float(h[d - 15:d].max())
Z = zg(line + 1.0, 2.0e6)
check("the line is the base's high", abs(Z["line"]["X"].iloc[d] - line) < 1e-9)
check("a close over the line on 2x volume: the volume breakout", bool(Z["vol"]["X"].iloc[d]) and not bool(Z["quiet"]["X"].iloc[d]) and abs(Z["vr"]["X"].iloc[d] - 2.0) < 1e-9)
Zq = zg(line + 1.0, 1.2e6)
check("the same close on 1.2x volume: the control, not the setup", bool(Zq["quiet"]["X"].iloc[d]) and not bool(Zq["vol"]["X"].iloc[d]))
Zc = zg(line * 1.06, 3.0e6)
check("6% past the line is a chase: no signal", not bool(Zc["vol"]["X"].iloc[d]) and not bool(Zc["quiet"]["X"].iloc[d]))
Zn = zg(line - 0.2, 3.0e6)
check("a close under the line: no signal", not bool(Zn["vol"]["X"].iloc[d]))
atr = float(L._mc_atr(pd.DataFrame({"X": h}), pd.DataFrame({"X": lo}), pd.DataFrame({"X": c}), 14)["X"].iloc[d])
check("the stop is the line less 1 ATR", abs(Z["stop"]["X"].iloc[d] - (line - L._mc_atr(*(pd.DataFrame({"X": x}, index=ix) for x in (np.r_[h[:d], line + 1.3, h[d + 1:]], lo, np.r_[c[:d], line + 1.0, c[d + 1:]])), 14)["X"].iloc[d])) < 1e-9)
lo2 = lo.copy()
lo2[d - 8] = 80.0                                                # one deep day: the base is 26% deep
fr = lambda x: pd.DataFrame({"X": x}, index=ix)
cc = c.copy(); cc[d] = line + 1.0
vv = v.copy(); vv[d] = 2e6
check("a base deeper than 15% doesn't count", not bool(L.zg_signals(fr(np.r_[h[:d], line + 1.3, h[d + 1:]]), fr(lo2), fr(cc), fr(vv))["vol"]["X"].iloc[d]))
check("the family is wired into the ledger", L.LG_SETUPS["zg:vol"][0] == "Zanger" and "Zanger" in L.LG_FAMILIES and L.AM_TYPES["zg:vol"] == "Breakout"
      and L.LG_EXIT_SEED["Zanger"] == "trail" and "zgb" in L.LG_STOP_LABEL)
prm = {"horizon": 10, "cooldown": 10, "min_price": 5.0, "min_dv": 1.0, "base_step": 5, "tgt": 2.0, "mode": "next_open", "win": 1, "cap": 3.0, "cost": 10.0}
Pz = {"open": fr(cc), "high": fr(np.r_[h[:d], line + 1.3, h[d + 1:]]), "low": fr(lo), "close": fr(cc), "volume": fr(vv)}
ev = L.lg_chunk(Pz, None, ("Zanger",), "12/26/9", prm)["ev"]
zz = ev[ev["setup"] == "zg:vol"]
check("the ledger records the breakout on its day", len(zz) == 1 and zz["date"].iloc[0] == ix[d], ev["setup"].value_counts().to_dict() if len(ev) else "no events")

print("Volume pace")
days_ = pd.bdate_range("2026-01-05", periods=8)
rows = []
for k, dd in enumerate(days_):
    for s_ in range(13):
        vol = 100.0 if k < 7 else (300.0 if s_ < 4 else 100.0)      # the last day: 3x volume for four bars, then normal
        rows.append({"t": dd + pd.Timedelta(minutes=570 + 30 * s_), "day": dd, "slot": s_, "volume": vol})
m = pd.DataFrame(rows).set_index("t")
pc = L.pv_pace(m)
last = pc[-13:]
check("a normal day runs at 100", abs(pc[13 * 6 + 5] - 100.0) < 1e-9)
check("3x volume for four bars = pace 300", np.allclose(last[:4], 300.0))
check("then it eases as normal bars arrive: (1200 + 100) / 500 at the fifth", abs(last[4] - 260.0) < 1e-9 and abs(last[12] - 100 * 2100 / 1300) < 1e-9)
check("no reading before five sessions of history", np.isnan(pc[:13 * 5]).all())
check("the bands", [L.pv_pace_label(x) for x in (40, 100, 150, 250, np.nan)] == ["drying up", "normal", "heavy", "extreme", ""])

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
