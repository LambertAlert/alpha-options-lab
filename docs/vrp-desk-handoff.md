# Alpha & Options Lab: VRP desk (American) (Oct 27 2026)

Neil asked to go deeper on American options: find mispricings with the VRP, then exit or hedge as they correct, using
spreads to limit risk. His choices:
- **Side:** both, signed by the VRP.
- **Protection:** compare defined-risk exits and a share delta hedge in a simulator.
- **Universe:** SPY, QQQ and IWM plus his names.
- **Data:** Options Starter, with no quotes.

It's a new Options sub-tab, **VRP desk (American)**, second after Vol desk. Main shifts `O[1..6]` to `O[2..7]`. The
code is the VRP DESK (AMERICAN) block just above `render_dealer`. Function prefix: `av_`.

## Pricing: American throughout
- **`av_tree`:** a vectorized CRR tree over a batch of contracts on one underlying.
  - Discrete cash dividends use Hull's escrowed-dividend tree: the stock less the PV of the dividends is the random
    part, and the PV is added back at each node for the exercise check.
  - Rate is continuous.
  - Returns `price`. With `greeks=True` it adds delta, gamma and theta (per calendar day) from steps 1–2. With
    `with_euro=True` it rolls the European value back on the same tree.
  - Node prices are precomputed once (`U`). 1,000 contracts at N=150 take about 0.12 s.
- **`av_bs`, `av_bs_iv`:** European price with a rate and escrowed dividends, and a vectorized bisection IV (NaN
  outside the no-arbitrage range).
- **`av_american_iv`:** de-Americanizes the mark.
  1. EEP = American − European on the same tree, so the tree's error cancels.
  2. BS-invert mark − EEP.
  3. Repeat (2 passes).

  NaN when the mark is under intrinsic.
- **`av_baw`:** Barone-Adesi–Whaley with a continuous yield q. It's for the simulator's daily repricing.
  - Calls with q=0 are European.
  - Puts are within about 10¢ and 2.5% of a 1,000-step tree.
- **`av_yield_equiv`:** the yield that removes the same dividend PV.
- **`av_dividends`:**
  - Massive: `/stocks/v1/dividends`, filtered on `ticker` and `ex_dividend_date.gte`. It keeps declared future
    ex-dates and drops non-USD rows. It projects the last recurring dividend forward at its `frequency`, skipping
    dates near a declared one. Specials are not projected.
  - Demo: a synthetic quarterly schedule (SPY 1.2%, QQQ 0.6%, IWM 1.1%).
- **`av_div_list`:** converts the schedule to `[(years, cash)]`.
- **`av_rate`:** FRED `DTB3`, turned from a discount yield into a continuous rate. Memoized per day. 4% in demo or
  with no key.
- **`AV_STEPS = 150`** for pricing and **`AV_IV_STEPS = 100`** for the IV and the contract table.

## Forecast: HAR-RV (`av_daily_var`, `av_har_fit`, `av_har_forecast`, `av_vol_at`, `av_forecast_err`)
- **Daily variance:** the overnight gap squared plus Garman-Klass. Close-to-close where the bar is incomplete, with a
  floor at 5% of the median.
- **Model:** a direct multi-horizon log-HAR for h in `AV_HAR_H = (5, 10, 21, 42, 63, 126)` sessions.
  - Regressors: day, week (5), month (22) and year (252) terms.
  - One set of coefficients per h, pooled over the scanned names. The yearly term anchors each name to its own
    level.
  - Back-transformed with exp(fit + s²/2).
- **Out-of-sample check:** the last `AV_HOLDOUT = 250` sessions are held out and scored against the trailing RV21.
  It records QLIKE, vol RMSE, bias and the sd of the log error. Then the model is refit on all the data.
- **`av_vol_at`:** interpolates total variance between the fitted horizons and holds flat outside them.
- **`av_forecast_err`:** the out-of-sample log-vol error by horizon.

## One name (`av_name_read`)
- **Expiries:** thinned to the ones nearest 7/14/21/30/45/60/90/120/180 days (`av_pick_expiries`). Strikes run
  ±30%.
