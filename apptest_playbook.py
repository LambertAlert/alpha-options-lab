"""Headless sweep of playbook.py on demo data in a temporary folder: the nightly run writes the ledgers, a journal is
planted on real ledger signals, then every page: the playbook (a setup added by hand, settings saved, the stale-plan
warning), tonight, the journal (saved, the Book imported), the edge tracker (one setup up close) and the review."""
import json, os, re, shutil, tempfile, time, warnings
warnings.filterwarnings("ignore")
TMP = tempfile.mkdtemp(prefix="pb_app_")
os.environ["PLAYBOOK_DATA"] = TMP
os.environ["LAB_SOURCE"] = "demo"
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
import playbook as PB


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))
    errs = [m.value[:200] for m in at.markdown if "warnbox" in m.value and "Playbook:" in m.value and "demo (synthetic)" not in m.value
            and "different exit plan" not in m.value]
    assert not errs, (what, errs)


t0 = time.time()
out = PB.nightly("demo", limit=80, log=lambda *a: None)
assert out["ok"]
ev = pd.read_parquet(PB.f_ledger("setup"))
done = ev[(ev["status"] == 0) & (ev["outcome"] != 4) & ~ev["setup"].str.startswith("base:")]
sid = done["setup"].value_counts().index[0]
key = PB.pb_key("setup", sid, "shares")
pb = PB.pb_load()
PB.pb_admit(pb, key, ev, 10, "", "an older plan", today="2000-01-01")        # frozen under another plan: flagged
PB.pb_save(pb)
pick = done[done["setup"] == sid].iloc[:6]
rows = []
for k, (_, e) in enumerate(pick.iterrows()):
    risk = e["entry"] - e["stop"]
    rows.append({"status": "closed", "ticker": e["ticker"], "key": key, "ledger": "setup", "setup": sid, "book": "shares",
                 "side": "long", "signal_date": str(e["date"].date()), "entry_date": str((e["date"] + pd.Timedelta(days=1)).date()),
                 "entry_px": e["entry"] + (0.3 * risk if k % 3 == 0 else 0.0), "size": 100, "init_stop": e["stop"],
                 "exit_px": e["entry"] + (1.5 if k % 2 else -1.0) * risk,
                 "exit_date": str((e["date"] + pd.Timedelta(days=10)).date()), "deviation": "chased" if k % 3 == 0 else ""})
rows.append({"status": "open", "ticker": pick.iloc[0]["ticker"], "key": "", "book": "shares", "side": "long",
             "entry_date": "2026-10-20", "entry_px": 10.0, "size": 10, "init_stop": 9.0})
PB.jr_save(pd.DataFrame(rows))
pd.DataFrame([{"sleeve": "shares", "ticker": "NEWX", "shares": 20, "entry": 30.0, "stop": 28.0, "entry_date": "2026-10-28",
               "init_stop": 28.0, "setup": sid, "note": "from the Book"}]).to_csv(PB.f_book(), index=False)
print(f"nightly and the plant | {time.time() - t0:.0f}s")

