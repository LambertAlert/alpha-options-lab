"""Planted-case tests for Stocks > Process plinko: the states (eligibility floors, Stage 2 by hand, leadership with a
leading group, the location and trigger priorities, the episode states), a Luk-style outcome by hand (a day-1 cut, a
run to 2R+, a stop on day 1), the funnel's counts adding up (nodes = eligible name-days, edges = the next row's
nodes, ring shares = 1), the best paths (a planted good path first, t 2+, thin paths dropped), one name's episodes and
moves, the charts building, and no manufactured edge on a random walk.
Run: python test_pk.py"""
import os
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
os.environ["LAB_PV_CACHE"] = tempfile.mkdtemp(prefix="pk_test_")
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


def gbm_panel(n_days=700, n_names=30, seed=1, cheap=()):
    g = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n_days)
    cols = [f"T{i:02d}" for i in range(n_names)]
    mu = np.linspace(-0.0005, 0.0015, n_names)
    ret = g.normal(mu, 0.018, (n_days, n_names))
    C = 50 * np.exp(np.cumsum(ret, axis=0))
    for j in cheap:
        C[:, j] = C[:, j] / C[:, j].max() * 6          # always under $10
    O = C * np.exp(g.normal(0, 0.004, C.shape))
    H = np.maximum(O, C) * (1 + np.abs(g.normal(0, 0.008, C.shape)))
    Lo = np.minimum(O, C) * (1 - np.abs(g.normal(0, 0.008, C.shape)))
    V = g.lognormal(14.5, 0.4, C.shape)                  # ~2M shares: $100M a day at $50
    f = lambda a: pd.DataFrame(a, index=idx, columns=cols)
    return {"open": f(O), "high": f(H), "low": f(Lo), "close": f(C), "volume": f(V)}


PLAN = L.sim_plan_of({})


def at(df, mask):
    """The values of df where mask holds (pandas 3 keeps NaN in stack)."""
    return pd.Series(df.to_numpy()[np.asarray(mask, bool)])
print("States")
P = gbm_panel(cheap=(3,))
S = L.pk_states(P, {"near_atr": 1.0, "ext_atr": 3.0})
allowed = {"trend": {"", "s2", "s13", "s4"}, "lead": {"", "lg", "rs", "no", "new"}, "loc": {"", "pocket", "near", "above", "below", "ext"},
           "trig": {"", "pp", "ledger", "m30", "none"}, "epi": {"", "broken", "pullback", "base", "breakout", "extended"}}
check("codes are the listed ones", all(set(np.unique(S[k].to_numpy())) <= v for k, v in allowed.items()),
      {k: set(np.unique(S[k].to_numpy())) - v for k, v in allowed.items()})
check("a name under $10 is never eligible", (S["trend"]["T03"] == "").all())
check("no eligibility in the warm-up", (S["trend"].iloc[:L.LG_WARMUP] == "").all().all())
check("blank in one row = blank in all", all(((S[k] == "") == (S["trend"] == "")).all().all() for k in allowed))
C = P["close"]
s50, s150 = C.rolling(50).mean(), C.rolling(150).mean()
d, t = C.index[600], "T25"
hand = (C.loc[d, t] > s150.loc[d, t]) and (s150.loc[d, t] > s150[t].shift(20).loc[d]) and (s50.loc[d, t] > s150.loc[d, t])
check("Stage 2 by hand", (S["trend"].loc[d, t] == "s2") == hand, (S["trend"].loc[d, t], hand))
e = S["trend"] != ""
s4_hand = (C < s150) & (s150 < s150.shift(20))
check("Stage 4 = under a falling 150-day; the rest of 'not Stage 2' is Stage 1 or 3",
      (at(S["trend"], e_ := (S["trend"] != "")) != "").all() and (at(S["trend"], e_ & s4_hand) == "s4").all()
      and (at(S["trend"], e_ & ~s4_hand & (S["trend"] != "s2")) == "s13").all() and (S["trend"] == "s4").sum().sum() > 100)
check("Stage 2 is common on the up-drift names, rare on the down-drift ones",
      (S["trend"].iloc[:, 25:] == "s2").sum().sum() / e.iloc[:, 25:].sum().sum() > 0.5 >
      (S["trend"].iloc[:, :3] == "s2").sum().sum() / max(e.iloc[:, :3].sum().sum(), 1), "")
