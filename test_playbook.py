"""Planted-case tests for playbook.py: R on every kind of trade by hand (a trim, a short, a debit and a credit
spread, an open trade marked), Kelly on a coin with a known answer, sizing, frozen expectations, admission rules,
the plan re-run and its cache, tonight's entries and stops by hand, the same-signal match (entry cost, gap, the
rest), selection vs implementation by hand, the live record's band and sequential test on planted streams, skipped
signals, the review, the files (atomic, round trips, the Book import) and the nightly run on demo data.
Run: python test_playbook.py"""
import json
import os
import shutil
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
TMP = tempfile.mkdtemp(prefix="pb_test_")
os.environ["PLAYBOOK_DATA"] = TMP
import alpha_options_lab as L
import playbook as PB

PASS, FAIL = 0, []


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


rng = np.random.default_rng(12)

print("R on every kind of trade")
J = pd.DataFrame([
    {"status": "closed", "ticker": "AAA", "book": "shares", "side": "long", "entry_px": 100, "init_stop": 95, "size": 90,
     "trim_qty": 30, "trim_px": 110, "exit_px": 104},
    {"status": "closed", "ticker": "BBB", "book": "shares", "side": "short", "entry_px": 50, "init_stop": 52, "size": 100,
     "exit_px": 47},
    {"status": "closed", "ticker": "CCC", "book": "debit", "side": "long", "entry_px": 2.0, "size": 3, "exit_px": 3.0},
    {"status": "closed", "ticker": "DDD", "book": "credit", "side": "long", "entry_px": 1.0, "max_risk": 4.0, "size": 2,
     "exit_px": 0.2},
    {"status": "open", "ticker": "EEE", "book": "shares", "side": "long", "entry_px": 20, "init_stop": 19, "size": 100},
    {"status": "closed", "ticker": "FFF", "book": "credit", "side": "long", "entry_px": 1.0, "size": 2, "exit_px": 0.2},
])
R = PB.jr_r(J, {"EEE": 21.5})
check("shares with a trim: (30 at 110 + 60 at 104) / 90 = 106 on 100 with a 5 risk = +1.2R", abs(R.at[0, "r"] - 1.2) < 1e-12, R["r"].tolist())
check("a short: 50 to 47 with the stop at 52 = +1.5R", abs(R.at[1, "r"] - 1.5) < 1e-12)
check("a debit spread: 2.00 to 3.00 = +0.5 of the risk", abs(R.at[2, "r"] - 0.5) < 1e-12)
check("a credit spread: 1.00 received, closed at 0.20, max loss 4 = +0.2", abs(R.at[3, "r"] - 0.2) < 1e-12)
check("an open trade is marked at the last close (21.5 on 20 with a 1 risk = +1.5R), not counted as closed",
      np.isnan(R.at[4, "r"]) and abs(R.at[4, "r_open"] - 1.5) < 1e-12)
check("a credit spread without its max loss has no R (it can't be guessed)", np.isnan(R.at[5, "r"]))

print("Kelly and sizing")
coin = np.where(rng.random(40000) < 0.5, 2.0, -1.0)
check("Kelly on a fair coin paying 2 to 1: p - q/b = 0.25", abs(PB.pb_kelly(coin) - 0.25) < 0.02, PB.pb_kelly(coin))
check("no edge, no stake", PB.pb_kelly(np.where(rng.random(5000) < 0.3, 2.0, -1.0)) == 0.0)
acc = {"equity": 100000, "max_risk_pct": 1.0, "kelly_frac": 0.5}
check("risk per trade: half of a 1.2% Kelly = 0.6%; half of 25% Kelly is capped at your 1%",
      abs(PB.pb_risk_pct({"kelly": 0.012}, acc) - 0.6) < 1e-12 and PB.pb_risk_pct({"kelly": 0.25}, acc) == 1.0)

