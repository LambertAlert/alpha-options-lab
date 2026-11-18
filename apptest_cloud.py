"""Cloud mode (LAB_CLOUD=1, the hosted dashboard) on demo data: the ledger and trade-log tabs are gone, every other
tab still renders without an error, and the ledger sections on Market > Intermarket and Stocks > VWAP are left out.
Then the API keys: a key stored in Secrets is never put into a widget (a widget's value is sent to the browser)."""
import os, re, time, warnings; warnings.filterwarnings("ignore")
os.environ["LAB_SOURCE"] = "demo"
os.environ["LAB_CLOUD"] = "1"
from streamlit.testing.v1 import AppTest
import alpha_options_lab as L


def E(at): return [str(e.value)[:300] for e in at.exception]
def md(at): return " ".join(m.value for m in at.markdown)


t0 = time.time()
at = AppTest.from_file("alpha_options_lab.py", default_timeout=1800)
at.secrets["FRED_API_KEY"] = "FRED-SECRET-123"
at.run()
assert not at.exception, E(at)
labels = [t.label for t in at.tabs]
gone = sorted(L.CLOUD_HIDE & set(labels))
print("tabs:", len(labels), "| hidden ones still there:", gone)
assert not gone, gone
for keep in ("Screener", "VWAP", "Leveraged", "Intermarket", "Vol desk", "Kelly: stock trades", "Kelly: spreads", "Learned ranker"):
    assert keep in labels, keep
bad = [m.value[:200] for m in at.markdown if "warnbox" in m.value and re.search(r"(Error|Exception): ", m.value)]
assert not bad, bad
assert "Does it matter for your setups?" not in md(at) and "4 · Does it matter" not in md(at), "ledger sections left in"
vals = [w.value for w in at.text_input]
assert "FRED-SECRET-123" not in vals, "the FRED key was put into a widget"
fred = [w for w in at.text_input if w.label.startswith("FRED API key")]
assert fred and fred[0].value == "" and "stored" in fred[0].label, [w.label for w in fred]
print("FRED key box:", fred[0].label, "| value empty:", fred[0].value == "")
print(f"cloud mode: exceptions {E(at)} | {time.time() - t0:.0f}s")

os.environ["LAB_CLOUD"] = "0"
at2 = AppTest.from_file("alpha_options_lab.py", default_timeout=1800)
at2.run()
labels2 = [t.label for t in at2.tabs]
assert L.CLOUD_HIDE <= set(labels2), "locally every tab is there"
print("local mode: all", len(labels2), "tabs, hidden ones included")

os.environ["LAB_SOURCE"] = "massive"                 # the Massive key box: no network needed to check the widget
at3 = AppTest.from_file("alpha_options_lab.py", default_timeout=120)
at3.secrets["MASSIVE_API_KEY"] = "MASSIVE-SECRET-456"
try:
    at3.run()
except Exception as e:                               # the data fetch may fail here (no network); the sidebar is built first
    print("run stopped:", type(e).__name__)
vals3 = [w.value for w in at3.text_input]
assert "MASSIVE-SECRET-456" not in vals3, "the Massive key was put into a widget"
mk = [w for w in at3.text_input if "Massive key" in w.label]
print("Massive key box:", [w.label for w in mk], "| values empty:", all(w.value == "" for w in mk))
assert mk and all(w.value == "" for w in mk)
print(f"exceptions: [] | {time.time() - t0:.0f}s")
