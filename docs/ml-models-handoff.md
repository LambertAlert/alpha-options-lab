# Alpha & Options Lab: PyTorch models (Nov 2 2026; alpha inputs added Nov 3)

Neil asked what PyTorch could do for the War Room. Of six suggestions he picked #2 (an opening-range breakout model
on Luk's gappers) and #4 (a learned ranker on the alpha engine). Answers he gave:
- Breakout outcome: both heads (intraday and swing).
- Opening ranges: compare 5, 15 and 30 minutes.
- Breakout universe: Luk's filters, 4%+ gaps, whole market.
- Ranker universe: whole market, delisted names included.

Two new Stocks sub-tabs, after Trade ranker: **Breakout model (ORB)** (`S[11]`) and **Learned ranker** (`S[12]`).
- Both run as `st.fragment`.
- The tabs from Name stack on moved to `S[13..16]`.
- Code: the LEARNED MODELS block before the TRADE RANKER block. Prefixes `ob_` (breakout), `ar_` (ranker), `ml_`
  (shared); session keys `obx_` and `arx_`.
- Outputs: `data/ml/*.pkl` (atomic pickles).
- CLI: `ml_models.py`.

## Dependencies
- **PyTorch:** optional, lazy-imported (`_torch()`).
  - On Windows, `pip install torch` installs the CPU build.
  - Without it, both tabs say how to install it and still run the trees and the baselines.
  - Saved networks hold numpy state dicts, so pickles load without torch.
- **Trees:** LightGBM if installed (`pip install lightgbm`), else scikit-learn's histogram GBM (`ml_gbm_fit`). Shallow,
  slow, subsampled settings.

## Breakout model
- **Gap days (`ob_events`):** Luk's Premarket filters on the prior close. Names that could never qualify are dropped
  first.
  - Gap at the open ≥ 4%.
  - 10D average volume > 500K, prior day's price × volume > $50M, 1W volatility > 3.5% (mean H/L − 1, 5 sessions).
  - $3 and up; at most 25 a day (biggest gaps).
  - Market cap isn't applied (no history of it).
  - Context as of the prior close (`ob_daily_context`): perf 1W/1M/3M, ext21/50 EMA, 9/21/50 EMA convergence, 52W
    high distance, ADR20, vol 1W, dollar volume, RS (3M rank), market r5 and trend (median-return index), market gap
    (median gap that morning).
  - The next 4 sessions' OHLC ride along for the swing label.
- **Minute bars:** `ObClient(OdClient).minute`, one session per request, adjusted, extended hours. Cached gzip-JSON in
  `data/orb_cache/min/<T>/<date>`; today is never cached. Reused tickers (`T~1`) fetch the root.
- **Trade (`ob_break`, `ob_trade`):**
  - OR = first m ∈ {5, 15, 30} minutes from 9:30.
  - Entry = first bar after it (by 15:30) with high > ORH, filled at ORH or the bar's open if above.
  - Stop = session low before the entry bar, at least 0.2% under the fill. Target 2R.
  - Ties go to the stop: an entry bar through the stop counts as stopped; a bar touching both levels counts as the stop.
  - Intraday: target, stop or the 15:59 close.
  - Swing: the same, then daily bars for up to 5 sessions (a gap through either level fills at the open), else the
    5th close.
  - Costs: 5bp a side, in R.
- **Inputs (`ob_features`, only bars before the entry bar):**
  - 28 static: OB_STATIC, including pm volume share, pm range, open vs pm high, OR range / ADR, risk / ADR, volume pace
    vs `VOL_PROFILE`, VWAP distance, CLV.
  - The last 60 minute bars × 6 channels (return, range, body, log volume pace, position in the OR, VWAP distance),
    ADR-scaled and left-padded.
- **Network (`ob_net`):** Conv1d(6→32, k5) → GELU → Conv1d(32→32) → GELU → dropout; mean+max pool; concat with
  standardized static inputs; MLP 64 → 2 logits.
  - Training: BCE with masks; AdamW 1e-3, wd 1e-4; batch 256; ≤ 30 epochs; early stopping (patience 4) on the
    latest 15% of rows.
