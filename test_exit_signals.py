"""Planted-case tests for the exit signals (a close under the 10-day EMA, a distribution day, a climax) and the two
ways they replace a target: trim at the target with the signals on the rest, or no target at all. Checks the signal
panel by hand, the labeler's exit bar, price, outcome and R on planted paths, that the signals are off before the
trim, that an all-zero panel changes nothing, the Positions read, the plan text, and the playbook's exit lab (the
plans, the same-trade comparison by hand, the verdicts, the report).
Run: python test_exit_signals.py"""
import os
import shutil
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
TMP = tempfile.mkdtemp(prefix="xs_test_")
os.environ["PLAYBOOK_DATA"] = TMP
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


def panels(close, vol=None):
    """One name's bars from a close path: open = the prior close, a 0.5% wick each side."""
    c = pd.Series(np.asarray(close, float), index=pd.bdate_range("2024-01-02", periods=len(close)))
    o = c.shift(1).fillna(c.iloc[0])
    h, l = np.maximum(o, c) * 1.005, np.minimum(o, c) * 0.995
    P = {"open": o.to_frame("X"), "high": h.to_frame("X"), "low": l.to_frame("X"), "close": c.to_frame("X")}
    P["volume"] = pd.Series(np.full(len(c), 1e6) if vol is None else np.asarray(vol, float), index=c.index).to_frame("X")
    return P


def rules_for(trim_r, runner="signals", **sig):
    pl = {**PB.PB_PLAN_DEFAULT, "trim_r": trim_r, "runner": runner, "fail_n": 0, **sig}
    prm = {"mode": "next_open", "win": 1, "cap": 100.0, "trail_k": 3.0, "tgt": 2.0, "horizon": 20, "sim_plan": pl}
    return L.sim_trade_rules(prm, next(iter(L.LG_SETUPS)))


