"""Headless sweep of Options > Debit screen on demo data: the screen, the freshness note, the spot source per name,
when each vertical's legs printed, and the switch that keeps or drops legs from an earlier session."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
assert not at.exception, E(at)
btn = next(b for b in at.button if b.label == "Screen bull call debits")
btn.click().run(); assert not at.exception, E(at)
m = md(at)
print("freshness note:", "Screened " in m and "Spot: " in m)
N = [d for d in frames(at) if "spot_src" in d.columns and "n_verticals" in d.columns]
assert N, [list(d.columns)[:8] for d in frames(at)]
print("names:", N[0][["ticker", "spot", "spot_src", "spot_time", "n_verticals"]].head(5).to_dict("records"))
V = [d for d in frames(at) if "long_strike" in d.columns and "printed" in d.columns]
assert V and "prior_session" in V[0].columns
print("verticals:", len(V[0]), "| prior-session legs:", int(V[0]["prior_session"].sum()))
at.checkbox(key="deb_fresh").set_value(False).run(); assert not at.exception, E(at)
next(b for b in at.button if b.label == "Screen bull call debits").click().run(); assert not at.exception, E(at)
print("kept-and-flagged note:", "kept and flagged" in md(at) or "Latest session" not in md(at))
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
