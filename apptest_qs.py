"""Headless sweep of the Quantified Strategies additions on demo data: the Setup ledger with the Pullback family at
the signal-day close, the calendar splits, the close-vs-open comparison, then RS 8-week's new presets and columns."""
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


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
at.multiselect(key="lg_fams").set_value(["Pullback", "Trend", "Gap"]).run(); ok(at, "families")
at.radio(key="lg_mode").set_value("close").run(); ok(at, "close mode")
at.button(key="lg_go").click().run(); ok(at, "build")
SB = [d for d in frames(at) if "Deflated Sharpe" in d.columns and "Setup" in d.columns]
assert SB and SB[0]["Setup"].astype(str).str.contains("RSI\\(2\\)").any(), "Pullback setups on the scoreboard"
print(f"built {time.time() - t0:.0f}s |", SB[0][SB[0]["Setup"].astype(str).str.contains("in an uptrend")][["Setup"]].to_dict("records")[:5])
assert ("signal day&#x27;s close" in md(at)) or ("signal day's close" in md(at)), "the close entry is described"
for sp in ("tom", "opex", "weekday"):
    at.selectbox(key="lg_split").set_value(sp).run(); ok(at, sp)
    labs = set()
    for d in frames(at):
        for col in ("split", "Split"):
            if col in d.columns:
                labs |= set(map(str, d[col].unique()))
    print(sp, sorted(labs)[:8])
at.selectbox(key="lg_split").set_value("none").run()
at.button(key="lg_time_go").click().run(); ok(at, "entry timing")
TT = [d for d in frames(at) if "er_close" in d.columns and "er_open" in d.columns]
assert TT and len(TT[0]) >= 8, "the close-vs-open table"
print("timing:", kpi(at, "Close less next open"), kpi(at, "Setups better at the close"), kpi(at, "Average overnight gap"))
at.radio(key="rs8_src").set_value("universe").run(); ok(at, "rs8 universe")
for pre in ("dip", "stretch", "atr3"):
    at.radio(key="rs8_preset").set_value(pre).run(); ok(at, pre)
R8 = [d for d in frames(at) if "ext21_atr" in d.columns]
print("rs8 columns:", bool(R8), "| rows:", len(R8[0]) if R8 else 0)
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
