"""Planted-case tests for the Simulation's trim-and-trail exits (lg_label's trim options, the plan rules, relabeling
the ledger, the new path statistics). Run: python test_trim_exits.py"""
import sys, warnings
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


def bars(rows, pre=30):
    """One name: `pre` flat bars at 100, then the planted (open, high, low, close) rows. ATR is fixed at 3."""
    flat = [(100.0, 100.5, 99.5, 100.0)] * pre
    a = np.array(flat + list(rows), float)
    O, H, Lo, C = (a[:, k][:, None] for k in range(4))
    return O, H, Lo, C, np.full_like(C, 3.0), pre - 1          # the signal is the last flat bar


def lab(rows, lvl=95.0, tgt=2.0, hz=0, ma=None, kind="chandelier", trail=False, **kw):
    O, H, Lo, C, A, i0 = bars(rows)
    if ma is not None:
        ma = np.r_[np.full(i0 + 1, np.nan), np.asarray(ma, float)][:, None]
    out = L.lg_label(O, H, Lo, C, A, np.array([i0]), np.array([0]), np.array([lvl]), "next_open", 1, tgt, hz, 3.0, 0.5,
                     0.0, trail=trail, trail_kind=kind, trail_k=3.0, ma=ma, mark_open=True, **kw)
    return {k: (v[0] if hasattr(v, "__len__") else v) for k, v in out.items()}


T3 = dict(trim_frac=1 / 3, trim_stop_r=0.0, trail_from="trim")
print("Trim at the target, stop to breakeven")
# entry 100 (next open), stop 95 -> R = 5, 2R target = 110
path = [(100, 104, 99, 103), (103, 111, 102, 109), (108, 108.5, 99.5, 101), (101, 102, 100.5, 101)]
x = lab(path, **T3)                                    # no trail: the breakeven stop alone
check("trims a third at 110", bool(x["trimmed"]) and x["trim_px"] == 110.0, (x["trimmed"], x["trim_px"]))
check("the rest stops at breakeven the next bar it trades through", x["exit"] == 100.0 and x["outcome"] == 3,
      (x["exit"], x["outcome"]))
check("R = 1/3 x 2R + 2/3 x 0", abs(x["r"] - 2 / 3) < 1e-12, x["r"])
check("return blends the two exits", abs(x["ret"] - (110 / 100 - 1) / 3) < 1e-12, x["ret"])
y = lab(path)
check("without a trim the same path exits whole at the target", y["exit"] == 110.0 and y["outcome"] == 0 and abs(y["r"] - 2) < 1e-12)
z = lab(path, trim_frac=1.0)
check("trim_frac 1 is the old full target", z["exit"] == 110.0 and z["outcome"] == 0 and not z["trimmed"])
lk = lab(path, trim_frac=1 / 3, trim_stop_r=0.5, trail_from="trim")
cx = lab(path, trail=True, kind="chandelier", **T3)
check("with a chandelier the rest's stop is the higher of breakeven and 111 - 3 x 3", cx["exit"] == 102.0, cx["exit"])
check("+0.5R lock: the rest exits at 102.5", lk["exit"] == 102.5 and abs(lk["r"] - (2 / 3 + 2 / 3 * 0.5)) < 1e-12,
      (lk["exit"], lk["r"]))
kp = lab(path, trim_frac=1 / 3, trim_stop_r=np.nan, trail_from="trim")
check("leave the stop: the rest survives the dip to 99.5", kp["exit"] != 100.0 and kp["outcome"] == 4, (kp["exit"], kp["outcome"]))
gap = [(100, 104, 99, 103), (113, 115, 112, 114), (114, 114.5, 99, 100)]
g = lab(gap, trail=True, **T3)
check("gap over the target: the trim fills at the open", g["trim_px"] == 113.0, g["trim_px"])
both = [(100, 111, 94, 100)]
b = lab(both, trail=True, **T3)
check("target and stop in one bar: the stop comes first, no trim", not b["trimmed"] and b["outcome"] == 1 and abs(b["r"] + 1) < 1e-12)

print("The rest runs on a moving average")
run = [(100, 104, 99, 103), (103, 111, 102, 109), (109, 113, 108, 112), (112, 113, 103, 104),
       (104, 107, 103.5, 106), (106, 106.5, 103, 104), (104, 104.5, 102, 103), (103, 103.5, 101, 102)]
ma = [101, 102, 103, 105, 105, 105, 105, 105]
m1 = lab(run, ma=ma, kind="ma", trail=True, **T3)
check("one close under the average: out at 104 on day 4", m1["exit"] == 104.0 and m1["outcome"] == 3 and m1["hold"] == 4,
      (m1["exit"], m1["hold"]))