rs = L.lg_rs_rating(C)
ind = pd.DataFrame(np.where(np.arange(30) % 2 == 0, 90.0, 20.0)[None, :].repeat(len(C), 0), index=C.index, columns=C.columns)
S2 = L.pk_states(P, {}, ind_rs=ind)
m = (S2["lead"] != "") & (rs >= 80)
even = np.arange(30) % 2 == 0
check("RS 80+ in a leading group = lg, else rs",
      (at(S2["lead"].iloc[:, even], m.iloc[:, even]) == "lg").all() and (at(S2["lead"].iloc[:, ~even], m.iloc[:, ~even]) == "rs").all())
check("RS under 80 = no", (at(S2["lead"], (S2["lead"] != "") & (rs < 80)) == "no").all())
pk = (S["ext8"] >= -3) & (S["ext8"] <= 6) & (L.pv_ema8w(C)[0] > L.pv_ema8w(C)[1])
check("extended wins the location: 3+ ATR over the 21-day is never called the pocket", (at(S["loc"], e & (S["d21"] >= 3)) == "ext").all())
check("then the 8-week pocket (pocket before near)", (at(S["loc"], pk & e & ~(S["d21"] >= 3)) == "pocket").all())
rest = e & S["loc"].isin(["above", "below"])
check("what is left splits at the 21-day: above it (never 3+ ATR) or below it",
      (at(S["d21"], rest & (S["loc"] == "above")) > 0).all() and (at(S["d21"], rest & (S["loc"] == "above")) < 3).all()
      and (at(S["d21"], rest & (S["loc"] == "below")) <= 0).all() and (S["loc"] == "above").sum().sum() > 100
      and (S["loc"] == "below").sum().sum() > 100)
Plv = gbm_panel(seed=4)                                    # a quiet name: 6% over the 8-week EMA is more than 3 ATR
for k_ in ("open", "high", "low", "close"):
    Plv[k_] = Plv[k_].copy()
g_ = np.random.default_rng(2)
cq = 60 * np.exp(np.cumsum(g_.normal(0.0012, 0.004, len(Plv["close"]))))
Plv["close"]["T00"], Plv["open"]["T00"] = cq, cq * 0.999
Plv["high"]["T00"], Plv["low"]["T00"] = cq * 1.003, cq * 0.996
Slv = L.pk_states(Plv, {})
q_ext = ((Slv["d21"]["T00"] >= 3) & (Slv["trend"]["T00"] != ""))
check("a quiet name 3+ ATR over the 21-day reads extended, not pocket", q_ext.sum() > 5 and (Slv["loc"]["T00"][q_ext] == "ext").all(),
      (int(q_ext.sum()), Slv["loc"]["T00"][q_ext].value_counts().to_dict()))
Py = gbm_panel(seed=6)
for k_ in Py:
    Py[k_] = Py[k_].copy()
    Py[k_].iloc[:len(Py[k_]) - 200, 0] = np.nan           # T00 has 200 sessions of history
Sy = L.pk_states(Py, {})
ey = Sy["trend"]["T00"] != ""
check("a name with under a year of history: its own node, not RS under 80", ey.sum() > 0 and (Sy["lead"]["T00"][ey] == "new").all(),
      Sy["lead"]["T00"][ey].value_counts().to_dict())
la, ma_ = np.zeros(C.shape, bool), np.zeros(C.shape, bool)
r_, c_ = np.nonzero(e.to_numpy())
pick = np.random.default_rng(0).choice(len(r_), 400, replace=False)
la[r_[pick[:200]], c_[pick[:200]]] = True
ma_[r_[pick[100:300]], c_[pick[100:300]]] = True
led, m30 = pd.DataFrame(la, index=C.index, columns=C.columns), pd.DataFrame(ma_, index=C.index, columns=C.columns)
S3 = L.pk_states(P, {}, ledger_sig=led, m30_sig=m30)
tg = S3["trig"].to_numpy()
pp = (S3["trig"] == "pp").to_numpy()
both = led.to_numpy() & m30.to_numpy() & ~pp
check("trigger priority: ledger over 30-min", (tg[both] == "ledger").all() and both.sum() >= 90, both.sum())
only_m = m30.to_numpy() & ~led.to_numpy() & ~pp
check("a 30-min trigger alone shows as m30", (tg[only_m] == "m30").all() and only_m.sum() > 50)
check("no ledger or 30-min trigger without a planted one", not ((tg == "ledger") & ~led.to_numpy()).any()
      and not ((tg == "m30") & ~m30.to_numpy()).any())
