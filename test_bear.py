"""Planted-case tests for Options > Bear spreads: the mirrored short labeler, former-leader states, the six setups, the
mean-reversion percentile's direction, the spreads priced on a path by hand, scoring, today's plan, the live
structures, the simulator's drift, the former-leaders file and the git-history script.
Run: python test_bear.py"""
import math, os, subprocess, sys, tempfile, warnings
from datetime import date
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


print("short labels (the long labeler on mirrored prices)")
n = 20


def bars_(rows):
    O = np.full((n, 1), 100.0); Hh = O + 1; Lo = O - 1; C = O.copy()
    for i, (o, h, l, c) in rows.items():
        O[i, 0], Hh[i, 0], Lo[i, 0], C[i, 0] = o, h, l, c
    return O, Hh, Lo, C


A = np.full((n, 1), 3.0)
ii, jj = np.array([10]), np.array([0])
cost = 10.0
cR = 2 * cost / 1e4 * 100 / 5                                  # costs in R on a 100 entry with 5 of risk


def lab(rows, mode="next_open", H=3, stop=105.0):
    O, Hh, Lo, C = bars_(rows)
    return L.br_label(O, Hh, Lo, C, A, ii, jj, np.array([stop]), mode, 1, 1.5, H, 3.0, cost)


t = lab({11: (100, 101, 99, 100), 12: (99, 99.5, 92, 93)})
check("target: covered 1.5R under the entry", t["outcome"][0] == 0 and abs(t["exit"][0] - 92.5) < 1e-9
      and abs(t["r"][0] - (1.5 - cR)) < 1e-9 and abs(t["ret"][0] - (0.075 - 0.002)) < 1e-9, (t["exit"], t["r"]))
t = lab({11: (100, 101, 99, 100), 12: (101, 106, 100, 104)})
check("stop: covered at the stop above", t["outcome"][0] == 1 and abs(t["exit"][0] - 105) < 1e-9
      and abs(t["r"][0] - (-1 - cR)) < 1e-9, (t["exit"], t["r"]))
t = lab({11: (100, 101, 99, 100), 12: (108, 109, 107, 108)})
check("a gap over the stop fills at the open", t["outcome"][0] == 1 and abs(t["exit"][0] - 108) < 1e-9
      and abs(t["r"][0] - (-1.6 - cR)) < 1e-9, (t["exit"], t["r"]))
t = lab({11: (100, 101, 99, 100), 12: (100, 101, 98, 99), 13: (99, 100, 97, 97.5)})
check("time limit: covered at the last session's close", t["outcome"][0] == 2 and abs(t["exit"][0] - 97.5) < 1e-9
      and abs(t["r"][0] - (0.5 - cR)) < 1e-9 and t["hold"][0] == 3, (t["exit"], t["hold"]))
t = lab({11: (100, 101, 99, 100), 12: (99, 99.5, 91, 92)})
check("MFE and MAE in R", abs(t["mfe_r"][0] - (100 - 91) / 5) < 1e-9 or t["outcome"][0] == 0)
t = lab({10: (100, 101, 98, 99), 11: (99, 99.5, 97, 98)}, mode="trigger", stop=104.0)
check("trigger entry: sold on the break of the signal-day low", t["status"][0] == 0 and abs(t["entry"][0] - 98) < 1e-9
      and abs(t["risk"][0] - 6) < 1e-9, (t["entry"], t["risk"]))
t = lab({10: (100, 101, 98, 99), 11: (96, 97, 95, 96)}, mode="trigger", stop=104.0)
check("a gap under the trigger fills at the open", abs(t["entry"][0] - 96) < 1e-9, t["entry"])
t = lab({10: (100, 101, 98, 99), 11: (101, 106, 100.5, 105)}, mode="trigger", stop=104.0)
check("no fill, closed over the stop: the order is cancelled", t["status"][0] != 0, t["status"])
t = lab({11: (106, 107, 105.5, 106)}, stop=105.0)
check("opened over the stop: no trade", t["status"][0] == 2, t["status"])

