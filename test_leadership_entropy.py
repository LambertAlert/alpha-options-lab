"""Planted-case tests for the leadership-entropy measures in alpha_options_lab.py. Run: python test_leadership_entropy.py"""
import math, sys, warnings
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


rng = np.random.default_rng(3)
G, per = 10, 30                                     # 10 groups x 30 names; group 0 is three times as big
sizes = [90] + [per] * (G - 1)
names = [f"N{i}" for i in range(sum(sizes))]
grp = pd.Series(np.repeat([f"G{k}" for k in range(G)], sizes), index=names)
dates = pd.bdate_range("2022-01-03", periods=400)


def state_from(leader_mask: np.ndarray) -> dict:
    rs = np.where(leader_mask, 90.0, 40.0)
    return {"rs": pd.DataFrame(rs, index=dates, columns=names), "groups": grp, "rs_min": 80.0}


def leaders_in(groups_w: np.ndarray, n_lead: int, seed: int) -> np.ndarray:
    """Each date, n_lead leaders drawn by group weights (then a random name in that group)."""
    r = np.random.default_rng(seed)
    M = np.zeros((len(dates), len(names)), bool)
    idx_by_g = [np.flatnonzero(grp.to_numpy() == f"G{k}") for k in range(G)]
    for t in range(len(dates)):
        cnt = r.multinomial(n_lead, groups_w)
        for k, c in enumerate(cnt):
            if c:
                M[t, r.choice(idx_by_g[k], min(c, len(idx_by_g[k])), replace=False)] = True
    return M


q = np.array(sizes) / sum(sizes)
print("Concentration and effective groups")
one = np.zeros((len(dates), len(names)), bool)
one[:, :40] = True                                   # every leader in group 0
E1 = L.ga_leadership_entropy(state_from(one))
check("all leaders in one group: effective groups = 1", abs(E1["eff"].iloc[-1] - 1.0) < 1e-9, E1["eff"].iloc[-1])
check("all in one group: concentration = log(1/q0) minus the random-spread bias",
      abs(E1["conc"].iloc[-1] - (math.log(1 / q[0]) - (G - 1) / 80)) < 1e-9, E1["conc"].iloc[-1])
