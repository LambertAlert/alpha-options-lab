"""Planted-case tests for the Quantified Strategies additions: IBS and RSI(2) by hand, the Pullback family's four
setups on planted bars (and not under the 200-day), the signal-day-close entry (entry, a gap through the stop or the
target at the next open, R from the close), the next-open and buy-stop entries unchanged against the previous file,
the NYSE calendar (Good Friday, an observed July 4, the turn of the month, options-expiration week), the calendar
splits, the close-vs-open comparison on a planted overnight drift, and the RS 8-week columns (ATR extension, RSI(2),
IBS, the stretched flag).
Run: python test_qs.py"""
import importlib.util
import os
import sys
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ["PLAYBOOK_DATA"] = tempfile.mkdtemp(prefix="qs_test_")
import alpha_options_lab as L
import playbook as PB

PASS, FAIL = 0, []


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


print("IBS and RSI(2) by hand")
idx = pd.bdate_range("2025-01-02", periods=6)
c = pd.DataFrame({"X": [10.0, 11.0, 10.5, 10.0, 10.6, 10.6]}, index=idx)
h, l_ = c + 0.5, c - 0.5
l_.iloc[2, 0] = 10.4                                        # day 2: close 10.5 in a 10.4-11.0 range
h.iloc[2, 0] = 11.0
ind = L.lg_oversold(c, h, l_, c)
check("IBS = (close - low) / (high - low): (10.5 - 10.4) / 0.6", abs(ind["ibs"]["X"].iloc[2] - 0.1 / 0.6) < 1e-12)
d = c["X"].diff()
up, dn = [np.nan, 1.0], [np.nan, 0.0]
for x in d.iloc[2:]:
    up.append(0.5 * max(x, 0) + 0.5 * up[-1])
    dn.append(0.5 * max(-x, 0) + 0.5 * dn[-1])
rsi = [np.nan] + [100 - 100 / (1 + u / q) if q > 0 else 100.0 for u, q in zip(up[1:], dn[1:])]
check("RSI(2), Wilder's smoothing (alpha 1/2), by hand", np.allclose(ind["rsi2"]["X"].iloc[2:].to_numpy(), np.array(rsi[2:]), atol=1e-9),
      (ind["rsi2"]["X"].round(3).tolist(), np.round(rsi, 3).tolist()))
z = L.lg_oversold(c, c, c, c)
check("a zero-range day has no IBS", z["ibs"]["X"].isna().all())

print("The Pullback family on planted bars")
n = 320
ix = pd.bdate_range("2024-01-02", periods=n)
cl = pd.Series(50 * 1.003 ** np.arange(n), index=ix)
cl.iloc[-3:] = cl.iloc[-4] * np.array([0.99, 0.98, 0.97])        # three lower closes at the end
vol = pd.Series(2e6, index=ix)
Pq = {"close": cl.to_frame("UP"), "open": cl.to_frame("UP") * 1.001, "high": cl.to_frame("UP") * 1.01,
      "low": cl.to_frame("UP") * 0.995, "volume": vol.to_frame("UP")}
Pq["low"].iloc[-1, 0] = cl.iloc[-1] * 0.999                      # the last close near its low: IBS small
dn_ = cl.copy()
dn_[:] = 50 * 0.997 ** np.arange(n)
dn_.iloc[-3:] = dn_.iloc[-4] * np.array([0.99, 0.98, 0.97])
Pd = {k: pd.concat([v, (v["UP"] / cl * dn_).to_frame("DN") if k != "volume" else v["UP"].to_frame("DN")], axis=1) for k, v in Pq.items()}
prm = {**PB.pb_ledger_prm({}), "min_price": 1.0, "min_dv": 1.0}
ch = L.lg_chunk(Pd, None, ("Pullback",), "12/26/9", prm)
ev = ch["ev"]
last = ix[-1]
fired = set(ev[(ev["date"] >= ix[-3]) & (ev["ticker"] == "UP")]["setup"])
check("over the 3-day dip: three lower closes, a 5-day-low close, RSI(2) under 10 and IBS under 0.2 all fire (first day each)",
      {"pb:down3", "pb:low5", "pb:rsi2", "pb:ibs"} <= fired, fired)