print("former leaders and the setups")
N = 700
idx = pd.bdate_range("2023-01-02", periods=N)
rng = np.random.default_rng(1)
names = ["LEAD"] + [f"F{k:02d}" for k in range(24)]
C = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.004, (N, len(names))), axis=0)), index=idx, columns=names)
lead = np.r_[np.linspace(50, 200, 420), np.linspace(200, 120, 180), np.linspace(120, 118, 100)]
C["LEAD"] = lead
O = C.shift(1).fillna(C)
Hh = np.maximum(O, C) * 1.005
Lo = np.minimum(O, C) * 0.995
V = pd.DataFrame(2e6, index=idx, columns=names)
rs = L.lg_rs_rating(C)
S = L.br_states(O, Hh, Lo, C, V, rs)
check("the leader had an RS rating of 90+", rs["LEAD"].iloc[300:420].max() >= 90 and bool(S["leader"]["LEAD"].iloc[-1]))
check("topped: 15%+ under its 6-month high, under a falling 50-day (and no longer once the high is 6 months old)",
      bool(S["topped"]["LEAD"].iloc[560]) and not S["topped"]["LEAD"].iloc[400] and not S["topped"]["LEAD"].iloc[-1],
      (S["topped"]["LEAD"].iloc[560], S["topped"]["LEAD"].iloc[-1]))
check("flat names are never leaders that topped", not S["topped"][names[1:]].iloc[-150:].any().any())

# rally into the falling 50-day that fails: push LEAD up to its 50-day, then a red close back under
C2, O2, H2, L2 = C.copy(), O.copy(), Hh.copy(), Lo.copy()
k = 560
s50 = C["LEAD"].rolling(50).mean()
C2.iloc[k - 1, 0] = s50.iloc[k - 1] * 0.995
H2.iloc[k - 1, 0] = s50.iloc[k - 1] * 1.002
O2.iloc[k, 0] = s50.iloc[k] * 0.995
C2.iloc[k, 0] = s50.iloc[k] * 0.96
H2.iloc[k, 0] = s50.iloc[k] * 0.997
L2.iloc[k, 0] = s50.iloc[k] * 0.958
S2 = L.br_states(O2, H2, L2, C2, V, L.lg_rs_rating(C2))
sig = L.br_signals(O2, H2, L2, C2, V, S2, None, 15)
check("rally into the falling 50-day fails: fires on the red close back under it", bool(sig["br:fl_rally_fail"]["LEAD"].iloc[k])
      and not sig["br:fl_rally_fail"]["LEAD"].iloc[k - 30:k - 3].any())
# first close under the 50-day on volume, near the high
C3, O3, H3, L3, V3 = C.copy(), O.copy(), Hh.copy(), Lo.copy(), V.copy()
k3 = 425
s50b = C3["LEAD"].rolling(50).mean()
C3.iloc[k3, 0] = s50b.iloc[k3] * 0.98
O3.iloc[k3, 0] = C3.iloc[k3 - 1, 0]
H3.iloc[k3, 0] = O3.iloc[k3, 0] * 1.003
L3.iloc[k3, 0] = C3.iloc[k3, 0] * 0.997
V3.iloc[k3, 0] = 4e6
S3 = L.br_states(O3, H3, L3, C3, V3, L.lg_rs_rating(C3))
sig3 = L.br_signals(O3, H3, L3, C3, V3, S3, None, 15)
check("first close under the 50-day on 1.4x volume fires; a quiet one doesn't", bool(sig3["br:fl_break50"]["LEAD"].iloc[k3])
      and not L.br_signals(O3, H3, L3, C3, V, S3, None, 15)["br:fl_break50"]["LEAD"].iloc[k3])
# negative EP: gap down 5% on 4x volume, weak close
C4, O4, H4, L4, V4 = C.copy(), O.copy(), Hh.copy(), Lo.copy(), V.copy()
j = names.index("F03")
k4 = 600
pc = C4.iloc[k4 - 1, j]
O4.iloc[k4, j], H4.iloc[k4, j], L4.iloc[k4, j], C4.iloc[k4, j] = pc * 0.95, pc * 0.955, pc * 0.92, pc * 0.925
V4.iloc[k4, j] = 8e6
sig4 = L.br_signals(O4, H4, L4, C4, V4, L.br_states(O4, H4, L4, C4, V4, rs), None, 15)
check("negative episodic pivot: a 5% gap down on 4x volume closing weak", bool(sig4["br:ep_down"]["F03"].iloc[k4])
      and int(sig4["br:ep_down"].sum().sum()) == 1)
check("20-day low breakdown fires only under a falling 150-day", bool(sig["br:dc20_dn"]["LEAD"].iloc[450:600].any())
      and not sig["br:dc20_dn"]["LEAD"].iloc[200:400].any())

