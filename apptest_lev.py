"""Headless sweep of Stocks > Leveraged on demo data: the settings, the KPIs, your names with a fund, the index and
sector funds, the tracking check, the plan, the full list's filters; the Screener's leveraged-fund column and filter;
the Brief's setup cards carrying the fund line."""
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
    bad = [m.value[:300] for m in at.markdown if "warnbox" in m.value and re.search(r"(Error|Exception|Leveraged): ", m.value)]
    assert not bad, (what, bad)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
for lab in ("Funds", "Single-stock funds", "Your names with a fund", "Using funds"):
    print(lab, "->", kpi(at, lab)); assert kpi(at, lab) is not None, lab
N = [d for d in frames(at) if "lev_long" in d.columns and "lev_long_dv" in d.columns and "ticker" in d.columns]
assert N and len(N[0]) >= 5, "your names with a fund"
print(N[0].head(8).round(3).to_string())
G = [d for d in frames(at) if "levers" in d.columns and "long_fund" in d.columns]
assert G and len(G[0]) >= 10, "index and sector funds"
print(G[0].head(8).round(2).to_string())
TR = [d for d in frames(at) if "beta" in d.columns and "gap" in d.columns]
assert TR and len(TR[0]) == 3, "the tracking check"
print(TR[0].round(3).to_string())
opts = at.selectbox(key="lev_pick").options
at.selectbox(key="lev_pick").set_value(opts[min(3, len(opts) - 1)]).run(); ok(at, "another fund")
for k in ("Stop in the stock", "Stop in the fund", "Capital for the same risk", "Drag"):
    assert kpi(at, k) is not None, k
at.selectbox(key="lev_pl").set_value(3.0).run(); ok(at, "3x plan")
print("capital for the same risk at 3x:", kpi(at, "Capital for the same risk"))
at.multiselect(key="lev_kinds").set_value(["single stock"]).run(); ok(at, "list: single stocks")
at.radio(key="lev_side").set_value("short").run(); ok(at, "list: inverse")
at.text_input(key="lev_q").input("nvda").run(); ok(at, "list: search")
Lst = [d for d in frames(at) if "under_label" in d.columns and "issuer" in d.columns]
assert Lst and set(Lst[0]["under"]) == {"NVDA"} and (Lst[0]["lev"] < 0).all(), "the filtered list"
print("NVDA inverse funds:", list(Lst[0]["ticker"]))
at.number_input(key="lev_min_dv").set_value(100.0).run(); ok(at, "a higher liquidity floor")
print("names with a fund at $100M+:", kpi(at, "Your names with a fund"))
at.number_input(key="lev_min_dv").set_value(5.0).run()
# the Screener
at.checkbox(key="sc_lev").check().run(); ok(at, "screener: has a fund")
S = [d for d in frames(at) if "lev_txt" in d.columns and "composite" in d.columns]
assert S and (S[0]["lev_txt"].fillna("") != "").all(), "screener filter"
print("screener names with a fund:", len(S[0]), list(S[0]["lev_txt"].head(5)))
at.checkbox(key="sc_lev").uncheck().run()
at.checkbox(key="lev_prefer").uncheck().run(); ok(at, "using funds off")
assert kpi(at, "Using funds") == "OFF"
at.checkbox(key="lev_prefer").check().run(); ok(at, "using funds on")
print("Brief cards with the fund line:", md(at).count("Leveraged: "))
print(f"exceptions: {E(at)} | {time.time() - t0:.0f}s")
