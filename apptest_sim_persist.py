"""View 1's settings survive a trip to views 2 and 3, and view 3 follows view 1's signal source."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest
E = lambda at: [str(e.value)[:400] for e in at.exception]
t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1500); at.run()
at.button(key="sim_build").click().run(); assert not at.exception, E(at)
at.radio(key="sim_src").set_value("all").run(); at.number_input(key="sim_recent").set_value(5).run()
at.number_input(key="sim_k").set_value(200).run(); at.number_input(key="sim_h").set_value(40).run()
assert not at.exception, E(at)
at.radio(key="sim_part").set_value("model").run()
at.number_input(key="sim_iters").set_value(300).run(); at.number_input(key="sim_warm").set_value(150).run()
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
at.radio(key="sim_part").set_value("predictive").run(); assert not at.exception, E(at)
ok3 = None
for i in range(len(at.selectbox(key="sim_setup").options)):
    at.selectbox(key="sim_setup").select_index(i).run()
    if len(at.radio(key="sim_cond").options) == 2:
        at.radio(key="sim_cond").set_value("signal").run(); assert not at.exception, E(at)
        ok3 = (at.radio(key="sim_cond").options, at.selectbox(key="sim_pcand").options[:2])
        break
print("view 3 on 'Every signal':", ok3)
at.radio(key="sim_part").set_value("paths").run(); assert not at.exception, E(at)
vals = (at.radio(key="sim_src").value, at.number_input(key="sim_recent").value, at.number_input(key="sim_k").value,
        at.number_input(key="sim_h").value)
print("view 1 after views 2 and 3:", vals, "kept:", vals == ("all", 5, 200, 40))
at.radio(key="sim_part").set_value("model").run()
print("view 2 settings kept:", (at.number_input(key="sim_iters").value, at.number_input(key="sim_warm").value) == (300, 150))
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
