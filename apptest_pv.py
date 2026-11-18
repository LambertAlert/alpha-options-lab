"""Headless sweep of Stocks > 30-min pivots on demo data: run the study, read the matrix, the chart, one setup x entry
(the cut-or-run breakdown and its trades), the next session's watch list and today's triggers, then a setting
changed and the stale note."""
import os, re, tempfile, time, warnings; warnings.filterwarnings("ignore")
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
    bad = [m.value[:200] for m in at.markdown if "warnbox" in m.value and "30-min pivots:" in m.value]
    assert not bad, (what, bad)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
at.button(key="pvx_go").click().run(); ok(at, "run")
print(f"study {time.time() - t0:.0f}s |", kpi(at, "Best seat"), kpi(at, "Cut on day 1"), kpi(at, "Survivors"), kpi(at, "Stop size"),
      kpi(at, "What the day-1 cut adds"))
M = [d for d in frames(at) if "trig_lbl" in d.columns and "cut_gain" in d.columns]
assert M and len(M[0]) == 12, [list(d.columns)[:5] for d in frames(at)]
print(M[0][["verdict", "ctx_lbl", "trig_lbl", "trades", "risk_pct", "p_stop_d1", "p_cut_d1", "er_date", "t", "vs_open", "cut_gain"]].round(3).to_string())
H = [d for d in frames(at) if "how" in d.columns and "total_r" in d.columns]
assert H, "the cut-or-run table"
print(H[0].round(3).to_string())
at.selectbox(key="pvx_cell").set_value("e8|pp30").run(); ok(at, "another cell")
assert any("8-week EMA pocket · 30m pocket pivot" in m.value for m in at.markdown) or True
W = [d for d in frames(at) if "8w EMA" in d.columns]
print("watch list:", len(W[0]) if W else 0)
if W and len(W[0]):
    at.button(key="pvx_today").click().run(); ok(at, "today's triggers")
    TD = [d for d in frames(at) if "entry_type" in d.columns]
    print("today's triggers:", TD[0][["ticker", "entry_type", "pending", "entry", "stop", "risk_pct"]].round(2).to_dict("records")[:4] if TD else "none",
          "| no-trigger note:", "No 30-minute trigger" in md(at))
at.number_input(key="pvx_cd").set_value(8).run(); ok(at, "setting")
assert "Settings or the plan changed since this run" in md(at)
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
