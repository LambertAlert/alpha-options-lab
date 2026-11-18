"""Planted-case tests for the anchored VWAP (Stocks > VWAP, the Setup ledger's VWAP family, the Brief's VWAP scan):
the line by hand, no look-ahead, each anchor found point-in-time, the bar price (own VWAP or typical price), each setup
planted (reclaim, pullback to the low's line, pullback to a gap day's line and its volume control, the pinch), the
stops, the snapshot's plan, the ledger run with its features and splits, the ledger read and the Brief's rows.
Run: python test_aw.py"""
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


def panel(closes, vols=None, opens=None, lows=None, highs=None, name="X"):
    """One-name panels with a 2% bar around each close, so the typical price equals the close."""
    c = pd.Series(np.asarray(closes, float), index=pd.bdate_range("2020-01-01", periods=len(closes)))
    v = pd.Series(np.asarray(vols, float) if vols is not None else np.full(len(c), 1e6), index=c.index)
    o = pd.Series(np.asarray(opens, float), index=c.index) if opens is not None else c.shift(1).fillna(c.iloc[0])
    h = pd.Series(np.asarray(highs, float), index=c.index) if highs is not None else c * 1.01
    l = pd.Series(np.asarray(lows, float), index=c.index) if lows is not None else c * 0.99
    F = lambda s: s.to_frame(name)
    return {"open": F(o), "high": F(h), "low": F(l), "close": F(c), "volume": F(v)}


def run(Q, tp=None):
    return L.aw_panels(Q["open"], Q["high"], Q["low"], Q["close"], Q["volume"], tp)


rng = np.random.default_rng(7)

print("The line")
cw = 50 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, 600)))
vw_ = rng.uniform(5e5, 3e6, 600)
Q = panel(cw, vw_)
A = run(Q)
ph_ = Q["high"].rolling(252, min_periods=1).max().shift(1)
anc = L._aw_anchor((Q["high"] > ph_) | ph_.isna())[:, 0]
t = 590
a = int(anc[t])
c_, v_ = Q["close"]["X"].to_numpy(), Q["volume"]["X"].to_numpy()
hand = (c_[a:t + 1] * v_[a:t + 1]).sum() / v_[a:t + 1].sum()
check("by hand: the AVWAP from the last new 52-week high = sum(price x volume) / sum(volume) from that bar to today",
      abs(A["hi"]["X"].iloc[t] - hand) < 1e-9 * hand, (A["hi"]["X"].iloc[t], hand))
check("its age is the sessions since that bar", A["age_hi"]["X"].iloc[t] == t - a)
Q2 = panel(np.r_[cw[:560], cw[560:] * 1.5], np.r_[vw_[:560], vw_[560:] * 3])
A2 = run(Q2)
same = all(np.allclose(A2[k]["X"].iloc[:560].dropna(), A[k]["X"].iloc[:560].dropna()) for k in ("hi", "lo", "ev", "state"))
check("no look-ahead: changing the last 40 sessions leaves every earlier line and state alone", same)
pl_ = Q["low"].rolling(63, min_periods=1).min().shift(1)
lo_hand = L._aw_anchor((Q["low"] < pl_) | pl_.isna())[:, 0]
check("the low's anchor is the last session under every low of the prior 63", (A["age_lo"]["X"].iloc[t] == t - lo_hand[t]))

print("The bar's price")
tpq = L.aw_typical(Q["high"], Q["low"], Q["close"], None)
vwp = Q["close"] * 1.004
vwp.iloc[5] = Q["high"].iloc[5] * 1.2                     # outside the bar: not trusted
vwp.iloc[6] = np.nan
tpv = L.aw_typical(Q["high"], Q["low"], Q["close"], vwp)
check("the bar's own VWAP is used when it is inside the bar", abs(tpv["X"].iloc[10] - vwp["X"].iloc[10]) < 1e-12)
check("outside the bar or missing: the typical price (H+L+C)/3", abs(tpv["X"].iloc[5] - tpq["X"].iloc[5]) < 1e-12
      and abs(tpv["X"].iloc[6] - tpq["X"].iloc[6]) < 1e-12)