check("all in one group: top-3 share = 1", abs(E1["top3"].iloc[-1] - 1) < 1e-12)
prop = np.zeros((len(dates), len(names)), bool)
for k in range(G):                                   # exactly proportional: a third of every group
    ix = np.flatnonzero(grp.to_numpy() == f"G{k}")
    prop[:, ix[: len(ix) // 3]] = True
E2 = L.ga_leadership_entropy(state_from(prop))
check("proportional leaders: raw KL = 0, so concentration = -(G-1)/2N",
      abs(E2["conc"].iloc[-1] + (G - 1) / (2 * prop[-1].sum())) < 1e-9, E2["conc"].iloc[-1])
check("proportional leaders: effective groups ~ the names' own", abs(E2["eff"].iloc[-1] / E2["eff_names"].iloc[-1] - 1) < 0.05)
R = leaders_in(q, 60, 1)                             # random allocation by size: no real concentration
E3 = L.ga_leadership_entropy(state_from(R))
raw_kl = E3["conc"] + (E3["groups"] - 1) / (2 * E3["N"])
check("random spread: raw KL is biased up", raw_kl.mean() > 0.05, raw_kl.mean())
check("random spread: bias-corrected concentration averages ~0", abs(E3["conc"].mean()) < 0.012, E3["conc"].mean())
U = leaders_in(np.full(G, 1 / G), 40, 2)             # uniform across groups: true H = log(G)
EU = L.ga_leadership_entropy(state_from(U))
plug = np.log(EU["eff"]) - (EU["groups_with"] - 1) / (2 * EU["N"])
check("Miller-Madow is closer to log(G) than the plug-in",
      abs(np.log(EU["eff"]).mean() - math.log(G)) < abs(plug.mean() - math.log(G)), (np.log(EU["eff"]).mean(), plug.mean()))
w_conc = np.array([0.6] + [0.4 / (G - 1)] * (G - 1))
C = leaders_in(w_conc, 60, 3)
E4 = L.ga_leadership_entropy(state_from(C))
check("concentrated spread scores well above random", E4["conc"].mean() > E3["conc"].mean() + 0.1,
      (E4["conc"].mean(), E3["conc"].mean()))
check("concentrated spread has fewer effective groups", E4["eff"].mean() < E3["eff"].mean() - 2)
few = np.zeros((len(dates), len(names)), bool); few[:, :5] = True
check("under 10 leaders: no reading", L.ga_leadership_entropy(state_from(few))["conc"].isna().all())

print("Percentile and regimes")
mix = np.vstack([R[:200], C[200:]])                  # broad first, then concentrated
E5 = L.ga_leadership_entropy(state_from(mix))
check("percentile high once leadership narrows", E5["pct"].iloc[210:260].mean() > 0.8, E5["pct"].iloc[210:260].mean())
cut = {**state_from(mix), "rs": state_from(mix)["rs"].iloc[:250]}
E5c = L.ga_leadership_entropy(cut)
check("percentile uses only the past (no look-ahead)", np.allclose(E5["pct"].iloc[:250], E5c["pct"], equal_nan=True))
reg = L.ga_entropy_regime(pd.Series([0.9, 0.5, 0.1, np.nan]))
check("regime labels", list(reg) == ["Narrow leadership", "Middle", "Broad leadership", "n/a"], list(reg))
T = L.ga_entropy_table(E1)
check("table: group 0 holds every leader", T["group"].iloc[0] == "G0" and T["share_leaders"].iloc[0] == 1.0
      and abs(T["over"].iloc[0] - 1 / q[0]) < 1e-9)

print("Does the rule pay more when leadership is narrow?")
wk = dates[::5]
rows = []
for d in wk:
    narrow = d >= dates[200]
    for j in range(30):
        is_rule = j < 10
        r_ = rng.normal(0.0, 1.0) + (0.6 if (is_rule and narrow) else 0.0)
        rows.append({"date": d, "lead_group": is_rule, "rr_bucket": "R:R 3+" if is_rule else "R:R 2-3", "R": r_})
ev = pd.DataFrame(rows)
tab, gap = L.ga_entropy_edge(ev, E5, h=20)
tn = tab.set_index("regime")
check("narrow regime: rule beats the rest (t > 2)", tn.loc["Narrow leadership", "t"] > 2, tn.to_dict("index"))
check("broad regime: no planted edge", abs(tn.loc["Broad leadership", "diff"]) < 0.3, tn.loc["Broad leadership", "diff"])
check("narrow minus broad is positive and significant", gap["gap"] > 0.3 and gap["gap_t"] > 2, gap)

print("Ledger hooks")
st_full = state_from(mix)
st_full["group_pct"] = pd.DataFrame(rng.random((len(dates), len(names))), index=dates, columns=names)
st_full.update({"rr": st_full["group_pct"] * 0 + 2.0, "rr_bucket": st_full["group_pct"] * 0, "leader": st_full["rs"] >= 80,
                "liquid": st_full["rs"] > -1})
pan = L.ga_ledger_panels(st_full)
check("ledger gets the entropy panels", all(k in pan for k in ("lead_conc", "lead_conc_pct", "lead_eff_groups", "ga_x_lead")))
check("same value for every name on a date", float(pan["lead_conc"].iloc[300].std()) == 0.0)
x = pan["ga_x_lead"].iloc[300].to_numpy(float); gp = st_full["group_pct"].iloc[300].to_numpy(); pc = float(pan["lead_conc_pct"].iloc[300, 0])
check("interaction = (group pct - 0.5)(conc pct - 0.5) x 4", np.allclose(x, (gp - 0.5) * (pc - 0.5) * 4, atol=1e-6))
evl = pd.DataFrame({"lead_conc_pct": [0.9, 0.2, 0.9, np.nan], "ga_gpct": [0.95, 0.95, 0.1, 0.95], "ga_bucket": [0, 0, 0, 0],
                    "ga_leader": [1, 1, 1, 1]})
lab = L.lg_split_col(evl, "ga_rule_lead")
check("ledger split: rule x leadership", list(lab) == ["The rule · narrower leadership than usual",
                                                        "The rule · broader leadership than usual",
                                                        "Other RS leaders · narrower leadership than usual", "n/a"], list(lab))
check("ledger split: regimes", list(L.lg_split_col(evl, "lead_conc"))[:2] == ["Narrow leadership", "Broad leadership"])

print(f"\n{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
