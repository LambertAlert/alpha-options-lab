"""Planted-case tests for the Deflated Sharpe, the daily-bar spread estimators and the MAE/MFE counterfactuals in
alpha_options_lab.py. Run: python test_ledger_stats.py"""
import math, sys, warnings
import numpy as np
import pandas as pd
from statistics import NormalDist

warnings.filterwarnings("ignore")
import alpha_options_lab as L

PASS, FAIL = 0, []
N = NormalDist()


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


rng = np.random.default_rng(7)

print("Deflated Sharpe")
# 1. PSR against the formula by hand
sr, n, sk, ku = 0.15, 200, -0.8, 6.0
want = N.cdf((sr - 0.0) * math.sqrt(n - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2))
check("psr matches the closed form", abs(L.psr(sr, 0.0, n, sk, ku) - want) < 1e-6)   # the lab CDF is A&S 7.1.26
# 2. normal returns: denominator is 1 + SR^2/2
want = N.cdf(sr * math.sqrt(n - 1) / math.sqrt(1 + sr ** 2 / 2))
check("psr under normality", abs(L.psr(sr, 0.0, n, 0.0, 3.0) - want) < 1e-6)
# 3. negative skew and fat tails lower confidence in a positive Sharpe
check("skew/kurtosis lower psr", L.psr(sr, 0, n, -1.5, 9) < L.psr(sr, 0, n, 0, 3))
# 4. E[max SR]: zero at N=1, rises with N, scales with sqrt(V)
e = [L.expected_max_sr(k, 0.01) for k in (1, 2, 10, 100, 1000)]
check("E[max SR] is 0 at N=1", e[0] == 0.0)
check("E[max SR] rises with N", all(a < b for a, b in zip(e, e[1:])), e)
check("E[max SR] scales with sqrt(V)", abs(L.expected_max_sr(50, 0.04) / L.expected_max_sr(50, 0.01) - 2) < 1e-12)
# 5. E[max SR] against Monte Carlo maxima of N standard normals (an approximation: about 4% high at N=10, tighter
#    as N grows; erring high makes the deflation a little stricter)
for k, tol in ((10, 0.05), (100, 0.03), (1000, 0.03)):
    mc = rng.standard_normal((4000, k)).max(axis=1).mean()
    f = L.expected_max_sr(k, 1.0)
    check(f"E[max] vs Monte Carlo, N={k}", abs(f / mc - 1) < tol, (f, mc))
# 6. sharpe_stats: moments and n_eff from a Newey-West error
x = rng.standard_normal(500) * 1.3 + 0.2
s = L.sharpe_stats(x)
check("sharpe_stats SR", abs(s["sr"] - x.mean() / x.std(ddof=1)) < 1e-12)
check("sharpe_stats n_eff defaults to n", s["n_eff"] == 500)
se = x.std(ddof=1) / math.sqrt(125)                 # as if only 125 independent observations
check("n_eff from the NW error", abs(L.sharpe_stats(x, se)["n_eff"] - 125) < 1e-9)
check("n_eff never above n", L.sharpe_stats(x, x.std(ddof=1) / 100)["n_eff"] == 500)
check("normal sample: skew ~0, kurt ~3", abs(s["skew"]) < 0.3 and abs(s["kurt"] - 3) < 0.6, (s["skew"], s["kurt"]))
# 7. one tested row and no extra trials: DSR = PSR(0)
sb = pd.DataFrame({"sr": [0.2], "skew": [0.0], "kurt": [3.0], "n_eff": [100.0]})
d = L.deflate_table(sb)
check("N=1: DSR equals PSR", abs(d["dsr"].iloc[0] - d["psr"].iloc[0]) < 1e-12)
# 8. more trials lower the DSR, never the PSR
sb = pd.DataFrame({"sr": [0.25, 0.1, 0.05, -0.05, 0.0], "skew": 0.0, "kurt": 3.0, "n_eff": 150.0})
d0, d1 = L.deflate_table(sb, 0), L.deflate_table(sb, 200)
check("extra trials lower the DSR", (d1["dsr"] < d0["dsr"]).all())
check("extra trials leave PSR alone", np.allclose(d1["psr"], d0["psr"]))
check("trial count recorded", d1.attrs["dsr_trials"] == 205)
# 9. untested rows (the baseline) get no DSR but keep PSR
d = L.deflate_table(sb, 0, np.array([True, True, True, True, False]))
check("baseline row: no DSR", np.isnan(d["dsr"].iloc[4]) and np.isfinite(d["psr"].iloc[4]))
check("baseline excluded from N", d.attrs["dsr_trials"] == 4)
# 10. calibration under the null: pick the best of 50 unskilled strategies
hits_psr = hits_dsr = 0
R = 400
for _ in range(R):
    X = rng.standard_normal((50, 250))
    rows = [L.sharpe_stats(r) for r in X]
    t = L.deflate_table(pd.DataFrame(rows))
    b = int(np.nanargmax(t["sr"].to_numpy()))
    hits_psr += t["psr"].iloc[b] >= 0.95
    hits_dsr += t["dsr"].iloc[b] >= 0.95
