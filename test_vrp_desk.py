"""Planted-case tests for Options > VRP desk (American): the tree, Barone-Adesi-Whaley, American IV, dividends and the
rate, the HAR-RV forecast, one name's read, the spreads, and the exit and hedge simulator.
Run: python test_vrp_desk.py"""
import math, warnings
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


def bs_closed(S, K, T, s, r, call, pv=0.0):
    Sx = S - pv
    d1 = (math.log(Sx / K) + (r + 0.5 * s * s) * T) / (s * math.sqrt(T))
    d2 = d1 - s * math.sqrt(T)
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    c = Sx * N(d1) - K * math.exp(-r * T) * N(d2)
    return c if call else c - Sx + K * math.exp(-r * T)


print("pricing: the tree")
for S, K, T, s, r, cp, dv in ((100, 100, 0.5, 0.25, 0.05, True, []), (100, 110, 1.0, 0.30, 0.03, False, []),
                              (100, 95, 0.6, 0.25, 0.05, True, [(0.25, 2.0), (0.5, 2.0)]),
                              (50, 55, 0.3, 0.45, 0.04, False, [(0.1, 0.5)])):
    pv = sum(D * math.exp(-r * t) for t, D in dv if t < T)
    eu = L.av_tree(S, K, T, s, r, cp, dv, N=800, american=False)["price"][0]
    check(f"European tree = Black-Scholes on the escrowed stock (K={K}, divs={len(dv)})",
          abs(eu - bs_closed(S, K, T, s, r, cp, pv)) < 0.01, f"{eu:.4f} vs {bs_closed(S, K, T, s, r, cp, pv):.4f}")
am_c = L.av_tree(100, 100, 1.0, 0.2, 0.05, True, (), N=600)["price"][0]
check("an American call with no dividend is worth the European", abs(am_c - bs_closed(100, 100, 1.0, 0.2, 0.05, True)) < 0.01, f"{am_c:.4f}")
h1, h2 = (L.av_tree(50, 50, 5 / 12, 0.4, 0.10, False, (), N=n_)["price"][0] for n_ in (1000, 2000))
check("Hull's American put (S=K=50, r=10%, 40% vol, 5 months) is about 4.28 and converges",
      abs(h2 - 4.28) < 0.01 and abs(h1 - h2) < 0.003, f"{h1:.4f} {h2:.4f}")
eu_p = L.av_tree(50, 50, 5 / 12, 0.4, 0.10, False, (), N=1000, american=False)["price"][0]
check("the American put is worth more than the European", h1 > eu_p + 0.15, f"{h1:.3f} vs {eu_p:.3f}")
o = L.av_tree(100, 80, 0.4, 0.2, 0.03, True, [(0.2, 3.0)], N=600, with_euro=True)
check("a deep in-the-money call with a big dividend carries an early-exercise premium", o["price"][0] - o["euro"][0] > 0.5,
      f"{o['price'][0] - o['euro'][0]:.3f}")
check("with_euro matches the European tree", abs(o["euro"][0] - L.av_tree(100, 80, 0.4, 0.2, 0.03, True, [(0.2, 3.0)], N=600, american=False)["price"][0]) < 1e-9)
g = L.av_tree(100, 100, 0.25, 0.3, 0.04, np.array([True, False]), (), N=300, greeks=True)
d1 = (math.log(1) + (0.04 + 0.045) * 0.25) / (0.3 * 0.5)
nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
gam = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (100 * 0.3 * 0.5)
check("tree delta and gamma match Black-Scholes on a call with no dividend",
      abs(g["delta"][0] - nd1) < 0.004 and abs(g["gamma"][0] / gam - 1) < 0.03, f"{g['delta'][0]:.4f} {nd1:.4f} {g['gamma'][0]:.4f} {gam:.4f}")
check("put delta is negative and theta is a daily cost", -0.6 < g["delta"][1] < -0.3 and (g["theta"] < 0).all() and (g["theta"] > -0.2).all())
bat = L.av_tree(100.0, np.array([90, 100, 110.0]), np.array([0.1, 0.5, 1.0]), np.array([0.2, 0.3, 0.4]), 0.05,
                np.array([True, False, True]), (), N=200)["price"]
