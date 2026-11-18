# Alpha & Options Lab: Martin Luk's pre-market scanner (Nov 1 2026; Fade added Nov 2)

Neil asked for Martin Luk's pre-market scanner as a tab on the Brief, pointing to an X clip from a TraderLion podcast
(x.com/fabianfindsedge). X blocks fetching, so the clip itself wasn't read.

The settings come from martinluk.com, an unofficial fan site that logs his TradingView screeners with stream
timestamps (28 Oct 2026). The process notes come from that site and from a Financial Wisdom write-up. The tab also
carries his other two morning screeners, Leader and Potent, since they run on the same data.

**Brief > Pre-market scanner (Luk)** is the third Brief sub-tab. It runs as an `st.fragment`, so its controls rerun
only the tab. The code is the MARTIN LUK'S SCANNERS block just before `render_brief`. Function prefix `lk_`; session
keys `lkx_`.

## Settings (`LK_DEFAULTS`, all editable in the Filters popover)

| Screener | Filters | Sort |
|---|---|---|
| Premarket | mkt cap > $100M; avg vol 10D > 500K; price × vol > $50M (he may raise it to $100M); volatility 1W > 3.5% | pre-market change %, desc |
| Leader | mkt cap > $100M; avg vol 10D > 500K; price × vol 1W > $300M | perf 1M, desc |
| Potent | price > EMA50; price ≥ EMA21; mkt cap > $100M; vol 1W > 3.5%; price × vol > $50M; change from open outside ±0.5% | chg %, desc |
| Fade (shorts) | avg vol 10D and price × vol as above; the weak-bounce rules below | rejected, testing, triggered since; then tightest EMAs |

Not reproduced: Potent's industry selection (the list wasn't visible in the stream).

## Fade (his shorts), added Nov 2
Neil pasted TraderLion's post (Nov 2026): "Martin Luk doesn't short stocks just because they look overextended. He
targets weak technical bounces during market pullbacks, executing high-probability short entries when price gets
rejected at converging EMAs. Fade the weak bounce." His intraday details come from Trading Resource Hub's write-up of
his short-selling study:
- Names already weak on the higher timeframe, rejected at declining 21 and 50-day EMAs (tighter EMAs, higher
  rejection rate).
- Entry on a break of the prior hourly bar's low or a VWAP retest; stop at the day's high (1.5–5%); 0.5% risk.
- A partial at 3R and at support; out on an hourly close over the 50-day EMA.

The lab uses daily bars, so it applies a daily version. The rules are shared with the bear ledger (`br_fade_parts`,
`BR_FADE`):
- **Weak:** close under the 50-day EMA, the 21 under the 50, the 50 lower than 10 sessions ago and the 21 lower than 5
  sessions ago.