print("Reclaim of the line from the high")
up = np.linspace(50, 100, 260)
dn = np.linspace(100, 80, 41)[1:]
back = np.linspace(80, 100, 31)[1:]
cr = np.r_[up, dn, back]
Q = panel(cr)
A = run(Q)
pk = 259
mean_since = np.array([cr[pk:i + 1].mean() if i >= pk else np.nan for i in range(len(cr))])
first = next(i for i in range(pk + 21, len(cr)) if cr[i] > mean_since[i] and cr[i - 1] <= mean_since[i - 1])
fired = np.flatnonzero(A["S"]["reclaim"]["X"].to_numpy())
check("fires on the first close over the line from the 52-week high, once", list(fired) == [first], (list(fired), first))
check("the line there is the average close since the high (equal volume)", abs(A["hi"]["X"].iloc[first] - mean_since[first]) < 1e-9)
check("the stop is the line less half an ATR, under the close",
      abs(A["stops"]["avh"]["X"].iloc[first] - (A["hi"]["X"].iloc[first] - 0.5 * L._mc_atr(Q["high"], Q["low"], Q["close"], 14)["X"].iloc[first])) < 1e-9
      and A["stops"]["avh"]["X"].iloc[first] < cr[first])
check("the reference cross fires there too; the state before it is under the high's line",
      bool(A["S"]["cross_raw"]["X"].iloc[first]) and A["state"]["X"].iloc[first - 1] < 2)
Qy = panel(np.r_[up, np.linspace(100, 95, 11)[1:], np.linspace(95, 101, 6)[1:]])
check("no reclaim when the high is under 20 sessions old", not run(Qy)["S"]["reclaim"]["X"].any())

print("Pullback holding the line from the swing low")
base = np.r_[np.linspace(40, 100, 260), np.linspace(100, 82, 31)[1:], np.linspace(82, 118, 61)[1:]]
path, hit = list(base), None
for k in range(40):
    path.append(path[-1] * 0.985)
    A = run(panel(path))
    if A["S"]["pull_lo"]["X"].iloc[-1]:
        hit = len(path) - 1
        break
check("a pullback that tests the line from the 63-day low and closes back over it fires", hit is not None)
if hit is not None:
    lo_line, cl = A["lo"]["X"].iloc[hit], path[hit]
    check("the test: the low within 0.25 ATR of the line, the close over it",
          0.99 * cl <= lo_line + 0.25 * L._mc_atr(*(panel(path)[k] for k in ("high", "low", "close")), 14)["X"].iloc[hit] and cl > lo_line,
          (cl, lo_line))
    check("the anchor is the swing low (the low of the decline)", A["age_lo"]["X"].iloc[hit] == hit - 289, (A["age_lo"]["X"].iloc[hit], hit))
    under = path[:hit] + [lo_line * 0.98]
    check("a close under the line doesn't fire", not run(panel(under))["S"]["pull_lo"]["X"].iloc[-1])

print("Pullback holding the line from a gap-up day, and the volume control")


def gap_path(gvol):
    c0 = list(np.linspace(80, 100, 260))
    o0 = list(np.r_[c0[0], c0[:-1]])
    lo0, hi0, v0 = [x * 0.99 for x in c0], [x * 1.01 for x in c0], [1e6] * 260
    c0 += [108.0]; o0 += [106.0]; lo0 += [105.5]; hi0 += [109.0]; v0 += [gvol]
    return c0, o0, lo0, hi0, v0


c0, o0, lo0, hi0, v0 = gap_path(3.5e6)
for k in range(8):                                         # it runs on after the gap, then pulls back to the line
    nx = c0[-1] * 1.01
    c0.append(nx); o0.append(c0[-2]); lo0.append(nx * 0.99); hi0.append(nx * 1.01); v0.append(1e6)
hit = None
for k in range(25):
    nx = c0[-1] * 0.985
    c0.append(nx); o0.append(c0[-2]); lo0.append(nx * 0.99); hi0.append(nx * 1.01); v0.append(1e6)
    A = run(panel(c0, v0, o0, lo0, hi0))
    if A["S"]["pull_ev"]["X"].iloc[-1]:
        hit = len(c0) - 1
        break
check("a gap of 6% on 3.5x volume anchors a line; a pullback that holds it fires", hit is not None)
if hit is not None:
    check("at least 3 sessions after the gap, the close over the gap day's low", hit - 260 >= 3 and c0[hit] > 105.5,
          (hit - 260, c0[hit]))
    tp_ = (np.array(hi0) + np.array(lo0) + np.array(c0)) / 3
    vv_ = np.array(v0)
    hand_ev = (tp_[260:hit + 1] * vv_[260:hit + 1]).sum() / vv_[260:hit + 1].sum()
    check("by hand: the gap day's line, the gap day weighted by its 3.5x volume", abs(A["ev"]["X"].iloc[hit] - hand_ev) < 1e-9,
          (A["ev"]["X"].iloc[hit], hand_ev))
