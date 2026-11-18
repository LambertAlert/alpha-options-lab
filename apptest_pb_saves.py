"""The lab saves what playbook.py reads: the Setup ledger's verdicts carry the source and the full parameters, and a
Bear or Bull spreads build writes its events, candidates and metadata. Demo data, headless."""
import json, os, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
from pathlib import Path
from streamlit.testing.v1 import AppTest
D = Path(__file__).resolve().parent / "data"
t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=2400); at.run()
assert not at.exception, [str(e.value)[:300] for e in at.exception]
at.button(key="lg_go").click().run()
assert not at.exception, [str(e.value)[:300] for e in at.exception]
vm = json.load(open(D / "setup_ledger_verdicts.json"))
assert vm.get("source") == "demo" and "prm_full" in vm and vm["prm_full"]["mode"] in ("next_open", "buy_stop"), vm.keys()
print("setup ledger verdicts:", vm["source"], sorted(vm["prm_full"])[:5], f"| {time.time() - t0:.0f}s")
for side, K in (("bear", "bsp_"), ("bull", "bls_")):
    at.button(key=f"{K}build").click().run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    meta = json.load(open(D / f"{side}_ledger_meta.json"))
    import pandas as pd
    ev = pd.read_parquet(D / f"{side}_ledger.parquet")
    cands = pd.read_parquet(D / f"{side}_candidates.parquet")
    assert meta["source"] == "demo" and len(ev) > 1000 and "db_follow" in ev and "universe" in ev, (side, meta)
    print(side, "saved:", len(ev), "events,", len(cands), "candidates,", meta["asof"], f"| {time.time() - t0:.0f}s")
print("exceptions:", [str(e.value)[:200] for e in at.exception], f"| {time.time() - t0:.0f}s")