m2 = lab(run, ma=ma, kind="ma", trail=True, ma_closes=2, **T3)
check("two closes in a row: day 4 alone doesn't do it, days 6-7 do (out at 103)", m2["exit"] == 103.0 and m2["hold"] == 7,
      (m2["exit"], m2["hold"]))
pre = [(100, 104, 99, 101), (101, 105, 100.5, 102), (102, 111, 101, 110), (110, 111, 108, 109)]
m3 = lab(pre, ma=[103, 103, 103, 112], kind="ma", trail=True, **T3)
check("before the trim a close under the average doesn't exit", bool(m3["trimmed"]) and m3["hold"] == 4, (m3["trimmed"], m3["hold"]))
m4 = lab(pre, ma=[103, 103, 103, 112], kind="ma", trail=True)
check("the ledger's average exit (from entry) does exit on day 1", m4["hold"] == 1 and m4["outcome"] == 3, (m4["hold"], m4["outcome"]))
ch = [(100, 104, 99, 103), (103, 111, 102, 110), (110, 125, 109, 124), (124, 124.5, 115, 116)]
c1 = lab(ch, trail=True, kind="chandelier", **T3)
check("chandelier after the trim: 125 - 3 x 3 = 116 stops the rest", c1["exit"] == 116.0, c1["exit"])
c0 = lab([(100, 108, 99, 101), (101, 101.5, 96.5, 97)], trail=True, kind="chandelier", trim_frac=1 / 3, trail_from="trim")
ce = lab([(100, 108, 99, 101), (101, 101.5, 96.5, 97)], trail=True, kind="chandelier")
check("the ledger's chandelier (from entry) does: out at 108 - 9 = 99", ce["exit"] == 99.0, ce["exit"])
check("chandelier from the trim doesn't ratchet before it", c0["outcome"] == 4, (c0["exit"], c0["outcome"]))

print("Shorter losers, longer winners")
slow = [(100, 101, 98.5, 99), (99, 100, 97.5, 98), (98, 100.2, 97.6, 99.5), (99.5, 100, 96, 97)]
f3 = lab(slow, fail_n=3, fail_r=0.0)
check("not working by session 3: cut at that close", f3["outcome"] == 5 and f3["exit"] == 99.5 and f3["hold"] == 3,
      (f3["outcome"], f3["exit"], f3["hold"]))
check("cut costs -0.1R instead of riding to the stop", abs(f3["r"] + 0.1) < 1e-12, f3["r"])
f0 = lab(slow)
check("without the cut it is still open after 4 sessions", f0["outcome"] == 4 and f0["hold"] == 4)
fr = lab(slow, fail_n=3, fail_r=-0.5)
check("a -0.5R threshold lets 99.5 (-0.1R) live", fr["outcome"] != 5 or fr["hold"] > 3, (fr["outcome"], fr["hold"]))
late = [(100, 101, 99.2, 100.5), (100.5, 101, 99.8, 100.4), (100.4, 101, 100.1, 100.6), (100.6, 101, 99, 99.4),
        (99.4, 100, 98.5, 99)]
o1 = lab(late, fail_n=3, fail_r=0.0, fail_once=True)
o2 = lab(late, fail_n=3, fail_r=0.0)
check("once: above the entry at session 3, so a later dip under it isn't cut", o1["outcome"] == 4 and o1["hold"] == 5,
      (o1["outcome"], o1["hold"]))
check("every close: the dip under the entry on session 4 is cut", o2["outcome"] == 5 and o2["hold"] == 4 and o2["exit"] == 99.4,
      (o2["outcome"], o2["hold"], o2["exit"]))
o3 = lab(slow, fail_n=3, fail_r=0.0, fail_once=True)
check("once: under the entry at session 3 is cut there", o3["outcome"] == 5 and o3["hold"] == 3)
ok_ = lab([(100, 104, 99, 103), (103, 111, 102, 109), (109, 109.5, 101, 101.5), (101.5, 102, 100.5, 101)],
          fail_n=2, fail_r=0.5, trail=True, **T3)
