# Quantified Strategies additions to the Setup ledger and RS 8-week (Nov 8 2026)

Neil asked what on quantifiedstrategies.com could add to the dashboard, then said yes to the three ideas ranked
first: oversold-in-an-uptrend setups, a close entry mode and calendar splits. Most of the site's exact rules are
members-only and tested on indices and ETFs, so these go in as hypotheses that the ledger's tests judge on his list.
Context: he had just asked how not to buy extended, so RS 8-week also got extension in ATRs and a short-term
stretch flag.

## Setup ledger
- **Pullback family** (`LG_FAMILIES` += "Pullback"; `LG_SETUPS` `pb:*`, stop `n2` = close − 2N):
  - Uptrend: close > 200-day, > 50-day, and the 50-day > its level 10 sessions ago.
  - `pb:ibs`: IBS < 0.2 (`LG_IBS_LO`).
  - `pb:rsi2`: RSI(2) < 10 (`LG_RSI2_LO`, Connors).
  - `pb:down3`: three lower closes.
  - `pb:low5`: close at the 5-day low.
  - `lg_oversold(o, h, l, c)` gives IBS = (c − l)/(h − l) (NaN on a zero range) and RSI(2) with Wilder's smoothing
    (alpha 1/2).
  - Defaults: `LG_EXIT_SEED["Pullback"]` = target; `LG_TL_SEED` = 5 (used when time limits are per family).
  - `EXP_FAMILY_COLOR` gets green. `n2` is built in the family block if Trend isn't selected.
- **Entry "Signal-day close"** (`lg_mode` = `close`):
  - In `lg_label`, mode `close` buys at C[signal] with e = signal + 1. A `post` flag makes the first bar use gap
    logic: an open through the stop or over the target fills at the open.
  - next_open and buy_stop are identical to the previous file (200 random events, every output).
  - The UI help says the close entry assumes acting in the last minutes on near-final values.
  - Texts updated: the ledger's mode text, `_sim_rules_txt`, and playbook.py's Tonight entry rule.
- **Close vs next open on the same signals** (`lg_entry_timing`, `_lg_entry_timing`):
  - A section before "Inside one setup" (list universe), button `lg_time_go`.
  - Each signal is re-run both ways with the ledger's own exits per family: `sim_relabel(P, ev, prm, sid=…)` per
    family, since `sim_relabel` gained a `sid`.
  - The stop is the setup's level as of the signal: close × (1 − clip(plan_risk_atr, 0.5, cap) × atr_pct/100).
  - Per setup: E[R] each way with NW t, the paired difference (close − open) by date with t, the overnight gap in R
    ((next open − signal close) / risk), win rates. "Better entry" at |t| ≥ 2.
  - KPIs: overall difference, counts better each way, average overnight gap.
- **Calendar splits** (`LG_SPLITS`):
  - `tom`: entry in the last 4 or first 3 sessions, the turn-of-the-month window (QS: long from the 5th-last close to
    the 3rd day).
  - `opex`: the week of the third Friday.
  - `weekday`.
  - Helpers: `lg_calendar(dates)` (the entry session = the next NYSE trading day; position from the month's start and
    end; weekday; opex week) and `nyse_holidays(start, end)` (rule-based: New Year's Sunday→Monday, MLK, Presidents,
    Good Friday, Memorial, Juneteenth from 2022, July 4, Labor, Thanksgiving, Christmas).

## RS 8-week
- **New columns:**
  - `ext21_atr` / `ext50_atr`: (close − 21-day EMA, or 50-day SMA) / ATR14.
  - `rsi2`, `ibs`.
  - `st_oversold`: RSI(2) < 10 or IBS < 0.2.
  - `st_stretched`: RSI(2) > 95 and IBS > 0.8.
- **Presets:** `dip`, `stretch`, `atr3` (> 3 ATR over the 21-day).
- **Note:** a buyable zone is within about 1 ATR of a rising 10/21-day; 2-3 ATR is stretched; beyond that, and 20%+
  over the 50-day (TraderLion's first sell signal), don't initiate.

## Demo read (synthetic)
- Pullback setups: E[R] +0.14 to +0.23, NOISE against the uptrend baseline.
- Close vs open: no clear difference except the 20-day breakout (the next open better at t −2.4). Demo bars barely gap
  overnight, so real data is the test.

## Tests
- **`test_qs.py` (23 checks):**
  - IBS and RSI(2) by hand; zero range;
  - the four setups on a planted dip (and none under the 200-day); the family defaults;
  - the close entry: entry, risk, a gap through the stop fills at the open, a gap over the target at the open, the
    next open buys after the gap;
  - next_open and buy_stop unchanged against the previous file (`LAB_OLD`);
  - the calendar: Good Friday 2025, July 3 2026 observed, October's 4th-last session, November opex, the turn-of-month
    labels, the splits listed;
  - close beats open on a planted 1% overnight drift, with a positive gap in R;
  - RS 8-week ATR extension by hand, the flags, the presets.
- **`apptest_qs.py`:** Pullback + Trend + Gap at the close, the three splits, the timing table, the RS 8-week presets.
- **Regression:** test_ledger_stats 56, test_trim_exits 48, test_simulation 65, test_playbook 40, test_exit_signals 52.

## Open
- **On real data:**
  1. Rebuild the Setup ledger (the Pullback family is selected by default).
  2. Run the close-vs-open comparison.
  3. Split by turn of the month.
- **Still to build:** the industry 52-week-high ranking (Group leaders) and the market-level dip-window flags for the
  War Room (SPY 3 down days, 5-day low, IBS < 0.2 against the regime model's BUY_DIP), both from the same review.
