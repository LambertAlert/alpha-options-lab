# Alpha & Options Lab

A single-file Streamlit research lab for swing trading. It finds momentum names, tests every setup it uses on your own
list, and turns tonight's signals into plans in shares, options or leveraged funds. A companion app, the Playbook,
trades only what has passed the lab's tests and keeps score against it. Part of the Pivot Scanner War Room.

## Run it

```bash
pip install -r requirements-lab.txt
streamlit run alpha_options_lab.py      # the lab
python playbook.py                      # the Playbook (or: streamlit run playbook.py)
```

### Data sources (sidebar)

| Source | What you get |
|---|---|
| **Massive** | Daily bars with VWAP, options, grouped bars and the reference lists (needs an API key). |
| **Yahoo** | Daily bars only: no VWAP and no options. |
| **Demo** | Synthetic data, so every tab runs offline. |

The key goes in `.streamlit/secrets.toml` as `MASSIVE_API_KEY` (or `POLYGON_API_KEY`), or in an environment variable
of the same name. Never commit it; `.gitignore` already excludes `secrets.toml` and `.env`.

`LAB_SOURCE=demo` (or `massive` / `yahoo`) sets the default source.

### Universe

Upload a CSV in the sidebar, or drop `Tickers.csv` or `watchlist_input.csv` next to the app. The symbol column is
auto-detected. `sector_themes.csv` (included) fills in industries and themes.

### Local files

The app writes everything it saves under `data/` (ledgers, caches, your trade log, preferences), which is git-ignored.
Environment variables can relocate them: `LAB_TRADE_LOG`, `LAB_PV_CACHE`, `LAB_OPT_BARS`, `LAB_HESTON_FILE`,
`WARROOM_DATA`.

## Hosted dashboard (Streamlit Community Cloud)

1. On share.streamlit.io, choose **Create app**, then this repo, branch `main`, main file `alpha_options_lab.py`.
   Under Advanced settings, pick Python 3.13.
2. In the app's **Settings > Secrets**, paste:

   ```toml
   MASSIVE_API_KEY = "your key"
   FRED_API_KEY = "your key"        # optional: Market > Macro
   LAB_CLOUD = "1"                  # the hosted layout (below)
   ```

3. Under **Settings > Sharing**, choose "Only specific people can view this app" and invite your own email. The repo
   is public, so the app starts public, and your key pays for anything a visitor runs. Community Cloud allows one
   private app at a time.

How the hosted app differs:
- It installs `requirements.txt`, which leaves out torch and lightgbm. The Breakout model and Learned ranker fall
  back to scikit-learn.
- `LAB_CLOUD = "1"` leaves out the tabs that build or need the ledgers, and the trade log:
  - Stocks: Setup ledger, Expectancy & Kelly, Simulation, Trade ranker, Process plinko, Scorecard, Alphas by trade.
  - Options: Bull and Bear spreads.

  The disk is wiped on every restart, and building ledgers takes minutes and a lot of memory.
- Keys stored in Secrets are never put into a sidebar box. A box's value is sent to the browser; the box is only
  there to override the stored key.
- The app sleeps after 12 hours without a visit; the next visit wakes it.

## What's in it

- **Command / Brief:** the morning read.
  - Movers and gaps against yesterday's range.
  - Brief > Setups: six scans written up as cards with a plan each: MACD, TraderLion LaunchPads, RS leaders, the
    8-week pocket, anchored VWAP and EP 9M.
- **Market:**
  - Climate.
  - Narratives (cross-asset, quads, carry, credit).
  - Narrative charts (Murphy, Pring, Dow Theory).
  - **Intermarket**: confirmation, rotation, and mechanical positioning by trend followers and vol-control funds.
  - Mandelbrot.
  - Price action (LBR, Turtle systems).
  - Breadth.
  - Vol & sentiment.
  - CMT.
  - Macro.
- **Stocks:**
  - Screener.
  - RS 8-week.
  - **VWAP**: Shannon's anchored VWAPs, with the reclaim, pullback and pinch setups.
  - **Leveraged**: daily 2x/3x and inverse funds per name and per sector, the plan in the fund, variance drag and a
    tracking check.
  - RS leaders, Group leaders, IPO leaders.
  - Alphas (the 101 formulaic alphas) and Alphas by trade.
  - Calibration.
  - **Setup ledger**: every long setup family traded on your list's history, scored by date with Newey-West t,
    BH q-values, a holdout and splits.
  - Expectancy & Kelly.
  - Simulation.
  - Trade ranker.
  - Breakout model (ORB).
  - 30-min pivots.
  - Process plinko.
  - Scorecard.
  - Learned ranker.
  - Name stack.
  - Filings & flows.
  - Quality.
  - Kelly for stock trades.
- **Options:**
  - Vol desk.
  - VRP desk.
  - Bull and bear spreads.
  - Market odds.
  - Strategy lab.
  - Dealer positioning.
  - Debit screen.
  - Strike / hit.
  - Flow tape.
  - Kelly for spreads.
- **Positions, Grader, Book, Thesis, Notes:** what you hold, graded and logged.

Each tab has a "How it works" expander with its rules and sources. `docs/` holds the design notes, one per feature,
starting with `alpha-options-lab-handoff.md`.

## Tests

Two kinds, both plain scripts run from the repo root:

- `test_*.py`: unit tests with planted cases and hand checks.
- `apptest_*.py`: headless Streamlit `AppTest` sweeps on demo data. Some take 5-40 minutes.

```bash
python test_lev.py                      # one suite
for f in test_*.py; do python "$f" || echo "FAIL $f"; done
LAB_SOURCE=demo python apptest_lev.py   # one app sweep
```

`group_asym.py` and `odds_build.py` are small helpers some tests import.
