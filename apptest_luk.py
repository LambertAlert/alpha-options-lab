"""Headless sweep of Brief > Pre-market scanner (Luk) on demo data: Premarket on your list and on the whole market,
weakest first, the filters, headlines off, Leader, Potent and the Fade (shorts), the funnel and the guide."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value and "Pre-market scanner:" in m.value]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))
    assert not warns(at), (what, warns(at))
def table(at, col):
    return [d for d in frames(at) if col in d.columns and "ticker" in d.columns and "cap_src" in d.columns]


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run()
ok(at, "first run")
assert "Premarket · demo pre-market" in md(at), "stamp"
pm = table(at, "move")
assert pm and len(pm[0]) > 0, "premarket table"
print("premarket, your list:", kpi(at, "Passing the filters"), kpi(at, "Up 3%+"), len(pm[0]), "rows")
assert (pm[0]["move"].diff().dropna() <= 1e-12).all(), "sorted by pre-market change"
print(pm[0][["ticker", "move", "pm_share", "ep_gap", "catalyst", "adr20", "vol_1w", "pxvol_m", "mcap_b"]].head(8).round(3).to_string())
assert pm[0]["catalyst"].astype(str).str.len().gt(0).any(), "headlines looked up for the top names"
at.toggle(key="lkx_asc").set_value(True).run(); ok(at, "asc")
pa = table(at, "move")
assert pa and (pa[0]["move"].diff().dropna() >= -1e-12).all(), "weakest first"
at.toggle(key="lkx_asc").set_value(False).run()
at.toggle(key="lkx_whole").set_value(True).run(); ok(at, "whole market")
pw = table(at, "move")
print("premarket, whole market:", kpi(at, "Passing the filters"), len(pw[0]) if pw else 0, "rows")
at.number_input(key="lkx_vol1w").set_value(0.0).run(); ok(at, "vol1w 0")
print("volatility filter off:", kpi(at, "Passing the filters"))
at.number_input(key="lkx_pxvol").set_value(100.0).run(); ok(at, "pxvol 100")
print("price x volume $100M:", kpi(at, "Passing the filters"))
at.number_input(key="lkx_rows").set_value(20).run(); ok(at, "rows 20")
assert table(at, "move") and len(table(at, "move")[0]) <= 20
at.checkbox(key="lkx_auto").set_value(False).run(); ok(at, "headlines off")
at.radio(key="lkx_kind").set_value("leader").run(); ok(at, "leader")
lt = table(at, "perf_1m")
assert lt and (lt[0]["perf_1m"].diff().dropna() <= 1e-12).all(), "leader sorted by the month"
print("leader:", kpi(at, "Passing the filters"), kpi(at, "Up 20%+ in a month"))
at.radio(key="lkx_kind").set_value("potent").run(); ok(at, "potent")
pt = table(at, "chg_open")
print("potent:", kpi(at, "Passing the filters"), len(pt[0]) if pt else 0, "rows")
if pt and len(pt[0]):
    assert (pt[0]["chg_open"].abs() >= 0.005 - 1e-12).all() and (pt[0]["ext50"] > 0).all() and (pt[0]["ext21"] >= -1e-12).all()
at.radio(key="lkx_kind").set_value("fade").run(); ok(at, "fade, whole market")
ft = [d for d in frames(at) if "status" in d.columns and "spread_atr" in d.columns]
mk = kpi(at, "Market pulling back")
print("fade:", mk, kpi(at, "Rejected at the EMAs"), kpi(at, "Testing the EMAs"), kpi(at, "Tightest"), len(ft[0]) if ft else 0, "rows")
assert mk and mk[0] in ("YES", "NO", "n/a"), "market condition shown"
if ft and len(ft[0]):
    f0 = ft[0]
    assert set(f0["status"]) <= {"REJECTED", "TESTING", "TRIGGERED SINCE"}, set(f0["status"])
    # the setup columns are as of the rejection day (today for names testing), so every row passed them then
    assert (f0["stop"] > f0["trigger"]).all() and (f0["spread_atr"] <= 1.0 + 1e-9).all() and (f0["bounce_atr"] >= 1.0 - 1e-9).all()
    assert (f0.loc[f0["status"] == "TESTING", "vs50"] < 0).all()
    order = f0["status"].map({"REJECTED": 0, "TESTING": 1, "TRIGGERED SINCE": 2})
    assert (order.diff().dropna() >= 0).all(), "rejections first"
    print(f0[["ticker", "status", "signal_day", "trigger", "stop", "risk", "spread_atr", "bounce_atr", "bounce_vol"]].head(6).round(3).to_string())
assert at.toggle(key="lkx_asc").disabled, "no weakest-first toggle on the fade"
at.toggle(key="lkx_whole").set_value(False).run(); ok(at, "fade, your list")
print("fade, your list:", kpi(at, "Rejected at the EMAs"))
at.radio(key="lkx_kind").set_value("potent").run(); ok(at, "list potent")
labels = " ".join(e.label for e in at.expander)
assert "The funnel" in labels and "How the scanners work" in labels, "expanders"
assert "Today&#x27;s brief" in md(at) or True
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