check("trimmed trades are never cut", ok_["outcome"] != 5, ok_["outcome"])
be = lab([(100, 105.5, 99, 104), (104, 104.5, 99, 100)], be_r=1.0)
check("breakeven at +1R before the trim: out at 100 for 0R", be["exit"] == 100.0 and abs(be["r"]) < 1e-12 and be["outcome"] == 3)
hz_rows = [(100, 104, 99, 103), (103, 111, 102, 109), (109, 112, 108, 111), (111, 114, 110, 113), (113, 116, 112, 115)]
h1 = lab(hz_rows, hz=3, trail=True, **T3)
check("a trimmed winner outlives the 3-session limit", h1["hold"] == 5 and h1["outcome"] == 4, (h1["hold"], h1["outcome"]))
h2 = lab([(100, 104, 99, 103), (103, 105, 102, 104), (104, 106, 103, 105), (105, 107, 104, 106)], hz=3, trail=True, **T3)
check("an untrimmed trade still ends at the limit", h2["hold"] == 3 and h2["outcome"] == 2, (h2["hold"], h2["outcome"]))

print("The plan's rules")
prm = {"mode": "next_open", "win": 1, "tgt": 2.0, "horizon": 10, "cap": 3.0, "cost": 10.0, "tl_mode": "family",
       "exit_mode": "family", "trail": "chandelier", "trail_k": 3.0, "trail_ma": 21}
sid = next(s_ for s_, v_ in L.LG_SETUPS.items() if v_[0] == "MACD" and s_ not in L.RK_SKIP)
led = L.sim_trade_rules(prm, sid)
check("no plan: the ledger's rules (MACD: 2R target, 10 sessions)", led["plan"] == "ledger" and led["tgt"] == 2.0
      and led["tlimit"] == 10 and led["trim"] == 0.0)
ss = dict(L.SIM_DEFAULTS)
pl = L.sim_plan_of(ss)
tr = L.sim_trade_rules({**prm, "sim_plan": pl}, sid)
check("defaults: trim a third at 2R, breakeven, 21-day EMA, a time stop at session 5 under the entry",
      tr["plan"] == "trim" and abs(tr["trim"] - 1 / 3) < 1e-12 and tr["tgt"] == 2.0 and tr["trim_stop_r"] == 0.0
      and tr["kind"] == "ma" and tr["trail_ma"] == 21 and tr["ma_type"] == "ema" and tr["fail_n"] == 5
      and tr["fail_r"] == 0.0 and tr["fail_once"]
      and tr["tlimit"] == 0 and tr["trail_from"] == "trim", tr)
check("the plan is the same for every setup", L.sim_trade_rules({**prm, "sim_plan": pl}, "base:uptrend")["tgt"] == tr["tgt"])
check("the plan reads as a sentence", "sell 1/3 at 2R" in L.sim_plan_txt(tr) and "a close under the 21-day EMA" in L.sim_plan_txt(tr)
      and "closes under the entry at session 5 is cut there" in L.sim_plan_txt(tr),
      L.sim_plan_txt(tr))
emaP = L.sim_ma_panel(pd.DataFrame({"a": np.arange(60, dtype=float)}), tr)
check("EMA panel for the runner", emaP is not None and np.isnan(emaP[19, 0]) and np.isfinite(emaP[20, 0]))

print("Stats and the stunted-winner check on simulated paths")
rng = np.random.default_rng(5)
m, Hn = 400, 90
drift = np.where(rng.random(m) < 0.3, 0.012, -0.002)            # 30% of paths trend hard, the rest drift down
lc = drift[:, None] + rng.normal(0, 0.015, (m, Hn))
bank = {"lc": lc, "lo": np.zeros((m, Hn)), "lh": np.abs(rng.normal(0, 0.008, (m, Hn))) + np.maximum(lc, 0) * 0,
        "ll": -np.abs(rng.normal(0, 0.008, (m, Hn))) + np.minimum(lc, 0) * 0, "vol": np.full(m, 2.0)}
bank["lh"] = np.maximum(bank["lh"], lc) + 0.002
bank["ll"] = np.minimum(bank["ll"], lc) - 0.002
hist = {k: np.full(260, 50.0) for k in ("open", "high", "low", "close")}
hist["high"], hist["low"] = hist["high"] * 1.01, hist["low"] * 0.99
rl = {"mode": "next_open", "win": 1, "tgt": 2.0, "tlimit": 10, "trail": False, "kind": "chandelier", "trail_k": 3.0,
      "trail_ma": 21, "cap": 3.0, "plan": "ledger"}
a_led = L.sim_run_paths(bank, 2.0, hist, 48.5, rl, 10.0)
a_trim = L.sim_run_paths(bank, 2.0, hist, 48.5, tr, 10.0)
s_led, s_trim = L.sim_set_stats(a_led), L.sim_set_stats(a_trim)
check("target plan: no trade beats ~2R", s_led["r_max"] <= 2.0 + 1e-9, s_led["r_max"])
check("trim and trail: the best trades run far past 2R", s_trim["r_max"] > 4 and s_trim["r_top5"] > s_led["r_top5"] + 1,
      (s_trim["r_max"], s_trim["r_top5"], s_led["r_top5"]))
