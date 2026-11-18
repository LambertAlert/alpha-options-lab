"""Tests for the alpha inputs in the breakout model: each gapper's alphas as percentiles of the prior close's crowd
(by hand), the categories and composite, no lookahead, today's inputs = training's, PCA and the decile mutual
information selection, the walk-forward finding a planted alpha signal (and not finding one in noise), the verdict
moving to the alpha model only when it beats the same model without alphas, permutation importance, the saved
models and today's odds from the recommended model.
Run: python test_orb_alphas.py"""
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import alpha_options_lab as L

PASS, FAIL = 0, []
TORCH = L._torch() is not None


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


rng = np.random.default_rng(4)

print("percentiles of the crowd, by hand")
dates = pd.bdate_range("2024-01-01", periods=3)
names = [f"N{i:02d}" for i in range(30)]
ids = [4, 24, 30, 9, 19, 52]
A = {aid: pd.DataFrame(rng.normal(size=(3, 30)), index=dates, columns=names) for aid in ids}
U = pd.DataFrame(False, index=dates, columns=names)
U.iloc[:, :25] = True                                   # N25..N29 aren't in the crowd
A[4].iloc[1, 27] = np.nan
pairs = pd.DataFrame({"ticker": ["N03", "N27", "N28"], "asof": [dates[1]] * 3})
al = L.ob_alpha_rows(A, U, pairs)


def mid(ref, v):
    ref = np.sort(ref)
    return ((ref < v).sum() + (ref <= v).sum()) / (2 * len(ref))


ref = {aid: A[aid].iloc[1, :25].to_numpy() for aid in ids}
exp3 = mid(ref[24], A[24].at[dates[1], "N03"]) - 0.5
exp28 = mid(ref[9], A[9].at[dates[1], "N28"]) - 0.5
check("each alpha = its place among the day's crowd (ties in the middle), centred; a name outside the crowd placed in it",
      abs(al.at[0, "al_a24"] - exp3) < 1e-6 and abs(al.at[2, "al_a9"] - exp28) < 1e-6, (al.at[0, "al_a24"], exp3))
check("a missing alpha stays missing; alphas not computed are missing", np.isnan(al.at[1, "al_a4"]) and np.isnan(al.at[0, "al_a1"]))
pe = {aid: np.array([mid(ref[aid], A[aid].at[dates[1], "N03"])]) for aid in ids}
mom, mrv = np.mean([pe[i][0] for i in (9, 19, 52)]), np.mean([pe[i][0] for i in (4, 24, 30)])
raw3 = (0.22 * mom + 0.10 * (1 - mrv)) / 0.32
prc = {aid: np.array([mid(ref[aid], x) for x in ref[aid]]) for aid in ids}
raw_ref = (0.22 * np.mean([prc[i] for i in (9, 19, 52)], 0) + 0.10 * (1 - np.mean([prc[i] for i in (4, 24, 30)], 0))) / 0.32
check("categories = the mean of their alphas' percentiles; the composite = the weighted mean (mean reversion inverted), "
      "placed among the crowd's composites",
      abs(al.at[0, "al_cat_MOM"] - (mom - 0.5)) < 1e-6 and abs(al.at[0, "al_cat_MRV"] - (mrv - 0.5)) < 1e-6
      and abs(al.at[0, "al_composite"] - (mid(raw_ref, raw3) - 0.5)) < 1e-6, (al.at[0, "al_composite"], mid(raw_ref, raw3) - 0.5))
check("a crowd under 20 names gives nothing", L.ob_alpha_rows(A, U.iloc[:, :10].reindex(columns=names, fill_value=False), pairs)
      .isna().all().all())

print("gap days: the prior close, no lookahead, today = training")
n_d, n_n = 420, 40
idx = pd.bdate_range("2022-01-03", periods=n_d)
cols = [f"S{i:02d}" for i in range(n_n)]
lc = np.cumsum(rng.normal(0, 0.02, (n_d, n_n)), 0) + np.log(rng.uniform(20, 80, n_n))
C = pd.DataFrame(np.exp(lc), index=idx, columns=cols)
O = C.shift(1).fillna(C) * np.exp(rng.normal(0, 0.005, (n_d, n_n)))
H = np.maximum(O, C) * (1 + rng.uniform(0, 0.02, (n_d, n_n)))
Lo = np.minimum(O, C) * (1 - rng.uniform(0, 0.02, (n_d, n_n)))
V = pd.DataFrame(rng.uniform(5e5, 3e6, (n_d, n_n)), index=idx, columns=cols)
P = {"open": O, "high": H, "low": Lo, "close": C, "volume": V}
gd = idx[400]
ev = pd.DataFrame({"ticker": ["S05", "S11"], "date": [gd, gd]})
a1 = L.ob_alpha_inputs(P, ev)
P2 = {k: v.copy() for k, v in P.items()}
for k in P2:
    P2[k].loc[gd:] = P2[k].loc[gd:] * rng.uniform(0.5, 1.5, P2[k].loc[gd:].shape)