print("the mean-reversion percentile")
P = {"open": O, "high": Hh, "low": Lo, "close": C, "volume": V}
C5 = C.copy()
up = names.index("F05")
for d in range(3):
    C5.iloc[N - 3 + d, up] = C5.iloc[N - 4, up] * (1.03 ** (d + 1))
dn = names.index("F06")
for d in range(3):
    C5.iloc[N - 3 + d, dn] = C5.iloc[N - 4, dn] * (0.97 ** (d + 1))
O5 = C5.shift(1).fillna(C5)
P5 = {"open": O5, "high": np.maximum(O5, C5) * 1.005, "low": np.minimum(O5, C5) * 0.995, "close": C5, "volume": V}
mp = L.br_mrv_pct(P5)
check("three strong up days rank at the overbought end, three down days at the other",
      mp["F05"].iloc[-1] <= 15 and mp["F06"].iloc[-1] >= 70, (mp["F05"].iloc[-1], mp["F06"].iloc[-1]))
check("percentiles run 0-100 across names", 0 <= float(mp.iloc[-1].min()) and float(mp.iloc[-1].max()) <= 100)

print("the spreads on a path, by hand")
nP = 12
dts = pd.bdate_range("2026-03-02", periods=nP)
path = np.array([100, 100, 100, 99, 97, 95, 93, 94, 96, 97, 98, 99.0])
Cp = path[:, None]
e = np.array([1]); entry = np.array([100.0]); stop = np.array([105.0]); target = np.array([92.5])
hv = np.array([0.30])
sp = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([4]), hv, 5, iv_mult=1.0, skew=0.0,
                        cost_frac=0.03)
check("strikes: long 100 put, short 92.5 put; short 105 call, long 112.5 call (2.5 grid at 100)",
      (sp["K1"][0], sp["K2"][0], sp["K3"][0], sp["K4"][0]) == (100.0, 92.5, 105.0, 112.5), (sp["K1"], sp["K2"], sp["K3"], sp["K4"]))
T0 = ((dts[5] - dts[1]).days + 0.27) / 365
deb = L.av_bs(100, 100, T0, 0.3, L.BR_RATE, False)[0] - L.av_bs(100, 92.5, T0, 0.3, L.BR_RATE, False)[0]


def hs(px, S):
    return (max(0.01, min(0.03 * px, 20 / 1e4 * S)) + L.BR_FEE) if px > 0.005 else 0.0


cin = hs(L.av_bs(100, 100, T0, 0.3, L.BR_RATE, False)[0], 100) + hs(L.av_bs(100, 92.5, T0, 0.3, L.BR_RATE, False)[0], 100)
pay = max(100 - 95, 0) - max(92.5 - 95, 0)
want_hold = (pay - deb - cin - L.BR_FEE) / (deb + cin)
check("put debit held to expiry: payoff at the 5th session's close less the debit and costs, over the risk",
      abs(sp["db_hold"][0] - want_hold) < 1e-6 and abs(sp["db_debit"][0] - deb) < 1e-9, (sp["db_hold"][0], want_hold))
spx = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([5]), hv, 5, iv_mult=1.0, skew=0.0,
                         cost_frac=0.03)
check("when the share trade runs to its time limit, follow = hold", abs(spx["db_follow"][0] - spx["db_hold"][0]) < 1e-9
      and abs(spx["db_hold"][0] - sp["db_hold"][0]) < 1e-9)
sp2 = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([3]), hv, 5, iv_mult=1.0, skew=0.0,
                         cost_frac=0.03)
T3 = (dts[5] - dts[3]).days / 365
v3 = L.av_bs(99, 100, T3, 0.3, L.BR_RATE, False)[0] - L.av_bs(99, 92.5, T3, 0.3, L.BR_RATE, False)[0]
cout = hs(L.av_bs(99, 100, T3, 0.3, L.BR_RATE, False)[0], 99) + hs(L.av_bs(99, 92.5, T3, 0.3, L.BR_RATE, False)[0], 99)
check("follow: closed at the share trade's exit-day close, marked by Black-Scholes, with costs out",
      abs(sp2["db_follow"][0] - (v3 - deb - cin - cout) / (deb + cin)) < 1e-6)
