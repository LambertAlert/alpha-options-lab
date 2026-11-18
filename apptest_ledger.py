"""Headless sweep of the ledger's new pieces: cost model, spread split, Deflated Sharpe, excursions, Expectancy."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest
import numpy as np


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]


def board(at):
    for d in frames(at):
        if "Deflated Sharpe" in d.columns and "Setup" in d.columns:
            return d.rename(columns={"Deflated Sharpe": "dsr", "P(Sharpe > 0)": "psr", "Setup": "setup", "Split": "split"})
    return None


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1200); at.run()
assert not at.exception, E(at)
scr = [d for d in frames(at) if "spread_bp" in d.columns]
print("screener spread column:", bool(scr), (scr[0]["spread_bp"].describe()[["count", "min", "50%", "max"]].round(0).to_dict() if scr else None))

at.button(key="lg_go").click().run(); assert not at.exception, E(at)
print("ledger built (flat)", f"{time.time()-t0:.0f}s")
b = board(at)
print("scoreboard has psr/dsr:", b is not None, None if b is None else b[["setup", "psr", "dsr"]].head(5).round(3).to_dict("records"))
import re
allt = md(at) + " ".join(str(getattr(c, "value", "")) for c in at.caption)
print("dsr note:", re.findall(r"luckiest of [\d,]+ trials.{0,60}", allt)[:1])
print("survive KPI:", "Survive deflation" in md(at))
d0 = b["dsr"].to_numpy(float)
at.number_input(key="lg_dsr_extra").set_value(500).run(); assert not at.exception, E(at)
d1 = board(at)["dsr"].to_numpy(float)
ok = np.isfinite(d0) & np.isfinite(d1)
print("500 extra variants lower every DSR:", bool(ok.any() and (d1[ok] <= d0[ok] + 1e-12).all()), f"median {np.nanmedian(d0):.3f} -> {np.nanmedian(d1):.3f}")

# drill into the first setup: excursions
dk = [w.key for w in at.selectbox if str(w.key).startswith("lg_drill_")]
print("drill keys:", dk)
if dk:
    sel = at.selectbox(key=dk[0])
    for opt in sel.options[:3]:
        sel = at.selectbox(key=dk[0])
        sel.set_value(sel.options[sel.options.index(opt)] if opt in sel.options else opt).run()
        assert not at.exception, E(at)
    m = md(at)
    print("excursions section:", "Excursions:" in m, "| edge ratio:", "edge ratio" in m.lower(),
          "| tables:", sum(1 for d in frames(at) if any(c in d.columns for c in ("stop_r", "target_r", "scale_r"))))

# spread cost model, then the spread split
at.radio(key="lg_cost_mode").set_value("spread").run(); assert not at.exception, E(at)
for m_ in ("ar", "cs", "avg"):
    at.selectbox(key="lg_spread_m").set_value(m_)
at.selectbox(key="lg_spread_m").set_value("ar")
at.button(key="lg_go").click().run(); assert not at.exception, E(at)
print("ledger built (spread)", f"{time.time()-t0:.0f}s", "| Rules KPI mentions spread:", "spread" in md(at).lower())
at.selectbox(key="lg_split").set_value("spread").run(); assert not at.exception, E(at)
labs = set()
for d in frames(at):
    for col in ("split", "Split"):
        if col in d.columns:
            labs |= set(map(str, d[col].unique()))
print("spread split buckets:", sorted(labs))
evs = [d for d in frames(at) if "cost_bp" in d.columns]
if evs:
    print("per-trade cost bp:", evs[0]["cost_bp"].describe()[["min", "50%", "max"]].round(1).to_dict())
at.selectbox(key="lg_split").set_value("none").run(); assert not at.exception, E(at)

# Expectancy & Kelly
m = md(at)
ex = [d for d in frames(at) if "Deflated Sharpe" in d.columns and "Kelly, shrunk" in d.columns]
print("expectancy table has dsr:", bool(ex), "| best tile shows Deflated Sharpe:", "Deflated Sharpe" in m)
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
