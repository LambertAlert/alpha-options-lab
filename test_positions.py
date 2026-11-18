"""Planted-case tests for the Positions tab (what the plan says today, the continuation evidence, swaps, the Book file).
Run: python test_positions.py"""
import sys, tempfile, warnings
from pathlib import Path
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


MID = next(s_ for s_ in L.LG_SETUPS if s_.startswith("macd:") and s_ not in L.RK_SKIP)
n = 300
dates = pd.bdate_range("2025-01-02", periods=n)
rng = np.random.default_rng(2)
names = ["TRM", "RUN", "CUT", "OK", "HIT", "EXT", "REC"]
C = pd.DataFrame(100 + rng.normal(0, 0.05, (n, len(names))).cumsum(axis=0) * 0, index=dates, columns=names, dtype=float)
C[:] = 100.0
e = n - 10                                                     # entry row for most: 10 sessions held
# TRM: rose to a 111 high (2R on a 5-point risk) three sessions in, now 108
C.loc[dates[e:], "TRM"] = [101, 104, 108, 109, 108.5, 108, 108.2, 108, 108.1, 108]
# RUN: trimmed earlier; the last two closes under its 21-day EMA
C.loc[dates[e:], "RUN"] = [104, 108, 112, 115, 117, 118, 118.5, 112, 106, 105.5]
# CUT: under the entry at the close of session 5
C.loc[dates[e:], "CUT"] = [100.5, 99.8, 99.5, 99.2, 99.0, 99.4, 99.6, 99.9, 99.7, 99.6]
# REC: under the entry at session 5, recovered since
C.loc[dates[e:], "REC"] = [100.5, 99.8, 99.5, 99.2, 99.0, 100.4, 101.6, 102.9, 103.1, 103.2]
# OK: entered 3 sessions ago, up a little
C.loc[dates[-3:], "OK"] = [100.4, 100.9, 101.2]
# HIT: the last bar's low breaks the stop
C.loc[dates[e:], "HIT"] = [101, 101.5, 102, 101, 100.5, 100, 99, 98, 97.5, 97]
# EXT: a long run that leaves the high 30% over the 50-day
C.loc[dates[-60:], "EXT"] = np.linspace(100, 200, 60)
H_ = C + 0.5
Lw = C - 0.5
H_.loc[dates[e + 2], "TRM"] = 111.0
Lw.loc[dates[-1], "HIT"] = 94.5
O = C.shift(1).fillna(100.0)
P = {"open": O, "high": H_, "low": Lw, "close": C, "volume": C * 0 + 1e6}
pos = pd.DataFrame([
    {"sleeve": "shares", "ticker": "TRM", "shares": 100, "entry": 100.0, "stop": 95.0, "init_stop": 95.0, "entry_date": dates[e], "trimmed": False, "setup": ""},
    {"sleeve": "shares", "ticker": "RUN", "shares": 100, "entry": 100.0, "stop": 100.0, "init_stop": 95.0, "entry_date": dates[e], "trimmed": True, "setup": ""},
    {"sleeve": "shares", "ticker": "CUT", "shares": 100, "entry": 100.0, "stop": 95.0, "init_stop": 95.0, "entry_date": dates[e], "trimmed": False, "setup": ""},
    {"sleeve": "shares", "ticker": "OK", "shares": 100, "entry": 100.0, "stop": 97.0, "init_stop": 97.0, "entry_date": dates[-3], "trimmed": False, "setup": ""},
    {"sleeve": "shares", "ticker": "HIT", "shares": 100, "entry": 100.0, "stop": 95.0, "init_stop": 95.0, "entry_date": dates[e], "trimmed": False, "setup": ""},
    {"sleeve": "shares", "ticker": "EXT", "shares": 10, "entry": 120.0, "stop": 140.0, "init_stop": 110.0, "entry_date": dates[-40], "trimmed": True, "setup": ""},
    {"sleeve": "shares", "ticker": "REC", "shares": 100, "entry": 100.0, "stop": 95.0, "init_stop": 95.0, "entry_date": dates[e], "trimmed": False, "setup": ""},
    {"sleeve": "shares", "ticker": "ZZZ", "shares": 10, "entry": 50.0, "stop": 45.0, "init_stop": 45.0, "entry_date": dates[e], "trimmed": False, "setup": ""},
    {"sleeve": "shares", "ticker": "OK", "shares": 5, "entry": 100.0, "stop": None, "init_stop": None, "entry_date": dates[e], "trimmed": False, "setup": ""},
])
pl = L.sim_plan_of(dict(L.SIM_DEFAULTS))
prm = {"mode": "next_open", "win": 1, "tgt": 2.0, "horizon": 10, "cap": 3.0, "cost": 10.0, "trail_k": 3.0}
rules = L.sim_trade_rules({**prm, "sim_plan": pl}, next(iter(L.LG_SETUPS)))
S = L.pos_status(P, L.pos_book_rows(pos), rules)
g = lambda t: S[S["ticker"] == t].iloc[0]