one = [L.av_tree(100.0, k, t, s, 0.05, c, (), N=200)["price"][0] for k, t, s, c in ((90, .1, .2, True), (100, .5, .3, False), (110, 1, .4, True))]
check("batch pricing equals one at a time", np.allclose(bat, one))

print("pricing: Barone-Adesi-Whaley")
rng = np.random.default_rng(0)
n = 120
K = rng.uniform(80, 120, n); T = rng.uniform(0.05, 0.6, n); sg = rng.uniform(0.15, 0.5, n); cp = rng.random(n) < 0.5
tr = L.av_tree(100.0, K, T, sg, 0.045, cp, (), N=1000)["price"]
bw = L.av_baw(100.0, K, T, sg, 0.045, 0.0, cp)
check("calls with no yield are European", np.max(np.abs(bw[cp] - tr[cp])) < 0.01, f"{np.max(np.abs(bw[cp] - tr[cp])):.4f}")
check("puts within 10 cents and 2.5% of the tree (strikes ±20%, 0.05-0.6 years)",
      np.max(np.abs(bw[~cp] - tr[~cp])) < 0.10 and np.max(np.abs(bw[~cp] / tr[~cp] - 1)[tr[~cp] > 0.5]) < 0.025,
      f"{np.max(np.abs(bw[~cp] - tr[~cp])):.4f}")
dense = [(t, 100 * 0.03 / 52) for t in np.arange(1 / 104, 1.0, 1 / 52)]
tc = L.av_tree(100, np.array([90, 100, 110.0]), 0.5, 0.25, 0.045, True, dense, N=800)["price"]
bc = L.av_baw(100, np.array([90, 100, 110.0]), 0.5, 0.25, 0.045, 0.03, True)
check("calls with a 3% yield match a tree with weekly dividends", np.max(np.abs(tc - bc)) < 0.03, f"{tc} {bc}")
check("never under intrinsic", (L.av_baw(100, np.array([150.0, 60.0]), 0.5, 0.3, 0.05, 0.0, np.array([False, True])) >= np.array([50.0, 40.0]) - 1e-9).all())

print("pricing: implied vol")
Ke = np.array([80, 95, 100, 105, 125.0]); Te = np.array([0.1, 0.3, 0.5, 0.8, 1.2]); se = np.array([0.4, 0.3, 0.25, 0.22, 0.2])
ce = np.array([False, True, False, True, True])
pe = np.array([bs_closed(100, k, t, s, 0.04, c) for k, t, s, c in zip(Ke, Te, se, ce)])
check("European IV round trip", np.max(np.abs(L.av_bs_iv(pe, 100, Ke, Te, 0.04, ce) - se)) < 1e-4)
check("a price under the no-arbitrage bound has no IV", np.isnan(L.av_bs_iv(np.array([0.5]), 100, 80.0, 0.5, 0.04, True)[0]))
dv = [(0.15, 0.9), (0.4, 0.9)]
Ka = np.array([85, 95, 100, 105, 115, 85, 100, 115.0]); ca = np.array([1, 1, 1, 1, 1, 0, 0, 0], bool)
sa = np.array([0.33, 0.30, 0.28, 0.27, 0.26, 0.36, 0.29, 0.25])
pa = L.av_tree(100, Ka, 0.5, sa, 0.045, ca, dv, N=1500)["price"]
ia = L.av_american_iv(pa, 100, Ka, 0.5, 0.045, ca, dv)
check("American IV round trip with dividends (inside 0.15 vol pts)", np.nanmax(np.abs(ia["iv"] - sa)) < 0.0015,
      f"{np.nanmax(np.abs(ia['iv'] - sa)):.5f}")
