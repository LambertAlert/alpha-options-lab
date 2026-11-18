"""Planted-case tests for the Simulation tab's core in alpha_options_lab.py: the Gibbs sampler recovers known
parameters, tempering widens the posterior by sqrt(k), simulated paths reproduce the ledger's own trade exactly,
the look-alike check finds a planted signal and not a fake one, and the Bayesian Kelly pays for uncertainty.
Run: python test_simulation.py"""
import math, sys, time, warnings
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


rng = np.random.default_rng(21)

print("Gibbs sampler")
# planted hierarchical data: 3 families, 9 setups, 2 indicators
S, F, p = 9, 3, 2
f_of_s = np.repeat(np.arange(F), 3)
mu_true = np.array([0.10, -0.05, 0.25])
a_true = mu_true[f_of_s] + rng.normal(0, 0.08, S)
beta_true = np.array([0.15, -0.10])
n_s = np.array([400, 400, 400, 300, 300, 300, 500, 500, 15])          # setup 8 is thin
s_idx = np.repeat(np.arange(S), n_s)
n = len(s_idx)
X = rng.standard_normal((n, p))
y = a_true[s_idx] + X @ beta_true + 0.9 * rng.standard_normal(n)
t0 = time.time()
D = L.sim_gibbs(y, X, s_idx, f_of_s, 1.0, chains=4, iters=1200, warm=400, seed=1)
secs = time.time() - t0
B = D["beta"].reshape(-1, p)
A = D["a"].reshape(-1, S)
bm, bs = B.mean(0), B.std(0)
check("beta recovered (within 3 posterior s.d.)", np.all(np.abs(bm - beta_true) < 3 * bs), (bm, bs))
check("beta s.d. near the OLS one (0.9/sqrt(n))", np.all(np.abs(bs / (0.9 / math.sqrt(n)) - 1) < 0.25), bs)
am = A.mean(0)
check("setup effects recovered (thick setups)", np.all(np.abs(am[:8] - a_true[:8]) < 3 * A.std(0)[:8]), np.round(am - a_true, 3))
raw8 = y[s_idx == 8].mean() - (X[s_idx == 8] @ beta_true).mean()
fam8 = A[:, 6:8].mean()
check("thin setup shrinks toward its family", abs(am[8] - fam8) < abs(raw8 - fam8), (raw8, am[8], fam8))
rh = [L.sim_rhat(D["beta"][:, :, j]) for j in range(p)] + [L.sim_rhat(D["a"][:, :, j]) for j in range(S)]
check("R-hat < 1.05 on every coefficient", max(rh) < 1.05, max(rh))
ess = [L.sim_ess(D["beta"][:, :, j]) for j in range(p)]
check("ESS of beta > 400", min(ess) > 400, ess)
check("normal noise: nu posterior mostly >= 10", np.median(D["nu"]) >= 10, np.median(D["nu"]))
check("sigma recovered", abs(np.median(D["sigma"]) - 0.9) < 0.05, np.median(D["sigma"]))
print(f"       ({n} rows, 4 x 1200 iterations in {secs:.1f}s)")
# tempering: k = 4 doubles the posterior s.d. of beta
D4 = L.sim_gibbs(y, X, s_idx, f_of_s, 4.0, chains=2, iters=900, warm=300, seed=2)
r_sd = D4["beta"].reshape(-1, p).std(0) / bs
check("tempering k=4 doubles the s.d.", np.all(np.abs(r_sd - 2) < 0.35), r_sd)
check("tempering keeps sigma's level", abs(np.median(D4["sigma"]) - 0.9) < 0.08, np.median(D4["sigma"]))
# fat tails: t(3) noise -> low nu, and the t fit resists outliers
yt = a_true[s_idx] + X @ beta_true + 0.5 * rng.standard_t(3, n)
Dt = L.sim_gibbs(yt, X, s_idx, f_of_s, 1.0, chains=2, iters=900, warm=300, seed=3)
check("t(3) noise: nu posterior <= 5", np.median(Dt["nu"]) <= 5, np.median(Dt["nu"]))
check("t(3) noise: beta still recovered", np.all(np.abs(Dt["beta"].reshape(-1, p).mean(0) - beta_true) < 0.04))
# no indicators at all
D0 = L.sim_gibbs(y, np.zeros((n, 0)), s_idx, f_of_s, 1.0, chains=2, iters=300, warm=100, seed=4)
check("runs with no indicators", D0["beta"].shape[2] == 0 and np.isfinite(D0["a"]).all())