at = AppTest.from_file("playbook.py", default_timeout=1800); at.run()
ok(at, "first run")
m = md(at)
assert "PLAYBOOK" in m and "Setup ledger as of" in m, "masthead"
assert "demo (synthetic)" in m, "the demo warning"
assert "different exit plan" in m, "the stale-plan warning"
print("kpis:", kpi(at, "Active setups"), kpi(at, "Proposed"), kpi(at, "On deck"), f"| {time.time() - t0:.0f}s")
assert kpi(at, "Active setups")[0] == "1"
opts = at.selectbox(key="pb_manual").options
print("manual options:", len(opts))
at.selectbox(key="pb_manual").set_value(PB.pb_key("bull", "bl:pullback_ma", "debit")).run(); ok(at, "pick manual")
at.button(key="pb_manual_go").click().run(); ok(at, "admit by hand")
assert kpi(at, "Active setups")[0] == "2", kpi(at, "Active setups")
pb2 = json.load(open(PB.f_playbook()))
assert "bull|bl:pullback_ma|debit" in pb2["setups"] and pb2["setups"]["bull|bl:pullback_ma|debit"]["expect"]["metric"] == "db_follow"
at.number_input(key="pb_trim_r").set_value(2.5).run()
at.button(key="pb_set_save").click().run(); ok(at, "settings")
assert json.load(open(PB.f_playbook()))["plan"]["trim_r"] == 2.5
print("settings saved; plan:", json.load(open(PB.f_playbook()))["plan"]["trim_r"], f"| {time.time() - t0:.0f}s")
tracker = [d for d in frames(at) if "live_status" in d.columns]
assert tracker and len(tracker[0]) == 2, "the tracker table"
tr = tracker[0].set_index("key")
print(tr[["label", "live_status", "live_n", "live_cum", "e_all", "e_pick", "e_you", "selection", "implementation"]].round(3).to_string())
assert int(tr.at[key, "live_n"]) == 6 and np.isfinite(tr.at[key, "implementation"]), "six closed trades, decomposed"
tw = [d for d in frames(at) if "entry_cost_r" in d.columns and "gap_r" in d.columns]
assert tw and (tw[0]["entry_cost_r"].round(6) == 0.3).sum() == 2, "two chased entries at +0.3R"
assert (tw[0]["key"] == "off-playbook").sum() == 1
at.selectbox(key="pb_tr_key").set_value(key).run(); ok(at, "one setup")
assert "Skipped since" in md(at), "skipped signals"
at.radio(key="pb_rv_f").set_value("M").run(); ok(at, "review by month")
rv = [d for d in frames(at) if "discipline" in d.columns]
dv = [d for d in frames(at) if "mean_gap_r" in d.columns]
assert rv and dv and set(dv[0]["deviation"]) == {"chased", "followed the plan"}, (rv, dv)
print("review:", rv[0][["period", "trades", "total_r", "discipline", "chased"]].to_dict("records")[:2])
at.button(key="pb_jr_book").click().run(); ok(at, "import from the Book")
J = PB.jr_load()
assert (J["ticker"] == "NEWX").sum() == 1 and J.loc[J["ticker"] == "NEWX", "key"].iloc[0] == key
at.button(key="pb_jr_save").click().run(); ok(at, "save the journal")
J2 = PB.jr_load()
assert len(J2) == len(J) and list(J2["key"]) == list(J["key"]) and list(J2["setup"]) == list(J["setup"]), "saving keeps every setup"
tn = [d for d in frames(at) if "entry_rule" in d.columns] + [d for d in at.dataframe if hasattr(d, "value") and "entry_rule" in getattr(d.value, "columns", [])]
print("tonight rows:", len(tn[0]) if tn else 0, "| tonight notes:", "No playbook setup fired" in md(at) or "No signal tonight" in md(at))
# the exit lab: the plan changed above (trim at 2.5R), so its runs aren't cached: run them
if any(b.key == "pb_xl_go" for b in at.button):
    at.button(key="pb_xl_go").click().run(); ok(at, "run the exit lab")
xk = kpi(at, "Your plan: E[R]")
print("exit lab KPIs:", xk, kpi(at, "Trim + signals: E[R]"), kpi(at, "Signals only: E[R]"))
assert xk and kpi(at, "Signals only: E[R]"), "the exit lab KPIs"
side = [d for d in frames(at) if "measure" in d.columns and "signals only" in d.columns]
assert side and {"your plan", "trim + signals", "signals only"} <= set(side[0].columns), "the side-by-side table"
print(side[0].set_index("measure").loc[["E[R] per trade", "vs your plan, per trade (t)", "distribution day", "climax"]].to_string())
wide = [d for d in frames(at) if "er_sig_only" in d.columns]
assert wide and len(wide[0]) > 3, "the by-setup table"
sc = at.selectbox(key="pb_xl_scope")
pick_s = [o for o in at.session_state["_pb_xl"]["T"]["scope"].unique() if o.startswith("setup:")][0]
sc.set_value(pick_s).run(); ok(at, "one setup in the exit lab")
at.button(key="pb_xl_use_sig_only").click().run(); ok(at, "adopt signals only")
pl = json.load(open(PB.f_playbook()))["plan"]
assert pl["runner"] == "signals" and pl["trim_r"] == 0.0 and pl["fail_n"] == 5, pl
assert "no target: the whole trade out on the first exit signal" in md(at), "the masthead shows the new plan"
assert any(b.key == "pb_xl_go" for b in at.button) or kpi(at, "Your plan: E[R]"), "the lab re-runs for the new plan"
print("adopted:", PB.pb_plan_tag(pl))
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
shutil.rmtree(TMP, ignore_errors=True)
