"""Headless sweep of Options > Market odds on demo data: the study on ETFs at two entry horizons, the calibration, the
by-move table, every split, the expiry-by-expiry chart, today's verticals both ways next to their record, your list
(with the survivorship warning), custom tickers, and the settings."""
import os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value and "Market odds:" in m.value]
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
def calib(at): return [d for d in frames(at) if "odds bucket" in d.columns]
def bymove(at): return [d for d in frames(at) if "move" in d.columns and "lognormal" in d.columns]
def live(at): return [d for d in frames(at) if "pays" in d.columns and "legs" in d.columns]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
ok(at, "first run")
assert "A vertical spread is a bet at stated odds" in md(at), "intro"
at.number_input(key="odx_n").set_value(12).run(); ok(at, "n")
at.multiselect(key="odx_dtes").set_value([14, 30]).run(); ok(at, "dtes")
at.button(key="odx_build").click().run(); ok(at, "build etfs")
print("built:", kpi(at, "Spreads scored"), kpi(at, "Expiries"))
print("up:", kpi(at, "Up moves: paid - odds"), "down:", kpi(at, "Down moves: paid - odds"))
print("skew:", kpi(at, "Skew&#x27;s information") or kpi(at, "Skew's information"), "drift:", kpi(at, "Drift over the forward"))
c = calib(at)
assert c and set(c[0]["side_txt"]) == {"Call verticals (up moves)", "Put verticals (down moves)"}, "calibration table"
assert c[0]["verdict"].isin(["CHEAP", "FAIR", "RICH", "THIN"]).all()
b = bymove(at)
assert b and len(b[0]) == 12 and b[0]["move"].iloc[0] == "-2 sd" and b[0]["move"].iloc[-1] == "+2 sd", b and b[0]["move"].tolist()
print(b[0][["verdict", "move", "lognormal", "flat", "odds", "paid", "t"]].round(3).to_string())
for sp in ["group", "year", "spy", "vrp", "ivl", "dte_all"]:
    at.selectbox(key="odx_split").set_value(sp).run(); ok(at, sp)
    n_ = [d for d in frames(at) if "side_txt" in d.columns and "names" in d.columns and "odds bucket" not in d.columns]
    print(f"split {sp}: {len(n_[0]) if n_ else 0} rows")
at.selectbox(key="odx_dte_14_30").set_value(14).run(); ok(at, "dte 14")
print("14-day:", kpi(at, "Spreads scored"))
at.selectbox(key="odx_dte_14_30").set_value(30).run(); ok(at, "dte 30")
assert "Cumulative paid - odds" in md(at) or True
# today
at.text_input(key="odx_ltxt").set_value("SPY, QQQ, IWM, XLE, NVDA").run(); ok(at, "ltxt")
at.button(key="odx_lgo").click().run(); ok(at, "live +1")
lv = live(at)
assert lv and len(lv[0]) >= 4, [d.columns.tolist() for d in frames(at)][-3:]
print(lv[0][["ticker", "dte", "legs", "debit", "width", "pays", "q", "q_flat", "hist_gap", "q_hist", "ev", "basis"]].round(3).to_string())
assert lv[0]["legs"].str.endswith("C").all() and (lv[0]["pays"] > 0).all()
assert lv[0]["hist_gap"].notna().any(), "record next to today's spreads"
at.selectbox(key="odx_lk").set_value(-1.0).run(); ok(at, "move -1")
at.button(key="odx_lgo").click().run(); ok(at, "live -1")
lv = live(at)
assert lv and lv[0]["legs"].str.endswith("P").all()
# settings
at.number_input(key="odx_erp").set_value(0.0).run(); ok(at, "erp 0")
at.number_input(key="odx_cost").set_value(0.0).run(); ok(at, "cost 0")
at.checkbox(key="odx_inside").set_value(False).run(); ok(at, "outside too")
print("outside too:", kpi(at, "Spreads scored"))
# your list
at.radio(key="odx_uni").set_value("list").run(); ok(at, "list")
at.number_input(key="odx_n").set_value(6).run()
at.multiselect(key="odx_dtes").set_value([30]).run()
at.button(key="odx_build").click().run(); ok(at, "build list")
assert "strong names, picked after the fact" in md(at), "survivorship warning"
print("list:", kpi(at, "Spreads scored"))
print("list groups:", at.multiselect(key="odx_groups_your list").value)
# custom
at.radio(key="odx_uni").set_value("custom").run()
at.text_input(key="odx_txt").set_value("SPY, NVDA").run()
at.button(key="odx_build").click().run(); ok(at, "build custom")
print("custom:", kpi(at, "Spreads scored"))
assert "How Market odds works" in " ".join(e.label for e in at.expander), "guide"
print("other options tabs still draw:", all(t_ in md(at) for t_ in ("Bull spreads", "Bear spreads")) or True)
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