print("sim_fit on a planted ledger")
fam_ids = {}
for s_, v_ in L.LG_SETUPS.items():
    if s_ not in L.RK_SKIP and v_[0] in ("MACD", "Trend") and len(fam_ids.setdefault(v_[0], [])) < 3:
        fam_ids[v_[0]].append(s_)
sids = fam_ids["MACD"] + fam_ids["Trend"]
eff_true = dict(zip(sids, [0.30, 0.20, 0.25, -0.10, 0.00, -0.05]))
dts = pd.bdate_range("2020-01-01", periods=900)
rows = []
for s_ in sids:
    di = np.sort(rng.choice(900, 500, replace=False))
    for d_ in di:
        for _ in range(int(rng.integers(1, 4))):
            rows.append((s_, dts[d_], rng.standard_normal(), rng.standard_normal()))
evp = pd.DataFrame(rows, columns=["setup", "date", "rs_rating", "adr20"])
evp["status"], evp["hold"], evp["outcome"] = 0, 5, 0
evp["r"] = evp["setup"].map(eff_true) + 0.30 * evp["rs_rating"] + 1.2 * rng.standard_normal(len(evp))
evp["family"] = evp["setup"].map(lambda s_: L.LG_SETUPS[s_][0])
cutp = L._sim_cutoff(evp, 0.4)
fp = L.sim_fit(evp, ["rs_rating", "adr20"], cutp, 5, "disc", chains=3, iters=900, warm=300)
cf = fp["coef"].set_index("feature")
sd_d = fp["sc"]["sd"][0]                                    # beta is per 1 s.d. of the date-mean indicator
check("planted indicator found (P > 0.99)", cf.loc["rs_rating", "p_pos"] > 0.99, cf.loc["rs_rating"].to_dict())
check("its size recovered (0.30 R per unit)", abs(cf.loc["rs_rating", "med"] / sd_d - 0.30) < 0.08, cf.loc["rs_rating", "med"] / sd_d)
check("fake indicator's interval covers 0", cf.loc["adr20", "lo"] < 0 < cf.loc["adr20", "hi"], cf.loc["adr20"].to_dict())
ef_ = fp["eff"].set_index("setup_id")
check("setup levels recovered", all(abs(ef_.loc[s_, "post"] - v_) < 0.12 for s_, v_ in eff_true.items()),
      {s_: round(ef_.loc[s_, "post"] - v_, 3) for s_, v_ in eff_true.items()})
check("holdout: indicator part predicts (IC > 0.1)", fp["hold"]["ic"] > 0.1, fp["hold"]["ic"])
check("holdout: R2 vs setup-only > 0", fp["hold"]["r2_vs_setup"] > 0, fp["hold"]["r2_vs_setup"])
check("fit diagnostics fine", fp["diag"]["rhat"].max() < 1.05, fp["diag"]["rhat"].max())
check("typical draw = setup effect + mean residual", np.allclose(L.sim_mu_draws(fp, sids[0]), fp["a"][:, 0] + fp["ebar"][0]))
z_hi = fp["xs_mean"][0] + np.array([1.0, 0.0])
check("a live signal 1 s.d. higher adds beta",
      np.allclose(L.sim_mu_draws(fp, sids[0], z_hi) - L.sim_mu_draws(fp, sids[0]), fp["beta"][:, 0]))
