# Heston pricer for the spread ledgers (Nov 4 2026)

Neil shared Matthew Lorig's open CFRM 504 lecture notes (github.com/mattlorig/intro-financial-derivatives; arXiv
2611.01355; CC BY-SA 4.0). They cover stochastic volatility and the Heston model. The real gap they pointed to: the
Bull and Bear spreads ledgers price every past spread with one IV (HV20 × `iv_mult`) and a straight-line put skew,
which is worst for the legs far from the money. He asked to build Heston in **as an option**, then rebuild the
ledgers both ways and see whether any spread setup's verdict changes. Everything is in `alpha_options_lab.py`, in
the HESTON block just above `br_price_spreads`. It is numpy only (no scipy).

## Engine
- **`hs_cf(w, T, v0, kappa, theta, xi, rho)`:** the characteristic function of ln(S_T/F) in the "little Heston trap"
  form (Albrecher et al. 2007), which stays on the principal branch.
- **`hs_price(S, K, T, r, call, v0, kappa, theta, xi, rho)`:** Lewis's single-integral formula, vectorized.
  - **Range:** composite Gauss-Legendre (`HS_NODES` = 32 per panel). The upper limit U = sqrt(90 / (min(v0, θ)·T)).
    The panel count, 4 to 64, follows e^(iuX)'s oscillation, so short-dated far strikes stay accurate.
  - **Control variate:** Black-Scholes at the expected average variance (closed form), so the quadrature only carries
    the small, smooth difference. Without it, the 1/(u²+¼) spike near 0 broke 1-day options.
  - **Puts and bounds:** puts by parity, held inside the no-arbitrage bounds. Batches of `HS_BATCH` rows.
  - **Speed:** about 20k prices a second.
- **Accuracy:**
  - Black-Scholes limit (ξ ≈ 0, ρ = 0), 1 day to 1 year, strikes 70-130: < $0.0002 on $100.
  - Adaptive quadrature on extreme parameters (ξ up to 3, ρ −0.8 to +0.2): < $0.0001.
  - Monte Carlo (400k paths): within MC error.
  - With ρ ≠ 0, a tiny ξ is *not* Black-Scholes. That's real (the skew is first-order in ρξ), not a bug.
- **`hs_event_params(iv, T0, r, hs, S)`:** per-event parameters from the pooled shape at each event's own level.
  - v0 is set so the Heston ATM IV at the entry's time to expiry equals the ledger's IV (two fixed-point steps).
  - **The two pricers differ only in the smile.**
  - θ = `hs_theta_ratio`·v0 and ξ = `hs_nu`·v0^`hs_pow` (`hs_xi`).

## Fit
- **`hs_chain_points(cons, spot)`:** out-of-the-money quotes (puts under spot, calls at or over it) with an IV, 3-45
  days out (`HS_FIT_DTE`), within 25% of spot (`HS_FIT_BAND`).
- **`hs_fit(pts, spot)`:** Levenberg-Marquardt on price error / Black-Scholes vega (≈ IV error).
  - Bounded transforms; `HS_BOUNDS` holds ξ ≤ 10 and ρ in −0.95 to +0.6.
  - A soft prior (`HS_PRIOR` 0.02) pulls κ toward 3 and θ toward v0, because short expiries barely identify them.
  - A planted Heston smile is recovered to 0.0001 IV.
- **`hs_pool(fits)`:**
  - Uses the names that fit to 4 vol points or better (`HS_MAX_RMSE`).
  - Medians of κ, θ/v0 (clipped 0.25-4, `HS_RATIO_CLIP`) and ρ.
  - `hs_pow` comes from a regression of ln ξ on ln v0 across 8+ names (held to 0.25-1.25); otherwise 0.5.
  - `hs_nu` = median ξ / v0^pow.
