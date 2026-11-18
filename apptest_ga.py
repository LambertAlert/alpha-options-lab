import time, warnings; warnings.filterwarnings("ignore")
from streamlit.testing.v1 import AppTest
def E(at): return [e.value for e in at.exception]
t0=time.time()
at=AppTest.from_file("group_asym_app.py",default_timeout=600); at.run(); assert not at.exception,E(at)
at.sidebar.button[0].click().run(); assert not at.exception,E(at)
print("loaded:",[s.value for s in at.success], f"{time.time()-t0:.0f}s")
print("tiles:", [m.value[:0] for m in at.markdown][:0])
at.button(key="ga_run").click().run(); assert not at.exception,E(at)
print("replay ok")
for k,v in [("ga_by","Theme"),("ga_by","Industry")]:
    at.selectbox(key=k).set_value(v).run(); assert not at.exception,(k,v,E(at))
at.slider(key="ga_top").set_value(40).run(); assert not at.exception
at.slider(key="ga_rs").set_value(90).run(); assert not at.exception
at.number_input(key="ga_rr").set_value(2.0).run(); at.number_input(key="ga_risk").set_value(2.5).run(); at.number_input(key="ga_ext").set_value(2.0).run(); assert not at.exception,E(at)
at.toggle(key="ga_cap").set_value(True).run(); assert not at.exception,E(at)
at.number_input(key="ga_ming").set_value(15).run(); print("min 15:",E(at),[w.value[:50] for w in at.warning])
at.number_input(key="ga_ming").set_value(3).run()
at.radio(key="ga_scope").set_value("All RS leaders").run(); at.multiselect(key="ga_stat").set_value([]).run(); assert not at.exception
at.multiselect(key="ga_stat").set_value(["Asymmetric now","Wait for pullback","Extended","No clean stop"]).run()
for t in at.selectbox(key="ga_pick").options[:15]:
    at.selectbox(key="ga_pick").set_value(t).run(); assert not at.exception,(t,E(at))
at.slider(key="ga_h").set_value(10).run(); at.button(key="ga_run").click().run(); assert not at.exception,E(at)
print("sweep ok", f"{time.time()-t0:.0f}s", "exceptions", E(at))
