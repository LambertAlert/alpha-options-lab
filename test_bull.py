"""Planted-case tests for Options > Bull spreads: leader and Stage 2 states, the seven bull setups (the mean-reversion
dip inside a leader, a leading group or an uptrend among them), long labels and the uptrend baseline, the bull call
debit and bull put credit priced on a path by hand, scoring, today's plan and the live structures.
Run: python test_bull.py"""
import math, warnings
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


print("leaders, Stage 2 and the setups")
N = 700
idx = pd.bdate_range("2023-01-02", periods=N)
rng = np.random.default_rng(3)
names = ["LEAD"] + [f"F{k:02d}" for k in range(24)]
C = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.004, (N, len(names))), axis=0)), index=idx, columns=names)
C["LEAD"] = np.linspace(50, 220, N)
O = C.shift(1).fillna(C)
Hh = np.maximum(O, C) * 1.005
Lo = np.minimum(O, C) * 0.995
V = pd.DataFrame(2e6, index=idx, columns=names)
rs = L.lg_rs_rating(C)
S = L.br_states(O, Hh, Lo, C, V, rs)
check("a steady riser is an RS leader in Stage 2 over a rising 40-day", bool(S["lead"]["LEAD"].iloc[-1])
      and bool(S["stage2"]["LEAD"].iloc[-1]) and bool(S["up"]["LEAD"].iloc[-1]))
check("Stage 2 never without a rising 150-day and the 40-day over it; a leader is RS 80+ that day",
      not (S["stage2"] & ~(S["rise150"] & (S["s_bl"] > S["s150"]))).any().any() and not (S["lead"] & (rs < 80)).any().any())
s40 = C.rolling(40, min_periods=40).mean()
check("the bull side runs on the 40-day: uptrend = over a 40-day higher than 10 sessions ago",
      L.BL_MA == 40 and S["s_bl"].equals(s40) and S["up"].equals((C > s40) & (s40 > s40.shift(10))))
s50_ = C.rolling(50, min_periods=50).mean()
check("the bear side keeps the 50-day", S["s50"].equals(s50_) and S["down"].equals((C < s50_) & (s50_ < s50_.shift(10))))
check("bull labels name the 40-day; bear labels keep the 50-day",
      "40-day" in L.BL_SETUPS["bl:pullback_ma"][1] and "40-day" in L.BL_SETUPS["base:uptrend"][1]
      and "50-day" in L.BR_SETUPS["base:downtrend"][1] and "bl:pullback50" not in L.BL_SETUPS)
Cf = C.copy()
Cf["F00"] = np.linspace(200, 60, N)
Sf = L.br_states(Cf.shift(1).fillna(Cf), Cf * 1.005, Cf * 0.995, Cf, V, L.lg_rs_rating(Cf))
check("a steady faller is never a Stage 2 leader", not (Sf["lead"] & Sf["stage2"])["F00"].any())

# pullback to the rising 40-day that holds: dip to the 40-day, then a green close back over it. The leader here rises
# 0.3% a day, so its lows normally run ~5% over the 40-day (the linear riser above sits inside the 2% band every day)
C2 = C.copy()
C2["LEAD"] = np.geomspace(50, 400, N)
O2 = C2.shift(1).fillna(C2)
H2, L2 = np.maximum(O2, C2) * 1.005, np.minimum(O2, C2) * 0.995
k = 600
sma = C2["LEAD"].rolling(40).mean()
L2.iloc[k - 1, 0] = sma.iloc[k - 1] * 1.01
C2.iloc[k - 1, 0] = sma.iloc[k - 1] * 1.02
O2.iloc[k, 0] = sma.iloc[k] * 1.01
C2.iloc[k, 0] = sma.iloc[k] * 1.05
H2.iloc[k, 0] = sma.iloc[k] * 1.052
L2.iloc[k, 0] = sma.iloc[k] * 1.008
S2 = L.br_states(O2, H2, L2, C2, V, L.lg_rs_rating(C2))
sig = L.br_signals(O2, H2, L2, C2, V, S2, None, 15, side="bull")
check("pullback to the rising 40-day holds: fires on the green close back over it",
      bool(sig["bl:pullback_ma"]["LEAD"].iloc[k]) and not sig["bl:pullback_ma"]["LEAD"].iloc[k - 40:k - 3].any())
check("bull setups only (no bear ids)", all(s_.startswith("bl:") for s_ in sig))
# new 55-day closing high on volume
V3 = V.copy()
V3.iloc[650, 0] = 4e6
sig3 = L.br_signals(O, Hh, Lo, C, V3, S, None, 15, side="bull")
check("a 55-day closing high on 1.4x volume fires; the same high on quiet volume doesn't",
      bool(sig3["bl:breakout55"]["LEAD"].iloc[650]) and not sig3["bl:breakout55"]["LEAD"].iloc[649])