check("none fire in the downtrend (under the 200-day)", not len(ev[(ev["ticker"] == "DN") & ev["setup"].str.startswith("pb:")]))
check("the family's exit defaults: a 2R target, 5 sessions when time limits are per family",
      L.LG_EXIT_SEED["Pullback"] == "target" and L.LG_TL_SEED["Pullback"] == 5)

print("The signal-day-close entry")
nn = 8
I = pd.bdate_range("2025-03-03", periods=nn)
O = np.array([[100.0], [102.0], [96.0], [100.0], [100], [100], [100], [100]])
Hh = O + 0.5
Lw = O - 0.5
C_ = np.array([[100.0], [101.0], [100.0], [100.0], [100], [100], [100], [100]])
A = np.full((nn, 1), 2.0)
lab = L.lg_label(O, Hh, Lw, C_, A, np.array([0]), np.array([0]), np.array([98.0]), "close", 1, 2.0, 0, 3.0, 0.5, 0.0)
check("in at the signal day's close (100), risk 2 to the 98 stop", lab["entry"][0] == 100.0 and lab["risk"][0] == 2.0)
check("the next open gaps over the 2R target (104)? no: 102 opens under it; the day's high 102.5 doesn't reach it either",
      lab["outcome"][0] != 0 or lab["exit_i"][0] > 1)
lab2 = L.lg_label(O, Hh, Lw, C_, A, np.array([1]), np.array([0]), np.array([99.5]), "close", 1, 2.0, 0, 3.0, 0.5, 0.0)
check("a gap under the stop at the next open fills at the open (96), not the stop", lab2["exit"][0] == 96.0 and lab2["exit_i"][0] == 2
      and abs(lab2["r"][0] - (96.0 - 101.0) / 1.5) < 1e-12, (lab2["exit"][0], lab2["r"][0]))
O3 = O.copy()
O3[1, 0] = 106.0
lab3 = L.lg_label(O3, np.maximum(O3, Hh), Lw, C_, A, np.array([0]), np.array([0]), np.array([98.0]), "close", 1, 2.0, 0, 3.0, 0.5, 0.0)
check("a gap over the target at the next open fills at the open (106 > 104)", lab3["exit"][0] == 106.0 and lab3["outcome"][0] == 0)
lab4 = L.lg_label(O3, np.maximum(O3, Hh), Lw, C_, A, np.array([0]), np.array([0]), np.array([98.0]), "next_open", 1, 2.0, 0, 3.0, 0.5, 0.0)
check("the next-open entry on the same signal buys after that gap (106)", lab4["entry"][0] == 106.0)

spec = importlib.util.spec_from_file_location("lab_old", os.environ.get("LAB_OLD", ""))
if spec and os.path.exists(os.environ.get("LAB_OLD", "")):
    O_ = importlib.util.module_from_spec(spec)
    sys.modules["lab_old"] = O_
    spec.loader.exec_module(O_)
    rng = np.random.default_rng(5)
    px = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, (300, 8)), axis=0))
    Ov = px * (1 + rng.normal(0, 0.005, px.shape))
    Hv, Lv = np.maximum(px, Ov) * 1.01, np.minimum(px, Ov) * 0.99
    Av = np.full(px.shape, 1.0)
    ii, jj = rng.integers(10, 280, 200), rng.integers(0, 8, 200)
    lv = px[ii, jj] * 0.95
    same = True
    for mode in ("next_open", "buy_stop"):
        a_ = L.lg_label(Ov, Hv, Lv, px, Av, ii, jj, lv, mode, 2, 2.0, 10, 3.0, 0.5, 10.0)
        b_ = O_.lg_label(Ov, Hv, Lv, px, Av, ii, jj, lv, mode, 2, 2.0, 10, 3.0, 0.5, 10.0)
        same &= all(np.array_equal(np.nan_to_num(a_[k], nan=-9), np.nan_to_num(b_[k], nan=-9)) for k in b_)
    check("next-open and buy-stop entries give identical trades to the previous file (200 random events)", same)
else:
    print("  (set LAB_OLD to the previous alpha_options_lab.py to run the regression check)")