c1, o1, lo1, hi1, v1 = gap_path(1.5e6)
for k in range(25):
    nx = c1[-1] * 0.993
    c1.append(nx); o1.append(c1[-2]); lo1.append(nx * 0.99); hi1.append(nx * 1.01); v1.append(1e6)
A1 = run(panel(c1, v1, o1, lo1, hi1))
check("the same gap on 1.5x volume is no event: no line, no setup", A1["ev"]["X"].isna().all() and not A1["S"]["pull_ev"]["X"].any())

print("The pinch")
cp = np.r_[np.linspace(50, 100, 260), np.linspace(100, 80, 31)[1:], np.linspace(80, 85, 6)[1:], np.full(120, 85.0), [90.0, 91.0, 92.0]]
Q = panel(cp)
A = run(Q)
bo = len(cp) - 3
atr_bo = L._mc_atr(Q["high"], Q["low"], Q["close"], 14)["X"].iloc[bo]
check("in the base the lines from the high and the low converge within 1 ATR",
      abs(A["hi"]["X"].iloc[bo - 1] - A["lo"]["X"].iloc[bo - 1]) <= atr_bo, (A["hi"]["X"].iloc[bo - 1], A["lo"]["X"].iloc[bo - 1], atr_bo))
check("the first close over both fires the pinch, once", list(np.flatnonzero(A["S"]["pinch"]["X"].to_numpy())) == [bo],
      list(np.flatnonzero(A["S"]["pinch"]["X"].to_numpy())))
check("the pinch's stop is the lower line less half an ATR",
      abs(A["stops"]["avp"]["X"].iloc[bo] - (min(A["hi"]["X"].iloc[bo], A["lo"]["X"].iloc[bo]) - 0.5 * atr_bo)) < 1e-9)
check("the state goes to ABOVE BOTH on the breakout", A["state"]["X"].iloc[bo] == 2 and A["state"]["X"].iloc[bo - 1] == 1)
Qr = panel(np.r_[np.linspace(50, 80, 260), np.full(120, 85.0), [90.0]])
check("no pinch when the low came before the high (no decline into the base)", not run(Qr)["S"]["pinch"]["X"].any())

print("The snapshot's plan")
S = L.aw_snapshot(A, Q)
r = S.loc["X"]
check("the freshest setup within 5 sessions, 2 sessions back", r["vw_setup_key"] in ("reclaim", "pinch") and r["vw_setup_age"] == 2, r.to_dict())
check("buy stop over the signal day's high; the setup's stop under it",
      abs(r["vw_trigger"] - Q["high"]["X"].iloc[bo]) < 1e-9 and r["vw_stop"] < r["vw_trigger"])
check("triggered when a later high went through it", r["vw_triggered"].startswith("triggered "), r["vw_triggered"])
check("state and distances", r["vw_state"] == "ABOVE BOTH" and r["vw_pos_hi"] > 0 and r["vw_pos_lo"] > 0)

print("The ledger")
names = list(L.demo_universe()["ticker"])[:30]
bars = {t: L._demo_daily(t, L.UNIVERSE_DAYS) for t in names + ["SPY"]}
spy = bars.pop("SPY")["close"]
P = L.panel_from_bars(bars)
prm = {**{"horizon": 10, "cooldown": 10, "min_price": 5.0, "min_dv": 1.0, "target": 2.0, "mode": "next_open", "win": 1,
          "cost": 10.0, "cap": 3.0, "nsess": 1000, "base_step": 5}}
try:
    import playbook as PB
    prm = PB.pb_ledger_prm({})
except Exception:
    pass
rr = L.lg_run(P, spy, None, ("VWAP", "Zanger"), "12/26/9", prm, "Your list")
ev = rr["ev"]
vws = ev[ev["setup"].astype(str).str.startswith("vw:")]
check("the VWAP family trades on demo bars", len(vws) > 20 and vws["setup"].nunique() >= 3, vws["setup"].value_counts().to_dict())
check("every trade carries its AVWAP state and distances", {"aw_state", "aw_hi_pos", "aw_lo_pos"} <= set(ev.columns)
      and ev["aw_state"].notna().mean() > 0.8)
