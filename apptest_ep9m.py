"""Headless sweep of Stockbee's EP 9 million across the app (demo data): Screener column, Brief > Setups scan,
movers flag, the Setup ledger's EP family and the Simulation's Brief board."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1500); at.run()
assert not at.exception, E(at)
scr = [d for d in frames(at) if "ep9_age" in d.columns]
print("screener EP 9M column:", bool(scr), "| names with one in 20 sessions:",
      int(scr[0]["ep9_age"].notna().sum()) if scr else None, "| fired on the last bar:",
      int((scr[0]["ep9_age"] == 0).sum()) if scr else None)
fams = at.multiselect(key="su_fams")
print("Brief scans:", fams.options)
assert "EP 9M" in fams.options and "EP 9M" in fams.value
su = [d for d in frames(at) if "family" in d.columns and "to_trig" in d.columns]
fam_col = su[0]["family"].astype(str) if su else None
print("Brief setups table rows on EP 9M:", int(fam_col.str.contains("EP 9M").sum()) if su else None)
at.number_input(key="su_adr").set_value(0.0).run() if any(w.key == "su_adr" for w in at.number_input) else None
assert not at.exception, E(at)
su = [d for d in frames(at) if "family" in d.columns and "to_trig" in d.columns]
if su:
    ep = su[0][su[0]["family"].astype(str).str.contains("EP 9M")]
    print("  with ADR 0:", len(ep), ep[[c for c in ("signal", "status", "trigger", "stop", "score") if c in ep]].head(5).to_dict("records"))
m = md(at)
print("cards mention Stockbee's plan:", "Taken as an EP 9M" in m, "| guide has EP 9M:", "EP 9 million" in m)
mov = [d for d in frames(at) if "ep9m" in d.columns]
print("movers table EP 9M column shown:", bool(mov), "| flagged:", int(mov[0]["ep9m"].sum()) if mov else 0)
at.multiselect(key="su_fams").set_value(["EP 9M"]).run(); assert not at.exception, E(at)
print("EP 9M scan alone: ok")
at.multiselect(key="su_fams").set_value(list(fams.options)).run(); assert not at.exception, E(at)

# ledger with the EP family (on by default), at the default $10 floor and at $3
print("ledger families:", at.multiselect(key="lg_fams").value)
at.button(key="lg_go").click().run(); assert not at.exception, E(at)
def ep_rows(at):
    for d in frames(at):
        if "Setup" in d.columns and "Deflated Sharpe" in d.columns:
            x = d[d["Setup"].astype(str).str.contains("EP 9 million")]
            x = x[x["Split"].astype(str) == "all"] if "Split" in x.columns else x
            return x[[c for c in ("Setup", "Verdict", "Trades", "E[R]", "Deflated Sharpe") if c in x.columns]]
    return None
r10 = ep_rows(at)
print(f"ledger built ({time.time() - t0:.0f}s), EP rows at $10:", None if r10 is None else r10.round(3).to_dict("records"))
at.number_input(key="lg_px").set_value(3.0).run()
at.number_input(key="lg_dv").set_value(3.0).run()
at.button(key="lg_go").click().run(); assert not at.exception, E(at)
r3 = ep_rows(at)
print(f"ledger rebuilt ({time.time() - t0:.0f}s), EP rows at $3:", None if r3 is None else r3.round(3).to_dict("records"))
print("ledger guide has the EP section:", "The EP family (Stockbee's EP 9 million)" in md(at))
at.selectbox(key="lg_split").set_value("family").run() if any(w.key == "lg_split" and "family" in w.options for w in at.selectbox) else None
assert not at.exception, E(at)

# simulation board
at.radio(key="sim_part").set_value("paths").run(); assert not at.exception, E(at)
B = [d for d in frames(at) if "verdict" in d.columns and "brief" in d.columns]
if B:
    b = B[0]
    print("simulation board rows:", len(b), "| EP setups simulated:",
          int(b["setup"].astype(str).str.contains("EP 9 million").sum()) if "setup" in b else "n/a")
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")

# planted EP 9M names (the demo has none live this week): the Brief scan, cards, plan and caution lines
print("\n--- planted EP 9M names")
pt = AppTest.from_file("apptest_ep9m_planted_app.py", default_timeout=1500); pt.run()
assert not pt.exception, E(pt)
pt.number_input(key="su_adr").set_value(0.0).run(); assert not pt.exception, E(pt)
rows = [d[d["signal"].astype(str).str.startswith("EP 9 million")] for d in frames(pt)
        if "signal" in d.columns and "to_trig" in d.columns]
import pandas as pd
rows = pd.concat(rows).drop_duplicates("ticker") if rows else pd.DataFrame()
print("EP 9M rows on Brief > Setups:", len(rows))
print(rows[["ticker", "status", "signal", "score", "trigger", "stop", "risk_pct"]].to_string() if len(rows) else "")
assert len(rows) >= 2, "planted EP 9M names should reach the Brief"
assert set(rows["status"]) >= {"fired today"}
m = md(pt)
print("card plan line:", "Taken as an EP 9M" in m, "| no-catalyst caution:", "EP 9M with no catalyst" in m)
pk = pt.session_state["brief_top"]
print("Brief pack names with an EP 9M ledger setup:",
      [r["ticker"] for r in pk["rows"] if any(str(x).startswith("ep:") for x in r["ledger_ids"])])
pt.multiselect(key="su_fams").set_value(["EP 9M"]).run(); assert not pt.exception, E(pt)
print("EP 9M scan alone: ok | exceptions:", E(pt), f"| {time.time() - t0:.0f}s")
