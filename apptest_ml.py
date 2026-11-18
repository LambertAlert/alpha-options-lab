"""Headless sweep of Stocks > Breakout model (ORB) and Stocks > Learned ranker on demo data: build the trades, train
and test (network and trees) with and without the alpha inputs, the alpha comparison, importance and PCA tables, both heads, today's breaks; train and test the ranker, every horizon of today's ranks."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from streamlit.testing.v1 import AppTest


def E(at): return [str(e.value)[:400] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)
def frames(at): return [d.value for d in at.dataframe if hasattr(d.value, "columns")]
def warns(at): return [m.value[:240] for m in at.markdown if "warnbox" in m.value
                       and ("Breakout model:" in m.value or "Learned ranker:" in m.value or "PyTorch isn" in m.value)]
def kpi(at, label):
    for m in at.markdown:
        if f"kpi-lbl'>{label}" in m.value:
            v = re.search(r"kpi-val'>([^<]*)<", m.value); s = re.search(r"kpi-sub'>([^<]*)<", m.value)
            return (v.group(1) if v else "", s.group(1) if s else "")
    return None
def ok(at, what):
    assert not at.exception, (what, E(at))
    assert not warns(at), (what, warns(at))


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=2400); at.run()
ok(at, "first run")
assert "Luk buys gappers" in md(at) and "The alpha composite averages" in md(at), "intros"
at.number_input(key="obx_years").set_value(2).run()
at.button(key="obx_build").click().run(); ok(at, "orb build")
base = [d for d in frames(at) if "intra_R" in d.columns and "swing_win" in d.columns]
assert base and len(base[0]) == 3, "the trade itself, per range"
print("orb base:\n", base[0].round(3).to_string(), f"| {time.time() - t0:.0f}s")
at.button(key="obx_train").click().run(); ok(at, "orb train")
sc = [d for d in frames(at) if "verdict" in d.columns and "auc_nn" in d.columns]
assert sc, "scoreboard with the network"
print(sc[0][["verdict", "m", "head", "trades", "R_all", "auc_nn", "R_nn", "t_nn", "auc_gbm", "R_gbm", "t_gbm"]].round(3).to_string(),
      f"| {time.time() - t0:.0f}s")
assert {"alphas", "alphas_best"} <= set(sc[0].columns), "the scoreboard says what the alphas did"
va = [d for d in frames(at) if "t_vs_base" in d.columns and "inputs" in d.columns]
assert va and {"break inputs only", "+ every alpha", "+ alpha components (PCA)", "+ the most informative alphas"} <= set(va[0]["inputs"]), "every input set"
print(va[0][["m", "inputs", "model", "status", "auc", "R", "t_vs_base", "q_vs_base"]].round(3).to_string())
im = [d for d in frames(at) if "input" in d.columns and any(c.startswith("auc_drop") for c in d.columns)]
assert im and len(im[0]) > 0 and im[0]["input"].str.contains("#").any(), "which alphas the models lean on"
print(im[0].head(6).round(4).to_string())
pc = [d for d in frames(at) if "loads on" in d.columns]
assert pc and len(pc[0]) >= 2, "how the alphas group"
print(pc[0].to_string())
ak = [kpi(at, f"Alphas, {m}-min intra") for m in (5, 15, 30)]
print("alpha KPIs:", ak)
assert all(k and k[0] in ("ADDS INFORMATION", "MAYBE", "NO DIFFERENCE", "WORSE") for k in ak), "an alpha verdict per range"
at.radio(key="obx_head").set_value("swing").run(); ok(at, "swing head")
assert [d for d in frames(at) if "t_vs_base" in d.columns], "swing alpha table"
at.button(key="obx_today").click().run(); ok(at, "orb today")
td = [d for d in frames(at) if "status" in d.columns and "m" in d.columns and "ticker" in d.columns]
assert td and len(td[0]) > 0, "today's breaks"
assert "alpha_composite" in td[0].columns and td[0]["alpha_composite"].notna().any(), "today's alpha composite"
print("today:", td[0]["status"].value_counts().to_dict(), [c for c in td[0].columns if c.startswith(("nn_", "gbm_", "best_", "alpha"))])
at.multiselect(key="obx_variants").set_value(["base", "pca"]).run(); ok(at, "two input sets")
at.button(key="obx_train").click().run(); ok(at, "orb train, base and PCA")
va2 = [d for d in frames(at) if "t_vs_base" in d.columns and "inputs" in d.columns]
assert va2 and set(va2[0]["inputs"]) == {"break inputs only", "+ alpha components (PCA)"}, "only the chosen sets"
print("base + PCA only:", va2[0][["m", "inputs", "model", "status"]].to_dict("records")[:4], f"| {time.time() - t0:.0f}s")
at.number_input(key="arx_years").set_value(3).run()
at.number_input(key="arx_top").set_value(200).run()
at.button(key="arx_go").click().run(); ok(at, "ranker")
tb = [d for d in frames(at) if "method" in d.columns and "t_ic" in d.columns]
assert tb and {"composite", "nn", "gbm", "ridge"} <= set(tb[0]["method"]), "every method"
print(tb[0][["horizon", "method", "ic", "t_ic", "sharpe", "turnover"]].round(3).to_string(), f"| {time.time() - t0:.0f}s")
vr = [d for d in frames(at) if "verdict" in d.columns and "horizon" in d.columns]
print("verdicts:", vr[0][["horizon", "verdict"]].to_dict("records") if vr else None)
for h in (5, 20, 10):
    at.radio(key="arx_h").set_value(h).run(); ok(at, f"h{h}")
print("exceptions:", E(at), f"| {time.time() - t0:.0f}s")
