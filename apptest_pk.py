"""Headless sweep of Stocks > Process plinko on demo data: build it, read the KPIs, the funnel, the best paths, one
node's names and one name's plinko, then switch to history, replay an earlier session, change the history length
and see the stale note."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))
    bad = [m.value[:300] for m in at.markdown if "warnbox" in m.value and "Process plinko:" in m.value]
    assert not bad, (what, bad)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
assert "How the plinko works" in " ".join(e.label for e in at.expander), "the guide before a build"
at.button(key="pkx_go").click().run(); ok(at, "build")
print(f"built {time.time() - t0:.0f}s |", kpi(at, "Names in the funnel"), kpi(at, "Name-days in history"), kpi(at, "Best path"))
assert kpi(at, "Names in the funnel") and int(kpi(at, "Names in the funnel")[0]) > 0
PT = [d for d in frames(at) if "names_now" in d.columns]
assert PT and len(PT[0]), "best paths"
print(PT[0][["path", "trades", "er_date", "t", "p_run", "p_cut", "names_now"]].head(6).round(2).to_string())
assert "Setup-ledger signals: build the ledger" in md(at), "the missing-ledger note"
NS = [d for d in frames(at) if "next" in d.columns and "share" in d.columns]
print("now:", kpi(at, "Now"), "| next:", kpi(at, "Usually next"), "| entering:", kpi(at, "Trades on entering it"))
assert kpi(at, "Now") is not None and NS, "one name's read"
nm0 = at.selectbox(key="pkx_name").value
at.selectbox(key="pkx_node").set_value("loc|pocket").run(); ok(at, "a node")
ND = [d for d in frames(at) if "atr_21" in d.columns]
print("pocket names:", len(ND[0]) if ND else 0, "| node note" if "No name in this node" in md(at) else "")
assert ND or "No name in this node" in md(at)
names = at.selectbox(key="pkx_name").options
at.selectbox(key="pkx_name").set_value(names[-1]).run(); ok(at, "another name")
print("name", names[-1], kpi(at, "Now"))
ms = at.multiselect(key="pkx_mark")
print("marked by default:", ms.value); assert ms.value == [nm0], (ms.value, nm0)
pick = [n for n in ms.options if n != (ms.value[0] if ms.value else None)][:2]
at.multiselect(key="pkx_mark").set_value(list(ms.value) + pick).run(); ok(at, "names marked")
NR = [d for d in frames(at) if "route" in d.columns and "rank" in d.columns]
assert NR and len(NR[0]) == len(at.multiselect(key="pkx_mark").value), "the marked-names table"
print(NR[0].round(2).to_string())
at.radio(key="pkx_mode").set_value("history").run(); ok(at, "history mode")
days = at.select_slider(key="pkx_day").options
at.select_slider(key="pkx_day").set_value(days[-20]).run(); ok(at, "replay")
print("replay", days[-20], kpi(at, "Names in the funnel"))
at.radio(key="pkx_years").set_value(1).run(); ok(at, "history length")
assert "build again to match" in md(at), "the stale note"
print(f"exceptions: {E(at)} | {time.time() - t0:.0f}s")