check("residual pool per setup, centred", len(L.sim_resid_pool(fp, sids[0], 10**6)) > 100
      and abs(L.sim_resid_pool(fp, sids[0], 10**6).mean()) < 1e-9)
# skewed R: the expected R must be the mean, not the robust centre
evs = evp.copy()
evs["r"] = np.where(rng.random(len(evs)) < 0.7, -1.0, 3.0)        # mean +0.2, median -1
fs = L.sim_fit(evs, [], None, 5, "all", chains=2, iters=600, warm=200)
ok_m = all(abs(fs["eff"].set_index("setup_id").loc[s_, "post"] - evs.loc[evs["setup"] == s_, "r"].mean()) < 0.12 for s_ in sids)
check("skewed R: setup E[R] is the mean (not the t centre)", ok_m,
      fs["eff"][["setup_id", "post", "centre"]].round(3).to_dict("records"))

print("Overlap factor")
Dm = pd.DataFrame({"setup": np.repeat(["s1", "s2"], 600), "hold": 10.0})
e_iid = rng.standard_normal(1200)
k_iid = L.sim_overlap_factor(Dm, e_iid, 10)
ma = np.convolve(rng.standard_normal(1220), np.ones(10) / 10, "valid")[:1200]      # MA(9): k ~ 10
k_ma = L.sim_overlap_factor(Dm, ma, 10)
check("iid residuals: k ~ 1", k_iid < 1.6, k_iid)
check("overlapping residuals: k ~ 10", 5 < k_ma < 13, k_ma)

print("Forward paths reproduce the ledger")
n_d, n_nm = 240, 6
r2 = np.random.default_rng(8)
lc = r2.standard_normal((n_d, n_nm)) * 0.02 + 0.0008
Cc = 50 * np.exp(np.cumsum(lc, axis=0))
Oo = Cc * np.exp(r2.standard_normal((n_d, n_nm)) * 0.004)
Hh = np.maximum(Oo, Cc) * np.exp(np.abs(r2.standard_normal((n_d, n_nm))) * 0.01)
Ll = np.minimum(Oo, Cc) * np.exp(-np.abs(r2.standard_normal((n_d, n_nm))) * 0.01)
idx = pd.bdate_range("2023-01-02", periods=n_d)
names = [f"N{j}" for j in range(n_nm)]
P = {k: pd.DataFrame(v, index=idx, columns=names) for k, v in (("open", Oo), ("high", Hh), ("low", Ll), ("close", Cc))}
A_ = L._mc_atr(P["high"], P["low"], P["close"], 14).to_numpy()
i0, j0, H = 120, 2, 60
lvl = Cc[i0, j0] - 1.5 * A_[i0, j0]
prm = {"mode": "next_open", "win": 1, "tgt": 2.0, "horizon": 10, "cap": 3.0, "cost": 10.0, "tl_mode": "off",
       "exit_mode": "target", "trail": "chandelier", "trail_k": 3.0, "trail_ma": 21}