# positive EP
C4, O4, H4, L4, V4 = C.copy(), O.copy(), Hh.copy(), Lo.copy(), V.copy()
j = names.index("F03")
pc = C4.iloc[599, j]
O4.iloc[600, j], L4.iloc[600, j], H4.iloc[600, j], C4.iloc[600, j] = pc * 1.05, pc * 1.045, pc * 1.09, pc * 1.085
V4.iloc[600, j] = 8e6
sig4 = L.br_signals(O4, H4, L4, C4, V4, L.br_states(O4, H4, L4, C4, V4, rs), None, 15, side="bull")
check("positive episodic pivot: a 5% gap up on 4x volume closing strong", bool(sig4["bl:ep_up"]["F03"].iloc[600])
      and int(sig4["bl:ep_up"].sum().sum()) == 1)
check("20-day high breakout fires over a rising 150-day", bool(sig["bl:dc20_up"]["LEAD"].iloc[300:600].any())
      and not sig["bl:dc20_up"]["LEAD"].iloc[:149].any())

print("the mean-reversion dip, bought inside leaders and leading groups")
C5 = C.copy()
for d in range(3):                                      # LEAD dips three days in a row at the end
    C5.iloc[N - 3 + d, 0] = C5.iloc[N - 4, 0] * (0.985 ** (d + 1))
O5 = C5.shift(1).fillna(C5)
P5 = {"open": O5, "high": np.maximum(O5, C5) * 1.005, "low": np.minimum(O5, C5) * 0.995, "close": C5, "volume": V}
mp = L.br_mrv_pct(P5)
S5 = L.br_states(O5, P5["high"], P5["low"], C5, V, L.lg_rs_rating(C5))
check("three down days put the leader at the oversold end", mp["LEAD"].iloc[-1] >= 85, mp["LEAD"].iloc[-1])
ind = pd.DataFrame(50.0, index=idx, columns=names)
ind["LEAD"] = 90.0
sig5 = L.br_signals(O5, P5["high"], P5["low"], C5, V, S5, mp, 15, side="bull", ind_rs=ind)
check("oversold leader in Stage 2, and in a leading group", bool(sig5["bl:lead_mrv"]["LEAD"].iloc[-1])
      and bool(sig5["bl:group_dip"]["LEAD"].iloc[-1]))
ind2 = ind.copy()
ind2["LEAD"] = 40.0
sig6 = L.br_signals(O5, P5["high"], P5["low"], C5, V, S5, mp, 15, side="bull", ind_rs=ind2)
check("the same dip in a lagging group isn't the leading-group setup", not sig6["bl:group_dip"]["LEAD"].iloc[-1]
      and bool(sig6["bl:lead_mrv"]["LEAD"].iloc[-1]))
check("no group map: no leading-group setup at all", "bl:group_dip" not in L.br_signals(O5, P5["high"], P5["low"], C5, V, S5, mp, 15, side="bull"))

print("the spreads on a path, by hand")
nP = 12
dts = pd.bdate_range("2026-03-02", periods=nP)
path = np.array([100, 100, 100, 101, 103, 108, 107, 105, 104, 103, 102, 101.0])
Cp = path[:, None]
e = np.array([1]); entry = np.array([100.0]); stop = np.array([95.0]); target = np.array([107.5])
hv = np.array([0.30])
sp = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([5]), hv, 5, iv_mult=1.0, skew=0.0,
                        side="bull")
check("strikes: long 100 call, short 107.5 call; short 95 put, long 87.5 put",
      (sp["K1"][0], sp["K2"][0], sp["K3"][0], sp["K4"][0]) == (100.0, 107.5, 95.0, 87.5), (sp["K1"], sp["K2"], sp["K3"], sp["K4"]))
T0 = ((dts[5] - dts[1]).days + 0.27) / 365
c1, c2 = (L.av_bs(100, k_, T0, 0.3, L.BR_RATE, True)[0] for k_ in (100, 107.5))
p3, p4 = (L.av_bs(100, k_, T0, 0.3, L.BR_RATE, False)[0] for k_ in (95, 87.5))


def hs(px, S):
    return (max(0.01, min(0.03 * px, 20 / 1e4 * S)) + L.BR_FEE) if px > 0.005 else 0.0


deb, cred = c1 - c2, p3 - p4
cin_d, cin_c = hs(c1, 100) + hs(c2, 100), hs(p3, 100) + hs(p4, 100)
pay = max(108 - 100, 0) - max(108 - 107.5, 0)
check("bull call debit held to expiry at 108: the full 7.5 width less the debit and costs, over the risk",
      abs(sp["db_hold"][0] - (pay - deb - cin_d - 2 * L.BR_FEE) / (deb + cin_d)) < 1e-6 and abs(sp["db_debit"][0] - deb) < 1e-9,
      (sp["db_hold"][0],))