check("the early-exercise premium is non-negative and biggest on the in-the-money put", (ia["eep"] >= 0).all() and ia["eep"][7] == ia["eep"].max())
naive = L.av_bs_iv(pa, 100, Ka, 0.5, 0.045, ca, sum(D * math.exp(-0.045 * t) for t, D in dv))
check("the European inversion overstates the in-the-money put's IV", naive[7] > sa[7] + 0.003, f"{naive[7]:.4f} vs {sa[7]}")
bad = L.av_american_iv(np.array([4.0, np.nan]), 100, np.array([110.0, 100.0]), 0.3, 0.045, np.array([False, True]))
check("a print under intrinsic, or no print, has no IV", np.isnan(bad["iv"]).all())
q = L.av_yield_equiv(100, [(0.1, 1.0), (0.35, 1.0)], [0.05, 0.2, 0.5], 0.04)
pv = [0.0, math.exp(-0.004), math.exp(-0.004) + math.exp(-0.014)]
check("the equivalent yield takes out the same dividends", all(abs(100 * (1 - math.exp(-q_ * t_)) - p_) < 1e-6 for q_, t_, p_ in zip(q, (0.05, 0.2, 0.5), pv)))

print("dividends and the rate")
dd = L.av_dividends("SPY", "demo", None, 600.0, horizon_days=400)
gaps = np.diff([d_.toordinal() for d_ in dd["ex_date"]])
check("demo SPY: quarterly, 1.2% a year", len(dd) >= 4 and (gaps == 91).all() and abs(dd["amount"].iloc[0] - 600 * 0.012 / 4) < 1e-3)
today = date.today()
planted = [{"ticker": "XYZ", "ex_dividend_date": (today - timedelta(days=300)).isoformat(), "cash_amount": 0.50, "frequency": 4,
            "distribution_type": "recurring", "currency": "USD"},
           {"ticker": "XYZ", "ex_dividend_date": (today - timedelta(days=30)).isoformat(), "cash_amount": 0.55, "frequency": 4,
            "distribution_type": "recurring", "currency": "USD"},
           {"ticker": "XYZ", "ex_dividend_date": (today - timedelta(days=10)).isoformat(), "cash_amount": 2.00, "frequency": 0,
            "distribution_type": "special", "currency": "USD"},
           {"ticker": "XYZ", "ex_dividend_date": (today + timedelta(days=60)).isoformat(), "cash_amount": 0.55, "frequency": 4,
            "distribution_type": "recurring", "currency": "USD"},
           {"ticker": "XYZ", "ex_dividend_date": (today + timedelta(days=20)).isoformat(), "cash_amount": 9.0, "frequency": 4,
            "distribution_type": "recurring", "currency": "CAD"}]
real_get = L.massive_get_all
L.massive_get_all = lambda path, params, key, max_pages=20: planted if path == "/stocks/v1/dividends" else []
try:
    md_ = L.av_dividends("XYZ", "massive", "k", 50.0, horizon_days=330)
finally:
    L.massive_get_all = real_get
dec = md_[md_["kind"] == "declared"]
proj = md_[md_["kind"] == "projected"]
check("declared ex-dates are kept, other currencies dropped", len(dec) == 1 and dec["amount"].iloc[0] == 0.55 and 9.0 not in set(md_["amount"]))
check("the last regular dividend is carried forward quarterly, not next to a declared one, and specials aren't",
      len(proj) >= 2 and (proj["amount"] == 0.55).all()
      and all(abs((p_ - dec["ex_date"].iloc[0]).days) > 30 for p_ in proj["ex_date"]) and 2.0 not in set(md_["amount"]), md_.to_dict("records"))
dl = L.av_div_list(md_, today)
check("the dividend list is in years ahead", all(t_ > 0 for t_, _ in dl) and abs(dl[0][0] - (md_["ex_date"].iloc[0] - today).days / 365) < 1e-9)
r0, txt0 = L.av_rate({"source": "demo", "fred_key": "x"})
check("demo or no key: the default rate", r0 == L.AV_RATE_DEFAULT and "assumed" in txt0)
real_fs = L.fred_series
L.fred_series = lambda sid, key, start: pd.Series([5.0], index=[pd.Timestamp(today)]) if sid == "DTB3" else pd.Series(dtype=float)
try:
    L._compute_store().clear()
    r1, txt1 = L.av_rate({"source": "massive", "fred_key": "x"})
finally:
    L.fred_series = real_fs
check("DTB3 is turned from a discount yield into a continuous rate", abs(r1 + math.log(1 - 0.05 * 91 / 360) / (91 / 365)) < 1e-12 and "DTB3" in txt1,
      f"{r1} {txt1}")

