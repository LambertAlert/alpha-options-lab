# Alpha & Options Lab: Deflated Sharpe, spread estimates, MAE/MFE (Oct 24 2026)

All three live inside `alpha_options_lab.py` (single file). The new helpers sit in one block just above `def lg_cell`.

## Deflated Sharpe (Setup ledger + Expectancy & Kelly)
- `sharpe_stats(x, se_nw)`: per-signal-date Sharpe, skew, kurtosis; `n_eff = s^2 / se_NW^2` (overlap-aware).
- `psr`, `expected_max_sr`, `deflate_table(sb, extra_trials, test_mask)` (Bailey & Lopez de Prado 2014).
- Trials N = tested scoreboard rows (not the baseline) + the **Other variants tried** input (`lg_dsr_extra`).
- Scoreboard columns `P(Sharpe > 0)` and `Deflated Sharpe`; KPI "Survive deflation" (DSR >= 0.95); a note shows N and SR*.
- Expectancy table merges psr/dsr; the best-expectancy tile shows the DSR.
- Caveat: SR* also grows with the spread of Sharpes across the board.

## Spread from daily bars
- `spread_abdi_ranaldo`, `spread_corwin_schultz` (only day 2 of each pair gets the overnight shift), `spread_panel(P, "ar"|"cs"|"avg")`.
- Uses the trailing 21 sessions, no look-ahead, capped at 5%. Noise floor is about 30 bp on a name moving 2% a day.
- Ledger **Cost model**: flat bp, or flat + half the estimated spread per side (`lg_cost_mode`, `lg_spread_m`).
  Events carry `spread_bp` and `cost_bp`. New split `spread` (<10, 10-30, 30-80, >=80 bp).
- Screener column `est. spread bp` (Abdi-Ranaldo).
- This is for share trades. It does not replace the option ATM-spread column.

## Excursions (drill-down inside one setup)
- `exc_summary`, `exc_stop_curve` (er + er_risk = er/k), `exc_target_curve`, `exc_scale_out`, `edge_ratio_curve` (Faith; aligned by date; list universe only).
- KPIs, Sweeney MAE scatter, MFE histogram, three replay tables, best-row note, edge-ratio charts.
- Replays are exact for tighter stops and earlier exits only. Wider stops and later targets need a rebuild.

## Tests
- `test_ledger_stats.py`: 56 planted-case checks.
  - PSR closed form
  - E[max] vs Monte Carlo
  - null calibration: best-of-50 passes PSR >50% of the time and DSR <10%
  - spread recovery on simulated bid/ask bounce; no look-ahead
  - exact counterfactuals
  - edge ratio
  - per-event cost
- Headless sweeps pass (`apptest_ledger.py`, `apptest_lab.py`, the group-asym and burst suites).
