"""Planted-case tests for the Heston pricer in the spread ledgers: prices against Black-Scholes (no vol of variance),
a brute-force integral, put-call parity, no-arbitrage shape (monotone, convex in strike), the skew sign, a fit that
recovers planted parameters, the pooled shape, the ATM level match, the ledger re-priced under the fixed skew equal to
the build, a Heston build equal to a Heston re-price, the comparison's bar logic by hand, the candidates, and the
saved parameters carrying the pricer for playbook.py.
Run: python test_heston.py"""
import os
import shutil
import tempfile
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
TMP = tempfile.mkdtemp(prefix="hs_test_")
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


r = L.BR_RATE
print("Prices")
worst = 0.0
for T in (1 / 365, 3 / 365, 10 / 365, 45 / 365, 1.0):
    for sig in (0.12, 0.4, 0.9):
        K = np.linspace(70, 130, 31)
        for call in (True, False):
            h = L.hs_price(100.0, K, T, r, call, sig ** 2, 2.0, sig ** 2, 1e-4, 0.0)
            b = L.av_bs(np.full(31, 100.0), K, np.full(31, T), np.full(31, sig), r, call)
            worst = max(worst, float(np.max(np.abs(h - b))))
check("no vol of variance (xi ~ 0, rho 0) is Black-Scholes, 1 day to 1 year, 70-130 strikes", worst < 2e-4, worst)


def brute(S, K, T, v0, k, th, xi, rho):
    """The Lewis integral on a fine log-spaced grid (trapezoid, 400k points): slow, independent of the panels."""
    u = np.concatenate([np.linspace(0, 1, 20001), np.geomspace(1.0001, 3e4, 400000)])
    X = np.log(S / K) + r * T
    f = np.real(np.exp(1j * u * X) * L.hs_cf(u - 0.5j, T, v0, k, th, xi, rho)) / (u * u + 0.25)
    I = np.trapezoid(f, u) if hasattr(np, "trapezoid") else np.trapz(f, u)
    return S - np.sqrt(S * K) * np.exp(-0.5 * r * T) / np.pi * I


wb = 0.0
for (T, v0, k, th, xi, rho) in ((3 / 365, 0.25, 2.0, 0.16, 2.0, -0.6), (14 / 365, 0.04, 3.0, 0.04, 0.6, -0.8),
                                (45 / 365, 0.6, 5.0, 0.6, 3.0, -0.3)):
    for K in (80.0, 95.0, 100.0, 108.0, 125.0):
        h = float(L.hs_price(100.0, K, T, r, True, v0, k, th, xi, rho).ravel()[0])
        wb = max(wb, abs(h - max(brute(100.0, K, T, v0, k, th, xi, rho), max(100 - K * np.exp(-r * T), 0))))
check("against a brute-force integral: within $0.0005 on a $100 stock (strong skew, short and long dated)", wb < 5e-4, wb)
p_ = dict(v0=0.09, kappa=2.0, theta=0.09, xi=0.9, rho=-0.7)
K = np.arange(80, 121, 1.0)
T = 20 / 365
c = L.hs_price(100.0, K, T, r, True, **p_)
p = L.hs_price(100.0, K, T, r, False, **p_)
check("put-call parity", np.allclose(c - p, 100 - K * np.exp(-r * T), atol=1e-9))
check("calls fall and are convex in the strike", (np.diff(c) < 0).all() and (np.diff(c, 2) > -1e-9).all())
iv = L.av_bs_iv(p, np.full(len(K), 100.0), K, np.full(len(K), T), r, False)
check("negative rho makes a put skew: IV falls with the strike", iv[0] > iv[20] > iv[-1], iv[[0, 20, -1]])
iv_pos = L.av_bs_iv(L.hs_price(100.0, K, T, r, False, **{**p_, "rho": 0.5}), np.full(len(K), 100.0), K, np.full(len(K), T), r, False)
check("positive rho tilts it the other way", iv_pos[-1] > iv_pos[0])
c_sym = L.av_bs_iv(L.hs_price(100.0, K, T, r, False, **{**p_, "rho": 0.0}), np.full(len(K), 100.0), K, np.full(len(K), T), r, False)
check("rho 0: a smile, the wings over the money", c_sym[0] > c_sym[20] and c_sym[-1] > c_sym[20])
check("expiry-day legs are intrinsic in the ledger (T 0 is never integrated)",
      np.allclose(L.hs_price(100.0, 90.0, 1e-6, r, True, **p_), 10.0, atol=1e-3))