check("null: best-of-50 passes PSR often", hits_psr / R > 0.5, hits_psr / R)
check("null: best-of-50 rarely passes DSR", hits_dsr / R < 0.10, hits_dsr / R)
# 11. a real edge still clears the deflation
X = rng.standard_normal((50, 250))
X[0] += 0.5                                         # SR 0.5 per trade over 250 trades
t = L.deflate_table(pd.DataFrame([L.sharpe_stats(r) for r in X]))
check("real edge survives deflation", t["dsr"].iloc[0] >= 0.95, t["dsr"].iloc[0])

print("Spread estimators")


def sim_bars(n_days, n_names, spread, vol=0.02, steps=78, seed=0):
    """Mid follows a random walk; each print is the mid +- half the spread with a random side."""
    r = np.random.default_rng(seed)
    dt = vol / math.sqrt(steps)
    lm = np.cumsum(r.standard_normal((n_days * steps, n_names)) * dt, axis=0) + math.log(50)
    side = r.choice([-1.0, 1.0], size=lm.shape)
    px = np.exp(lm) * (1 + side * np.asarray(spread)[None, :] / 2)
    px = px.reshape(n_days, steps, n_names)
    idx = pd.bdate_range("2022-01-03", periods=n_days)
    f = lambda a: pd.DataFrame(a, index=idx, columns=[f"T{j}" for j in range(n_names)])
    return f(px[:, 0]), f(px.max(1)), f(px.min(1)), f(px[:, -1])


spreads = np.array([0.0, 0.002, 0.005, 0.01, 0.02])
o, h, l, c = sim_bars(300, len(spreads), spreads, seed=3)
P = {"open": o, "high": h, "low": l, "close": c}
for m in ("ar", "cs"):
    est = L.spread_panel(P, m).iloc[30:].mean().to_numpy()
    # at 2% daily vol neither estimator resolves spreads under ~30bp (a positive noise floor), so rank from 0.5% up
    check(f"{m}: ranks 0.5% < 1% < 2%", est[2] < est[3] < est[4], np.round(est * 1e4))
    check(f"{m}: 1% spread above the zero-spread floor", est[3] > 1.5 * est[0], np.round(est * 1e4))
    check(f"{m}: 1% spread within 0.5x-1.6x", 0.005 < est[3] < 0.016, est[3])
    check(f"{m}: 2% spread within 0.5x-1.6x", 0.01 < est[4] < 0.032, est[4])
    check(f"{m}: values in [0, cap]", np.nanmin(L.spread_panel(P, m).to_numpy()) >= 0
          and np.nanmax(L.spread_panel(P, m).to_numpy()) <= L.SPREAD_CAP + 1e-15)
    # no look-ahead: the estimate at date t is the same when the data ends at t
    full = L.spread_panel(P, m)
    cut = L.spread_panel({k: v.iloc[:151] for k, v in P.items()}, m)
    check(f"{m}: no look-ahead", np.allclose(full.iloc[:151].to_numpy(), cut.to_numpy(), equal_nan=True))
avg = L.spread_panel(P, "avg")
check("avg is the mean of the two", np.allclose(avg, (L.spread_panel(P, "ar") + L.spread_panel(P, "cs")) / 2, equal_nan=True))
# overnight gaps should not show up as spread (CS adjustment)
o2, h2, l2, c2 = sim_bars(300, 1, np.array([0.005]), seed=11)
gap = pd.Series(np.where(np.arange(300) % 5 == 0, 1.03, 1.0), index=c2.index).cumprod()
Pg = {k: v.mul(gap, axis=0) for k, v in {"open": o2, "high": h2, "low": l2, "close": c2}.items()}
base = L.spread_panel({"open": o2, "high": h2, "low": l2, "close": c2}, "cs").iloc[30:].mean().iloc[0]
gapped = L.spread_panel(Pg, "cs").iloc[30:].mean().iloc[0]
check("cs: 3% gaps every 5 days barely move it", abs(gapped - base) < 0.0025, (base, gapped))

print("Excursions")
g = pd.DataFrame({"r": [2.0, -1.0, 0.5, -1.0, 3.0, -0.4],
                  "mae_r": [-0.2, -1.0, -0.6, -1.0, -0.4, -0.7],
                  "mfe_r": [2.0, 0.3, 1.2, 1.1, 3.5, 0.2],
                  "outcome": [0, 1, 2, 1, 3, 2]})
