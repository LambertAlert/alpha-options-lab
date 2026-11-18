"""Planted-case tests for Stockbee's EP 9 million in alpha_options_lab.py. Run: python test_ep9m.py"""
import sys, warnings
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


rng = np.random.default_rng(7)
n, i0 = 400, 300
dates = pd.bdate_range("2024-01-02", periods=n)
spec = {   # name: (price, usual volume, spike volume, spike move, close place in the day's range)
    "A": (20.0, 2e6, 12e6, 0.08, 0.90),    # textbook EP 9M, strong close
    "B": (50.0, 15e6, 16e6, 0.03, 0.90),   # always trades 15M: 9M+ but not unusual
    "C": (20.0, 2e6, 12e6, -0.06, 0.10),   # huge volume, down day
    "D": (2.0, 2e6, 12e6, 0.10, 0.90),     # under $3
    "E": (20.0, 2e6, 8e6, 0.08, 0.90),     # 4x volume but under 9M shares
    "F": (20.0, 2e6, 9.5e6, 0.02, 0.20),   # EP 9M, weak close (bottom of the range, still up on the day)
}
names = list(spec) + ["G", "H"]
O, Hh, Ll, C, V = (np.zeros((n, len(names))) for _ in range(5))
for j, t in enumerate(names):
    px, vol, spk, mv, dcr = spec.get(t, (20.0, 2e6, 0, 0, 0))
    r = rng.normal(0, 0.004, n)
    r[i0] = mv if t in spec else 0.0
    c = px * np.exp(np.cumsum(r))
    c[i0] = c[i0 - 1] * (1 + mv) if t in spec else c[i0]
    rng_ = c * 0.02
    lo, hi = c - rng_ * 0.5, c + rng_ * 0.5
    if t in spec:                                  # place the close at `dcr` of the spike day's range
        hi[i0] = c[i0] + rng_[i0] * (1 - dcr) * 2
        lo[i0] = c[i0] - rng_[i0] * dcr * 2
    vv = vol * rng.uniform(0.9, 1.1, n)
    if t in spec:
        vv[i0] = spk
    O[:, j], Hh[:, j], Ll[:, j], C[:, j], V[:, j] = np.r_[c[0], c[:-1]], hi, lo, c, vv
# G: an EP 9M two sessions before the last bar, then a break over the pivot on the last bar
g = names.index("G")
C[:, g], V[:, g] = 20.0, 2e6
O[:, g], Hh[:, g], Ll[:, g] = 20.0, 20.2, 19.8
O[n - 3, g], Hh[n - 3, g], Ll[n - 3, g], C[n - 3, g], V[n - 3, g] = 20.5, 22.0, 20.4, 21.8, 15e6
O[n - 2, g], Hh[n - 2, g], Ll[n - 2, g], C[n - 2, g], V[n - 2, g] = 21.8, 22.5, 21.5, 22.0, 6e6
O[n - 1, g], Hh[n - 1, g], Ll[n - 1, g], C[n - 1, g], V[n - 1, g] = 22.1, 23.0, 22.0, 22.8, 5e6
# H: an EP 9M three sessions back that fell under its low (a failed pivot)
h_ = names.index("H")
C[:, h_], V[:, h_] = 20.0, 2e6
O[:, h_], Hh[:, h_], Ll[:, h_] = 20.0, 20.2, 19.8
O[n - 4, h_], Hh[n - 4, h_], Ll[n - 4, h_], C[n - 4, h_], V[n - 4, h_] = 20.5, 22.0, 20.4, 21.8, 12e6
for k_ in (n - 3, n - 2, n - 1):
    O[k_, h_], Hh[k_, h_], Ll[k_, h_], C[k_, h_] = 20.3, 20.4, 19.5, 19.9
P = {k: pd.DataFrame(x, index=dates, columns=names) for k, x in
     (("open", O), ("high", Hh), ("low", Ll), ("close", C), ("volume", V))}