lab = L.lg_split_col(ev, "aw_state")
check("the 'AVWAP state' split labels every trade", set(lab.unique()) <= set(L.AW_STATES) | {"n/a"} and (lab != "n/a").mean() > 0.8)
lab2 = L.lg_split_col(ev, "aw_hi")
check("the 'Close vs the AVWAP from the high' split bands", (lab2 != "n/a").mean() > 0.8 and lab2.nunique() >= 3, lab2.value_counts().to_dict())
tr = vws[vws["status"] == 0]
check("most VWAP trades open over their stop", len(tr) > 0.6 * len(vws), (len(tr), len(vws)))
pinch_on_reclaim = ev[(ev["setup"] == "vw:reclaim") & (ev["status"] == 0)]
check("a reclaim is a close over the high's line", (pinch_on_reclaim["aw_hi_pos"] > 0).all())
T1, T2 = L.aw_ledger_read(ev, 10)
check("the ledger read: VWAP setups and every family by state", len(T1) >= 2 and len(T2) >= 3 and {"er", "t"} <= set(T2.columns),
      (len(T1), len(T2)))
check("registered: family, stops, Alphas-by-trade types, the ranker's inputs",
      "VWAP" in L.LG_FAMILIES and all(L.LG_SETUPS[k][0] == "VWAP" for k in ("vw:reclaim", "vw:pull_lo", "vw:pull_ev", "vw:pinch"))
      and all(k in L.AM_TYPES for k in L.LG_SETUPS if k.startswith("vw:")) and "aw_state" in L.RK_FEATURES
      and all(L.LG_SETUPS[k][2] in L.LG_STOP_LABEL for k in L.LG_SETUPS) and "aw_state" in L.LG_SPLITS)

print("The Brief and the breadth")
ab = {"P": P, "asof": P["close"].index[-1]}
B = L.aw_block(ab)
Sn = B["snap"]
F = Sn.copy()
F["last"], F["close"] = P["close"].iloc[-1], P["close"].iloc[-1]
F["su_dv"], F["adr20"], F["bar_date"] = 50.0, 4.0, str(P["close"].index[-1].date())
F["vw_setup_key"] = F["vw_setup_key"].where(F["vw_setup_key"] != "", "")
if True:                                                    # plant one so the scan always has a fresh setup to read
    t0 = F.index[0]
    F.loc[t0, ["vw_setup_key", "vw_setup_age", "vw_trigger", "vw_stop", "vw_triggered"]] = ["pull_lo", 0, F.at[t0, "last"] * 1.01, F.at[t0, "last"] * 0.95, ""]
SC = L.su_candidates(F)
vr = SC[SC["family"] == "VWAP"] if len(SC) else SC
check("the Brief's VWAP scan writes rows with its plan and ledger id", len(vr) > 0 and vr["ledger_id"].str.startswith("vw:").all()
      and (vr["stop"] < vr["trigger"]).all(), vr.head(3).to_dict("records") if len(vr) else None)
check("VWAP is one of the Brief's scans", "VWAP" in L.SU_FAMILIES and "VWAP" in L.SU_FAM_COLOR)
Bd = L.aw_breadth(B["A"])
check("breadth: shares between 0 and 1, every day with 5+ names", len(Bd) > 200 and Bd[["above_hi", "above_both", "below_both"]].stack().between(0, 1).all())

print("The session VWAP on 30-minute bars")
ix = pd.to_datetime(["2026-03-02 09:30", "2026-03-02 10:00", "2026-03-02 10:30", "2026-03-03 09:30", "2026-03-03 10:00"])
m = pd.DataFrame({"open": [10, 10.5, 11, 12, 12], "high": [11, 11, 12, 12.5, 13], "low": [9, 10, 10.5, 11.5, 12],
                  "close": [10.5, 10.8, 11.5, 12, 12.6], "volume": [100, 300, 200, 50, 150]}, index=ix)
m["day"] = m.index.normalize()
sv = L.pv_svwap(m)
tp = (m["high"] + m["low"] + m["close"]) / 3
hand = [tp.iloc[0], (tp.iloc[0] * 100 + tp.iloc[1] * 300) / 400, (tp.iloc[:3] * m["volume"].iloc[:3]).sum() / 600,
        tp.iloc[3], (tp.iloc[3] * 50 + tp.iloc[4] * 150) / 200]
check("by hand: cumulative price x volume over cumulative volume, restarting each session", np.allclose(sv, hand), (sv, hand))
m2 = m.assign(vwap=[10.2, 10.6, 30.0, 12.1, np.nan])
sv2 = L.pv_svwap(m2)
check("the bar's own VWAP when it is inside the bar, else the typical price",
      abs(sv2[1] - (10.2 * 100 + 10.6 * 300) / 400) < 1e-12 and abs(sv2[4] - (12.1 * 50 + tp.iloc[4] * 150) / 200) < 1e-12)

print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
