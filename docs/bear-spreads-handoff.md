# Alpha & Options Lab: Bear spreads (Oct 29 2026; Luk's fade added Nov 2)

> **Update (Nov 2): Martin Luk's fade of the weak bounce.** Two new setups, scored side by side so the table shows
> whether his market condition earns its place. Both use family "Luk" and a `day_hi` stop.
> - `br:luk_fade`: with SPY pulling back.
> - `br:ema_reject`: in any market.
>
> The rules live in `br_fade_parts` (params `BR_FADE`). Brief > Pre-market scanner (Luk) > Fade uses the same
> function; see luk-scanner-handoff.md.
> - **Weak:** under the 50-day EMA, with the 21 under the 50 and both falling.
> - **Converging:** the 21 and 50 within 1 ATR14.
> - **Bounce:** a close in the last 3 sessions at least 1 ATR over the lowest close of the 10 before it.
> - **Light volume:** the 3-day average ≤ the 50-day average from before the bounce.
> - **Rejection:** the high within 1% of the 21-day EMA, then a close under it: red, in the bottom half of the range.
> - **Market pullback (`br_market_pullback`):** SPY under its 21-day EMA, or 3%+ off its 20-day closing high.
>
> Plumbing:
> - `br_states` now also returns `e21`, `e50` and `atr14`.
> - `br_signals(..., mkt_pb=)`, `br_chunk(..., pb=)`; `br_run` builds the SPY pullback series and passes it down.
>   Without a market series only `br:ema_reject` fires.
> - Entry and exit are the ledger's own (next open or under the rejection day's low; target and time limit). His hourly
>   entries (prior hourly bar's low, VWAP retest) and exits (a partial at 3R, out on an hourly close over the 50-day
>   EMA) aren't modelled.
>
> Demo read (synthetic, meaningless): both NOISE; the market-pullback version had t +1.6 vs the baseline, the
> any-market one +0.5.
>
> Tests: `test_fade.py` (22 checks), and `test_bear.py` still passes 45. `apptest_bear.py` shows both setups on the
> list and the whole market.

> **Update (Oct 29, later):** Bull spreads now shares this engine; see bull-spreads-handoff.md. Renamed: the debit spread's fields `pd_*` → `db_*`, the credit spread's `cc_*` → `cr_*`, live structure keys `put_debit`/`call_credit` → `debit`/`credit`, candidate strike strings → `debit_legs`/`credit_legs`, and `br_price_spreads(cc_short=)` → `credit_short=`. Options sub-tabs: Bull spreads is third, Bear spreads fourth. Today's plan now caps 1R at 3 ATR (floor half an ATR), as the history does.

Neil asked whether the mean-reversion alpha, or another factor, could drive bear put and bear call spreads, then asked
to build it with short-dated spreads rather than 30 days.

It's a new Options sub-tab, **Bear spreads**, third after Vol desk and the VRP desk. Main shifts `O[2..7]` to
`O[3..8]`. The code is the BEAR SPREADS block between the VRP desk and `render_dealer`. Function prefix `br_`; session
keys `bsp_` (`br_` was taken by another tab).

## Who to be bearish on
- **Former leader that topped (`br_states`):**
  - `leader`: an IBD-style RS rating (`lg_rs_rating`) of 90+ at some point in the last 252 sessions.
  - `topped`: a leader now 15%+ (`BR_FL_OFF`) under its 126-session closing high, under a 50-day that is lower than
    10 sessions ago.
  - Read from each name's own history, so names that dropped off the weekly screen still qualify.
- **Downtrend:** under a falling 50-day. This is also the baseline.
- **Former leaders file:** `data/former_leaders.csv` (`br_former_list`, `br_save_former`; atomic). Its names are added
  to the list universe by `br_list_panel`.
  - `former_leaders_from_git.py` builds the file from every past version of `watchlist_input.csv` and
    `sector_themes.csv` in the pivot-scanner repo.
  - It reads with `git log --follow` and `git show`, and writes the tickers that aren't on HEAD with their first and
    last seen dates and how many versions they were on.

## Setups (`BR_SETUPS`, `br_signals`)

