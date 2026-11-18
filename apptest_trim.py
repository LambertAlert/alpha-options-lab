"""Headless sweep of the Simulation tab's exit plans (demo data): trim and trail by default, its settings, the
comparison on the same paths, the ledger's exits, and the model and next-trades views on relabeled trades."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def kpi(at, label):
    import re
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value)
            return v.group(1) if v else ""
    return None


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
assert not at.exception, E(at)
at.button(key="sim_build").click().run(); assert not at.exception, E(at)
print(f"ledger built {time.time() - t0:.0f}s | exits:", at.radio(key="sim_plan").value, "| H:", at.number_input(key="sim_h").value)
rec = at.session_state["_sim_relabel"]
print(f"relabel: {rec['secs']:.1f}s, trades {int((rec['ev']['status'] == 0).sum()):,}, trimmed "
      f"{rec['ev']['trimmed'].mean():.1%}, cut {(rec['ev']['outcome'] == 5).mean():.1%}")
m = md(at)
print("plan note:", "Every view uses it" in m)
B = [d for d in frames(at) if "verdict" in d.columns and "er_cmp" in d.columns]
print("board:", B[0][["ticker", "verdict", "er", "er_cmp", "p_exit", "p_big", "p_open"]].round(2).to_dict("records") if B else None)
C = [d for d in frames(at) if "measure" in d.columns and "best trade" in set(d["measure"].astype(str))]
print("comparison:", C[0].set_index("measure").to_dict("index") if C else None)
assert C and C[0].shape[1] == 3 and "median hold, losers (sessions)" in set(C[0]["measure"])
print("KPI trimmed:", kpi(at, "Trimmed at the target"))

# settings in the popover
for k_, v_ in (("sim_runner", "ema10"), ("sim_closes", "2"), ("sim_trim_frac", "1/2"), ("sim_trim_stop", "lock"),
               ("sim_trim_r", 3.0), ("sim_fail_n", 3), ("sim_fail_mode", "every"), ("sim_be_r", 1.0)):
    w = (at.selectbox(key=k_) if k_ == "sim_runner" else at.radio(key=k_) if k_ in ("sim_closes", "sim_trim_frac", "sim_trim_stop",
                                                                                       "sim_fail_mode")
         else at.number_input(key=k_))
    w.set_value(v_).run()
    assert not at.exception, (k_, E(at))
C = [d for d in frames(at) if "measure" in d.columns and "best trade" in set(d["measure"].astype(str))]
print("after settings:", C[0].iloc[:, :2].set_index("measure").iloc[:, 0].to_dict() if C else None)
import re as _re
_m = _re.search(r"Exits: ((?:sell|breakeven)[^<]{0,300})", md(at))
print("plan note after settings:", _m.group(1) if _m else None)
for k_, v_ in (("sim_runner", "chandelier"), ("sim_runner", "sma50"), ("sim_fail_n", 0)):
    (at.selectbox(key=k_) if k_ == "sim_runner" else at.number_input(key=k_)).set_value(v_).run()
    assert not at.exception, (k_, E(at))
print("other runners and no cut: ok")
for k_, v_ in (("sim_runner", "ema21"), ("sim_closes", "1"), ("sim_trim_frac", "1/3"), ("sim_trim_stop", "be"),
               ("sim_trim_r", 2.0), ("sim_fail_n", 5), ("sim_fail_mode", "once"), ("sim_be_r", 0.0)):
    w = (at.selectbox(key=k_) if k_ == "sim_runner" else at.radio(key=k_) if k_ in ("sim_closes", "sim_trim_frac", "sim_trim_stop",
                                                                                       "sim_fail_mode")
         else at.number_input(key=k_))
    w.set_value(v_).run()

# the ledger's exits
at.radio(key="sim_plan").set_value("ledger").run(); assert not at.exception, E(at)
B2 = [d for d in frames(at) if "verdict" in d.columns and "er_cmp" in d.columns]
print("ledger exits board:", B2[0][["ticker", "er", "er_cmp"]].round(2).to_dict("records")[:3] if B2 else None)
C2 = [d for d in frames(at) if "measure" in d.columns and "best trade" in set(d["measure"].astype(str))]
print("ledger exits comparison columns:", list(C2[0].columns) if C2 else None)
at.radio(key="sim_plan").set_value("trim").run(); assert not at.exception, E(at)

# model and next trades on the relabeled trades
at.radio(key="sim_part").set_value("model").run(); assert not at.exception, E(at)
t1 = time.time()
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
print(f"model fit {time.time() - t1:.0f}s | rows {kpi(at, 'Signal dates')} | k {kpi(at, 'Overlap factor k')} | "
      f"R-hat {kpi(at, 'Worst R-hat')} | ESS {kpi(at, 'Fewest effective draws')}")
at.radio(key="sim_part").set_value("predictive").run(); assert not at.exception, E(at)
print("next trades:", kpi(at, "Expected R per trade"), kpi(at, "Bayesian Kelly"))
at.radio(key="sim_part").set_value("paths").run(); assert not at.exception, E(at)
print("guide has the exits section:", "Exits: trim at the target" in md(at))
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
