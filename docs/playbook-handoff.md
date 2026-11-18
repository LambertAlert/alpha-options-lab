# playbook.py: the expectancy playbook (Nov 3 2026; exit lab added Nov 3)

Neil wants to find positive expectancy and track it, in the spirit of Andrew Mack (co-author with Euan Sinclair of
*Retail Options Trading*; an algorithmic trader and sports bettor): edge first, size to survive, keep score
against what the edge should pay. He asked for it as its own file, `playbook.py`. Choices he made: options tracked
from the start; your trim and trail for the same-signal comparison; setups proposed automatically with a manual
override; a nightly command-line mode.

## Running it
- `python playbook.py` opens the app with the War Room theme (or `streamlit run playbook.py`).
- `python playbook.py nightly [--source massive|yahoo|demo] [--limit N]` rebuilds the Setup ledger and both spread
  ledgers on your list, then writes tonight's signals and the report. Exit 0 ok, 2 no key or no bars.
- It imports `alpha_options_lab` for every engine; the lab stays the research bench.
- Folder: `data/`, or `$PLAYBOOK_DATA` (the tests use temporary folders).

## Files
- **Written by playbook.py:**
  - `playbook.json`: setups (key `ledger|setup_id|book`), frozen expectations, the exit plan, account, the bar.
  - `playbook_journal.csv`: trades (`JOURNAL_COLS`).
  - `playbook_tonight.csv` and `playbook_report.md` (nightly).
  - `playbook_ledger_plan.parquet` + `.json`: the Setup ledger re-run under the plan, cached under a stamp.
