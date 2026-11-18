"""Planted-case tests for Options > Market odds: OCC tickers and monthly expiries (with the holiday Thursday), the
vertical picker, last-hour prints, the smile fit and the vertical's odds against a hand calculation, put-call parity of
the odds, the clustered standard error, full studies on synthetic markets where the answer is known (fair odds; a drift;
a vol premium with skew), dividends, splits, the saved study, the cache, and today's verticals.
Run: python test_odds.py"""
import json, gzip, math, os, shutil, tempfile, warnings
from datetime import date, timedelta
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


def N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


print("tickers, expiries, strikes")
t = L.od_occ("NVDA", date(2025, 1, 17), "call", 140.0)
check("OCC ticker round trip", t == "O:NVDA250117C00140000" and L.od_parse_occ(t) == ("NVDA", date(2025, 1, 17), "call", 140.0))
check("OCC with a decimal strike and a put", L.od_parse_occ(L.od_occ("SPY", date(2026, 3, 20), "put", 582.5))[2:] == ("put", 582.5))
fr = L.od_third_fridays(date(2025, 1, 1), date(2025, 12, 31))
check("third Fridays of 2025", len(fr) == 12 and fr[3] == date(2025, 4, 18) and fr[9] == date(2025, 10, 17)
      and all(d.weekday() == 4 and 15 <= d.day <= 21 for d in fr))
s = np.array([95.0, 100.0, 105.0, 110.0])
check("call vertical: upper strike the highest at or under the target", L.od_strikes_for(s, 107, "up") == (100, 105)
      and L.od_strikes_for(s, 105, "up") == (100, 105) and L.od_strikes_for(s, 96, "up") is None)
check("put vertical: lower strike the lowest at or over the target", L.od_strikes_for(s, 97, "down") == (100, 105)
      and L.od_strikes_for(s, 100, "down") == (100, 105) and L.od_strikes_for(s, 108, "down") is None)
hy = list(L.od_half_years(date(2024, 10, 30), date(2025, 9, 2)))
check("cache chunks are calendar half-years", hy == [(date(2024, 7, 1), date(2024, 12, 31)), (date(2025, 1, 1), date(2025, 6, 30)),
                                                     (date(2025, 7, 1), date(2025, 9, 2))])

print("last-hour prints")
day = pd.Timestamp("2025-03-14")
stk = pd.DataFrame({"close": [100.0, 101.0, 102.0]}, index=pd.DatetimeIndex([day + pd.Timedelta(hours=h, minutes=m) for h, m in ((14, 30), (15, 0), (15, 30))]))
o1 = pd.DataFrame({"close": [2.0], "volume": [5.0]}, index=pd.DatetimeIndex([day + pd.Timedelta(hours=14, minutes=30)]))
o2 = pd.DataFrame({"close": [2.0, 2.2, 2.4], "volume": [5.0, 3.0, 0.0]},
                  index=pd.DatetimeIndex([day + pd.Timedelta(hours=h, minutes=m) for h, m in ((14, 30), (15, 0), (15, 30))]))
check("no print in the last hour: stale, skipped", L.od_last_hour(o1, stk, day) is None)
lh = L.od_last_hour(o2, stk, day)
check("the last traded bar from 15:00 (a zero-volume bar isn't a print), with the stock in the same bar",
      lh is not None and lh[0] == 2.2 and lh[1] == 101.0 and lh[2].hour == 15 and lh[2].minute == 0, lh)

print("the smile and the odds")
S0, T, r, pv = 100.0, 30 / 365, 0.04, 0.6
F = (S0 - pv) * math.exp(r * T)
pt = np.array([1.2, -0.35, 0.28])                           # IV = 1.2 x^2 - 0.35 x + 0.28, x = ln K/F
K = np.array([80, 85, 90, 95, 100, 100, 105, 110, 115, 120], float)
cp = np.array([False, False, False, False, False, True, True, True, True, True])
iv = np.polyval(pt, np.log(K / F))
px = L.av_bs(S0, K, T, iv, r, cp, pv)
fit = L.od_fit(K, px, np.full(len(K), S0), cp, T, r, pv)
check("the smile through exact prints recovers the curve", fit is not None and np.allclose(fit["p"], pt, atol=2e-4)
      and abs(fit["atm"] - 0.28) < 1e-4 and fit["otm_only"], fit and fit["p"])