| id | Fires when | Stop |
|---|---|---|
| `br:fl_rally_fail` | Topped leader; was under its 50-day 5 sessions ago; high within 2% of the 50-day in the last 3 sessions; closes back under it, red, in the bottom half of the range | `hi3`: highest high of the last 3 sessions |
| `br:fl_break50` | Leader that spent 15 of the last 20 sessions over the 50-day; first close under it on 1.4x the 50-day volume; within 25% of the yearly high | `day_hi`: signal-day high |
| `br:fl_mrv` | Topped leader, mean-reversion percentile ≤ 15 | `hi3` |
| `br:mrv_fade` | Downtrend, mean-reversion percentile ≤ 15 | `hi3` |
| `br:ep_down` | Gap down ≥ 4% on 3x the 50-day volume, closing in the bottom half | `day_hi` |
| `br:dc20_dn` | New 20-day low under a 150-day that is lower than 20 sessions ago (Stage 4) | `n2`: close + 2N |
| `br:luk_fade` | Luk's weak bounce rejected at converging falling EMAs (see the Nov 2 update), SPY pulling back | `day_hi` |
| `br:ema_reject` | The same, in any market | `day_hi` |
| `base:downtrend` | Every 5th session for any downtrend name | `hi10`: 10-day high |

- **Mean-reversion percentile (`br_mrv_pct`):** the composite's mean-reversion category, i.e. alphas #4, #24 and #30
  via `compute_alphas`, each turned into a cross-sectional percentile, averaged, then ranked again (0–100).
  - Low means overbought: three up days, the low at the top of its 9-day range, stretched over the 100-day low.
  - The long composite inverts this category.
  - VWAP falls back to the typical price for the market panel.
- **Fallback stop:** the 10-day high, then the close plus 1 ATR.

## Scoring
- **`br_label`:** runs `lg_label` on prices mirrored about M = 3 × the name's max high + 1 (price → M − price, with
  high and low swapped).
  - Every barrier rule carries over: gaps through the stop fill at the open; trigger entries fill on a break of the
    signal-day low, are cancelled on a close over the stop, and fill at the open on a gap under.
  - R and the % return are recomputed on real prices with costs.
- **Entries:** the next open, or under the signal-day low (trigger).
- **Exits:** target at `tgt` R (default 1.5); time limit = spread life (3, 5 or 10 sessions).
- **`br_chunk` / `br_run`:**
  - RS rating and the mean-reversion percentile are computed on all names at once; the rest runs in blocks of
    `LG_CHUNK`.
  - Floors per event: price and 20-day dollar volume.
  - Each event's forward short return is `fwd` = −(close at i+H ÷ open at i+1 − 1); `xs` = `fwd` minus the downtrend
    baseline's same-date average.
  - Also: the SPY context, today's state per name (`fl`), and the SPY pullback series for `br:luk_fade`.
- **`br_score` / `br_cell` / `br_verdict`:** these mirror the long ledger.
  - Date-averaged E[R] with Newey-West errors.
  - Edge t vs the downtrend baseline.
  - Holdout: the last 40% of dates.
  - BH q.
  - PROVEN at t ≥ 3 and q ≤ 0.10 with a positive holdout and positive E[R]; PROMISING at t ≥ 2; NEGATIVE when it
    reliably trails; THIN under 40 trades or 30 dates.
- **Splits (`BR_SPLITS`):** SPY cycle, year, mean-reversion thirds, topped leader or not.

## Spreads on every event (`br_price_spreads`)
- **Expiry:** the close of the trade's last session (entry + H − 1). T runs from the entry open to that close, about
  4, 7 or 14 calendar days.
- **Strikes:** on a listed-style grid (`br_strike_step`).
  - Bear put debit: long the strike nearest the entry, short at or under the target (at least one step).
  - Bear call credit: short at or over the stop (or the first strike over the entry, `cc_short='entry'`), long the
    same width higher.
- **Pricing:** Black-Scholes at HV20 × `iv_mult` (1.15), with put skew iv × (1 − skew × ln K/S), skew 0.5, rate 4%.
  Marked at closes; intrinsic at expiry.