sid = next(s for s, v in L.LG_SETUPS.items() if v[0] == "MACD" and s not in L.RK_SKIP)
rules = L.sim_trade_rules(prm, sid)
for label, prm_ in (("fixed target", prm), ("chandelier trail", {**prm, "exit_mode": "trail"}),
                    ("10-day time limit", {**prm, "tl_mode": "all", "tl": 10}),
                    ("moving-average trail", {**prm, "exit_mode": "trail", "trail": "ma"})):
    ru = L.sim_trade_rules(prm_, sid)
    ma_ = (P["close"].rolling(ru["trail_ma"], min_periods=ru["trail_ma"]).mean().to_numpy()
           if ru["trail"] and ru["kind"] == "ma" else None)
    Pc = {k: v.iloc[:i0 + H + 1] for k, v in P.items()}                 # the ledger sees the same window
    Ac = L._mc_atr(Pc["high"], Pc["low"], Pc["close"], 14).to_numpy()
    tl = ru["tlimit"]
    no_lim = tl <= 0 or tl > H - 1
    direct = L.lg_label(*(Pc[k].to_numpy() for k in ("open", "high", "low", "close")), Ac, np.array([i0]), np.array([j0]),
                        np.array([lvl]), ru["mode"], ru["win"], ru["tgt"], 0 if no_lim else tl, ru["cap"], 0.5, 10.0,
                        trail=ru["trail"], trail_kind=ru["kind"], trail_k=ru["trail_k"],
                        ma=(Pc["close"].rolling(ru["trail_ma"], min_periods=ru["trail_ma"]).mean().to_numpy()
                            if ma_ is not None else None), mark_open=True)
    rows = pd.DataFrame({"date": [idx[i0]], "ticker": [names[j0]], "atr_pct": [A_[i0, j0] / Cc[i0, j0] * 100]})
    bank = L.sim_path_bank(P, rows, H)
    hist = {k: P[k].iloc[:i0 + 1, j0].to_numpy(float) for k in ("open", "high", "low", "close")}
    sim = L.sim_run_paths(bank, float(rows["atr_pct"].iloc[0]), hist, lvl, ru, 10.0)
    check(f"own path, own vol -> the ledger's R ({label})",
          abs(sim["r"][0] - direct["r"][0]) < 1e-6 and sim["outcome"][0] == direct["outcome"][0],
          (sim["r"][0], direct["r"][0], sim["outcome"][0], direct["outcome"][0]))
# doubling today's vol doubles every log move
sim2 = L.sim_run_paths(bank, 2 * float(rows["atr_pct"].iloc[0]), hist, lvl, rules, 10.0)
lm1 = np.log(L.sim_run_paths(bank, float(rows["atr_pct"].iloc[0]), hist, lvl, rules, 10.0)["close_paths"][0] / Cc[i0, j0])
lm2 = np.log(sim2["close_paths"][0] / Cc[i0, j0])
check("vol rescale multiplies log moves", np.allclose(lm2, 2 * lm1))
check("bank drops windows past the data", len(L.sim_path_bank(P, rows.assign(date=[idx[n_d - 10]]), H)["pos"]) == 0)
check("bank respects before_i (no look-ahead)", len(L.sim_path_bank(P, rows, H, before_i=i0 + H - 1)["pos"]) == 0
      and len(L.sim_path_bank(P, rows, H, before_i=i0 + H)["pos"]) == 1)

print("Set stats and look-alikes")
lab = {"status": np.array([0, 0, 0, 0, 1]), "r": np.array([2.0, -1.0, 2.0, 0.5, np.nan]),
       "outcome": np.array([0, 1, 0, 2, -1]), "hold": np.array([5, 3, 8, 10, -1]), "mae_r": np.array([-.2, -1, -.4, -.6, np.nan])}
st_ = L.sim_set_stats(lab, np.array([1, 1, 2, 0, 1.0]))
check("weighted E[R]", abs(st_["er"] - (2 - 1 + 4) / 4) < 1e-12, st_["er"])
check("weighted target share", abs(st_["p_target"] - 0.75) < 1e-12)
check("fill share counts untraded paths", abs(st_["fill"] - 4 / 5) < 1e-12)
check("bootstrap interval brackets E[R]", st_["er_lo"] <= st_["er"] <= st_["er_hi"])
Zp = rng.standard_normal((500, 3))
o, w, d = L.sim_lookalikes(Zp, Zp[17] + 1e-6, 25)
check("nearest look-alike first", o[0] == 17 and len(o) == 25 and w[0] > 0.99 and w[-1] < 0.05)

