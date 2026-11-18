import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"]="demo"
from streamlit.testing.v1 import AppTest
E=lambda at:[str(e.value)[:300] for e in at.exception]
t0=time.time(); at=AppTest.from_file("alpha_options_lab.py",default_timeout=1200); at.run()
at.button(key="lg_go").click().run(); assert not at.exception,E(at)
at.button(key="rk_go").click().run(); print("ranker exceptions", E(at), f"{time.time()-t0:.0f}s")
txt=" ".join(str(d.value.to_string()) if hasattr(d.value,"to_string") else "" for d in at.dataframe)
print("ga features in ranker output:", "Group strength percentile" in txt, "R:R at the signal" in txt)