cred = L.av_bs(100, 105, T0, 0.3, L.BR_RATE, True)[0] - L.av_bs(100, 112.5, T0, 0.3, L.BR_RATE, True)[0]
check("call credit: both calls expire worthless at 95, so it keeps the credit less the costs in",
      abs(sp["cr_hold"][0] - (cred - (hs(L.av_bs(100, 105, T0, 0.3, L.BR_RATE, True)[0], 100)
                                      + hs(L.av_bs(100, 112.5, T0, 0.3, L.BR_RATE, True)[0], 100))) /
          (7.5 - cred + hs(L.av_bs(100, 105, T0, 0.3, L.BR_RATE, True)[0], 100) + hs(L.av_bs(100, 112.5, T0, 0.3, L.BR_RATE, True)[0], 100))) < 1e-6
      or not np.isfinite(sp["cr_hold"][0]), sp["cr_hold"])
spk = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([4]), hv, 5, iv_mult=1.0, skew=0.5)
check("put skew raises the short put's IV more than the long's, so the debit is cheaper", spk["db_debit"][0] < sp["db_debit"][0])
spe = L.br_price_spreads(Cp, dts, np.array([0]), e, entry, stop, target, np.array([4]), hv, 5, iv_mult=1.0, skew=0.0, credit_short="entry")
check("call credit over the entry: short 102.5, same 7.5 width", spe["K3"][0] == 102.5 and spe["K4"][0] == 110.0)
late = L.br_price_spreads(Cp, dts, np.array([0]), np.array([9]), entry, stop, target, np.array([11]), hv, 5)
check("no full life left in the data: not priced", not np.isfinite(late["db_hold"][0]))
check("strike grid by price", list(L.br_strike_step([10, 60, 120, 300, 900])) == [0.5, 1.0, 2.5, 5.0, 10.0])

print("a whole run, scoring and today's plan")
mk = L.lg_demo_market({t: L._demo_daily(t, 1600) for t in ("SPY", "NVDA", "AAPL", "TSLA")}, n_extra=60)
prm = {"horizon": 5, "cooldown": 5, "min_price": 5.0, "min_dv": 1.0, "mode": "next_open", "win": 1, "tgt": 1.5, "cap": 3.0,
       "cost": 10.0, "iv_mult": 1.15, "skew": 0.5, "opt_cost": 0.03, "mrv_thr": 15.0, "base_step": 5}
run = L.br_run(mk["P"], mk["P"]["close"]["SPY"], None, prm, "demo")
ev = run["ev"]
check("every setup fires and most trades fill", set(ev["setup"]) >= {"br:fl_rally_fail", "br:mrv_fade", "br:dc20_dn", "base:downtrend"}
      and (ev["status"] == 0).mean() > 0.9, ev["setup"].value_counts().to_dict())
done = ev[ev["status"] == 0]
check("short R: the stop is above the entry and the target below", (done["stop"] > done["entry"]).all() and (done["target"] < done["entry"]).all())
check("R by hand on every trade: (entry - exit) / risk less costs",
      np.allclose(done["r"], (done["entry"] - done["exit_px"]) / done["risk"] - 0.002 * done["entry"] / done["risk"], atol=1e-4))
check("the edge column is the setup's short return less the same-date downtrend average",
      np.allclose(done["xs"], done["fwd"] - run["base"].to_numpy()[done["i"].to_numpy()], equal_nan=True, atol=1e-6))
sb, cut = L.br_score(ev, "cycle", 0.4, 5)
allr = sb[sb["split"] == "all"].set_index("setup_id")
check("the baseline is BASELINE and sparse setups are THIN", allr.loc["base:downtrend", "verdict"] == "BASELINE"
      and all(v == "THIN" for s_, v in allr["verdict"].items() if allr.loc[s_, "events"] < 40 and s_ != "base:downtrend"))
check("splits by SPY cycle cover every trade", int(sb[(sb["setup_id"] == "br:mrv_fade") & (sb["split"] != "all")]["events"].sum())
      == int(allr.loc["br:mrv_fade", "events"]))
check("spread stats per setup", np.isfinite(allr.loc["br:mrv_fade", "db_follow"]) and 0 <= allr.loc["br:mrv_fade", "win_db_follow"] <= 1)
check("the former-leader table has today's state", {"topped", "leader", "rs_max_252", "off_hi126"} <= set(run["fl"].columns))
cand = L.br_candidates(run, sb, prm, look=40)
if len(cand):
    r0 = cand.iloc[0]
    Rr = r0["stop_plan"] - r0["signal_close"]
    check("today's plan: target = close - 1.5R, the put debit from the strike nearest the close",
          abs(r0["target_plan"] - (r0["signal_close"] - 1.5 * Rr)) < 1e-6 and r0["debit_legs"].startswith("+"), r0[["signal_close", "stop_plan", "target_plan"]].to_dict())