a2 = L.ob_alpha_inputs(P2, ev)
check("changing the gap day and every later bar changes nothing (the inputs are as of the prior close)",
      np.allclose(a1[list(L.OB_ALPHA_COLS)].to_numpy(float), a2[list(L.OB_ALPHA_COLS)].to_numpy(float), equal_nan=True)
      and a1[list(L.OB_ALPHA_COLS)].notna().sum().sum() > 40)
td = L.ob_alpha_today({k: v.loc[:idx[399]] for k, v in P.items()}, ["S05", "S11"])
check("today's inputs (the panel ending at the prior close) = the training inputs for the same gap day",
      np.allclose(td.loc[["S05", "S11"], list(L.OB_ALPHA_COLS)].to_numpy(float),
                  a1[list(L.OB_ALPHA_COLS)].to_numpy(float), atol=1e-6, equal_nan=True),
      (td.iloc[:, :5], a1.iloc[:, 2:7]))
rows_ = pd.DataFrame({"ticker": ["S05"] * 3 + ["S11"] * 2 + ["S20"], "date": [gd] * 6, "m": [5, 15, 30, 5, 15, 5], "x": range(6)})
att = L.ob_attach_alphas(rows_, a1)
check("attached to every opening range of the gap day, order kept; a day without inputs gets blanks",
      list(att["x"]) == list(range(6)) and np.allclose(att.loc[0, "al_a24"], att.loc[2, "al_a24"])
      and att.loc[5, list(L.OB_ALPHA_COLS)].isna().all() and L.ob_has_alphas(att))

print("PCA and the selection")
n = 3000
f1, f2 = rng.normal(size=(n, 1)), rng.normal(size=(n, 1))
load = rng.normal(size=(2, len(L.OB_ALPHA_COLS)))
Am = (np.hstack([f1, f2]) @ load + 0.15 * rng.normal(size=(n, len(L.OB_ALPHA_COLS)))).astype(np.float32)
p = L.ob_pca_fit(Am)
check("two factors behind 34 inputs: two components explain 80%+", p["k"] == 2 and p["evr"][:2].sum() > 0.8, p["evr"][:4])
check("components applied to new rows use the training mean and loadings",
      np.allclose(L.ob_pca_apply(p, Am[:5]), (Am[:5] - p["mu"]) @ p["V"].T, atol=1e-4))
Au = rng.uniform(-0.5, 0.5, size=(n, len(L.OB_ALPHA_COLS))).astype(np.float32)
ju = 7
pu = 0.15 + 2.0 * Au[:, ju] ** 2                         # U-shaped: both extremes win, the middle doesn't
Yu = np.stack([(rng.random(n) < pu).astype(float), (rng.random(n) < pu).astype(float)], 1)
s = L.ob_select_fit(Au, Yu)
check("mutual information picks a U-shaped alpha a correlation would miss (AUC near 0.5)",
      s["mi"].argmax() == ju and abs(L.ml_auc(Yu[:, 0], Au[:, ju]) - 0.5) < 0.05 and ju in s["idx"] and len(s["idx"]) == L.OB_SELECT_K,
      (s["mi"].argmax(), L.ml_auc(Yu[:, 0], Au[:, ju])))

print("walk-forward with the alpha inputs")
n = 4000
dts = np.sort(rng.choice(pd.bdate_range("2021-01-04", periods=900), n))
xs = rng.normal(size=(n, len(L.OB_STATIC))).astype(np.float32)
fac = rng.normal(size=(n, 3))
Aw = fac @ rng.normal(size=(3, len(L.OB_ALPHA_COLS))) + rng.normal(size=(n, len(L.OB_ALPHA_COLS)))
Aw = (pd.DataFrame(Aw).rank(pct=True).to_numpy() - 0.5).astype(np.float32)
j24 = list(L.OB_ALPHA_COLS).index("al_a24")
pw = 1 / (1 + np.exp(-(6.0 * Aw[:, j24] - 1.0)))


def mkrows(pwin, alphas):
    r = pd.DataFrame({f"x_{k}": xs[:, j] for j, k in enumerate(L.OB_STATIC)})
    for j, c in enumerate(L.OB_ALPHA_COLS):
        r[c] = alphas[:, j]
    r["date"], r["ticker"], r["m"] = pd.to_datetime(dts), [f"T{i % 50}" for i in range(n)], 15
    wi, ws = (rng.random(n) < pwin).astype(float), (rng.random(n) < pwin).astype(float)
    r["intra_win"], r["swing_win"] = wi, ws
    r["intra_R"], r["swing_R"] = np.where(wi == 1, 2.0, -1.0), np.where(ws == 1, 2.0, -1.0)
    return r