print("the vol forecast")
idx = pd.bdate_range("2021-01-04", periods=4)
bar = pd.DataFrame({"open": [100, 101, 99, 100.0], "high": [102, 103, 101, 100.0], "low": [99, 100, 97, 100.0],
                    "close": [101, 102, 98, 100.5]}, index=idx)
v = L.av_daily_var(bar)
want = math.log(101 / 101) ** 2 + 0.5 * math.log(103 / 100) ** 2 - (2 * math.log(2) - 1) * math.log(102 / 101) ** 2
check("daily variance = overnight gap squared + Garman-Klass", abs(v.iloc[0] - want) < 1e-12, f"{v.iloc[0]} {want}")
check("a bar with high = low falls back to close-to-close, floored", v.iloc[2] >= v.median() * 0.05 - 1e-15 and len(v) == 3)
rng = np.random.default_rng(11)


def har_names(k, n_, seed):
    out = {}
    rg = np.random.default_rng(seed)
    for j in range(k):
        lv = np.empty(n_)
        lv[:30] = math.log(0.0002)
        base = math.log(0.0001 * (1 + j))
        for t in range(30, n_):
            m_ = np.mean(lv[t - 22:t]); w_ = np.mean(lv[t - 5:t])
            lv[t] = 0.25 * base + 0.35 * m_ + 0.25 * w_ + 0.15 * lv[t - 1] + rg.normal(0, 0.35)
        vv = np.exp(lv) * rg.chisquare(3, n_) / 3
        out[f"N{j}"] = pd.Series(vv, index=pd.bdate_range("2019-01-01", periods=n_))
    return out


VAR = har_names(6, 1500, 3)
M = L.av_har_fit(VAR)
check("HAR fits every horizon", sorted(M["coefs"]) == list(L.AV_HAR_H) and all(np.isfinite(b).all() for b in M["coefs"].values()))
check("persistence: the week, month and year terms carry the weight", all(M["coefs"][h][2:].sum() > 0.6 for h in M["coefs"]))
check("out of sample it beats last month's realized vol on a persistent process",
      all(M["oos"][h]["qlike_har"] < M["oos"][h]["qlike_rv21"] for h in (21, 63)), {h: (round(o_["qlike_har"], 3), round(o_["qlike_rv21"], 3)) for h, o_ in M["oos"].items()})
fc = L.av_har_forecast(M, VAR["N0"])
check("a forecast for every horizon, in annual vol", fc and all(0.01 < x < 3 for x in fc.values()))
lo_, hi_ = L.av_vol_at(fc, 2), L.av_vol_at(fc, 500)
mid = L.av_vol_at(fc, 30)
w21, w42 = fc[21] ** 2 * 21, fc[42] ** 2 * 42
check("between horizons: total variance interpolated; outside: flat",
      lo_ == fc[5] and hi_ == fc[126] and abs(mid - math.sqrt((w21 + (w42 - w21) * 9 / 21) / 30)) < 1e-12)
check("forecast error grows shorter, from the out-of-sample record", L.av_forecast_err(M, 5) > L.av_forecast_err(M, 126) > 0)
check("too little history: no forecast", L.av_har_forecast(M, VAR["N0"].iloc[:100]) is None)

print("one name")
SPOT, R = 100.0, 0.04
FC_VOL = 0.20
ATM_IV = 0.26                                        # implied 30% above the forecast: ln 1.3 = 0.262
DIVS = pd.DataFrame([{"ex_date": today + timedelta(days=40), "amount": 0.6, "kind": "declared"},
                     {"ex_date": today + timedelta(days=131), "amount": 0.6, "kind": "projected"}])
DL = L.av_div_list(DIVS, today)


def smile(x):
    return ATM_IV * (1 - 0.6 * x + 1.5 * x * x)


