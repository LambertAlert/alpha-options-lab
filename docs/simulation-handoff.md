# Alpha & Options Lab: Simulation tab (Oct 25 2026; exit signals Nov 3)

The tab is Stocks > Simulation, between Expectancy & Kelly and Trade ranker. It reads the Setup ledger's events and
can build the ledger itself. It renders as an `st.fragment`, so its controls rerun only this page. Everything is in
`alpha_options_lab.py`, in the SIMULATION block just above `main()`. The sampler is numpy only (no PyMC needed).

## Shared controls
- **Indicators** multiselect (`sim_feats`). The defaults are rs_rating, ga_gpct, ga_rr, ext8w, plan_risk_atr,
  atr_pct, n_setups and breadth50; any numeric ledger feature with coverage of at least 50% can be added.
- The scaler winsorizes at 1/99, fills gaps with the median and standardizes.
- **Settings persist across views.** `SIM_PERSIST` keys are re-assigned at the top of each run, because Streamlit
  drops a widget's value while the widget isn't drawn (view 1's settings while on view 3).

## Brief → Simulation hand-off
- **The Brief saves its list.** `render_brief_setups` writes `st.session_state["brief_top"] = sim_brief_pack(Rk, S,
  bar_date)`. The list runs: today's focus (`SU_TODAY_N`), this week's (`SU_WEEK_N`), then the rest of the
  fired/triggered/setting-up names by rank, up to 25. Each name keeps its live scans' `ledger_id`s.
- **The Simulation matches names to signals** (`sim_brief_candidates`). Each name's ledger signals come from the last
  max(N, 5) sessions, with the Brief's own scan first and otherwise the newest. Names with no ledger signal are listed
  separately; the RS-leader scan has no ledger setup.
- **View 1:**
  - `Signals` radio (`sim_src`: brief | all, default brief) and `Brief names` (`sim_nbrief`, default 7).
  - The table *The Brief's names, simulated* (`_sim_board`) shares the `sim_fwd` memo with the single-signal view. It
    shows the verdict, look-alike E[R] and band, P(E[R]>0), the reference sets, exit share, ESS, open at H and, after
    a fit, the model's E[R] and P(edge).
  - The verdict (`sim_verdict`): supports means band > 0 and beats uptrend names; against means band < 0 or
    P(E[R]>0) < 0.2; mixed otherwise; "(thin)" is added under 30 effective look-alikes.
- **View 3:** the live-signal picker follows the same source ("a Brief name's signal").
- **First load:** the Brief renders after the Stocks tab in `main()`, so the tab shows every signal with a note.
  Any click (a fragment rerun) picks the list up.

## 1 · Forward paths (Monte Carlo)
- **Stop level.** Rebuilt as close × (1 − plan_risk_atr × atr_pct/100), and held to 0.5–cap ATR as in the ledger.
- **Look-alikes.**
  - The K nearest past signals of the same setup on the chosen indicators, tricube-weighted; the family is used when
    the setup has fewer than 40.
  - Each look-alike's forward window must end at or before the signal date.
- **Path rebuild.**
  - Each look-alike's H-session path is stored as log moves of O/H/L/C from the prior close (`sim_path_bank`).
  - The moves are rescaled by today's ATR % over the analog's ATR % (clipped to 0.33–3), with the name's last 260 real
    bars put in front.
  - The result is traded with **`lg_label` itself** (`sim_run_paths`). A time limit longer than H, or none, marks
    trades still open at H at the last close.
- **Comparison sets.** All of the setup's past signals and the `base:uptrend` events, up to 2,000 each.
- **Uncertainty.** A Bayesian bootstrap (Dirichlet × kernel weights) gives the 90% bands.
- **Out-of-sample check** (`sim_knn_check`): IC, top-minus-bottom third, and OOS R² vs the setup's plain average.

## 2 · Indicator model (MCMC)
- **Rows.** One per setup and signal date, y = the mean R of that date's trades.
- **Indicators** are standardized and **centred within each setup**.
- **Model.** Student-t errors; setup effects ~ N(family mean, τ²); τ ~ half-Cauchy(0.25R); β ~ N(0, 0.25R).
- **Tempering.** The likelihood is raised to 1/k, with k from Newey-West on ridge residuals (`sim_overlap_factor`).
- **Sampler** (`sim_gibbs`), in blocks:
  - ν collapsed, then the scales.
  - β.
  - τ by Metropolis on its fully collapsed marginal, then the family means, then the setup effects.
  - σ².

  Demo: R-hat 1.005, ESS 684.
- **Expected R.** Each setup's mean residual is added back to the t location, so "expected R" is a mean.
- **Saving.** The posterior goes to `data/sim_posterior.parquet` plus a `.json` sidecar, written atomically.

## 3 · Next trades (posterior predictive)
- **Bayesian Kelly** (`sim_bayes_kelly`), alongside the cautious Kelly (10th-percentile edge) and the plug-in.
- **Equity fan** (`sim_equity`). Each path keeps one edge draw for all its trades; the default stake is half Bayesian
  Kelly.

## Exits: trim and trail (Oct 26 2026)
Neil found the tab stunted by exits on big winners and asked for a trim at the target, raised stops, and longer holds
on winners with shorter ones on losers, in TraderLion's style.
- **Labeler.** `lg_label` gained `trim_frac`, `trim_stop_r`, `trail_from`, `ma_closes`, `fail_n`, `fail_r`,
  `fail_once`, `be_r` and `runner_horizon`. All are off by default. A one-off check against the previous labeler gave
  identical output (all keys) over 180 combinations × 3,000 random trades: entry modes, targets, time limits, trail
  kinds, `mark_open`.
  - At the target, `trim_frac` is sold at the target, or at the open if the price gapped over it.
  - The rest has no target. Its stop moves to entry + `trim_stop_r`·R from the next bar, and its time limit becomes
    `runner_horizon`.
  - With `trail_from="trim"`, the trail or moving-average exit applies only after the trim.
  - `fail_n`/`fail_r`: an untrimmed trade that closes under entry + `fail_r`·R is cut there, as outcome 5, "cut: not
    working" (`LG_OUTCOME`). With `fail_once` the check is at session `fail_n` only; otherwise it's every close from
    `fail_n` on.
  - `be_r`: before the trim, a high of +`be_r`·R moves the stop to breakeven.
  - R and the return blend the two parts. New outputs: `trimmed`, `trim_px` and `trim_i`.
- **Plan.**
  - Constants `SIM_PLANS`, `SIM_TRIM_FRACS`, `SIM_TRIM_STOPS`/`_R`, `SIM_RUNNERS`/`_SPEC`/`_SHORT`, `SIM_FAIL_MODES`
    and `SIM_BIG_R` (3R).
  - Defaults in `SIM_DEFAULTS`: trim 1/3 at 2R, breakeven on the rest, close under the 21-day EMA, one close, a time
    stop at session 5 under the entry (once), no early breakeven. `sim_h` is now 90.
  - `sim_plan_of(ss)` reads the plan, `sim_trade_rules` puts it into `prm["sim_plan"]`, and `sim_plan_txt` describes it.
  - `sim_ma_panel` builds the EMA or SMA panel, and `sim_label_kw` passes the trim keywords to `lg_label`.
- **Wiring.**
  - `_sim_exit_plan` draws the *Exits* radio (`sim_plan`) and the settings popover. It returns `run` with
    `rid + "|x<crc>"` (so each plan gets its own caches) and `prm["sim_plan"]`/`["sim_plan_cmp"]`.
  - Under trim and trail it also returns the ledger re-run by `sim_relabel(ab["P"], ev, prm)`: same entries and
    `stop`, new exits. This is about 1–3 s for 190k demo trades, kept in a one-slot `ss["_sim_relabel"]`. The
    whole-market universe falls back to the ledger's exits.
  - `sim_forward` also runs the other plan on the same look-alike paths (`look_cmp`, `st_cmp`), and drops the
    reference sets' close paths to save memory.
  - `sim_set_stats` adds `p_trim`, `p_cut`, `p_big`, `r_win`, `r_loss`, `r_top5`, `r_max`, `hold_win` and
    `hold_loss`.
  - The board adds *E[R] under the other plan* and *3R+ winners*.
  - The single-signal view adds the *Trimmed at the target* tile, the new table columns, a measure × plan table *The
    same look-alike paths under both exit plans*, and a fourth histogram line (clipped at +12R).
  - The model's overlap lags are now the longer of the edge window and the 75th-percentile hold.
- **Why the time stop is checked once:** checking every close from session 5 cut 27% of trades and lost expectancy
  against a single check at session 5 (18% cut). TraderLion gives no fixed day count.
- **Demo read** (whole ledger, 137k trades, illustrative):

  | Exits | E[R] | 3R+ | Top-5% avg | Winners held | Losers held | Avg loser |
  |---|---|---|---|---|---|---|
  | Ledger's exits | −0.083 | 2.5% | +4.26R | 22.3 sessions | 8.2 sessions | −1.01R |
  | Default trim and trail | −0.055 | 4.4% | +5.05R | 29.4 sessions | 6.8 sessions | −0.90R |
  | 1/3 at 3R | −0.002 | 7.7% | +6.01R | 44.5 sessions | | |
  | Two closes under the EMA | −0.047 | | | | | |
  | No time stop | −0.037 | | | | 9.4 sessions | |

## Tests
- `test_simulation.py`: 65 checks, including the Brief pack order, scan matching, the missing list and the verdicts.
- Headless sweeps:
  - `apptest_sim.py`: all views
  - `apptest_brief_sim.py`: the Brief table, the 25-name list, switching sources, model columns and view 3 Brief
    signals
  - `apptest_sim_persist.py`: settings survive switching views
- The ledger, lab and group-leader suites still pass.
- `test_trim_exits.py`: 48 checks on planted bars.
  - The trim at 110 and the rest at breakeven (+0.67R).
  - The +0.5R lock, a gap trim, and target-and-stop in one bar (the stop wins).
  - The 21-EMA exit with one and two closes, and that it stays off before the trim.
  - The chandelier from the trim, the loser cut, its threshold, and once vs every close, early breakeven, and a
    winner outliving the limit.
  - The plan's rules and sentence.
  - Paths: a 2R-capped plan vs trim and trail (top 5% and best R, winners held longer).
  - `sim_relabel` against a direct `lg_label`.
- `apptest_trim.py` runs the tab headless: defaults, every setting, the ledger's exits, the model fit (R-hat 1.006)
  and next trades, with 0 exceptions.
- README: `SIMULATION_README.md` (with `readme_images/simulation/`) and a self-contained `SIMULATION_README.html`.

## Exit signals (Nov 3 2026)
Neil asked for an exit signal instead of only a target R: a close under the 10-day EMA, a distribution day or a
climax, tested side by side with the target. The side-by-side lives in playbook.py's Exit lab (see the playbook
handoff); the lab carries the engine and the settings.
- **Labeler.** `lg_label(..., exit_sig=None)` takes a dates × names int8 panel of signal codes. Where the trailing
  rule is live (after the trim with `trail_from="trim"`, from entry otherwise), a close on a signal day ends the trade
  at that close: outcome 6, "exit signal" (`LG_OUTCOME`). It has priority over an EMA close on the same bar. The new
  output `sig_code` says which signal fired. With `exit_sig=None` or all zeros, the output is identical to before; the
  ledger and the ema21/ema10/chandelier relabels were checked equal against the previous file on demo data.
