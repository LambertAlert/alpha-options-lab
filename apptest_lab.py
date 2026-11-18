import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"]="demo"
from streamlit.testing.v1 import AppTest
def E(at): return [str(e.value)[:300] for e in at.exception]
def W(at,needle=""): return [w.value[:160] for w in at.warning if needle in w.value] if hasattr(at,"warning") else []
t0=time.time()
at=AppTest.from_file("alpha_options_lab.py",default_timeout=900); at.run()
print("first run", f"{time.time()-t0:.0f}s", "exceptions", E(at))
wb=[m.value for m in at.markdown if "warnbox" in m.value or "Group leaders" in m.value][:3]
print("group-leaders warn:", [x[:200] for x in wb if "Group leaders" in x])
# group leaders widgets
print("ga keys present:", [k for k in ["ga_by","ga_top","ga_rs","ga_rr","ga_pick","ga_run"] if any(getattr(w,'key',None)==k for w in list(at.selectbox)+list(at.slider)+list(at.number_input)+list(at.button))])
for v in at.selectbox(key="ga_by").options:
    at.selectbox(key="ga_by").set_value(v).run(); assert not at.exception,(v,E(at))
at.selectbox(key="ga_by").set_value(at.selectbox(key="ga_by").options[0]).run()
at.button(key="ga_run").click().run(); assert not at.exception, E(at)
print("ga tab ok", f"{time.time()-t0:.0f}s")
# command tile
md=" ".join(m.value for m in at.markdown)
print("command tile:", "Group leaders" in md and "asymmetric" in md)
# brief setups toggle
print("su_ga toggle:", at.toggle(key="su_ga").value)
cards_on=md.count("Leading group #")
at.toggle(key="su_ga").set_value(False).run(); assert not at.exception, E(at)
md_off=" ".join(m.value for m in at.markdown); print("leading-group badges on/off:", cards_on, md_off.count("Leading group #"))
at.toggle(key="su_ga").set_value(True).run()
# ledger: build then split by the three ga splits
at.button(key="lg_go").click().run(); assert not at.exception, E(at)
print("ledger built", f"{time.time()-t0:.0f}s")
for sp in ["ga_rule","ga_group","ga_rr"]:
    at.selectbox(key="lg_split").set_value(sp).run(); assert not at.exception,(sp,E(at))
    dfs=[d.value for d in at.dataframe]
    hits=[d for d in dfs if hasattr(d,"columns") and any(c in d.columns for c in ("split","Split")) ]
    labs=set()
    for d in hits:
        col="split" if "split" in d.columns else "Split"; labs|=set(map(str,d[col].unique()))
    print(sp, sorted(labs)[:6])
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
# burst odds inside the lab
at.selectbox(key="ga_pick").set_value(at.selectbox(key="ga_pick").options[0]).run(); assert not at.exception, E(at)
md=" ".join(m.value for m in at.markdown)
print("lab burst panel:", "Burst odds" in md)
at.button(key="ga_cal_go").click().run(); assert not at.exception, E(at)
print("lab burst calibration:", "Do the burst odds hold up?" in " ".join(m.value for m in at.markdown), "exceptions", E(at))