- **Read:**
  - `setup_ledger.parquet` and `setup_ledger_verdicts.json` (the lab's Setup ledger). The lab now also writes
    `source` and `prm_full` into the verdicts.
  - `bull_ledger.parquet` / `bear_ledger.parquet`, `_candidates.parquet` and `_ledger_meta.json`, written by the
    lab's new `br_save` on every Bull or Bear spreads build.
  - `book_positions.csv`.
- All writes are atomic.

## Engine (all pure functions, prefix `pb_` / `jr_`)
- **Admission (`pb_options`):**
  - Setup ledger: shares, scored on `pb_relabel` (the lab's `sim_relabel` under the playbook's plan) by
    `lg_score`. PROPOSED = PROVEN and deflated Sharpe ≥ `bar.dsr` (0.95).
  - Spread ledgers, shares: PROVEN.
  - Debit or credit: the signal is PROVEN or PROMISING, and `db_follow` / `cr_follow` (return on risk) > 0 at a
    Newey-West t ≥ `bar.t_spread` (2.5).
  - ON DECK = close (PROMISING, or a spread at t ≥ 2).
  - `RK_SKIP` and baselines are left out of proposals; they can still be added by hand.
- **Frozen expectation (`pb_expect` via `pb_admit`):** n, dates, per-trade mean and sd, win, avg win/loss, payoff,
  the date-averaged E with NW t, full Kelly (`pb_kelly`: the grid argmax of mean log(1 + f·R)), first/last, the
  ledger date and the plan tag.
  - `pb_retire` keeps the record.
  - A Setup-ledger setup frozen under another plan is flagged.
- **Sizing (`pb_risk_pct`):** Kelly fraction (half) × full Kelly, capped at `max_risk_pct` (1%).
- **Tonight (`pb_tonight`):**
  - Setup ledger signals on its last date. Stop = signal close × (1 − clip(plan_risk_atr, 0.5, cap) × atr% /
    100), as the labeler clamps.
  - Entry: the next open, or a buy stop over the signal high in buy_stop mode.
  - Spreads: the saved candidates (legs, estimated debit or credit; max loss from `cr_payoff`).
  - Size = dollars at risk / risk per share or per spread × 100.
- **Journal R (`jr_r`):**
  - Shares: blended trim and rest, over the initial stop's risk; shorts mirrored; open trades marked at the last
    close (`r_open`).
  - Debit: (exit − debit) / max loss (the debit unless given).
  - Credit: (credit − cost to close) / max loss (required).
- **Same signal (`pb_match`):** same ledger, setup, ticker and signal date (else the latest signal in 5 days up to
  the entry).
  - `ledger_r` is the book's measure.
  - `entry_cost_r`: shares = side × (fill − ledger entry) / ledger risk; debit = (paid − `db_debit`) /
    `db_debit`; credit = (`cr_credit` − received) / `cr_risk`.
  - `gap_r` = yours − the ledger's; `exit_r` = gap + entry cost.
- **Decomposition (`pb_decompose`, per setup since admission, your list):**
  - selection = the ledger on your picks − the ledger on every completed signal;
  - implementation = you − the ledger, on the same closed matched trades.
- **Live record (`pb_live`, `pb_band_path`):**
  - Running total vs n·E with a ±1.645·sd·√n band, and z.
  - Wald SPRT, H1 mean 0 vs H0 the frozen E, normal approximation:
    LLR = (n·E² − 2E·Σx) / (2sd²), bounds ±ln 9.
  - Statuses:
    - NEW: under 5 trades.
    - RETIRE: LLR ≥ ln 9.
    - REVIEW: z < −1.645.
    - WATCH: z < −1.
    - KEEP: otherwise ("confirmed" at LLR ≤ −ln 9).
  - Trades needed for t 2 alone: ⌈(2sd/E)²⌉.
- **Skipped (`pb_skipped`), tracker (`pb_tracker`), review (`pb_review`):**
  - The review groups by week or month.
  - Disciplined = no deviation tag and |entry cost| ≤ 0.1R.
  - Chased = tagged, or an entry cost > 0.25R.
  - It also shows the gap by deviation tag.

## App pages
- **Masthead:** the ledger date, its source and the plan.
- **Warnings:** no ledgers saved, a ledger built on demo data, setups frozen under another plan.
- **Playbook:**
  - KPIs.
  - An active editor (`pb_act_ed`, retire with `pb_retire`).
  - A proposals editor (`pb_pro_ed`, admit with `pb_admit`), plus on deck and retired.
  - Manual add (`pb_manual`, `pb_manual_go`).
  - Settings (`pb_eq`, `pb_mx`, `pb_kf`, the plan: `pb_trim_r`, `pb_frac`, `pb_stop`, `pb_runner`, `pb_fail_n`,
    `pb_fail_r`, `pb_closes`; save with `pb_set_save`).
  - The guide (`PB_GUIDE`).
- **Tonight:** KPIs, an editor with "log as planned" (`pb_tn_ed`, `pb_tn_log`: deduped planned rows), and the
  setups with no signal.
- **Journal:**
  - A dynamic editor (`pb_jr_ed`). Setups show by name and map back to keys on save, which also fills the ledger,
    setup, book and side.
  - Save (`pb_jr_save`), import from the Book (`pb_jr_book`), download.
- **Edge tracker:**
  - KPIs: closed trades, total, implementation, selection.
  - A per-setup table.
  - One setup (`pb_tr_key`): the band chart and skipped signals.
  - A trade-by-trade table.
- **Review:** `pb_rv_f` (week or month) and the deviation-cost table.

## Exit lab (Nov 3 2026)
Neil asked for an exit signal instead of only a target R: a close under the 10-day EMA, a distribution day, a climax,
tested side by side with the target.
- **The signals** (the lab's new `signals` runner; thresholds in the plan, Settings):
  - a close under the 10-day EMA (`closes` in a row);
  - a distribution day: down `dist_drop` % (3) on `dist_vol` x (1.5) the average volume of the 50 sessions before;
  - a climax: a close `climax_ext` % (20) over the 50-day SMA.

  Each sells at that close.
- **The plans (`pb_exit_plans`):**
  - *your plan* as set;
  - *trim + signals*: your trim at your target (2R if yours has none), the signals take the rest;
  - *signals only*: `trim_r` 0 = no target, the signals take the whole trade.

  The stop after the trim, the time stop and the thresholds are yours in all three.
- **Runs (`pb_exit_runs`):** `pb_relabel` per plan. Each plan has its own cache file (`playbook_ledger_plan_<slot>.parquet`);
  yours shares the main one. `pb_relabel_cached` checks the stamp. The nightly runs it (`--no-exit-lab` skips it), so
  the page opens without a re-run.
- **Table (`pb_exit_table`):**
  - Trades that every plan completed: open ones, baselines and `RK_SKIP` are out.
  - Scopes: every setup pooled, your active Setup-ledger share setups (`pb_active_setup_ids`) pooled, each setup.
  - Measures: n, E[R], date-averaged E with NW t, win, avg win and loss, 3R+, best 5%, best, hold for winners and
    losers, and the exit mix: trimmed, first stop, raised stop or EMA close (3), distribution day, climax (6 with
    `exit_sig`), cut.
  - `d_er`/`d_t`: per-trade R less yours on the same trades, NW t on date averages; `d_q` BH across setups.
  - Verdict: BETTER/WORSE at |t| ≥ 2 (`PB_EXIT_T`), plus q ≤ 0.10 per setup (`PB_EXIT_Q`), TOO FEW under 30
    (`PB_EXIT_MIN`), else NO CLEAR DIFFERENCE.
  - `pb_exit_wide`: per setup, the three E[R]s, the differences, t, verdicts and the best supported plan.
- **Page (Exit lab tab, between Edge tracker and Review):**
  - A plan sentence; a run button `pb_xl_go` (only when not cached); results in `ss["_pb_xl"]` by stamp.
  - Scope picker `pb_xl_scope`, KPIs, the measure × plan table, running R by signal date per plan, the by-setup table.
  - `pb_xl_use_trim_sig` / `pb_xl_use_sig_only` adopt a plan (flags setups frozen under the old one).
  - `PB_EXIT_GUIDE`.
- **Report:** an "Exit lab" section (pooled lines, and setups where a plan is BETTER).
- **Settings:** trim at 0 = no target; thresholds `pb_dist_drop`, `pb_dist_vol`, `pb_climax_ext`. `pb_plan_tag` and
  `pb_sig_txt` describe them. The default plan's tag is unchanged, so nothing frozen is flagged.
- **Demo read** (40 names, 12,399 common trades, illustrative): your plan −0.016R, trim + signals −0.044R (t −1.6),
  signals only −0.071R (t −1.5); signals only holds winners 8 sessions against your 22.

## Lab changes
- **`br_save(side, res, prm, source, hold, folder)`:** called after each Bull or Bear spreads build in
  `render_spreads_side`. Saves events, candidates (`br_candidates`) and metadata. `BR_FILES`.
- **`lg_build_store`:** the verdict map now carries `source` and `prm_full`.

## Tests
- **`test_playbook.py` (40 checks):**
  - R for a trim, a short, debit, credit, open marked, and a credit without its max loss.
  - Kelly 0.25 on a 2:1 coin; no edge = 0; sizing and its cap.
  - On a real demo ledger (40 names):
    - parameters round-trip;
    - the lab's spread save is read back;
    - the relabel equals the Simulation's, and its cache hits and misses correctly;
    - admission rules;
    - frozen expectations for shares and spreads.
  - Tonight: the stop by hand, size, buy-stop trigger, the debit spread and contracts, logging.
  - Matching: entry cost 0.25R, the gap and the rest; selection and implementation by hand; skipped.
  - Live record: KEEP + confirmed vs RETIRE on planted streams, NEW, the band and z, 20 stops, trades needed, the
    band path.
  - Review: discipline, chased, the deviation table.
  - Journal and playbook round-trips; the Book import.
  - The nightly on demo (30 names) writes every file, with the source.
- **`apptest_playbook.py`:** the nightly into a temporary folder, a planted journal, then every page:
  - warnings; manual admit; settings saved;
  - the tracker (6 trades decomposed, two chased entries, off-playbook);
  - skipped; review by month;
  - the Book import; saving keeps every key.
- **`test_exit_signals.py` (52 checks):** the signal panel by hand; signals only out on a distribution day, an EMA
  close (one and two), a climax; trim + signals ignores a pre-trim signal and blends R by hand; an all-zero panel
  changes nothing; Positions; the plan text (the default tag unchanged); the exit lab on planted runs (BETTER, WORSE,
  TOO FEW, the same-trade set) and on a demo ledger (cached after the nightly, same entries and stops).
- **`apptest_playbook.py`** also runs the Exit lab, picks a setup and adopts signals only.
- **`apptest_pb_saves.py`:** the lab's Setup ledger, Bear and Bull builds save what the playbook reads.

## Open
- **First real use:**
  1. Build the Setup ledger and both spread ledgers on Massive (or run `python playbook.py nightly`).
  2. Read the proposals.
  3. Admit the few that pass.
  4. Log trades from Tonight.
- **Task Scheduler:** `python playbook.py nightly` on weekdays after 4:15 ET.
- **Spread trades:** compared with the spread ledgers' own follow-exits, not trim and trail.
- **Bear-side share trades:** use the bear ledger's exits.
- **Saved ledgers from a demo build:** the lab overwrites real saved ledgers when you build on demo; the playbook
  warns.