def planted_chain(stale=None, dislocate=None, event=None):
    cons = []
    for dte in (10, 24, 38, 52, 80, 115):
        T_ = dte / 365
        pvd = sum(D * math.exp(-R * t) for t, D in DL if t < T_)
        F = (SPOT - pvd) * math.exp(R * T_)
        for k in np.arange(70, 130.1, 2.5):
            for typ in ("call", "put"):
                x = math.log(k / F)
                iv = smile(x)
                if event and dte >= event[0]:
                    iv = math.sqrt(iv * iv + event[1] ** 2 / T_)
                if dislocate and (dte, typ, k) == dislocate:
                    iv += 0.04
                px = float(L.av_tree(SPOT, k, T_, iv, R, typ == "call", DL, N=300)["price"][0])
                feed = iv
                if stale and (dte, typ, k) == stale:
                    px = px * 1.8 + 0.5
                cons.append({"occ": f"X{dte}{typ}{k}", "underlying": "XYZ", "type": typ, "strike": float(k),
                             "expiration": (today + timedelta(days=dte)).isoformat(), "dte": dte, "delta": None, "iv": feed,
                             "oi": 100.0, "volume": 10.0, "bid": None, "ask": None, "mid": None, "last": px, "mark": round(px, 4),
                             "mark_src": "last", "spot": SPOT})
    return cons


real_fc, real_err = L.av_har_forecast, L.av_forecast_err
L.av_har_forecast = lambda model, v: {h: FC_VOL for h in L.AV_HAR_H}
L.av_forecast_err = lambda model, s: 0.15
VV = pd.Series(np.full(400, FC_VOL ** 2 / 252), index=pd.bdate_range("2024-01-01", periods=400))
MM = {"coefs": {}, "s2": {h: 1e-6 for h in L.AV_HAR_H}, "oos": {}}
try:
    rd = L.av_name_read("XYZ", planted_chain(stale=(38, "call", 105.0), dislocate=(52, "put", 92.5)), SPOT, VV, MM, DIVS, R)
    rd_ev = L.av_name_read("XYZ", planted_chain(event=(38, 0.06)), SPOT, VV, MM, DIVS, R, event_sd_real=0.03)
    rd_fair = None
finally:
    L.av_har_forecast, L.av_forecast_err = real_fc, real_err
tm = rd["term"]
check("ATM American IV recovered at every expiry (inside 0.3 pts)", (tm["atm_iv"] - ATM_IV).abs().max() < 0.003, tm["atm_iv"].round(4).tolist())
check("VRP = ln(implied / forecast)", abs(rd["vrp30_log"] - math.log(ATM_IV / FC_VOL)) < 0.015 and abs(rd["vrp30_pts"] - 6.0) < 0.4,
      f"{rd['vrp30_log']:.4f} {rd['vrp30_pts']:.2f}")
check("signal: sell premium; z = VRP over the forecast error", L.av_signal(rd) == "SELL PREMIUM" and abs(rd["z30"] - rd["vrp30_log"] / 0.15) < 1e-9)
ct = rd["contracts"]
st_row = ct[(ct["dte"] == 38) & (ct["type"] == "call") & (ct["strike"] == 105.0)].iloc[0]
check("a stale print (IV far off the feed's) is replaced by the feed", st_row["iv_src"] == "feed", st_row[["iv_mark", "iv_feed"]].to_dict())
otm = ct[((ct["type"] == "put") & (ct["strike"] <= SPOT)) | ((ct["type"] == "call") & (ct["strike"] >= SPOT))]
dis = otm[(otm["dte"] == 52) & (otm["type"] == "put") & (otm["strike"] == 92.5)].iloc[0]
rest = otm[(otm["iv_src"] == "mark") & ~((otm["dte"] == 52) & (otm["strike"] == 92.5))]
check("a dislocated print stands 4 pts off its smile; the rest sit on it",
      abs(dis["resid_iv"] - 0.04) < 0.008 and rest["resid_iv"].abs().quantile(0.9) < 0.004, f"{dis['resid_iv']:.4f} {rest['resid_iv'].abs().max():.4f}")
check("fair IV keeps the skew: fair / smile = forecast / ATM at each strike",
      np.allclose(ct["iv_fair"] / ct["iv_smooth"], [dict(zip(tm["dte"], tm["fair_vol"] / tm["atm_iv"]))[d] for d in ct["dte"]]))
