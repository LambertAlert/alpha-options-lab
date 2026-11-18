# Market > Intermarket (Nov 11 2026)

Neil shared a summary of John Murphy's *Trading with Intermarket Analysis* (via @JohnxTrades17), AQR's cross-asset
momentum work, Hedgeye's quads and flows, and the capital-flows literature, and asked to refine the overall market
tabs with it. The lab already finds good momentum-burst names, so the new tab answers Murphy's three questions
(what confirms the move, where capital is rotating, where risk is building) and then tests each answer against the
lab's own breakout trades.

## Where it lives
- New Market tab **Intermarket**, `M[3]`. Market tabs are now: Climate, Narratives, Narrative charts, Intermarket,
  Mandelbrot, Price action, Breadth, Vol & sentiment, CMT, Macro.
- Code block "INTERMARKET" just before the "CFA LAYER" header: constants `IMK_*`, `imk_trend`, `imk_trend_shocked`,
  `imk_volctl`, `imk_volctl_shocked`, `imk_frame`, `imk_board`, `imk_dow_record`, `imk_setups`, `imk_page`,
  `IMK_GUIDE`, `_imk_board_chart`, `render_imk`.
- In `main`, built once per data load with `memo(("imk",) + base + ...)` from the same `closes` as Climate; the daily
  frame goes into `ctx["imk"]` so the Setup ledger can split on it.

## Not duplicated (already in the lab)
- Murphy's four-market relationships, Pring's stages and Dow Theory: Market > Narrative charts (`murphy_map`,
  `pring_stages`, `dow_theory`, `ratio_trend`). Intermarket reuses `dow_theory` and points to that tab.
- Intermarket ratio table, RRG and correlation regime: Market > CMT.
- The market-implied quad, RORO, carry, leadership pairs, credit canary, Ilmanen lens: Market > Narratives / Climate.

## The four sections
**1 · Confirmation**
- `imk_confirm`:
  - CONFIRMED: SPY or QQQ within 3% of its 52-week high (`IMK_HI_LEAD`) and two or more of IWM, IYT, RSP within 8%
    (`IMK_HI_LEG`) and over their 200-day.
  - NARROW: a leader at its high and one or no healthy legs. This is the case @JohnxTrades17 described: Nasdaq at
    highs while R2K and Transports lag.
  - BROAD WEAKNESS: SPY 10%+ off its high or under its 200-day, with two legs under their 200-day.
  - MIXED: anything else.
- `imk_dow` = "PRIMARY " + `dow_theory(c)["trend"]`, as a daily state.
- `imk_dow_record`: SentimenTrader's divergence test (DIA at a 52-week high, IYT 8%+ below its own) with SPY's next 63
  sessions. Their long history found it was *not* reliably bearish; the table shows the loaded history.

**2 · Rotation**
- Trend score per market (`imk_trend`), after Macrosynergy's CTA replication on AQR's time-series momentum:
  - lookbacks of 80, 160 and 252 sessions;
  - return / (90-day vol × √L), capped at ±1, then averaged.
- The 20-session change is the rotation. 12-1 month momentum (AQR) ranks the markets.
- Boards for 16 cross-asset ETFs (`IMK_ASSETS`) and 12 sectors (`IMK_SECTORS`).
- `imk_def` / `imk_def_gap`: defensives (XLP, XLU, XLV) against cyclicals (XLY, XLK, XLI, XLF, SMH) on the trend
  score.
- `imk_quad_tape` / `imk_quad_gap`: the lab's market-implied quad picks leaders and laggards (`IMK_QUAD_PLAY`, from
  Hedgeye's published quad playbooks and Fidenza's table). CONFIRMS means the leaders trend 0.30 or more
  (`IMK_QUAD_BAR`) above the laggards, CONTRADICTS means the reverse, and MIXED is anything else.

**3 · Risk building (mechanical flows)**
- Trend followers (CTA proxy): `imk_cta` = the trend score on SPY.
- Vol-control: `imk_vc` = 10% target / max(rv20, rv60), capped at 1.5 (Acadian's example).
- Shock table: the CTA and vol-control positions after one more session down 2%, 3% and 5%. The shocked session is
  appended, not swapped in for today.
- `imk_flow`:
  - STACKED: CTA near fully long and vol-control in its top fifth;
  - UNWINDING: either has dropped sharply in 10 sessions;
  - LIGHT: little left to sell;
  - NORMAL: anything else.

**4 · Your setups**
- `imk_setups(ev, f)` reads the ledger's breakout-type trades (`IMK_BURST_TYPES`: breakout, tight base, gap/EP) by
  each state, with Newey-West t.
- All five reads are Setup ledger splits: `imk_confirm`, `imk_dow`, `imk_flow`, `imk_quad_tape`, `imk_def`, added to
  `LG_SPLITS` and `lg_split_col`. The numeric columns (`IMK_LEDGER_NUM`) ride along in `lg_spy_context`.

## Demo readout (made-up data, not a finding)
KPIs: BROAD WEAKNESS · PRIMARY DOWN · DEFENSIVES LEAD · tape MIXED (deflation scare) · flow UNWINDING.

Breakout-type trades by state (all trades: −0.12R, t −1.7):

| Read | State | E[R] | t |
|---|---|---|---|
| Positioning | UNWINDING | −0.51 | −3.7 |
| Positioning | LIGHT | +0.14 | 0.8 |
| Confirmation | MIXED | −0.29 | −4.3 |
| Confirmation | CONFIRMED | +0.03 | 0.3 |
| Def vs cyc | CYCLICALS LEAD | −0.48 | −5.6 |
| Def vs cyc | MIXED | −0.01 | −0.1 |

These numbers are only a check that the splits work; real data will differ.

## Tests
- `test_imk.py`, 27 checks:
  - the trend score by hand, plus its cap and no look-ahead;
  - the asset board's sort and 12-1 ranks;
  - the vol-control weight and cap;
  - the shock appends a session, and a bigger shock sells more;
  - each confirmation state planted;
  - defensive/cyclical and quad tape planted;
  - flow states;
  - the Dow record;
  - setups by state;
  - the ledger splits wired.
- `apptest_imk.py`: renders the tab, KPIs, legs, shocks, and setups by state after the ledger is built (extra
  `at.run()`, since Market renders before Stocks). No exceptions.

## Caveats
- Positioning is a proxy from prices, not anyone's actual book (no CFTC/COT or prime-broker data).
- Quad playbooks come from published summaries, not Hedgeye's proprietary signals.
- The states are daily and can flicker near their thresholds; check on real data before trading off them.

## Open ideas
- COT (CFTC) positioning as a real check on the CTA proxy.
- Stock-bond correlation sign (AQR: it flips with growth vs inflation shocks) as a state.
- Per-quad playbook confirmation for sectors, scored like the leadership pairs.
