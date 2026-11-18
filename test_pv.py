"""Planted-case tests for Stocks > 30-min pivots: the 30m pivot matches pivot_scanner.py's detect_pivot bar for bar, the
30m pocket pivot and the first-hour break on planted bars, every exit path by hand (a day-1 stop, a day-1 close cut,
breakeven then a gap, a trim and a trailing close, the same trade without the cut), the daily setups (a pocket pivot
day, the 8-week EMA with no look-ahead), no edge on a random walk (the rules don't manufacture R), the scores, and
today's pending triggers.
Run: python test_pv.py"""
import os
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ["LAB_PV_CACHE"] = tempfile.mkdtemp(prefix="pv_test_")
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


# pivot_scanner.py's detect_pivot (War Room, v5.0), verbatim but for logging, to check parity bar for bar
def wr_detect_pivot(df, min_streak=3):
    if len(df) < min_streak + 2:
        return None
    df = df[df["close"] > 0].copy()
    if len(df) < min_streak + 2:
        return None
    trigger_bar, pivot_bar = df.iloc[-1], df.iloc[-2]
    is_green = lambda r: r["close"] > r["open"]
    is_red = lambda r: r["close"] <= r["open"]

    def count_streak(start_idx, qualifier):
        count = 0
        for i in range(start_idx, min(start_idx + 10, len(df))):
            if qualifier(df.iloc[-(i)]):
                count += 1
            else:
                break
        return count
    if is_green(pivot_bar):
        streak = count_streak(3, is_red)
        if streak >= min_streak and float(trigger_bar["close"]) > float(pivot_bar["high"]):
            return {"direction": "bullish", "pivot_bar": pivot_bar}
    return None


def bars(days, rows):
    """30-minute bars from (o, h, l, c, v) rows, 13 a session, from 9:30."""
    idx = []
    for d in days:
        idx += [pd.Timestamp(d) + pd.Timedelta(minutes=570 + 30 * k) for k in range(13)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx[:len(rows)])
    return L.pv_regular(df)


print("Massive's 30-minute bars")
# Saved from Massive (Nov 8 2026): /v2/aggs/ticker/AAOI/range/30/minute/2025-09-15/2025-09-15, adjusted
RAW = [(1359.0, 27.15, 27.25, 27.26, 27.15, 1757923200000), (2879.0, 27.23, 27.15, 27.23, 27.14, 1757925000000),
       (33530.0, 27.49, 27.79, 27.79, 27.0, 1757937600000), (2057218.0, 28.09, 28.92, 29.8, 27.75, 1757943000000),
       (1229949.0, 28.9, 29.21, 29.25, 28.02, 1757944800000), (454821.0, 29.19, 28.825, 29.21, 28.612, 1757946600000),
       (453662.0, 28.8, 28.655, 29.0, 28.63, 1757948400000), (433715.0, 28.66, 28.71, 29.14, 28.6, 1757950200000),
       (280110.0, 28.72, 28.65, 28.95, 28.42, 1757952000000), (255501.0, 28.62, 28.835, 29.02, 28.6186, 1757953800000),
       (269486.0, 28.87, 28.951, 29.03, 28.76, 1757955600000), (431481.0, 28.96, 29.1575, 29.43, 28.96, 1757957400000),
       (374683.0, 29.16, 29.45, 29.57, 29.14, 1757959200000), (291652.0, 29.4783, 29.14, 29.65, 29.135, 1757961000000),
       (319847.0, 29.155, 29.39, 29.4145, 29.11, 1757962800000), (737650.0, 29.4146, 29.565, 29.6, 29.24, 1757964600000),
       (28685.0, 29.56, 29.34, 29.58, 29.25, 1757966400000), (480.0, 29.46, 29.58, 29.58, 29.43, 1757979000000)]
mm = L.pv_regular(L.od_bars([dict(zip(("v", "o", "c", "h", "l", "t"), r_)) for r_ in RAW], daily=False))
check("regular session only: 13 bars, 9:30 (slot 0) to 15:30 (slot 12), pre- and after-market dropped",
      len(mm) == 13 and mm.index[0] == pd.Timestamp("2025-09-15 09:30") and mm["slot"].tolist() == list(range(13)), mm.index[[0, -1]])
check("the 9:30 bar's volume and the 15:30 close", mm["volume"].iloc[0] == 2057218.0 and mm["close"].iloc[-1] == 29.565)

print("The 30m pivot is pivot_scanner.py's")
rng = np.random.default_rng(7)
days = pd.bdate_range("2025-03-03", periods=40)
px, rows = 50.0, []
for _ in range(13 * len(days)):
    o = px
    c = o * (1 + rng.normal(0, 0.004))
    rows.append((o, max(o, c) * (1 + abs(rng.normal(0, 0.002))), min(o, c) * (1 - abs(rng.normal(0, 0.002))), c, 1e5))
    px = c
