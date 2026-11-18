# Alpha & Options Lab: Alphas by trade (Nov 3 2026)

Neil: "Alphas might be more important for different trades. Mean reversion may be more important for a short or
rebound trade, vwap may be important on a breakout etc. Can we include what alphas matter and why by category?"

New tab **Stocks > Alphas by trade** (`S[6]`, right after Alphas). It runs as an `st.fragment`. The later Stocks tabs
moved to `S[7..17]`. Code: the ALPHAS BY TRADE block after `ML_GUIDE`; prefix `am_`, session keys `amx_`. The breakout
model's section 3 also gained a by-category table (`ob_importance_by_category`).

## Trades it reads (`am_collect`)
- **Sources:**
  - Setup ledger: `ss["lg_res"]["runs"]` (market first, then list). With nothing built, it reads the saved
    `data/setup_ledger.parquet`.
  - Bull spreads: `ss["bls_res"]["run"]["ev"]`. Bear spreads: `ss["bsp_res"]["run"]["ev"]`.
  - The breakout model's trades: `ss["obx_trades"]` or `data/ml/orb_trades.pkl`.
- **Rows:** traded rows only (status 0, finite `r`). A trade in both Setup ledger runs counts once.
- **Baselines:** the same `base:uptrend` id means different things in the long ledger and Bull spreads, so baselines
  get per-ledger types and a `setup_key` of "base:… · source".
- **Breakout model:** one row per range per head ("Gap-up ORB, intraday" / "swing", setup `orb:{m}m`). These rows
  keep their prior-close alpha inputs (`lag` 1).
- **Trade types (`AM_TYPES`):** every setup in `LG_SETUPS`, `BL_SETUPS` and `BR_SETUPS` maps to one of:
  - Long: Breakout; Tight base / launch pad; Pullback in trend; Rebound / oversold; Trend signal; Gap / episodic
    pivot; Gap-up ORB intraday and swing.
  - Short: failed bounce; breakdown; overbought fade; gap down.
  - Three baselines.

  Descriptions are in `AM_TYPE_DESC`.

## Inputs (`am_attach`)
- `ob_alpha_inputs(..., lag=0)` at the signal's own close (ledger entries are the next session): the same 34 inputs as
  the breakout model (27 alphas, 6 categories, the composite).
- Each is a percentile of that day's top 1,000 by dollar volume.
- **Panel:** `ml_panel` on Massive or Demo (whole market, years sized to the trades' span, up to 6), else your universe
  panel (Yahoo: the crowd is your list).
- Memoized per (panel, trade pairs).

## The test (`am_profile`)
For each type (and each `setup_key`, for the setup-by-setup view) and each input:
- **Within setups:** R minus its setup's average R, so the setup mix can't fake an effect (tested with a planted
  confound).
- **Slope:** OLS slope from the bottom of the crowd to the top, standard errors clustered by date (`am_cluster_ols`:
  Liang-Zeger with the small-sample factor; equals HC1 with one trade per cluster).
- **Halves:** each half of the dates has the same sign and its own t ≥ 1. The first version used the sign only; a
  planted first-half-only effect passed that, so the t was added.
- **Fifths:** `effect` = top fifth less bottom fifth of the within-setup R (the heatmap number). `R_lo` and `R_hi`
  are the plain averages, shown in the drill-down. The first version showed plain R; on demo, Gap setups picked by
  #101 / #20 made the plain Candle effect disagree with the within-setup t.
- **Shape:** a squared-term t (`shape`: U or ∩ at |t| ≥ 2.5).
- **BH q** across every row.
- **Status:**
  - MATTERS: |t| ≥ 2.5, halves, q ≤ 0.10.
  - MAYBE: |t| ≥ 2.
  - NO EFFECT otherwise.
  - THIN: under 100 trades or 30 dates.

## Readings (`am_summary`, `am_why`)
Per type × category:
- The category score's result.
- The leading alpha in the category (by `ID_TO_CAT`, selected and reference alphas; best status, then |t|).
- What high and low mean:
  - `AM_CAT_SIDES` for each category.
  - `AM_ALPHA_SIDES` for each of the 27 alphas, derived from the formulas. VWAP is the typical price on daily bars,
    so the VWAP alphas read the close against the range.
- What it says about the trade (`AM_READ[(side, cat, better)]`, 24 readings).
- The usual reading where there is one (`AM_PRIOR`), checked as agrees / opposite / not seen. Examples:
  - MRV low for failed-bounce shorts.
  - MRV high for rebounds.
  - VWP low, CMP high and MOM high for breakouts.
- `AM_ALPHA_DEFINED` maps setups picked by a category's own alphas (the MRV dips and fades; the Gap family by #20
  and #101, i.e. Candle). The type's note says that category's range is cut short there.
- Category names come from `AM_CAT_LABEL`: "Mean reversion", not the composite's "Mean-rev (inverted)". The category
  score isn't inverted; only the composite inverts it.

## Tab (`render_am`)
- Source multiselect (`amx_src`) and "Map the alphas" (`amx_go`). The result goes to `ss["amx_res"]` with a signature;
  a note appears when the trades change.
- KPIs: trades mapped (with alpha coverage and the crowd), types, MATTERS cells, and the strongest non-baseline cell
  (MATTERS first, then |t|).
- **1 · The map:** an Altair heatmap (`am_heatmap`) of types × categories. Colour = t (green: better when high), text
  = top fifth less bottom fifth in R, * = MATTERS.
- **2 · What matters and why:** type selector (`amx_type`) with the type's description and a bullet reading per
  category, strongest first.
  - "Every alpha input" expander: 34 rows with what the better side means.
  - "Setup by setup" pivot: t per category per setup.
- **3 · Each category, across every trade** (`amx_cat`): status, effect, leading alpha, the usual reading and the
  check per type.
- Guide: `AM_GUIDE`.

## Tests
- **`test_alpha_map.py` (24 checks):**
  - Coverage of types, meanings and readings.
  - Clustered errors vs HC1 by hand, and wider with date clusters.
  - Planted effects: MRV low for the failed-bounce short, high for the rebound, VWP low for the breakout. Each comes
    first in its type, leads with the planted alpha, and the reading and usual reading agree.
  - Noise: nothing MATTERS.
  - Traps: the setup-mix confound removed; first-half-only not MATTERS; the U-shape flagged; THIN.
  - Collection: dedupe, sides, baselines apart, the breakout model's heads.
  - The `lag` 0 close; attach keeps carried inputs; the by-category roll-up.
- **`apptest_am.py`:** on demo, the empty state, then the Setup ledger and both spread ledgers built, the map, every
  type drilled (34 inputs each), every category, Bear only.

## Open
- **Real data is the test:** build the Setup ledger and both spread ledgers on Massive (whole market for the most
  trades), then map. Demo trades are synthetic.
- **It's descriptive:** an association in each ledger's history with the bar raised for many tests, not an
  out-of-sample prediction. The breakout model's section 3 is the out-of-sample one.
- **Possible next steps:**
  - Feed the categories that MATTER per type into the Trade ranker as features.
  - Add an alpha-category split to the ledgers' split selector.