- **Walk-forward (`ob_folds`, `ob_walk_forward`):** 6 test blocks after the first 40% of dates. Training rows are dated
  more than 8 days before each block.
  - Each model's picks are the top 20% by score, the cut taken on its validation rows.
  - The trees see the static inputs.
- **Scoring (`ob_score`, `ob_verdict`):** per range × head.
  - All-trades win rate and mean R with NW t; AUC per model; picks' mean R.
  - Paired-by-day edge vs all trades (NW t), `t_pick` (picks' own mean R t), network vs trees.
  - Verdicts:
    - USE THE NETWORK: beats all at t ≥ 2.5, both halves, picks profitable at t ≥ 2, not behind the trees.
    - USE THE TREES: the same test for the trees.
    - LOSES LESS, STILL LOSES; BETTER, NOT YET SURE; TAKE THEM ALL; AVOID; NO EDGE YET.
- **Final models (`ob_fit_final`):** on every trade, for today.
  - `ob_today`: today's gappers (blank = the Luk Premarket scan's 4%+ names) get today's context
    (`ob_context_today`: panel plus a today row with only the open, same code as training), today's minute bars (live,
    15 minutes late), the break so far and both models' odds.
- **Demo:** `ObDemoClient` builds minute paths that agree with the daily bar. First-hour volume is planted to track the
  day's close location. Demo defaults are looser (2% gaps, $5M, 100K, 1%).

## Alpha inputs in the breakout model (Nov 3)
Neil asked to add the alpha scores to the ML models ("it needs more information than just it broke its ORB"),
suggesting PyTorch or PCA for the most informative alphas. The model already had 28 break and context inputs; this
adds the alpha engine's daily cross-sectional view and tests whether it carries anything they don't. Code: the
"alpha engine's view of each gapper" sub-block after `ob_build`; prefixes `ob_alpha_*`, `ob_pca_*`, `ob_select_*`,
`ob_variant_*`.
- **Inputs (`OB_ALPHA_COLS`, 34):**
  - `al_a{id}` for the 27 `AR_IDS` alphas.
  - `al_cat_{MOM,MRV,VOL,CMP,CND,VWP}`.
  - `al_composite`.
  - All centred percentiles (−0.5..0.5); missing = 0 at model time.
- **How they're computed (`ob_alpha_inputs`):**
  - As of the PRIOR close (the session before the gap day). The panel is cut at the last prior close needed, so
    nothing from the gap day on leaks in.
  - Each alpha is placed among that close's crowd (`ob_alpha_universe`): the top 1,000 by 20-day median dollar
    volume, $5+. This is the ranker's universe. A gapper outside it is still placed in it (`_ob_mid_pct`, mid-rank).
  - Categories and the composite are built from those percentiles the way `composite_frames` does: MRV inverted,
    `CATEGORY_WEIGHTS`, IND absent. They are then ranked against the crowd's own (`ob_alpha_rows`).
  - Alphas are computed on the crowd-ever ∪ gappers columns. Internal cross-sectional ranks run over those columns,
    as in the ranker.
- **Attached to the trades:** `ob_attach_alphas` on (ticker, date), one set per gap day for every range. The build
  does this automatically.
  - Older saved trades: the tab's "Add the alpha inputs" button or `python ml_models.py orb --add-alphas` (daily bars
    only, no minute bars).
- **Today (`ob_alpha_today`):** the same computation on the last 320 sessions ending at the last completed close.
  Tested equal to the training inputs for the same day.
- **Four input sets (`OB_VARIANTS`), same walk-forward, network and trees (`ob_walk_forward(variants=)`):**
  - `base`: the 28 break inputs.
  - `alphas`: + all 34.
  - `pca`: + principal components. `ob_pca_fit` uses an eigen-decomposition of the covariance and keeps the fewest
    components reaching 80% of the variance, at most 8. Fit per fold on training rows.
  - `select`: + the 8 with the highest decile mutual information with a win, averaged over heads (`ob_select_fit`,
    `ob_mi_decile`). Fit per fold. MI catches U-shapes.
  - Out-of-sample columns: base keeps the old names (`nn_intra`, `sel_gbm_swing`); the others are `gbm.pca_intra` etc.
    (`ob_col`).
