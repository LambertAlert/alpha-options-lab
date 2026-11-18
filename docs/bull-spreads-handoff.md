# Alpha & Options Lab: Bull spreads (Oct 29 2026)

Neil asked for the same setup as Bear spreads, but for bull spreads. **Options > Bull spreads** is a new sub-tab, third
after Vol desk and the VRP desk, with Bear spreads fourth. The tabs after them moved from `O[3..8]` to `O[4..9]`.

> **Update (Oct 29, evening):** the bull side runs on the **40-day** (`BL_MA = 40`) wherever it used the 50-day: the
> uptrend state and baseline, Stage 2's short line (40-day over the 150-day), the pullback setup (now
> `bl:pullback_ma`, "Pullback to a rising 40-day holds") and the leaders table's "vs 40-day" column (`vs_bl_ma`).
> `br_states` adds `s_bl`/`rise_bl` (slope still over 10 sessions). Volume is still compared with its 50-day average,
> and the bear side keeps the 50-day. The per-event extension column `ext50` is now `ext_ma`: over the 40-day for
> bull, the 50-day for bear. Change `BL_MA` to try another length; the guide text says 40.

## One engine for both sides
The BEAR SPREADS block became "BULL AND BEAR SPREADS" (between the VRP desk and `render_dealer`). Every `br_`
function takes a side:

| Piece | How it handles the side |
|---|---|
| `BR_SIDE` | Per side: setups dict, baseline id, direction, the debit and credit spread names, the option type of each spread, the session key prefix (`bsp_` bear, `bls_` bull), and wording |
| `br_states` | Returns both sides' states: `leader`/`topped`/`down` and `lead` (RS 80+ now)/`stage2`/`up` |
| `br_signals(..., side, ind_rs)` | Builds that side's setups |
| `br_chunk` | Long labels with `lg_label` directly, short labels with `br_label` (mirrored); bull stops `lo3`/`day_lo`/`n2l`/`lo10` |
| `br_strikes(S0, stop, target, side, credit_short)` | The strike rules for both sides |
| `br_price_spreads(..., credit_short, side)` | Prices both sides |
| `br_run(..., extra)` | `extra` carries panels such as industry RS |
| `br_score(..., side)` | Infers the side from the events if not given |
| `br_verdict` | Wording per side |
| `br_candidates` | Reads the side from `prm` |
| `br_live_structures(..., cc_short, side)` | Builds both sides' structures from the chain |
| `render_spreads_side(side)` | Behind `render_bear` and `render_bull`; `_br_live_view` |

**Renamed fields:**
- Debit spread `pd_*` → `db_*`.
- Credit spread `cc_*` → `cr_*`.
- Live structure keys `put_debit`/`call_credit` → `debit`/`credit`.
- Candidate strike strings → `debit_legs`/`credit_legs`.
- `cc_short` → `credit_short` in `br_price_spreads`.
- The bear tests and sweep were updated to match.

## Bull: who and when (`BL_SETUPS`)
- **Who:**
  - RS leader: an IBD-style rating of 80+ today (`BL_LEAD_RS`).
  - Stage 2: over a 150-day that's higher than 20 sessions ago, with the 40-day over the 150-day.
  - Leading group: the group's members' average RS ranked 80+ across groups (`BL_GROUP_RS`), via
    `industry_rs_panels` and `resolve_groups`. Your list only.
  - Uptrend: over a 40-day that's higher than 10 sessions ago. This is also the baseline.

| id | Fires when | Stop |
|---|---|---|
| `bl:pullback_ma` | Stage 2 leader was over its 40-day 5 sessions ago, its low came within 2% of it in the last 3 sessions, and it closes back over, green, in the top half | `lo3` |
| `bl:breakout55` | Stage 2 leader at a new 55-day closing high on 1.4x the 50-day volume | `day_lo` |
| `bl:group_dip` | Stage 2 leader, mean-reversion percentile ≥ 85, group RS ≥ 80 (the group-strength + RS read). Fires only with groups | `lo3` |
| `bl:lead_mrv` | Stage 2 leader, mean-reversion percentile ≥ 85 | `lo3` |
| `bl:mrv_dip` | Uptrend, mean-reversion percentile ≥ 85 | `lo3` |
| `bl:ep_up` | Gap up ≥ 4% on 3x volume, closing in the top half | `day_lo` |
| `bl:dc20_up` | New 20-day high over a rising 150-day | `n2l` (close − 2N) |
| `base:uptrend` | Every 5th session for any uptrend name | `lo10` |

The threshold is `bsp_mrv`/`bls_mrv`: bear fades the bottom N%, bull buys the top N% (default 15).

## Bull spreads (`br_strikes` with side='bull')
- **Bull call debit:** long the call nearest the entry, short the call at or over the target (at least one step).
- **Bull put credit:** short the put at or under the stop (or the first strike under the entry), long the same width
  lower.
- Pricing, exits (follow or hold), costs and return on risk are the same as the bear side.

## Tab
- **Keys:** `bls_*` (uni, h, tgt, mode, cd, mrv, ivm, skew, cost, stock_bp, cc, px, dv, hold, split, pick, cand,
  build, live_go, sim_struct, sim_go). No former-leaders file on the bull side.
- **Sections:**
  1. RS leaders in Stage 2 and in leading groups today.
  2. Scoreboard. Splits: SPY cycle, year, mean-reversion thirds, RS leader or not, group RS thirds.
  3. One setup.
  4. Today's candidates (target = close + tgt·R) and live chain pricing with `br_live_read`, a call debit and a put
     credit, simulated with drift = half the setup's past stock move.
- **Guide:** `BL_GUIDE` (O'Neil, Weinstein/Minervini, Moskowitz and Grinblatt, Jegadeesh, Lehmann, Nagel, Bernard
  and Thomas).

## Tests
- **`test_bull.py` (40 checks):**
  - leader and Stage 2 states; the 40-day on the bull side, the 50-day kept on the bear side; labels; the leaders
    table's "vs 40-day" and each event's extension
  - each bull setup on planted paths, including the mean-reversion dip in a leader, in a leading group, not in a
    lagging group, and with no group map
  - both bull spreads by hand: hold at 108 pays the full width, put credit keeps the credit, follow, strikes under the
    entry, skew
  - the shared strike helper on both sides
  - a demo run's long R by hand and edge vs the uptrend baseline; group RS on events; verdicts; group-split coverage;
    today's plan
  - no group setup on the market
  - live call debit and put credit from a demo chain
- **`apptest_bull.py`:** the whole tab headless, including both simulations.
- **`test_bear.py`** (45) and **`apptest_bear.py`** still pass after the refactor.

## Heston pricer (Nov 4 2026)
Settings > *Option pricer* chooses the fixed skew (default) or Heston fitted to today's chains; section 5 fits it, shows the smiles and re-prices this ledger both ways with the setups whose spread answer changes. See `heston-pricer-handoff.md`.

## Pricer audit (Nov 7 2026)
Options Starter does keep two years of option bars (trades, no quotes). Section 6 of both spread tabs audits the ledger's IV level, smile and spread returns against the real prints of those two years. See `pricer-audit-handoff.md`.
