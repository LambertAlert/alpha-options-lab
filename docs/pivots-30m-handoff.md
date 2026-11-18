# 30-minute pivots: find the seat, cut it fast or let it run (Nov 8 2026)

Neil: "Part of Martin Luk's success comes from cutting losers so quickly. This dashboard project gets us into the
ballpark, in the right section; now we need to find our seat." He wants to study a 30-minute pivot entry, especially
around pocket pivots or the 8-week EMA, on the names the dashboard finds, giving a position that is either cut quickly
or left to run. His answers:
- Daily setups: both, compared, plus an any-uptrend baseline.
- 30m triggers: compare three.
- Management: Luk-style cut, then run.

New Stocks sub-tab **30-min pivots** (`S[13]`, after Breakout model; Learned ranker and the tabs after it moved to
`S[14..18]`). It renders as an `st.fragment`. Code: the 30-MINUTE PIVOTS block just before LEARNED MODELS. Prefix
`pv_`, session keys `pvx_`.

## Data
- **`PvClient(OdClient).m30(t, start, end)`:** Massive's adjusted 30-minute bars, one request per half-year. Cached as
  gzip JSON under `data/pv_cache/m30a/` (`$LAB_PV_CACHE`); the half-year still growing is fetched each run.
- **`pv_regular`:** keeps the regular session (9:30 to the 15:30 bar, ET) and adds `day` and `slot` (0-12). Checked
  on a real AAOI response: 13 bars, 9:30-15:30.
- **Yahoo:** keeps only 60 days of 30m bars, so the tab needs Massive or the demo.
- **`pv_demo_m30`:** demo bars. Each session is a Brownian bridge from the day's open to its close (6 sub-steps a bar),
  aggregated into consistent bars, with a U-shaped volume day. A first version forced the daily high and low into
  single bars; those wicks biased tight stops (−0.65R on random data), so it was replaced.

## Daily setups (`pv_context`, known at the prior close: `elig[...]` is shifted one session)
- **Base:** close > a rising 50-day (over 10 sessions), price ≥ $10 and 20-day dollar volume ≥ $10M (the ledger's
  floors).
- **Pocket pivot day (`pp_day`, Morales & Kacher):**
  - An up close on volume above the largest down-day volume of the prior 10 sessions; at least one down day is
    required.
  - Location: at or up to `pp_band` (4%) over the 10-day, or a low within 1% of the 50-day and a close over it.
  - Eligibility: `pp_look` (3) sessions, while the close stays within the band of the 10-day.
- **8-week EMA pocket:**
  - Close −3% to +6% around the point-in-time 8-week EMA (`pv_ema8w`): 2/9 × today's close + 7/9 × the last
    completed week's EMA. The lab's RS 8-week table back-fills the week (look-ahead); this doesn't.
  - Rising: forming EMA > last week's.
- **Any:** the base, sampled every `base_step` (5) sessions per name, offset by a hash.
- **Next-session list:** `ctx["now"]` holds today's unshifted pp and e8.

## 30-minute triggers (`pv_triggers`; the first fill of each session per trigger)
- **pivot30:** `pivot_scanner.py`'s `detect_pivot`.
  - Rule: 3+ red bars (close ≤ open), a green pivot bar, a bar closing over the pivot's high.
  - Entry: the next bar's open (the scanner sees a bar after it closes). Stop: the pivot bar's low.
  - Parity with the War Room's function was tested bar for bar over 40 random sessions.
- **pp30, an intraday pocket pivot:**
  - Rule: a green bar over the prior bar's close, closing in its upper half. Its volume, relative to the same
    half-hour's median of the prior 20 sessions (`pv_rv`), must beat every red bar's in the prior 10 bars.
  - Entry: a buy stop over its high later that session; cancelled if a bar closes under its low first. Stop: its low.
- **fh:** `pivot_scanner.py`'s RANGE_BREAK. A bar after 10:30 closes over the first hour's high on 1.3× the prior 20
  bars' average volume. Entry: the next bar's open. Stop: the first hour's low.
- **open:** the ballpark entry. The session's open; stop under the prior 3 sessions' low, clipped to 0.5-3 ATR.
- **Stop width:** stops under `min_risk` (0.2%) of price are widened to it. 30m stops wider than `max_risk_atr` (1.5
  daily ATR) are skipped and counted as "too wide".
- **Cooldown:** `cd` (5) sessions per setup × entry × name.
- **Live:** `live=True` keeps a signal on the last bar so far as pending (index −1). `pv_today` reports each trigger
  in the latest session, pending or filled.

