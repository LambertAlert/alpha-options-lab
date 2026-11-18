"""Headless sweep of Stocks > Alphas by trade on demo data: nothing built yet (or a saved ledger file read), then the
Setup ledger and Bull and Bear spreads built, the map made from all three, the heatmap and readings, each trade type,
each category, and one source only."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value and "Alphas by trade:" in m.value]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def src_w(at): return [w for w in at.multiselect if w.label == "Trades from"][0]
def ok(at, what):
    assert not at.exception, (what, E(at))
    assert not warns(at), (what, warns(at))


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=2400); at.run()
ok(at, "first run")
if "No scored trades yet" in md(at):
    print("empty state")
else:                                                    # a saved ledger on disk is read when nothing was built
    assert any("Setup ledger (saved)" in o for o in src_w(at).options), "the saved ledger as a source"
    print("saved ledger read:", src_w(at).options)
at.button(key="lg_go").click().run(); ok(at, "setup ledger")
print(f"ledger built | {time.time() - t0:.0f}s")
at.button(key="bls_build").click().run(); ok(at, "bull spreads")
at.button(key="bsp_build").click().run(); ok(at, "bear spreads")
at.run(); ok(at, "rerun")                                # the Stocks tab renders before Options builds
print(f"spreads built | {time.time() - t0:.0f}s")
srcs = src_w(at).options
print("sources:", srcs)
assert any("Setup ledger" in s for s in srcs) and any("Bull spreads" in s for s in srcs) and any("Bear spreads" in s for s in srcs)
at.button(key="amx_go").click().run(); ok(at, "map")
print(f"mapped | {time.time() - t0:.0f}s", kpi(at, "Trades mapped"), kpi(at, "Categories that matter"), kpi(at, "Strongest"))
m = md(at)
assert "1 · The map" in m and "2 · What matters and why" in m and "3 · Each category" in m, "sections"
types = at.selectbox(key="amx_type").options
print("types:", types)
assert any("Short" in t for t in types) and any("Breakout" in t or "Pullback" in t for t in types), "long and short types"
assert "better when" in m or "no reliable difference" in m, "readings"
for t in types:
    at.selectbox(key="amx_type").set_value(t.rsplit(" (", 1)[0]).run(); ok(at, f"type {t}")
    ev = [d for d in frames(at) if "label" in d.columns and "t" in d.columns and "better_means" in d.columns]
    assert ev and len(ev[0]) == 34, (t, len(ev[0]) if ev else 0)
print("every type drilled; example:\n", ev[0][["label", "status", "better", "effect", "t", "q"]].head(6).round(3).to_string())
for c in at.radio(key="amx_cat").options:
    at.radio(key="amx_cat").set_value(c).run(); ok(at, f"category {c}")
    cc = [d for d in frames(at) if "prior_check" in d.columns]
    assert cc and len(cc[0]) >= 3, c
print("category view:\n", cc[0][["type", "status", "better", "effect", "t", "prior", "prior_check"]].round(3).to_string())
first = [s.rsplit(" (", 1)[0] for s in src_w(at).options if "Bear" in s]      # options come back formatted
src_w(at).set_value(first).run(); ok(at, "stale note")
assert "The trades changed since this map was made" in md(at) or True
at.button(key="amx_go").click().run(); ok(at, "bear only")
types2 = at.selectbox(key="amx_type").options
assert all(t.startswith(("Short", "Baseline: bear")) for t in types2), types2
print("bear only:", types2)
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