- **Permutation importance:** on each test block, every input of the `alphas` set is shuffled and the AUC drop is
  recorded per head (`ob_perm`). Results go to `wf["perm"]`; per-fold PCA k and selections go to `wf["fits"]`.
  `ob_importance` aggregates them: mean drop, blocks helped, t across blocks, folds selected, mean MI.
- **The test (`ob_score_variants`):** each alpha model's picks vs the same model's picks without alphas, paired by day
  (NW t, halves). BH q runs across every comparison.
  - ADDS INFORMATION: t ≥ 2.5, both halves, q ≤ 0.10.
  - MAYBE: t ≥ 2.
  - WORSE: t ≤ −2 (overfit).
  - NO DIFFERENCE otherwise.
- **The headline (`ob_score`):** gains `alphas`, `alphas_best`, `t_alphas` and `use`.
  - The verdict becomes "USE THE TREES + ALPHA PCA" etc. only if that variant ADDS INFORMATION and also beats every
    break (t ≥ 2.5, halves) with profitable picks (t_pick ≥ 2).
  - Among the qualifying variants, the one with the highest pick R wins, and only if it beats the base recommendation.
- **Final models (`ob_fit_final(variants=)`):** `final["variants"][v]` = {`fit` (PCA or selection on every trade),
  `names`, `nn`, `gbm`}, with numpy state dicts.
- **Today's odds (`ob_today(alpha_today=, use=)`):**
  - Every alpha model scores.
  - `best_intra` / `best_swing` (+ `_by`) carry the odds from the model `ob_use_map(score)` recommends per range and
    head; blank where none is.
  - `alpha_composite` is shown for each gapper.
- **Tab:**
  - "Input sets to compare" (`obx_variants`) and "Add the alpha inputs" (`obx_add_alphas`).
  - New section 3 (`ob_render_alpha_section`):
    - KPIs "Alphas, {m}-min {head}".
    - The variant table (`t_vs_base`, `q_vs_base`, status).
    - The importance table (`auc_drop_gbm` / `_nn`, blocks helped, folds selected, MI).
    - The PCA loadings table (`ob_pca_describe`).
    - By category (`ob_importance_by_category`, Nov 3): permutation AUC losses summed over each category's alphas
      and score, its strongest input, and what high and low mean (`AM_CAT_SIDES`). Stocks > Alphas by trade reads
      the same categories for every other trade type (alpha-map-handoff.md).
  - Today moved to section 4.
- **CLI:** `--no-alphas`, `--add-alphas`, `--variants base,alphas,pca,select`. The run prints the alpha comparison and
  the trees' top alphas.
- **Demo read (synthetic, meaningless):** every set NO DIFFERENCE, except trees + PCA on the 30-minute range, which
  was WORSE (t −2.1). The demo only plants a signal in early minute-bar volume, so that's the right answer there.
- **Tests: `test_orb_alphas.py` (25 checks):**
  - Percentiles, categories and composite by hand.
  - No lookahead; today = training; attach.
  - PCA k on a two-factor matrix; MI picks a U-shaped alpha with AUC ≈ 0.5.
  - A planted alpha found by every-alpha and select (ADDS INFORMATION, verdict moves, importance #1 in every block,
    selected every fold).
  - PCA fit per fold; random alphas never ADD INFORMATION; trades without alphas keep the old columns.
  - Final models with variants; numpy state; today's recommended odds equal a direct prediction.
  - The network finds the planted alpha too.
- **`apptest_ml.py`:** extended: the variant table, importance, PCA, alpha KPIs, today's composite, a base + PCA-only
  run.

## Learned ranker
- **Universe (`ar_panel_prep`):** each day's top 1,000 by 20-day median dollar volume, $5 and up, from
  `lg_market_panel` (delisted names included). The panel is cut to names ever in it; VWAP = typical price.
- **Inputs (`ar_features`):** 27 alphas (`AR_IDS`: all `ALPHA_FUNCS` except the industry-neutral 48/82/90), each as a
  centred percentile across the day's universe (missing = 0). Plus dollar-volume and volatility ranks, and the
  universe's 20-day return and volatility (expanding z) for regime interactions.