## Management (`pv_manage`, Luk-style, `cut_d1=True`)
- **Day 1 (30m bars from the fill):**
  - A bar touching the stop exits at the stop (or the bar's open if lower, after the fill bar). Ties go to the stop.
  - The plan's trim can come the same day.
  - Not trimmed and day 1 closes under the entry → out at the close (`cut_d1`). Otherwise the stop goes to breakeven.
- **Then daily bars:** a gap through the stop fills at the open; the trim at the plan's target; the rest on the plan's
  exit. That is moving-average closes (`ma_closes` in a row), the exit signals (`SIG`) or the chandelier, live after
  the trim when `trail_from="trim"`. Time limit `hold` (60); still open at the data's end → outcome `open`, left out of
  scores.
- **Plan:** the Simulation's (`sim_plan_of`, `sim_trade_rules`). Costs `cost` bp a side, in R.
- **The same trade with `cut_d1=False`** gives `r_nocut`: the stop stays at the pivot low until the trim.

## Study and scores
- **`pv_run(P, fetch, prm, plan)`:** builds the contexts, the MA and signal panels, and fetches 30m bars with 8
  threads. `pv_name` produces a row per setup × trigger × entry, memoised across setups.
- **`pv_score(T, elig_n)`, per setup × entry:**
  - Volume and stops: trades, dates, entries per 100 eligible name-days, too wide, stop % and stop in ATR.
  - Day 1: % stopped, % cut at the close, % held; the day-1 losers' average R and the survivors' average R.
  - Results: E[R] date-averaged with NW t (lag 5), win, 3R+, best 5%, the survivors' hold.
  - `vs_open` and `t_vs_open`: the 30m entry less the next-open entry on the same setup.
  - `cut_gain` and `t_cut`: the day-1 cut's value, paired by date against `r_nocut`.
  - Verdicts (`PV_MIN_DATES` 30): EDGE at t ≥ 2, PROMISING at t ≥ 1.5, NEGATIVE at t ≤ −2, THIN, NOISE.
- **Trades:** saved to `data/pv_trades.parquet`.

## Tab
- **Controls:** a plan sentence, History (1/2/3 years, `pvx_years`), the Settings popover (every `PV_DEFAULTS` key)
  and *Run the study* (`pvx_go`).
- **KPIs:** best seat (says "no edge yet" unless EDGE), % cut on day 1 and their average, the survivors' average R,
  the stop size against the ballpark's, what the day-1 cut adds.
- **Section 1:** the matrix and the E[R] ± 2 s.e. chart.
- **Section 2:** one setup × entry (`pvx_cell`). An R histogram coloured stopped / cut / held, a day-1 summary
  (trades, average, total R, hold) and the trade list.
- **Section 3:** the next session's watch list (pocket pivot, 8-week pocket, close, 8w EMA, vs 8w %, 10-day, a pocket
  pivot today) and *Check today's 30-minute triggers* (`pvx_today`, up to `pvx_n_today` 40 names; pending or
  filled, entry, stop, risk %).
- **Guide:** `PV_GUIDE`.

## Demo read (synthetic random paths, meaningless)
- Every cell NOISE or NEGATIVE, near −cost.
- Stops: 30m pivot 0.37%, pocket pivot 0.25%, first hour 0.7%, against 2.4-2.9% for the next open.
- The random-walk test confirms the rules make no R from nothing.

## Tests
- **`test_pv.py` (25 checks):**
  - the real Massive 30m fixture;
  - War Room pivot parity and the next-open fill;
  - the planted pocket pivot (fill at the stop level, cancel) and the first-hour break;
  - live pending;
  - every exit path by hand (day-1 stop, close cut, the no-cut path to the stop, breakeven then a gap, a trim at 2R
    and a 21-EMA close, costs);
  - the pocket-pivot day (and not without the volume), eligibility from the next session, the 8-week EMA with no
    look-ahead and by hand;
  - a random walk with no costs giving E[R] ≈ 0 for pivot30 and open;
  - scores (EDGE vs NOISE, the cut's paired value, vs open, shares).
- **`apptest_pv.py`:** run, the matrix (12 rows), the cut-or-run table, another cell, the watch list, today's
  triggers, the stale note.

## Open
- **First real run:** Massive → 30-min pivots → 2 years → *Run the study* (about 435 requests the first time, then
  cached). Read three things:
  1. whether any 30m entry beats the next open on the same setup (`vs open`);
  2. whether the day-1 cut adds R (`the cut adds`);
  3. whether the survivors' total covers the day-1 losers in section 2.
- **Next steps:**
  - If a cell earns EDGE, wire it into playbook.py (tonight's watch list with the 30m rule) and into
    `pivot_scanner.py`, which already fires PIVOT and RANGE_BREAK. The War Room's scanner would then gate on the
    setups that paid.
  - Luk's own intraday refinements (the prior hourly bar's low, VWAP retests, 5-minute entries) aren't modelled.