- **`sim_sig_panel(C, rules, V=None)`:** code 1 = a distribution day (close down `dist_drop` % on `dist_vol` × the
  average volume of the 50 sessions before; needs volume), 2 = a climax (close `climax_ext` % over the 50-day SMA),
  3 = both. `SIM_SIG_DEFAULT` = 3 / 1.5 / 20; `SIM_SIG_CODES`.
- **Runner `signals`** (`SIM_RUNNERS`/`_SHORT`/`_SPEC`, spec `("ma", 10, "ema")`): the 10-day EMA is the
  moving-average panel; `rules["sig"]` holds the thresholds.
- **No target:** a trim at 0R in the plan (`sim_trim_r` now 0–10) gives `tgt` inf, `trim` 0, `trail_from="entry"`,
  `no_target` True, so the runner's exit takes the whole trade.
- **Wiring:**
  - `sim_relabel` passes the panel (with volume) and stores `exit_sig`.
  - `sim_run_paths` passes it without volume, so simulated paths have climaxes and the EMA only.
  - `sim_plan_txt` describes both plans.
  - The Simulation popover shows `sim_dist_drop`, `sim_dist_vol` and `sim_climax_ext` (in `SIM_DEFAULTS` and
    `SIM_PERSIST`) when the runner is signals.
  - Positions: `pos_status` adds the action `sell_signal` ("SELL: exit signal") for the untrimmed no-target case, and
    uses `sell_rest` after a trim. It says which signal, records `sig_now`, and shows no trim level without a target.
    `_pos_chart` marks signal days with red triangles and drops infinite levels.
- **Tests:**
  - `test_exit_signals.py` (52 checks).
  - `apptest_trim.py` runs trim + signals (signal exits present) and no target (nothing trimmed).
  - `apptest_positions.py` runs no target with signals.