check("bull put credit: both puts expire worthless, so it keeps the credit less the costs in",
      abs(sp["cr_hold"][0] - (cred - cin_c) / (7.5 - cred + cin_c)) < 1e-6, sp["cr_hold"])
sp2 = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([3]), hv, 5, iv_mult=1.0, skew=0.0, side="bull")
T3 = (dts[5] - dts[3]).days / 365
v3 = L.av_bs(101, 100, T3, 0.3, L.BR_RATE, True)[0] - L.av_bs(101, 107.5, T3, 0.3, L.BR_RATE, True)[0]
cout = hs(L.av_bs(101, 100, T3, 0.3, L.BR_RATE, True)[0], 101) + hs(L.av_bs(101, 107.5, T3, 0.3, L.BR_RATE, True)[0], 101)
check("follow: closed at the share trade's exit-day close, marked by Black-Scholes", abs(sp2["db_follow"][0] - (v3 - deb - cin_d - cout) / (deb + cin_d)) < 1e-6)
spe = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([5]), hv, 5, side="bull", credit_short="entry")
check("put credit under the entry: short 97.5, same 7.5 width", spe["K3"][0] == 97.5 and spe["K4"][0] == 90.0)
spk = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([5]), hv, 5, iv_mult=1.0, skew=0.5, side="bull")
check("the put skew makes the short call cheaper, so the call debit costs more", spk["db_debit"][0] > sp["db_debit"][0])
check("the strike helper agrees on both sides",
      L.br_strikes(100.0, 95.0, 107.5, "bull") == (100.0, 107.5, 95.0, 87.5)
      and L.br_strikes(100.0, 105.0, 92.5, "bear") == (100.0, 92.5, 105.0, 112.5))

print("a whole run, scoring and today's plan")
mk = L.lg_demo_market({t: L._demo_daily(t, 1600) for t in ("SPY", "NVDA", "AAPL", "TSLA")}, n_extra=60)
prm = {"side": "bull", "horizon": 5, "cooldown": 5, "min_price": 5.0, "min_dv": 1.0, "mode": "next_open", "win": 1, "tgt": 1.5,
       "cap": 3.0, "cost": 10.0, "iv_mult": 1.15, "skew": 0.5, "opt_cost": 0.03, "mrv_thr": 15.0, "base_step": 5}
cols = mk["P"]["close"].columns
grp = {t: ("G1" if k % 3 == 0 else "G2" if k % 3 == 1 else "G3") for k, t in enumerate(cols)}
ext = {"ind_rs": L.industry_rs_panels(mk["P"]["close"], grp)["ind_rs"]}
run = L.br_run(mk["P"], mk["P"]["close"]["SPY"], None, prm, "demo", extra=ext)
ev = run["ev"]
check("bull setups fire, the uptrend baseline too, most trades fill",
      {"bl:mrv_dip", "bl:dc20_up", "base:uptrend"} <= set(ev["setup"]) and not ev["setup"].str.startswith("br:").any()
      and (ev["status"] == 0).mean() > 0.9, ev["setup"].value_counts().to_dict())
done = ev[ev["status"] == 0]
check("long R: the stop is under the entry and the target over it", (done["stop"] < done["entry"]).all() and (done["target"] > done["entry"]).all())
check("R by hand on every trade: (exit - entry) / risk less costs",
      np.allclose(done["r"], (done["exit_px"] - done["entry"]) / done["risk"] - 0.002 * done["entry"] / done["risk"], atol=1e-4))
check("the edge column is the setup's return less the same-date uptrend average",
      np.allclose(done["xs"], done["fwd"] - run["base"].to_numpy()[done["i"].to_numpy()], equal_nan=True, atol=1e-6))
check("group RS rides along on every event", done["ind_rs"].notna().mean() > 0.9 and run["has_groups"])
sb, cut = L.br_score(ev, "group", 0.4, 5)
allr = sb[sb["split"] == "all"].set_index("setup_id")
check("the side is read from the events: the uptrend baseline is BASELINE", allr.loc["base:uptrend", "verdict"] == "BASELINE")
check("group thirds cover every trade of a setup",
      int(sb[(sb["setup_id"] == "bl:mrv_dip") & (sb["split"] != "all")]["events"].sum()) == int(allr.loc["bl:mrv_dip", "events"]))