rows = mkrows(pw, Aw)
seqs = rng.normal(size=(n, L.OB_L, len(L.OB_CH))).astype(np.float32)
wf = L.ob_walk_forward(rows, seqs, use_nn=False)
V = L.ob_score_variants(rows, wf)
sc = L.ob_score(rows, wf).set_index("head")
g = V[(V["model"] == "gbm") & (V["head"] == "intra")].set_index("inputs")
check("all four input sets run; without alphas the trees see nothing (AUC ~0.5), with every alpha they find it (> 0.7)",
      wf["variants"] == list(L.OB_VARIANTS) and abs(g.at["base", "auc"] - 0.5) < 0.05 and g.at["alphas", "auc"] > 0.7,
      g[["auc", "R", "t_vs_base"]])
check("every alpha set: ADDS INFORMATION (beats the same trees without alphas, both halves, BH q <= 0.10)",
      g.at["alphas", "status"] == "ADDS INFORMATION" and g.at["alphas", "q_vs_base"] <= 0.10 and g.at["select", "status"] == "ADDS INFORMATION",
      g[["status", "t_vs_base", "q_vs_base"]])
check("the verdict moves to the trees with alphas, and names the model today's odds come from",
      sc.loc["intra", "verdict"].startswith("USE THE TREES +") and sc.loc["intra", "use"].startswith("gbm.")
      and sc.loc["intra", "alphas"] == "ADDS INFORMATION" and L.ob_use_map(sc.reset_index())[(15, "intra")] == sc.loc["intra", "use"],
      sc[["verdict", "use", "alphas", "alphas_best"]])
imp = L.ob_importance(wf)
gi = imp[(imp["model"] == "gbm") & (imp["head"] == "intra")]
check("permutation importance: the planted alpha first, helping in every test block; the selection kept it in every fold",
      gi["feature"].iloc[0] == "al_a24" and gi["blocks_helped"].iloc[0] == gi["blocks"].iloc[0]
      and gi["selected_folds"].iloc[0] == len(wf["folds"]) and "Conditional fade" in gi["input"].iloc[0], gi.head(3))
f1_ = L.ob_folds(rows["date"], 6)[0]
pf = L.ob_pca_fit(L.ob_alpha_mat(rows.iloc[f1_["train"]]))
fr = wf["fits"]
check("the PCA inside each fold is fit on that fold's training rows only",
      int(fr[(fr["fold"] == 1) & (fr["variant"] == "pca")]["pca_k"].iloc[0]) == pf["k"]
      and abs(float(fr[(fr["fold"] == 1) & (fr["variant"] == "pca")]["pca_explained"].iloc[0]) - float(np.cumsum(pf["evr"])[pf["k"] - 1])) < 1e-5)
ev_, ld_ = L.ob_pca_describe(rows)
check("the PCA table: three factors behind the alphas show as the first three components", len(ld_) >= 3
      and ev_["explains"].iloc[:3].sum() > ev_["explains"].iloc[3:6].sum() * 3 and "loads on" in ld_, ev_.head(5))

print("noise in the alphas")
pz = 1 / (1 + np.exp(-(1.4 * xs[:, list(L.OB_STATIC).index("pace")] - 1.0)))
Az = (rng.uniform(-0.5, 0.5, size=(n, len(L.OB_ALPHA_COLS)))).astype(np.float32)
rz = mkrows(pz, Az)
wz = L.ob_walk_forward(rz, seqs, use_nn=False)
Vz = L.ob_score_variants(rz, wz)
sz = L.ob_score(rz, wz).set_index("head")
check("random alphas never ADD INFORMATION; the verdict stays with the trees on the break inputs",
      not (Vz["status"] == "ADDS INFORMATION").any() and sz.loc["intra", "verdict"] == "USE THE TREES"
      and sz.loc["intra", "use"] == "gbm", (Vz[Vz["inputs"] != "base"][["head", "inputs", "auc", "t_vs_base", "status"]], sz["verdict"]))
check("q-values are there for every comparison with alphas, within 0..1",
      Vz.loc[Vz["inputs"] != "base", "q_vs_base"].between(0, 1).all())
wb = L.ob_walk_forward(rz.drop(columns=list(L.OB_ALPHA_COLS)), seqs, use_nn=False)
check("trades without alpha inputs: the base inputs only, with the original column names",
      wb["variants"] == ["base"] and set(wb["oos"].columns) == {f"{p_}{w}_{h}" for p_ in ("", "sel_") for w in ("nn", "gbm")
                                                                  for h in L.OB_HEADS} | {"fold"}
      and "alphas" not in L.ob_score(rz, wb))

