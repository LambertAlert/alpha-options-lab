import time, warnings; warnings.filterwarnings("ignore")
from streamlit.testing.v1 import AppTest
E=lambda at:[str(e.value)[:300] for e in at.exception]
t0=time.time()
at=AppTest.from_file("group_asym_app.py",default_timeout=900); at.run()
at.sidebar.button[0].click().run(); assert not at.exception,E(at)
md=lambda: " ".join(m.value for m in at.markdown)
print("burst panel:", "Burst odds" in md(), "| Setups col:", any("p_target" in getattr(d.value,"columns",[]) for d in at.dataframe))
for t in at.selectbox(key="ga_pick").options[:12]:
    at.selectbox(key="ga_pick").set_value(t).run(); assert not at.exception,(t,E(at))
import datetime as dt
at.date_input(key="ga_bdate").set_value(at.date_input(key="ga_bdate").value+dt.timedelta(days=40)).run(); assert not at.exception,E(at)
for v in (0.5,2.5): at.slider(key="ga_bk").set_value(v).run(); assert not at.exception,E(at)
at.select_slider(key="ga_bw").set_value(252).run(); at.toggle(key="ga_btouch").set_value(False).run(); assert not at.exception,E(at)
at.toggle(key="ga_btouch").set_value(True).run(); at.slider(key="ga_bk").set_value(1.0).run()
at.button(key="ga_cal_go").click().run(); assert not at.exception,E(at)
print("calibration ok", "Brier skill" in md(), f"{time.time()-t0:.0f}s")
at.slider(key="ga_h").set_value(10).run(); at.button(key="ga_cal_go").click().run(); assert not at.exception,E(at)
print("sweep done", f"{time.time()-t0:.0f}s", E(at))