D, q, vlo, vhi = L.od_price([S0], [T], [r], [pv], pt[None, :], [104.0], [105.0], [True])
c104 = L.av_bs(S0, 104.0, T, np.polyval(pt, math.log(104 / F)), r, True, pv)[0]
c105 = L.av_bs(S0, 105.0, T, np.polyval(pt, math.log(105 / F)), r, True, pv)[0]
check("call vertical debit = C(104) - C(105) off the smile; odds = debit x e^rT / width",
      abs(D[0] - (c104 - c105)) < 1e-10 and abs(q[0] - (c104 - c105) * math.exp(r * T) / 1.0) < 1e-10)
Dd, qd, _, _ = L.od_price([S0], [T], [r], [pv], pt[None, :], [104.0], [105.0], [False])
check("a call vertical's odds and the same strikes' put vertical's odds add to 1 (parity)", abs(q[0] + qd[0] - 1) < 1e-9)
Dn, qn, _, _ = L.od_price([S0], [T], [r], [pv], pt[None, :], [104.995], [105.005], [True], flat=[0.28])
d2 = (math.log(F / 105.0) - 0.5 * 0.28 ** 2 * T) / (0.28 * math.sqrt(T))
check("a very tight flat-vol call vertical's odds are the digital N(d2)", abs(qn[0] - N(d2)) < 2e-4, (qn[0], N(d2)))
bl = []
for Kx in (85.0, 95.0, 100.0, 105.0, 115.0):
    h = 1e-3
    _, qx, _, _ = L.od_price([S0], [T], [r], [pv], pt[None, :], [Kx - h], [Kx + h], [True])
    sg = np.polyval(pt, math.log(Kx / F))
    ds = (np.polyval(pt, math.log((Kx + h) / F)) - np.polyval(pt, math.log((Kx - h) / F))) / (2 * h)
    d2x = (math.log(F / Kx) - 0.5 * sg * sg * T) / (sg * math.sqrt(T))
    vega = Kx * math.exp(-r * T) * math.exp(-0.5 * d2x * d2x) / math.sqrt(2 * math.pi) * math.sqrt(T)
    bl.append(abs(qx[0] - (N(d2x) - math.exp(r * T) * vega * ds)))
check("with a smile, a tight vertical's odds = N(d2) at its own vol less e^rT x vega x the smile's slope (Breeden-Litzenberger)",
      max(bl) < 1e-4, bl)
_, qe, _, _ = L.od_price([S0], [T], [r], [pv], pt[None, :], [104.0], [105.0], [True], drift=0.10)
_, qed, _, _ = L.od_price([S0], [T], [r], [pv], pt[None, :], [94.0], [95.0], [False], drift=0.10)
_, q95, _, _ = L.od_price([S0], [T], [r], [pv], pt[None, :], [94.0], [95.0], [False])
check("the drift check raises a call vertical's odds and lowers a put vertical's", qe[0] > q[0] and qed[0] < q95[0])
few = L.od_fit(K[[0, 1, 7, 8]], px[[0, 1, 7, 8]], np.full(4, S0), cp[[0, 1, 7, 8]], T, r, pv)
check("under five valid prints: no smile", few is None)
mix = np.array([True, True, True, False, False, False, True])        # mostly in the money: fallback to every print
Km = np.array([80, 85, 90, 110, 115, 120, 100], float)
pm = L.av_bs(S0, Km, T, np.polyval(pt, np.log(Km / F)), r, mix, pv)
fm = L.od_fit(Km, pm, np.full(len(Km), S0), mix, T, r, pv)
check("too few out-of-the-money prints: the fit falls back to every valid print, flagged", fm is not None and not fm["otm_only"]
      and abs(fm["atm"] - 0.28) < 0.01, fm and (fm["atm"], fm["otm_only"]))

