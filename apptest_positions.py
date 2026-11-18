"""Headless sweep of the Positions tab (demo data): example positions, the plan's actions, the continuation evidence,
the Brief's names as new trades, swaps, one position up close, settings, and saving to the Book file."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from pathlib import Path
from streamlit.testing.v1 import AppTest

BOOK = Path(__file__).resolve().parent / "data" / "book_positions.csv"
backup = BOOK.read_bytes() if BOOK.exists() else None
if BOOK.exists():
    BOOK.unlink()


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:200] for m in at.markdown if "warnbox" in m.value and "Positions:" in m.value]
def kpi(at, label):
    import re
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None


t0 = time.time()
try:
    at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
    assert not at.exception, E(at)
    assert not warns(at), warns(at)
    m = md(at)
    print("tab drawn:", "Positions: hold, trim or swap" in m, "| example note:", "example positions" in m)
    A = [d for d in frames(at) if "act" in d.columns and "plan_stop" in d.columns]
    print("actions:", A[0][["ticker", "act", "days", "open_r", "stop_now", "plan_stop"]].round(2).to_dict("records") if A else None)
    assert A and len(A[0]) >= 3
    print("to-do list:", [x.value[:300] for x in at.markdown if "bf-h'>To do" in x.value][:1])
    print("KPIs:", kpi(at, "Positions read"), kpi(at, "Open risk to your stops"), kpi(at, "Actions from the plan"))
    print("needs the ledger:", "Build the ledger with its current settings" in [b.label for b in at.button])
    at.button(key="pos_build").click().run(); assert not at.exception, E(at); assert not warns(at), warns(at)
    print(f"ledger built {time.time() - t0:.0f}s")
    CR = [d for d in frames(at) if "state" in d.columns and "er" in d.columns]
    print("hold from here:", CR[0][["ticker", "state", "er", "lo", "hi", "p_loss", "ess", "pool"]].round(3).to_dict("records") if CR else None)
    assert CR and CR[0]["er"].notna().all()
    print("swap KPIs:", kpi(at, "Weakest position"), kpi(at, "Best new name"), kpi(at, "Best swap"))
    NR = [d for d in frames(at) if "brief" in d.columns and "setup" in d.columns and "er" in d.columns]
    print("Brief names as new trades:", len(NR[0]) if NR else 0)
    SW = [d for d in frames(at) if "sell" in d.columns and "buy" in d.columns]
    print("swaps worth a look:", SW[0].round(3).head(3).to_dict("records") if SW else "none shown")
    print("up-close note:", any("Look-alike trades in the same state" in x.value for x in at.markdown))
    at.number_input(key="pos_h").set_value(40).run(); assert not at.exception, E(at); assert not warns(at), warns(at)
    CR2 = [d for d in frames(at) if "state" in d.columns and "er" in d.columns]
    print("40 sessions:", CR2[0]["er"].round(3).tolist() if CR2 else None)
    at.number_input(key="pos_cost").set_value(25.0).run(); assert not at.exception, E(at)
    sel = at.selectbox(key="pos_pick")
    sel.set_value(sel.options[-1]).run(); assert not at.exception, E(at); assert not warns(at), warns(at)
    print("picked:", at.selectbox(key="pos_pick").value)
    # the plan follows the Simulation's settings
    at.session_state["sim_trim_r"] = 3.0
    at.run(); assert not at.exception, E(at)
    A3 = [d for d in frames(at) if "act" in d.columns and "plan_stop" in d.columns]
    print("trim level at 3R:", A3[0][["ticker", "trim_lvl"]].round(2).to_dict("records")[:2] if A3 else None)
    at.session_state["sim_runner"] = "signals"
    at.session_state["sim_trim_r"] = 0.0
    at.run(); assert not at.exception, E(at)
    A4 = [d for d in frames(at) if "act" in d.columns and "plan_stop" in d.columns]
    print("no target, exit signals:", A4[0][["ticker", "act", "trim_lvl"]].to_dict("records")[:3] if A4 else None)
    assert A4 and A4[0]["trim_lvl"].isna().all()
    at.session_state["sim_runner"] = "ema21"
    at.session_state["sim_trim_r"] = 3.0
    at.run(); assert not at.exception, E(at)
    at.button(key="pos_save").click().run(); assert not at.exception, E(at)
    print("saved file:", BOOK.exists(), "| rows:", sum(1 for _ in open(BOOK)) - 1 if BOOK.exists() else 0)
    at2 = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at2.run()
    assert not at2.exception, E(at2)
    print("after saving, the example note is gone:", "example positions" not in md(at2),
          "| Book tab still draws:", any("Open positions: heat and stress" in x.value for x in at2.markdown))
    print("exceptions:", E(at), E(at2), f"| {time.time() - t0:.0f}s")
finally:
    if BOOK.exists():
        BOOK.unlink()
    if backup is not None:
        BOOK.write_bytes(backup)
