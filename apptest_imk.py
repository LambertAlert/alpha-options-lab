"""Headless sweep of Market > Intermarket on demo data: the KPIs, the index legs, the boards, the shocks; then the
Setup ledger built and its breakout trades read by state, and an Intermarket split chosen in the ledger."""
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
    bad = [m.value[:300] for m in at.markdown if "warnbox" in m.value and re.search(r"(Error|Exception|Intermarket): ", m.value)]
    assert not bad, (what, bad)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
for lab in ("Is the move confirmed?", "Dow Theory", "Rotation", "Tape vs the quad", "Mechanical positioning"):
    print(lab, "->", kpi(at, lab)); assert kpi(at, lab) is not None, lab
R = [d for d in frames(at) if "role" in d.columns and "off_high" in d.columns]
assert R and len(R[0]) == 6, "the index legs"
print(R[0].round(3).to_string())
Sh = [d for d in frames(at) if "cta_after" in d.columns]
assert Sh and len(Sh[0]) == 3
print(Sh[0].round(3).to_string())
assert "Build the Setup ledger" in md(at)
at.multiselect(key="lg_fams").set_value(["Trend", "Zanger", "Gap"]).run(); ok(at, "families")
at.button(key="lg_go").click().run(); ok(at, "ledger")
at.run(); ok(at, "rerun: the Market tab is drawn before the ledger builds")
T = [d for d in frames(at) if "read" in d.columns and "state" in d.columns and "er" in d.columns]
assert T and len(T[0]) >= 3, "the breakout trades by state"
print(T[0].round(2).to_string())
at.selectbox(key="lg_split").set_value("imk_flow").run(); ok(at, "ledger split by mechanical positioning")
print(f"exceptions: {E(at)} | {time.time() - t0:.0f}s")
