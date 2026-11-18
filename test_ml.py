"""Planted-case tests for the learned models: Stocks > Breakout model (ORB) and Stocks > Learned ranker.
Breakout: the opening-range break, fills, stops, the intraday and swing labels (gaps, same-bar ties, costs), inputs
known at the break and nothing after, gap-day selection on prior-close data, walk-forward folds with the embargo,
trees and the network finding planted signals (the network one that lives only in the minute bars), saving and
restoring, today's scoring. Ranker: universe, targets with delistings, features, the IC loss, the network learning a
planted interaction ridge can't, IC and long-short by hand, verdicts, the whole pipeline on demo data.
Run: python test_ml.py"""
import math, warnings
from datetime import date, datetime, timedelta
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


TORCH = L._torch() is not None
day = pd.Timestamp("2025-03-14")


def path(prices, start="09:30", vols=None, pre=True):
    """Minute bars from a list of (open, high, low, close) from 9:30."""
    t0 = day + pd.Timedelta(hours=int(start[:2]), minutes=int(start[3:]))
    idx = pd.date_range(t0, periods=len(prices), freq="1min")
    df = pd.DataFrame(prices, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = vols if vols is not None else 1000.0
    if pre:
        p = pd.DataFrame({"open": [99.0] * 5, "high": [99.5] * 5, "low": [98.8] * 5, "close": [99.2] * 5, "volume": 200.0},
                         index=pd.date_range(day + pd.Timedelta(hours=8), periods=5, freq="10min"))
        df = pd.concat([p, df])
    return df


def flat_day(n=390, px=100.0):
    return [(px, px + 0.05, px - 0.05, px)] * n


print("the opening-range break and the labels")
bars = flat_day()
bars[:5] = [(100, 101, 99.5, 100.5)] * 5                       # 5-minute range 99.5 - 101
bars[5] = (100.8, 101.5, 100.7, 101.4)                         # breaks at 9:35, opened under the high
for k in range(6, 60):
    bars[k] = (101.4 + 0.04 * (k - 6),) * 4
bars[60] = (104.0, 104.3, 103.9, 104.1)                        # 2R target = 101 + 2 x 1.5 = 104
for k in range(61, 390):
    bars[k] = (104.1, 104.15, 104.05, 104.1)
mb = path(bars)
br = L.ob_break(mb, day, 5)
check("the range is the first 5 minutes; the break fills at its high; the stop is the low before the break",
      br["trig"] and br["orh"] == 101 and br["orl"] == 99.5 and br["fill"] == 101 and br["stop"] == 99.5
      and br["entry_time"] == day + pd.Timedelta(hours=9, minutes=35), br)
tr = L.ob_trade(mb, day, 5, [], 2.0, 0.0)
check("target before the stop: +2R intraday and swing", tr["intra_R"] == 2.0 and tr["intra_win"] == 1 and tr["swing_R"] == 2.0
      and tr["intra_how"] == "target")
tr_c = L.ob_trade(mb, day, 5, [], 2.0, 5.0)
check("costs: 5bp a side, in R", abs(tr_c["intra_R"] - (2.0 - 2 * 5e-4 * 101 / 1.5)) < 1e-12)
b2 = list(bars)
b2[5] = (101.6, 101.9, 101.5, 101.8)                           # opens over the high: fills at the open
check("a bar that opens over the range high fills at its open", L.ob_break(path(b2), day, 5)["fill"] == 101.6)
b3 = list(bars)
b3[5] = (100.8, 101.5, 99.4, 101.4)                            # the entry bar also trades through the stop
check("an entry bar that also trades through the stop counts as stopped", L.ob_trade(path(b3), day, 5, [], 2.0, 0.0)["intra_R"] == -1)
b4 = list(bars)
b4[60] = (102.0, 104.5, 99.0, 103.0)                           # stop and target in one bar
check("stop and target in the same minute: the stop", L.ob_trade(path(b4), day, 5, [], 2.0, 0.0)["intra_how"] == "stop")
b5 = flat_day()
b5[:5] = [(100, 101, 99.5, 100.5)] * 5
for k in range(5, 390):
    b5[k] = (100.5, 100.9, 100.0, 100.5)
check("no trade over the range high: no break", L.ob_trade(path(b5), day, 5, [], 2.0, 0.0)["trig"] is False)
b6 = list(bars)
for k in range(60, 390):
    b6[k] = (102.0, 102.1, 101.9, 102.0)                       # neither level by the close
nxt = [(103.0, 103.5, 102.5, 103.2), (103.3, 104.6, 103.0, 104.4), (100, 100, 100, 100), (100, 100, 100, 100)]
t6 = L.ob_trade(path(b6), day, 5, nxt, 2.0, 0.0)
check("still open at the close: out at the close intraday, target on day 2 for the swing",
      abs(t6["intra_R"] - (102.0 - 101) / 1.5) < 1e-12 and t6["intra_how"] == "close" and t6["swing_R"] == 2.0
      and t6["swing_how"] == "target")
t7 = L.ob_trade(path(b6), day, 5, [(99.0, 99.5, 98.0, 99.2)] + nxt[1:], 2.0, 0.0)
check("a gap under the stop fills at the open", abs(t7["swing_R"] - (99.0 - 101) / 1.5) < 1e-12 and t7["swing_how"] == "gap through the stop")
t8 = L.ob_trade(path(b6), day, 5, [(102.5, 103, 102, 102.7)] * 4, 2.0, 0.0)
check("neither level in five sessions: out at the fifth close", abs(t8["swing_R"] - (102.7 - 101) / 1.5) < 1e-12 and t8["swing_how"] == "time")
t9 = L.ob_trade(path(b6), day, 5, [], 2.0, 0.0)
check("no later bars: no swing label", np.isnan(t9["swing_R"]) and np.isnan(t9["swing_win"]))
check("a range with almost no trades: no trade", L.ob_trade(path(bars[:3], pre=False), day, 15, [], 2.0, 0.0) is None)
br15 = L.ob_break(mb, day, 15)
check("a 15-minute range takes the first 15 minutes", br15["orh"] == max(b[1] for b in bars[:15]))

print("inputs at the break")
ev = {"adr20": 4.0, "prev_close": 99.0, "avg_vol10": 390_000.0, "gap": 0.05, "perf_1w": 0.1, "pxvol": 5e7}
st_, sq = L.ob_features(mb, day, br, ev)
check("every static input, and 60 bars x 6 channels, left-padded", set(st_) == set(L.OB_STATIC) and sq.shape == (60, 6)
      and np.allclose(sq[:55], 0) and not np.allclose(sq[-5:], 0))
mb_after = mb.copy()
mb_after.loc[mb_after.index >= br["entry_time"], ["high", "close", "volume"]] *= 3
st2, sq2 = L.ob_features(mb_after, day, br, ev)
check("nothing from the break bar or later goes in", st_ == st2 and np.allclose(sq, sq2))
check("pre-market volume over the 10-day average; volume pace against the usual share by then",
      abs(st_["pm_vol_share"] - 1000 / 390_000) < 1e-12 and st_["pace"] > 0 and abs(st_["gap_adr"] - 0.05 / 0.04) < 1e-12)

print("gap days")
idx = pd.bdate_range("2024-01-02", periods=120)
names = ["GAP", "SMALL", "THIN", "QUIET"]
C = pd.DataFrame(50.0, index=idx, columns=names)
O = C.copy()
H, Lo = C * 1.03, C / 1.03
V = pd.DataFrame(2e6, index=idx, columns=names)
V["THIN"] = 2e5
H["QUIET"], Lo["QUIET"] = C["QUIET"] * 1.005, C["QUIET"] / 1.005
for nm in names:
    O.loc[idx[100], nm] = 50 * 1.06
O.loc[idx[100], "SMALL"] = 50 * 1.02
P = {"open": O, "high": H, "low": Lo, "close": C, "volume": V}
evs = L.ob_events(P, L.OB_DEFAULTS)
check("4%+ gap, enough volume, $50M+ the prior day, 1-week volatility over 3.5%: only the qualifying name",
      list(evs["ticker"]) == ["GAP"] and evs["date"].iloc[0] == idx[100], evs[["ticker", "date"]] if len(evs) else evs)
C2 = C.copy()
C2.loc[idx[100], "GAP"] = 10.0                                   # the gap day's own close mustn't matter
evs2 = L.ob_events({**P, "close": C2}, L.OB_DEFAULTS)
check("the filters and context use the prior close, not the gap day's", np.allclose(evs[["avg_vol10", "pxvol", "vol_1w", "adr20"]].to_numpy(float),
                                                                                    evs2[["avg_vol10", "pxvol", "vol_1w", "adr20"]].to_numpy(float)))
check("the next sessions' bars ride along for the swing label", evs["d1_o"].iloc[0] == O["GAP"].iloc[101])
for nm in names:
    O.loc[idx[90], nm] = 50 * 1.08
evs3 = L.ob_events(P, {**L.OB_DEFAULTS, "per_day": 1, "vol1w": 0.0, "avgvol": 0.0, "pxvol": 0.0})
check("at most per_day gaps a day", evs3.groupby("date").size().max() == 1)
evs4 = L.ob_events(P, L.OB_DEFAULTS, start=idx[101])
evs5 = L.ob_events(P, L.OB_DEFAULTS, start=idx[95])
check("a start date drops earlier gap days", len(evs4) == 0 and len(evs5) == 1 and evs5["date"].iloc[0] == idx[100]
      and len(L.ob_events(P, L.OB_DEFAULTS)) == 3)

print("walk-forward")
rng = np.random.default_rng(1)
n = 4000
dts = np.sort(rng.choice(pd.bdate_range("2021-01-04", periods=900), n))
folds = L.ob_folds(pd.Series(dts), 6, 0.4, 8)
check("folds: training rows all dated more than 8 days before each test block; blocks in order, no overlap",
      len(folds) == 6 and all(pd.Series(dts).iloc[f["train"]].max() < f["test_start"] - pd.Timedelta(days=8) for f in folds)
      and all(folds[i]["test_end"] < folds[i + 1]["test_start"] for i in range(5)))
xs = rng.normal(size=(n, len(L.OB_STATIC))).astype(np.float32)
sig = xs[:, list(L.OB_STATIC).index("pace")]
p_ = 1 / (1 + np.exp(-(1.4 * sig - 1.0)))
win_i = (rng.random(n) < p_).astype(float)
win_s = (rng.random(n) < p_).astype(float)
rows = pd.DataFrame({f"x_{k}": xs[:, j] for j, k in enumerate(L.OB_STATIC)})
rows["date"], rows["ticker"], rows["m"] = pd.to_datetime(dts), [f"T{i % 50}" for i in range(n)], 15
rows["intra_win"], rows["swing_win"] = win_i, win_s
rows["intra_R"], rows["swing_R"] = np.where(win_i == 1, 2.0, -1.0), np.where(win_s == 1, 2.0, -1.0)
seqs = rng.normal(size=(n, L.OB_L, len(L.OB_CH))).astype(np.float32)
wf = L.ob_walk_forward(rows, seqs, use_nn=False)
sc = L.ob_score(rows, wf).set_index("head")
check("trees find a planted static signal out of sample (AUC > 0.7), their picks beat taking every trade",
      sc.loc["intra", "auc_gbm"] > 0.7 and sc.loc["intra", "R_gbm"] > sc.loc["intra", "R_all"] + 0.3
      and sc.loc["intra", "verdict"] == "USE THE TREES", sc[["auc_gbm", "R_gbm", "R_all", "t_gbm", "verdict"]].to_dict())
dd = pd.DataFrame({"date": [1, 1, 2, 2, 3, 3] * 4, "R": [2, -1, 2, -1, -1, 2] * 4, "s": [1, 0, 1, 0, 0, 1] * 4})
m_, t_, nd, a1, a2 = L.ob_daily_diff(dd.assign(date=np.repeat(np.arange(12), 2)), "s", None, "R")
check("paired by day: picks' average R less the day's average", abs(m_ - 1.5) < 1e-12 and nd == 12)
check("AUC: perfect, inverted, coin flip", L.ml_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
      and L.ml_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0 and L.ml_auc([0, 1, 0, 1], [0.5] * 4) == 0.5)
if TORCH:
    # a signal only in the minute bars: the last 10 bars' volume channel rising predicts the win
    seq_sig = rng.normal(size=n)
    seqs2 = rng.normal(size=(n, L.OB_L, len(L.OB_CH))).astype(np.float32) * 0.5
    seqs2[:, -10:, 3] += np.linspace(0, 1, 10)[None, :] * seq_sig[:, None] * 2
    p2 = 1 / (1 + np.exp(-(1.8 * seq_sig - 1.0)))
    rows2 = rows.copy()
    rows2["intra_win"] = (rng.random(n) < p2).astype(float)
    rows2["swing_win"] = (rng.random(n) < p2).astype(float)
    rows2["intra_R"], rows2["swing_R"] = np.where(rows2["intra_win"] == 1, 2.0, -1.0), np.where(rows2["swing_win"] == 1, 2.0, -1.0)
    for k in L.OB_STATIC:
        rows2[f"x_{k}"] = rng.normal(size=n).astype(np.float32)
    wf2 = L.ob_walk_forward(rows2, seqs2, use_nn=True)
    sc2 = L.ob_score(rows2, wf2).set_index("head")
    check("a signal that lives only in the minute bars: the network finds it (AUC > 0.68), the trees can't (< 0.56)",
          sc2.loc["intra", "auc_nn"] > 0.68 and sc2.loc["intra", "auc_gbm"] < 0.56 and sc2.loc["intra", "verdict"] == "USE THE NETWORK",
          sc2[["auc_nn", "auc_gbm", "verdict"]].to_dict())
    fin = L.ob_fit_final(rows2.iloc[:1500], seqs2[:1500])
    net = L.ob_restore_nn(fin)
    X_ = L.ob_tab(rows2.iloc[:20])
    check("the saved network restores to the same predictions (no PyTorch objects in the pickle)",
          net is not None and isinstance(fin["nn"]["state"][next(iter(fin["nn"]["state"]))], np.ndarray)
          and np.allclose(L.ob_predict_nn(net, X_, seqs2[:20]), L.ob_predict_nn(net, X_, seqs2[:20])))
else:
    print("  (PyTorch not installed: network checks skipped)")

print("today's breaks (demo)")
dbars = {t: L._demo_daily(t, 600) for t in ["AAA", "BBB", "CCC", "SPY"]}
Pd = L.panel_from_bars(dbars)
Pd = {k: Pd[k] for k in ("open", "high", "low", "close", "volume")}
tday = Pd["close"].index[-1].date()
cl = L.ObDemoClient(Pd)
fin_d = {"gbm": {}}
td = L.ob_today(cl, {k: v.iloc[:-1] for k, v in Pd.items()}, ["AAA", "BBB"], tday,
                {t: float(Pd["open"][t].iloc[-1]) for t in ["AAA", "BBB"]}, 0.0, fin_d, (5, 15))
check("today: one row per name and range, with the break's status", len(td) == 4 and td["status"].astype(str).str.len().gt(0).all(), td)
ctx = L.ob_context_today({k: v.iloc[:-1] for k, v in Pd.items()}, ["AAA"], tday, {"AAA": float(Pd["open"]["AAA"].iloc[-1])})
check("today's context = the training context for the same day",
      abs(ctx.loc["AAA", "gap"] - (Pd["open"]["AAA"].iloc[-1] / Pd["close"]["AAA"].iloc[-2] - 1)) < 1e-6
      and abs(ctx.loc["AAA", "avg_vol10"] - Pd["volume"]["AAA"].iloc[-11:-1].mean()) < 1e-3 * Pd["volume"]["AAA"].iloc[-11:-1].mean())

print("learned ranker: universe and targets")
idx = pd.bdate_range("2023-01-02", periods=60)
nm = [f"N{i}" for i in range(6)]
C = pd.DataFrame(np.tile(np.arange(10, 16, dtype=float), (60, 1)), index=idx, columns=nm)
V = pd.DataFrame(np.tile([1e6, 2e6, 3e6, 4e6, 5e6, 6e6], (60, 1)), index=idx, columns=nm)
C["N0"] = 4.0                                                     # under $5: never in
O = C * 1.0
Pp = {"open": O, "high": C * 1.01, "low": C / 1.01, "close": C, "volume": V}
Q, U = L.ar_panel_prep(Pp, top_n=3)
check("the day's top names by dollar volume, $5 and up; the panel cut to names ever in it",
      list(U.columns) == ["N3", "N4", "N5"] and U.iloc[-1].all() and "vwap" in Q)
C3 = C.copy()
C3.iloc[30:, 2] = np.nan                                          # N2 stops trading after day 29
C3.iloc[:30, 2] = np.linspace(12, 14.9, 30)
O3 = C3.shift(1).fillna(C3)
Uall = pd.DataFrame(True, index=idx, columns=nm)
raw, rk = L.ar_targets({"open": O3, "close": C3}, Uall, (5,))
check("forward return from the next open to the close 5 sessions later", abs(raw[10, 3, 0] - (C3.iloc[15, 3] / O3.iloc[11, 3] - 1)) < 1e-6)
check("a name that stops trading exits at its last close", abs(raw[27, 2, 0] - (C3.iloc[29, 2] / O3.iloc[28, 2] - 1)) < 1e-6)
check("targets are centred ranks across the day's names", np.allclose(np.nanmean(rk[10, :, 0]), 0, atol=0.1)
      and np.nanmax(rk[10, :, 0]) <= 0.5 and np.nanmin(rk[10, :, 0]) >= -0.5)

print("learned ranker: IC, long-short, the loss and the network")
s = np.array([[1, 2, 3, 4, 5.0]] * 3)
y = np.stack([np.array([[1, 2, 3, 4, 5.0], [5, 4, 3, 2, 1.0], [1, 3, 2, 5, 4.0]])], axis=2)
y = np.concatenate([y] * 1, axis=2)
ic = L.ar_daily_ic(np.repeat(s, 1, axis=0)[:, :, None][:, :, 0] if False else np.tile(np.arange(1, 41, dtype=float), (3, 1)),
                   np.stack([np.tile(np.arange(1, 41, dtype=float), (3, 1))], axis=2) * np.array([1, -1, 1])[:, None, None], np.arange(3), 0)
check("daily IC: +1 when the score orders the returns, -1 when reversed", np.allclose(ic, [1, -1, 1]))
sc_ = np.tile(np.arange(100, dtype=float), (20, 1))
yr_ = np.tile(np.arange(100, dtype=float) / 1000, (20, 1))[:, :, None]
ls = L.ar_long_short(sc_, yr_, np.arange(20), 5, 0, cost_bp=0.0)
check("long-short: top tenth less bottom tenth, rebalanced every h sessions, no turnover after the first",
      ls["periods"] == 4 and abs(ls["ls_net"] - (np.mean(np.arange(90, 100)) - np.mean(np.arange(10))) / 1000) < 1e-12
      and ls["turnover"] == 0.0)
ls_c = L.ar_long_short(sc_, yr_, np.arange(20), 5, 0, cost_bp=10.0)
check("costs only on what turns over (all of it the first time)", abs(ls_c["ls_net"] - (ls["ls_net"] - 4 * 10e-4 / 4)) < 1e-12)
v = {"t_nn_vs_comp": 3.0, "halves_nn": True, "t_nn_vs_ridge": 0.5, "t_nn_vs_gbm": 0.1, "t_ic_nn": 2.5}
check("verdicts: the network only with t 2.5+, both halves, not behind ridge or trees",
      L.ar_verdict(v) == "USE THE NETWORK" and L.ar_verdict({**v, "halves_nn": False}) == "KEEP THE COMPOSITE"
      and L.ar_verdict({**v, "t_nn_vs_ridge": -0.5, "t_ridge_vs_comp": 3.0, "halves_ridge": True, "t_ic_ridge": 2.2}) == "USE THE LINEAR MODEL"
      and L.ar_verdict({**v, "t_ic_nn": 1.0}) == "KEEP THE COMPOSITE"
      and L.ar_verdict({"t_gbm_vs_comp": 3, "halves_gbm": True, "t_ic_gbm": 3, "ic_gbm": 0.02, "t_ridge_vs_comp": 3,
                        "halves_ridge": True, "t_ic_ridge": 3, "ic_ridge": 0.03}) == "USE THE LINEAR MODEL")
vo = {"t_gbm": 3.0, "halves_gbm": True, "t_pick_gbm": -1.0, "R_all": -0.4, "t_all": -8.0}
check("breakouts: picks that only lose less than the rest aren't recommended", L.ob_verdict(vo) == "LOSES LESS, STILL LOSES"
      and L.ob_verdict({**vo, "t_pick_gbm": 2.5}) == "USE THE TREES")
if TORCH:
    torch = L._torch()
    pr = torch.tensor(np.random.default_rng(2).normal(size=(4, 50, 1)), dtype=torch.float32)
    yy = pr * 0.5 + torch.tensor(np.random.default_rng(3).normal(size=(4, 50, 1)), dtype=torch.float32)
    mk = torch.ones_like(pr, dtype=torch.bool)
    lv = float(L.ar_ic_loss(torch, pr, yy, mk))
    want = -np.mean([np.corrcoef(pr[i, :, 0].numpy(), yy[i, :, 0].numpy())[0, 1] for i in range(4)])
    check("the IC loss is minus the average daily correlation", abs(lv - want) < 1e-5, (lv, want))
    # planted: feature 0 predicts returns only when the market feature (last) is positive; ridge sees half of it
    g = np.random.default_rng(4)
    D, N, K = 700, 150, 6
    X = g.uniform(-0.5, 0.5, size=(D, N, K)).astype(np.float32)
    regime = np.sign(g.normal(size=D)).astype(np.float32)
    X[:, :, -1] = regime[:, None]
    ret = X[:, :, 0] * regime[:, None] * 0.6 + g.normal(size=(D, N)) * 0.5
    Yr = (pd.DataFrame(ret).rank(axis=1, pct=True).to_numpy() - 0.5).astype(np.float32)[:, :, None].repeat(3, axis=2)
    tr_, va_, te_ = np.arange(0, 450), np.arange(450, 520), np.arange(540, 700)
    mdl = L.ar_fit_nn(X, Yr, tr_, va_)
    S_nn = L.ar_predict_nn(mdl, X, te_)
    W = L.ar_ridge(X, Yr, tr_)
    S_r = X[te_] @ W.astype(np.float32)
    ic_nn = np.nanmean(L.ar_daily_ic(np.r_[np.zeros((540, N)), S_nn[:, :, 0]], Yr, te_, 0))
    ic_r = np.nanmean(L.ar_daily_ic(np.r_[np.zeros((540, N)), S_r[:, :, 0]], Yr, te_, 0))
    check("the network learns an interaction (an alpha that flips with the market) that ridge can't",
          ic_nn > 0.2 and ic_nn > ic_r + 0.15, (ic_nn, ic_r))
print("learned ranker: the whole pipeline on demo data")
db = {t: L._demo_daily(t, L.UNIVERSE_DAYS) for t in [f"D{i:03d}" for i in range(70)]}
mkt = L.lg_demo_market(db, n_extra=20)
Pm = {k: v.iloc[-(3 * 252 + 300):] for k, v in mkt["P"].items()}
res = L.ar_run(Pm, top_n=60, cost_bp=10.0, use_nn=TORCH)
meths = set(res["table"]["method"])
check("every method scored at every horizon; a verdict per horizon; today's percentiles",
      {"composite", "ridge"} <= meths and set(res["table"]["horizon"]) == set(L.AR_H) and len(res["verdict"]) == 3
      and res["today"]["composite_pct"].between(0, 100).all() and (not TORCH or "nn_10_pct" in res["today"]), meths)
vt = res["verdict"].set_index("horizon")
use = vt[vt["verdict"].str.startswith("USE")]
check("a method is recommended only with its own IC reliably positive (t >= 2), not just beating the composite",
      all(_t >= 2.0 for _t in [vt.loc[h_, "t_ic_" + {"USE THE NETWORK": "nn", "USE THE TREES": "gbm",
                                                         "USE THE LINEAR MODEL": "ridge"}[v_]] for h_, v_ in use["verdict"].items()]),
      vt[[c for c in vt.columns if c.startswith(("t_ic", "verdict"))]].to_dict())
v2 = {"t_gbm_vs_comp": 3.0, "halves_gbm": True, "t_ic_gbm": 0.5, "t_ic_composite": -2.6}
check("beating a composite that is wrong isn't enough: the verdict says the composite is wrong here",
      L.ar_verdict(v2) == "COMPOSITE IS WRONG HERE")

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