print("a real ledger on demo bars")
names = list(L.demo_universe()["ticker"])[:40]
bars = {t: L._demo_daily(t, L.UNIVERSE_DAYS) for t in names + ["SPY"]}
spy = bars.pop("SPY")["close"]
P = L.panel_from_bars(bars)
prm = PB.pb_ledger_prm({})
run = L.lg_run(P, spy, None, tuple(L.LG_FAMILIES), "12/26/9", prm, "Your list")
ev = run["ev"]
pd.DataFrame(ev).assign(universe="list").drop(columns=["outcome_txt", "status_txt"], errors="ignore").to_parquet(PB.f_ledger("setup"))
L.atomic_write_json(PB.f_meta("setup"), {"asof": str(P["close"].index[-1].date()), "source": "demo", "setting": "12/26/9",
                                        "prm_full": {k: (list(v) if isinstance(v, tuple) else v) for k, v in prm.items()}})
prm2 = PB.pb_ledger_prm(PB._read_json(PB.f_meta("setup")))
check("the ledger's saved parameters come back (lists back to tuples)", prm2 == prm, {k: (prm[k], prm2.get(k)) for k in prm if prm2.get(k) != prm[k]})
for side in ("bull", "bear"):
    prm_b = PB.pb_br_prm(side)
    rb = L.br_run(P, spy, None, prm_b, side)
    L.br_save(side, {"run": rb, "which": "list"}, prm_b, "demo", 0.4, folder=PB.pb_dir())
led = PB.pb_read_ledgers()
check("the lab's spread save is what the playbook reads: events, candidates and metadata",
      len(led["bull"]["ev"]) > 100 and len(led["bear"]["ev"]) > 100 and led["bear"]["meta"]["source"] == "demo"
      and len(led["bull"]["cands"]) > 0 and {"db_est", "debit_legs", "cr_payoff"} <= set(led["bull"]["cands"].columns))
plan = dict(PB.PB_PLAN_DEFAULT)
evp = PB.pb_relabel(led["setup"]["ev"], P, prm, plan, tag="t1")
ref = L.sim_relabel(P, led["setup"]["ev"], {**prm, "sim_plan": plan})
check("the Setup ledger re-run under your plan = the lab's Simulation re-run", np.allclose(evp["r"].to_numpy(float), ref["r"].to_numpy(float),
                                                                                         equal_nan=True) and evp["r"].notna().sum() > 100)
mt = PB.f_plan_ledger().stat().st_mtime
evp2 = PB.pb_relabel(led["setup"]["ev"], P, prm, plan, tag="t1")
check("cached on disk: the same stamp reads the file back, a new plan re-runs",
      PB.f_plan_ledger().stat().st_mtime == mt and np.allclose(evp2["r"].to_numpy(float), evp["r"].to_numpy(float), equal_nan=True)
      and not np.allclose(PB.pb_relabel(led["setup"]["ev"], P, prm, {**plan, "trim_r": 3.0}, tag="t1")["r"].to_numpy(float),
                          evp["r"].to_numpy(float), equal_nan=True))
sbs = PB.pb_scoreboards(led, evp, prm)
opts = PB.pb_options(sbs, {"dsr": 0.95, "t_spread": 2.5})
s_rows = opts[opts["ledger"] == "setup"]
sb_all = sbs["setup"][sbs["setup"]["split"] == "all"].set_index("setup_id")
want = [(sb_all.at[s, "verdict"] == "PROVEN") and (L._n(sb_all.at[s, "dsr"], 0) >= 0.95) for s in s_rows["setup"]]
check("Setup ledger proposals: exactly the PROVEN ones with a deflated Sharpe of 0.95+ (your exits)",
      list(s_rows["proposal"] == "PROPOSED") == want and len(s_rows) == len(sb_all) - sb_all.index.str.startswith("base:").sum()
      - sb_all.index.isin(list(L.RK_SKIP - {"base:uptrend"})).sum())
sp = opts[(opts["ledger"] != "setup") & (opts["book"] != "shares")]
ok_sp = all((r["proposal"] == "PROPOSED") == (r["verdict"] in ("PROVEN", "PROMISING") and L._n(r["er"], -1) > 0 and L._n(r["t_er"], 0) >= 2.5)
            for r in sp.to_dict("records"))
check("spread proposals: the signal PROVEN or PROMISING and the spread's return on risk positive at t 2.5+", ok_sp and len(sp) > 0)

