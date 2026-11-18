"""Tests for Stocks > Alphas by trade: every setup has a trade type, the readings cover every alpha and category,
clustered standard errors by hand, planted effects found on the right side for the right trade type (mean
reversion low for a failed-bounce short, high for a rebound, VWAP low for a breakout), nothing found in noise, a
setup-mix confound removed by the within-setup demeaning, an effect in only one half of the history not passing,
a U-shape flagged, the readings and the usual-reading check, collecting trades from the session (dedupe, baselines
kept apart, the breakout model's two heads), the alphas at the signal's own close, and the breakout model's
category roll-up.
Run: python test_alpha_map.py"""
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


rng = np.random.default_rng(8)

print("coverage")
ids = set(L.LG_SETUPS) | set(L.BL_SETUPS) | set(L.BR_SETUPS)
missing = [s for s in ids if not s.startswith("base:") and s not in L.AM_TYPES]
check("every ledger setup has a trade type; every type has a description", not missing
      and set(L.AM_TYPES.values()) <= set(L.AM_TYPE_ORDER) and set(L.AM_TYPE_ORDER) <= set(L.AM_TYPE_DESC), missing)
check("high and low meanings for every alpha and category; every alpha has a category",
      set(L.OB_ALPHA_IDS) <= set(L.AM_ALPHA_SIDES) and set(L.OB_ALPHA_CATS) <= set(L.AM_CAT_SIDES)
      and all(L.am_alpha_cat(f"al_a{i}") in L.OB_ALPHA_CATS for i in L.OB_ALPHA_IDS))
check("a reading for every side x category x direction", all((sd, c, b) in L.AM_READ for sd in ("long", "short")
                                                            for c in L.OB_ALPHA_CATS for b in ("high", "low")))

print("clustered standard errors")
n = 400
x = rng.normal(size=n)
y = 0.5 * x + rng.normal(size=n)
X = np.column_stack([np.ones(n), x])
b, se = L.am_cluster_ols(X, y, np.arange(n))
e = y - X @ b
inv = np.linalg.inv(X.T @ X)
V = inv @ (X.T * e ** 2) @ X @ inv * (n / (n - 1)) * ((n - 1) / (n - 2))
check("one trade per cluster = the White (HC1) errors", np.allclose(se, np.sqrt(np.diag(V)), rtol=1e-6), (se, np.sqrt(np.diag(V))))
g = np.repeat(np.arange(40), 10)
xg = np.repeat(rng.normal(size=40), 10) + 0.05 * rng.normal(size=n)
yg = np.repeat(rng.normal(size=40), 10) + rng.normal(size=n)
_, se_c = L.am_cluster_ols(np.column_stack([np.ones(n), xg]), yg, g)
_, se_i = L.am_cluster_ols(np.column_stack([np.ones(n), xg]), yg, np.arange(n))
check("trades that move together on a date: clustered errors wider than per-trade ones", se_c[1] > 1.8 * se_i[1], (se_c, se_i))

print("planted effects by trade type")
days = pd.bdate_range("2021-01-04", periods=700)
C = list(L.OB_ALPHA_COLS)


def make(setup, n, eff=None, base_r=0.0, seed=0, half=False, ushape=None):
    r_ = np.random.default_rng(seed)
    A = r_.uniform(-0.5, 0.5, size=(n, len(C))).astype(np.float32)
    d = np.sort(r_.choice(days, n))
    y = base_r + r_.normal(0, 1.0, n)
    for col, k in (eff or {}).items():
        j = C.index(col)
        w = (d < days[350]) if half else np.ones(n, bool)
        y = y + np.where(w, k * A[:, j], 0.0)
    if ushape:
        j = C.index(ushape)
        y = y + 4.0 * (A[:, j] ** 2 - 1 / 12)
    ev = pd.DataFrame(A, columns=C)
    ev["setup"], ev["ticker"], ev["date"], ev["r"], ev["lag"] = setup, [f"T{i % 80}" for i in range(n)], d, y, 0
    ev["source"] = "test"
    ev["type"] = L.AM_TYPES.get(setup, "Baseline: long ledger")
    ev["side"] = "short" if ev["type"].iloc[0].startswith("Short") else "long"
    ev["setup_key"] = setup
    return ev


ev = pd.concat([make("br:luk_fade", 1500, {"al_cat_MRV": -1.2, "al_a30": -1.0}, seed=1),
                make("bl:mrv_dip", 1500, {"al_cat_MRV": 1.2}, seed=2),
                make("bl:breakout55", 1500, {"al_cat_VWP": -1.2, "al_a42": -1.0}, seed=3),
                make("macd:pullback", 1500, seed=4)], ignore_index=True)
T = L.am_profile(ev)
S = L.am_summary(T)


def cell(typ, cat):
    return S[(S["type"] == typ) & (S["category"] == cat)].iloc[0]