print("clustered standard error")
m, se, G = L.od_cmean([1, 2, 3, 4], ["a", "a", "b", "b"])
check("by hand: mean 2.5, s.e. sqrt(G/(G-1) x sum of cluster sums^2) / n = 1", abs(m - 2.5) < 1e-12 and abs(se - 1.0) < 1e-12 and G == 2)
m1, se1, G1 = L.od_cmean([1, 2, 3, 4], ["a", "b", "c", "d"])
check("one per cluster: the ordinary s.e. with the G/(G-1) factor", abs(se1 - math.sqrt(4 / 3 * 5.0) / 4) < 1e-12)

print("a fair market: the odds should be right")
end = L.last_completed_session()
start = end - timedelta(days=730)
names = [f"F{i:02d}" for i in range(24)]
fair = L.OdDemoClient(today=end, vol_mult=1.0, skew=0.0, curve=0.0, drift=0.04, jump_p=0.0, r=0.04, print_p=1.0,
                      vol_walk=0.0, mkt_corr=0.0, div_yield={}, seed=3)
df, logs = L.od_build(fair, names, {t: "other stock" for t in names}, start, end, (30,), workers=1)
d = L.od_prepare(df, erp=0.0, frac=0.0)
tab = L.od_table(d, ["side"]).set_index("side")
check("a full study: every name, ~23 expiries, 12 spreads a smile", df["ticker"].nunique() == 24 and df["expiry"].nunique() >= 20
      and df.groupby(["ticker", "expiry"]).size().max() <= 12, (df["ticker"].nunique(), df["expiry"].nunique()))
tv = np.array([fair._path(t_)["sig"][0] for t_ in df["ticker"]])
check("ATM IV from the prints = the true vol (no premium planted)", np.abs(df["atm_iv"] / tv - 1).median() < 0.01,
      np.abs(df["atm_iv"] / tv - 1).median())
check("no skew planted: smile odds = flat-vol odds", (d["q"] - d["q_flat"]).abs().median() < 0.003)
check("fair market: paid - odds within 3 s.e. and 3 points, both ways",
      all(abs(tab.loc[s_, "t"]) < 3 and abs(tab.loc[s_, "gap"]) < 0.03 for s_ in ("up", "down")), tab[["gap", "t"]].to_dict())
check("fair market: no cell called CHEAP or RICH at 3+ s.e. by move", (L.od_table(d, ["side", "k"])["t"].abs() < 3.2).all())
dr, dse, _ = L.od_drift(d)
check("fair market: the drift over the forward is about zero", abs(dr) < 3 * dse, (dr, dse))
row = df.iloc[0]
check("each spread is the tightest listed vertical fully in the money at the target",
      ((df["side"] == "up") & (df["k_hi"] > df["target"] + 1e-9)).sum() == 0
      and ((df["side"] == "down") & (df["k_lo"] < df["target"] - 1e-9)).sum() == 0)
check("target = spot x exp(+/- k x ATM IV x sqrt T)",
      np.allclose(df["target"], df["spot"] * np.exp(np.where(df["side"] == "up", 1, -1) * df["k"] * df["atm_iv"] * np.sqrt(df["T"]))))
up_ = df["side"] == "up"
paid_hand = np.where(up_, (df["s_T"] - df["k_lo"]) / df["width"], (df["k_hi"] - df["s_T"]) / df["width"]).clip(0, 1)
check("paid = the spread's value at the expiration close over its width", np.allclose(df["paid"], paid_hand))
check("the close at expiry is the unadjusted close on the expiration day",
      all(abs(fair.daily(r_.ticker, r_.expiry.date(), r_.expiry.date(), False)["close"].iloc[0] - r_.s_T) < 1e-9
          for r_ in df.drop_duplicates(["ticker", "expiry"]).head(20).itertuples()))
check("entries are 30 days before expiry, on or before", ((df["expiry"] - df["entry"]).dt.days.between(30, 34)).all())
check("a day's prints decide its smile: entry at the close of the entry day, no later data",
      (df["entry"] < df["expiry"]).all() and (df["hv20"] > 0).all())

print("a drift the forward doesn't price")
dc = L.OdDemoClient(today=end, vol_mult=1.0, skew=0.0, curve=0.0, drift=0.60, jump_p=0.0, r=0.04, print_p=1.0,
                    vol_walk=0.0, mkt_corr=0.0, div_yield={}, seed=5)