- **Converging:** |EMA50 − EMA21| ≤ 1 ATR14 (`conv_atr`).
- **A bounce:** some close in the last three sessions at least 1 ATR (`bounce_atr`) over the lowest close of the ten
  sessions before it.
  - The first version measured the last three highs against the 10-day low. A planted test showed a slow grind lower
    passes that from its daily ranges alone, so it now uses closes, and the low has to come before the bounce (a drop
    doesn't count either).
- **Light:** the 3-day average volume ≤ the 50-day average from before the bounce (shifted 3).
- **Rejection:** the high within 1% of the 21-day EMA (`touch`), the close under it, a red candle, the close in the
  bottom half of the range.
- **Market pullback:** SPY under its 21-day EMA, or 3%+ (`pb_off`) off its 20-day closing high
  (`br_market_pullback`).

`lk_fade(P, spy, today, Lv=None, look=2)` uses completed sessions only (the last 260 before today). It returns
`(rows, info)`.
- **Status:**
  - REJECTED: a rejection in the last `look` sessions, still under the 21-day EMA.
  - TRIGGERED SINCE: a later session already broke the rejection day's low.
  - TESTING: the setup holds and today touched the EMA without a rejection.
- **Columns:**
  - `trigger` = the rejection day's low; `stop` = its high; `risk` = stop / trigger − 1; `in_range` = risk ≤ 5%.
  - `spread_atr`, `bounce_atr` and `bounce_vol` are as of the rejection day (today for TESTING).
  - `vs21`, `vs50` and `close` are today's.
  - With live quotes (`Lv`): `last` and `triggered` (trading under the trigger now).
- **`info`:** SPY's `pullback`, `vs21`, `off20`, `asof`.

`lk_render_fade` applies the volume filters, then the cap check on the top rows. It shows four KPIs: market pulling
back (YES/NO), rejected, testing, and tightest. It adds a note when the market isn't pulling back, the table, and a
pointer to Options > Bear spreads, where the same rules are scored (`br:luk_fade` with the market condition and
`br:ema_reject` in any market). The weakest-first toggle is off for Leader and Fade.

## Data
- **Whole US market (`lkx_whole`, on by default with Massive):**
  - `lk_whole_panel` = `grouped_panel(LK_SESSIONS=170)` restricted to `lk_stock_set`, $1 and up.
  - `lk_stock_set`: active CS (`common_stock_set`) plus ADRC from `/v3/reference/tickers`, cached a week in
    `data/cache/lk_stocks.json`.
  - Memoized per day. Grouped bars are disk-cached and shared with Market > Breadth.
  - `grouped_panel` now also returns `open`.
  - Off: your universe panel (`ab["P"]`).
- **Live (`lk_live`):** the Brief's `brief_snapshot` (all tickers, reused for 5 minutes, Refresh forces a new one).
  - last = today's latest minute (`min.c` when `min.t` is today) else `day.c`; prior close = `prevDay.c`.
  - Volume so far = max(`min.av`, `day.v`); `fresh` = printed today.
  - `chg_now`; `gap_open` = `day.o` / `prevDay.c` − 1.
- **Modes:**
  - `pre-market` (phase pre-market, ≥ 50 fresh names): sorted by `chg_now`.
  - `session` (after the open): `gap_open` stands in for the frozen pre-market change; Potent goes live (today's chg,
    chg from open, last × volume so far).
  - `last session` (no key, weekends, before 4:00 ET): the last session's open gap, with the fields as of the session
    before (`drop_last`) and that day's open-to-close, i.e. what the list would have said that morning.
  - Demo: `lk_demo_snapshot`, a synthetic 8:45 ET pre-market on the demo panel.
- **Fields (`lk_features`, as of the last completed session):**
  - `avg_vol10`; `pxvol` = last close × last volume; `pxvol_1w` = last close × 5-session volume.
  - `vol_1w` = mean (H/L − 1) over 5 sessions × 100. This is my reading: TradingView's formula wasn't reachable, so
    the threshold is editable.
  - `adr20` = 20-session mean(H/L) × 100 − 100.
  - `chg`, `chg_open`, `perf_1w`, `perf_1m`, `perf_1m_wk_ago`.
  - EMA 9/21/50/150 (pandas `ewm(span, min_periods=span)`); `ext21`, `ext50`; `ema_conv` = (max − min of the
    9/21/50 EMAs) / price × 100; `hi52`.
- **Market cap (`lk_caps`, `lk_apply_caps`):**
  - Checked on the top max(60, rows + 10) after the other filters.
  - Your universe file's `mcap` first, else `fetch_overview` (Massive reference; also gives an industry from SIC),
    kept for the day in the brief store.
  - Under the floor is dropped; unknown is kept and marked (`cap_src`).
- **Extras on Premarket:**
  - Headlines for the top 8 (`lookup_catalysts`, the Brief's memo key) and reported earnings (`earnings_calendar`
    plus `split_earnings`).
  - `lk_ep_gap`: the War Room EP tier by gap only (WATCH 8%, STANDARD 15%, STRONG 25%); the volume test waits for the
    session.
  - Pre-market volume / 10D average.
- **KPIs:**
  - Premarket: names passing, up and down 3%+, 8%+ EP gaps.
  - Leader: names up 20%+ in a month now vs a week ago (his expand/contract read).
  - Potent: passing names and the session read, plus an industries table (rotation).
- **The funnel expander** shows the names left after each filter.
- **Guide:** `LK_GUIDE`: his process (including the fade), how each field is computed, and the sources.

## Tests
- **`test_luk.py` (27 checks):**
  - Each field by hand; today's bar dropped when live; `drop_last`.
  - The snapshot reader (fresh vs stale minute, bad symbols).
  - Each Premarket filter at its edge, the sort, the funnel, weakest first, pre-market volume share, loosened filters.
  - Session and last-session modes.
  - Leader; Potent (EMAs, band, live session values).
  - Caps: file first, Massive cached for the day, under-floor dropped, unknown kept.
  - EP tiers, the demo snapshot, the stock-list cache, grouped bars carrying open.
- **`test_fade.py` (22 checks):** planted charts that pass every rule, plus variants that each fail exactly one (a
  heavy-volume bounce, EMAs far apart, an uptrend, a close back over the EMA).
  - The market gate; both ledger versions firing or not with SPY falling or rising.
  - The ledger event on the rejection day only (not the grind before it), with the stop at that day's high and the
    entry at the next open; the slide after it paying.
  - The Fade screen: REJECTED with trigger and stop, TESTING, TRIGGERED SINCE, live under the trigger, the risk flag.
- **`apptest_luk.py`:** the tab headless on demo data: list and whole market, weakest first, filters, rows, headlines
  off, Leader, Potent, Fade (statuses, sort, setup columns, no weakest-first toggle).
- `apptest_bear.py` still runs clean with the two new ledger setups.

## Open
- **First live morning:** run it after ~8:15 ET (Starter is 15 minutes behind). Check a few pre-market changes and the
  volatility 1W column against his TradingView screen.
- If the X clip gives different numbers, change the defaults in `LK_DEFAULTS`.
- **Potent's industry list:** add it if he shows it.
- **The fade on real data:** build Options > Bear spreads on the whole market and compare `br:luk_fade` with
  `br:ema_reject`. That shows whether the market condition earns its place. His hourly entries and exits aren't
  modelled; the ledger enters at the next open or under the rejection day's low.
