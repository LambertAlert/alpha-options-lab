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

os.environ["LAB_SOURCE"] = "massive"                 # the Massive key box, checked on the sidebar itself (no network)
os.environ["MASSIVE_API_KEY"] = "MASSIVE-SECRET-456"
seen = []
real_ti = L.st.sidebar.text_input
def spy(label, value="", *a, **k):
    seen.append((label, value))
    return real_ti(label, value, *a, **k)
L.st.sidebar.text_input = spy
try:
    cfg = L.sidebar()
except Exception as e:                               # later sidebar parts may need a running app; the key box comes first
    cfg = None
    print("sidebar stopped:", type(e).__name__)
finally:
    L.st.sidebar.text_input = real_ti
mk = [(lab, v) for lab, v in seen if "Massive key" in lab]
print("Massive key box:", mk)
assert mk and all(v == "" for _, v in mk), "the Massive key was put into a widget"
assert cfg is None or cfg.get("key") == "MASSIVE-SECRET-456", "the stored key is still used"
print(f"exceptions: [] | {time.time() - t0:.0f}s")
