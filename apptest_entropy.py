"""Headless check of leadership entropy: Group leaders sub-tab, ledger splits, Simulation indicator, ranker (demo data)."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest
E = lambda at: [str(e.value)[:500] for e in at.exception]
md = lambda at: " ".join(m.value for m in at.markdown)
frames = lambda at: [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def tile_vals(at, label):
    out = []
    for m in at.markdown:
        if ">" + label + "<" in m.value:
            v = re.findall(r"font-size:20px[^>]*>([^<]*)<", m.value); s_ = re.findall(r"font-size:11px'>([^<]*)<", m.value)
            out.append((v[0] if v else "", s_[-1] if s_ else ""))
    return out
t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1500); at.run()
assert not at.exception, E(at)
print("tiles:", tile_vals(at, "Effective leading groups"), tile_vals(at, "Leadership"), tile_vals(at, "Top 3 groups hold"),
      tile_vals(at, "Concentration"))
tabs = [d for d in frames(at) if "share_leaders" in d.columns]
print("where-the-leaders-sit table:", bool(tabs), tabs[0].head(3)[["group", "leaders", "share_leaders", "over"]].round(2).to_dict("records") if tabs else None)
at.button(key="ga_run_ent").click().run(); assert not at.exception, E(at)
print("edge tiles:", tile_vals(at, "Narrow leadership"), tile_vals(at, "Broad leadership"), tile_vals(at, "Narrow minus broad"))
reg = [d for d in frames(at) if "regime" in d.columns and "rule_trades" in d.columns]
print("regime table:", reg[0][["regime", "dates", "rule_trades", "diff", "t"]].round(2).to_dict("records") if reg else None)
print("Does it pay? shares the replay:", any("Rule minus rest" in m.value for m in at.markdown), f"{time.time()-t0:.0f}s")
for opt in ("Industry", "Theme"):
    pass
at.button(key="lg_go").click().run(); assert not at.exception, E(at)
print("ledger built", f"{time.time()-t0:.0f}s")
for sp in ("lead_conc", "ga_rule_lead"):
    at.selectbox(key="lg_split").set_value(sp).run(); assert not at.exception, (sp, E(at))
    labs = set()
    for d in frames(at):
        for col in ("split", "Split"):
            if col in d.columns:
                labs |= set(map(str, d[col].unique()))
    print(sp, "->", sorted(labs))
at.selectbox(key="lg_split").set_value("none").run()
opts = at.multiselect(key="sim_feats").options
print("simulation indicators include entropy:", [o for o in opts if "eadership" in o or "x leadership" in o])
at.multiselect(key="sim_feats").set_value(list(at.multiselect(key="sim_feats").value) + ["ga_x_lead", "lead_conc_pct"]).run()
assert not at.exception, E(at)
at.radio(key="sim_part").set_value("model").run()
at.number_input(key="sim_iters").set_value(300).run(); at.number_input(key="sim_warm").set_value(150).run()
at.button(key="sim_fit_go").click().run(); assert not at.exception, E(at)
coef = [d for d in frames(at) if "P(helps)" in d.columns or "p_pos" in d.columns]
c0 = coef[0] if coef else None
if c0 is not None:
    lab = "label" if "label" in c0.columns else "indicator"
    print("model coefficients:", c0[c0[lab].astype(str).str.contains("eadership")].round(3).to_dict("records"))
at.radio(key="sim_part").set_value("paths").run(); assert not at.exception, E(at)
at.button(key="rk_go").click().run(); print("ranker exceptions", E(at), f"{time.time()-t0:.0f}s")
print("total", f"{time.time()-t0:.0f}s", "exceptions", E(at))
