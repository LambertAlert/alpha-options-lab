"""Planted-case tests for the Debit screen's price freshness: Massive timestamps, the mark and its session, the stock
snapshot spot, the freshest-spot pick, and the screen leaving out legs last printed in an earlier session.
Run: python test_fresh_prices.py"""
import math, warnings
from datetime import datetime, timedelta, timezone
import numpy as np

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


ET = L._ET
now = L.now_et()
today = now.date()
yday = today - timedelta(days=1)


def ns(d, h, m):
    return int(datetime(d.year, d.month, d.day, h, m, tzinfo=ET).timestamp() * 1e9)


print("timestamps")
t_ns = ns(today, 14, 31)
check("nanoseconds, milliseconds and seconds read as the same Eastern time",
      L.ts_et(t_ns) == L.ts_et(t_ns // 1_000_000) == L.ts_et(t_ns // 1_000_000_000)
      and (L.ts_et(t_ns).hour, L.ts_et(t_ns).minute) == (14, 31), L.ts_et(t_ns))
check("missing or zero is no time", L.ts_et(None) is None and L.ts_et(0) is None and L.ts_et("x") is None)

print("one contract (Options Starter shape: no quote, no trade)")


def raw(k, close, when, vwap=None, typ="call", oi=500, vol=50, spot=None, spot_when=None, exp_days=14):
    exp = (today + timedelta(days=exp_days)).isoformat()
    r = {"details": {"contract_type": typ, "expiration_date": exp, "strike_price": float(k),
                     "ticker": f"O:XYZ{exp.replace('-', '')[2:]}{typ[0].upper()}{int(k * 1000):08d}"},
         "day": {"close": close, "vwap": vwap if vwap is not None else close, "volume": vol,
                 "last_updated": when}, "implied_volatility": 0.30, "open_interest": oi,
         "greeks": {"delta": 0.5}}
    r["underlying_asset"] = {"ticker": "XYZ", "timeframe": "DELAYED"}
    if spot is not None:
        r["underlying_asset"]["price"] = spot
    if spot_when is not None:
        r["underlying_asset"]["last_updated"] = spot_when
    return r


c = L.extract_contract(raw(100, 2.5, ns(today, 14, 31), spot=101.2, spot_when=ns(today, 14, 40)), today)
check("the mark is the day bar's close, stamped with when it printed",
      c["mark"] == 2.5 and c["mark_src"] == "day_close" and c["mark_date"] == today and c["mark_time"].hour == 14, c)
check("the chain's underlying price and its time come through", c["spot"] == 101.2 and c["spot_time"].minute == 40
      and c["spot_timeframe"] == "DELAYED")
c0 = L.extract_contract(raw(100, 0, ns(today, 9, 0), vwap=2.4), today)
check("a zero close falls back to the VWAP", c0["mark"] == 2.4 and c0["mark_src"] == "day_vwap")
cz = L.extract_contract(raw(100, 0, None, vwap=0), today)
check("an all-zero day bar is no price", cz["mark"] is None and cz["mark_date"] is None)
co = L.extract_contract(raw(100, 2.1, ns(yday, 15, 59)), today)
check("a day bar from an earlier session keeps that session's date", co["mark_date"] == yday)
check("the latest session in a chain", L.chain_session([c, co, cz]) == today and L.chain_session([co, cz]) == yday
      and L.chain_session([cz]) is None)

print("stock snapshot spot")
calls = []


def fake_http(url, params=None, **kw):
    calls.append((url, params))
    tk = params["tickers"].split(",")
    out = []
    for t in tk:
        if t == "AAA":     # traded today: the latest minute bar
            out.append({"ticker": t, "min": {"c": 50.5, "t": ns(today, 14, 30) // 1_000_000}, "day": {"c": 50.4},
                        "prevDay": {"c": 49.0}, "updated": ns(today, 14, 31)})
        elif t == "BBB":   # minute bar not from today, day bar has a close
            out.append({"ticker": t, "min": {"c": 30.0, "t": ns(yday, 15, 59) // 1_000_000}, "day": {"c": 31.0},
                        "prevDay": {"c": 30.0}, "updated": ns(today, 10, 0)})
        elif t == "CCC":   # before the open: zeros, previous close only
            out.append({"ticker": t, "min": {}, "day": {"c": 0}, "prevDay": {"c": 20.0}})
        elif t == "DDD":
            out.append({"ticker": t, "error": "NOT_ENTITLED"})
        else:
            out.append({"ticker": t, "day": {"c": 10.0}, "updated": ns(today, 11, 0)})
    return {"status": "OK", "tickers": out}


real_http = L.http_json
L.http_json = fake_http
try:
    sp = L.massive_stock_spots(["AAA", "BBB", "CCC", "DDD"], "k")
    calls.clear()
    many = L.massive_stock_spots([f"T{i}" for i in range(150)], "k")
    n_calls = len(calls)
finally:
    L.http_json = real_http
check("traded today: the latest minute bar's close", sp["AAA"]["price"] == 50.5 and "minute" in sp["AAA"]["src"])
check("an old minute bar: today's day-bar close", sp["BBB"]["price"] == 31.0 and "day bar" in sp["BBB"]["src"])
check("before the open: the previous close, labeled", sp["CCC"]["price"] == 20.0 and "before the open" in sp["CCC"]["src"])
check("a name outside the plan is skipped", "DDD" not in sp)
check("100 names per request", n_calls == 2 and len(many) == 150, n_calls)

print("picking the spot")
fresh_chain = [L.extract_contract(raw(100, 2.5, ns(today, 14, 31), spot=101.0, spot_when=ns(today, 14, 45)), today)]
old_chain = [L.extract_contract(raw(100, 2.5, ns(today, 14, 31), spot=99.0, spot_when=ns(yday, 15, 59)), today)]
no_spot = [L.extract_contract(raw(100, 2.5, ns(today, 14, 31)), today)]
live = {"price": 100.6, "time": L.ts_et(ns(today, 14, 40)), "src": "stock snapshot, latest minute"}
p1 = L.pick_spot(fresh_chain, live, 98.0)
p2 = L.pick_spot(old_chain, live, 98.0)
p3 = L.pick_spot(no_spot, live, 98.0)
p4 = L.pick_spot(no_spot, None, 98.0)
check("the chain's underlying when it is the later one", p1[0] == 101.0 and p1[1].startswith("chain underlying"), p1)
check("the stock snapshot when the chain's underlying is older", p2[0] == 100.6 and p2[1] == live["src"], p2)
check("the stock snapshot when the chain has no underlying price", p3[0] == 100.6, p3)
check("the daily bar only when nothing else has a price, and labeled so", p4 == (98.0, "last daily bar close", None), p4)

print("the screen")
S0 = 100.0


def bs(k, T, s=0.3):
    return float(L.bs_call(S0, k, T, s))


def chain(tk, stale_strikes=(), all_old=False, with_spot=False):
    out = []
    for k in np.arange(90, 121, 2.5):
        when = ns(yday, 15, 50) if (all_old or k in stale_strikes) else ns(today, 13, 0) + int(k) * 60_000_000_000
        out.append(raw(k, round(bs(k, 14 / 365), 2), when, oi=800, vol=120,
                       spot=S0 if with_spot else None, spot_when=ns(today, 14, 45) if with_spot else None))
    return out


real_fetch = L.fetch_chain
planted = {"AAA": chain("AAA", stale_strikes=(105.0, 107.5)), "BBB": chain("BBB", with_spot=True)}
L.fetch_chain = lambda tk, dte_hi, source, key, spot, hv, strip, band=None: planted[tk]
try:
    live_sp = {"AAA": {"price": S0, "time": L.ts_et(ns(today, 14, 40)), "src": "stock snapshot, latest minute"}}
    args = ([("AAA", 90.0), ("BBB", 80.0)], {"AAA": 96.0, "BBB": 96.0}, {"AAA": 0.3, "BBB": 0.3}, "massive", "k", False,
            0, 30, 100.0, 0.0, 0.5)
    R, V = L.screen_debits(*args, fresh_only=True, live_spots=live_sp)
    R2, V2 = L.screen_debits(*args, fresh_only=False, live_spots=live_sp)
    planted["AAA"] = chain("AAA", all_old=True)
    planted["BBB"] = chain("BBB", all_old=True, with_spot=True)
    R3, V3 = L.screen_debits(*args, fresh_only=True, live_spots=live_sp)
finally:
    L.fetch_chain = real_fetch
ra = R.set_index("ticker")
check("spot comes from the snapshot, not yesterday's daily bar (96)", ra.loc["AAA", "spot"] == S0
      and ra.loc["AAA", "spot_src"] == "stock snapshot, latest minute", ra.loc["AAA", ["spot", "spot_src"]].to_dict())
check("or from the chain's own underlying", ra.loc["BBB", "spot"] == S0 and ra.loc["BBB", "spot_src"].startswith("chain underlying"))
check("the latest session in the chains is today", R.attrs["session"] == today.isoformat())
priced = [k for k in np.arange(90, 121, 2.5) if round(bs(k, 14 / 365), 2) > 0]
want = sum(1 for k in priced if k not in (105.0, 107.5)) / len(priced)
check("share of AAA's priced contracts that printed today", abs(ra.loc["AAA", "prints_this_session"] - want) < 1e-9,
      ra.loc["AAA", "prints_this_session"])
a_legs = V[V["ticker"] == "AAA"]
check("legs last printed yesterday are left out", len(a_legs) > 0 and not (a_legs["long_strike"].isin([105.0, 107.5]).any()
                                                                         or a_legs["short_strike"].isin([105.0, 107.5]).any()))
a2 = V2[V2["ticker"] == "AAA"]
flag = a2["long_strike"].isin([105.0, 107.5]) | a2["short_strike"].isin([105.0, 107.5])
check("with the switch off they stay in, flagged", flag.any() and (a2.loc[flag, "prior_session"]).all()
      and not a2.loc[~flag, "prior_session"].any())
check("each vertical says when its legs printed", V["printed"].str.contains("ET").all())
check("on a holiday or before the open (every print from the last session) nothing is left out",
      R3.attrs["session"] == yday.isoformat() and len(V3) == len(V2) and not V3["prior_session"].any(), (len(V3), len(V2)))

print("the session a delayed feed should show")
from datetime import datetime as _dt
real_now = L.now_et
try:
    wed = _dt(2026, 10, 28, 14, 53, tzinfo=ET)
    L.now_et = lambda: wed
    e1 = L.expected_session()
    L.now_et = lambda: wed.replace(hour=9, minute=40)
    e2 = L.expected_session()
    L.now_et = lambda: _dt(2026, 10, 26, 8, 0, tzinfo=ET)          # Monday before the open
    e3 = L.expected_session()
    L.now_et = lambda: _dt(2026, 10, 31, 12, 0, tzinfo=ET)         # Saturday
    e4 = L.expected_session()
finally:
    L.now_et = real_now
check("Wednesday afternoon: today; 9:40 (inside the delay): Tuesday; Monday before the open and Saturday: Friday",
      (e1.isoformat(), e2.isoformat(), e3.isoformat(), e4.isoformat()) == ("2026-10-28", "2026-10-27", "2026-10-23", "2026-10-30"),
      (e1, e2, e3, e4))

print("demo data still screens")
R4, V4 = L.screen_debits([("NVDA", 90.0), ("AAPL", 80.0)], {"NVDA": 120.0, "AAPL": 200.0}, {"NVDA": 0.45, "AAPL": 0.25},
                         "demo", None, True, 0, 21, 50.0, 0.0, 0.5)
check("demo chains: spots from the chain, verticals found, nothing flagged",
      (R4["spot_src"].str.startswith("chain underlying")).all() and len(V4) > 0 and not V4["prior_session"].any()
      and R4.attrs["session"] is None)

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