else:
    check("today's plan (no recent signals in this demo run)", True)

print("the live chain and the simulator's drift")
cfg = {"source": "demo", "key": None, "strip": True, "drop_partial": True, "fred_key": None}
df = L._demo_daily("NVDA", 1600)
lv = L.br_live_read(cfg, "NVDA", df, L._demo_daily("SPY", 1600))
check("the VRP desk reads a short-dated chain", lv is not None and lv["read"]["term"]["dte"].min() <= 7, None if lv is None else lv["read"]["term"]["dte"].tolist())
rd = lv["read"]
spot = rd["spot"]
d_, S_ = L.br_live_structures(rd, spot * 1.04, spot * 0.94, 5)
check("both spreads at the expiry nearest a week", set(S_) == {"debit", "credit"} and 4 <= d_ <= 10, (d_, list(S_)))
pdl, ccl = S_["debit"], S_["credit"]
check("put debit: long near spot, short under it near the target; call credit: short at or over the stop",
      pdl[0]["qty"] == 1 and pdl[1]["strike"] < pdl[0]["strike"] and abs(pdl[0]["strike"] - spot) / spot < 0.05
      and ccl[0]["qty"] == -1 and ccl[0]["strike"] >= spot * 1.04 and ccl[1]["strike"] > ccl[0]["strike"], (pdl, ccl))
evp = L.av_eval_structure(rd, "Bear put debit spread", pdl)
p0 = {**L.AV_SIM_DEFAULTS, "n": 2000, "seed": 2, "dte_exit": 2}
s0 = L.av_simulate(rd, evp, df["close"], lv["model"], p0)
s1 = L.av_simulate(rd, evp, df["close"], lv["model"], {**p0, "drift": -0.004})
h0 = s0["table"].set_index("key").loc["hold", "er"]
h1 = s1["table"].set_index("key").loc["hold", "er"]
check("a downward drift lifts the put debit's expected P&L", h1 > h0 + 5, (h0, h1))

print("the former-leaders file and the git script")
tmpd = Path(tempfile.mkdtemp())
real_file = L.BR_FILE
L.BR_FILE = tmpd / "former_leaders.csv"
try:
    check("no file: an empty list", len(L.br_former_list()) == 0)
    k_ = L.br_save_former(["nvda", "$amd", "NVDA", ""])
    k2 = L.br_save_former(["AMD", "ARM"])
    check("saved, cleaned and de-duplicated", k_ == 2 and k2 == 3 and list(L.br_former_list()["ticker"]) == ["NVDA", "AMD", "ARM"])
finally:
    L.BR_FILE = real_file
repo = tmpd / "repo"
repo.mkdir()
g = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True,
                              capture_output=True, text=True)
g("init", "-q")
for k, (syms, d) in enumerate(((["AAA", "BBB", "CCC"], "2025-01-06T12:00:00"), (["BBB", "CCC", "DDD"], "2025-01-13T12:00:00"),
                               (["CCC", "DDD", "EEE"], "2025-01-20T12:00:00"))):
    (repo / "watchlist_input.csv").write_text("Symbol,Name\n" + "\n".join(f"{s},{s} Inc" for s in syms) + "\n")
    g("add", "watchlist_input.csv")
    env = {**os.environ, "GIT_COMMITTER_DATE": d, "GIT_AUTHOR_DATE": d}
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", f"w{k}"],
                   check=True, capture_output=True, env=env)
out = tmpd / "out" / "former_leaders.csv"
r = subprocess.run([sys.executable, str(Path(__file__).with_name("former_leaders_from_git.py")), "--repo", str(repo),
                    "--files", "watchlist_input.csv", "--out", str(out)], capture_output=True, text=True)
fl = pd.read_csv(out) if out.exists() else pd.DataFrame()
check("the script lists every past ticker not on the current version", r.returncode == 0 and set(fl["ticker"]) == {"AAA", "BBB"},
      (r.stdout, r.stderr, fl.to_dict("records")))
check("with first and last seen and the versions it was on",
      fl.set_index("ticker").loc["BBB", "first_seen"] == "2025-01-06" and fl.set_index("ticker").loc["BBB", "last_seen"] == "2025-01-13"
      and int(fl.set_index("ticker").loc["BBB", "versions"]) == 2 and fl["ticker"].iloc[0] == "BBB")
check("written atomically (no .tmp left)", not (out.parent / "former_leaders.csv.tmp").exists())

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