- **`hs_calibrate(cfg, names, bars)`:** `fetch_chain` and `extract_contract`, then a fit per name. Writes
  `data/heston_fit.json` (pooled, per name including `iv_hv` = market ATM IV / HV20, the median, asof, source) and
  `data/heston_fit.parquet` (the quotes with each name's own fitted IV). Both are atomic; `$LAB_HESTON_FILE`
  overrides the path.
- **Loading:** `hs_load()` returns `HS_DEFAULT` when there's no fit (ρ −0.5, ν 2.0, pow 0.5, κ 3, θ/v0 1).
  `hs_load_points()` reads the quotes.
- **`hs_shape_iv(pts, atm, hs, skew)`:** each ledger pricer's smile at the name's own market ATM level, for the
  shape-error comparison.

## Ledger wiring
- **Parameters:**
  - `BR_DEFAULTS` gains `pricer` "flat" and `hs_n` 15. `BR_PRICERS` holds the labels.
  - `br_params` adds `pricer`, plus the `hs_*` keys from the saved fit when Heston is chosen (flat keys, so the memo
    signature stays hashable).
  - `br_with_pricer(prm, pricer, hs)` switches pricers; `br_hs_params(prm)` reads the shape back out.
- **Pricing:**
  - `br_price_spreads(..., pricer, hs)`: under Heston, legs at T > 0 are priced by `hs_price` with the entry's
    parameters (marks keep them, as the fixed skew keeps its shape in moneyness). Expiry legs are intrinsic and
    never integrated. The fixed-skew branch is numerically unchanged.
  - `br_chunk` and `br_candidates` pass the pricer through.
- **Re-pricing:**
  - `br_run` keeps `run["C"]` (closes, float32).
  - `br_reprice(run, prm)` re-prices every traded event on the same paths. e = exit_i − hold + 1, and the stored
    entry, stop, target, exit and hv20 are reused. Under the fixed skew this reproduces the build exactly, and a
    Heston build equals a Heston re-price.
- **Comparison (`br_pricer_compare(ev_flat, ev_heston, hold, H, side)`):**
  - `br_score` under both pricers, per setup: ror, t and win for each spread.
  - `pass_*`: the playbook's bar. The signal must be PROVEN or PROMISING, with ror > 0 at t ≥ 2.5 (`HS_PB_T`,
    mirroring playbook.py's `bar.t_spread`).
  - `chg_db`/`chg_cr` flag where the answer differs.
  - Median entry debit and credit ratios (Heston / flat).
- **playbook.py:** unchanged. The saved meta's `prm` carries `pricer` and `hs_*`, so `pb_br_prm` and the nightly
  rebuild a Heston ledger the same way. An older meta has no pricer and stays flat.

## UI (both spread tabs)
- **Settings popover:** the *Option pricer* radio (`{K}pricer`).
- **New section 5, "Option pricing: the fixed skew against Heston"** (`_br_heston_section`):
  - KPIs: this build's pricer, the fit date and names, ρ, vol of variance, the chain IV / realized vs your multiple.
  - Fit controls: *Names to fit* (`{K}hs_n`) and *Fit Heston to today's chains* (`{K}hs_fit`). The names are
    today's candidates first, then the list's most liquid. Needs Massive or demo.
  - The per-name table: own fit error, fixed-skew error vs pooled-Heston error at the name's ATM level, IV / HV and
    the parameters.
  - The smile chart (`{K}hs_pick`): market dots, both ledger pricers and the name's own fit, at the expiry nearest
    the spread life.
  - *Re-price this ledger's spreads under … and compare* (`{K}hs_cmp`): KPIs (answers that change, price ratios,
    setups that clear the bar under both) and the per-setup table.
  - `HS_GUIDE`.
- **Prefixes:** bear `bsp_`, bull `bls_`.

## Demo read (synthetic, illustrative)
- **Fit:** 6 demo names, 4 pooled. Pooled ρ −0.43, ν 5.1. Heston's shape beat the fixed skew on 5 of 6 names (the
  demo smile is a parabola, which a straight line can't follow).
- **Price ratios (Heston / flat):** bull put credits priced 1.30× and call debits 1.01×. Bear call credits priced
  0.90×.
- **Verdicts:** no spread answer changed on demo. The real test is a fit on Massive chains, then the compare button
  on each side.

## Tests
- **`test_heston.py` (35 checks):**
  - the Black-Scholes limit, a brute-force integral, parity, monotone and convex, the skew signs, intrinsic at expiry;
  - planted fit recovery, chain-point filters, pooling (power law, a bad fit left out, defaults), the ATM level
    match;
  - calibration files;
  - per side: flat re-price = build, Heston build = re-price, share trades identical, prices differ, candidates;
  - the comparison on a planted edge (bar, change flag, untouched rows);
  - the saved meta carries the pricer, and an older meta stays flat.
- **`apptest_heston.py`:** the bull tab built flat, then fit, smiles, compare, switch to Heston, rebuild, compare
  back (equal); the bear tab compare. 0 exceptions.
- **Regression:** flat bull and bear ledgers are identical to the previous file on demo. `test_bull` (40) and
  `test_bear` (45) pass, as do `apptest_bull` and `apptest_bear`.

## Open
- **First real use:**
  1. Massive key → Bull spreads → build → section 5 → *Fit Heston* (15-30 names).
  2. Read the smile errors.
  3. *Re-price and compare*.
  4. Repeat on Bear.

  If a setup clears the bar only under one pricer, don't admit it until the live chain agrees.
- **The level matters too:** the chains' IV / realized against `iv_mult`. A big gap there is the bigger pricing
  error; it lives in the multiple setting, not the smile.
- **Fit timing:** the fit is today's smile applied to all history (the smile shape is fairly stable; the level isn't,
  and the level still comes from realized vol). Refit occasionally; a dated fit is shown.

## Pricer audit (Nov 7 2026)
Options Starter does keep two years of option bars (trades, no quotes). Section 6 of both spread tabs audits the ledger's IV level, smile and spread returns against the real prints of those two years. See `pricer-audit-handoff.md`.
