"""Planted-case tests for the pricer audit: the option ticker format, parsing real Massive responses (an AAOI listing
and a put's daily bars, saved from the API), picking the listed contracts, the disk cache (expired contracts kept, live
ones fetched again), a real implied vol from those prints, the demo truth recovered (IV = 1.30 x realized), a spread's
return from the prints by hand, the model/prints price ratios, and the per-setup verdicts on planted biases.
Run: python test_audit.py"""
import os
import shutil
import tempfile
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
TMP = tempfile.mkdtemp(prefix="au_test_")
os.environ["LAB_OPT_BARS"] = os.path.join(TMP, "opt_bars")
os.environ["LAB_HESTON_FILE"] = os.path.join(TMP, "heston_fit.json")
os.environ["PLAYBOOK_DATA"] = TMP
import alpha_options_lab as L
import playbook as PB

PASS, FAIL = 0, []


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


# Saved from Massive (Nov 7 2026): /v3/reference/options/contracts?underlying_ticker=AAOI&as_of=2025-09-15&... and
# /v2/aggs/ticker/O:AAOI250926P00030000/range/1/day/2025-09-12/2025-09-26, and AAOI's own daily bars.
LISTING = [{"contract_type": "put", "expiration_date": e, "strike_price": k, "ticker": f"O:AAOI{e[2:4]}{e[5:7]}{e[8:]}P{int(k * 1000):08d}",
            "underlying_ticker": "AAOI", "shares_per_contract": 100}
           for e in ("2025-09-19", "2025-09-26") for k in (28.0, 28.5, 29.0, 30.0, 31.0)]
LISTING.append({"contract_type": "put", "expiration_date": "2025-09-26", "strike_price": 29.5,
                "ticker": "O:AAOI1250926P00029500", "underlying_ticker": "AAOI", "shares_per_contract": 50})
BARS = {"results": [dict(zip(("v", "vw", "o", "c", "h", "l", "t", "n"), row)) for row in (
    (11, 2.7236, 2.82, 2.55, 2.82, 2.55, 1757908800000, 6), (3, 2.3433, 2.37, 2.34, 2.37, 2.32, 1758081600000, 3),
    (26, 2.2462, 2.15, 2.1, 2.55, 2.1, 1758168000000, 14), (101, 1.7579, 1.71, 2.0, 2.0, 1.7, 1758254400000, 15),
    (310, 1.3031, 1.77, 1.11, 1.85, 1.05, 1758513600000, 45), (73, 1.4521, 1.18, 2.0, 2.0, 1.0, 1758600000000, 23),
    (5, 3.07, 2.35, 3.25, 3.25, 2.35, 1758686400000, 2), (23, 4.4757, 4.6, 3.94, 4.6, 3.94, 1758772800000, 6),
    (33, 4.0945, 4.41, 4.3, 4.41, 3.95, 1758859200000, 9))]}
AAOI_C = [21.53, 22.19, 21.415, 23.23, 22.33, 21.59, 20.86, 22.79, 23.02, 21.01, 22.365, 26.13, 22.77, 21.93, 23.7, 24.79,
          24.34, 25.07, 24.05, 25.49, 24.2, 23.35, 23.02, 23.32, 23.99, 23.63, 23.72, 27.72, 26.85, 27.07, 29.56]   # Aug 1 - Sep 15 2025

print("Formats and parsing")
check("the option ticker format matches Massive's", L.au_occ("AAOI", date(2025, 9, 26), "put", 30.0) == "O:AAOI250926P00030000")
check("...for calls and half strikes", L.au_occ("spy", date(2024, 12, 20), "call", 550.5) == "O:SPY241220C00550500")
b = L.au_parse_bars(BARS)
check("bars: one row per session, dated in New York time (first is Sep 15 2025)",
      len(b) == 9 and b.index[0] == pd.Timestamp("2025-09-15") and b.index[-1] == pd.Timestamp("2025-09-26"), b.index[:2])
check("bars: VWAP and close kept", abs(b.at[pd.Timestamp("2025-09-15"), "vw"] - 2.7236) < 1e-12 and b["c"].iloc[-1] == 4.3)
check("an empty response is an empty frame", L.au_parse_bars({"results": []}).empty and L.au_parse_bars(None).empty)
lst = L.au_parse_listing(LISTING)
check("listing: 10 standard contracts, the adjusted (50-share) one left out", len(lst) == 10 and 29.5 not in set(lst["K"]))