ep = S["epi"]
check("episode: extended wins", (at(ep, e & (S["d21"] >= 3)) == "extended").all())
brk = C >= C.rolling(20).max()
check("episode: a new 20-day closing high (not extended) = breakout", (at(ep, e & brk & (S["d21"] < 3)) == "breakout").all())
check("episode: under the 50-day and nothing else = broken",
      (at(ep, e & (C < s50) & ~brk & (S["d21"] < 3) & ~S["loc"].isin(["pocket", "near"])) == "broken").all())

print("Outcome by hand")
n = 320
idx = pd.bdate_range("2024-01-01", periods=n)
base = {"open": np.full(n, 100.0), "high": np.full(n, 101.0), "low": np.full(n, 99.0), "close": np.full(n, 100.0)}


def one(mod):
    a = {k: v.copy() for k, v in base.items()}
    mod(a)
    df = {k: pd.DataFrame({"X": v}, index=idx) for k, v in a.items()}
    df["volume"] = pd.DataFrame({"X": np.full(n, 1e6)}, index=idx)
    return df


d0 = 290


def cut(a):                                    # signal day d0 (low 99 = 0.5 ATR), day 1 opens 100, closes 99.6
    a["open"][d0 + 1], a["high"][d0 + 1], a["low"][d0 + 1], a["close"][d0 + 1] = 100.0, 100.5, 99.5, 99.6


O1 = L.pk_outcomes(one(cut), idx[[d0]], PLAN, hold=20, cost_bp=10)
r1, c1 = O1["r"][d0, 0], O1["code"][d0, 0]
check("day 1 closes under the entry: cut at the close", c1 == "cut" and abs(r1 - (-0.4 - 0.2)) < 0.03, (c1, r1))   # 10 bp a side = 0.2R


def run_up(a):
    for k in range(1, 26):
        p = 100 + 1.0 * k
        a["open"][d0 + k], a["high"][d0 + k], a["low"][d0 + k], a["close"][d0 + k] = p - 0.6, p + 0.3, p - 0.8, p
    for k in range(26, n - d0):
        a["open"][d0 + k], a["high"][d0 + k], a["low"][d0 + k], a["close"][d0 + k] = 110, 110.5, 109, 110


O2 = L.pk_outcomes(one(run_up), idx[[d0]], PLAN, hold=20)
check("a steady run: 2R+ = ran", O2["code"][d0, 0] == "run" and O2["r"][d0, 0] >= 2, (O2["code"][d0, 0], O2["r"][d0, 0]))


def stop1(a):
    a["open"][d0 + 1], a["high"][d0 + 1], a["low"][d0 + 1], a["close"][d0 + 1] = 100.0, 100.2, 98.0, 98.5


O3 = L.pk_outcomes(one(stop1), idx[[d0]], PLAN, hold=20)
check("stopped on day 1 = cut, -1R less costs", O3["code"][d0, 0] == "cut" and -1.25 < O3["r"][d0, 0] < -1.15, (O3["code"][d0, 0], O3["r"][d0, 0]))
check("only the asked days get a trade", np.isfinite(O3["r"]).sum() == 1)
n_long = 480
idxL = pd.bdate_range("2023-06-01", periods=n_long)
upL = {k: np.full(n_long, v) for k, v in (("open", 100.0), ("high", 101.0), ("low", 99.0), ("close", 100.0))}
for k in range(1, n_long - 300):
    p_ = 100 + 1.0 * k
    upL["open"][300 + k], upL["high"][300 + k], upL["low"][300 + k], upL["close"][300 + k] = p_ - 0.6, p_ + 0.3, p_ - 0.8, p_
