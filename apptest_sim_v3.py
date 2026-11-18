"""Headless check of view 3 with a live / Brief signal (radio options are display labels in AppTest)."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest
E = lambda at: [str(e.value)[:400] for e in at.exception]
def kpis(at, label):
    return [re.search(r"kpi-val'>([^<]*)<", m.value).group(1) for m in at.markdown if f"kpi-lbl'>{label}" in m.value]
t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1500); at.run()
at.button(key="sim_build").click().run(); assert not at.exception, E(at)
at.radio(key="sim_part").set_value("model").run()
at.number_input(key="sim_iters").set_value(300).run(); at.number_input(key="sim_warm").set_value(150).run()
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
for src in ("brief", "all"):
    at.radio(key="sim_src").set_value(src).run() if src == "all" else None
    at.radio(key="sim_part").set_value("predictive").run(); assert not at.exception, E(at)
    found = 0
    for i in range(len(at.selectbox(key="sim_setup").options)):
        at.selectbox(key="sim_setup").select_index(i).run(); assert not at.exception, E(at)
        if len(at.radio(key="sim_cond").options) == 2:
            typ = kpis(at, "Expected R per trade")
            at.radio(key="sim_cond").set_value("signal").run(); assert not at.exception, E(at)
            print(src, "|", at.radio(key="sim_cond").options, "|", at.selectbox(key="sim_pcand").options[:2],
                  "| typical", typ, "-> signal", kpis(at, "Expected R per trade"))
            if len(at.selectbox(key="sim_pcand").options) > 1:
                at.selectbox(key="sim_pcand").select_index(1).run(); assert not at.exception, E(at)
                print("   second signal", kpis(at, "Expected R per trade"))
            at.radio(key="sim_cond").set_value("typical").run(); assert not at.exception, E(at)
            found += 1
            if found >= 2:
                break
    print(src, "setups with a signal tested:", found)
    at.radio(key="sim_part").set_value("paths").run()
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
