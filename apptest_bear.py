"""Headless sweep of Options > Bear spreads on demo data: the ledger on your list plus former leaders and on the whole
market, the former-leaders file, the scoreboard and its splits, one setup up close, today's candidates priced from the
chain, the simulator with the setup's drift, and the settings."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from pathlib import Path
from streamlit.testing.v1 import AppTest

FL = Path(__file__).resolve().parent / "data" / "former_leaders.csv"
backup = FL.read_bytes() if FL.exists() else None


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value and "Bear spreads:" in m.value]
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
try:
    if FL.exists():
        FL.unlink()
    at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
    ok(at, "first run")
    print("intro:", "classic short" in md(at))
    at.text_area(key="bsp_fl_txt").set_value("ZD001, ZD002 ZD003").run(); ok(at, "fl text")
    at.button(key="bsp_fl_save").click().run(); ok(at, "fl save")
    print("former leaders file:", FL.exists(), "| rows:", sum(1 for _ in open(FL)) - 1 if FL.exists() else 0)
    at.button(key="bsp_build").click().run(); ok(at, "build list")
    print(f"list built {time.time() - t0:.0f}s | KPIs:", kpi(at, "Leaders in the last year"), kpi(at, "Topped now"), kpi(at, "Best edge"))
    SB = [d for d in frames(at) if "verdict" in d.columns and "db_follow" in d.columns]
    assert SB, [list(d.columns)[:6] for d in frames(at)]
    print("scoreboard:", SB[0][["verdict", "setup", "events", "er_date", "t_xs", "db_follow", "cr_follow"]].round(3).to_dict("records"))
    for sp in ("cycle", "mrv", "topped", "year"):
        at.selectbox(key="bsp_split").set_value(sp).run(); ok(at, sp)
    SB2 = [d for d in frames(at) if "verdict" in d.columns and "db_follow" in d.columns]
    print("split rows (year):", len(SB2[0]) if SB2 else 0)
    at.selectbox(key="bsp_split").set_value("none").run(); ok(at, "none")
    opts = at.selectbox(key="bsp_pick").options
    for o in opts[:3]:
        at.selectbox(key="bsp_pick").set_value(o).run(); ok(at, o)
    REC = [d for d in frames(at) if "outcome_txt" in d.columns and "db_follow" in d.columns]
    print("recent trades table:", len(REC[0]) if REC else 0)
    CAND = [d for d in frames(at) if "setup_label" in d.columns and "debit_legs" in d.columns]
    print("candidates:", CAND[0][["ticker", "setup_label", "signal_close", "stop_plan", "debit_legs", "db_est", "credit_legs", "cr_est"]].head(4).round(2).to_dict("records") if CAND else "none today")
    if CAND:
        at.button(key="bsp_live_go").click().run(); ok(at, "live")
        LV = [d for d in frames(at) if "spread" in d.columns and "strikes" in d.columns]
        print("chain-priced spreads:", LV[0][["spread", "strikes", "price", "max_loss", "edge", "pop"]].round(2).to_dict("records") if LV else None)
        if LV:
            at.button(key="bsp_sim_go").click().run(); ok(at, "sim")
            SIM = [d for d in frames(at) if "rule" in d.columns and "cvar5" in d.columns]
            print("simulated rules:", SIM[0][["rule", "er", "win", "days"]].round(2).to_dict("records") if SIM else None)
            at.radio(key="bsp_sim_struct").set_value("credit").run(); ok(at, "struct")
            at.button(key="bsp_sim_go").click().run(); ok(at, "sim call credit")
    # settings
    at.radio(key="bsp_h").set_value(10).run(); ok(at, "h10")
    print("stale-settings warning:", "Settings changed since the last build" in md(at))
    at.radio(key="bsp_mode").set_value("trigger").run(); ok(at, "trigger")
    at.radio(key="bsp_cc").set_value("entry").run(); ok(at, "cc entry")
    at.button(key="bsp_build").click().run(); ok(at, "rebuild h10")
    SB3 = [d for d in frames(at) if "verdict" in d.columns and "db_follow" in d.columns]
    print("10 sessions, trigger entry, call short over the entry:", SB3[0][["setup", "events", "er_date", "db_follow", "cr_follow"]].round(3).head(4).to_dict("records") if SB3 else None)
    at.radio(key="bsp_h").set_value(3).run()
    at.radio(key="bsp_uni").set_value("market").run(); ok(at, "market")
    at.button(key="bsp_build").click().run(); ok(at, "build market")
    SB4 = [d for d in frames(at) if "verdict" in d.columns and "db_follow" in d.columns]
    print("whole market, 3 sessions:", SB4[0][["setup", "events", "verdict"]].to_dict("records") if SB4 else None)
    print("guide:", any("What it's for" in x.value for x in at.markdown))
    print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
finally:
    if FL.exists():
        FL.unlink()
    if backup is not None:
        FL.write_bytes(backup)
