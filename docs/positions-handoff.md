# Alpha & Options Lab: Positions tab (Oct 26 2026)

Neil asked how to evaluate open positions, including when to trim or sell one for a better opportunity, as a tab.
It's a new top-level tab, **Positions**, between Brief and Market. It renders after the Brief in `main()` (so the
Brief's list is fresh) and as an `st.fragment`. The code is the POSITIONS block just above `main()`.

## Where the positions come from
- It reads the Book file, `data/book_positions.csv`, the same one the Book tab edits.
- `BOOK_COLS` gained `entry_date`, `init_stop` (the stop at entry: 1R = entry − this), `trimmed` and `setup` (a ledger
  setup id).
- `load_book` adds the new columns to old files. `pos_book_rows` cleans the share rows; the initial stop falls back to
  the stop.
- With no saved Book, or none of its names in the loaded list, `pos_examples` makes five example positions:
  - names that rose into the last bar
  - entered 3–40 sessions ago at that day's open, with a 1.5 ATR stop
  - the first one already trimmed

  Saving writes the share rows and keeps the Book's options rows. The Book tab's placeholder rows are never saved.

## 1 · What the exit plan says today (`pos_status`)
- The plan is the Simulation tab's trim and trail: `sim_plan_of(ss)` → `sim_trade_rules`. Change it in Stocks >
  Simulation > Exits.
- Actions, in priority order:
  1. **stopped**: the last low ≤ your stop.
  2. **cut**: not trimmed (and the target not reached), under entry + fail_r·R at the close of session `fail_n` (or
     any close from then on, in every-close mode), and still under it. If it has recovered since, the position
     holds with a note that the plan would have sold it then.
  3. **sell_rest**: trimmed, with `ma_closes` closes in a row under the plan's average.
     With the exit-signals runner (Nov 3), a distribution day or climax on the last bar also fires it; under a
     no-target plan (trim at 0R) the same rules fire **sell_signal** ("SELL: exit signal") on an untrimmed
     position, and no trim level is shown. The chart marks signal days with red triangles.
  4. **trim**: the high since entry reached entry + tgt·R and the position isn't marked trimmed.
  5. **raise**: your stop is under the plan's. The plan's stop is breakeven, or +lock, once trimmed or once the
     target is reached; the chandelier if that's the exit; breakeven at +be_r if set.
  6. **extended**: the last high is 20% or more over the 50-day (40% is climactic). From TraderLion, *Master the art
     of selling*.
  7. **hold**.
- Also shown: open R, best and worst R, the plan's average, the high vs the 50-day, the RS rating (`lg_rs_rating`),
  the group percentile (`ga_lab_state`), and days to earnings (the universe's `bc_earn`). A warning appears for
  earnings inside 10 days.
- The table, then a *To do* list with each reason in full.

## 2 · What holding is worth from here (`pos_trades`, `pos_continuation`, `pos_window`, `pos_wstats`)
- Needs the Setup ledger for your list. `_pos_ledger_run` offers the build button.
- The ledger is re-run under the plan by `sim_relabel_cached`. That's one session slot shared with the Simulation,
  keyed by run id and plan tag. `sim_relabel` now also returns `trim_date` and `trim_px`.
- For each position, the ledger trades that were alive at the close of the same session held, in the same trimmed
  state (trimmed, or target reached), weighted tricube by |open R − yours|. The bandwidth starts at 0.5R and widens
  to 150 trades.
- The pool is the setup's own trades, else its family's, else every setup's. With too few trades it steps back to
  80/60/40% of the days held.
- The value per share after H sessions:
  - the trim share at its price, if the trim falls in the window
  - the rest at its exit, if that falls in the window, else the close H sessions on

  Windows that run past the data on still-open trades are dropped.
- Shown: the weighted mean, a Bayesian-bootstrap 90% band, P(loss), the 10th and 90th percentiles, the median
  sessions still held, the effective count and the pool.

## 3 · Hold or swap (`pos_new_trade`, `pos_swaps`)
- **Candidates:** the Brief's names (`ss["brief_top"]` via `sim_brief_candidates`, not already held), each on its
  ledger setup.
- **Return measure:** the return on the entry price over the setup's trades' first H sessions, trim included. It's
  the same plan and window as the positions.
- **Swaps:** every (sell, buy) pair. The gain is the new name's E minus the position's E minus 2 × cost per side.
  P(new does better) comes from 4,000 independent weighted draws.
- **On screen:**
  - KPIs: weakest position, best new name, best swap
  - a hold-vs-buy dot-and-band chart
  - the Brief's names as new trades (expander)
  - a *Swaps worth a look* table
  - a note when the best swap has under a 50% chance of doing better, because few large winners lift its average
- **Not in it:** taxes and position size. The note says a breakeven position frees capital but no risk.

## 4 · One position up close
- A price chart since entry, with the entry, the initial stop, your stop, the plan's stop, the trim level and the
  plan's average.
- A histogram of the look-alike returns, next to the best new name's.

## Controls (session keys)
`pos_ed_ex` / `pos_ed_bk` (the editor), `pos_save`, `pos_build`, `pos_h` (sessions ahead, default 20), `pos_cost` (bp
per side, defaults to the ledger's), `pos_pick`.

## Demo read (illustrative)
- Of the five example positions, one stop was hit, one trim plus a stop raise is due, one time-stop cut is due, and
  two hold.
- Expected returns over 20 sessions ran from −0.35% (KEYS, 3 sessions in at −0.87R) to +1.0% (HNGE).
- The best swap was KEYS → STNG: +1.4% after costs, but only a 45% chance of doing better.

## Tests
- `test_positions.py` (31 checks) on planted bars:
  - each action, plus the recovered-time-stop case
  - an outside name, and a missing initial stop
  - R, open R and best R, value and risk
  - every-close mode
  - window values by hand: trim inside the window, trimmed before, an incomplete window dropped
  - continuation pools: setup, trimmed state, fallback
  - new-trade windows, swap gain and costs
  - Book back-compatibility and saving, and readable example positions
- `apptest_positions.py`: the whole tab headless, then saving to the Book file and reloading. It backs up and
  restores any real `data/book_positions.csv`.
