"""Headless sweep of the Heston pricer on Options > Bull and Bear spreads (demo data): build under the fixed skew, fit
Heston to the demo chains, read the smiles and the per-name errors, re-price the ledger under Heston and compare,
then switch the pricer to Heston, rebuild, and compare back."""
import os, re, tempfile, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
TMP = tempfile.mkdtemp(prefix="hs_app_")
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
print(f"bull built {time.time() - t0:.0f}s |", kpi(at, "This build priced with"), kpi(at, "Heston fit"))
assert kpi(at, "This build priced with")[0] == "fixed skew"
assert "Not fitted yet" in md(at)
at.number_input(key="bls_hs_n").set_value(6).run()
at.button(key="bls_hs_fit").click().run(); ok(at, "fit")
print(f"fitted {time.time() - t0:.0f}s |", kpi(at, "Heston fit"), kpi(at, "rho (stock-vol correlation)"), kpi(at, "vol of variance"),
      kpi(at, "Chain IV / realized"))
assert kpi(at, "Heston fit")[0] not in ("not fitted", "")
ft = [d for d in frames(at) if "err_flat" in d.columns and "err_hs" in d.columns]
assert ft and len(ft[0]) >= 4, "the per-name fit table"
print(ft[0][["sym", "n", "rmse", "err_flat", "err_hs", "rho", "xi"]].round(3).to_string())
assert "Smile error at each name" in md(at)
sel = at.selectbox(key="bls_hs_pick")
sel.set_value(sel.options[-1]).run(); ok(at, "another smile")
at.button(key="bls_hs_cmp").click().run(); ok(at, "compare")
print("compare:", kpi(at, "Spread answers that change"), kpi(at, "Bull call debit: Heston / fixed skew"),
      kpi(at, "Bull put credit: Heston / fixed skew"), kpi(at, "Clear the bar, both pricers"))
ct = [d for d in frames(at) if "chg_db" in d.columns]
assert ct and {"db_follow_flat", "db_follow_heston", "cr_follow_flat", "cr_follow_heston"} <= set(ct[0].columns)
print(ct[0][["setup", "verdict", "db_follow_flat", "db_follow_heston", "cr_follow_flat", "cr_follow_heston", "chg_db", "chg_cr"]].round(3).to_string())
# switch to Heston and rebuild
at.radio(key="bls_pricer").set_value("heston").run(); ok(at, "pricer heston")
assert "Settings changed since the last build" in md(at)
t1 = time.time()
at.button(key="bls_build").click().run(); ok(at, "rebuild heston")
print(f"heston rebuild {time.time() - t1:.0f}s |", kpi(at, "This build priced with"))
assert kpi(at, "This build priced with")[0] == "Heston"
at.button(key="bls_hs_cmp").click().run(); ok(at, "compare back")
ct2 = [d for d in frames(at) if "chg_db" in d.columns]
assert ct2 and abs(ct2[0]["db_follow_heston"].astype(float).sum() - ct[0]["db_follow_heston"].astype(float).sum()) < 1e-3, \
    "re-priced under Heston == built under Heston"
print("compare back: same Heston column as the re-price:", True)
# the bear side reads the same saved fit
at.button(key="bsp_build").click().run(); ok(at, "build bear")
print("bear:", kpi(at, "Heston fit"))
at.button(key="bsp_hs_cmp").click().run(); ok(at, "bear compare")
print("bear compare:", kpi(at, "Spread answers that change"), kpi(at, "Bear call credit: Heston / fixed skew"))
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