fb, rb, bo = cell("Short: failed bounce", "MRV"), cell("Rebound / oversold", "MRV"), cell("Breakout", "VWP")
check("mean reversion MATTERS for the failed-bounce short, better when LOW (overbought); for the rebound, better when HIGH",
      fb["status"] == "MATTERS" and fb["better"] == "low" and rb["status"] == "MATTERS" and rb["better"] == "high",
      (fb[["status", "better", "t"]].to_dict(), rb[["status", "better", "t"]].to_dict()))
check("VWAP MATTERS for the breakout, better when LOW (closing over VWAP)", bo["status"] == "MATTERS" and bo["better"] == "low",
      bo[["status", "better", "t"]].to_dict())
check("each type's strongest category comes first in its list",
      S[S["type"] == "Short: failed bounce"].iloc[0]["category"] == "MRV" and S[S["type"] == "Breakout"].iloc[0]["category"] == "VWP")
noise = T[(T["type"] == "Pullback in trend")]
check("pure noise (the pullback trades): nothing MATTERS across 34 inputs", not (noise["status"] == "MATTERS").any()
      and noise["q"].between(0, 1).all(), noise.sort_values("t")[["input", "t", "q", "status"]].head(3))
check("the planted alpha leads its category, with its own meaning",
      fb["lead"].startswith("#30") and bo["lead"].startswith("#42"), (fb["lead"], bo["lead"]))
check("the reading: effect, what low means, the leading alpha, what it says, and the usual reading agrees",
      "better when low" in fb["why"].lower() and "overbought" in fb["why"] and "#30" in fb["why"]
      and "fading an exhausted bounce" in fb["why"] and "agrees" in fb["why"] and fb["prior_check"] == "agrees", fb["why"])
check("breakout + VWAP: 'a close over VWAP helped' and the usual reading agrees",
      "close over VWAP helped" in bo["why"] and bo["prior_check"] == "agrees", bo["why"])
check("top fifth vs bottom fifth, within setups: the effect has the slope's sign", fb["effect"] < -0.4 and bo["effect"] < -0.4 and rb["effect"] > 0.4,
      (fb["effect"], bo["effect"], rb["effect"]))
pb_mrv = cell("Pullback in trend", "MRV")
check("no effect where the usual reading expects one: says so", pb_mrv["prior_check"] == "not seen" and "isn't borne out" in pb_mrv["why"],
      pb_mrv["why"])

print("traps")
a1 = make("trend:dc20", 1200, base_r=+0.6, seed=5)
a2 = make("trend:dc55", 1200, base_r=-0.6, seed=6)
a1["al_cat_MOM"] = rng.uniform(0.0, 0.5, len(a1)).astype(np.float32)          # one setup lives high on momentum...
a2["al_cat_MOM"] = rng.uniform(-0.5, 0.0, len(a2)).astype(np.float32)         # ...the other low, with different R
Tm = L.am_profile(pd.concat([a1, a2], ignore_index=True))
mom = Tm[Tm["input"] == "al_cat_MOM"].iloc[0]
pooled = np.polyfit(np.r_[a1["al_cat_MOM"], a2["al_cat_MOM"]], np.r_[a1["r"], a2["r"]], 1)[0]
check("a setup-mix confound (one setup high on momentum and better, the other low and worse): no effect within setups",
      mom["status"] in ("NO EFFECT", "MAYBE") and abs(mom["t"]) < 2.5 and pooled > 1.0 and abs(mom["effect"]) < 0.3
      and mom["R_hi"] - mom["R_lo"] > 0.8, (mom["t"], pooled, mom["effect"], mom["R_hi"] - mom["R_lo"]))
hh = L.am_profile(make("br:fl_break50", 2000, {"al_cat_VOL": 2.0}, seed=7, half=True))
hv = hh[hh["input"] == "al_cat_VOL"].iloc[0]
check("an effect in only the first half of the history: not MATTERS (the halves disagree)",
      hv["status"] != "MATTERS" and not hv["halves"] and abs(hv["slope_h1"]) > 1.0 and abs(hv["slope_h2"]) < 0.6, hv[["t", "slope_h1", "slope_h2", "status"]].to_dict())
uu = L.am_profile(make("lbr:taylor", 2000, ushape="al_cat_CMP", seed=9))
uv = uu[uu["input"] == "al_cat_CMP"].iloc[0]
check("a U-shape (both extremes better, no straight-line slope) is flagged", uv["shape"].startswith("U") and abs(uv["t"]) < 2.5,
      uv[["t", "t_curve", "shape"]].to_dict())
thin = L.am_profile(make("br:ep_down", 60, seed=10))
check("under 100 trades: THIN, with a reading that says so", (thin["status"] == "THIN").all()
      and L.am_summary(thin)["why"].str.lower().str.contains("too few").all())

print("collecting the session's trades")


def ledger_ev(setups, n, seed):
    r_ = np.random.default_rng(seed)
    return pd.DataFrame({"setup": r_.choice(setups, n), "ticker": [f"N{i % 30}" for i in range(n)],
                         "date": r_.choice(days, n), "r": r_.normal(size=n), "status": r_.choice([0, 0, 0, 1], n)})