dfL = {k: pd.DataFrame({"X": v}, index=idxL) for k, v in upL.items()}
dfL["volume"] = pd.DataFrame({"X": np.full(n_long, 1e6)}, index=idxL)
O5 = L.pk_outcomes(dfL, idxL[[300]], PLAN, hold=20)
check("the time limit holds after a trim: out by session 20 of a 170-session run", O5["code"][300, 0] == "run" and 5 < O5["r"][300, 0] < 20,
      (O5["code"][300, 0], O5["r"][300, 0]))
O4 = L.pk_outcomes(one(run_up), idx[[d0]], PLAN, hold=60)
check("a trade still open at the data's end has no outcome", O4["code"][d0, 0] == "" and not np.isfinite(O4["r"][d0, 0]))

print("Funnel")
days = C.index[-400:]
O_ = L.pk_outcomes(P, days, PLAN, hold=40)
Fh = L.pk_flows(S, O_, days)
D, N, Ed = Fh["D"], Fh["nodes"], Fh["edges"]
n_elig = int((S["trend"].loc[days] != "").sum().sum())
check("one record per eligible name-day", len(D) == n_elig, (len(D), n_elig))
check("each row's nodes add up to the name-days", all(N[N["row"] == r_]["n"].sum() == n_elig for r_ in ("trend", "lead", "loc", "trig")))
for a_, b_ in zip(Fh["seq"][:3], Fh["seq"][1:4]):
    sub = Ed[(Ed["from_row"] == a_) & (Ed["to_row"] == b_)]
    ok_in = all(sub[sub["to"] == cd]["n"].sum() == N[(N["row"] == b_) & (N["code"] == cd)]["n"].iloc[0] for cd in sub["to"].unique())
    ok_out = all(sub[sub["from"] == cd]["n"].sum() == N[(N["row"] == a_) & (N["code"] == cd)]["n"].iloc[0] for cd in sub["from"].unique())
    check(f"edges {a_} -> {b_} conserve name-days", ok_in and ok_out)
fin = D[D["out"] != ""]
check("outcome nodes = the finished trades", N[N["row"] == "out"]["n"].sum() == len(fin) and len(fin) > 0.5 * len(D), (len(fin), len(D)))
tn = N[(N["row"] == "trend") & (N["code"] == "s2")].iloc[0]
check("node E[R] = mean R of its trades", abs(tn["er"] - fin[fin["trend"] == "s2"]["r"].mean()) < 1e-9)
check("ring shares add to 1", np.allclose(N[N["trades"] > 0][[f"p_{o}" for o in L.PK_OUT]].sum(axis=1), 1.0))
check("ran = R 2+, held = under 2", (fin[fin["out"] == "run"]["r"] >= 2).all() and (fin[fin["out"] == "held"]["r"] < 2).all())
Ft = L.pk_flows(S, None, pd.DatetimeIndex([C.index[-1]]))
check("today's funnel: one record per eligible name", len(Ft["D"]) == int((S["trend"].iloc[-1] != "").sum()) and "out" not in Ft["seq"])
kk = S["trend"].astype(str) + "|" + S["lead"].astype(str) + "|" + S["loc"].astype(str) + "|" + S["trig"].astype(str)
arr_hand = ((kk != kk.shift(1).fillna("")) & (S["trend"] != "")).loc[days]
check("arrivals: the day a name's route changes (or it becomes eligible)", int(D["arr"].sum()) == int(arr_hand.sum().sum())
      and 0 < D["arr"].mean() < 1, (int(D["arr"].sum()), int(arr_hand.sum().sum())))

print("Best paths")
g = np.random.default_rng(5)
dts = pd.bdate_range("2024-01-01", periods=150)
rows = []
for k in range(300):
    rows.append({"trend": "s2", "lead": "lg", "loc": "pocket", "trig": "pp", "date": dts[k % 150], "ticker": f"A{k % 7}",
                 "r": g.normal(0.8, 1.0), "out": "x"})
for k in range(300):
    rows.append({"trend": "no", "lead": "no", "loc": "ext", "trig": "none", "date": dts[k % 150], "ticker": f"B{k % 7}",
                 "r": g.normal(-0.1, 1.0), "out": "x"})
for k in range(12):
    rows.append({"trend": "s2", "lead": "rs", "loc": "mid", "trig": "none", "date": dts[k], "ticker": "C", "r": 5.0, "out": "x"})