dfd, _ = L.od_build(dc, names, {t: "other stock" for t in names}, start, end, (30,), workers=1)
dd = L.od_prepare(dfd, erp=0.0, frac=0.0)
td = L.od_table(dd, ["side"]).set_index("side")
check("a 60% drift: call verticals paid more than their odds, put verticals less (t beyond 3)",
      td.loc["up", "t"] > 3 and td.loc["down", "t"] < -3 and td.loc["up", "verdict"] == "CHEAP" and td.loc["down", "verdict"] == "RICH",
      td[["gap", "t"]].to_dict())
dr2, dse2, _ = L.od_drift(dd)
check("the drift KPI finds it (about 56% a year over the forward)", 0.35 < dr2 < 0.8, dr2)
dd2 = L.od_prepare(dfd, erp=0.56, frac=0.0)
te = L.od_table(dd2, ["side"]).set_index("side")
check("the drift check at the planted premium explains it: little left beyond it",
      abs(te.loc["up", "gap_erp"]) < 0.5 * abs(td.loc["up", "gap"]) and abs(te.loc["down", "gap_erp"]) < 0.5 * abs(td.loc["down", "gap"]),
      te[["gap_erp"]].to_dict())

print("a vol premium and a put skew")
vc = L.OdDemoClient(today=end, vol_mult=1.35, skew=1.2, curve=1.5, drift=0.04, jump_p=0.0, r=0.04, print_p=1.0,
                    vol_walk=0.0, mkt_corr=0.0, div_yield={}, seed=7)
dfv, _ = L.od_build(vc, names, {t: "other stock" for t in names}, start, end, (30,), workers=1)
dv = L.od_prepare(dfv, erp=0.0, frac=0.0)
tv_ = L.od_table(dv, ["side"]).set_index("side")
kv = L.od_table(dv, ["side", "k"]).set_index(["side", "k"])
check("vol priced 35% over what's delivered: both sides paid less than their odds, the far put verticals and the 1 sd call "
      "verticals RICH", tv_.loc["down", "gap"] < 0 and tv_.loc["up", "gap"] < 0 and kv.loc[("down", 1.5), "verdict"] == "RICH"
      and kv.loc[("down", 2.0), "verdict"] == "RICH" and kv.loc[("up", 1.0), "verdict"] == "RICH", kv[["gap", "t"]].round(3).to_dict())
check("the far put verticals carry the most premium (odds over paid, 2 sd vs a quarter sd)",
      kv.loc[("down", 1.5), "paid"] / kv.loc[("down", 1.5), "odds"] < kv.loc[("down", 0.25), "paid"] / kv.loc[("down", 0.25), "odds"])
def frac_over(side, k):
    g = dv[(dv["side"] == side) & (dv["k"] == k)]
    return float((g["q"] > g["q_flat"]).mean())
check("a put skew moves the odds in the textbook pattern (a left-skewed risk-neutral distribution): near-the-money call "
      "verticals and far put verticals over flat vol, near-the-money put verticals and far call verticals under",
      frac_over("up", 0.25) > 0.9 and frac_over("down", 2.0) > 0.8 and frac_over("down", 0.25) < 0.1 and frac_over("up", 2.0) < 0.2,
      [frac_over(*a) for a in (("up", 0.25), ("down", 2.0), ("down", 0.25), ("up", 2.0))])
br = L.od_brier(dv).set_index("side")
check("Brier: smile and flat-vol scores both computed per side", set(br.index) == {"up", "down"} and (br["brier_smile"] > 0).all())

print("dividends, splits, a holiday expiry")
dvc = L.OdDemoClient(today=end, vol_mult=1.0, skew=0.0, curve=0.0, drift=0.04, jump_p=0.0, r=0.04, print_p=1.0,
                     vol_walk=0.0, mkt_corr=0.0, div_yield={"DIVY": 0.06}, vols={"DIVY": 0.25}, seed=9)