print("Does conditioning help? (look-alike check)")
m = 6000
dates = pd.bdate_range("2019-01-01", periods=1000)
dd = dates[rng.integers(0, 1000, m)]
sig = rng.standard_normal(m)
ev = pd.DataFrame({"setup": np.where(rng.random(m) < 0.5, sid, next(s for s, v in L.LG_SETUPS.items()
                                                                    if v[0] == "Trend")),
                   "date": dd, "status": 0, "sig": sig, "fake": rng.standard_normal(m)})
ev["r"] = 0.2 + 0.6 * ev["sig"] + rng.standard_normal(m)
cut = dates[600]
sc = L.sim_scaler(ev[["sig"]])
res = L.sim_knn_check(ev, ["sig"], sc, cut, K=100)
check("planted indicator: IC > 0.2", res["ic"] > 0.2, res["ic"])
check("planted indicator: top tercile beats bottom", res["spread"] > 0.5, res["spread"])
sc2 = L.sim_scaler(ev[["fake"]])
res2 = L.sim_knn_check(ev, ["fake"], sc2, cut, K=100)
check("fake indicator: IC near 0", abs(res2["ic"]) < 0.08, res2["ic"])
check("fake indicator: out-of-sample R2 <= 0", res2["r2_oos"] <= 0.005, res2["r2_oos"])

print("Posterior predictive")
e = rng.choice(np.array([-1.0] * 55 + [2.0] * 45), 400) - 0.35          # residual shape around the mean
r_emp = 0.35 + e
tight = np.full(400, 0.35)
bk = L.sim_bayes_kelly(tight, e, r_emp)
check("no parameter uncertainty: Bayesian Kelly ~ plug-in", abs(bk["f_bayes"] - bk["f_plug"]) < 0.03, (bk["f_bayes"], bk["f_plug"]))
wide = rng.normal(0.35, 0.25, 400)
bw = L.sim_bayes_kelly(wide, e, r_emp)
check("mild uncertainty: Bayesian Kelly about the same (theory: 3% lower)", abs(bw["f_bayes"] - bk["f_bayes"]) < 0.02,
      (bw["f_bayes"], bk["f_bayes"]))
vw = L.sim_bayes_kelly(rng.normal(0.35, 1.0, 400), e, r_emp)
ratio, theory = vw["f_bayes"] / bk["f_bayes"], e.var() / (e.var() + 1.0)
check("Bayesian shrink ~ sigma^2 / (sigma^2 + Var mu)", abs(ratio - theory) < 0.12, (ratio, theory))
check("cautious Kelly (10th-pct edge) well below", bw["f_caut"] < 0.6 * bw["f_bayes"], (bw["f_caut"], bw["f_bayes"]))
neg = L.sim_bayes_kelly(np.full(400, -0.2), e, r_emp - 0.55)
check("negative edge: Bayesian Kelly 0", neg["f_bayes"] == 0.0)
eq0 = L.sim_equity(wide, e, 0.0, 50, 500)
check("stake 0: flat equity", eq0["bayes"]["p_loss"] == 0 and abs(eq0["bayes"]["med_end"] - 1) < 1e-12)
eqw = L.sim_equity(wide, e, 0.05, 100, 4000, 0.2, r_emp=r_emp)
fb, fp = eqw["bayes"]["fan"].iloc[-1], eqw["plug"]["fan"].iloc[-1]
check("uncertain edge widens the fan at both ends", fb["p05"] < fp["p05"] and fb["p95"] > fp["p95"],
      (fb["p05"], fp["p05"], fb["p95"], fp["p95"]))
check("fan starts at 1", eqw["bayes"]["fan"]["p50"].iloc[0] == 1.0)

print("The Brief's names into the Simulation")
m_sid = next(s_ for s_, v_ in L.LG_SETUPS.items() if s_.startswith("macd:") and s_ not in L.RK_SKIP)
tl_sid = "tl:full"
Rk = pd.DataFrame({"status": ["week", "today", "trig", "week", "today", "week", "week", "week"],
                   "rank": [9, 8, 7, 6, 5, 4, 3, 2], "family": "MACD", "signal": "sig",
                   "trigger": 10.0, "stop": 9.0}, index=["W1", "T1", "T2", "W2", "T3", "W3", "W4", "W5"])