def label(P, ru, i_sig, stop, cost=0.0):
    A = L._mc_atr(P["high"], P["low"], P["close"], 14).to_numpy()
    O, H, Lo, C = (P[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    ma = L.sim_ma_panel(P["close"], ru)
    sig = L.sim_sig_panel(P["close"], ru, P["volume"])
    lab = L.lg_label(O, H, Lo, C, A, np.array([i_sig]), np.array([0]), np.array([stop]), "next_open", 1, ru["tgt"], 0,
                     100.0, 0.5, cost, trail=ru["trail"], trail_kind=ru["kind"], ma=ma, mark_open=True, exit_sig=sig,
                     **L.sim_label_kw(ru))
    return {k: (v[0] if isinstance(v, np.ndarray) else v) for k, v in lab.items()}


print("The signal panel by hand")
n = 120
c = 100 * 1.01 ** np.arange(n)
v = np.full(n, 1e6)
c[100:] = c[99] * 0.95 * 1.01 ** np.arange(n - 100)      # day 100: down 5%...
v[100] = 2.0e6                                            # ...on 2x the 50-day volume: a distribution day
c[105:] = c[104] * 0.96 * 1.01 ** np.arange(n - 105)     # day 105: down 4% on ordinary volume: not one
P = panels(c, v)
ru = rules_for(0.0, climax_ext=1000.0)
code = L.sim_sig_panel(P["close"], ru, P["volume"])[:, 0]
check("a 5% drop on 2x the 50-day volume is a distribution day (code 1)", code[100] == 1, code[98:107])
check("a 4% drop on ordinary volume is not", code[105] == 0)
check("no other day is flagged with the climax off", int((code > 0).sum()) == 1, np.flatnonzero(code))
code_nv = L.sim_sig_panel(P["close"], ru, None)[:, 0]
check("without volume there are no distribution days (simulated paths)", int((code_nv & 1).sum()) == 0)
ru_c = rules_for(0.0, climax_ext=25.0)
code_c = L.sim_sig_panel(P["close"], ru_c, P["volume"])[:, 0]
ext = (P["close"]["X"] / P["close"]["X"].rolling(50, min_periods=50).mean() - 1).to_numpy()
check("climax days are exactly the closes 25%+ over the 50-day SMA", np.array_equal((code_c & 2) > 0, ext >= 0.25),
      np.flatnonzero((code_c & 2) > 0)[:5])
check("a day that is both is code 3", (code_c[100] == 3) == (ext[100] >= 0.25))
check("other runners carry no signal panel", L.sim_sig_panel(P["close"], rules_for(2.0, "ema21"), P["volume"]) is None)

print("Signals only (no target): the distribution day ends the trade")
ema10 = P["close"]["X"].ewm(span=10, adjust=False, min_periods=10).mean().to_numpy()
i_sig = 70
check("precondition: no close under the 10-day EMA from entry to the day before", (c[71:100] >= ema10[71:100]).all())
lb = label(P, ru, i_sig, c[i_sig] * 0.9)
entry = c[i_sig]                                          # next open = the signal close
R0 = entry - c[i_sig] * 0.9
check("out at the distribution day's close (day 100)", lb["exit_i"] == 100 and abs(lb["exit"] - c[100]) < 1e-9,
      (lb["exit_i"], lb["exit"], c[100]))
check("outcome 'exit signal' (6), code 1 (distribution), credited over the EMA close the same day",
      lb["outcome"] == 6 and lb["sig_code"] == 1 and c[100] < ema10[100], (lb["outcome"], lb["sig_code"]))
check("R by hand: (close - entry) / risk", abs(lb["r"] - (c[100] - entry) / R0) < 1e-9, (lb["r"], (c[100] - entry) / R0))
check("nothing trimmed, no target", not lb["trimmed"] and not np.isfinite(lb["target"]))

print("Signals only: a close under the 10-day EMA")
c2 = c.copy()
v2 = v.copy()
v2[100] = 1.0e6                                           # the day-100 drop now on ordinary volume
c2[110:] = c2[109] * 0.90                                 # day 110: down 10% on ordinary volume, under the EMA
P2 = panels(c2, v2)
ema2 = P2["close"]["X"].ewm(span=10, adjust=False, min_periods=10).mean().to_numpy()
first_under = 71 + int(np.argmax(c2[71:] < ema2[71:]))
lb2 = label(P2, ru, i_sig, c2[i_sig] * 0.85)
check("out at the first close under the 10-day EMA", lb2["exit_i"] == first_under, (lb2["exit_i"], first_under))
check("outcome 'trailing exit' (3), no signal code", lb2["outcome"] == 3 and lb2["sig_code"] == 0)
ru2 = {**rules_for(0.0, climax_ext=1000.0), "ma_closes": 2}
lb2b = label(P2, ru2, i_sig, c2[i_sig] * 0.85)
two = next(t for t in range(72, n) if c2[t] < ema2[t] and c2[t - 1] < ema2[t - 1])
check("two closes in a row: out at the second", lb2b["exit_i"] == two, (lb2b["exit_i"], two))

print("Signals only: a climax")
c3 = np.r_[np.full(60, 100.0), 100 * 1.02 ** np.arange(1, 61)]
P3 = panels(c3)
ru3 = rules_for(0.0, climax_ext=20.0)
ext3 = (P3["close"]["X"] / P3["close"]["X"].rolling(50, min_periods=50).mean() - 1).to_numpy()
first_c = 63 + int(np.argmax(ext3[63:] >= 0.20))
lb3 = label(P3, ru3, 62, 95.0)
check("out at the first close 20%+ over the 50-day SMA", lb3["exit_i"] == first_c and lb3["sig_code"] == 2,
      (lb3["exit_i"], first_c, lb3["sig_code"]))
check("sold into strength: a winner", lb3["r"] > 0)

print("Trim at the target, then the signals on the rest")
ruA = rules_for(2.0, climax_ext=1000.0)
cA = 100 * 1.01 ** np.arange(n)
vA = np.full(n, 1e6)
cA[75:] = cA[74] * 0.965 * 1.01 ** np.arange(n - 75)     # day 75: a distribution day BEFORE the 2R trim
vA[75] = 3e6
cA[100:] = cA[99] * 0.95 * 1.01 ** np.arange(n - 100)   # day 100: another one, after the trim
vA[100] = 3e6
PA = panels(cA, vA)
eA = cA[70]
stopA = eA - 10.0                                         # 2R = +20, about 10%
lbA = label(PA, ruA, 70, stopA)
hiA = PA["high"]["X"].to_numpy()
t_trim = 71 + int(np.argmax(hiA[71:] >= eA + 20.0))
check("precondition: the first distribution day comes before the trim", 75 < t_trim, t_trim)
check("the pre-trim distribution day does not end the trade", lbA["exit_i"] != 75)
check("trimmed at 2R", lbA["trimmed"] and abs(lbA["trim_px"] - (eA + 20.0)) < 1e-9 and lbA["trim_i"] == t_trim,
      (lbA["trimmed"], lbA["trim_px"], lbA["trim_i"], t_trim))
check("the rest out on the post-trim distribution day (day 100)", lbA["exit_i"] == 100 and lbA["sig_code"] == 1,
      (lbA["exit_i"], lbA["sig_code"]))
f = 1 / 3
check("R blends the trim and the rest by hand", abs(lbA["r"] - (f * 20.0 + (1 - f) * (cA[100] - eA)) / 10.0) < 1e-9,
      (lbA["r"], (f * 20.0 + (1 - f) * (cA[100] - eA)) / 10.0))

print("Nothing changes without signals")
rng = np.random.default_rng(3)
cr = 50 * np.exp(np.cumsum(rng.normal(0.0008, 0.02, (400, 6)), axis=0))
Pr = {"close": pd.DataFrame(cr)}
Pr["open"] = Pr["close"].shift(1).fillna(Pr["close"].iloc[0])
Pr["high"] = np.maximum(Pr["open"], Pr["close"]) * 1.01
Pr["low"] = np.minimum(Pr["open"], Pr["close"]) * 0.99
Ar = L._mc_atr(Pr["high"], Pr["low"], Pr["close"], 14).to_numpy()
ii = rng.integers(60, 360, 80)
jj = rng.integers(0, 6, 80)
lv = cr[ii, jj] * 0.94
ruR = rules_for(2.0, "ema21")
maR = L.sim_ma_panel(Pr["close"], ruR)
args = [Pr[k].to_numpy(float) for k in ("open", "high", "low", "close")] + [Ar, ii, jj, lv, "next_open", 1, ruR["tgt"], 0,
                                                                               3.0, 0.5, 10.0]
kw = dict(trail=True, trail_kind="ma", ma=maR, mark_open=True, **L.sim_label_kw(ruR))
a0 = L.lg_label(*args, **kw)
a1 = L.lg_label(*args, exit_sig=np.zeros(cr.shape, np.int8), **kw)
same = all(np.array_equal(np.nan_to_num(a0[k], nan=-9), np.nan_to_num(a1[k], nan=-9)) for k in a0)
check("an all-zero signal panel gives identical trades (80 random events)", same)
check("no outcome 6 without signals", not (a0["outcome"] == 6).any())

print("Positions read the signals")
cP = 100 * 1.01 ** np.arange(80)
vP = np.full(80, 1e6)
cP[-1] = cP[-2] * 0.95
vP[-1] = 3e6
PP = panels(cP, vP)
pos = pd.DataFrame([{"ticker": "X", "shares": 100, "entry": cP[60], "stop": cP[60] * 0.95, "init_stop": cP[60] * 0.95,
                     "entry_date": PP["close"].index[61], "trimmed": False, "setup": ""}])
ps0 = L.pos_status(PP, pos, rules_for(0.0, climax_ext=1000.0)).iloc[0]
check("no target: a distribution day on the last bar says SELL (exit signal)", "sell_signal" in ps0["actions"], ps0["why"])
check("...and says why", "distribution day" in ps0["why"])
ps1 = L.pos_status(PP, pos.assign(trimmed=True), rules_for(2.0, climax_ext=1000.0)).iloc[0]
check("trimmed, trim + signals: SELL THE REST", "sell_rest" in ps1["actions"], ps1["actions"])
ps2 = L.pos_status(PP, pos, rules_for(8.0, climax_ext=1000.0)).iloc[0]
check("not yet trimmed, trim + signals: the signal isn't live yet", "sell_signal" not in ps2["actions"]
      and "sell_rest" not in ps2["actions"], ps2["actions"])
ps3 = L.pos_status(PP, pos.assign(trimmed=True), rules_for(2.0, "ema21")).iloc[0]
check("the 21-day EMA plan ignores the distribution day", "sell_rest" not in ps3["actions"], ps3["actions"])
check("no target: no trim level shown", np.isnan(ps0["trim_lvl"]))

print("The plan in words")
check("your default plan's tag is unchanged (setups frozen under it aren't flagged)",
      PB.pb_plan_tag(PB.PB_PLAN_DEFAULT) == "trim 1/3 at 2R, stop to breakeven, the rest out on the 21-day EMA, cut by session 5 if under breakeven",
      PB.pb_plan_tag(PB.PB_PLAN_DEFAULT))
tA = PB.pb_plan_tag({**PB.PB_PLAN_DEFAULT, "runner": "signals"})
tB = PB.pb_plan_tag({**PB.PB_PLAN_DEFAULT, "runner": "signals", "trim_r": 0.0})
check("trim + signals names the target and all three signals", "at 2R" in tA and "distribution day (down 3%+ on 1.5x+" in tA
      and "climax (20%+" in tA and "10-day EMA" in tA, tA)
check("signals only says no target", tB.startswith("no target: the whole trade out on the first exit signal"), tB)
st_txt = L.sim_plan_txt(rules_for(0.0))
check("the Simulation's sentence for no target", st_txt.startswith("no target: the whole trade exits on the first exit signal"), st_txt)

print("The exit lab")
plans = PB.pb_exit_plans(PB.PB_PLAN_DEFAULT)
check("three plans: yours, trim + signals at your 2R, signals only",
      plans["yours"]["runner"] == "ema21" and plans["trim_sig"]["runner"] == "signals" and plans["trim_sig"]["trim_r"] == 2.0
      and plans["sig_only"]["trim_r"] == 0.0 and plans["sig_only"]["fail_n"] == 5)
p0 = PB.pb_exit_plans({**PB.PB_PLAN_DEFAULT, "trim_r": 0.0, "runner": "signals"})
check("a plan already at no target: trim + signals falls back to a 2R trim", p0["trim_sig"]["trim_r"] == 2.0 and p0["sig_only"] == p0["yours"])
dates = pd.bdate_range("2023-01-02", periods=300)
k = 1800
base = pd.DataFrame({"setup": np.where(np.arange(k) < 1500, "gap:hi_any", np.where(np.arange(k) < 1520, "gap:in_any", "base:up")),
                     "date": dates[rng.integers(0, 300, k)], "status": 0, "outcome": 1, "r": rng.normal(0.1, 1.5, k),
                     "hold": 10, "trimmed": False, "exit_sig": 0})
base.loc[5, "outcome"] = 4                                # still open under your plan: out of all three
better = base.assign(r=base["r"] + 0.5 + rng.normal(0, 0.2, k), outcome=6, exit_sig=1)
worse = base.assign(r=base["r"] - 0.5 + rng.normal(0, 0.2, k))
T = PB.pb_exit_table({"yours": base, "trim_sig": better, "sig_only": worse}, 10, active=["gap:hi_any"])
a_ = T[(T["scope"] == "all")].set_index("variant")
keep = (base["outcome"] != 4) & ~base["setup"].str.startswith("base:")
check("same trades: the open one and the baselines are out", int(a_.at["yours", "n"]) == int(keep.sum()), (a_.at["yours", "n"], keep.sum()))
check("the difference by hand", abs(a_.at["trim_sig", "d_er"] - (better["r"] - base["r"])[keep].mean()) < 1e-12)
check("a planted +0.5R is BETTER", a_.at["trim_sig", "verdict"] == "BETTER" and a_.at["trim_sig", "d_t"] > 5, a_.at["trim_sig", "d_t"])
check("a planted -0.5R is WORSE", a_.at["sig_only", "verdict"] == "WORSE")
check("exit reasons: all distribution days under the planted plan", abs(a_.at["trim_sig", "p_dist"] - 1.0) < 1e-12)
s20 = T[(T["scope"] == "setup:gap:in_any") & (T["variant"] == "trim_sig")].iloc[0]
check("a setup with 20 trades is TOO FEW", s20["verdict"] == "TOO FEW", s20["verdict"])
check("per-setup comparisons carry a q", T[T["scope"].str.startswith("setup:") & (T["variant"] != "yours")]["d_q"].notna().all())
check("your active setups pooled", (T["scope"] == "active").any() and int(T[T["scope"] == "active"]["n"].iloc[0]) == int(
    (keep & (base["setup"] == "gap:hi_any")).sum()))
W = PB.pb_exit_wide(T)
check("the wide table names the best supported plan", W.set_index("scope").at["setup:gap:hi_any", "best"] == "trim_sig")

print("The exit lab on a real demo ledger, and the report")
out = PB.nightly("demo", limit=30, log=lambda *a: None)
S = out["state"]
XT = S.get("exit_lab")
check("the nightly runs the exit lab", XT is not None and len(XT) > 3)
rep = open(PB.f_report()).read()
check("the report has the exit lab", "## Exit lab" in rep and "signals only" in rep, rep[-400:])
cfg = PB.pb_cfg("demo")
cfg["uni"] = cfg["uni"].head(30)
_, Pd = PB.pb_bars(cfg)
led = PB.pb_read_ledgers()
tag = f"{led['setup']['mtime']}"
rc = PB.pb_exit_runs(led["setup"]["ev"], Pd, S["prm"], PB.pb_load()["plan"], tag=tag, only_cached=True)
check("after the nightly every plan is cached (the page opens without a re-run)", rc is not None)
if rc is not None:
    y, b = rc["yours"], rc["sig_only"]
    d = (y["status"] == 0) & (b["status"] == 0)
    check("same entries and initial stops under every plan", np.allclose(y.loc[d, "entry"], b.loc[d, "entry"])
          and np.allclose(y.loc[d, "stop"], b.loc[d, "stop"]))
    check("signal codes only on signal exits", ((b["exit_sig"] > 0) <= (b["outcome"] == 6)).all()
          and ((b["outcome"] == 6) <= (b["exit_sig"] > 0)).all())
    check("signals only never trims", not b.loc[d, "trimmed"].any())
    check("on real bars the signals fire", int((b["outcome"] == 6).sum()) > 0)

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
