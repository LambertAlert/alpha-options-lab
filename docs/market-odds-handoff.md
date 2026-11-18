# Alpha & Options Lab: Market odds (Oct 29 2026)

Neil asked for a tab built on Moontower's "Are the options market's odds any good?" (moontower.substack.com,
Oct 2026). The post is paywalled past the setup. What's public:
- **The Verticals screen:** for each name, the tightest vertical that is fully in the money at a ±k sd move, ranked by
  payout.
- **Odds from a price:** debit / width ≈ the risk-neutral chance of the move. A +1 sd move has about a 16% lognormal
  chance, so fair odds are about 5.25 to 1.
- **The study:** 42,500 spreads on 434 names, monthly expiries from Feb 2022 to Sep 2026, scored against where they
  expired.
- **Topics listed past the paywall:** backtest traps, shrinking samples, conflated risk premia, the market maker's edge,
  and prediction markets compared with SPY.

The tab rebuilds that test on Massive data.

**Options > Market odds** is the fifth sub-tab, after Bear spreads; the tabs from Strategy lab on moved to
`O[5..10]`. The code is the MARKET ODDS block between the bull/bear spreads block and `render_dealer`. Function prefix
`od_`; session keys `odx_`. The lab now imports `gzip`.

## History (`od_name`, `od_build`)
- **Expiries:** monthly options, the third Friday or the Thursday before when that Friday was a holiday (`od_listed`
  tries both). Contracts come from `/v3/reference/options/contracts`, with adjusted roots dropped.
- **Entry:** the session on or before the expiry minus each `dte` (7/14/30/45; default 30).
- **Contracts:** about 14 per expiry and entry. Strikes are nearest to S·exp(z·σ√T) for z in `OD_Z` (±2.75 sd),
  σ = 1.1 × max(HV20, HV60). Puts at and below spot, calls at and above.
- **Prices (`od_last_hour`):** each contract's last traded 30-minute bar starting 15:00–15:30 ET, with the stock's
  unadjusted 30-minute close in the same bar. A contract that didn't trade in the last hour is stale and skipped.
- **Smile (`od_fit`):**
  - European IV via `av_bs_iv`, with dividends escrowed (PV of ex-dates in (entry, expiry]).
  - Then `av_smile_fit` on the out-of-the-money prints; needs `OD_MIN_PTS` = 5.
  - Falls back to every valid print when too few OTM ones traded (`otm_only` False).
- **Spreads:**
  - For k in `OD_KS` (0.25, 0.5, 0.75, 1, 1.5, 2) each way, the target is S·exp(±k·ATM IV·√T).
  - `od_strikes_for`: the call spread's upper strike is the highest listed one at or under the target; the put spread's
    lower strike is the lowest at or over it. Adjacent listed strikes.
- **Pricing (`od_price`):**
  - Off the smile with `av_bs`: `q` = debit·e^{rT}/width.
  - `q_flat` = the same strikes at ATM vol.
  - `drift=` shifts the stock by e^{μT} with the smile riding along.
- **Outcome:**
  - `paid` = the spread's value on the expiration close (unadjusted) over its width.
  - A window holding a split (unadjusted/adjusted ratio moves > 1%) is dropped.
  - `inside` flags strikes within the printed range.
- **Rate:** FRED DTB3 per entry day (`od_rate_fn`) with a FRED key, else 4%.
- **Columns saved:** ticker, group (ETF / your list / other stock), expiry, entry, dte, T, r, spot, pv_div, fwd, atm_iv,
  hv20, n_pts, rmse, kmin, kmax, p2/p1/p0 (smile), otm_only, s_T, side, k, target, k_lo, k_hi, width, debit, q,
  q_flat, v_lo, v_hi, paid, inside, built.

