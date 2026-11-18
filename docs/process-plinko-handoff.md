# Process plinko: Stocks > Process plinko (Nov 9 2026)

Neil sent a screenshot of Baseball Savant's Pitcher Plinko and asked whether it could become a workflow for finding the
best names in his process. He asked for both views:
- the process as a funnel, today and over history;
- one name's own plinko.

## How the Savant idea maps onto the process
| Savant | Here |
|---|---|
| Ball-strike counts (nodes) | Process stages, top to bottom |
| Pitches that move between counts (line thickness) | Name-days that make the move |
| Pitch mix at each count (the ring) | What a trade started there did: ran 2R+ / held / cut day 1 |

## 1 · The funnel
- **Eligible:** $10+ and $10M+ a day traded (the ledger's floors), with 260 sessions of warm-up.
- **Trend, three nodes:**
  - Stage 2 = a close over a rising 150-day (vs 20 sessions ago), with the 50-day over the 150-day.
  - Stage 4 = a close under a falling 150-day.
  - Stage 1 or 3 = anything else.
- **Leadership:**
  - RS rating 80+ (`lg_rs_rating`).
  - "lg" when the group's RS is also 80+ (`industry_rs_panels` over `resolve_groups`).
  - "new" for a name with under 252 sessions: no rating yet, its own node.
- **Location, in priority order:**
  1. Extended: 3+ ATR over the 21-day.
  2. The 8-week pocket: −3% to +6% around a rising point-in-time 8-week EMA (`pv_ema8w`).
  3. Within 1 ATR of a rising 10- or 21-day EMA.
  4. Above the 21-day EMA (1-3 ATR over it, or over averages that aren't rising).
  5. Below the 21-day EMA.
- **Trigger, in priority order:**
  1. A pocket pivot that day (`pv_context`'s `pp_day`).
  2. A Setup-ledger signal: non-baseline events in `lg_res["runs"]["list"]["ev"]`, once the ledger is built this session.
  3. A 30-minute trigger: `_pv_res` trades, excluding the open entry and wide stops, once the 30-min study has run.
  4. None.
- **Outcome (`pk_outcomes`):** a Luk-style trade from every name-day.
  - Entry at the next open; the stop is the day's low, held to 0.5-3 ATR.
  - Cut at day 1's close if it's under the entry (fail_n 1, fail_r 0, fail_once).
  - After that, the Simulation's plan (`sim_plan_of`), out by session 60 at the latest (`runner_horizon`), 10 bp a side.
  - Codes: "cut" = cut, or stopped on day 1; "run" = R ≥ 2; "held" = everything else.
  - A trade still open at the end of the data has no outcome.
- **Display:**
  - "Today's names" mode: lines are today's name-days. History mode: lines are 1-3 years of name-days.
  - Rings and E[R] always come from history. The outcome row shows each outcome's share of past trades.
  - A replay slider covers the last 60 sessions.
  - The best path is traced as a dashed line.
- **Best paths (`pk_paths`):**
  - Scored on arrivals: one trade per name each time it lands on the path (`arr` in `pk_flows`).
  - A path needs the minimum arrivals (30 by default) on 60+ dates (`PK_MIN_DATES`).
  - Per path: E[R] averaged by date, a Newey-West t, a BH q across the ranked paths, the outcome mix, and the names on it on the chosen session.
  - Scored at render time, so the minimum applies without a rebuild.
- **Where a name sits (added Nov 9, Neil asked for a marker in the image):**
  - A multiselect, "Show where these names sit" (`pkx_mark`), takes up to 6 names.
  - On the chosen session, each name's nodes are circled and its route is traced in its own colour (`PK_MARK_COLORS`), with "◀ TICKER" at its trigger node.
  - When names share a node, the rings grow and the labels stack (`pk_mark_frames`).
  - By default it marks section 3's name: the first name on a top-3 path today.
  - Under the chart, `pk_name_rows` builds a table: where each name sits, its episode state, its route's past trades, E[R], ran 2R+ / cut on day 1, and its best-path rank. A name outside the funnel that session is said to be outside.
- **Node drill-down:** the names in any node on that session, with RS and distance from the 21-day in ATRs.

## 2 · One name
- **Episode states (`pk_states` `epi`), in priority order:**
  1. Extended: 3+ ATR over the 21-day.
  2. Breakout: a new 20-day closing high.
  3. Pullback: the pocket, or near the 10- or 21-day.
  4. Broken: under the 50-day.
  5. Base: everything else.
- **Building it:** `pk_episodes` collapses runs of one state, and the trade on each episode's first day is its outcome. `pk_name_graph` gives per-state episodes, median days and E[R], plus move counts and shares.
- **Chart:**
  - States sit on a line; moves to the right arch above it, moves back arch below.
  - Thickness = how often the move happened. A ring = the outcome of trades on entering that state.
  - The current state is circled.
- **KPIs:** the current state and its run length against the usual, the most likely next state, and the E[R] of entering it.
- **Also shown:** the next-state table and a strip of the last 120 sessions' states.

## Code (alpha_options_lab.py, after the 30-MINUTE PIVOTS block)
- **Constants:**
  - `PK_ROWS`, `PK_OUT`, `PK_OUT_COLOR`, `PK_EPI`, `PK_EPI_X`, `PK_MIN_N`.
  - `PK_DEFAULTS`, keys `pkx_*`: years, mode, min_n, hold, ext, near, day, node, name.
- **Engine:** `pk_states`, `pk_outcomes`, `pk_flows`, `pk_paths`, `pk_episodes`, `pk_name_graph`.
- **Charts:** `_pk_ring_df` builds arc slices for `mark_arc`, `pk_funnel_chart(F, H, title, hl=path)` and `pk_name_chart`.
- **Signals:** `_pk_signals(ss, idx, cols)` returns the ledger and 30-min flags, plus notes for whatever is missing.
- **UI:** `render_pk(cfg, ab, bars)` runs as a fragment in Stocks `S[14]`. Learned ranker and the tabs after it moved to `S[15..19]`.
- **Module docstring:** the index has a Process plinko entry.
- **pandas 3:** `.values` is read-only, so flag panels are built from numpy arrays.

## Tests
- **`test_pk.py`, 60 checks** (8 cover the name markers: circles on its nodes, route order, colours, label at the trigger row, shared-node stacking, the route table, an ineligible name):
  - Codes and floors: the allowed codes, the $10 floor, the warm-up, and blanks that agree across rows.
  - Stage 2 by hand.
  - Leadership: "lg" vs "rs" with a planted group RS; RS under 80 gives "no".
  - Priorities: pocket before near; extended; trigger priority with planted ledger and 30-min flags; the episode states.
  - Outcomes by hand:
    - a day-1 close cut: −0.4R − 0.2R costs;
    - a run to 2R+;
    - a day-1 stop: −1.2R;
    - only the requested days trade;
    - a trade still open at the data's end has no outcome.
  - Conservation: nodes = eligible name-days, edges conserve counts, node E[R] = the mean, ring shares sum to 1.
  - Best paths: the planted good path ranks first with t > 2, and a thin path is dropped.
  - Episodes and moves.
  - Charts build, including with empty inputs.
  - A random walk shows no overall edge and no path with t 3+.
- **`apptest_pk.py`:**
  - build; KPIs; the best-paths table; the missing-ledger note;
  - a node; another name;
  - history mode; replay; changing the history length gives the stale note.
  - Demo: 432 names, 218k name-days, 144 s to build.

## Caveats and open items
- **Survivorship:** history is today's list.
- **Short episodes:** episode states flip often, and many demo episodes last 1 day. If real data reads too noisy, the next step is a minimum episode length (2-3 sessions) or hysteresis.
- **Multiple testing:** about 96 paths are tested, so only trust paths with t 2+ and many trades. A BH q per path would be a natural addition.
- **Ledger triggers:** the trigger row only gets Setup-ledger signals after the ledger has been built this session (the saved ledger file isn't read).

## Review findings (Nov 9 review pass; the six "To fix" items were applied the same day, see `claude/lab-review-fix-list.md`)
Checked by reading the code and by experiments on synthetic panels (scripts were scratch, not kept in the repo).

**Confirmed correct**
- States use only data up to that day's close; the outcome codes match `LG_OUTCOME` (5 = cut, 1 = stop) and `hold` = 1 for a day-1 exit.
- Counts conserve through the funnel; no manufactured edge: on a true martingale with consistent intraday bars and no costs, the mean path t is +0.08.
- No bias from quick losers at the end of the data: `lg_label` drops every trade with fewer than 60 future bars, so the last 60 sessions add nothing to history.
- A next open under the signal day's low is no trade (about 7.6% of name-days on a random walk).

**To fix**
1. **The path t overstates significance.** On the martingale, |t| ≥ 2 on 16% of paths (5% expected); paths with under 60 dates have a t with sd about 2.9.
   - Cause 1: every day a name sits on a path is a separate trade, and consecutive days are near-duplicates.
   - Cause 2: small samples of a skewed outcome (many small losses, rare big wins).
   - Counting only the day a name arrives on a path brings paths with 150+ dates close to nominal (sd 1.1-1.2).
   - Fix: count arrivals, require 60+ dates, add a BH q (`lg_bh`), and stop marking the Best path KPI "good" at t 2.
2. **Two E[R] conventions on one screen.** Node labels and `pk_name_rows` average by trade; `pk_paths` averages by date. The same route showed +0.10 and −0.00 in the demo.
3. **"Best paths: min trades" does nothing after a build.** `rec["paths"]` is computed in the build only, and the caption prints the new number over the old table. Fix: compute `pk_paths` at render time.
4. **Location priority hides extension in low-volatility names.** Pocket wins over extended, so at ATR 1.2% of price, 80% of days 3+ ATR over the 21-day are labelled "8-week pocket" (none at ATR 2.9%+). The episode view uses the opposite priority. Fix: extended first in both.
5. **Names with under 252 sessions get "RS under 80".** `lg_rs_rating` is NaN for them, and `rs >= 80` is then False. Fix: a shorter-window RS for young names, or a separate "too young to rank" code.
6. **"60 sessions at most" is not true after a trim.** The runner has no time limit (`runner_horizon` 0): max hold 149 sessions in the test, 0.8% of trades over 60. Runners still open at the data's end are dropped, a small downward bias in the most recent months. Fix: pass `runner_horizon=hold`, or mark open trades at the last close.

**Design points**
- RS and group ranks are within the 435-name list (already a strong-name screen), not the market.
- No baseline: a path's E[R] should be shown against all eligible names on the same dates.
- Per-name numbers rest on 5-50 episodes; show the all-names figure beside them.
- The Setup-ledger trigger lumps every family (dip buys with breakouts); 30-minute triggers exist only on days the 30-min study sampled; a market-only ledger still shows "build the ledger".
- Replay moves the names but the rings and best paths use all history, including sessions after the replayed one.
- Median hold is 1 session and about half of trades are cut on day 1 by construction, so the red share of a ring mostly reflects the rule.
- A worst-paths list (what to avoid) would serve the "don't buy extended" question.

## Steps checked on real prices (Nov 9, late)
Neil asked whether the steps make sense and whether the picture changes on real data. Checked on 27 watchlist names
(every 11th ticker with enough history), April 2024 to Nov 9 2026, in SQL on the Massive connector. Averages were
simple, not exponential, and the 8-week EMA was a 40-day SMA, so the shares are approximate.

- **Trend:** Stage 2 on 48% of eligible name-days, Stage 1 or 3 on 27%, Stage 4 on 26%. "Not Stage 2" was two equal groups, hence the split.
- **Location:** pocket 18%, near the 10/21-day 33%, extended 6%. The old "In between" held 43%, and was two different things: 14% above the 21-day (average +1.8 ATR) and 29% below it (average −1.7 ATR). Hence the split.
- **Trigger:** a pocket pivot on about 1.6% of name-days (about 3% in the pocket or near the averages, 0% below the 21-day). Thin on any one day, usable over history.

**Changes**
- `pk_states`: trend codes `s2` / `s13` / `s4`; location codes `pocket` / `near` / `above` / `ext` / `below`.
- Episode labels: "At support" (was Pullback) and "In between" (was Base, which never tested tightness). The codes are unchanged.
- `pk_positions(seq, present)`: a node no name-day reached takes no place in the chart, so the unbuilt trigger nodes disappear until their source is built.
- The line colour scale spans the moves' own E[R] (90th percentile of |E[R]|, between 0.05 and 2).
- The guide says a no-trigger day is the baseline.

**Still open:** the per-name states are untested on real data for day-to-day flicker.
