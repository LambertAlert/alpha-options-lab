"""Headless sweep of the pricer audit (section 6) on Options > Bull and Bear spreads, demo data: build, run the audit
on the demo's known truth (IV = 1.30 x realized), read the level, the shape and the per-setup table, use the prints'
multiple, rebuild, and run the bear side."""
import os, re, tempfile, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
TMP = tempfile.mkdtemp(prefix="au_app_")
os.environ["LAB_OPT_BARS"] = os.path.join(TMP, "opt_bars")
os.environ["LAB_HESTON_FILE"] = os.path.join(TMP, "heston_fit.json")
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800); at.run(); ok(at, "first run")
at.button(key="bls_build").click().run(); ok(at, "build bull")
assert "Not run yet" in md(at)
at.number_input(key="bls_au_n").set_value(40).run()
at.button(key="bls_au_go").click().run(); ok(at, "audit")
lvl = kpi(at, "IV / realized, from the prints")
print(f"audit {time.time() - t0:.0f}s |", kpi(at, "Spreads matched"), lvl, kpi(at, "Bull call debit: model / prints"),
      kpi(at, "Bull put credit: model / prints"))
assert lvl and abs(float(lvl[0].rstrip("x")) - 1.30) < 0.03, "the audit finds the demo's 1.30x"
assert os.path.exists(os.path.join(TMP, "bull_audit_spreads.parquet"))
tb = [d for d in frames(at) if "v_flat" in d.columns and "bias_hs" in d.columns]
assert tb and len(tb[0]) >= 6, "the per-setup table"
print(tb[0][["setup", "spread", "n", "mkt", "flat", "v_flat", "hs", "v_hs"]].round(3).to_string())
print("verdict KPIs:", kpi(at, "Pricer too kind"), kpi(at, "Pricer too harsh"), kpi(at, "Too few to tell"))
assert "describes the past smiles better" in md(at)
at.button(key="bls_au_use").click().run(); ok(at, "use the prints' multiple")
assert abs(float(at.number_input(key="bls_ivm").value) - 1.30) < 1e-9, at.number_input(key="bls_ivm").value
assert "Settings changed since the last build" in md(at)
at.button(key="bls_build").click().run(); ok(at, "rebuild at 1.30")
at.button(key="bls_au_go").click().run(); ok(at, "audit again")
print("after the multiple:", kpi(at, "Bull call debit: model / prints"), kpi(at, "Pricer too kind"))
at.button(key="bsp_build").click().run(); ok(at, "build bear")
at.button(key="bsp_au_go").click().run(); ok(at, "bear audit")
print("bear:", kpi(at, "IV / realized, from the prints"), kpi(at, "Bear call credit: model / prints"))
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