m = bars(days, rows)
trg = L.pv_triggers(m, {"streak": 3})
mine, theirs = {}, {}
for d, (k, e, s) in trg["pivot30"].items():
    mine[d] = (k - 1, s)
for j in range(4, len(m) - 1):
    r = wr_detect_pivot(m[["open", "high", "low", "close", "volume"]].iloc[: j + 1])
    d = m["day"].iloc[j]
    if r and m["day"].iloc[j + 1] == d and d not in theirs:
        theirs[d] = (j, float(r["pivot_bar"]["low"]))
check("the same trigger bar and stop on every session (40 sessions of random bars)", mine == theirs and len(mine) > 5,
      (len(mine), len(theirs), set(mine) ^ set(theirs)))
d0 = sorted(mine)[0]
k, e, s = trg["pivot30"][d0]
check("in at the next bar's open", abs(e - m["open"].iloc[k]) < 1e-12)

print("The 30m pocket pivot and the first-hour break, planted")
days = pd.bdate_range("2025-01-02", periods=26)
rows = []
for d in days[:-1]:
    for k_ in range(13):
        rows.append((100, 100.3, 99.7, 100.0 + (0.05 if k_ % 2 else -0.05), 1000 * L.PV_PROFILE[k_]))
last = [(100, 100.2, 99.6, 99.8, 1000 * L.PV_PROFILE[0]), (99.8, 99.9, 99.5, 99.6, 1500 * L.PV_PROFILE[1]),
        (99.6, 99.7, 99.3, 99.4, 1200 * L.PV_PROFILE[2]),
        (99.4, 100.4, 99.4, 100.3, 4000 * L.PV_PROFILE[3]),                 # green, upper half, 4x its half-hour's usual volume
        (100.3, 100.35, 100.0, 100.1, 900 * L.PV_PROFILE[4]),              # not over 100.4 yet
        (100.1, 100.9, 100.05, 100.8, 3000 * L.PV_PROFILE[5])]             # through the high: filled at 100.4
rows += last + [(100.8, 101.0, 100.7, 100.9, 1000 * L.PV_PROFILE[k_]) for k_ in range(6, 13)]
m2 = bars(days, rows)
t2 = L.pv_triggers(m2, {"pp30_n": 10, "fh_rvol": 1.3})
dl = pd.Timestamp(days[-1])
check("pocket pivot: filled on the stop over its high (100.4), stop at its low (99.4)", dl in t2["pp30"]
      and abs(t2["pp30"][dl][1] - 100.4) < 1e-9 and abs(t2["pp30"][dl][2] - 99.4) < 1e-9, t2["pp30"].get(dl))
rows_c = rows[: -13] + last[:4] + [(100.3, 100.35, 99.0, 99.1, 900)] + [(99.1, 100.9, 99.0, 100.8, 3000)] + rows[-7:]
t3 = L.pv_triggers(bars(days, rows_c), {"pp30_n": 10})
check("pocket pivot: cancelled when a bar closes under its low before the stop is hit (no fill at 100.4)",
      dl not in t3["pp30"] or abs(t3["pp30"][dl][1] - 100.4) > 1e-9, t3["pp30"].get(dl))
check("first-hour break: a bar after 10:30 over the first hour's high on 1.3x volume, stop at its low",
      dl in t2["fh"] and abs(t2["fh"][dl][2] - 99.5) < 1e-9, t2["fh"].get(dl))
live = L.pv_today(bars(days, rows[: -13] + last[:4]), {"pp30_n": 10})
check("today, live: a pocket pivot waiting for its buy stop", "pp30" in live and live["pp30"]["pending"] and abs(live["pp30"]["entry"] - 100.4) < 1e-9, live)

print("Every exit path by hand")
rules = L.sim_trade_rules({"mode": "next_open", "win": 1, "cap": 3.0, "trail_k": 3.0, "tgt": 2.0, "horizon": 10,
                           "sim_plan": {**L.sim_plan_of({}), "runner": "ema21"}}, next(iter(L.LG_SETUPS)))
day1 = pd.Timestamp("2025-06-02")


def run(path1, daily, cut=True, ma=None):
    """path1: day 1's 30m bars from the fill; daily: (o, h, l, c) rows after day 1."""
    b = bars([day1], path1)
    o, h, l, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(daily) + 1
    D = {"O": np.r_[np.nan, [x[0] for x in daily]], "H": np.r_[np.nan, [x[1] for x in daily]],
         "L": np.r_[np.nan, [x[2] for x in daily]], "C": np.r_[np.nan, [x[3] for x in daily]], "bar_day": b["day"].to_numpy(),
         "MA": np.r_[np.nan, ma] if ma is not None else np.full(n, np.nan), "SIG": None, "ATR": np.full(n, 1.0)}
    return L.pv_manage(o, h, l, c, 0, 100.0, 99.0, 1.0, D, 0, rules, cut, 60, 0.0)


