# Group Leaders: handoff (updated Oct 25, 2026: leadership entropy added; inlined into the lab, burst odds included)

Neil's rule: "Seek out group strength and search for asymmetric risk-to-reward spots in RS names."

**Status: built into alpha_options_lab.py (one file).** The former `group_asym.py` module lives inside the lab in a section headed "GROUP LEADERS: group strength x asymmetric R:R in RS names, and burst odds", just above the "GROUP LEADERS: shared state" helpers before `main()`. Every top-level name carries a `ga_` / `GA_` / `_ga_` prefix (e.g. `ga_rs_rating`, `ga_atr`, `ga_ema`, `ga_asymmetry`, `ga_group_table`, `ga_name_table`, `ga_render_group_asym`, `ga_burst_odds`); renamed with the tokenizer, so UI text and dict keys are unchanged. No import, no file beside the lab. A standalone copy (`group_asym.py` + `group_asym_app.py`) still ships in the Moontower desk zip with its old unprefixed names; the lab copy is the one to edit going forward.

This supplements `claude/alpha-options-lab-handoff.md`, whose tab map predates this build: Stocks now has 15 sub-tabs (Screener, RS 8-week, RS leaders, Group leaders, IPO leaders, Alphas, Calibration, Setup ledger, Expectancy & Kelly, Simulation, Trade ranker, Name stack, Filings & flows, Quality, Kelly: stock trades). `typing` import includes `Iterable`, `Sequence`.

## Where it shows up in the lab

| Place | Code | What |
| --- | --- | --- |
| Stocks > Group leaders | `render_group_leaders` (runs as `st.fragment`) → `ga_render_group_asym(ab["P"], key="ga", group_maps=ga_lab_maps(cfg), state_fn=...)` | KPI row, Burst odds settings expander, sub-tabs Groups / Setups / One name / Does it pay? / Leadership entropy. Group-by: Lab groups (resolve_groups), Industry, Theme |
| Shared state | `ga_lab_state(cfg, ab, label, params)` | `memo` keyed by asof, columns, group map and settings; with no args it reads the tab's controls via `ga_params`, so the Brief and ledger read what the tab shows |
| Brief > Setups | toggle `su_ga` (default on), `su_group_read` → `ga_brief_points`, `su_card_html` badges via `best["ga_badges"]`, table column `group_read` | +1 leading group, +1 RS leader asymmetric now, −1 extended |
| Setup ledger | `lg_build` adds `ga_ledger_panels(state)` to `extra` (`ga_gpct`, `ga_rr`, `ga_bucket`, `ga_leader`, plus the entropy features below); rid includes the ga settings; `LG_SPLITS` `ga_rule`, `ga_group`, `ga_rr`, `lead_conc`, `ga_rule_lead`; `lg_split_col` → `ga_rule_labels`, `ga_group_labels`, `ga_rr_labels`, `ga_entropy_regime` | `ga_rule` = the rule vs other RS leaders vs non-leaders, with the ledger's own exits |
| Trade ranker | `RK_FEATURES` `ga_gpct`, `ga_rr`, `ga_x_lead`; `lead_*` in `RK_MARKET` | used automatically |
| Command | tile "Asymmetric leaders" from `st.session_state["ga_last"]` | count, RS leaders in leading groups, extended |

## Definitions (all read with data through day t only; truncation-tested)

- **RS rating:** 0.4·C/C63 + 0.2·C/C126 + 0.2·C/C189 + 0.2·C/C252, ranked 1–99 across the loaded universe.
- **Group strength (0–100):** 40% members' median RS ranked across groups, 20% 20-session change in that rank, 20% breadth (% above 50-day), 20% depth (% RS 80+); each a cross-group percentile that day. Groups need ≥3 members. Leading = strictly top 20%.
- **RS leader:** RS ≥ 80 and above its group's median RS; liquid (price ≥ $5, 20-day median $ volume ≥ $5M).
- **Asymmetry (ATR(14)):** risk = nearest support ≥ 0.5 ATR below the close among 5-day low, 10-day low, 21 EMA, 50-day (stop 0.1 ATR under it). Reward = name's own 75th-percentile 20-session MFE over the past year (completed windows only). Asymmetric = R:R ≥ 3, risk ≤ 1.5 ATR, ≤ 3 ATR over the 21 EMA. Optional 52-week-high cap, off by default.
- **Buy below:** (T + 3S)/4 capped at S + 1.5 ATR.

## Burst odds