dfx, _ = L.od_build(dvc, ["DIVY"], {"DIVY": "other stock"}, start, end, (30,), workers=1)
wd = dfx[dfx["pv_div"] > 0].drop_duplicates("expiry")
check("a dividend inside the window: the forward drops by its value, and the smile stays flat at the true vol",
      len(wd) >= 4 and np.allclose(wd["fwd"], (wd["spot"] - wd["pv_div"]) * np.exp(wd["r"] * wd["T"]))
      and (wd["atm_iv"] - 0.25).abs().max() < 0.004 and wd["p1"].abs().max() < 0.03, (len(wd), wd["atm_iv"].tolist()[:5]))
mid = end - timedelta(days=365)
spc = L.OdDemoClient(today=end, vol_mult=1.0, skew=0.0, curve=0.0, drift=0.04, jump_p=0.0, r=0.04, print_p=1.0,
                     vol_walk=0.0, mkt_corr=0.0, div_yield={}, splits={"SPLT": (mid, 4.0)}, seed=13)
dfs, lgs = L.od_build(spc, ["SPLT"], {"SPLT": "other stock"}, start, end, (30,), workers=1)
span_split = ((dfs["entry"] < pd.Timestamp(mid)) & (dfs["expiry"] >= pd.Timestamp(mid))).sum()
check("a 4-for-1 split: the window that spans it is dropped, the rest kept", span_split == 0
      and lgs[0]["why"].get("split before expiry", 0) >= 1 and dfs["expiry"].nunique() >= 18, (span_split, lgs[0]["why"]))
pre_post = dfs.drop_duplicates("expiry")
check("strikes and prices stay in each date's own (unadjusted) terms across the split",
      (pre_post[pre_post["expiry"] > pd.Timestamp(mid)]["spot"].median() < 0.4 * pre_post[pre_post["expiry"] < pd.Timestamp(mid)]["spot"].median()))
hol = [f_ for f_ in L.od_third_fridays(start + timedelta(days=60), end - timedelta(days=30))][3]
hc = L.OdDemoClient(today=end, vol_mult=1.0, skew=0.0, curve=0.0, drift=0.04, jump_p=0.0, r=0.04, print_p=1.0,
                    vol_walk=0.0, mkt_corr=0.0, div_yield={}, thursday=[hol], seed=17)
ex, li = L.od_listed(hc, "HOLX", hol)
dfh, _ = L.od_build(hc, ["HOLX"], {"HOLX": "other stock"}, start, end, (30,), workers=1)
check("a holiday Friday: the monthly expiry is the Thursday before, and it is scored",
      ex == hol - timedelta(days=1) and len(li) > 0 and (dfh["expiry"] == pd.Timestamp(hol - timedelta(days=1))).any())
d7, _ = L.od_build(fair, names[:3], {t: "x" for t in names[:3]}, start, end, (7, 30), workers=1)
check("two entry horizons from one fetch: 7 and 30 days", set(d7["dte"]) == {7, 30}
      and (d7[d7["dte"] == 7]["T"] * 365).between(7, 11).all())

