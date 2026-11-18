# alpha_options_lab.py review and fix list (Nov 9 2026)

Neil asked for a review of the whole lab file, with the six Process plinko fixes kept at the end of one list.
**All 16 were applied on Nov 9** (see "What was done" at the end).

## What was checked
- **Automated, all 40,375 lines:**
  - pyflakes and ruff: no undefined names, no duplicate functions.
  - 481 literal widget keys: no real clashes (the two repeats are either/or branches).
  - Every session-state key read by subscript has a default, a widget or an assignment.
  - Every file write goes through a temp file and `os.replace`.
  - Closures in loops (23 flagged): all are called inside the same iteration.
  - Every forward shift is a label, not a feature; the centered swing-point code is delayed two bars before use.
- **Read line by line, about 4,800 lines (12%):**
  - `lg_label`, `lg_chunk`, `lg_run`, the ledger statistics (`lg_nw`, `lg_bh`, PSR / deflated Sharpe, the two spread estimators, `lg_cell`, `lg_verdict`).
  - The alpha engine and composite, calibration.
  - Kelly sizing and Expectancy & Kelly.
  - Mandelbrot cluster, name stack, strike / hit.
  - Trend systems, dealer positioning, the Trade ranker's training and scoring, Positions, the 30-min data layer, the pricer audit's spread loop, the bar loaders, clock helpers and the cache.
- **Unit suites:** 25 run; 21 pass in full (the other four are items 2, 7 and 8).
- **Not read:** the Brief, Screener, Grader, Vol desk, VRP desk, spreads engine, Market odds, climate, narratives, CMT / CFA layers, the learned models, Simulation and Group leaders. Most of those have passing unit suites; the Brief, Screener, Grader, Vol desk, climate and narratives do not.

## Fixes found in this pass
1. **An API key can be printed on screen.** `http_json` calls `r.raise_for_status()`, whose message carries the full URL, and the key is a query parameter. A 400 or 422 reaches the tabs' `warnbox(f"...{e}")`. Verified with a mocked 400. Fix: catch `HTTPError` and re-raise with the status code only. `massive_chain`'s `next_url` call has the same exposure.
2. **The Pullback setups have no trade type.** `pb:ibs`, `pb:rsi2`, `pb:down3`, `pb:low5` are missing from `AM_TYPES`, so Stocks > Alphas by trade leaves them untyped and `test_alpha_map.py` fails 1 of 24. A miss from the Quantified Strategies work. Fix: map them to "Rebound / oversold".
3. **The Trade ranker's candidates are not checked for being open.** `rk_today` takes status 3 ("not enough future bars") within the last `rk_recent` sessions. A signal three sessions old that stopped out the next day is still status 3. Verified. Fix: drop candidates whose low since entry has reached the stop, or reword "still open" to "fired in the last N sessions".
4. **A failed download hides a name until the session phase changes.** `get_bars` stores `(None, "miss")` under the day-and-phase key. Old phases are never evicted either, so memory grows over a multi-day session. Fix: don't cache misses; drop entries from earlier stamps.
5. **The ranker's calibration table is fitted and shown on the same trades.** The isotonic map is fit on the out-of-sample scores, then binned on them. It shows the fit, not a test. Fix: fit on the first walk-forward blocks, show the last.
6. **Clock helpers ignore holidays and half days**, and the no-timezone fallbacks disagree (4 hours in three places, 5 in one). Low impact: tz data ships with pandas. `nyse_holidays` now exists and could back `last_completed_session`.
7. **Demo option bars are not fixed per contract-day.** `AuDemo.bars` draws its noise in sequence from the requested start date, so one contract asked for over two windows gives two prices. Demo and test only: `test_audit.py` fails 1 of 28 depending on the date. Fix: seed per contract and date.
8. **Two stale tests.** `test_burst.py` and `test_group_asym.py` import `group_asym`, a module that no longer exists.
9. **Positions, two small mismatches with the ledger's rules.**
   - The chandelier plan stop uses the latest ATR; `lg_label` ratchets bar by bar.
   - Closes under the average are counted from the entry; `lg_label` counts from the trim.
   - The first only matters with a chandelier runner, the second only with the two-close rule. Neither is the default.
10. **Housekeeping.** 4 unused imports and 6 unused locals; one `astype(copy=False)` (line 27515) that pandas 4 removes; no pinned requirements, and the file was verified on pandas 3.0.5.