- **IV per contract:**
  - The American IV from the print where the print is at least 5¢ and within 25% of the feed's IV.
  - Otherwise the feed's IV. This covers stale prints and deep in-the-money prints with no vega.
- **Smile per expiry (`av_smile_fit`):** a weighted quadratic in ln(K/F) over the OTM side, refit once without
  points more than 3 robust sd off. ATM IV is the fit at x=0.
- **Term table:** ATM IV, the feed's ATM, the forecast, `fair_vol`, `vrp_pts`, `vrp_log`, `err_sd`, `z` and
  `event_in`.
  - Events come from `implied_event` on the American ATM curve.
  - For the event expiry and later ones, `fair_var` adds `event_sd_real²`. That's the name's last four reports via
    `earnings_history` when available. Otherwise it adds the market's own event, so no edge is claimed on it.
- **30-day constant maturity:** `iv30`, `fair30`, `vrp30_log` and `z30`.
- **Contract table:**
  - Values: `value_mkt` (the tree at the smooth smile), `value_fair` (the tree at forecast × smile shape) and the
    European value.
  - `eep`, and delta, gamma and theta.
  - `edge_vrp` = market − fair. `resid_iv` = print IV − smile IV. `resid_px`.
- **`av_signal`:** SELL PREMIUM at ln(IV/forecast) ≥ `AV_RICH = 0.10`, BUY PREMIUM at ≤ `AV_CHEAP = −0.05`,
  otherwise FAIR. Both thresholds are editable under the Thresholds popover.
- **Demo:** `av_demo_remark` re-marks the demo prints on the American tree with the rate and the demo dividends. It
  adds 1.5% IV noise and 9% dislocations on 4% of the strikes.

## Structures (`av_build_structures`, `av_eval_structure`)
- **Strikes by American delta:**

  | Structure | Legs |
  |---|---|
  | Put / call credit spread | short ≈ 0.25 delta, wing ≈ 0.10 delta |
  | Iron condor | both credit spreads |
  | Call / put debit spread | long ≈ 0.50 delta, short ≈ 0.25 delta |
  | Calendar (ATM) | sell this expiry, buy the one about +30 days out, strike nearest spot |

- **Evaluation:**
  - net and edge = Σ qty × (fair − market)
  - max loss and gain from the expiry payoff grid, for single-expiry structures
  - POP: lognormal at the forecast vol, to the forward
  - costs in and out, net greeks, vega by a 1-point bump, and the EEP in the legs
- **Assignment flags:**
  - A short call ITM, or near it, with an ex-dividend date before expiry.
  - A short put that's ITM with time value under K(1 − e^(−rT)).
- **Costs (`av_half_spread`):** a half-spread of 2% of the option's price, capped at 1bp of the stock for ETFs and
  5bp for stocks, with a 1¢ floor. Plus $0.65 a contract.

## Simulator (`av_simulate`)
- **Stock paths:**
  - 5-day blocks of the name's EWMA-standardized returns (`av_std_returns`) at the forecast vol.
  - A per-path vol multiplier of exp(N(−s², s)), with s = the forecast error at H, so E[σ²] is kept.
  - Martingale-corrected to no drift.
- **ATM IV per expiry:**
  - Mean-reverts toward `target × exp(prem)` with the set half-life (0 = never).
  - The target is sqrt(0.6·forecast² + 0.4·path RV₁₀²).
  - The normal premium `AV_NORMAL_PREM` is 0.10 for ETFs and 0.05 for stocks.
  - Leverage per 1-sd stock move (`AV_LEV`): −0.05 for ETFs, −0.025 for stocks. Own shocks (`AV_VOLVOL`) are 0.03 a
    day. The back month's shocks are damped by 0.7.
  - Strikes keep the entry smile's shape in moneyness to the forward.
- **Repricing:** BAW daily, with q taken from the dividends left, and BS-Merton delta for the hedge.
- **Assignment:**
  - A short ITM call the session before an ex-date, when its time value is under the dividend.
  - A short ITM put with time value under max(1¢, 1bp·K).

  Assignment closes the trade at that day's values.