check("trim and trail: winners held longer than losers", s_trim["hold_win"] > s_trim["hold_loss"],
      (s_trim["hold_win"], s_trim["hold_loss"]))
check("trim and trail: some trades cut for not working, some trimmed",
      0 < s_trim["p_cut"] < 1 and 0 < s_trim["p_trim"] < 1, (s_trim["p_cut"], s_trim["p_trim"]))
check("stats: shares add up", abs(sum(s_trim[k] for k in ("p_target", "p_stop", "p_trail", "p_time", "p_open", "p_cut")) - 1) < 1e-9)
check("stats: 3R+ share and average winner", s_trim["p_big"] > 0 and s_trim["r_win"] > 0 > s_trim["r_loss"])
check("trimmed trades' R is at least a third of 2R minus costs when the rest stops at breakeven",
      np.all(a_trim["r"][a_trim["trimmed"] & (a_trim["outcome"] == 3)] >= 2 / 3 - 2 * 10 / 1e4 * 50 / 1.5 - 1e-9))

print("Relabeling the ledger")
n_, k_ = 500, 12
r_ = rng.normal(0.0008, 0.02, (n_, k_))
C_ = 40 * np.exp(np.cumsum(r_, 0))
O_ = C_ * np.exp(rng.normal(0, 0.005, (n_, k_)))
H_ = np.maximum(O_, C_) * np.exp(np.abs(rng.normal(0, 0.01, (n_, k_))))
L_ = np.minimum(O_, C_) * np.exp(-np.abs(rng.normal(0, 0.01, (n_, k_))))
dates = pd.bdate_range("2022-01-03", periods=n_)
names = [f"S{j}" for j in range(k_)]
P = {k: pd.DataFrame(v, index=dates, columns=names) for k, v in (("open", O_), ("high", H_), ("low", L_), ("close", C_),
                                                                    ("volume", np.full((n_, k_), 5e6)))}
lprm = {**prm, "cooldown": 10, "cost_mode": "flat", "spread_m": "ar", "min_price": 1.0, "min_dv": 0.1, "base_step": 5,
        "warmup": 60, "tl": 10, "tl_fam": (), "exit_fam": (), "mark_open": True}
ev = L.lg_run(P, None, None, ("Trend", "Gap"), "12/26/9", lprm, "test")["ev"]
ev2 = L.sim_relabel(P, ev, {**lprm, "sim_plan": pl})
done = ev["status"].to_numpy() == 0
check("relabel keeps every row and the entries", len(ev2) == len(ev) and np.allclose(ev2["entry"], ev["entry"], equal_nan=True))
check("relabel leaves non-trades alone", (ev2.loc[~done, "r"].isna() == ev.loc[~done, "r"].isna()).all())
check("some trades trimmed, some cut", bool(ev2["trimmed"].any()) and bool((ev2["outcome"] == 5).any()))
j = int(np.flatnonzero(done & ev2["trimmed"].to_numpy())[0])
e1 = ev.iloc[j]
ri = int(dates.get_indexer([e1["date"]])[0])
cj = names.index(e1["ticker"])
A_ = L._mc_atr(P["high"], P["low"], P["close"], 14).to_numpy()
d1 = L.lg_label(O_, H_, L_, C_, A_, np.array([ri]), np.array([cj]), np.array([e1["stop"]]), "next_open", 1, tr["tgt"], 0,
                3.0, 0.5, np.array([e1["cost_bp"]]), trail=True, trail_kind="ma", trail_k=3.0,
                ma=L.sim_ma_panel(P["close"], tr), mark_open=True, **L.sim_label_kw(tr))
check("a relabeled trade equals lg_label run directly", abs(d1["r"][0] - ev2.iloc[j]["r"]) < 1e-9, (d1["r"][0], ev2.iloc[j]["r"]))
check("exit dates line up with holds", (pd.to_datetime(ev2.loc[ev2["status"] == 0, "exit_date"]).notna()).all())
check("winners held longer than losers in the relabeled ledger",
      ev2.loc[(ev2["status"] == 0) & (ev2["r"] > 0), "hold"].median() > ev2.loc[(ev2["status"] == 0) & (ev2["r"] <= 0), "hold"].median())
check("cut outcome has a label", L.LG_OUTCOME[5] == "cut: not working")

print(f"\n{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
