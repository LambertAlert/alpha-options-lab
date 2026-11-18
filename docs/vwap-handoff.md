# Anchored VWAP across the Stocks section (Nov 11 2026)

Neil asked to make VWAP a bigger part of the Stocks section, on a par with MACD and the 8-week pivot. Before this,
VWAP showed up only as alphas (#42 close vs session VWAP and its cousins), the Brief's above/below-VWAP scans, the
ledger's "vwap" split and an AVWAP distance on Market > CMT. It is now a full system after Brian Shannon's anchored
VWAP (*Maximum Trading Gains with Anchored VWAP*, 2023): its own tab, a Setup ledger family, a Brief scan, Screener
filters, a split for every other family, ranker inputs and a session-VWAP read on the 30-minute triggers.

## The engine (block "ANCHORED VWAP" after `zg_signals`; settings `AW_*` above `LG_FAMILIES`)
- Three lines per name per day, each anchored point-in-time (from data up to that day):
  - **the high**: the last session whose high beat every high of the prior 252 (`AW_HI_LB`);
  - **the low**: the last session whose low undercut every low of the prior 63 (`AW_LO_LB`). Strict, so a flat base
    doesn't move the anchor daily;
  - **the event**: the last open 4%+ over the prior close (`AW_EV_GAP`) on 2.5x+ the 50-day volume (`AW_EV_VOL`) with an
    up close, live for 63 sessions (`AW_EV_LB`).
- Line = sum(bar price x volume) / sum(volume) from the anchor bar to today (`_aw_line`, cumulative sums, one
  `take_along_axis`). Bar price (`aw_typical`) = the bar's own VWAP (Massive, demo) when inside the bar, else (H+L+C)/3.
- `aw_panels` returns the lines, anchor ages, % position against each, the state and the setups with their stops.
  `aw_snapshot` is one row per name. `aw_block(ab)` caches both per data load (last `MC_MAX_ROWS` sessions).
- **State** (`AW_STATES`): ABOVE BOTH / BETWEEN / BELOW BOTH, the close against the lines from the high and the low.

## Setups (ledger family "VWAP"; all long)
| id | rule | stop |
|---|---|---|
| `vw:reclaim` | first close over the high's line (same anchor as yesterday), high 20+ sessions old (`AW_RECLAIM_AGE`), close over the 50-day | `avh`: the high's line − 0.5 ATR |
| `vw:pull_lo` | low within 0.25 ATR of the low's line (`AW_TOUCH`) or through it; close over it, top half of the range (`AW_HOLD_CLV`), no more than 1.5 ATR above (`AW_HOLD_MAX`); low anchor 10+ old; rising 50-day, over the 200-day, within 25% of the 52-week high | `avl`: the low's line − 0.5 ATR |
| `vw:pull_ev` | the same test of the gap day's line, 3+ sessions after it, close over the gap day's low | `ave`: the gap's line − 0.5 ATR |
| `vw:pinch` | high anchor before the low anchor (a decline into a base), lines within 1 ATR (`AW_PINCH`), first close over both | `avp`: the lower line − 0.5 ATR |
| `vw:cross_raw` | any close over the high's line, no filters (reference; skipped by confluence and the ranker) | `avh` |

- Exit seed: trail. Time limit seed: none. Colour #e8c547.
- Alphas by trade types: reclaim and cross_raw = Breakout, pinch = Tight base / launch pad, the pullbacks = Pullback in trend.

## Every family gets the read
- Ledger features: `aw_state`, `aw_hi_pos`, `aw_lo_pos` on every trade (computed in `lg_chunk` for all families).
- Splits (`LG_SPLITS`): `aw_state` ("AVWAP state at the signal") and `aw_hi` (close vs the high's line, in % bands).
- Ranker inputs (`RK_FEATURES`): the same three.
- Brief cautions: any non-VWAP card warns when the name is under its AVWAP from the 52-week high.

## Where it shows
- **Stocks > VWAP** (`render_aw`, new tab `S[2]`; later Stocks tabs moved up one, to `S[3..21]`):
  - KPIs: state counts, setups today and in 5 sessions, share of bars with a real VWAP;
  - breadth of the list over its own lines (`aw_breadth`), last two years;
  - presets: everything, a setup in 5 sessions, each state, pinched, gap anchor live;
  - a scatter of position against the high's line and the low's line;
  - one name's chart with the lines drawn from today's anchors (`aw_chart_frame`) and its setups as triangles;
  - the table with each name's plan (buy stop over the signal day's high, the setup's stop, risk) and a "failed" box
    (closed under the stop since);
  - once the ledger is built (`aw_ledger_read`): the VWAP setups' E[R] and t, and every family split by state;
  - a guide (`AW_GUIDE`).
- **Screener**:
  - an "Anchored VWAP (Shannon)" expander with three filters: state, a setup in 5 sessions, and a minimum % vs the
    high's line;
  - VWAP columns and two sorts;
  - two presets: "Anchored VWAP setup, leader" and "Over the AVWAP from the high, RS leader".
- **Brief > Setups**:
  - a sixth scan, VWAP (`SU_FAMILIES`), drawing on `aw_snapshot`;
  - names whose setup failed are dropped;
  - score: above both, pullback or pinch over a reclaim, risk ≤ 1.5 ADR, composite and peer RS 70+, no 200-day
    overhead, minus one when 15%+ over the high's line.
- **Stocks > 30-min pivots**: today's triggers show the entry vs the session VWAP and "over a rising VWAP / over
  VWAP / under VWAP" (`pv_svwap`).

## Demo check (made-up data, 120 names, VWAP family only)
| setup | trades | E[R] |
|---|---|---|
| pull_lo | 262 | +0.08 |
| reclaim | 595 | −0.11 |
| pinch | 188 | −0.13 |
| cross_raw | 1081 | −0.14 |
| pull_ev | 6 | — |
| uptrend baseline | 4582 | +0.06 |

Demo prices have no real edge; the table only shows the family trades. Real data decides.

## Tests
- `test_aw.py`, 41 checks:
  - the line by hand, and no look-ahead;
  - each anchor by hand;
  - the bar price (own VWAP vs typical);
  - planted cases: reclaim (fires once, at the right bar, with its stop) and young-high control; pullback to the low's
    line (fires, the test's geometry, the anchor, a close under doesn't fire); pullback to the gap's line (fires, by-hand
    line, 1.5x-volume control); pinch (converges, fires once, stop, state change; no pinch without a decline);
  - the snapshot's plan and trigger;
  - a demo ledger (trades, features, both splits, the read);
  - the registry; the Brief rows; breadth; the session VWAP by hand.
- `apptest_aw.py`:
  - the tab (KPIs, table, every preset, the picker);
  - Screener filters and preset;
  - the Brief's scan list;
  - a ledger with VWAP, then the tab's ledger read and both splits.

## Limits
- Daily bars. Shannon times entries on intraday charts; the 30-minute session VWAP is the only intraday piece.
- The anchors are rules standing in for anchors chosen by eye (a particular earnings day, an IPO, a major low).
- Yahoo bars have no VWAP, so lines use the typical price there.
