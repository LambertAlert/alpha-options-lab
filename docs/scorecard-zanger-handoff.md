# Scorecard and Zanger additions (Nov 9 2026, late)

Neil asked what would fill the project's gaps and suggested Dan Zanger's volume breakout and grading trades like
baseball (Joe Peta, *Trading Bases*). He said to build both.

## Stocks > Scorecard (`render_tc`, block before LEARNED MODELS)
Your own closed share trades, graded. Tab `S[15]`; Learned ranker and later tabs moved to `S[16..20]`.

**The log**
- `data/trade_log.csv` (env `LAB_TRADE_LOG`), columns `TC_COLS`: ticker, entry_date, entry, init_stop, exit_date, exit, shares, setup, note.
- `tc_clean` reads loose headers (`TC_ALIASES`), drops bad rows and repeats. `tc_load` / `tc_save` (atomic).
- In the tab: an editable table, a CSV merge, "Load example trades" (`tc_examples`, 60 made-up trades), "Save the log".

**Measures (`tc_measure`)**
- R = entry less the initial stop; 1.5 ATR assumed and flagged when none was logged. Costs 10 bp a side.
- Entry timing = share of the entry day's range saved; exit timing likewise.
- MFE / MAE over the hold, capture = R / MFE for winners, sessions held, `past_stop` (loss worse than 1.2R), chase (entry over the prior close).
- `plan_r`: the plan from the same entry and stop, one `lg_label` call per trade:
  - The entry bar's open is set to the fill and its low to min(fill, close), then both are restored.
  - Plan = cut at day 1's close under the entry, then the Simulation's plan, out by session 60.
  - A recent trade is compared with the plan so far (marked at the last close).

**Run expectancy split (`tc_spots`)**
- The spot = the plinko path the name was on at the close before the entry.
- base + entry_v + luck + exit_v = r, where:
  - base = `pk_baseline` (every finished arrival, by date);
  - entry_v = the path's E[R] (arrivals, by date) − base;
  - luck = plan_r − the path's E[R];
  - exit_v = r − plan_r.
- The spot's E[R] uses the plinko's stop (the signal day's low), so entry and luck are in slightly different R units.
- `pk_build(cfg, ab, ss)` now builds the plinko for both tabs; grading builds it if it isn't there.

**Process grade (`tc_grade`, 100 points)**
- Spot 30 (path rank; 0 if extended or Stage 4; 15 if unranked), risk 15 (logged stop 0.25-3 ATR), chase 15 (≤ 5% over the prior close), stop 25 (never past 1.2R), exit 15 (a winner kept half its MFE, or a loser was out within 5 sessions).
- A 85+, B 70+, C 55+, D 40+. Outcome grade from R alone. The 2 x 2 uses process ≥ 70 and R > 0.

**Cluster luck (`tc_cluster`)**
- The trades in closing order against 5,000 reshuffles at 1% risk each: percentile of the worst drawdown and the longest losing streak, plus the t of mean R.

**The card (`tc_card`, `tc_card_chart`)**
- Six 0-100 scores in Savant's colours: entry timing, capture, stop discipline, cut speed (chance a winner was held longer than a loser), spot selection, exits vs the plan.
- The card and cluster luck need 10 graded trades (`TC_MIN`).

## Zanger
**Setup ledger family "Zanger" (`zg_signals`)**
- Base = the prior 15 sessions (`ZG_BASE`), no deeper than 15% high to low (`ZG_DEPTH`), its high within 15% of the prior 52-week high, in a name over a 50-day that is higher than 10 sessions ago.
- The line = the base's high. A breakout = a close over the line and no more than 5% past it (`ZG_CHASE`).
- `zg:vol`: on 1.5x+ the prior 30 sessions' average volume (`ZG_VOL`).
- `zg:quiet`: the same breakout on less. It is the control, so the ledger shows what volume adds.
- Stop kind `zgb`: the line less 1 ATR ("back in the base"). Exit seed: trail. Type in Alphas by trade: Breakout.
- The base is a stand-in for his hand-drawn trend lines; his rules don't define a pattern numerically.

**Volume pace on Stocks > 30-min pivots (`pv_pace`)**
- The session's volume so far at each 30-minute bar, as a percentage of the median by the same time of day over the prior 20 sessions (5 needed).
- Shown on today's triggers as "volume pace %" with a band: under 60 drying up, 60-120 normal, 120-200 heavy, 200+ extreme. The bands are this lab's, not Zanger's.

## Tests
- `test_scorecard.py`, 48 checks:
  - the log; one trade by hand (R, timing, MFE, capture, the plan); the split adding up; the grade's parts and the 2 x 2;
  - cluster luck on a planted bad and good order; the card's scores;
  - an end-to-end run on a panel;
  - Zanger's breakout by hand (volume, control, chase, loose base, stop, the ledger event); the volume pace by hand.
- `apptest_tc.py`: examples, grade, the KPIs, the card, save, and no error box on any tab.

## Open
- The log holds closed share trades only. Option trades stay in the Grader's log.
- Nothing imports fills from a broker; it is typed or merged from a CSV.
- Entry-day timing and MFE are approximate on daily bars (the order of that day's high and low is unknown).
- The plinko baseline (paths scored against the same-date baseline) is still unbuilt; the Scorecard's entry part already uses a baseline of its own.
