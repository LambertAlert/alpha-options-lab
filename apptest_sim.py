"""Headless sweep of the Simulation tab (demo data): paths, the look-alike check, the MCMC fit and the predictive view."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:500] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def warns(at): return [m.value[:300] for m in at.markdown if "warnbox" in m.value and "Simulation" in m.value]
def kpis(at, label):
    out = []
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            out.append((v.group(1) if v else "", s.group(1) if s else ""))
    return out


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1500); at.run()
assert not at.exception, E(at)
print("first run", f"{time.time()-t0:.0f}s")
at.button(key="sim_build").click().run(); assert not at.exception, E(at)
print("built from the Simulation tab", f"{time.time()-t0:.0f}s", "| sim warnings:", warns(at))
print("feature options:", len(at.multiselect(key="sim_feats").options), "chosen:", at.multiselect(key="sim_feats").value)
print("look-alike E[R]:", kpis(at, "Look-alikes: E[R]"), "| all:", kpis(at, "This setup, all signals"),
      "| base:", kpis(at, "Random uptrend names"), "| used:", kpis(at, "Look-alikes used"))
picks = at.selectbox(key="sim_pick").options
print("candidates:", len(picks))
for i_ in (1, 2, len(picks) - 1):
    at.selectbox(key="sim_pick").select_index(i_).run(); assert not at.exception, E(at)
    print("  ", picks[i_][:60], kpis(at, "Look-alikes: E[R]")[:1], "| warn:", warns(at)[:1])
at.number_input(key="sim_h").set_value(30).run(); assert not at.exception, E(at)
print("H=30:", kpis(at, "Look-alikes: E[R]")[:1])
at.button(key="sim_check_go").click().run(); assert not at.exception, E(at)
print("knn check IC:", kpis(at, "Information coefficient"), kpis(at, "Out-of-sample R squared"), f"{time.time()-t0:.0f}s")
# model
at.radio(key="sim_part").set_value("model").run(); assert not at.exception, E(at)
at.number_input(key="sim_iters").set_value(500).run()
at.number_input(key="sim_warm").set_value(250).run()
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
print("fit:", kpis(at, "Signal dates"), kpis(at, "Overlap factor k"), kpis(at, "Worst R-hat"), kpis(at, "Fewest effective draws"),
      kpis(at, "Tail thickness (nu)"), kpis(at, "Sampling time"), f"{time.time()-t0:.0f}s")
print("holdout:", kpis(at, "Information coefficient"), kpis(at, "Out-of-sample R squared"), kpis(at, "Predicted vs realized"))
nopt = len(at.selectbox(key="sim_trace").options)
for i_ in (0, 1, nopt - 3, nopt - 1):
    at.selectbox(key="sim_trace").select_index(i_).run(); assert not at.exception, (i_, E(at))
print("traces ok; warn:", warns(at))
# predictive
at.radio(key="sim_part").set_value("predictive").run(); assert not at.exception, E(at)
print("predictive:", kpis(at, "P(the edge is real)"), kpis(at, "Expected R per trade"), kpis(at, "Bayesian Kelly"),
      kpis(at, "Per open trade"))
for sz in ("half", "caut", "custom"):
    at.radio(key="sim_size").set_value(sz).run(); assert not at.exception, (sz, E(at))
print("fan:", kpis(at, "P(a 20% drawdown)"), kpis(at, "Median ending equity"))
for sid in range(min(3, len(at.selectbox(key="sim_setup").options))):
    at.selectbox(key="sim_setup").select_index(sid).run(); assert not at.exception, (sid, E(at))
    if "signal" in at.radio(key="sim_cond").options:
        at.radio(key="sim_cond").set_value("signal").run(); assert not at.exception, E(at)
        print("  live-signal condition ok for", sid, kpis(at, "Expected R per trade"))
        at.radio(key="sim_cond").set_value("typical").run()
# change indicators: model shows stale warning, predictive still works
at.multiselect(key="sim_feats").set_value(at.multiselect(key="sim_feats").value[:3]).run(); assert not at.exception, E(at)
at.radio(key="sim_part").set_value("model").run(); assert not at.exception, E(at)
print("stale-fit warning shown:", "Showing the last fit" in md(at))
at.multiselect(key="sim_feats").set_value([]).run(); assert not at.exception, E(at)
at.radio(key="sim_part").set_value("paths").run(); assert not at.exception, E(at)
print("no indicators, paths:", kpis(at, "Look-alikes: E[R]")[:1], "| warn:", warns(at))
at.radio(key="sim_part").set_value("model").run(); assert not at.exception, E(at)
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
print("fit with no indicators:", kpis(at, "Signal dates"), kpis(at, "Worst R-hat"), "| warn:", warns(at))
at.radio(key="sim_part").set_value("predictive").run(); assert not at.exception, E(at)
print("predictive with no indicators:", kpis(at, "Expected R per trade"), kpis(at, "Bayesian Kelly"))
print("saved posterior:", os.path.exists("data/sim_posterior.parquet"), os.path.exists("data/sim_posterior.json"))
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
