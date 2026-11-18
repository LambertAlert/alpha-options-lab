"""Headless sweep of Options > Bull spreads on demo data: the ledger on your list (with industry groups) and on the
whole market, RS leaders in Stage 2 and in leading groups, the scoreboard and its splits, one setup up close, today's
candidates priced from the chain, the simulator with the setup's drift for both spreads, and the settings."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value and "Bull spreads:" in m.value]
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
def board(at):
    return [d for d in frames(at) if "verdict" in d.columns and "db_follow" in d.columns and "cr_follow" in d.columns
            and d["setup"].astype(str).str.contains("uptrend|Leader|leader|Stage 2|oversold|EP|55-day|40-day holds").any()]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
ok(at, "first run")
print("intro:", "Leaders in leading groups, bought at the right spot" in md(at))
at.button(key="bls_build").click().run(); ok(at, "build list")
print(f"list built {time.time() - t0:.0f}s | KPIs:", kpi(at, "RS leaders in Stage 2"), kpi(at, "In a leading group"),
      kpi(at, "Oversold now"), kpi(at, "Best edge"))
SB = board(at)
assert SB, [list(d.columns)[:6] for d in frames(at)]
print("scoreboard:", SB[0][["verdict", "setup", "events", "er_date", "t_xs", "db_follow", "cr_follow"]].round(3).to_dict("records"))
for sp in ("cycle", "mrv", "lead", "group", "year"):
    at.selectbox(key="bls_split").set_value(sp).run(); ok(at, sp)
SBg = board(at)
at.selectbox(key="bls_split").set_value("group").run(); ok(at, "group")
SBg = board(at)
print("group split labels:", sorted(set(SBg[0]["split"])) if SBg else None)
at.selectbox(key="bls_split").set_value("none").run(); ok(at, "none")
for o in at.selectbox(key="bls_pick").options[:3]:
    at.selectbox(key="bls_pick").set_value(o).run(); ok(at, o)
CAND = [d for d in frames(at) if "setup_label" in d.columns and "debit_legs" in d.columns]
print("candidates:", CAND[0][["ticker", "setup_label", "signal_close", "stop_plan", "target_plan", "debit_legs", "db_est", "credit_legs", "cr_est"]].head(4).round(2).to_dict("records") if CAND else "none today")
if CAND:
    at.button(key="bls_live_go").click().run(); ok(at, "live")
    LV = [d for d in frames(at) if "spread" in d.columns and "strikes" in d.columns]
    print("chain-priced spreads:", LV[0][["spread", "strikes", "price", "max_loss", "edge", "pop", "delta"]].round(2).to_dict("records") if LV else None)
    if LV:
        at.button(key="bls_sim_go").click().run(); ok(at, "sim debit")
        SIM = [d for d in frames(at) if "rule" in d.columns and "cvar5" in d.columns]
        print("simulated call debit:", SIM[0][["rule", "er", "win", "days"]].round(2).head(3).to_dict("records") if SIM else None)
        at.radio(key="bls_sim_struct").set_value("credit").run(); ok(at, "struct")
        at.button(key="bls_sim_go").click().run(); ok(at, "sim credit")
        SIM2 = [d for d in frames(at) if "rule" in d.columns and "cvar5" in d.columns]
        print("simulated put credit:", SIM2[0][["rule", "er", "win"]].round(2).head(3).to_dict("records") if SIM2 else None)
        print("drift note:", "simulator gives the stock half of that" in md(at))
at.radio(key="bls_h").set_value(3).run(); ok(at, "h3")
at.radio(key="bls_mode").set_value("trigger").run(); ok(at, "trigger")
at.radio(key="bls_cc").set_value("entry").run(); ok(at, "cc entry")
print("stale-settings warning:", "Settings changed since the last build" in md(at))
at.button(key="bls_build").click().run(); ok(at, "rebuild")
SB3 = board(at)
print("3 sessions, buy-stop entry, put short under the entry:", SB3[0][["setup", "events", "er_date", "db_follow", "cr_follow"]].round(3).head(4).to_dict("records") if SB3 else None)
at.radio(key="bls_uni").set_value("market").run(); ok(at, "market")
at.button(key="bls_build").click().run(); ok(at, "build market")
SB4 = board(at)
print("whole market:", SB4[0][["setup", "events", "verdict"]].to_dict("records") if SB4 else None)
print("bear tab still draws:", any("Bear spreads: short setups" in x.value for x in at.markdown))
print("guide:", any("What it's for" in x.value and "Bull trades" in x.value for x in at.markdown))
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
