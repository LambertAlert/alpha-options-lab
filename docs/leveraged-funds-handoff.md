# Leveraged funds (Nov 11 2026)

Neil shared financecharts.com's leveraged ETF category and asked to add leveraged funds to the dashboard, to use them
when one is available. The session couldn't reach financecharts.com, so the catalogue is built from Massive's ticker
reference instead. On Nov 10 that held 5,557 active ETFs plus 45 ETNs; about 800 names look leveraged or inverse,
including index, sector and hundreds of 2x single-stock funds. The CSV loader also takes a financecharts export.

## The catalogue (block "LEVERAGED FUNDS" after `render_aw`)
- `lev_parse(ticker, name)` reads, from the fund's name:
  - the signed leverage;
  - the side;
  - what it levers (a stock ticker, or the reference ETF for an index, sector, country, rates, commodity, crypto or
    VIX fund);
  - the kind and the reset (daily, monthly or quarterly).
- Single-stock name styles handled:
  - "2X Long NVDA Daily" (GraniteShares, Tradr, Leverage Shares, T-Rex);
  - "Daily Target 2X Long RKLB" (Defiance);
  - "Direxion Daily MU Bull 2X", including one "Dailly" typo;
  - "Corgi MU 2x Daily".
- Aliases (`LEV_ALIAS`): NVIDIA, Tesla, Alphabet, SpaceX, BRKB and SK hynix. SK hynix is foreign-listed, so those funds
  are kept with no US underlying.
- Index and sector names map through `LEV_INDEX_MAP`, about 60 patterns to reference ETFs.
- `LEV_OVERRIDE` fixes names that state no leverage: SVXY −0.5, UVXY 1.5.
- Not counted: ultra-short bond funds, buffers, long/short funds, option-income funds, "short-term" in a name, and
  1x long products (`LEV_NOT_LEV`).
- Sources, in priority order:
  1. A saved list: `data/lev_funds.csv`, from "Refresh from Massive" (`lev_refresh_massive`: every active ETF and ETN,
     plus the last session's dollar volume from grouped bars) or a loaded CSV merged over it. It is stale after
     7 days.
  2. The built-in seed `LEV_SEED`: 269 funds traded at $0.2M+ a day on 2026-11-10, each with its $M a day.
- Fund choice (`lev_pick`):
  - daily reset only;
  - leverage at most 3x for index and sector funds and 2x for single stocks;
  - at least $5M a day;
  - the highest leverage wins, unless a lower-leverage fund trades over 3x as much.
- Preferences (`LEV_DEFAULTS`, saved to `data/lev_prefs.json`): use funds when available (on), $5M a day minimum,
  3x maximum, 2x maximum for single stocks, 10-session planned hold.

## Maths
- Drag (`lev_drag`) = exp(−(L² − L)/2 · σ² · t) − 1, with σ the underlying's daily volatility (Cheng & Madhavan 2009;
  Avellaneda & Zhang 2010). Checked against a simulation of daily resets: 2x at 3%/day over 20 sessions: model
  −1.80%, simulated −1.81%; 3x: −5.4% vs −5.5%.
- Plan in the fund (`lev_plan`): stop distance L× the stock's on day one; fund shares = dollar risk / (fund price ×
  fund stop %); the same risk takes 1/L of the capital. The cards say to keep the stop on the stock's price, since the
  fund's level drifts after day one.
- Tracking (`lev_tracking`): daily beta, yearly tracking error against L × the underlying, and the realized gap against
  L × held over 20, 60 and 120 sessions, next to the model drag. On demo data the fund's bars come from
  `lev_demo_fund`: L × the underlying's daily return, less a fee, plus noise.

## Where it shows
- **Stocks > Leveraged** (`render_lev`, new tab `S[3]`; later Stocks tabs moved to `S[4..22]`):
  - settings and the list's source, with a Massive refresh and a CSV loader;
  - KPIs;
  1. your names that have a fund: the long and inverse funds, $M a day, the 20-day vol, the drag over the hold, and
     the AVWAP state and setup;
  2. index and sector funds sorted by the trend score of the ETF they lever (Market > Intermarket's score);
  3. the tracking check, with a chart of the fund against L × the underlying;
  4. a plan translator;
  5. the full, filterable list;
  - a guide (`LEV_GUIDE`).
- **Brief > Setups cards**: `su_plan` adds a "Leveraged:" line when using funds is on (`lev_line`). It names the fund,
  its leverage, $M a day, the stop % in the fund against the stock, the capital share and the drag over the hold. ADR
  × 0.6 stands in for the daily σ there.
- **Screener**: a "Leveraged fund" column (shown when using funds is on) and a "Has a leveraged fund" filter in the
  vehicle expander (`sc_lev`).

## Tests
- `test_lev.py`, 26 checks:
  - 32 real names parsed exactly, and 22 look-alikes rejected;
  - the whole seed parses;
  - fund-pick rules;
  - drag vs simulation, plus by hand;
  - plan maths;
  - tracking on a perfect 2x fund and on the demo fund;
  - a financecharts-style CSV;
  - save and load;
  - the Brief line and `su_plan`.
- `apptest_lev.py`:
  - the tab's KPIs and tables;
  - the tracking check;
  - another fund;
  - a 3x plan;
  - list filters (NVDA inverse funds);
  - the liquidity floor;
  - the Screener filter;
  - the on/off switch;
  - a count of Brief cards carrying the line.

## Open
- The ledger still tests setups on the stock. Testing the same entries through the actual fund bars (with Massive)
  would show what drag and fees cost per setup.
- Short-side setups (the bear ledger) could use the inverse fund the same way. The map already has it.
- Option-like gap risk around earnings isn't modelled. The guide only warns about it.
