# Alpha & Options Lab: Stockbee's EP 9 million (Oct 25 2026)

Neil asked to highlight Pradeep Bonde's (Stockbee's) **EP 9 million** in the Lab. It now runs in four places, all from
one definition in `alpha_options_lab.py`, just above `build_screen`.

## The definition
- `EP9M_VOL, EP9M_RVOL, EP9M_MIN_PX, EP9M_DCR, EP9M_LOOK = 9e6, 3.0, 3.0, 0.70, 5`.
- `ep9m_panels(P)` returns dates x names panels:
  - `sig`: volume ≥ 9M, relative volume ≥ 3 against the prior 50-day average (`shift(1)`, so the EP day is excluded), a close
    above the prior close, and a close of $3 or more.
  - `strong`: the subset with a close in the top 30% of the day's range (`dcr` ≥ 0.70).
  - `rvol` and `dcr` themselves.
- `ep9m_last(P, look)`: each name's latest EP 9M within `look` sessions. Columns:
  - `ep9_age` (sessions ago; 0 = the last bar)
  - `ep9_vol_m`, `ep9_rvol`, `ep9_dcr`
  - the EP day's `ep9_hi`, `ep9_lo`, `ep9_mid`
  - `ep9_hi_since`: the highest high from the EP day through the session before the last, so a break over it on the
    last bar reads as triggered.
- **Why 3x relative volume:** Stockbee's own scan is simply volume over 9M and price over $3. The 3x test keeps out names
  that trade 9M every day; the write-ups use some form of unusual volume. The strong-close split follows the common
  write-ups (DCR of 70% or more).
- **Sources (they differ on details):**
  - Stockbee / Pradeep Bonde's posts on X
  - tradeinski's Substack, "EP 9 Million (EPV) - Basics"
  - thestratlab.substack.com backtest
  - breakoutshappen.com

## Where it shows
| Place | Code | What |
| --- | --- | --- |
| Setup ledger | `LG_FAMILIES` + "EP"; `LG_SETUPS["ep:9m"]`, `["ep:9m_dcr"]` (stop kind `day` = the EP day's low); `LG_TL_SEED["EP"] = 5`; `LG_EXIT_SEED["EP"] = "trail"`; `ep:9m_dcr` in `LG_CONFLUENCE_SKIP`; `lg_chunk` block; `EXP_FAMILY_COLOR["EP"]` | On by default (`LG_DEFAULTS["lg_fams"]` is every family). The stop is still held to the ledger's 0.5 to cap ATR band. The 5-session limit is Stockbee's "most of the move in 3 to 5 days". LG_GUIDE has a section on it |
| Brief > Setups | `SU_FAMILIES` + "EP 9M" (color `#e05c5c`); `su_frame` joins `ep9m_last(P, 5)` (it drops the Screener's 20-session `ep9_age` first: a join clash had hidden the scan); EP 9M block at the end of `su_candidates`; `_cards` adds the plan and caution lines | *Fired today*: trigger = the EP day's high. *Setting up*: within 5 sessions and above the EP day's low, trigger = `ep9_hi_since`. Names back under that low drop off. Score: 2 + strong close + rvol ≥ 5 + 20M+ shares + IBD ≥ 80 + composite ≥ 70, minus 1 if the last price is below the EP day's midpoint. `ledger_id` is `ep:9m_dcr` or `ep:9m`, so the names flow into the Simulation's Brief board. Card plan: take some off in 3-5 days, trail the rest. Caution when no catalyst was found |
| Today's brief | `in_play_table` adds `D["ep9m"]` (volume ≥ 9M, close above the prior close, $3+, paced rvol ≥ 3 when known); `focus_card_html` badge "EP 9M"; movers table checkbox column (hidden when no name has one) | Live from the snapshot intraday, last session otherwise |
| Screener | `build_screen` adds `ep9_age` from `ep9m_last(P, 20)`; column "EP 9M (sessions ago)" | Sort or filter on it like any column |

## Caveats
- **Price gates leave out cheap EP names.** The Brief's gate (price $5+, $5M a day, ADR 3.5%+) still applies, and so do
  the ledger's defaults (`lg_px` $10, `lg_dv` $10M). Many EP 9M days are in $3-10 names, so lower the ledger's minimums
  to test those. Costs bite harder on cheap names.
- **Demo results are illustrative.** On demo data (435 names, the $10 floor), the ledger shows:
  - *EP 9 million*: 437 trades, E[R] -0.02R, NOISE.
  - *Strong close*: 250 trades, E[R] +0.08R, NOISE.

  The demo has no live EP 9M this week, so the sweep plants some (`apptest_ep9m_planted_app.py`).

## Grok page
- `make_grok_page.py` explains EP 9M in "How to read the numbers" and adds an *EP 9 million (Stockbee) tonight*
  section: counts, the Brief's EP 9M names, and the ledger's EP rows.
- Task C adds a fourth post, on tonight's EP 9M names, crediting Stockbee.
- The export adds `ep9m_counts`, `ep9m` and `ep9m_ledger`.

## Tests
- `test_ep9m.py` (44 checks):
  - The signal on planted names: textbook, always-15M, down day, under $3, 8M at 4x, weak close.
  - No look-ahead.
  - `ep9m_last` ages, levels and the pivot excluding today.
  - The Brief scan: triggered, fired today, failed pivot dropped, strong-close point and `ledger_id`, the fade point.
  - The ledger through `lg_run`: the right trades, the EP day's low as the stop, trail and 5-session limit.
  - The movers flag and focus-card badge.
  - The Simulation hand-off (`sim_brief_pack`) keeps the EP ledger setup.
- `apptest_ep9m.py` runs the whole app on demo data:
  - Screener column, Brief scans, movers, ledger rows at $10 and $3, and the guide.
  - Then the planted harness: 4 EP rows on the Brief and the card's plan line. The no-catalyst caution can't show on
    demo data, which gives every name a headline.
- The older suites still pass: simulation 65, entropy 23, ledger stats 56, and the lab, ledger, Brief/Simulation,
  Simulation, entropy and ranker sweeps, all with 0 exceptions.