- **Targets (`ar_targets`):** next open to the close h ∈ {5, 10, 20} sessions later. A delisted name exits at its last
  close (`ffill(limit=h)`). Raw and centred ranks.
- **Network (`ar_net`):** Linear(31→64) GELU dropout → 32 GELU → 3 heads.
  - Loss: `ar_ic_loss`, minus the average daily Pearson correlation per date and horizon.
  - Batches of 16 dates; AdamW; ≤ 25 epochs; early stopping on validation IC.
- **Benchmarks:**
  - `ar_composite`: the lab's composite, recomputed within the universe.
  - `ar_ridge`: closed form.
  - Trees: regression on ~150 subsampled dates.
- **Walk-forward (`ar_walk_forward`):** 260 warm-up + 250 training days, then 126-day test blocks. Training dates end
  25 sessions (20 + 5 embargo) before each block; the latest 15% validate.
- **Scoring (`ar_score`, `ar_verdict`):**
  - Daily rank IC (NW t, lags = h); IC IR; IC by year.
  - Decile long-short every h sessions, 10bp a side on turnover: net, annualized, Sharpe, turnover, max drawdown.
  - Paired IC edges vs the composite (NW t, both halves) and the network vs ridge and trees.
  - Verdict:
    - The best qualifying method (beats the composite at t ≥ 2.5 in both halves, its own IC t ≥ 2; the network must
      also not trail ridge or the trees).
    - COMPOSITE IS WRONG HERE when the composite's own IC t ≤ −2.
    - KEEP THE COMPOSITE otherwise.
- **Final model (`ar_fit_final`) and today's percentiles** (network and ridge, per horizon, against the composite);
  your list's names flagged.
- **Run time:** in-app on the whole market is slow (alphas on ~2,000+ names × 1,500 days, five blocks), so
  `python ml_models.py ranker` is the way.

## Findings while building
- **The first verdicts were too easy to pass.** On the demo the composite's IC was reliably negative, so anything near
  zero "beat" it. Now a method must also have positive IC of its own (t ≥ 2), and the verdict says COMPOSITE IS WRONG
  HERE when that's the story.
- **Same idea for the breakout model:** picks that only lose less than taking every break get LOSES LESS, STILL LOSES,
  not a recommendation.
- **Synthetic checks:**
  - With a signal planted only in the minute bars, the network found it (AUC > 0.68) and the trees couldn't (< 0.56).
  - With a static signal, the trees found it and the verdict recommended them.
  - With an alpha that flips sign with the market, the network beat ridge by more than 0.15 IC.

## Tests
- **`test_ml.py` (43 checks):**
  - The break, fills, stops, ties, costs, the close exit, swing day 2, gaps through, the 5th close, no later bars, thin
    ranges.
  - Inputs: none from the break bar on; shapes.
  - Gap days: filters on prior-close data, per-day cap, start date.
  - Folds and the embargo.
  - Trees on a static signal; the network on a sequence-only signal; save/restore; daily-paired edge; AUC.
  - Today's rows and context = training context.
  - Ranker: universe, targets (including delisting), IC by hand, long-short and costs by hand, the IC loss vs numpy,
    the network on a regime interaction vs ridge, verdict rules, the full pipeline.
- **`apptest_ml.py`:** both tabs headless on demo data (build, train, both heads, today, ranker, every horizon).
  0 exceptions.
- `apptest_lab.py` and `apptest_rk.py` still pass.

## Open
- **First real run:**
  1. `pip install torch lightgbm`
  2. `python ml_models.py orb --years 1` (one gap day per minute-bar request, cached), then the full 5 years overnight.
  3. `python ml_models.py ranker`
- **Market cap** history isn't available for the gap filter.
- **Survivorship:** `lg_market_panel`'s delisted coverage depends on Massive's inactive CS list.
- **Alpha inputs on the real build:** the first full run answers whether they add anything. Expect the alpha
  computation to add several minutes on the whole market (27 alphas on ~2,500 names x 5 years).
- **Run time:** all four input sets roughly quadruple the walk-forward. `--variants base,pca` is the quick
  comparison.