- **Model:** burst = close-to-close move ≥ `GA_BURST_K` (1.0) ATR. Rate λ with a gamma prior of `GA_PRIOR_SESS` (63) sessions at the group's rate → NegBin burst counts; up share with a Beta prior of `GA_PRIOR_BURSTS` (10) bursts; sizes shrunk with `GA_SIZE_PRIOR` (5). Two-barrier walk on a 0.25 ATR grid (`ga_burst_walk`) mixed over 9 Beta quantiles; timing from the NB survival curve. Lookback `GA_BURST_W` 126.
- **Touch correction:** Broadie-Glasserman-Kou, both barriers 0.5826 × daily s.d. closer (`ga_touch_shift`), on by default.
- **Outputs and UI:** P(target first by t), P(stop first by t), burst E[R], days to target; Setups columns, One name panel, "Score the burst odds" calibration (Brier, log loss, skill, reliability vs random walk, burst E[R] fifths vs realized R).
- **Functions:** `ga_burst_state`, `ga_burst_params`, `ga_burst_walk`, `ga_nb_pmf_matrix`, `ga_burst_odds`, `ga_burst_timing`, `ga_gauss_odds`, `ga_barrier_outcome`, `ga_burst_table`, `ga_burst_calibration`, `ga_calibration_scores`, `ga_reliability`.
- **Demo calibration (synthetic):** realized 15%; burst model 14% (skill +0.5%), closes-only 11%, random walk 11% (+1.3%). Real data decides.

## Checks

The 33 group-strength and 18 burst checks run against the lab's inlined functions through a name shim (all pass); full lab AppTest: 0 exceptions across every group map, replay, burst panel, burst calibration, Command tile, Brief toggle, ledger build with all the ga splits, ranker training.

## Open

- First live ledger build: split by "Group leaders rule". Does the rule cell beat other RS leaders, and in 2026 alone?
- First live "Score the burst odds": does the burst model beat the random walk, and do burst E[R] fifths sort realized R? If yes: burst E[R] as a ranker feature / ledger split, a Brief evidence line, expiry choice from days-to-target.
- Known model limit: ignores moves smaller than a burst; bursts cluster (Hawkes, backlog #12).
- 435-name list leaves many industries under 3 members; the 1,796-name Tickers.csv or Lab groups gives sturdier reads.
- Ledger results are keyed to the tab's settings at build time; changing thresholds needs a rebuild.
- The desk's standalone `group_asym.py` is now a separate copy; port any lab-side changes there only if the standalone page is still used.

## Leadership entropy (added Oct 25, 2026)

**The question:** does the rule ("seek group strength, then asymmetric R:R in RS names") pay more when leadership is
concentrated in a few groups?

**The measures** (functions `ga_leadership_entropy`, `ga_entropy_cached`, `ga_entropy_regime`, `ga_entropy_table`,
`ga_entropy_edge`):
- **Inputs:** each date, RS leaders are names with RS ≥ the tab's "RS at least", counted by group (the tab's group
  map), against how all names with an RS reading are spread across the same groups.
- **Effective leading groups** = exp(entropy of the leaders' group shares), with the Miller–Madow correction
  (+ (groups with leaders − 1)/2N).
- **Concentration** = KL(leaders' shares ‖ groups' size shares) − (groups − 1)/2N. 2N·KL is the G-statistic, about
  χ²(groups − 1) under random allocation, so 0 means "spread like the names". There's no reading under 10 leaders.
- **Smoothing and percentile:** both are 5-session averages (`GA_ENT_SMOOTH`). The percentile ranks against the
  trailing 252 sessions only (no look-ahead, truncation-tested).
- **Regimes:** narrow = percentile ≥ 2/3, broad ≤ 1/3, middle otherwise.

**Where it shows up:**
- **Group leaders** has a 5th sub-tab, **Leadership entropy**:
  - tiles: effective groups vs spread-like-names, regime and percentile, leader count, top-3 share vs names, and
    concentration in nats
  - history charts: effective groups, and the concentration percentile with the regime lines
  - a "Where the leaders sit" table: share of leaders, share of names, over-representation and contribution
  - "Does the rule pay more when leadership is narrow?": the replay's rule-minus-rest by regime, with NW t's and a
    narrow-minus-broad gap. It shares the replay cache with "Does it pay?".
- **Setup ledger:**
  - `ga_ledger_panels` adds `lead_conc`, `lead_conc_pct` and `lead_eff_groups` (date-level, broadcast to names), plus
    `ga_x_lead` = (group pct − 0.5)(conc pct − 0.5)·4, the interaction.
  - New splits: `lead_conc` (narrow / middle / broad) and `ga_rule_lead` (rule / other RS leaders / non-leaders ×
    narrower / broader than usual).
- **Ranker:** the three date-level features are in `RK_MARKET` (full market mode only); `ga_x_lead` is name-level.
- **Simulation:** all four are in the indicator picker. To test the dependence, add `ga_x_lead`; a green coefficient
  means group strength matters more when leadership is narrow.

**Checks:** `test_leadership_entropy.py` has 23 planted-case checks:
- one group → 1 effective group and log(1/q) concentration
- proportional leaders → KL 0
- a random spread → bias-corrected concentration about 0, while the raw KL is biased up
- Miller–Madow is closer to log G
- the percentile has no look-ahead
- a planted narrow-regime rule edge is found (t > 2, a positive gap)
- the ledger panels and splits

`apptest_entropy.py` covers the sub-tab, the replay, both splits, the Simulation fit with the new indicators, and the
ranker.

**Open:** the first live read. On demo data the rule's edge was −0.19R (t −2.6) in narrow leadership and +0.02R in
broad, which is noise in random data.