**Worth knowing, not a bug:** alpha #1 and #57 use `ts_argmax` as days since the maximum. The usual open-source reading is the position in the window, which makes #1 the exact mirror (rank correlation −1.0). The lab's own labels ("coiled: the 5-day high a few days old") match its convention.

## Process plinko fixes (from the earlier review)
11. **The path t overstates significance.** On a no-edge martingale, |t| ≥ 2 on 16% of paths (5% expected). Count arrivals on a path, require 60+ dates, add a BH q, stop marking the Best path tile "good" at t 2.
12. **Two E[R] conventions on one screen** (by trade in the nodes and the marked-names table, by date in the best paths).
13. **"Best paths: min trades" does nothing after a build.** Compute `pk_paths` at render time.
14. **Location priority hides extension in low-volatility names.** Extended should win over the pocket, as it does in the per-name view.
15. **Names with under 252 sessions get "RS under 80".**
16. **"60 sessions at most" is not true after a trim**, and still-open runners are dropped. Pass `runner_horizon=hold` or `mark_open=True` (the ledger's default).

Design points for the plinko are in `claude/process-plinko-handoff.md`.

## What was done (Nov 9, all 16 applied)
- **1:** `http_json` raises `RuntimeError("HTTP <code>")` for any 4xx it doesn't already handle; the URL never reaches the message.
- **2:** the four `pb:*` setups map to "Rebound / oversold" in `AM_TYPES`.
- **3:** `rk_alive(C, P)` drops candidates whose planned stop has traded since the signal; `rk_today(..., P=ab["P"])` and the consensus-only list both use it.
- **4:** `get_bars` keeps failed downloads in a separate `miss` map and retries them after `BAR_RETRY_S` (600 s); bars and misses from an earlier day or phase are dropped on entry.
- **5:** the calibration table is fitted on the earlier walk-forward blocks and read on the last (`R["calib_oos"]`); with one block it shows the fit and says so. Today's scores still use the map fitted on every block.
- **6:**
  - `is_market_holiday` (backed by `nyse_holidays`) is used by `session_phase` and `last_completed_session`. Half days still count as full sessions.
  - `et_offset_hours` replaces the fixed 4- and 5-hour fallbacks.
- **7:** `AuDemo.bars` seeds its noise per contract and date.
- **8:** `group_asym.py` is a small shim that maps the prototype's names onto the lab's `ga_` functions, so `test_burst.py` (18) and `test_group_asym.py` (33) run again.
- **9:** in `pos_status`, the chandelier plan stop ratchets bar by bar from the trim bar, and closes under the average count from the bar after the trim.
- **10:**
  - Unused import and locals removed; the three imports left are availability probes.
  - `astype(copy=False)` dropped.
  - `requirements-lab.txt` lists the versions tested, plus `tzdata` for Windows.
- **11:**
  - `pk_flows` marks arrivals (`arr`: the day a name's route changes).
  - `pk_paths` scores arrivals only, needs `PK_MIN_DATES` (60) dates, and adds a one-sided p and a BH `q`.
  - The Best path tile is "good" only at q ≤ `PK_Q` (0.10) with E[R] > 0.
- **12:** `pk_name_rows` reads the route's record from `pk_paths` with no minimums, so both tables show the same figure.
- **13:** paths are scored at render time and cached per minimum in `rec["paths_by_n"]`.
- **14:** location is extended, then pocket, then near.
- **15:** a new leadership code, `new` ("Under a year: no RS yet").
- **16:** `pk_outcomes` passes `runner_horizon=hold`, so every counted trade ends by session 60 and none is dropped for still running.

**Checks**
- `test_review_fixes.py`: 20 checks for fixes 1-9.
- `test_pk.py`: 57 checks.
- On the no-edge martingale, after fix 11:
  - The sd of the path t fell from 1.66 to 1.19; |t| ≥ 2 fell from 16% to 9%.
  - With the simulator's own small stop-fill bias removed, t ≥ 2 on 2.6% of paths (2.5% expected) and no build of 8 flagged a "good" path.
  - With that bias left in (a uniform +0.03R), 3 of 8 builds flagged one.
  - So a small edge shared by every path, such as market drift, can still clear the bar. Scoring paths against the same-date baseline is the remaining fix (a plinko design point).
