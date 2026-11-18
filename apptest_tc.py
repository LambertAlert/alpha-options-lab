"""Headless sweep of Stocks > Scorecard on demo data: load the example trades, grade them (this builds the plinko),
read the split, the 2 x 2, cluster luck, the card and the trade table; save the log and load it back; and check that
no tab anywhere reports an error after the tab order changed."""
import os, re, tempfile, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
os.environ["LAB_TRADE_LOG"] = os.path.join(tempfile.mkdtemp(prefix="tc_app_"), "trade_log.csv")
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
    bad = [m.value[:300] for m in at.markdown if "warnbox" in m.value and re.search(r"(Error|Exception): ", m.value)]
    assert not bad, (what, bad)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
assert "How the scorecard works" in " ".join(e.label for e in at.expander)
at.button(key="tc_demo").click().run(); ok(at, "examples")
assert "Example trades loaded" in md(at)
at.button(key="tc_go").click().run(); ok(at, "grade")
print(f"graded {time.time() - t0:.0f}s |", kpi(at, "Trades graded"), kpi(at, "Your E[R]"), kpi(at, "From your entries"), kpi(at, "From your exits"), kpi(at, "Luck"))
assert kpi(at, "Trades graded") and int(kpi(at, "Trades graded")[0]) >= 40
for lab in ("Good decision, paid", "Good decision, lost", "Poor decision, paid", "Poor decision, lost"):
    assert kpi(at, lab) is not None, lab
print("2x2:", [kpi(at, l)[0] for l in ("Good decision, paid", "Good decision, lost", "Poor decision, paid", "Poor decision, lost")])
print("cluster:", kpi(at, "Worst drawdown"), kpi(at, "Against the reshuffles"), kpi(at, "Is the edge real?"))
assert kpi(at, "Against the reshuffles") is not None
card = [d for d in frames(at) if "skill" in d.columns]
assert card and len(card[0]) >= 5, "the card"
print(card[0][["skill", "score", "detail"]].round(0).to_string())
tr = [d for d in frames(at) if "process_grade" in d.columns and "quadrant" in d.columns]
assert tr and len(tr[0]) >= 40
print(tr[0][["ticker", "r", "process_grade", "outcome_grade", "entry_v", "luck", "exit_v"]].head(5).round(2).to_string())
gp = [d for d in frames(at) if "process_grade" in d.columns and "er" in d.columns]
print(gp[0].round(2).to_string() if gp else "no grade table")
at.button(key="tc_save").click().run(); ok(at, "save")
assert os.path.exists(os.environ["LAB_TRADE_LOG"]), "the log file"
import pandas as pd
print("saved rows:", len(pd.read_csv(os.environ["LAB_TRADE_LOG"])))
assert kpi(at, "Names in the funnel") is not None, "the plinko tab picked up the build"
print(f"exceptions: {E(at)} | {time.time() - t0:.0f}s")