print("What the plan says today")
r = g("TRM")
check("TRM: target reached, not trimmed -> TRIM first", r["action"] == "trim" and "trim" in r["actions"], r["actions"])
check("TRM: the plan's stop is breakeven, yours is the initial -> RAISE STOP too", "raise" in r["actions"] and r["plan_stop"] == 100.0)
check("TRM: R, open R and best R", r["R0"] == 5.0 and abs(r["open_r"] - 1.6) < 1e-9 and abs(r["mfe_r"] - 2.2) < 1e-9,
      (r["R0"], r["open_r"], r["mfe_r"]))
check("TRM: 10 sessions held", r["days"] == 10, r["days"])
r = g("RUN")
check("RUN: trimmed and two closes under the 21-day EMA -> SELL THE REST", r["action"] == "sell_rest" and r["under_n"] >= 1,
      (r["actions"], r["under_n"], r["ma_now"]))
r = g("CUT")
check("CUT: under the entry at the close of session 5 -> SELL: not working", r["action"] == "cut", r["actions"])
r = g("REC")
check("REC: missed the time stop but recovered -> HOLD, flagged", r["action"] == "hold" and "would have sold it" in r["why"],
      (r["actions"], r["why"]))
r = g("OK")
check("OK: three sessions in, above the entry -> HOLD", r["action"] == "hold" and r["days"] == 3, (r["actions"], r["days"]))
r = g("HIT")
check("HIT: the last low went through the stop -> STOP HIT first", r["action"] == "stopped", r["actions"])
r = g("EXT")
check("EXT: high 20%+ over the 50-day -> TRIM INTO STRENGTH", "extended" in r["actions"] and r["ext50"] >= 0.2, (r["actions"], r["ext50"]))
check("EXT: its stop is above the plan's, so no raise", "raise" not in r["actions"])
check("a name outside the list can't be read", g("ZZZ")["action"] == "n/a" and "Not in the loaded list" in g("ZZZ")["why"])
check("a position without an initial stop can't be read", (S["why"].str.contains("initial stop")).sum() == 1)
check("risk to the stop and value", abs(g("TRM")["risk_now"] - (108 - 95) * 100) < 1e-9 and abs(g("TRM")["value"] - 10800) < 1e-9)
every = L.sim_trade_rules({**prm, "sim_plan": L.sim_plan_of({**L.SIM_DEFAULTS, "sim_fail_mode": "every"})}, "base:uptrend")
S2 = L.pos_status(P, L.pos_book_rows(pos), every)
check("every-close mode also cuts CUT", S2[S2["ticker"] == "CUT"].iloc[0]["action"] == "cut")

print("Continuation evidence")
nn, m = 400, 600
Cm = np.full((nn, m), 100.0)
e_ = rng.integers(20, 300, m)
R_ = np.full(m, 5.0)
x_ = e_ + rng.integers(3, 60, m)
t_ = np.where(rng.random(m) < 0.5, e_ + rng.integers(1, 3, m), -1)
t_ = np.where(t_ >= x_, -1, t_)
for k in range(m):                                            # a straight line from 100 to the exit price
    xp = 100 + rng.normal(5, 8)
    Cm[e_[k]:x_[k] + 1, k] = np.linspace(100, xp, x_[k] - e_[k] + 1)
    Cm[x_[k] + 1:, k] = xp
T = {"setup": np.array([MID] * m, object), "family": np.array(["MACD"] * m, object), "e": e_, "x": x_,
     "j": np.arange(m), "t": t_, "tp": np.where(t_ >= 0, 110.0, np.nan), "entry": np.full(m, 100.0), "R": R_,
     "xp": Cm[x_, np.arange(m)], "outcome": np.full(m, 3), "frac": 1 / 3, "C": Cm, "n": nn}
