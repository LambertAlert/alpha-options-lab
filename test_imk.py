"""Planted-case tests for Market > Intermarket: the trend score (up, down, noise, no look-ahead, the shock), the
vol-control weight by hand, index confirmation and Dow Theory states on planted indices, the tape vs the quad, mechanical positioning (stacked, unwinding), the trend board, the breakout
trades read by state, and the reads reaching the Setup ledger's context and split list.
Run: python test_imk.py"""
import math
import warnings

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


n = 900
idx = pd.bdate_range("2023-01-02", periods=n)
g = np.random.default_rng(1)
walk = lambda mu, sig, seed: pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(mu, sig, n))), index=idx)

print("Trend score")
up, dn, flat = walk(0.002, 0.01, 1), walk(-0.002, 0.01, 2), walk(0.0, 0.01, 3)
tu, td, tf = L.imk_trend(up), L.imk_trend(dn), L.imk_trend(flat)
check("a steady uptrend reads near +1, a downtrend near -1", tu.iloc[-1] > 0.8 and td.iloc[-1] < -0.8, (tu.iloc[-1], td.iloc[-1]))
check("bounded in [-1, 1] and NaN before 252 sessions", tu.dropna().between(-1, 1).all() and tu.iloc[:250].isna().all())
r = np.log(flat).diff(); vol = r.rolling(90, min_periods=45).std()
hand = np.mean([np.clip((np.log(flat.iloc[-1]) - np.log(flat.iloc[-1 - L_])) / (vol.iloc[-1] * math.sqrt(L_)), -1, 1) for L_ in (80, 160, 252)])
check("by hand: each lookback's return in units of its volatility, capped, averaged", abs(tf.iloc[-1] - hand) < 1e-12, (tf.iloc[-1], hand))
fut = up.copy(); fut.iloc[-50:] *= 0.5
check("no look-ahead: changing the last 50 sessions leaves earlier scores alone", np.allclose(L.imk_trend(fut).iloc[:-50].dropna(), tu.iloc[:-50].dropna()))
s3 = L.imk_trend_shocked(flat, -0.05)
c2 = pd.concat([flat, pd.Series([flat.iloc[-1] * 0.95], index=[flat.index[-1] + pd.Timedelta(days=1)])])
check("the shocked score is the score after one more session 5% under today's close", abs(s3 - L.imk_trend(c2).iloc[-1]) < 1e-12 and s3 < tf.iloc[-1])

