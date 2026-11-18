"""Headless check of the Simulation's exit signals (demo data, one Brief name to keep it quick): the signals runner
with its thresholds, trim at the target with the signals on the rest, then no target at all."""
import os, re as _re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
assert not at.exception, E(at)
at.session_state["sim_nbrief"] = 1
at.button(key="sim_build").click().run(); assert not at.exception, E(at)
print(f"ledger built {time.time() - t0:.0f}s")
# exit signals: trim at the target with the signals on the rest, then no target at all
at.selectbox(key="sim_runner").set_value("signals").run(); assert not at.exception, E(at)
for k_ in ("sim_dist_drop", "sim_dist_vol", "sim_climax_ext"):
    assert at.number_input(key=k_) is not None, k_
at.number_input(key="sim_climax_ext").set_value(25.0).run(); assert not at.exception, E(at)
_m = _re.search(r"Exits: ((?:sell|breakeven|no target)[^<]{0,500})", md(at))
print("trim + signals note:", _m.group(1)[:260] if _m else None)
assert _m and "the first exit signal" in _m.group(1) and "25%+ over the 50-day SMA" in _m.group(1)
rec = at.session_state["_sim_relabel"]
print("trim + signals relabel: signal exits", int((rec["ev"]["outcome"] == 6).sum()), "| trimmed", f"{rec['ev']['trimmed'].mean():.1%}")
assert (rec["ev"]["outcome"] == 6).any()
at.number_input(key="sim_trim_r").set_value(0.0).run(); assert not at.exception, E(at)
_m = _re.search(r"Exits: ((?:sell|breakeven|no target)[^<]{0,300})", md(at))
print("no target note:", _m.group(1)[:200] if _m else None)
assert _m and _m.group(1).startswith("no target: the whole trade exits on the first exit signal")
rec = at.session_state["_sim_relabel"]
assert not rec["ev"]["trimmed"].any() and (rec["ev"]["outcome"] == 6).any()
C3 = [d for d in frames(at) if "measure" in d.columns and "best trade" in set(d["measure"].astype(str))]
print("no target vs the ledger's exits:", C3[0].set_index("measure").iloc[:3].to_dict("index") if C3 else None)
at.number_input(key="sim_climax_ext").set_value(20.0).run()
print("exit signals: ok")
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