check("rich smile: every contract's market value is over its fair value", (ct["edge_vrp"] > -1e-9).all())
itm_put = ct[(ct["type"] == "put") & (ct["strike"] >= 115) & (ct["dte"] == 115)]
check("the deep in-the-money put carries the biggest early-exercise premium", itm_put["eep"].max() >= ct["eep"].max() - 1e-9)
fd = ct[ct["iv_src"] == "feed"]
check("next ex-dividend; the feed fills in only where a print carries no vol (under a nickel, or under a nickel of "
      "time value) and for the stale one",
      rd["next_ex"] == (today + timedelta(days=40)).isoformat()
      and ((fd["mark"] < 0.05) | (fd["mark"] - fd["intrinsic"] < 0.05) | (fd["mark"] - fd.apply(lambda r_: abs(
          SPOT - sum(D * math.exp(-R * t) for t, D in DL if t < r_["dte"] / 365) - r_["strike"] * math.exp(-R * r_["dte"] / 365)), axis=1) < 0.05)
           | ((fd["dte"] == 38) & (fd["type"] == "call") & (fd["strike"] == 105.0))).all(),
      fd.assign(tv=fd["mark"] - fd["intrinsic"])[["dte", "type", "strike", "mark", "tv"]].sort_values("tv").tail(4).to_dict("records"))
tme = rd_ev["term"]
check("an event in the term structure is found", rd_ev["event"] is not None and rd_ev["event"]["dte"] == 38, rd_ev["event"])
aft = tme[tme["dte"] >= 38]
check("the forecast adds the name's own event variance after it",
      tme["event_in"].tolist() == [d >= 38 for d in tme["dte"]] and np.allclose(aft["fair_var"], FC_VOL ** 2 * aft["T"] + 0.03 ** 2))

print("structures")
d0 = L.av_default_dte(rd)
check("default expiry: nearest 45 days among 21-75", d0 == 52 or d0 == 38, d0)
S = L.av_build_structures(rd, 38)
check("all six structures build", set(S) == set(L.AV_STRUCTS), sorted(S))
pcs = S["put credit spread"]
e38 = ct[ct["dte"] == 38]
sp_ = e38[(e38["type"] == "put") & (e38["strike"] == pcs[0]["strike"])]["delta"].iloc[0]
check("put credit spread: short near -0.25 delta, wing below it", pcs[0]["qty"] == -1 and abs(sp_ + 0.25) < 0.06
      and pcs[1]["strike"] < pcs[0]["strike"] and pcs[1]["qty"] == 1, f"{sp_:.3f}")
check("iron condor is both credit spreads", S["iron condor"] == S["put credit spread"] + S["call credit spread"])
cal = S["calendar (ATM)"]
check("calendar: sells this expiry, buys the one about a month out, same strike near spot",
      cal[0]["dte"] == 38 and cal[1]["dte"] == 80 and cal[0]["strike"] == cal[1]["strike"] and abs(cal[0]["strike"] - SPOT) <= 1.25
      and cal[0]["qty"] == -1, cal)
ev = L.av_eval_structure(rd, "put credit spread", pcs)
w = pcs[0]["strike"] - pcs[1]["strike"]
check("credit spread: max loss = width - credit, max gain = credit", abs(ev["max_loss"] - (w - ev["credit"])) < 0.02
      and abs(ev["max_gain"] - ev["credit"]) < 1e-9, f"{ev['max_loss']:.3f} {w - ev['credit']:.3f}")
hand = sum(l_["qty"] * (l_["value_fair"] - l_["value_mkt"]) for l_ in ev["legs"])
check("edge = sum of qty x (fair - market), positive for selling a rich smile", abs(ev["edge"] - hand) < 1e-12 and ev["edge"] > 0)
check("P(profit) sits between 0 and 1 and above a coin flip for a 25-delta credit spread", 0.5 < ev["pop"] < 0.95, ev["pop"])
cds = L.av_eval_structure(rd, "call debit spread", S["call debit spread"])
check("debit spread: max loss = debit, edge negative when the smile is rich", abs(cds["max_loss"] - cds["debit"]) < 0.02 and cds["edge"] < 0)
check("costs: half the spread in and out on each leg, capped by the stock price",
      abs(ev["costs"] - 2 * sum(float(L.av_half_spread(l_["value_mkt"], SPOT, "stock", 0.02)) + 0.0065 for l_ in ev["legs"])) < 1e-9)