print("Vol-control weight")
alt_ = pd.Series(100 * np.exp(np.cumsum(np.tile([0.01, -0.01], n // 2))), index=idx)
vc = L.imk_volctl(alt_)
rv = 0.01 * math.sqrt(n / (n - 1)) * 0 + np.log(alt_).diff().rolling(20).std().iloc[-1] * math.sqrt(252)
check("weight = 10% / realized vol (the higher of 20 and 60 days)", abs(vc.iloc[-1] - 0.10 / rv) < 1e-9, (vc.iloc[-1], 0.10 / rv))
calm = walk(0.0, 0.002, 4)
check("capped at 1.5 in a very calm market", abs(L.imk_volctl(calm).iloc[-1] - 1.5) < 1e-12)
check("a 5% down day cuts the weight", L.imk_volctl_shocked(alt_, -0.05) < vc.iloc[-1])

print("Confirmation and Dow Theory")


def panel(spy, qqq, iwm, iyt, rsp, dia):
    return pd.DataFrame({"SPY": spy, "QQQ": qqq, "IWM": iwm, "IYT": iyt, "RSP": rsp, "DIA": dia})


strong, weak = walk(0.0015, 0.002, 5), walk(-0.0015, 0.002, 6)   # smooth, so the last day sits at the high / low
f1 = L.imk_frame(panel(strong, strong, strong * 1.01, strong * 0.99, strong, strong))
f2 = L.imk_frame(panel(strong, strong, weak, weak, strong * 0 + weak, strong))
f3 = L.imk_frame(panel(weak, weak, weak, weak, weak, weak))
check("leaders at highs, small caps / transports / equal weight healthy: CONFIRMED", f1["imk_confirm"].iloc[-1] == "CONFIRMED", f1["imk_confirm"].iloc[-1])
check("leaders at highs, the three legs in downtrends: NARROW", f2["imk_confirm"].iloc[-1] == "NARROW", f2["imk_confirm"].iloc[-1])
check("everything falling: BROAD WEAKNESS", f3["imk_confirm"].iloc[-1] == "BROAD WEAKNESS", f3["imk_confirm"].iloc[-1])
check("no state before there is a year of history", (f1["imk_confirm"].iloc[:190] == "").all())
dw1, dw3 = L.dow_theory(panel(strong, strong, strong, strong, strong, strong)), L.dow_theory(panel(weak, weak, weak, weak, weak, weak))
check("Dow Theory as a daily state: the lab's primary trend, both averages rising = PRIMARY UP, both falling = PRIMARY DOWN",
      f1["imk_dow"].iloc[-1] == "PRIMARY " + dw1["now"] == "PRIMARY UP" and f3["imk_dow"].iloc[-1] == "PRIMARY DOWN",
      (f1["imk_dow"].iloc[-1], f3["imk_dow"].iloc[-1]))
check("Industrials rising with Transports falling never confirms a new primary up trend", f2["imk_dow"].iloc[-1] != "PRIMARY UP", f2["imk_dow"].iloc[-1])
D = L.imk_dow_record(panel(strong, strong, weak, weak, weak, strong).assign(SPY=strong))
check("the Dow record: episodes counted once, against every day", len(D) == 2 and D.iloc[0]["cases"] >= 1 and D.iloc[1]["cases"] > D.iloc[0]["cases"], D.to_dict("records"))

print("Rotation and the quad")
cols = {t: walk(0.0, 0.01, 20 + k) for k, t in enumerate(["SPY", "QQQ", "IWM", "HYG", "EEM", "GLD", "DBC", "USO", "UUP", "TLT", "IEF", "CPER",
                                                          "XLP", "XLU", "XLV", "XLY", "XLK", "XLI", "XLF", "SMH"])}
for t in ("TLT", "IEF", "UUP", "GLD", "XLP", "XLU", "XLV"):
    cols[t] = walk(0.002, 0.008, 50 + len(t))
for t in ("IWM", "QQQ", "DBC", "USO", "HYG", "EEM", "XLY", "XLK", "XLI", "XLF", "SMH"):
    cols[t] = walk(-0.002, 0.008, 80 + len(t))
Q = pd.DataFrame(cols)
quad = pd.Series("DEFLATION SCARE", index=idx)
fq = L.imk_frame(Q, quad)
check("a deflation scare with bonds, dollar, gold and defensives leading: the tape CONFIRMS", fq["imk_quad_tape"].iloc[-1] == "CONFIRMS", fq["imk_quad_gap"].iloc[-1])
check("defensives lead cyclicals", fq["imk_def"].iloc[-1] == "DEFENSIVES LEAD" and fq["imk_def_gap"].iloc[-1] > 1)
fq2 = L.imk_frame(Q, pd.Series("REFLATION", index=idx))
check("the same tape under a reflation quad CONTRADICTS", fq2["imk_quad_tape"].iloc[-1] == "CONTRADICTS", fq2["imk_quad_gap"].iloc[-1])
B = L.imk_board(Q, [(t, t, "x") for t in ("TLT", "DBC", "SPY")])
check("the board sorts by trend, with 12-1 month momentum and its rank", B["etf"].iloc[0] == "TLT" and B["etf"].iloc[-1] == "DBC"
      and abs(B.set_index("etf").loc["TLT", "mom_12_1"] - (Q["TLT"].iloc[-22] / Q["TLT"].iloc[-253] - 1)) < 1e-12 and B["rank"].min() == 1)

print("Mechanical positioning")
quiet_up = pd.Series(100 * np.exp(np.cumsum(np.r_[np.random.default_rng(3).normal(0.0005, 0.02, 600), np.random.default_rng(4).normal(0.003, 0.003, 300)])), index=idx)
fs = L.imk_frame(pd.DataFrame({"SPY": quiet_up}))
check("a quiet steady rally after a volatile spell: STACKED", fs["imk_flow"].iloc[-1] == "STACKED", (fs["imk_cta"].iloc[-1], fs["imk_vc_pct"].iloc[-1]))
crash = quiet_up.copy(); crash.iloc[-8:] = crash.iloc[-9] * np.exp(np.cumsum(np.full(8, -0.04)))
fc = L.imk_frame(pd.DataFrame({"SPY": crash}))
check("then eight 4% down days: UNWINDING", fc["imk_flow"].iloc[-1] == "UNWINDING", (fc["imk_cta"].iloc[-1], fc["imk_vc"].iloc[-1]))

print("Your setups and the ledger")
ev = pd.DataFrame({"setup": ["zg:vol"] * 40 + ["tl:full"] * 40 + ["pb:rsi2"] * 20, "status": 0,
                   "date": np.r_[np.tile(idx[-200:-180], 2), np.tile(idx[-50:-30], 2), idx[-100:-80]],
                   "r": np.r_[np.full(40, 1.0), np.full(40, -0.5), np.full(20, 9.0)]})
fx = pd.DataFrame({"imk_confirm": np.where(np.arange(n) < n - 120, "CONFIRMED", "NARROW")}, index=idx)
T = L.imk_setups(ev, fx).set_index(["read", "state"])
check("only breakout-type trades are read (the Pullback trades are left out)", T.loc[("All breakout-type trades", "all"), "trades"] == 80)
check("read by the state on the signal day", abs(T.loc[("Index confirmation", "CONFIRMED"), "er"] - 1.0) < 1e-12
      and abs(T.loc[("Index confirmation", "NARROW"), "er"] + 0.5) < 1e-12)
ctx = L.lg_spy_context(None, {"imk": fq}, idx[-10:])
check("the ledger's context carries the reads on each date", (ctx["imk_quad_tape"] == "CONFIRMS").all() and np.isfinite(ctx["imk_cta"]).all() is not None
      and all(c_ in ctx for c_ in L.IMK_LEDGER_CAT + L.IMK_LEDGER_NUM))
evs = pd.DataFrame({"imk_flow": ["STACKED", "", "LIGHT"]})
sc = L.lg_split_col(evs, "imk_flow")
check("each read is a ledger split", all(k in L.LG_SPLITS for k in ("imk_confirm", "imk_dow", "imk_flow", "imk_quad_tape", "imk_def"))
      and sc.tolist() == ["STACKED", "n/a", "LIGHT"], sc.tolist())

print("The page")
need = sorted({t for _, t, _ in L.IMK_ASSETS} | {t for _, t in L.IMK_SECTORS} | {"DIA", "IYT", "RSP"})
Pn = pd.DataFrame({t: walk(0.0004, 0.012, 200 + k) for k, t in enumerate(need)})
nar = pd.DataFrame({"nar_quad": "GOLDILOCKS"}, index=idx)
pg = L.imk_page(Pn, nar)
check("the page builds every part", len(pg["legs"]) == 6 and pg["dow_now"] is not None and len(pg["assets"]) == len(L.IMK_ASSETS)
      and len(pg["sectors"]) == len(L.IMK_SECTORS) and len(pg["shocks"]) == 3 and pg["quad"] == "GOLDILOCKS")
check("bigger shocks mean more selling", pg["shocks"]["cta_change"].is_monotonic_decreasing and pg["shocks"]["vc_change"].is_monotonic_decreasing and (pg["shocks"]["cta_change"] < 0).all(),
      pg["shocks"].to_dict("records"))

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