print("The signal")
E = L.ep9m_panels(P)
d0 = dates[i0]
check("textbook EP 9M fires", bool(E["sig"].at[d0, "A"]))
check("and counts as a strong close", bool(E["strong"].at[d0, "A"]), E["dcr"].at[d0, "A"])
check("relative volume excludes the EP day itself (12M / ~2M = ~6x)", 5.4 < E["rvol"].at[d0, "A"] < 6.6, E["rvol"].at[d0, "A"])
check("a name that always trades 15M does not fire", not E["sig"]["B"].any(), int(E["sig"]["B"].sum()))
check("a down day does not fire", not bool(E["sig"].at[d0, "C"]))
check("under $3 does not fire", not bool(E["sig"].at[d0, "D"]))
check("under 9M shares does not fire, even at 4x", not bool(E["sig"].at[d0, "E"]))
check("weak close still fires (it closed up on the day)", bool(E["sig"].at[d0, "F"]))
check("but is not a strong close", not bool(E["strong"].at[d0, "F"]), E["dcr"].at[d0, "F"])
check("only the planted days fire", int(E["sig"].to_numpy().sum()) == 4, int(E["sig"].to_numpy().sum()))
cut = {k: x.iloc[: i0 + 1] for k, x in P.items()}
check("no look-ahead: the same reading from data through the EP day",
      bool(L.ep9m_panels(cut)["sig"].iloc[-1]["A"]) and np.isclose(L.ep9m_panels(cut)["rvol"].iloc[-1]["A"], E["rvol"].at[d0, "A"]))

print("The last EP 9M per name")
X = L.ep9m_last(P, 5)
check("G: two sessions ago", X.at["G", "ep9_age"] == 2, X.at["G", "ep9_age"])
check("G: EP day's levels", (X.at["G", "ep9_lo"], X.at["G", "ep9_hi"], X.at["G", "ep9_mid"]) == (20.4, 22.0, 21.2))
check("G: the pivot is the highest high from the EP day to yesterday (not today's)", X.at["G", "ep9_hi_since"] == 22.5,
      X.at["G", "ep9_hi_since"])
check("G: volume and rvol", np.isclose(X.at["G", "ep9_vol_m"], 15.0) and X.at["G", "ep9_rvol"] > 6)
check("names with no EP 9M in the window are blank", X.loc[["A", "B", "C"], "ep9_age"].isna().all())
X20 = L.ep9m_last(P, 120)
check("a longer window finds A's EP", X20.at["A", "ep9_age"] == n - 1 - i0, X20.at["A", "ep9_age"])
check("H: three sessions ago", X.at["H", "ep9_age"] == 3)

print("Brief > Setups")
F = X.copy()
F["last"] = P["close"].iloc[-1]
F["close"] = F["last"]
F["su_dv"], F["bar_date"], F["tf"], F["trend"] = 100.0, str(dates[-1].date()), 1, ""
F["IBD"], F["composite"] = 85.0, 75.0
S = L.su_candidates(F)
ep = S[S["family"] == "EP 9M"].set_index("ticker")
check("G is on the EP 9M scan", "G" in ep.index)
check("G: triggered (the last price is over the pivot)", ep.at["G", "status"] == "trig", ep.at["G", "status"] if "G" in ep.index else "")
check("G: trigger is the pivot, stop is the EP day's low", ep.at["G", "trigger"] == 22.5 and ep.at["G", "stop"] == 20.4)
check("G: points to the ledger setup", ep.at["G", "ledger_id"] in ("ep:9m", "ep:9m_dcr"))
check("H dropped off: back under the EP day's low", "H" not in ep.index)
F2 = F.copy()
F2.loc["G", "ep9_age"] = 0
F2.loc["G", "last"] = 21.8
S2 = L.su_candidates(F2).query("family == 'EP 9M'").set_index("ticker")
check("fired today: trigger is the EP day's high", S2.at["G", "status"] == "today" and S2.at["G", "trigger"] == 22.0)
weak, strong_ = F2.copy(), F2.copy()
weak.loc["G", "ep9_dcr"], strong_.loc["G", "ep9_dcr"] = 0.3, 0.9
sw = L.su_candidates(weak).query("family == 'EP 9M'").iloc[0]
ss_ = L.su_candidates(strong_).query("family == 'EP 9M'").iloc[0]
check("a strong close scores a point higher and maps to ep:9m_dcr",
      ss_["score"] == sw["score"] + 1 and ss_["ledger_id"] == "ep:9m_dcr" and sw["ledger_id"] == "ep:9m")
fade = F.copy()
fade.loc["G", "last"] = 20.6                       # above the EP day's low, under its midpoint
sf = L.su_candidates(fade).query("family == 'EP 9M'").set_index("ticker")
check("giving back more than half the EP day costs a point", sf.at["G", "score"] == ep.at["G", "score"] - 1
      and "gave back" in sf.at["G", "why"])