check("half-spread: a share of the price, capped at bp of the stock, never under a cent",
      abs(float(L.av_half_spread(10.0, 500.0, "etf", 0.02)) - 0.05) < 1e-12 and float(L.av_half_spread(0.10, 500.0, "etf", 0.02)) == 0.01
      and abs(float(L.av_half_spread(2.0, 100.0, "stock", 0.02)) - 0.04) < 1e-12)
ccs = L.av_eval_structure(rd, "call", [{"type": "call", "strike": 90.0, "dte": 52, "expiration": "", "qty": -1},
                                       {"type": "call", "strike": 100.0, "dte": 52, "expiration": "", "qty": 1}])
check("a short in-the-money call over an ex-dividend date is flagged", any("ex-dividend" in f_ for f_ in ccs["flags"]), ccs["flags"])
dip = L.av_eval_structure(rd, "put", [{"type": "put", "strike": 127.5, "dte": 115, "expiration": "", "qty": -1},
                                      {"type": "put", "strike": 120.0, "dte": 115, "expiration": "", "qty": 1}])
check("a short deep in-the-money put is flagged for early assignment", any("early assignment" in f_ for f_ in dip["flags"]), dip["flags"])

print("the simulator")
rng = np.random.default_rng(5)
CL = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.2 / math.sqrt(252), 1500))), index=pd.bdate_range("2020-01-01", periods=1500))
MM2 = {"coefs": {}, "s2": {h: 1e-6 for h in L.AV_HAR_H}, "oos": {}}


def flat_read(atm, fair, r=0.0, divs=(), is_etf=False):
    """A read with a flat smile, for checks the simulator should pass exactly."""
    dtes = [38, 80]
    term = pd.DataFrame({"dte": dtes, "expiration": ["", ""], "T": [d / 365 for d in dtes], "atm_iv": [atm, atm],
                         "fair_vol": [fair, fair]})
    rows = []
    for d in dtes:
        for k in np.arange(70, 131, 2.5):
            for typ in ("call", "put"):
                rows.append({"dte": d, "type": typ, "strike": float(k)})
    return {"spot": 100.0, "r": r, "divs": list(divs), "term": term, "fits": {d: np.array([0.0, 0.0, atm]) for d in dtes},
            "is_etf": is_etf}


legs = [{"type": "put", "strike": 95.0, "dte": 38, "qty": -1}, {"type": "put", "strike": 85.0, "dte": 38, "qty": 1}]
px0 = L.av_baw(100.0, np.array([95.0, 85.0]), 38 / 365, 0.2, 0.0, 0.0, np.array([False, False]))
net = float(-px0[0] + px0[1])
ste = {"legs": legs, "net": net, "max_loss": 10 + net, "max_gain": -net}
rd0 = flat_read(0.2, 0.2)
sim = L.av_simulate(rd0, ste, CL, MM2, {"n": 6000, "seed": 3, "cost_frac": 0.0, "fee": 0.0})
hold = sim["runs"]["hold"]["pnl"]
se = hold.std() / math.sqrt(len(hold))
check("fairly priced, no rate, no dividends: holding to expiry earns about nothing but the cent-wide spread",
      abs(hold.mean() + 2.0) < 3.5 * se, f"{hold.mean():.2f} ± {se:.2f}")
check("seven rules on the same paths", list(sim["table"]["key"]) == [k for k, _ in L.AV_RULES])
sim_b = L.av_simulate(rd0, ste, CL, MM2, {"n": 6000, "seed": 3, "cost_frac": 0.0, "fee": 0.0})
check("same seed, same answer", sim_b["table"].equals(sim["table"]))
rich = flat_read(0.30, 0.20)
net_r = float(-L.av_baw(100.0, 95.0, 38 / 365, 0.3, 0.0, 0.0, False)[0] + L.av_baw(100.0, 85.0, 38 / 365, 0.3, 0.0, 0.0, False)[0])
ste_r = {"legs": legs, "net": net_r, "max_loss": 10 + net_r, "max_gain": -net_r}
sr = L.av_simulate(rich, ste_r, CL, MM2, {"n": 3000, "seed": 4})
T_ = sr["table"].set_index("key")
check("selling a rich put spread: holding earns the gap", T_.loc["hold", "er"] > 15, T_.loc["hold", "er"])
runs = sr["runs"]
tg = runs["tp"]["why"] == "target"
check("take-profit exits happen at 50% of the credit or better before costs",
      tg.any() and (runs["tp"]["pnl"][tg] / 100 + 0.2 >= 0.5 * sr["credit"] - 1e-6).all())