st = L.exc_stop_curve(g, [0.5, 1.0])
# stop at 0.5R: trades 1, 2, 3, 5 hit it -> [2, -.5, -.5, -.5, 3, -.5]
check("tighter stop E[R]", abs(st["er"].iloc[0] - np.mean([2, -.5, -.5, -.5, 3, -.5])) < 1e-12, st["er"].iloc[0])
check("tighter stop: winners lost", abs(st["winners_lost"].iloc[0] - 1 / 3) < 1e-12)
check("stop at the original 1R changes nothing", abs(st["er"].iloc[1] - g["r"].mean()) < 1e-12)
check("E[R] per new risk = E[R] / k", np.allclose(st["er_risk"], st["er"] / st["stop_r"]))
tg = L.exc_target_curve(g, [1.0])
# target 1R: trades 0, 2, 3, 4 reached it -> [1, -1, 1, 1, 1, -.4]
check("fixed target E[R]", abs(tg["er"].iloc[0] - np.mean([1, -1, 1, 1, 1, -.4])) < 1e-12)
check("fixed target reach rate", abs(tg["p_reach"].iloc[0] - 4 / 6) < 1e-12)
so = L.exc_scale_out(g, [1.0], 0.5)
want = np.mean([1.5, -1, 0.75, 0.0, 2.0, -0.4])
check("scale-out exact", abs(so["er"].iloc[0] - want) < 1e-12, so["er"].iloc[0])
check("scale-out frac 0 = original", abs(L.exc_scale_out(g, [1.0], 0.0)["er"].iloc[0] - g["r"].mean()) < 1e-12)
check("scale-out frac 1 = fixed target", abs(L.exc_scale_out(g, [1.0], 1.0)["er"].iloc[0] - tg["er"].iloc[0]) < 1e-12)
sm = L.exc_summary(g)
check("summary: winners' median MAE", abs(sm["win_mae_med"] - (-0.4)) < 1e-12)
check("summary: losers that ran 1R first", abs(sm["loss_mfe_ge1"] - 1 / 3) < 1e-12)
check("summary: capture", abs(sm["capture"] - np.mean([2, .5, 3]) / np.mean([2, 1.2, 3.5])) < 1e-12)

# edge ratio on a planted path: every name rises 1 ATR a day for 5 days after the signal, then falls
idx = pd.bdate_range("2023-01-02", periods=80)
names = [f"N{j}" for j in range(30)]
base = np.full((80, 30), 100.0)
for t in range(41, 46):
    base[t:] += 1.0
base[46:] -= np.arange(1, 35)[:, None] * 0.5
C_ = pd.DataFrame(base, index=idx, columns=names)
Pp = {"open": C_, "high": C_ + 0.5, "low": C_ - 0.5, "close": C_}
ev = pd.DataFrame({"ticker": names, "i": 40, "date": idx[40], "entry": 101.0})   # day 1 low 100.5: MAE 0.5 ATR
er = L.edge_ratio_curve(Pp, ev, max_d=20)
check("edge ratio computed", len(er) >= 15, len(er))
check("edge ratio on day 3 = 2.5 / 0.5", abs(er.loc[er["day"] == 3, "edge_ratio"].iloc[0] - 5) < 1e-9, er.head(4))
check("MFE flat after the peak", er["mfe_atr"].iloc[-1] == er["mfe_atr"].max())
check("MAE grows after the drop", er["mae_atr"].iloc[-1] > er["mae_atr"].iloc[5])
ev2 = ev.drop(columns="i")
check("aligned by date", L.edge_ratio_curve(Pp, ev2, max_d=20).equals(er))

print("Per-event cost in lg_label")
n, k = 60, 4
r2 = np.random.default_rng(5)
Cc = 50 * np.exp(np.cumsum(r2.standard_normal((n, k)) * 0.02, axis=0))
Oo = Cc * (1 + r2.standard_normal((n, k)) * 0.003)
Hh = np.maximum(Oo, Cc) * 1.01
Ll = np.minimum(Oo, Cc) * 0.99
A = np.full((n, k), 1.0)
ii = np.array([10, 15, 20, 25])
jj = np.array([0, 1, 2, 3])
lvl = Cc[ii, jj] - 1.5
a = L.lg_label(Oo, Hh, Ll, Cc, A, ii, jj, lvl, cost_bp=12.0)
b = L.lg_label(Oo, Hh, Ll, Cc, A, ii, jj, lvl, cost_bp=np.full(4, 12.0))
check("array cost equal to flat", np.allclose(a["r"], b["r"], equal_nan=True))
c2 = L.lg_label(Oo, Hh, Ll, Cc, A, ii, jj, lvl, cost_bp=np.array([12.0, 12.0, 60.0, 12.0]))
check("higher cost lowers only that trade", np.allclose(np.delete(c2["r"], 2), np.delete(a["r"], 2), equal_nan=True)
      and (not np.isfinite(a["r"][2]) or c2["r"][2] < a["r"][2]))

print(f"\n{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