## Data and cache
- **`OdClient`:**
  - Massive with a gzip-JSON cache per request in `data/odds_cache/` (atomic; failed requests aren't cached). Stock
    30-minute bars come in calendar half-year chunks, so cache names stay put.
  - Dividends: `/stocks/v1/dividends`, then `/v3/reference/dividends`.
  - Raises `PlanError` on 401/403 from every base.
- **Saved study (`od_save`, `od_load`):** `data/odds_study.parquet` (Massive only; demo builds stay in the session).
  It merges: the (ticker, dte) pairs just built replace their rows. The path resolves at call time.
- **Cost:** roughly names × months × 15 requests (`od_estimate`). The 30 ETFs at 24 months is about 11,000.
- **`odds_build.py`:**
  - The same build from the command line, for an overnight run on the whole list. Exit codes: 2 key/plan, 3 nothing.
  - Usage: `python odds_build.py [--names etf|list|SPY,QQQ] [--n 100] [--dtes 14,30] [--months 24] [--offline]`.
- **`OdDemoClient`:**
  - Synthetic paths (own vol, optional wander, drift, rare gaps down, market factor) and prints from a "market" smile =
    true vol × premium with skew, priced with escrowed dividends.
  - Optional splits and holiday Thursdays.
  - Used by the demo source and the tests.

## Scoring
- **`od_prepare(df, erp, frac, inside_only)`** adds:
  - `q_erp`.
  - `cost`: half-spread on both legs via `av_half_spread` (ETF/stock caps) plus 2 × $0.0065, over width, grown at the
    rate.
  - `gap` = paid − q, `net` = gap − cost, `gap_erp`.
  - `ksig`, `qbin` (labels `OD_BIN_LABELS`), `year`.
- **`od_cmean`:** mean with a standard error clustered by expiry, √(G/(G−1)·Σ cluster sums²)/n (Petersen 2009).
- **`od_table(d, by)`:** spreads, names, expiries, odds, paid, gap, se, t, ret_debit (Σpaid/Σq − 1), net, t_net,
  ret_net, flat, erp_odds, gap_erp, t_erp, verdict.
  - Verdicts: CHEAP t ≥ 2, RICH t ≤ −2, FAIR otherwise, THIN under 12 expiries or 40 spreads.
- **`od_brier`:** smile vs flat-vol Brier and skill.
- **`od_drift`:** the sample's ln(S_T/F)/T per entry, clustered.
- **`od_lookup`:** the study's gap for a live spread's side and odds bucket. It tries the same group and nearest
  horizon, then wider; needs 12+ expiries.

## Tab (`render_odds`)
- **Controls:**
  - `odx_uni`: ETFs (`OD_ETFS`, 30), "My list, most traded" (20-day $ volume, `od_list_names`), or tickers.
  - `odx_n`, `odx_txt`, `odx_dtes`, `odx_months`.
  - Settings popover: `odx_erp` (5%), `odx_cost` (3% of each leg), `odx_inside`.
  - `odx_build`.
- **Filters:**
  - `odx_groups_<groups>`: your list is off by default; a survivorship warnbox appears when it's on.
  - `odx_dte_<dtes>`.
  - Keys carry the study's contents, so a new build resets them.
- **Sections:**
  1. Calibration: KPIs (spreads, expiries, up and down gap ± 2 s.e., Brier skill, drift over the forward), the
     calibration chart (THIN cells left off), and the bucket table.
  2. By move: gap ± 2 s.e. with net hollow points, and a table with N(−k), flat, market odds, paid, return gross and
     net, and beyond the drift check.
  3. Splits (`odx_split`): group, year, SPY vs its 200-day at entry, IV/HV20 thirds, IV level thirds, horizon.
  4. The cumulative gap per expiry, the biggest expiries, and the average with and without the 3 biggest.
  5. Today: `odx_ltxt`, `odx_ldte`, `odx_lk`, `odx_lgo`.
     - `od_live`: `fetch_chain`; prints from today's session when 5+ are out of the money, else all; the same fit and
       pricing.
     - Shows legs, debit, width, pays (W−D)/D, market odds, flat odds, the history gap and t, odds + history, and EV
       per $1 gross and net.
- **Guide:** `OD_GUIDE`, with sources:
  - Moontower (both posts)
  - Breeden-Litzenberger 1978
  - Coval-Shumway 2001
  - Bondarenko 2014
  - Bollen-Whaley 2004
  - Bliss-Panigirtzoglou 2004
  - Carr-Wu 2009
  - Petersen 2009
  - Snowberg-Wolfers 2010

## Findings while building
- **The skew's effect on vertical odds is not "puts dearer, calls cheaper".** A smile sloping down makes the
  risk-neutral distribution left-skewed:
  - Near-the-money call verticals and far put verticals get higher odds than flat vol.
  - Near-the-money put verticals and far call verticals get lower odds.
  - The tests check the exact identity q = N(d2(σ(K))) − e^{rT}·vega·σ′(K) (Breeden-Litzenberger with the smile's
    slope), and the tab's notes say so.
- **Synthetic checks:**
  - A vol premium of 35% with skew made the far put verticals and the near-to-1 sd call verticals RICH. The
    near-the-money put verticals stayed about fair.
  - A 60% drift made calls CHEAP and puts RICH, and the drift check at the planted premium explained most of it.

## Tests
- **`test_odds.py` (54 checks):**
  - OCC, third Fridays, the vertical picker, half-year chunks.
  - Last-hour prints.
  - Pricing: smile recovery, vertical = C(K1) − C(K2), call + put odds = 1, tight flat vertical = N(d2), the
    Breeden-Litzenberger identity with skew, drift direction; under-5 prints; the ITM fallback.
  - Clustered s.e. by hand.
  - A fair market (ATM IV = true vol; gaps within 3 s.e.; drift ~0; strikes, targets, paid and S_T by hand; 30-day
    entries).
  - A 60% drift; a 35% vol premium with skew and the skew pattern.
  - Dividends (forward and flat smile), a 4:1 split dropped, a holiday Thursday, two horizons.
  - Save/merge (atomic), the cache (0 calls the second time; failures not cached; 403 raises).
  - THIN, lookup, live call/put verticals on a demo chain, `odds_build.py` (build + merge).
- **`apptest_odds.py`:** the whole tab headless:
  - The ETF build at 14 and 30 days; calibration and by-move tables; every split; both horizons.
  - Live ±1 sd with the history beside it; settings.
  - List build with the survivorship warning; custom tickers.

## Open
- **First live build:** `python odds_build.py --names SPY,QQQ,IWM --months 6`, then compare a few ATM IVs with a known
  chart before the full ETF run. The live Massive paths are untested here (no key): option 30-minute bars, contracts
  with `expired=true`, dividends.
- **Earnings aren't excluded.** Single names' expiries that hold a report carry event vol.
- **Flat Files** (options minute aggregates) aren't wired in; the Moontower desk's `iv_backfill.py --flatfiles` reads
  them and could feed this.
