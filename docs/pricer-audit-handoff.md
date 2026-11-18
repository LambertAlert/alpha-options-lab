# Pricer audit: the spread ledgers' option prices against real prints (Nov 7 2026)

Neil asked whether Massive's Options Starter has historical option prices. It does: two years of daily (and minute)
bars for every contract, expired ones included. These are trade prints (o/h/l/c/vw/v/n), with no bid/ask quotes and
no past IVs or greeks. Checked live: the SPY Dec-20-2024 550 put's bars start exactly Nov 7 2024, two years before
the test. The lab had said "no option history on Starter" in four places; that's corrected. He asked to build the
audit. It's in `alpha_options_lab.py`, in the "Pricer audit" block just after `br_pricer_compare`.

## Engine (prefix `au_`)
- **Formats:** `au_occ(und, exp, typ, K)` builds the option ticker (`O:AAOI250926P00030000`). `au_parse_bars`
  turns `/v2/aggs` into a frame by ET session date. `au_parse_listing` turns `/v3/reference/options/contracts` into
  ticker, type, exp and K, leaving out adjusted contracts (shares ≠ 100).
- **Sources:**
  - **`AuMassive(key)`:** a listing call takes `as_of` (the entry date), an expiry window, a strike band and limit
    1000. `expired=true` returns nothing combined with `as_of`, so it isn't sent.
    - Bars cover a contract's whole life in the window (from expiry − 120 days), fetched once.
    - Disk cache in `data/opt_bars/` (`$LAB_OPT_BARS`): expired contracts are kept, live ones re-fetched; listings
      are cached too.
  - **`AuDemo(C, TP)`:** a synthetic history with a known truth.
    - Weekly Friday expiries on `br_strike_step`.
    - Prints are BS at IV = HV20 × `AU_DEMO_MULT` (1.30) × (1 − 0.8m + 2.5m²), with 2% noise.
    - Some days have no print, more often far from the money.
- **`au_events(run, per_setup)`:**
  - Traded events whose entry falls in the last `AU_DAYS` (728) days.
  - Entry and exit sessions come from exit_date and hold; `ledger_exp` = entry + H − 1.
  - Newest `per_setup` (`AU_PER_SETUP` 120) per setup, baseline included.
- **`au_pick(listing, ledger_exp, K, types)`:**
  - The first listed expiry on or after the ledger's, within `AU_EXP_SLACK` (14) days.
  - Each leg at the nearest listed strike.
  - None if a leg is missing or two legs of one spread land on one strike.
- **`au_run(run, prm, src, per_setup, progress, hs)`:**
  - Listings and bars are fetched in parallel (`AU_WORKERS` 12).
  - Per leg: the market price is the entry day's VWAP (close if none), against the stock's VWAP. `br_run` now keeps
    `run["TP"]` (VWAP, else (h+l+c)/3) beside `run["C"]`.
  - T = (days to the real expiry + 0.35) / 365.
  - Leg fields: market IV (`av_bs_iv`); fixed-skew IV and price at the ledger's IV (HV20 × multiple, floor 0.12);
    Heston price and IV from `hs_event_params` with the saved pooled shape.
  - Per spread: entry debit and credit; return on risk (in at the entry VWAP, out at the exit-day close, the ledger's
    half-spread cost model on every leg) from the prints and from both pricers on the same real contracts.
  - A spread needs only its own two legs' prints (`ok_db`, `ok_cr`); the pricers are scored only where the prints
    exist.
- **Readings:**
  - `au_level`: ATM legs (|m| ≤ 3%). IV / HV20: median, middle half, by month, by HV20 tercile, against the
    ledger's own ratio.
  - `au_shape`: each leg's IV over its own spread's K1 (ATM) IV, by moneyness bucket (±0.25 in 0.05 steps), for the
    prints, the fixed skew and Heston, with the median absolute errors.
  - `au_prices`: each pricer's debit and credit over the prints' (median ratio, median absolute miss).
  - `au_setups(sp, H)`: per setup and spread, the mean ror from the prints (with t) and from each pricer. Bias = the
    pricer less the prints, paired by trade, date-averaged, NW t. Verdicts: TOO KIND (t ≥ 2), TOO HARSH (t ≤ −2),
    CONSISTENT, THIN (under 20 trades).
  - `au_save`: `data/<side>_audit_legs.parquet` and `_spreads.parquet`.

## UI: section 6 of both spread tabs (`_br_audit_section`)
- **Controls:** *Newest trades per setup* (`{K}au_n`) and *Run the audit* (`{K}au_go`; Massive key or demo).
- **KPIs:** spreads matched (contracts, and how many had prints in and out), IV / realized from the prints against
  your multiple, debit and credit model/prints ratios (fixed skew and Heston).
- **The multiple:** *Set the IV multiple to the prints' X* (`{K}au_use`, rounded to 0.05) goes through
  `_{K}ivm_next`, applied before the widget draws; then rebuild.
- **Charts and tables:** IV/HV by month (your multiple dashed), the tercile table, the shape chart with the weighted
  shape error, the verdict KPIs and the per-setup table.
- **Guide:** `AU_GUIDE`.

## Wording fixed
The four places that said Starter has no option history now say Starter keeps two years of option bars (trades, no
quotes), shorter than the ledger, and point to section 6:
- the IV-multiple help;
- the section-2 note;
- `BR_GUIDE` and `BL_GUIDE` *Prices*.

## Demo read (synthetic, a check that it works)
- 30-40 names: the audit finds IV/HV = 1.30 (the planted truth) against the ledger's 1.15.
- At 1.15 the ledger's call debits come in at 0.92× the prints; after *Set the multiple* (1.30) and a rebuild,
  0.99×.
- Credits stay low (0.82-0.87×) because the demo smile's put wing is steeper than both pricers.

## Real data point (from the tests' saved responses)
AAOI 30 put, Sep 15 2025, 11 days to expiry: IV 104% against an HV20 of 111% (0.93×), after a 30% run-up. One contract
only; the audit is what gives the distribution.

## Tests
- **`test_audit.py` (28 checks):**
  - ticker formats;
  - parsing the saved real AAOI listing and put bars (ET dates, the 50-share contract dropped);
  - picking (first expiry on or after, nearest strikes, same-strike and slack rejections);
  - the disk cache with a stubbed HTTP (listing once, expired bars once, live contracts each time);
  - a real IV from the prints;
  - the demo truth (1.30 found, 1.15 seen, debits too cheap at 1.15 and about right at 1.30, the steeper wing);
  - one call debit spread's return by hand from the bars;
  - planted verdicts (TOO KIND, CONSISTENT, TOO HARSH, THIN); the save.
- **`apptest_audit.py`:** bull build → audit (1.30 found) → table → use the multiple → rebuild → audit → bear
  audit. 0 exceptions.
- **Regression:** `test_heston` (35), `test_bull` (40), `test_bear` (45), `apptest_bull`.

## Open
- **First real run:**
  1. Massive → Bull spreads → build → section 6 → *Run the audit* (120 per setup is a few hundred spreads and about
     1-2k contracts, a few minutes the first time).
  2. Read the multiple.
  3. Read the per-setup verdicts.
  4. Repeat on Bear.
- **One multiple for every name:** if the tercile table shows calm names at a much bigger multiple than wild ones, a
  per-name or per-vol-bucket multiple is the next step.
- **Coverage:** thin strikes often have no print on a day. If coverage is low, the minute bars (also on Starter) could
  fill an entry price closer to the stock's own entry time.
- **Depth:** the Kaggle SPY 2010-2023 EOD set would extend the audit past two years (2020, 2022) if Neil attaches it.