check("spread stats per setup", np.isfinite(allr.loc["bl:mrv_dip", "db_follow"]) and 0 <= allr.loc["bl:mrv_dip", "win_cr_follow"] <= 1)
check("leaders-now table", {"lead", "stage2", "ind_rs", "off_hi252"} <= set(run["fl"].columns))
cl_ = mk["P"]["close"].astype(float)
check("leaders-now vs-40-day and each event extension are measured from the 40-day",
      np.allclose(run["fl"]["vs_bl_ma"], (cl_.iloc[-1] / cl_.iloc[-300:].rolling(40).mean().iloc[-1] - 1) * 100, equal_nan=True, atol=1e-6)
      and np.allclose(done["ext_ma"], (done["signal_close"] / cl_.rolling(40).mean().to_numpy()[done["i"].to_numpy(),
                      [list(cl_.columns).index(t) for t in done["ticker"]]] - 1) * 100, rtol=1e-4, atol=1e-3))
cand = L.br_candidates(run, sb, prm, look=40)
if len(cand):
    r0 = cand.iloc[0]
    Rr = r0["signal_close"] - r0["stop_plan"]
    check("today's plan: target = close + 1.5R, a call debit and a put credit",
          Rr > 0 and abs(r0["target_plan"] - (r0["signal_close"] + 1.5 * Rr)) < 1e-6 and r0["debit_legs"].endswith("C")
          and (r0["credit_legs"] == "" or r0["credit_legs"].endswith("P")), r0[["signal_close", "stop_plan", "debit_legs", "credit_legs"]].to_dict())
    atr_ = cand["atr_pct"] * cand["signal_close"] / 100
    risk_ = cand["signal_close"] - cand["stop_plan"]
    check("today's stop is capped at 3 ATR and floored at half an ATR, as in the history",
          ((risk_ <= 3 * atr_ + 1e-6) & (risk_ >= 0.5 * atr_ - 1e-6)).all())
else:
    check("today's plan (no recent signals in this demo run)", True)
grp2 = {t: g_ for k, (t, g_) in enumerate(grp.items()) if k % 4}
run_p = L.br_run(mk["P"], mk["P"]["close"]["SPY"], None, prm, "demo", extra={"ind_rs": L.industry_rs_panels(mk["P"]["close"], grp2)["ind_rs"]})
sbp, _ = L.br_score(run_p["ev"], "group", 0.4, 5)
labs_ = set(sbp["split"])
check("names without a group get their own 'no group' row, and the rows still add up",
      "no group" in labs_ and all(isinstance(x, str) for x in labs_)
      and int(sbp[(sbp["setup_id"] == "bl:mrv_dip") & (sbp["split"] != "all")]["events"].sum())
      == int(sbp[(sbp["setup_id"] == "bl:mrv_dip") & (sbp["split"] == "all")]["events"].iloc[0]), sorted(labs_))
run_m = L.br_run(mk["P"], mk["P"]["close"]["SPY"], None, prm, "demo market")
check("no group map: no leading-group setup", "bl:group_dip" not in set(run_m["ev"]["setup"]) and not run_m["has_groups"])

print("the live chain")
cfg = {"source": "demo", "key": None, "strip": True, "drop_partial": True, "fred_key": None}
lv = L.br_live_read(cfg, "NVDA", L._demo_daily("NVDA", 1600), L._demo_daily("SPY", 1600))
rd = lv["read"]
spot = rd["spot"]
d_, S_ = L.br_live_structures(rd, spot * 0.96, spot * 1.06, 5, side="bull")
check("both bull spreads at the expiry nearest a week", set(S_) == {"debit", "credit"} and 4 <= d_ <= 10, (d_, list(S_)))
dbl, crl = S_["debit"], S_["credit"]
check("call debit: long near spot, short over it near the target; put credit: short at or under the stop, long under it",
      dbl[0]["type"] == "call" and dbl[0]["qty"] == 1 and dbl[1]["strike"] > dbl[0]["strike"] and abs(dbl[0]["strike"] - spot) / spot < 0.05
      and crl[0]["type"] == "put" and crl[0]["qty"] == -1 and crl[0]["strike"] <= spot * 0.96 and crl[1]["strike"] < crl[0]["strike"],
      (dbl, crl))
e_ = L.av_eval_structure(rd, "Bull call debit spread", dbl)
check("the bull call debit is long delta with a defined max loss", e_["delta"] > 0 and e_["kind"] == "debit" and e_["max_loss"] > 0)
d2, S2_ = L.br_live_structures(rd, spot * 0.96, spot * 1.06, 5, cc_short="entry", side="bull")
check("put credit under the entry when asked", S2_["credit"][0]["strike"] < spot and S2_["credit"][0]["strike"] > spot * 0.96 - 1e-9
      or S2_["credit"][0]["strike"] < spot)

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