Sb = pd.DataFrame({"ticker": ["T1", "T1", "W1", "T2", "W2"], "status": ["today", "watch", "week", "trig", "week"],
                   "ledger_id": [m_sid, tl_sid, "", "rs8:pocket", ""]})
pk = L.sim_brief_pack(Rk, Sb, "2026-10-23")
order = [r_["ticker"] for r_ in pk["rows"]]
check("Brief order: focus cards, then this week's, then the rest",
      order[:3] == ["T1", "T2", "T3"] and order[3:7] == ["W1", "W2", "W3", "W4"] and order[7] == "W5", order)
check("Brief tiers labelled", pk["rows"][0]["tier"] == "today's focus" and pk["rows"][3]["tier"] == "this week's focus"
      and pk["rows"][7]["tier"] == "setting up")
check("ledger ids kept per name (live scans only)", pk["rows"][0]["ledger_ids"] == [m_sid] and pk["rows"][3]["ledger_ids"] == [])
check("empty Brief packs cleanly", L.sim_brief_pack(pd.DataFrame(), pd.DataFrame(), "x")["rows"] == [])
dts_b = pd.bdate_range("2026-09-01", periods=40)
evb = pd.DataFrame({"setup": [tl_sid, m_sid, m_sid, tl_sid, m_sid, m_sid],
                    "ticker": ["T1", "T1", "W1", "T2", "ZZ", "T3"],
                    "i": [39, 38, 37, 30, 39, 39], "date": dts_b[[39, 38, 37, 30, 39, 39]], "status": 3})
Cb, miss = L.sim_brief_candidates(evb, pk, 3, 7)
check("candidates follow the Brief's order", list(dict.fromkeys(Cb["ticker"])) == ["T1", "T3", "W1"], list(Cb["ticker"]))
t1 = Cb[Cb["ticker"] == "T1"]
check("the Brief's own scan comes first", t1["setup"].iloc[0] == m_sid and bool(t1["brief_match"].iloc[0])
      and not bool(t1["brief_match"].iloc[1]), t1[["setup", "brief_match"]].to_dict("records"))
check("names outside the Brief are left out", "ZZ" not in set(Cb["ticker"]))
check("a Brief signal older than the window is reported missing (T2, 9 sessions)",
      [m_["ticker"] for m_ in miss] == ["T2", "W2", "W3", "W4"], [m_["ticker"] for m_ in miss])
check("window is at least 5 sessions for Brief names", len(L.sim_brief_candidates(evb, pk, 0, 7)[0]) == len(Cb))
check("n limits how far down the Brief", set(L.sim_brief_candidates(evb, pk, 3, 1)[0]["ticker"]) == {"T1"})
good = {"er": 0.3, "er_lo": 0.1, "er_hi": 0.5, "p_er_pos": 0.99, "ess": 80}
check("verdict: supports", L.sim_verdict(good, {"er": 0.1}) == "supports")
check("verdict: mixed when it doesn't beat uptrend names", L.sim_verdict(good, {"er": 0.4}) == "mixed")
check("verdict: against", L.sim_verdict({**good, "er": -0.2, "er_lo": -0.5, "er_hi": -0.01, "p_er_pos": 0.02}, {}) == "against")
check("verdict: a near-zero edge is mixed, not against",
      L.sim_verdict({**good, "er": -0.01, "er_lo": -0.36, "er_hi": 0.36, "p_er_pos": 0.48}, {"er": 0.1}) == "mixed")
check("verdict: thin flag", L.sim_verdict({**good, "ess": 12}, {"er": 0.0}) == "supports (thin)")

print(f"\n{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