- **P&L:** against the model's own entry value, so BAW's bias against the tree cancels.
- **Rules (`AV_RULES`), all on the same paths:**
  - hold
  - TP: 50% of the max gain (for a calendar, 50% of half the debit)
  - stop: 2× the credit, or 50% of the debit
  - VRP gap: 75% closed, read on a 2-day smoother; needs |gap| ≥ 0.02
  - DTE: exit at 21 days left, or half the life if it's short
  - combined
  - combined + share delta hedge: rebalance to flat when |net delta| passes the band (0.10/share), at 2bp a trade
- **Output:**
  - Table: E[P&L], E/max loss, win, P(loss), the 5th percentile, the worst-5% average, sd, sessions held, and the
    exit mix including assigned.
  - Charts: P&L densities for hold, combined and hedged, and an IV fan with the target.
- **Speed:** about 0.1–1 s at 1,500 paths.

## Tab layout (`render_vrp_desk`)
- **Controls:**
  - Names: Brief, Screener, Top composite or My list, plus SPY/QQQ/IWM. Keys `av_src`, `av_n`, `av_txt`, `av_idx`.
  - Thresholds popover: `av_rich`, `av_cheap`, `av_dte_hi`.
  - Scan button: `av_go`. The result is stored in `ss["av_res"]`.
- **Warning:** an approximate-prices warning whenever Starter (no quotes) or demo data is in use.
- **Sections:**
  1. **Forecast check:** QLIKE and RMSE at 21 and 63 sessions, plus a coefficients expander.
  2. **Board:** a table, plus VRP bars with ±1 forecast error.
  3. **One name (`av_pick`):** KPIs, the term structure against the forecast, the smile (prints, the fitted smile and
     the fair smile), and prints more than 2 pts off the smile (OTM, |Δ| 0.05–0.60).
  4. **Structures:** keys `av_dte_{sym}`, `av_sd`, `av_wd`, `av_cost`.
  5. **Simulator:** `av_struct_{sym}`, the settings popover (`av_n_paths`, `av_hl`, `av_tp`, `av_stc`, `av_std`,
     `av_vc`, `av_dx`, `av_band`, `av_hbp`) and the button `av_sim_go`. The result goes to `ss["av_sim"]`, keyed by
     name, structure, strikes, params and scan time.
- **Guide:** `AV_GUIDE` expander with the sources.

## Demo read (illustrative, synthetic)
On the run screenshotted:
- 13 of 18 names were sell-premium and 4 buy-premium.
- HAR beat RV21 out of sample: QLIKE 0.247 vs 0.334 at 21 sessions, 0.114 vs 0.197 at 63.
- QQQ 45-day iron condor:

  | | |
  |---|---|
  | Credit | $572 |
  | Max loss | $2,678 |
  | Edge after costs at forecast | +$185 |
  | Hold | +$234, worst-5% average −$2,457 |
  | All four rules | +$87, worst-5% average −$1,080 |
  | Plus hedge | +$79, sd $243 vs $336 |

## Tests
- **`test_vrp_desk.py` (75 checks):**
  - tree vs BS (escrowed); American call with no dividend = European
  - Hull's American put (4.28) and its convergence
  - the EEP on a dividend call; tree greeks vs BS; batch = one at a time
  - BAW vs the tree; BAW calls with a yield vs weekly dividends
  - IV round trips; the European inversion's bias on an ITM put
  - dividend parsing on planted Massive rows; DTB3 conversion
  - Garman-Klass by hand; HAR recovering a persistent process and beating RV21 out of sample
  - planted chain: ATM IV recovered, VRP, the stale print replaced, a dislocation found, fair keeps the skew, event
    variance
  - structure legs, max loss, edge by hand, costs, assignment flags
  - simulator: fair → ≈ −costs; same seed; TP, stop and VRP exits; hedge cuts sd; half-life convergence; assignment
    of a deep ITM put at 8% and of a call before a $3 dividend
- **`apptest_vrp.py`:** the whole tab headless. Scan, board, name, structures at another expiry and other deltas,
  the simulator under default and changed settings, the thresholds, a rescan without the ETFs.

## Limits
- No bid/ask on Starter.
- Paths have no drift and no new events.
- The IV model is simple.
- Calendars' max gain is undefined (TP uses half the debit).
- No position size or taxes.
- The Massive live path (dividends, chains, DTB3) wasn't exercised here: no key in the sandbox.
