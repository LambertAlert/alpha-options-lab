"""Headless sweep of Stocks > VWAP on demo data: the KPIs, breadth, presets, the name chart and table; the Screener's
anchored-VWAP filters and preset; the Brief's VWAP scan; then the Setup ledger built with the VWAP family, its read on
the VWAP tab, and the ledger split by the AVWAP state."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value)
            return v.group(1) if v else ""
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))
    bad = [m.value[:300] for m in at.markdown if "warnbox" in m.value and re.search(r"(Error|Exception|VWAP): ", m.value)]
    assert not bad, (what, bad)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
for lab in ("Above both", "Between", "Below both", "Setups today", "Bar prices"):
    print(lab, "->", kpi(at, lab)); assert kpi(at, lab) is not None, lab
T = [d for d in frames(at) if "vw_state" in d.columns and "vw_risk_pct" in d.columns and "composite" not in d.columns]
assert T, "the VWAP table"
print(T[0].head(5).round(2).to_string())
for k in ("above", "between", "below", "pinch", "setup", "all"):
    at.radio(key="aw_preset").set_value(k).run(); ok(at, f"preset {k}")
names = at.selectbox(key="aw_pick").options
print("names on the picker:", len(names))
if len(names) > 1:
    at.selectbox(key="aw_pick").set_value(names[1]).run(); ok(at, "pick a name")
assert "How the anchored VWAP tab works" in [e.label for e in at.expander]
assert "with the VWAP family on, and this reads its setups" in md(at)
# the Screener
at.multiselect(key="sc_vw_state").set_value(["ABOVE BOTH"]).run(); ok(at, "screener: AVWAP state")
S = [d for d in frames(at) if "vw_state" in d.columns and "composite" in d.columns]
assert S and set(S[0]["vw_state"].dropna().unique()) <= {"ABOVE BOTH"}, "screener filter"
print("screener above both:", len(S[0]))
at.multiselect(key="sc_vw_state").set_value([]).run()
at.checkbox(key="sc_vw_setup").check().run(); ok(at, "screener: setup in 5 sessions")
at.checkbox(key="sc_vw_setup").uncheck().run()
at.selectbox(key="sc_preset").set_value("Anchored VWAP setup, leader").run(); ok(at, "preset chosen")
# the Brief's scan
fam = at.multiselect(key="su_fams")
assert "VWAP" in fam.options and "VWAP" in fam.value, fam.options
# the ledger
at.multiselect(key="lg_fams").set_value(["VWAP", "RS 8-week", "Zanger"]).run(); ok(at, "families")
at.button(key="lg_go").click().run(); ok(at, "ledger")
at.run(); ok(at, "rerun: the VWAP tab is drawn before the ledger builds")
T1 = [d for d in frames(at) if "setup" in d.columns and "id" in d.columns and "er" in d.columns]
T2 = [d for d in frames(at) if "family" in d.columns and "state" in d.columns and "er" in d.columns]
assert T1 and T2, "the VWAP tab's ledger read"
print(T1[0].round(2).to_string())
print(T2[0].round(2).to_string())
at.selectbox(key="lg_split").set_value("aw_state").run(); ok(at, "ledger split by AVWAP state")
at.selectbox(key="lg_split").set_value("aw_hi").run(); ok(at, "ledger split by distance from the high's line")
print(f"exceptions: {E(at)} | {time.time() - t0:.0f}s")