print("the saved models and today's odds")
fin = L.ob_fit_final(rows, seqs, use_nn=TORCH, variants=L.OB_VARIANTS)
check("the final models: base plus every alpha input set, each with its own components or selection",
      set(fin["variants"]) == {"alphas", "pca", "select"} and "pca" in fin["variants"]["pca"]["fit"]
      and len(fin["variants"]["select"]["fit"]["select"]["idx"]) == L.OB_SELECT_K and "intra" in fin["variants"]["alphas"]["gbm"])
if TORCH:
    ent = fin["variants"]["alphas"]
    check("the alpha networks save as numpy and restore", isinstance(next(iter(ent["nn"]["state"].values())), np.ndarray)
          and L.ob_restore_nn(ent) is not None and int(ent["nn"]["n_static"]) == len(L.OB_STATIC) + len(L.OB_ALPHA_COLS))
dbars = {t: L._demo_daily(t, 600) for t in ["AAA", "BBB", "CCC", "SPY"]}
Pd = L.panel_from_bars(dbars)
Pd = {k: Pd[k] for k in ("open", "high", "low", "close", "volume")}
tday = Pd["close"].index[-1].date()
cl = L.ObDemoClient(Pd)
Pp = {k: v.iloc[:-1] for k, v in Pd.items()}
opens = {t: float(Pd["open"][t].iloc[-1]) for t in ["AAA", "BBB"]}
at_ = pd.DataFrame(rng.uniform(-0.5, 0.5, (2, len(L.OB_ALPHA_COLS))), index=["AAA", "BBB"], columns=list(L.OB_ALPHA_COLS))
use = {(5, "intra"): "gbm.alphas", (5, "swing"): "gbm", (15, "intra"): "gbm.pca"}
tdy = L.ob_today(cl, Pp, ["AAA", "BBB"], tday, opens, 0.0, fin, (5, 15), alpha_today=at_, use=use)
brk = tdy[tdy["status"].astype(str).str.startswith("broke")]
ok_ = len(brk) > 0
if ok_:
    r0 = brk.iloc[0]
    t0, m0 = r0["ticker"], int(r0["m"])
    mb = cl.minute(t0, tday)
    br = L.ob_break(mb, tday, m0)
    ctx = L.ob_context_today(Pp, [t0], tday, opens)
    st_, sq = L.ob_features(mb, tday, br, {**ctx.loc[t0].to_dict(), "mkt_gap": 0.0})
    xb = np.array([[st_[k] for k in L.OB_STATIC]], np.float32)
    a_ = at_.loc[[t0]].to_numpy(np.float32)
    u_ = use.get((m0, "intra"))
    if u_:
        w_, _, v_ = u_.partition(".")
        ent = fin["variants"][v_]
        exp_p = L.ml_gbm_predict(ent["gbm"]["intra"], L.ob_variant_X(xb, a_, v_, ent["fit"]))[0]
        ok_ = abs(r0["best_intra"] - exp_p) < 1e-9 and r0["best_intra_by"] == L.ob_use_label(u_)
    if m0 == 5:
        ok_ = ok_ and abs(r0["best_swing"] - r0["gbm_swing"]) < 1e-12
check("today: the recommended model's odds per range and head (alpha models fed today's inputs), the composite shown",
      ok_ and "alpha_composite" in tdy and tdy["alpha_composite"].between(0, 1).all(), tdy.head(4).T if len(tdy) else tdy)
check("no recommendation for a range and head: no best odds", ("best_swing" not in tdy) or tdy.loc[tdy["m"] == 15, "best_swing"].isna().all())
check("labels: alpha numbers carry the engine's descriptions", L.ob_alpha_label("al_a4").startswith("#4 Low-rank")
      and L.ob_alpha_label("al_cat_MRV") == "Mean reversion (category)" and L.ob_use_label("nn.pca") == "network + alpha components (PCA)")

if TORCH:
    print("the network with alphas")
    wn = L.ob_walk_forward(rows.iloc[:2500].reset_index(drop=True), seqs[:2500], use_nn=True, variants=["base", "alphas"])
    Vn = L.ob_score_variants(rows.iloc[:2500].reset_index(drop=True), wn)
    nn_ = Vn[(Vn["model"] == "nn") & (Vn["head"] == "intra")].set_index("inputs")
    check("the network finds the planted alpha too (AUC > 0.65 with alphas, ~0.5 without), with importance rows",
          nn_.at["alphas", "auc"] > 0.65 and abs(nn_.at["base", "auc"] - 0.5) < 0.07
          and (wn["perm"]["model"] == "nn").any(), nn_[["auc", "t_vs_base"]])

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