print("Picking the listed contracts")
types = {"K1": "put", "K2": "put", "K3": "put", "K4": "put"}
pk = L.au_pick(lst, pd.Timestamp("2025-09-22"), {"K1": 30.2, "K2": 28.4, "K3": 29.1, "K4": 31.4}, types)
check("the first listed expiry on or after the ledger's (Sep 26 for Sep 22)", pk and pk["exp"] == pd.Timestamp("2025-09-26"))
check("each leg at the nearest listed strike", pk and [pk["legs"][k][1] for k in L.AU_LEGS] == [30.0, 28.5, 29.0, 31.0],
      pk and [pk["legs"][k][1] for k in L.AU_LEGS])
check("an expiry already passed isn't used (Sep 19 for Sep 18 is fine)", L.au_pick(lst, pd.Timestamp("2025-09-18"),
      {"K1": 30, "K2": 28, "K3": 29, "K4": 31}, types)["exp"] == pd.Timestamp("2025-09-19"))
check("two legs on one strike: no match", L.au_pick(lst, pd.Timestamp("2025-09-22"), {"K1": 30.1, "K2": 30.2, "K3": 29, "K4": 31}, types) is None)
check("nothing within the slack: no match", L.au_pick(lst, pd.Timestamp("2025-10-30"), {"K1": 30, "K2": 28, "K3": 29, "K4": 31}, types) is None)

print("A real implied vol from those prints")
S_vw, T = 28.8912, (11 + 0.35) / 365.0          # AAOI's VWAP on Sep 15 2025; Sep 26 expiry
iv = float(L.av_bs_iv(2.7236, S_vw, 30.0, T, L.BR_RATE, False).ravel()[0])
hv = float(np.log(pd.Series(AAOI_C)).diff().iloc[-20:].std() * np.sqrt(252))
print(f"       AAOI 30 put, Sep 15 2025, 11 days: IV {iv:.1%}, HV20 {hv:.1%}, IV / HV20 {iv / hv:.2f}")
check("the put's IV backs out of its VWAP at a plausible level", 0.5 < iv < 1.6, iv)

print("The disk cache")
calls = {"n": 0}
real_http = L.http_json


def fake_http(url, params=None, **kw):
    calls["n"] += 1
    if "/v3/reference/options/contracts" in url:
        return {"results": LISTING}
    return BARS


L.http_json = fake_http
src = L.AuMassive("KEY", Path(os.environ["LAB_OPT_BARS"]))
a1 = src.listing("AAOI", date(2025, 9, 15), date(2025, 9, 19), date(2025, 9, 30), 27.0, 32.0)
a2 = src.listing("AAOI", date(2025, 9, 15), date(2025, 9, 19), date(2025, 9, 30), 27.0, 32.0)
check("a listing is fetched once, then read from disk", calls["n"] == 1 and len(a1) == len(a2) == 10, calls["n"])
b1 = src.bars("O:AAOI250926P00030000", date(2025, 9, 12), date(2025, 9, 26))
b2 = src.bars("O:AAOI250926P00030000", date(2025, 9, 1), date(2025, 9, 26))
check("an expired contract's bars are fetched once", calls["n"] == 2 and len(b1) == len(b2) == 9, calls["n"])
live = L.au_occ("AAOI", date.today() + timedelta(days=30), "put", 30.0)
src.bars(live, date.today(), date.today() + timedelta(days=30))
src.bars(live, date.today(), date.today() + timedelta(days=30))
check("a live contract is fetched every time (its bars still change)", calls["n"] == 4, calls["n"])
L.http_json = real_http

print("The demo truth")
cfg = PB.pb_cfg("demo")
cfg["uni"] = cfg["uni"].head(30)
bars, P = PB.pb_bars(cfg)
groups, _ = L.resolve_groups(cfg["uni"], 5)
ab = L.alpha_block(bars, groups, True, 5)
prm = {**PB.pb_br_prm("bull"), "pricer": "flat"}
Pb, _ = L.br_list_panel(cfg, ab, with_former=False)
run = L.br_run(Pb, None, None, prm, "t")
res = L.au_run(run, prm, L.AuDemo(run["C"], run["TP"]), per_setup=40)
check("every spread in the window matched to listed contracts", res["n_matched"] == res["n_events"] > 50, (res["n_matched"], res["n_events"]))
lv = L.au_level(res["legs"])
check("the level: IV / realized from the prints = the demo's 1.30", abs(lv["median"] - 1.30) < 0.02, lv["median"])
check("...against the ledger's own 1.15", abs(lv["ledger_ratio"] - 1.15) < 0.01, lv["ledger_ratio"])
check("by realized-vol tercile and by month", len(lv["by_hv"]) == 3 and len(lv["by_month"]) >= 3)
pr = L.au_prices(res["spreads"])
check("at 1.15x the ledger's debits are too cheap against prints at 1.30x", pr["db_flat_ratio"] < 0.97, pr)
prm13 = {**prm, "iv_mult": 1.30}
run13 = L.br_run(Pb, None, None, prm13, "t")
pr13 = L.au_prices(L.au_run(run13, prm13, L.AuDemo(run13["C"], run13["TP"]), per_setup=40)["spreads"])
check("at the prints' 1.30x the debit ratio moves to about 1", abs(pr13["db_flat_ratio"] - 1) < abs(pr["db_flat_ratio"] - 1)
      and abs(pr13["db_flat_ratio"] - 1) < 0.05, (pr["db_flat_ratio"], pr13["db_flat_ratio"]))