print("admission and the frozen expectation")
pb = PB.pb_load()
sid = evp[(evp["status"] == 0) & ~evp["setup"].str.startswith("base:")]["setup"].value_counts().index[0]
key = PB.pb_key("setup", sid, "shares")
PB.pb_admit(pb, key, evp, int(prm["horizon"]), "2026-11-02", PB.pb_plan_tag(plan), today="2020-01-01")
e = pb["setups"][key]["expect"]
x = evp[(evp["setup"] == sid) & (evp["status"] == 0)]["r"].dropna().to_numpy(float)
check("frozen at admission: n, mean, spread, win rate, payoff and Kelly from the setup's own trades under your plan",
      e["n"] == len(x) and abs(e["mean"] - x.mean()) < 1e-9 and abs(e["sd"] - x.std(ddof=1)) < 1e-9
      and abs(e["win"] - (x > 0).mean()) < 1e-12 and e["plan"] == PB.pb_plan_tag(plan) and abs(e["kelly"] - PB.pb_kelly(x)) < 1e-12)
PB.pb_save(pb)
pb_r = PB.pb_load()
check("the playbook file round-trips (atomic, no .tmp left)", pb_r["setups"][key]["expect"]["n"] == e["n"]
      and not any(f.endswith(".tmp") for f in os.listdir(TMP)))
kb = PB.pb_key("bull", "bl:pullback_ma", "debit")
PB.pb_admit(pb, kb, led["bull"]["ev"], 5, "x", "", today="2020-01-01")
xb = led["bull"]["ev"]
xb = xb[(xb["setup"] == "bl:pullback_ma") & (xb["status"] == 0)]["db_follow"].dropna()
check("a spread setup is frozen on the spread's return on risk", abs(pb["setups"][kb]["expect"]["mean"] - xb.astype(float).mean()) < 1e-6
      and pb["setups"][kb]["expect"]["metric"] == "db_follow")

print("tonight")
last = led["setup"]["ev"]["date"].max()
fired = led["setup"]["ev"][led["setup"]["ev"]["date"] == last]
pb_t = PB.pb_load()
pb_t["setups"] = {}
sid_t = fired["setup"].iloc[0]
kt = PB.pb_key("setup", sid_t, "shares")
PB.pb_admit(pb_t, kt, evp, 10, "", "", today="2020-01-01")
pb_t["setups"][kt]["expect"]["kelly"] = 0.02
tn = PB.pb_tonight(pb_t, led, P, prm)
r0 = tn[tn["key"] == kt].iloc[0]
e0 = fired[(fired["setup"] == sid_t) & (fired["ticker"] == r0["ticker"])].iloc[0]
c0 = float(P["close"].at[last, r0["ticker"]])
stop0 = c0 * (1 - np.clip(e0["plan_risk_atr"], 0.5, prm["cap"]) * e0["atr_pct"] / 100)
check("the stop: the signal close less the setup's ATR distance, clamped like the ledger's (0.5 to the cap)",
      abs(r0["plan_stop"] / stop0 - 1) < 1e-6 and r0["entry_rule"] == "buy at the next open", (r0["plan_stop"], stop0))   # float32 features