mk_ev = ledger_ev(["trend:dc20", "macd:pullback", "base:uptrend"], 300, 11)
li_ev = pd.concat([mk_ev.iloc[:100], ledger_ev(["ep:9m"], 50, 12)], ignore_index=True)     # 100 repeats of the market run
ss = {"lg_res": {"runs": {"market": {"ev": mk_ev}, "list": {"ev": li_ev}}},
      "bls_res": {"run": {"ev": ledger_ev(["bl:mrv_dip", "base:uptrend"], 200, 13)}},
      "bsp_res": {"run": {"ev": ledger_ev(["br:luk_fade", "base:downtrend"], 200, 14)}}}
orb = pd.DataFrame({"ticker": ["G1", "G2", "G3"], "date": [days[5]] * 3, "m": [5, 15, 30], "intra_R": [1.0, -1.0, np.nan],
                    "swing_R": [2.0, -1.0, 0.5], **{c: [0.1, 0.2, 0.3] for c in C}})
E = L.am_collect(ss, orb)
traded = lambda d: int((d["status"] == 0).sum())
check("traded rows only; a trade in both Setup ledger runs counts once",
      (E["source"] == "Setup ledger (whole market)").sum() == traded(mk_ev)
      and (E["source"] == "Setup ledger (your list)").sum() == traded(li_ev.iloc[100:]), E["source"].value_counts().to_dict())
check("types and sides: shorts from Bear spreads, the same baseline id kept apart by ledger",
      set(E.loc[E["source"] == "Bear spreads", "side"]) == {"short"}
      and {"Baseline: long ledger", "Baseline: bull spreads", "Baseline: bear spreads"} <= set(E["type"])
      and E.loc[E["type"] == "Baseline: bull spreads", "setup_key"].str.contains("Bull spreads").all())
ob = E[E["source"] == "Breakout model"]
check("the breakout model's trades: both heads, finite R only, their alpha inputs carried, at the prior close (lag 1)",
      (ob["type"] == "Gap-up ORB, intraday").sum() == 2 and (ob["type"] == "Gap-up ORB, swing").sum() == 3
      and (ob["lag"] == 1).all() and np.allclose(ob.loc[ob["setup"] == "orb:5m", "al_a4"], 0.1))

print("the alphas at the signal close")
n_d, n_n = 380, 30
idx = pd.bdate_range("2022-01-03", periods=n_d)
cols = [f"S{i:02d}" for i in range(n_n)]
Cl = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.02, (n_d, n_n)), 0) + 3.5), index=idx, columns=cols)
P = {"open": Cl.shift(1).fillna(Cl), "high": Cl * 1.01, "low": Cl * 0.99, "close": Cl,
     "volume": pd.DataFrame(rng.uniform(5e5, 2e6, (n_d, n_n)), index=idx, columns=cols)}
P["high"] = np.maximum(P["high"], P["open"])
P["low"] = np.minimum(P["low"], P["open"])
e0 = L.ob_alpha_inputs(P, pd.DataFrame({"ticker": ["S03"], "date": [idx[350]]}), lag=0)
e1 = L.ob_alpha_inputs(P, pd.DataFrame({"ticker": ["S03"], "date": [idx[351]]}), lag=1)
check("lag 0 = the signal's own close (the same inputs as lag 1 on the next session)",
      np.allclose(e0[C].to_numpy(float), e1[C].to_numpy(float), equal_nan=True) and e0[C].notna().sum(axis=1).iloc[0] > 20)
evs = pd.DataFrame({"ticker": ["S03", "S04", "S03"], "date": [idx[350], idx[350], idx[351]], "r": [1.0, 0.0, -1.0], "lag": [0, 0, 1],
                    "al_a4": [np.nan, np.nan, 0.33]})
at_ = L.am_attach(P, evs)
check("attaching: the ledger trades get their inputs; a trade that already carries them keeps them",
      np.allclose(at_.loc[0, C].to_numpy(float), e0[C].to_numpy(float)[0], equal_nan=True) and abs(at_.loc[2, "al_a4"] - 0.33) < 1e-6
      and at_.loc[2, "al_a1"] != at_.loc[2, "al_a1"])

print("the breakout model by category")
imp = pd.DataFrame({"feature": ["al_a30", "al_a4", "al_cat_MRV", "al_a42", "x_gap"], "model": "gbm", "head": "intra",
                    "auc_drop": [0.010, 0.004, 0.002, 0.001, 0.05], "input": ["#30", "#4", "MRV", "#42", "gap"]})
bc = L.ob_importance_by_category(imp, "intra")
check("permutation importance added up by category (its alphas and its score), strongest first, break inputs left out",
      bc["category"].iloc[0] == "Mean reversion" and abs(bc["auc_drop_gbm"].iloc[0] - 0.016) < 1e-12 and bc["helping"].iloc[0] == 3
      and bc["top"].iloc[0] == "#30" and len(bc) == 2 and "oversold" in bc["high_means"].iloc[0], bc)

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