shp = L.au_shape(res["legs"])
check("the shape: the demo smile curves up in the put wing more than the fixed skew allows",
      shp.set_index("bucket").at[-0.15, "market"] > shp.set_index("bucket").at[-0.15, "fixed_skew"], shp.round(3).to_dict("records")[:3])

print("A spread's return by hand")
sp = res["spreads"]
r0 = sp[sp["ok_db"]].iloc[0]
lg = res["legs"][res["legs"]["ev_id"] == r0["ev_id"]].set_index("leg")
src_d = L.AuDemo(run["C"], run["TP"])
o1 = L.au_occ(r0["ticker"], r0["exp"].date(), "call", lg.at["K1", "K"])
o2 = L.au_occ(r0["ticker"], r0["exp"].date(), "call", lg.at["K2", "K"])
b1, b2 = src_d.bars(o1, r0["date"].date() - timedelta(days=3), r0["exp"].date()), src_d.bars(o2, r0["date"].date() - timedelta(days=3), r0["exp"].date())
S_in, S_out = float(run["TP"].at[r0["date"], r0["ticker"]]), float(run["C"].at[r0["exit_date"], r0["ticker"]])
hsp = lambda x, S: (L.av_half_spread(x, S, "stock", float(prm["opt_cost"]), L.BR_CAP_BP) + L.BR_FEE) if x > 0.005 else 0.0
p1, p2 = float(b1.at[r0["date"], "vw"]), float(b2.at[r0["date"], "vw"])
q1, q2 = float(b1.at[r0["exit_date"], "c"]), float(b2.at[r0["exit_date"], "c"])
c_in, c_out = float(hsp(p1, S_in) + hsp(p2, S_in)), float(hsp(q1, S_out) + hsp(q2, S_out))
by_hand = ((q1 - q2) - (p1 - p2) - c_in - c_out) / ((p1 - p2) + c_in)
check("a call debit spread: in at the entry VWAP, out at the exit close, the ledger's costs", abs(by_hand - r0["ror_db_mkt"]) < 1e-9,
      (by_hand, r0["ror_db_mkt"]))

print("The verdicts")
rng = np.random.default_rng(3)
n = 60
dts = pd.bdate_range("2025-01-02", periods=n)
pl = pd.DataFrame({"setup": "bl:pullback_ma", "date": dts, "ror_db_mkt": rng.normal(0.0, 0.3, n), "ror_cr_mkt": rng.normal(0.0, 0.1, n)})
pl["ror_db_flat"] = pl["ror_db_mkt"] + 0.10 + rng.normal(0, 0.02, n)          # planted: too kind
pl["ror_db_hs"] = pl["ror_db_mkt"] + rng.normal(0, 0.02, n)                   # consistent
pl["ror_cr_flat"] = pl["ror_cr_mkt"] - 0.05 + rng.normal(0, 0.01, n)          # too harsh
pl["ror_cr_hs"] = pl["ror_cr_mkt"]
thin = pl.head(12).assign(setup="bl:breakout55")
V = L.au_setups(pd.concat([pl, thin]), 5).set_index(["setup_id", "book"])
check("a pricer 10 points kinder than the prints: TOO KIND", V.at[("bl:pullback_ma", "db"), "v_flat"] == "TOO KIND"
      and abs(V.at[("bl:pullback_ma", "db"), "bias_flat"] - 0.10) < 0.01)
check("matching the prints: CONSISTENT", V.at[("bl:pullback_ma", "db"), "v_hs"] == "CONSISTENT")
check("5 points harsher: TOO HARSH", V.at[("bl:pullback_ma", "cr"), "v_flat"] == "TOO HARSH")
check("12 trades: THIN", V.at[("bl:breakout55", "db"), "v_flat"] == "THIN")
L.au_save(res, "bull")
check("saved next to the bar cache", (Path(os.environ["LAB_OPT_BARS"]).parent / "bull_audit_spreads.parquet").exists())

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