print("The NYSE calendar and the calendar splits")
K = L.lg_calendar(["2025-04-17", "2026-07-02", "2026-10-26", "2026-10-30", "2026-11-03", "2026-11-19", "2026-11-25"])
check("after Thursday Apr 17 2025 comes Monday Apr 21 (Good Friday closed)", K["entry_day"].iloc[0] == pd.Timestamp("2025-04-21"))
check("after Jul 2 2026 comes Jul 6 (July 4 on a Saturday, observed Friday Jul 3)", K["entry_day"].iloc[1] == pd.Timestamp("2026-07-06"))
check("Oct 27 2026 is the 4th-last session of October; Nov 2 the 1st of November",
      K["from_end"].iloc[2] == 4 and K["from_start"].iloc[3] == 1)
check("Nov 20 2026 is options-expiration Friday; Nov 27 (after Thanksgiving) isn't in that week",
      bool(K["opex_week"].iloc[5]) and not bool(K["opex_week"].iloc[6]))
evc = pd.DataFrame({"date": pd.to_datetime(["2026-10-26", "2026-10-20", "2026-11-03", "2026-11-05"])})
tom = L.lg_split_col(evc, "tom").tolist()
check("turn of the month: entries in the last 4 or first 3 sessions", tom == ["turn of the month", "rest of the month",
                                                                             "turn of the month", "rest of the month"], tom)
check("the splits are on the scoreboard's list", all(k in L.LG_SPLITS for k in ("tom", "opex", "weekday")))

print("Close vs next open on a planted overnight drift")
n2 = 120
ix2 = pd.bdate_range("2025-01-02", periods=n2)
op, clo = np.zeros(n2), np.zeros(n2)
p_ = 50.0
for t in range(n2):
    op[t] = p_ * 1.01                                       # every session opens 1% over the prior close...
    clo[t] = op[t] * 0.999                                  # ...and gives a little back during the day
    p_ = clo[t]
Pg = {"open": pd.DataFrame({"G": op}, index=ix2), "close": pd.DataFrame({"G": clo}, index=ix2),
      "high": pd.DataFrame({"G": op * 1.002}, index=ix2), "low": pd.DataFrame({"G": clo * 0.998}, index=ix2),
      "volume": pd.DataFrame({"G": 1e6}, index=ix2)}
evg = pd.DataFrame({"setup": "pb:rsi2", "ticker": "G", "date": ix2[20:100:5], "status": 0, "plan_risk_atr": 1.5,
                    "atr_pct": 1.2, "cost_bp": 0.0})
prm_g = {**PB.pb_ledger_prm({}), "horizon": 5, "exit_mode": "target", "tl_mode": "all", "tl": 5}
res = L.lg_entry_timing(Pg, evg, prm_g)
T = res["table"].set_index("setup_id")
check("the close entry keeps the overnight gap: E[R] at the close beats the next open",
      T.at["pb:rsi2", "er_close"] > T.at["pb:rsi2", "er_open"] and T.at["pb:rsi2", "diff"] > 0, T)
check("the overnight gap in R is positive (opens over the signal close)", T.at["pb:rsi2", "gap_r"] > 0)

print("RS 8-week: extension in ATRs and the short-term stretch")
cfg = PB.pb_cfg("demo")
cfg["uni"] = cfg["uni"].head(10)
bars, _ = PB.pb_bars(cfg)
sym = next(iter(bars))
spy = bars[sym]["close"] * 0 + 100.0
row, _ = L.rs8_one(sym, bars[sym], spy)
dfx = bars[sym]
e21 = dfx["close"].ewm(span=21, adjust=False).mean()
a14 = L._mc_atr(*(dfx[[k]].set_axis(["x"], axis=1) for k in ("high", "low", "close")), 14).iloc[-1, 0]
check("21-day extension in ATRs by hand", abs(row["ext21_atr"] - (dfx["close"].iloc[-1] - e21.iloc[-1]) / a14) < 1e-9)
check("RSI(2), IBS and the flags are in the row", all(k in row for k in ("rsi2", "ibs", "st_oversold", "st_stretched"))
      and row["st_stretched"] == (row["rsi2"] > 95 and row["ibs"] > 0.8))
check("presets for oversold, stretched and 3+ ATR", all(k in L.RS8_PRESETS for k in ("dip", "stretch", "atr3")))

print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