a = run([(100, 100.5, 98.9, 99.2, 1)], [(99, 99, 99, 99)])
check("a bar through the stop on day 1: -1R, 'stopped day 1'", abs(a["r"] + 1) < 1e-12 and a["d1"] == "stop_d1", a)
a = run([(100, 100.5, 99.5, 99.8, 1), (99.8, 99.9, 99.4, 99.6, 1)], [(99.7, 100, 99.5, 99.9)] * 3)
check("day 1 closes under the entry: out at that close (-0.4R)", abs(a["r"] + 0.4) < 1e-12 and a["d1"] == "cut_d1", a)
b_ = run([(100, 100.5, 99.5, 99.8, 1), (99.8, 99.9, 99.4, 99.6, 1)], [(99.7, 100, 99.5, 99.9), (99.9, 100, 98.9, 99.2)], cut=False)
check("...without the cut it rides to the stop (-1R)", abs(b_["r"] + 1) < 1e-12 and b_["d1"] == "held", b_)
a = run([(100, 100.8, 99.6, 100.6, 1)], [(99.5, 100.2, 99.4, 99.8)])
check("held day 1 (closed over the entry): breakeven, a gap under it fills at the open (-0.5R)",
      abs(a["r"] + 0.5) < 1e-12 and a["d1"] == "held" and a["outcome"] == "stop", a)
a = run([(100, 100.8, 99.6, 100.6, 1)], [(100.7, 102.5, 100.6, 102.2), (102.2, 103.0, 101.8, 102.8), (102.8, 103.0, 101.0, 101.2)],
        ma=np.array([100.0, 101.0, 101.5]))
f = 1 / 3
check("a trim at 2R (102) on day 2, then out on the first close under the 21-day EMA (101.2)",
      a["trimmed"] and a["outcome"] == "trail" and abs(a["r"] - (f * 2.0 + (1 - f) * 1.2)) < 1e-12, a)
rc = L.pv_manage(*[bars([day1], [(100, 100.5, 98.9, 99.2, 1)])[k].to_numpy(float) for k in ("open", "high", "low", "close")], 0,
                 100.0, 99.0, 1.0, {"O": np.r_[np.nan, 99.0], "H": np.r_[np.nan, 99.0], "L": np.r_[np.nan, 99.0],
                                    "C": np.r_[np.nan, 99.0], "bar_day": np.array([day1]), "MA": None, "SIG": None,
                                    "ATR": np.ones(2)}, 0, rules, True, 60, 10.0)
check("costs: 10bp a side on a 1% stop is 0.2R", abs(rc["r"] + 1.2) < 1e-9, rc["r"])

print("The daily setups")
n = 140
idx = pd.bdate_range("2025-01-01", periods=n)
c = pd.Series(np.linspace(50, 80, n), index=idx)
v = pd.Series(1e6, index=idx)
c.iloc[-12:] = c.iloc[-13] * np.array([1.0, 0.99, 1.0, 0.99, 1.0, 0.99, 1.0, 0.99, 1.0, 0.99, 1.0, 1.01])
v.iloc[-12:-1] = np.where(np.diff(np.r_[c.iloc[-13], c.iloc[-12:-1].to_numpy()]) < 0, 1.5e6, 0.8e6)
v.iloc[-1] = 1.6e6
Pd = {"close": c.to_frame("X"), "open": c.to_frame("X") * 0.999, "high": c.to_frame("X") * 1.005, "low": c.to_frame("X") * 0.995,
      "volume": v.to_frame("X")}
cx = L.pv_context(Pd, {"pp_band": 4.0, "pp_look": 3, "e8_lo": -3.0, "e8_hi": 6.0, "base_step": 5})
check("a pocket pivot: up on 1.6M against down days of 1.5M, at the 10-day, in an uptrend", bool(cx["pp_day"]["X"].iloc[-1]))
v2 = v.copy()
v2.iloc[-1] = 1.4e6
cx2 = L.pv_context({**Pd, "volume": v2.to_frame("X")}, {"pp_band": 4.0})
check("...not when the volume falls short of the biggest down day", not bool(cx2["pp_day"]["X"].iloc[-1]))
check("eligible from the next session, not the same one (known at the close)", bool(cx["elig"]["pp"]["X"].iloc[-1]) is False
      and bool(cx["now"]["pp"]["X"]))
e8, prev = L.pv_ema8w(Pd["close"])
c3 = Pd["close"].copy()
c3.iloc[-3:] = 500.0                                                  # a jump later in the week
e8b, _ = L.pv_ema8w(c3)
check("the 8-week EMA uses no later close (changing the last 3 days leaves the day before alone)",
      np.allclose(e8.iloc[:-3].to_numpy(), e8b.iloc[:-3].to_numpy(), equal_nan=True))