Dp = pd.DataFrame(rows)
Pp = L.pk_paths(Dp, min_n=30)
check("the planted good path ranks first", len(Pp) == 2 and Pp.iloc[0][["trend", "lead", "loc", "trig"]].tolist() == ["s2", "lg", "pocket", "pp"])
check("its t is 2+ and the poor path's isn't", Pp.iloc[0]["t"] > 2 and Pp.iloc[1]["t"] < 2, Pp["t"].tolist())
check("a 12-trade path is dropped at min 30", not (Pp["loc"] == "mid").any())
check("q is there and no larger than 1; the good path clears 0.10", Pp["q"].between(0, 1).all() and Pp.iloc[0]["q"] <= 0.10, Pp["q"].tolist())
park = pd.DataFrame({"trend": "s2", "lead": "lg", "loc": "pocket", "trig": "pp", "date": np.tile(dts, 2),
                     "ticker": np.repeat(["P1", "P2"], 150), "r": 1.0, "out": "x"})
park["arr"] = False
park.loc[park.groupby("ticker").cumcount() % 30 == 0, "arr"] = True        # each name lands on the path 5 times, then sits
Pk = L.pk_paths(park, min_n=1, min_dates=1)
check("a parked name counts once per arrival, not once per day", int(Pk.iloc[0]["trades"]) == 10, Pk[["trades", "dates"]].to_dict("records"))
few = Dp[Dp["date"].isin(dts[:40])]
check("a path on under 60 dates isn't ranked", len(L.pk_paths(few, min_n=30)) == 0 and len(L.pk_paths(few, min_n=30, min_dates=30)) == 2)

print("One name")
s = pd.Series(["", "base", "base", "breakout", "extended", "extended", "pullback", "pullback", "breakout", "extended", "broken"],
              index=pd.bdate_range("2025-01-01", periods=11))
R = pd.Series(np.arange(11, dtype=float), index=s.index)
code = pd.Series(["", "held", "", "run", "cut", "", "run", "", "held", "cut", "cut"], index=s.index)
E = L.pk_episodes(s, R, code)
check("episodes collapse runs", E["state"].tolist() == ["base", "breakout", "extended", "pullback", "breakout", "extended", "broken"]
      and E["days"].tolist() == [2, 1, 2, 2, 1, 1, 1])
check("each episode's trade is its first day's", E["r"].tolist() == [1, 3, 4, 6, 8, 9, 10] and E["out"].tolist()[:3] == ["held", "run", "cut"])
G = L.pk_name_graph(E)
mv = G["edges"].set_index(["state", "next"])["n"]
check("moves counted", mv[("breakout", "extended")] == 2 and mv[("extended", "pullback")] == 1 and mv[("extended", "broken")] == 1)
check("shares out of a state add to 1", np.allclose(G["edges"].groupby("state")["share"].sum(), 1.0))
nd = G["nodes"].set_index("state")
check("node stats", nd.loc["breakout", "episodes"] == 2 and nd.loc["breakout", "er"] == 5.5 and nd.loc["extended", "p_cut"] == 1.0)

print("Charts")
try:
    L.pk_funnel_chart(Ft, Fh, "t").to_dict()
    L.pk_funnel_chart(Fh, Fh, "t").to_dict()
    L.pk_name_chart(G, "extended", "X").to_dict()
    L.pk_name_chart({"nodes": pd.DataFrame(), "edges": pd.DataFrame()}, "", "X").to_dict()
    check("funnel and name charts build (with empty inputs too)", True)
except Exception as ex:
    check("funnel and name charts build (with empty inputs too)", False, repr(ex))

print("Marked names")
day = C.index[-1]
inn = [t_ for t_ in C.columns if S["trend"].at[day, t_] != ""]
t1, t2 = inn[0], inn[1]
mk = [(t_, {r_: S[r_].at[day, t_] for r_ in L.PK_KEYS}) for t_ in (t1, t2)]
pos = L.pk_positions(Fh["seq"])
some = L.pk_positions(Fh["seq"], set(Fh["nodes"].set_index(["row", "code"]).index))
check("a node no name-day reached takes no place (the unbuilt triggers, here); the rest keep theirs in order",
      ("trig", "ledger") in pos and ("trig", "ledger") not in some and ("trig", "m30") not in some and ("trig", "none") in some
      and [k for k in some if k[0] == "loc"] == [k for k in pos if k[0] == "loc" and k in some]
      and max(abs(x) for x, _ in some.values()) <= 3.6 + 1e-9, sorted(k for k in pos if k not in some))