print("The fit")
true = dict(v0=0.16, kappa=2.5, theta=0.12, xi=1.2, rho=-0.6)
rows = []
for dte in (4, 11, 18, 32, 45):
    for Kk in np.arange(76, 125, 2.0):
        call = Kk >= 100
        px = L.hs_price(100.0, Kk, dte / 365, r, call, **true).ravel()[0]
        v = L.av_bs_iv(px, 100.0, Kk, dte / 365, r, call).ravel()[0]
        if np.isfinite(v):
            rows.append({"K": Kk, "dte": dte, "T": dte / 365, "iv": v, "call": call})
f = L.hs_fit(pd.DataFrame(rows), 100.0)
check("a Heston smile is fitted back to under 0.1 vol point", f["rmse"] < 1e-3, f["rmse"])
check("...recovering v0, xi and rho", abs(f["v0"] - 0.16) < 0.005 and abs(f["xi"] - 1.2) < 0.08 and abs(f["rho"] + 0.6) < 0.03,
      {k: round(f[k], 3) for k in ("v0", "xi", "rho")})
check("too few quotes: no fit", L.hs_fit(pd.DataFrame(rows).head(5), 100.0) is None)
cons = [x for x in (L.extract_contract(q, date.today()) for q in L.demo_chain("ABC", 50.0, 0.4, 45, False)) if x]
pts = L.hs_chain_points(cons, 50.0)
check("chain points: out of the money only, inside the band and the expiries",
      len(pts) > 20 and ((pts["K"] < 50) == ~pts["call"]).all() and (np.abs(np.log(pts["K"] / 50)) <= L.HS_FIT_BAND).all()
      and pts["dte"].between(*L.HS_FIT_DTE).all())
fits = {f"N{i}": {**f, "v0": v0_, "xi": 2.0 * v0_ ** 0.75, "theta": v0_ * 1.5, "rmse": 0.01}
        for i, v0_ in enumerate(np.geomspace(0.03, 0.8, 10))}
fits["bad"] = {**f, "rmse": 0.2}
pl = L.hs_pool(fits)
check("pooled: the power law of xi on v0 is found (0.75)", abs(pl["hs_pow"] - 0.75) < 1e-6 and abs(pl["hs_nu"] - 2.0) < 1e-6, pl)
check("pooled: a poor fit is left out; theta / v0 the median", pl["n_names"] == 10 and abs(pl["hs_theta_ratio"] - 1.5) < 1e-9)
check("nothing fits: the defaults", L.hs_pool({"x": {"rmse": 1.0}})["source"] == "defaults")
hp = L.hs_event_params(np.array([0.3, 0.6]), np.array([7 / 365, 14 / 365]), r, L.HS_DEFAULT, np.array([50.0, 200.0]))
atm = L.av_bs_iv(L.hs_price(np.array([50.0, 200.0]), np.array([50.0, 200.0]), np.array([7 / 365, 14 / 365]), r, True,
                            hp["v0"], hp["kappa"], hp["theta"], hp["xi"], hp["rho"]),
                 np.array([50.0, 200.0]), np.array([50.0, 200.0]), np.array([7 / 365, 14 / 365]), r, True)
check("the ledger's level is kept: Heston's ATM IV equals the IV given", np.allclose(atm, [0.3, 0.6], atol=2e-4), atm)

print("The ledgers")
cfg = PB.pb_cfg("demo")
cfg["uni"] = cfg["uni"].head(30)
bars, P = PB.pb_bars(cfg)
groups, _ = L.resolve_groups(cfg["uni"], 5)
ab = L.alpha_block(bars, groups, True, 5)
res = L.hs_calibrate(cfg, list(bars)[:6], bars)
check("calibration saves the fit, the quotes, and the chains' IV / realized", Path(os.environ["LAB_HESTON_FILE"]).exists()
      and len(L.hs_load_points()) > 50 and L.hs_load()["iv_hv_median"] is not None and L.hs_load()["pooled"]["n_names"] >= 1)