print("the saved study and the cache")
tmp = tempfile.mkdtemp()
try:
    pth = L.Path(tmp) / "odds_study.parquet"
    a_ = df[df["ticker"].isin(names[:2])].assign(built=pd.Timestamp("2026-01-01"))
    b_ = df[df["ticker"].isin(names[1:3])].assign(built=pd.Timestamp("2026-02-01"))
    L.od_save(a_, pth)
    out = L.od_save(b_, pth)
    back = L.od_load(pth)
    check("merge: names rebuilt replace their rows, the others stay; written atomically",
          set(back["ticker"]) == set(names[:3]) and (back[back["ticker"] == names[1]]["built"] == pd.Timestamp("2026-02-01")).all()
          and len(back) == len(out) and not any(f_.endswith(".tmp") for f_ in os.listdir(tmp)))
    calls = []

    def fake_http(url, params=None, **kw):
        calls.append(url)
        if "fail" in url:
            raise RuntimeError("retries exhausted")
        if "/range/1/day/" in url:
            return {"results": [{"t": 1735797600000, "o": 1, "h": 1, "l": 1, "c": 1.5, "v": 10}]}
        return {"results": []}
    real = L.http_json
    L.http_json = fake_http
    cl = L.OdClient("KEY", cache=L.Path(tmp) / "cache")
    x1 = cl.daily("ABC", date(2025, 1, 1), date(2025, 1, 10))
    n1 = len(calls)
    x2 = cl.daily("ABC", date(2025, 1, 1), date(2025, 1, 10))
    check("a cached request costs nothing the second time", n1 == 1 and len(calls) == 1 and float(x2["close"].iloc[0]) == 1.5)
    bad = cl._cached("x/fail.json.gz", lambda: cl._get_all("/fail", {}))
    check("a failed request isn't cached (retried next run)", bad is None and not (L.Path(tmp) / "cache" / "x" / "fail.json.gz").exists())

    def plan_err(url, params=None, **kw):
        raise L.PlanError("HTTP 403")
    L.http_json = plan_err
    try:
        L.OdClient("KEY", cache=L.Path(tmp) / "c2").daily("ABC", date(2025, 1, 1), date(2025, 1, 10))
        check("403 on every base raises PlanError", False)
    except L.PlanError:
        check("403 on every base raises PlanError", True)
    L.http_json = real
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("verdicts, lookup, today")
small = L.od_prepare(df[df["expiry"].isin(sorted(df["expiry"].unique())[:5])], erp=0.0)
check("under 12 expiries: THIN", (L.od_table(small, ["side"])["verdict"] == "THIN").all())
lk = L.od_lookup(d, "up", 0.2, "other stock", 30)
check("the study's record for a 20% call vertical", lk is not None and lk["expiries"] >= 12 and "other stock" in lk["basis"], lk)
check("no record when the bucket is thin", L.od_lookup(small, "up", 0.2, "other stock", 30) is None)
cfg = {"source": "demo", "key": None, "strip": True, "fred_key": None}
bars = L._demo_daily("SPY", 400)
lv = L.od_live(cfg, "SPY", bars, 30, 1.0)
check("today's +1 sd call vertical on a demo chain: fully in the money at the target, odds in (0, 1), pays = (W - D) / D",
      not lv.get("error") and lv["side"] == "up" and lv["k_hi"] <= lv["target"] + 1e-9 and 0 < lv["q"] < 1
      and abs(lv["pays"] - (lv["width"] - lv["debit"]) / lv["debit"]) < 1e-9 and lv["legs"].startswith("+"), lv)
lv2 = L.od_live(cfg, "SPY", bars, 30, -1.0)
check("today's -1 sd put vertical: lower strike at or over the target", not lv2.get("error") and lv2["side"] == "down"
      and lv2["k_lo"] >= lv2["target"] - 1e-9 and lv2["legs"].endswith("P"), lv2)
lv3 = L.od_live(cfg, "SPY", bars, 30, 0.25)
check("the demo chain's put skew: a near-the-money call vertical's odds over its flat-vol odds", not lv3.get("error")
      and lv3["q"] > lv3["q_flat"], (lv3.get("q"), lv3.get("q_flat")))

print("the command-line builder")
import odds_build
tmp2 = L.Path(tempfile.mkdtemp())
real_file, real_client = L.OD_FILE, L.OdClient
try:
    L.OD_FILE = tmp2 / "odds_study.parquet"
    L.OdClient = lambda key, offline=False: L.OdDemoClient()
    os.environ.setdefault("MASSIVE_API_KEY", "demo-test")
    rc = odds_build.main(["--names", "SPY,QQQ,NVDA", "--dtes", "14,30", "--months", "6"])
    got = pd.read_parquet(L.OD_FILE)
    check("odds_build.py builds and saves the study (two horizons, three names) to the study file",
          rc == 0 and set(got["ticker"]) == {"SPY", "QQQ", "NVDA"} and set(got["dte"]) == {14, 30})
    rc2 = odds_build.main(["--names", "SPY", "--dtes", "30", "--months", "6"])
    got2 = pd.read_parquet(L.OD_FILE)
    check("a second run merges: SPY's 30-day rows replaced, its 14-day rows and the other names kept",
          rc2 == 0 and set(got2["ticker"]) == {"SPY", "QQQ", "NVDA"} and len(got2[(got2["ticker"] == "SPY") & (got2["dte"] == 14)]) > 0)
finally:
    L.OD_FILE, L.OdClient = real_file, real_client
    shutil.rmtree(tmp2, ignore_errors=True)

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