check("EP 9M is one of the Brief's scans", "EP 9M" in L.SU_FAMILIES and "EP 9M" in L.SU_FAM_COLOR)
Rk = L.su_rank(S, F)
pk = L.sim_brief_pack(Rk, S, str(dates[-1].date()))
gp = next((r for r in pk["rows"] if r["ticker"] == "G"), None)
check("the Simulation hand-off carries G's EP ledger setup", gp is not None and any(x.startswith("ep:") for x in gp["ledger_ids"]),
      gp)

print("Setup ledger")
check("EP family registered", "EP" in L.LG_FAMILIES and L.LG_SETUPS["ep:9m"][0] == "EP" and L.LG_SETUPS["ep:9m"][2] == "day")
check("EP defaults: trail, 5-session limit", L.LG_EXIT_SEED["EP"] == "trail" and L.LG_TL_SEED["EP"] == 5)
check("the strong-close subset is not counted twice in confluence", "ep:9m_dcr" in L.LG_CONFLUENCE_SKIP)
prm = {"mode": "next_open", "win": 1, "tgt": 2.0, "horizon": 10, "cost": 10.0, "cost_mode": "flat", "spread_m": "ar",
       "cooldown": 10, "cap": 3.0, "min_price": 3.0, "min_dv": 1.0, "base_step": 5, "warmup": 60, "tl_mode": "family",
       "tl": 10, "tl_fam": (), "exit_mode": "family", "trail": "chandelier", "trail_k": 3.0, "trail_ma": 21,
       "mark_open": True, "exit_fam": ()}
R = L.lg_run(P, None, None, ("EP",), "12/26/9", prm, "test")
ev = R["ev"]
e9 = ev[ev["setup"] == "ep:9m"].set_index("ticker")
check("ledger: the planted EP days become trades", set(e9.index) == {"A", "F", "G", "H"}, sorted(e9.index))
check("ledger: strong-close trades are A, G and H", set(ev.loc[ev["setup"] == "ep:9m_dcr", "ticker"]) == {"A", "G", "H"},
      sorted(ev.loc[ev["setup"] == "ep:9m_dcr", "ticker"]))
check("ledger: on the EP day", e9.at["A", "date"] == d0)
atr = L._mc_atr(P["high"], P["low"], P["close"], 14).at[d0, "A"]
lo_a, c_a = P["low"].at[d0, "A"], P["close"].at[d0, "A"]
check("ledger: the stop is the EP day's low (or the ATR cap)", abs(e9.at["A", "plan_risk_atr"] - (c_a - lo_a) / atr) < 1e-3,
      (e9.at["A", "plan_risk_atr"], (c_a - lo_a) / atr))
check("ledger: EP trades use the trailing exit and a 5-session limit",
      (e9["exit_rule"] == "trail").all() and (e9["tlimit"] == 5).all(), (list(e9["exit_rule"]), list(e9["tlimit"])))
check("ledger: the signal-day volume ratio is a feature", e9.at["A", "vol_ratio"] > 5)
R10 = L.lg_run(P, None, None, ("EP",), "12/26/9", {**prm, "min_price": 10.0}, "test")
check("ledger: the $10 default floor drops nothing here (all planted names are $20)",
      set(R10["ev"].query("setup == 'ep:9m'")["ticker"]) == {"A", "F", "G", "H"})
check("Expectancy & Kelly has a colour for EP", "EP" in L.EXP_FAMILY_COLOR)

print("Today's brief: movers")
D, mode = L.in_play_table({k: x.iloc[: i0 + 1] for k, x in P.items()}, today=dates[i0].date())
check("movers: last-session mode on the EP day", mode == "last session", mode)
check("movers: A and F carry the EP 9M flag", set(D.index[D["ep9m"]]) == {"A", "F"}, sorted(D.index[D["ep9m"]]))
r_a = pd.Series(D.loc["A"].to_dict() | {"grade": "HIGH", "points": 8, "name": "", "industry": ""})
check("movers: the focus card shows an EP 9M badge", "EP 9M" in L.focus_card_html("A", r_a, {}, "", None, [], []))
r_b = pd.Series(D.loc["B"].to_dict() | {"grade": "LOW", "points": 2, "name": "", "industry": ""})
check("movers: no badge without one", "EP 9M" not in L.focus_card_html("B", r_b, {}, "", None, [], []))

check("EP 9M constants", (L.EP9M_VOL, L.EP9M_RVOL, L.EP9M_MIN_PX, L.EP9M_DCR) == (9e6, 3.0, 3.0, 0.70))

print(f"\n{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