sp_x = runs["stop"]["why"] == "stop"
check("stops happen at 2x the credit or worse", sp_x.any() and (runs["stop"]["pnl"][sp_x] / 100 <= -2 * sr["credit"] + 0.1).all())
check("the VRP-gap exit fires when IV corrects", T_.loc["vrp", "vrp"] > 0.5 and sr["gap0"] > 0.2, (T_.loc["vrp", "vrp"], sr["gap0"]))
check("a delta hedge cuts the spread of outcomes", T_.loc["hedged", "sd"] < 0.8 * T_.loc["combined", "sd"], (T_.loc["hedged", "sd"], T_.loc["combined", "sd"]))
fan_c = sr["fan"]
s_nc = L.av_simulate(rich, ste_r, CL, MM2, {"n": 3000, "seed": 4, "half_life": 0})
check("with a half-life IV settles toward forecast x normal premium; with none it doesn't",
      abs(fan_c["iv_q50"].iloc[-1] - fan_c["target"].iloc[0]) < abs(s_nc["fan"]["iv_q50"].iloc[-1] - fan_c["target"].iloc[0]) - 0.03,
      (fan_c["iv_q50"].iloc[-1], s_nc["fan"]["iv_q50"].iloc[-1], fan_c["target"].iloc[0]))
check("hold to expiry doesn't depend on the IV path when nothing is assigned",
      abs(s_nc["runs"]["hold"]["pnl"].mean() - runs["hold"]["pnl"].mean()) < 0.5 + 1e-9 or
      (runs["hold"]["why"] == "assigned").any(), (s_nc["runs"]["hold"]["pnl"].mean(), runs["hold"]["pnl"].mean()))
deep = flat_read(0.20, 0.20, r=0.08)
legs_d = [{"type": "put", "strike": 110.0, "dte": 80, "qty": -1}, {"type": "put", "strike": 100.0, "dte": 80, "qty": 1}]
v_d = L.av_baw(100.0, np.array([110.0, 100.0]), 80 / 365, 0.2, 0.08, 0.0, np.array([False, False]))
ste_d = {"legs": legs_d, "net": float(-v_d[0] + v_d[1]), "max_loss": 10.0, "max_gain": float(v_d[0] - v_d[1])}
sd_ = L.av_simulate(deep, ste_d, CL, MM2, {"n": 2000, "seed": 1})
check("a short in-the-money put at an 8% rate gets assigned early on some paths", sd_["table"].set_index("key").loc["hold", "assigned"] > 0.05,
      sd_["table"].set_index("key").loc["hold", "assigned"])
divr = flat_read(0.20, 0.20, r=0.04, divs=[(10 / 365, 3.0)])
legs_c = [{"type": "call", "strike": 90.0, "dte": 38, "qty": -1}, {"type": "call", "strike": 100.0, "dte": 38, "qty": 1}]
v_c = L.av_baw(100.0, np.array([90.0, 100.0]), 38 / 365, 0.2, 0.04, 0.0, np.array([True, True]))
ste_c = {"legs": legs_c, "net": float(-v_c[0] + v_c[1]), "max_loss": 10.0, "max_gain": float(v_c[0] - v_c[1])}
sc_ = L.av_simulate(divr, ste_c, CL, MM2, {"n": 2000, "seed": 1})
ac = sc_["runs"]["hold"]
check("a short in-the-money call is assigned the day before a $3 ex-dividend", (ac["why"] == "assigned").mean() > 0.3
      and np.median(ac["days"][ac["why"] == "assigned"]) <= 7, ((ac["why"] == "assigned").mean(), np.median(ac["days"][ac["why"] == "assigned"])))
check("too little history: no simulation", L.av_simulate(rd0, ste, CL.iloc[:100], MM2) is None)

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