ML_, MP_, MLb = L.pk_mark_frames(mk, pos, Fh["seq"])
want = [pos[(r_, mk[0][1][r_])] for r_ in L.PK_KEYS]
got = MP_[MP_["ticker"] == t1][["x", "y"]].to_records(index=False).tolist()
check("a marked name's circles sit on its nodes, one per row", got == want, (got, want))
check("its route runs through the same rows in order", ML_[ML_["ticker"] == t1]["y"].tolist() == [w[1] for w in want])
check("each name gets its own colour", MP_.groupby("ticker")["col"].nunique().eq(1).all() and MP_["col"].nunique() == 2)
check("the ticker label sits at the trigger row", (MLb["txt"] == f"◀ {t1}").any()
      and abs(MLb[MLb["txt"] == f"◀ {t1}"]["y"].iloc[0] - (pos[("trig", mk[0][1]["trig"])][1] + 0.08)) < 1e-9)
same = [(t1, mk[0][1]), ("ZZ", mk[0][1])]
_, MP2, ML2 = L.pk_mark_frames(same, pos, Fh["seq"])
check("names on the same node: rings grow, labels stack", MP2.groupby(["x", "y"])["size"].nunique().eq(2).all()
      and ML2["y"].nunique() == 2)
PA = L.pk_paths(Fh["D"], min_n=1, min_dates=1)
NR = L.pk_name_rows(S, Fh, L.pk_paths(Fh["D"], min_n=30), day, [t1, "T03"], PA)
key = [S[r_].at[day, t1] for r_ in L.PK_KEYS]
g_ = PA[(PA[list(L.PK_KEYS)] == np.array(key, dtype=object)).all(axis=1)]
check("the table gives its route's record in the best-paths table's terms (arrivals, E[R] by date)",
      (len(g_) == 0 and NR.iloc[0]["trades"] == 0) or (NR.iloc[0]["trades"] == g_.iloc[0]["trades"]
                                                       and abs(NR.iloc[0]["er"] - g_.iloc[0]["er_date"]) < 1e-12),
      (NR.iloc[0].to_dict(), len(g_)))
check("an ineligible name is said to be outside the funnel", "not in the funnel" in NR.iloc[1]["route"])
try:
    L.pk_funnel_chart(Ft, Fh, "t", hl=mk[1][1], marks=mk).to_dict()
    check("the funnel builds with names marked", True)
except Exception as ex:
    check("the funnel builds with names marked", False, repr(ex))

print("Random walk")
P0 = gbm_panel(seed=11)
for k in P0:
    pass
g0 = np.random.default_rng(11)
ret = g0.normal(0, 0.018, P0["close"].shape)
C0 = 50 * np.exp(np.cumsum(ret, axis=0))
P0["close"] = pd.DataFrame(C0, index=P0["close"].index, columns=P0["close"].columns)
P0["open"] = P0["close"].shift(1).fillna(P0["close"]) * np.exp(g0.normal(0, 0.003, C0.shape))
P0["high"] = np.maximum(P0["open"], P0["close"]) * (1 + np.abs(g0.normal(0, 0.008, C0.shape)))
P0["low"] = np.minimum(P0["open"], P0["close"]) * (1 - np.abs(g0.normal(0, 0.008, C0.shape)))
S0 = L.pk_states(P0, {})
dd = P0["close"].index[-400:]
F0 = L.pk_flows(S0, L.pk_outcomes(P0, dd, PLAN, hold=40), dd)
fin0 = F0["D"][F0["D"]["out"] != ""]
mu = fin0.groupby("date")["r"].mean()
check("random walk: no edge overall (|E[R]| small after costs)", abs(mu.mean()) < 0.12, mu.mean())
P0t = L.pk_paths(F0["D"], min_n=60)
check("random walk: no path with t 3+", len(P0t) == 0 or (P0t["t"] < 3).all(), P0t[["t", "trades"]].head(3).to_dict("records") if len(P0t) else "")

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