k0 = int(np.flatnonzero(t_ >= 0)[0])
sel = np.array([k0])
ret, dd, comp = L.pos_window(T, sel, np.array([e_[k0] - 1]), 5, np.array([100.0]))
tin = t_[k0] <= e_[k0] - 1 + 5 and t_[k0] <= x_[k0]
end_ = Cm[x_[k0], k0] if x_[k0] <= e_[k0] + 4 else Cm[e_[k0] + 4, k0]
want = ((1 / 3) * 110 + (2 / 3) * end_ if tin else end_) / 100 - 1
check("new-trade window: the trim share at 110, the rest at the window's end", abs(ret[0] - want) < 1e-12 and comp[0], (ret[0], want))
t0 = np.array([t_[k0] + 1])
ret2, _, _ = L.pos_window(T, sel, t0, 200, Cm[t0, [k0]])
check("trimmed before: the rest's exit only", abs(ret2[0] - (T["xp"][k0] / Cm[t0[0], k0] - 1)) < 1e-12)
late = np.array([int(np.argmax(x_))])
T["outcome"][late] = 4
Tx = {**T, "x": T["x"].copy()}
Tx["x"][late] = nn - 1
_, _, cmp_ = L.pos_window(Tx, late, np.array([nn - 3]), 10, np.array([100.0]))
check("a window running past the data on a still-open trade is dropped", not cmp_[0])
cs = L.pos_continuation(T, 5, 0.3, False, 10, MID, min_match=80)
check("continuation finds look-alike trades in the setup", cs and cs["pool"] == "this setup" and cs["ess"] > 20, cs.get("pool"))
check("continuation: band around the mean, loss share in [0, 1]", cs["lo"] <= cs["er"] <= cs["hi"] and 0 <= cs["p_loss"] <= 1)
cs_t = L.pos_continuation(T, 5, 1.0, True, 10, MID, min_match=80)
check("continuation keeps the trimmed state apart", cs_t and cs_t["n"] != cs["n"])
cs_f = L.pos_continuation(T, 5, 0.3, False, 10, "ep:9m", min_match=80)
check("an unknown setup falls back to every setup", cs_f and cs_f["pool"] == "every setup", cs_f.get("pool"))
nt = L.pos_new_trade(T, MID, 10)
check("new trade: the setup's trades over their first sessions", nt and nt["pool"] == "this setup" and nt["n"] > 100)

print("Swaps")
held = [("A", {"er": 0.01, "ret": np.array([0.0, 0.02]), "w": np.ones(2), "p10": 0.0}),
        ("B", {"er": 0.05, "ret": np.array([0.04, 0.06]), "w": np.ones(2), "p10": 0.04})]
cands = [("X", {"er": 0.04, "ret": np.array([0.03, 0.05]), "w": np.ones(2), "p10": 0.03})]
SW = L.pos_swaps(held, cands, 10.0)
top = SW.iloc[0]
check("swap A -> X gains 4% - 1% - 0.2% costs", top["sell"] == "A" and abs(top["gain"] - (0.04 - 0.01 - 0.002)) < 1e-12, top.to_dict())
check("swap B -> X loses after costs", SW.set_index("sell").loc["B", "gain"] < 0)
check("P(new does better) is 1 when every draw is higher", SW.iloc[0]["p_better"] == 1.0)

print("The Book file")
rows = L.pos_book_rows(pos)
check("rows: shares only, upper-case, initial stop falls back to the stop",
      len(rows) == 9 and rows["ticker"].str.isupper().all() and rows.iloc[0]["init_stop"] == 95.0)
check("setup ids from labels", L.pos_setup_id(L.LG_SETUPS[MID][1]) == MID and L.pos_setup_id(MID) == MID
      and L.pos_setup_id("") == "")
tmp = Path(tempfile.mkdtemp()) / "book_positions.csv"
pd.DataFrame([{"sleeve": "shares", "ticker": "AAA", "shares": 10, "entry": 20, "stop": 19, "opt_max_loss": None,
               "opt_dollar_delta": None, "note": "old file"}]).to_csv(tmp, index=False)
old = L.BOOK_FILE
L.BOOK_FILE = tmp
b = L.load_book()
check("an old Book file gains the new columns", list(b.columns) == L.BOOK_COLS and b.iloc[0]["trimmed"] == False)
L.save_book(b)
check("and saves with them", list(pd.read_csv(tmp).columns) == L.BOOK_COLS)
L.BOOK_FILE = old
ex = L.pos_examples(P, 3)
check("example positions are readable", (L.pos_status(P, L.pos_book_rows(ex), rules)["action"] != "n/a").all())

print(f"\n{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
