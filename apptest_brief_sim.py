"""Headless check: the Brief's top names flow into Stocks > Simulation (demo data)."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:500] for e in at.exception]
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def kpis(at, label):
    out = []
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            out.append((v.group(1) if v else "", s.group(1) if s else ""))
    return out
def board(at):
    for d in frames(at):
        if "verdict" in d.columns and "brief" in d.columns:
            return d
    return None
def notes(at, needle): return [m.value[:220] for m in at.markdown if needle in m.value]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1500); at.run()
assert not at.exception, E(at)
pack = at.session_state["brief_top"] if "brief_top" in at.session_state else None
print("Brief pack saved:", pack is not None, "| names:", len(pack["rows"]) if pack else 0,
      "| first:", [(r["order"], r["ticker"], r["tier"], r["ledger_ids"]) for r in (pack or {}).get("rows", [])[:4]])
at.button(key="sim_build").click().run(); assert not at.exception, E(at)
print("ledger built", f"{time.time()-t0:.0f}s", "| source:", at.radio(key="sim_src").value)
B = board(at)
print("board:", None if B is None else B[["brief", "ticker", "list", "setup", "same_scan", "er", "er_lo", "er_hi", "verdict"]]
      .round(2).to_string(index=False))
print("tiles:", kpis(at, "Brief names simulated"), kpis(at, "Simulation supports"), kpis(at, "Same scan as the Brief"))
print("missing note:", notes(at, "On the Brief but not simulated")[:1])
print("picker first options:", at.selectbox(key="sim_pick").options[:3])
at.number_input(key="sim_nbrief").set_value(25).run(); assert not at.exception, E(at)
B25 = board(at); print("25 names -> rows:", None if B25 is None else len(B25), f"{time.time()-t0:.0f}s")
at.radio(key="sim_src").set_value("all").run(); assert not at.exception, E(at)
print("every signal: board gone:", board(at) is None, "| picker options:", len(at.selectbox(key="sim_pick").options))
at.radio(key="sim_src").set_value("brief").run(); assert not at.exception, E(at)
at.number_input(key="sim_nbrief").set_value(7).run()
# fit, then the board's model columns and view 3 with a Brief signal
at.radio(key="sim_part").set_value("model").run()
at.number_input(key="sim_iters").set_value(400).run(); at.number_input(key="sim_warm").set_value(200).run()
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
at.radio(key="sim_part").set_value("paths").run(); assert not at.exception, E(at)
B = board(at)
print("board model columns:", None if B is None else [c for c in ("m_er", "m_p") if c in B.columns],
      None if B is None or "m_p" not in B else B[["ticker", "m_er", "m_p"]].round(2).head(4).to_dict("records"))
at.radio(key="sim_part").set_value("predictive").run(); assert not at.exception, E(at)
n_ok = 0
for i in range(len(at.selectbox(key="sim_setup").options)):
    at.selectbox(key="sim_setup").select_index(i).run(); assert not at.exception, E(at)
    if "signal" in at.radio(key="sim_cond").options:
        at.radio(key="sim_cond").set_value("signal").run(); assert not at.exception, E(at)
        print("view 3 Brief signal:", at.selectbox(key="sim_pcand").options[:2], kpis(at, "Expected R per trade"))
        at.radio(key="sim_cond").set_value("typical").run()
        n_ok += 1
        if n_ok >= 2:
            break
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