- **Exits:** `follow` closes on the share trade's exit-day close; `hold` runs to expiry.
- **Costs:** a half-spread of 3% of price, capped at 20bp of the stock (`BR_CAP_BP`), 1¢ floor, plus $0.0065 a share
  per leg traded. Nothing to close a leg that expires worthless; the fee only on legs that expire in the money.
- **Return on risk:** P&L over (debit + costs in), or over (width − credit + costs in). A credit under 1¢ isn't scored.

## Tab (`render_bear`)
- **Controls:**
  - Universe: `bsp_uni` (your list + former leaders, or the whole market, shared with the ledger's market panel memo).
  - `bsp_h` (3/5/10), `bsp_tgt`, `bsp_mode`.
  - Settings popover: `bsp_cd`, `bsp_mrv`, `bsp_ivm`, `bsp_skew`, `bsp_cost`, `bsp_stock_bp`, `bsp_cc`, `bsp_px`,
    `bsp_dv`, `bsp_hold`.
  - Former-leaders popover: `bsp_fl_txt`, `bsp_fl_save`.
  - Build: `bsp_build`, result in `ss["bsp_res"]`; warns when settings change.
- **Sections:**
  1. **Topped former leaders today:** KPIs and a table.
  2. **Scoreboard:** split `bsp_split`; KPIs; E[R] ± 2 s.e. chart; spread return-on-risk chart.
  3. **One setup (`bsp_pick`):** R histogram, spread histogram, SPY-cycle table, recent trades.
  4. **Today's candidates (`br_candidates`):** signals in the last 2 sessions with a plan from the signal close, both
     spreads' strikes and estimated prices at the IV proxy, and the setup's verdict.
     - **Chain pricing:** `bsp_cand` and `bsp_live_go` run `br_live_read`, the VRP desk's American read with
       short-dated expiries (`BR_LIVE_DTE`) and the HAR fit on the name plus SPY.
     - **Structures:** `br_live_structures` at the expiry nearest H × 7/5 days, evaluated with `av_eval_structure`.
     - **Simulator:** `bsp_sim_struct` and `bsp_sim_go` run `av_simulate` with `drift` = half the setup's past
       H-session stock move, per session.
- **Guide:** `BR_GUIDE` (now with a "Luk's fade of the weak bounce" bullet).

## Changes outside the block
- `av_pick_expiries(..., targets)` and `av_name_read(..., targets)`.
- `av_simulate` takes `p["drift"]` (log per session), applied after the martingale correction.
- `_av_sim_view`'s note states the drift.

## Demo read (synthetic, meaningless as evidence)
On your list plus former leaders, 5 sessions:
- No setup was PROVEN.
- The mean-reversion fade in a downtrend was NEGATIVE.
- The baseline short was −0.15R.

Real data is the test.

## Tests
- **`test_bear.py` (45 checks):**
  - the mirrored labeler: target, stop, gap through the stop, time limit, trigger fill, gap fill, cancel, opened over
    the stop
  - leader and topped states
  - each setup on planted paths
  - the mean-reversion percentile's direction
  - both spreads on a path by hand: hold, follow, costs, skew, strikes over the entry, not enough data
  - a full demo run's R by hand and edge column; verdicts; split coverage; today's plan
  - live structures from a demo chain; drift lifting the put debit
  - the former-leaders file; the git script on a temp repo
- **`test_fade.py` (22 checks):** Luk's fade rules one at a time on planted charts, the market gate, the ledger event
  and stop, and the Fade screen.
- **`apptest_bear.py`:** the whole tab headless:
  - the file, the list build, every split, setups, candidates
  - chain pricing and the simulator for both spreads
  - 10 sessions with trigger entry and the call strike over the entry
  - the whole market at 3 sessions

  It restores any real `data/former_leaders.csv`.

## Heston pricer (Nov 4 2026)
Settings > *Option pricer* chooses the fixed skew (default) or Heston fitted to today's chains; section 5 fits it, shows the smiles and re-prices this ledger both ways with the setups whose spread answer changes. See `heston-pricer-handoff.md`.

## Pricer audit (Nov 7 2026)
Options Starter does keep two years of option bars (trades, no quotes). Section 6 of both spread tabs audits the ledger's IV level, smile and spread returns against the real prints of those two years. See `pricer-audit-handoff.md`.
