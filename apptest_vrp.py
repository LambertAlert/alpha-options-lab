"""Headless sweep of Options > VRP desk (American) on demo data: the scan, the forecast check, the board, one name's
term structure, smile and prints, the spreads at two expiries and two deltas, the simulator under its default and
changed settings, a name switch, the thresholds, and a list of names typed in."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value and "VRP desk:" in m.value]
def kpi(at, label):
    import re
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))
    assert not warns(at), (what, warns(at))


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
ok(at, "first run")
print("intro note:", "Every US equity and ETF option is American" in md(at), "| names source:", at.radio(key="av_src").value)
at.radio(key="av_src").set_value("list").run(); ok(at, "list")
at.text_input(key="av_txt").set_value("NVDA, AAPL, TSLA, AMD, META, MSFT").run(); ok(at, "names")
at.button(key="av_go").click().run(); ok(at, "scan")
print(f"scanned {time.time() - t0:.0f}s")
m = md(at)
print("approximate-prices warning:", "Approximate prices: Options Starter carries no bid or ask" in m, "| rate note:", "Rate: " in m)
print("forecast KPIs:", kpi(at, "21-session forecast loss (QLIKE)"), kpi(at, "63-session vol error"))
B = [d for d in frames(at) if "signal" in d.columns and "vrp_log" in d.columns]
assert B and len(B[0]) == 9, [list(d.columns) for d in frames(at)]
print("board:", B[0][["sym", "signal", "iv30", "fair30", "vrp_pts", "z", "event"]].round(3).to_dict("records"))
CF = [d for d in frames(at) if "sessions ahead" in d.columns]
print("HAR coefficient rows:", len(CF[0]) if CF else 0)
print("name KPIs:", kpi(at, "Read"), kpi(at, "VRP"), kpi(at, "Early-exercise premium"))
ST = [d for d in frames(at) if "structure" in d.columns and "edge_net" in d.columns]
assert ST and len(ST[0]) >= 4
print("structures:", ST[0][["structure", "fits", "strikes", "price", "max_loss", "edge", "edge_net", "pop"]].round(2).to_dict("records"))
pick = at.selectbox(key="av_pick").value
print("name:", pick, "| sim button:", [b.label for b in at.button if b.key == "av_sim_go"])
at.button(key="av_sim_go").click().run(); ok(at, "simulate")
SIM = [d for d in frames(at) if "rule" in d.columns and "cvar5" in d.columns]
assert SIM and len(SIM[0]) == 7
print("simulation:", SIM[0][["rule", "er", "win", "cvar5", "days", "assigned"]].round(2).to_dict("records"))
print("sim KPIs:", kpi(at, "Best rule on these paths"), kpi(at, "VRP gap at entry"))

# another structure, another expiry, other deltas
sk = f"av_struct_{pick}"
opts = at.selectbox(key=sk).options
at.selectbox(key=sk).set_value(opts[-1]).run(); ok(at, "other structure")
at.button(key="av_sim_go").click().run(); ok(at, "simulate other")
print("other structure:", at.selectbox(key=sk).value, "| rows:", len([d for d in frames(at) if "rule" in d.columns][0]))
dk = f"av_dte_{pick}"
ex = at.selectbox(key=dk)
at.selectbox(key=dk).set_value(ex.options[-1] if hasattr(ex, "options") else ex.value).run(); ok(at, "other expiry")
at.number_input(key="av_sd").set_value(0.35).run(); ok(at, "short delta")
at.number_input(key="av_wd").set_value(0.15).run(); ok(at, "wing delta")
at.number_input(key="av_cost").set_value(4.0).run(); ok(at, "cost")
ST2 = [d for d in frames(at) if "structure" in d.columns and "edge_net" in d.columns]
print("structures at the last expiry, 35/15 delta:", ST2[0][["structure", "strikes", "edge_net"]].round(1).to_dict("records") if ST2 else None)
# simulator settings: no correction, tighter exits
for k_, v_ in (("av_hl", 0), ("av_tp", 0.25), ("av_stc", 1.0), ("av_vc", 0.5), ("av_dx", 10), ("av_band", 0.05), ("av_n_paths", 600)):
    at.number_input(key=k_).set_value(v_).run(); ok(at, k_)
at.button(key="av_sim_go").click().run(); ok(at, "simulate no correction")
SIM3 = [d for d in frames(at) if "rule" in d.columns and "cvar5" in d.columns]
print("no correction:", SIM3[0][["rule", "er", "win"]].round(2).to_dict("records") if SIM3 else None)
# a different name and the thresholds
names = at.selectbox(key="av_pick").options
at.selectbox(key="av_pick").set_value(names[-1]).run(); ok(at, "other name")
print("other name:", at.selectbox(key="av_pick").value, "| read:", kpi(at, "Read"))
at.number_input(key="av_rich").set_value(0.30).run(); ok(at, "rich threshold")
at.number_input(key="av_cheap").set_value(-0.20).run(); ok(at, "cheap threshold")
B2 = [d for d in frames(at) if "signal" in d.columns and "vrp_log" in d.columns]
print("signals at +0.30 / -0.20:", B2[0]["signal"].value_counts().to_dict() if B2 else None)
print("guide:", any("What the desk is for" in x.value for x in at.markdown))
# without the ETFs
at.checkbox(key="av_idx").set_value(False).run(); ok(at, "no ETFs")
at.button(key="av_go").click().run(); ok(at, "rescan")
B3 = [d for d in frames(at) if "signal" in d.columns and "vrp_log" in d.columns]
print("rescan without ETFs:", len(B3[0]) if B3 else 0, "names")
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