for side in ("bull", "bear"):
    prm = {**PB.pb_br_prm(side), "pricer": "flat"}
    Pb, _ = L.br_list_panel(cfg, ab, with_former=False)
    run = L.br_run(Pb, None, None, prm, "t")
    ev = run["ev"]
    tr = ev["status"] == 0
    rf = L.br_reprice(run, prm)
    same = all(np.allclose(ev.loc[tr, k].astype(float).fillna(-9), rf.loc[tr, k].astype(float).fillna(-9), rtol=1e-5, atol=1e-6)
               for k in ("db_follow", "cr_follow", "db_debit", "cr_credit", "db_hold", "cr_hold"))
    check(f"{side}: re-pricing under the fixed skew gives the build's own prices", same)
    ph = L.br_with_pricer(prm, "heston")
    check(f"{side}: the Heston parameters carry the saved fit", ph["pricer"] == "heston"
          and abs(ph["hs_rho"] - round(L.hs_load()["pooled"]["hs_rho"], 4)) < 1e-12)
    rh = L.br_reprice(run, ph)
    run_h = L.br_run(Pb, None, None, ph, "t")
    check(f"{side}: a Heston build equals a Heston re-price", np.allclose(run_h["ev"].loc[tr, "cr_follow"].astype(float).fillna(-9),
                                                                          rh.loc[tr, "cr_follow"].astype(float).fillna(-9), rtol=1e-4, atol=1e-5))
    check(f"{side}: only option prices move (the share trades are identical)",
          np.allclose(run_h["ev"]["r"].astype(float).fillna(-9), ev["r"].astype(float).fillna(-9)))
    check(f"{side}: Heston prices differ from the fixed skew", float(np.nanmax(np.abs(rh.loc[tr, "cr_credit"].astype(float)
                                                                                     - ev.loc[tr, "cr_credit"].astype(float)))) > 1e-3)
    sb, _ = L.br_score(ev, "none", 0.4, int(prm["horizon"]), side)
    c = L.br_candidates(run_h, sb, ph)
    check(f"{side}: today's candidates priced under Heston", (not len(c)) or np.isfinite(c["db_est"].astype(float)).all())
    if side == "bull":
        saved = (run, ev, prm)

print("The comparison")
run, ev, prm = saved
H = int(prm["horizon"])
sid = ev[(ev["status"] == 0) & (ev["setup"] != "base:uptrend")]["setup"].value_counts().index[0]
ev_b = ev.copy()
ev_b["db_follow"] = ev_b["db_follow"].astype(float)
m = (ev_b["setup"] == sid) & (ev_b["status"] == 0)
ev_b.loc[m, "db_follow"] = 0.4 + np.random.default_rng(1).normal(0, 0.05, int(m.sum()))   # planted: a big edge under "Heston"
cmp = L.br_pricer_compare(ev, ev_b, 0.4, H, "bull")
T = cmp["table"].set_index("setup_id")
v = T.at[sid, "verdict"]
exp_pass = v in ("PROVEN", "PROMISING")
check("the planted debit edge clears the bar under the second pricer when the signal is PROVEN/PROMISING",
      bool(T.at[sid, "pass_db_heston"]) == exp_pass, (v, T.at[sid, "t_db_follow_heston"]))
check("...and the change is flagged exactly when the answer differs",
      bool(T.at[sid, "chg_db"]) == (bool(T.at[sid, "pass_db_flat"]) != bool(T.at[sid, "pass_db_heston"])))
check("untouched spreads and setups don't change", not T.drop(index=sid)["chg_db"].any() and not T["chg_cr"].any())
check("the same trades priced the same: price ratios 1", abs(cmp["prices"]["debit_ratio"] - 1) < 1e-9)

print("Saved for playbook.py")
L.br_save("bull", {"run": run, "which": "list"}, L.br_with_pricer(prm, "heston"), "demo", 0.4, folder=Path(TMP))
pbp = PB.pb_br_prm("bull", PB._read_json(Path(TMP) / "bull_ledger_meta.json"))
check("the saved ledger's parameters carry the pricer and its shape (the nightly rebuilds it the same way)",
      pbp.get("pricer") == "heston" and "hs_rho" in pbp, {k: pbp.get(k) for k in ("pricer", "hs_rho")})
check("an older saved ledger without a pricer stays on the fixed skew", PB.pb_br_prm("bull", {}).get("pricer", "flat") == "flat")

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
