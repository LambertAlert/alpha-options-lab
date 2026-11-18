"""Checks for the Nov 9 review fixes outside the plinko: no API key in an HTTP error, the Pullback setups' trade type,
the ranker dropping candidates whose stop has traded, the bar store (a failed download retried, earlier phases
dropped), market holidays in the clock helpers, demo option bars fixed per contract and date, and the Positions plan
stop ratcheting like the ledger's.
Run: python test_review_fixes.py"""
import warnings
from datetime import date, datetime, timedelta
from unittest import mock

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import alpha_options_lab as L

PASS, FAIL = 0, []


def check(name, cond, info=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {info}")


print("HTTP errors")


class Resp:
    content = b"{}"

    def __init__(self, code):
        self.status_code, self.url = code, "https://api.example.com/x?apiKey=SECRET123"

    def raise_for_status(self):
        import requests
        raise requests.HTTPError(f"{self.status_code} Client Error for url: {self.url}", response=self)

    def json(self):
        return {"ok": 1}


for code in (400, 402, 422):
    with mock.patch.object(L.requests, "get", return_value=Resp(code)):
        try:
            L.http_json("https://api.example.com/x", {"apiKey": "SECRET123"})
            msg = "no error"
        except Exception as ex:
            msg = f"{type(ex).__name__}: {ex}"
    check(f"HTTP {code}: the error names the status and not the key", "SECRET123" not in msg and str(code) in msg, msg)
with mock.patch.object(L.requests, "get", return_value=Resp(200)):
    check("a 200 still returns the payload", L.http_json("https://api.example.com/x", {"apiKey": "k"}) == {"ok": 1})
with mock.patch.object(L.requests, "get", return_value=Resp(404)):
    check("a 404 is still None", L.http_json("https://api.example.com/x") is None)
with mock.patch.object(L.requests, "get", return_value=Resp(403)):
    try:
        L.http_json("https://api.example.com/x")
        ok_ = False
    except L.PlanError:
        ok_ = True
    check("a 403 is still a plan error", ok_)

print("Trade types")
check("every Pullback setup has a trade type", all(L.AM_TYPES.get(s) == "Rebound / oversold" for s in L.LG_SETUPS if s.startswith("pb:")))

print("Ranker candidates")
n = 300
idx = pd.bdate_range("2025-01-01", periods=n)
mk = lambda v: pd.DataFrame({"A": np.full(n, v), "B": np.full(n, v), "C": np.full(n, v)}, index=idx)
P = {"close": mk(100.0), "low": mk(99.5), "high": mk(100.5), "open": mk(100.0)}
P["low"] = P["low"].copy()
P["low"].loc[idx[-2], "A"] = 95.0                         # A traded through its stop the day after the signal
Cn = pd.DataFrame({"ticker": ["A", "B", "C", "ZZ"], "date": [idx[-3], idx[-3], idx[-1], idx[-3]],
                   "plan_risk_atr": [1.0, 1.0, 1.0, 1.0], "atr_pct": [2.0, 2.0, 2.0, 2.0]})
al = L.rk_alive(Cn, P)
check("a candidate whose stop has traded is dropped; the others stay", al.tolist() == [False, True, True, True], al.tolist())
check("with no price panel, nothing is dropped", L.rk_alive(Cn, None).all())

print("Bar store")
calls = {"n": 0}
good = pd.DataFrame({"open": [1.0] * 70, "high": [1.0] * 70, "low": [1.0] * 70, "close": [1.0] * 70, "volume": [1.0] * 70,
                     "vwap": [1.0] * 70}, index=pd.bdate_range("2025-01-01", periods=70))


def fake(tk, days, source, key):
    calls["n"] += 1
    return (None, "miss") if calls["n"] == 1 else (good, "yahoo")


L.clear_bar_store()
with mock.patch.object(L, "_fetch_one", side_effect=fake), mock.patch.object(L, "last_completed_session", return_value=date(2030, 1, 1)):
    b1, s1 = L.get_bars(["QQQQ"], 400, "yahoo", None, False)
    b2, _ = L.get_bars(["QQQQ"], 400, "yahoo", None, False)
    check("a failed download isn't fetched again straight away", "QQQQ" not in b1 and "QQQQ" not in b2 and calls["n"] == 1, calls["n"])
    with mock.patch.object(L, "BAR_RETRY_S", 0.0):
        b3, _ = L.get_bars(["QQQQ"], 400, "yahoo", None, False)
    check("and is tried again once the retry time has passed", "QQQQ" in b3 and calls["n"] == 2, calls["n"])
    st_ = L._bar_store()
    st_["bars"][("OLD", 400, "yahoo", ("1999-01-01", "post"))] = (good, "yahoo")
    L.get_bars(["QQQQ"], 400, "yahoo", None, False)
    check("bars from an earlier day or phase are dropped", not any(k[0] == "OLD" for k in st_["bars"]))
L.clear_bar_store()

print("Clock")
check("Thanksgiving 2026 and Christmas 2026 are holidays; the day after Thanksgiving isn't",
      L.is_market_holiday(date(2026, 11, 26)) and L.is_market_holiday(date(2026, 12, 25)) and not L.is_market_holiday(date(2026, 11, 27)))
ET = L._ET
with mock.patch.object(L, "now_et", return_value=datetime(2026, 11, 26, 18, 0, tzinfo=ET)):
    check("on Thanksgiving evening the last session is Wednesday", L.last_completed_session() == date(2026, 11, 25), L.last_completed_session())
    check("a holiday is 'post' all day", L.session_phase() == "post")
with mock.patch.object(L, "now_et", return_value=datetime(2026, 11, 27, 10, 0, tzinfo=ET)):
    check("Friday morning after Thanksgiving: still Wednesday, and intraday", L.last_completed_session() == date(2026, 11, 25)
          and L.session_phase() == "intra")
with mock.patch.object(L, "now_et", return_value=datetime(2026, 11, 9, 17, 0, tzinfo=ET)):
    check("an ordinary Monday after the close is its own session", L.last_completed_session() == date(2026, 11, 9))
check("the fallback offset follows daylight time", L.et_offset_hours(datetime(2026, 7, 1, 15)) == 4 and L.et_offset_hours(datetime(2026, 12, 1, 15)) == 5
      and L.et_offset_hours(datetime(2026, 3, 8, 6, 59)) == 5 and L.et_offset_hours(datetime(2026, 3, 8, 7, 0)) == 4
      and L.et_offset_hours(datetime(2026, 11, 1, 5, 59)) == 4 and L.et_offset_hours(datetime(2026, 11, 1, 6, 0)) == 5)

print("Demo option bars")
g = np.random.default_rng(3)
ix = pd.bdate_range("2026-01-05", periods=120)
Cc = pd.DataFrame({"XYZ": 100 * np.exp(np.cumsum(g.normal(0, 0.02, 120)))}, index=ix)
src = L.AuDemo(Cc)
exp = next(d for d in ix[60:] if d.weekday() == 4).date()
occ = L.au_occ("XYZ", exp, "call", 100.0)
a = src.bars(occ, (ix[30]).date(), exp)
b = src.bars(occ, (ix[45]).date(), exp)
common = a.index.intersection(b.index)
check("one contract asked for over two windows gives the same prints", len(common) > 3 and np.allclose(a.loc[common, ["vw", "c"]], b.loc[common, ["vw", "c"]])
      and set(b.index) == set(a.index[a.index >= ix[45]]), (len(a), len(b), len(common)))

print("Positions")
n = 120
ix = pd.bdate_range("2026-01-05", periods=n)
c = np.full(n, 100.0)
e = 60
c[e:e + 30] = 100 + np.arange(30) * 1.0                    # runs to 129, then drifts back
c[e + 30:] = 129 - np.arange(n - e - 30) * 0.3
h, lo = c + 0.5, c - 0.5
h[e + 20:e + 26] = c[e + 20:e + 26] + 6.0                  # a burst of wide bars lifts ATR late in the run
Pp = {"close": pd.DataFrame({"X": c}, index=ix), "high": pd.DataFrame({"X": h}, index=ix), "low": pd.DataFrame({"X": lo}, index=ix),
      "volume": pd.DataFrame({"X": np.full(n, 1e6)}, index=ix)}
plan = {**L.sim_plan_of({}), "runner": "chand"}
runner = next((k for k, v in L.SIM_RUNNER_SPEC.items() if v[0] == "chandelier"), None)
if runner is None:
    check("a chandelier runner exists to test", False, list(L.SIM_RUNNER_SPEC))
else:
    rules = L.sim_trade_rules({"mode": "next_open", "win": 1, "cap": 3.0, "trail_k": 3.0, "tgt": 2.0, "horizon": 10,
                               "sim_plan": {**L.sim_plan_of({}), "kind": "trim", "runner": runner}}, next(iter(L.LG_SETUPS)))
    pos = pd.DataFrame([{"ticker": "X", "shares": 100, "entry": 100.0, "stop": 98.0, "init_stop": 98.0, "trimmed": True,
                         "setup": "", "entry_date": ix[e].date().isoformat()}])
    S_ = L.pos_status(Pp, pos, rules).iloc[0]
    atr = L._mc_atr(Pp["high"], Pp["low"], Pp["close"], 14)["X"]
    hi_run = Pp["high"]["X"].iloc[e:].cummax()
    t_i = int(np.argmax(Pp["high"]["X"].iloc[e:].to_numpy() >= 100 + 2 * 2.0)) + e
    by_hand = max(100.0, float((hi_run - 3.0 * atr.iloc[e:]).iloc[t_i - e:].max()))
    latest_only = max(100.0, float(hi_run.iloc[-1] - 3.0 * atr.iloc[-1]))
    check("the chandelier plan stop ratchets bar by bar from the trim", abs(S_["plan_stop"] - by_hand) < 1e-9 and by_hand >= latest_only,
          (S_["plan_stop"], by_hand, latest_only))

print(f"\n{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
raise SystemExit(1 if FAIL else 0)