wk = Pd["close"]["X"].groupby(Pd["close"].index.to_period("W-FRI")).last()
ew = wk.ewm(span=8, adjust=False, min_periods=8).mean()
day = Pd["close"].index[-1]
by_hand = 2 / 9 * Pd["close"]["X"].iloc[-1] + 7 / 9 * ew.iloc[-2]
check("today's 8-week EMA by hand: 2/9 x today's close + 7/9 x last completed week's", abs(e8["X"].iloc[-1] - by_hand) < 1e-9)

print("No edge on a random walk")
g = np.random.default_rng(42)
nd, names = 260, 10
dix = pd.bdate_range("2024-01-02", periods=nd)
Pr = {k: pd.DataFrame(index=dix) for k in ("open", "high", "low", "close", "volume")}
m30 = {}
for t in range(names):
    nm = f"R{t}"
    steps = g.normal(0.0, 0.0012, (nd, 13 * 30))
    lp = np.log(100) + np.cumsum(steps.ravel()).reshape(nd, -1)
    px = np.exp(lp)
    prev = np.r_[100, px.ravel()[:-1]].reshape(nd, -1)
    o30, c30 = prev[:, ::30], px[:, 29::30]
    hh = np.maximum(prev, px).reshape(nd, 13, 30).max(axis=2)
    ll = np.minimum(prev, px).reshape(nd, 13, 30).min(axis=2)
    idx30 = pd.DatetimeIndex(np.repeat(dix.values, 13)) + pd.to_timedelta(np.tile(570 + 30 * np.arange(13), nd), unit="m")
    m30[nm] = L.pv_regular(pd.DataFrame({"open": o30.ravel(), "high": hh.ravel(), "low": ll.ravel(), "close": c30.ravel(),
                                         "volume": 1e5}, index=idx30))
    Pr["open"][nm], Pr["close"][nm] = o30[:, 0], c30[:, -1]
    Pr["high"][nm], Pr["low"][nm], Pr["volume"][nm] = hh.max(axis=1), ll.min(axis=1), 2e6
res = L.pv_run(Pr, lambda t: m30[t], {"streak": 3, "pp30_n": 10, "fh_rvol": 1.3, "min_risk": 0.05, "max_risk_atr": 5.0, "cd": 1,
                                       "base_step": 1, "cost": 0.0, "hold": 20, "pp_band": 4.0, "e8_lo": -3.0, "e8_hi": 6.0},
               {**L.sim_plan_of({}), "runner": "ema10"}, workers=2)
T = res["trades"]
x = T[(T["context"] == "any") & ~T["wide"] & (T["outcome"] != "open")]
for tr in ("pivot30", "open"):
    r = x[x["trigger"] == tr]["r"]
    se = r.std() / np.sqrt(len(r))
    check(f"{tr}: E[R] within 3 s.e. of zero with no costs ({len(r)} trades: {r.mean():+.3f} ± {se:.3f})",
          len(r) > 60 and abs(r.mean()) < 3 * se + 0.02)

print("The scores")
rng2 = np.random.default_rng(3)
dts = pd.bdate_range("2024-01-02", periods=80)
T2 = pd.DataFrame({"context": "e8", "trigger": np.repeat(["pivot30", "open"], 160), "date": np.tile(np.repeat(dts, 2), 2),
                   "r": np.r_[rng2.normal(0.4, 1.0, 160), rng2.normal(0.0, 1.0, 160)], "wide": False, "outcome": "trail",
                   "d1": np.tile(["stop_d1", "held"], 160), "risk_pct": 0.5, "risk_atr": 0.4, "hold": 5})
T2["r_nocut"] = T2["r"] - np.where(T2["trigger"] == "pivot30", 0.1, 0.0)
S2 = L.pv_score(T2, {"e8": 1000}).set_index("trigger")
check("a planted +0.4R entry is an EDGE; a planted zero is NOISE", S2.at["pivot30", "verdict"] == "EDGE" and S2.at["open", "verdict"] == "NOISE",
      S2[["er_date", "t", "verdict"]])
check("the day-1 cut's value, paired by date (+0.1R)", abs(S2.at["pivot30", "cut_gain"] - 0.1) < 1e-9)
check("vs the next-open entry on the same setup", abs(S2.at["pivot30", "vs_open"] - (S2.at["pivot30", "er_date"] - S2.at["open", "er_date"])) < 1e-12)
check("cut-or-run shares and the losers' average", abs(S2.at["pivot30", "p_stop_d1"] - 0.5) < 1e-12
      and np.isfinite(S2.at["pivot30", "r_d1_losers"]))

print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