check("the size: half of a 2% Kelly = 1% of 100,000 = $1,000 at risk, over the risk per share",
      abs(r0["risk_dollars"] - 1000) < 1e-9 and r0["size"] == int(1000 // (c0 - r0["plan_stop"])))
tb = PB.pb_tonight(pb_t, led, P, {**prm, "mode": "buy_stop"})
hb = float(P["high"].at[last, r0["ticker"]])
check("buy-stop mode: the trigger is the signal-day high", abs(tb[tb["key"] == kt].iloc[0]["plan_entry"] - hb * 1.0005) < 1e-9)
cb = led["bull"]["cands"]
cb0 = cb[cb["days_ago"] == cb["days_ago"].min()].iloc[0]
pb_t["setups"] = {}
kd = PB.pb_key("bull", cb0["setup"], "debit")
PB.pb_admit(pb_t, kd, led["bull"]["ev"], 5, "", "", today="2020-01-01")
pb_t["setups"][kd]["expect"]["kelly"] = 0.02
td = PB.pb_tonight(pb_t, led, P, prm)
d0 = td[(td["key"] == kd) & (td["ticker"] == cb0["ticker"])].iloc[0]
check("a debit spread tonight: the legs and the estimated debit, contracts = $1,000 over the debit x 100",
      d0["legs"] == cb0["debit_legs"] and abs(d0["plan_entry"] - cb0["db_est"]) < 1e-12 and d0["size"] == int(1000 // (cb0["db_est"] * 100)))
nj = PB.jr_new_rows(tn[tn["key"] == kt])
check("logging tonight's signals: planned rows with the plan filled", len(nj) == (tn["key"] == kt).sum()
      and (nj["status"] == "planned").all() and np.allclose(nj["plan_stop"].astype(float), tn[tn["key"] == kt]["plan_stop"].astype(float)))

print("the same signal: you against the ledger")
done = evp[(evp["setup"] == sid) & (evp["status"] == 0) & (evp["outcome"] != 4)].iloc[:3]
rows = []
for k_, (i_, e_) in enumerate(done.iterrows()):
    fill = e_["entry"] + (0.25 * (e_["entry"] - e_["stop"]) if k_ == 0 else 0.0)        # the first one chased by 0.25R
    rows.append({"status": "closed", "ticker": e_["ticker"], "key": key, "ledger": "setup", "setup": sid, "book": "shares",
                 "side": "long", "signal_date": str(e_["date"].date()) if k_ < 2 else "",
                 "entry_date": str((e_["date"] + pd.Timedelta(days=1)).date()), "entry_px": fill, "size": 100,
                 "init_stop": e_["stop"], "exit_px": e_["entry"] + 1.0 * (e_["entry"] - e_["stop"]),
                 "exit_date": str((e_["date"] + pd.Timedelta(days=7)).date()), "deviation": "chased" if k_ == 0 else ""})
Jt = PB.jr_r(pd.DataFrame(rows))
Jm = PB.pb_match(Jt, {"setup": evp})
check("matched on the signal (and, without a signal date, the latest signal in the days up to the entry)",
      Jm["matched"].all() and Jm.at[2, "signal_date"] == str(done.iloc[2]["date"].date()))
risk0 = done.iloc[0]["entry"] - done.iloc[0]["stop"]
check("entry cost: a fill 0.25R over the ledger's = +0.25R; on the ledger's price, 0",
      abs(Jm.at[0, "entry_cost_r"] - 0.25) < 1e-9 and abs(Jm.at[1, "entry_cost_r"]) < 1e-9)
check("the gap = your R less the ledger's R on the same signal; the rest = the gap plus the entry cost",
      np.allclose(Jm["gap_r"], Jm["r"] - done["r"].to_numpy(float)) and np.allclose(Jm["exit_r"], Jm["gap_r"] + Jm["entry_cost_r"]))
since = "1900-01-01"
dc = PB.pb_decompose(Jm, evp, key, since)
all_ = evp[(evp["setup"] == sid) & (evp["status"] == 0) & (evp["outcome"] != 4)]["r"].dropna()
check("selection = the ledger on your picks less the ledger on every signal; implementation = you less the ledger, same trades",
      abs(dc["e_all"] - all_.mean()) < 1e-9 and abs(dc["e_pick"] - done["r"].mean()) < 1e-9
      and abs(dc["selection"] - (done["r"].mean() - all_.mean())) < 1e-9 and abs(dc["implementation"] - (Jm["r"].mean() - done["r"].mean())) < 1e-9)
sk = PB.pb_skipped(evp, Jm, key, since)
n_sig = int((evp["setup"] == sid).sum())
check("skipped signals: every signal of the setup since admission less the ones you took", len(sk) == n_sig - 3
      and not set(zip(sk["ticker"], sk["signal_date"])) & set(zip(Jm["ticker"], Jm["signal_date"])))

print("the live record")
exp = {"mean": 0.4, "sd": 1.5}
good = rng.normal(0.4, 1.5, 300)
bad = rng.normal(-0.2, 1.5, 300)
lg, lb = PB.pb_live(good, exp), PB.pb_live(bad, exp)
check("a record drawn from the frozen edge: KEEP, and the sequential test confirms it", lg["status"] == "KEEP" and lg["confirmed"], lg)
check("a record with no edge (mean -0.2): RETIRE (the test favours 'no edge' 9 to 1)", lb["status"] == "RETIRE" and lb["llr"] > PB.PB_SPRT, lb)
check("under 5 trades: NEW; the band and z by hand", PB.pb_live([1, -1], exp)["status"] == "NEW"
      and abs(PB.pb_live(good[:50], exp)["band"] - 1.645 * 1.5 * np.sqrt(50)) < 1e-9
      and abs(PB.pb_live(good[:50], exp)["z"] - (good[:50].sum() - 50 * 0.4) / (1.5 * np.sqrt(50))) < 1e-9)
lr = PB.pb_live(np.r_[np.full(20, -1.0)], exp)
check("20 straight stops: under the band, and the test already says the edge is gone", lr["status"] == "RETIRE" and lr["z"] < -1.645)
check("trades needed for a live t of 2 alone: (2 x 1.5 / 0.4)^2 = 57", PB.pb_live(good, exp)["needed"] == 57)
bp = PB.pb_band_path([1.0, -1.0, 2.0], exp)
check("the band path: running total, n x E, +-1.645 sd sqrt(n)", list(bp["you"]) == [1.0, 0.0, 2.0]
      and abs(bp["hi"].iloc[2] - (1.2 + 1.645 * 1.5 * np.sqrt(3))) < 1e-9)

print("review")
Jr = Jm.copy()
Jr.loc[1, "deviation"] = "exited early"
per, dev = PB.pb_review(Jr, "M")
check("by month: trades, total R, discipline (no tag, entry within 0.1R), chased (tag or 0.25R+ worse)",
      per["trades"].sum() == 3 and abs(per["total_r"].sum() - Jr["r"].sum()) < 1e-9 and per["chased"].sum() == 1
      and abs(per["discipline"].mean() - (1 / 3 if len(per) == 1 else per["discipline"].mean())) < 1e-9)
check("what each deviation cost: the gap on its trades", set(dev["deviation"]) == {"chased", "exited early", "followed the plan"}
      and abs(dev.set_index("deviation").at["chased", "mean_gap_r"] - Jr.at[0, "gap_r"]) < 1e-9)

print("files")
PB.jr_save(Jm[PB.JOURNAL_COLS])
J2 = PB.jr_load()
check("the journal round-trips (ids kept, numbers and text intact, no .tmp)", list(J2["id"]) == list(PB.jr_clean(Jm)["id"])
      and np.allclose(J2["entry_px"].astype(float), Jm["entry_px"].astype(float)) and (J2["deviation"].iloc[0] == "chased")
      and not any(f.endswith(".tmp") for f in os.listdir(TMP)))
book = pd.DataFrame([{"sleeve": "shares", "ticker": "zzz", "shares": 50, "entry": 10.0, "stop": 9.5, "entry_date": "2026-10-01",
                      "init_stop": 9.0, "setup": "macd:pullback", "note": "x"},
                     {"sleeve": "options", "ticker": "OPT", "shares": None, "entry": None},
                     {"sleeve": "shares", "ticker": J2.at[0, "ticker"], "shares": 1, "entry": 5.0, "entry_date": J2.at[0, "entry_date"]}])
nb = PB.jr_from_book(book, J2)
check("from the Book: open share positions not in the journal yet, with their setup and initial stop",
      len(nb) == 1 and nb.at[0, "ticker"] == "ZZZ" and nb.at[0, "key"] == "setup|macd:pullback|shares" and nb.at[0, "init_stop"] == 9.0)

print("the nightly run (demo, 30 names)")
T2 = tempfile.mkdtemp(prefix="pb_night_")
os.environ["PLAYBOOK_DATA"] = T2
out = PB.nightly("demo", limit=30, log=lambda *a: None)
files = set(os.listdir(T2))
need = {"setup_ledger.parquet", "setup_ledger_verdicts.json", "bull_ledger.parquet", "bear_ledger.parquet",
        "bull_candidates.parquet", "bear_candidates.parquet", "bull_ledger_meta.json", "bear_ledger_meta.json",
        "playbook_tonight.csv", "playbook_report.md", "playbook_ledger_plan.parquet"}
vm = json.load(open(os.path.join(T2, "setup_ledger_verdicts.json")))
check("it writes every ledger, tonight's signals and the report, marked with the source",
      out["ok"] and need <= files and vm["source"] == "demo" and "prm_full" in vm and "# Playbook report" in open(os.path.join(T2, "playbook_report.md")).read(),
      need - files)
check("nothing left half-written", not any(f.endswith(".tmp") for f in files))
shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(T2, ignore_errors=True)

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
