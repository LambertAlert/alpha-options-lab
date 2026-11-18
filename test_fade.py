"""Planted-case tests for Martin Luk's fade of the weak bounce (TraderLion, Nov 2026): each rule on a chart built to
pass it and on variants that fail exactly one (a heavy-volume bounce, EMAs far apart, an uptrend, a close back over
the EMA), the market-pullback gate, the bear ledger scoring both versions with the stop at the day's high, and the
Luk scanner's Fade screen (rejected, testing, triggered since, live under the trigger).
Run: python test_fade.py"""
import warnings
from datetime import date
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


IDX = pd.bdate_range("2025-01-02", periods=300)


def plant(kind="fade", after=0):
    """A weak stock: a long decline, a slow grind (the 21 and 50-day EMAs converge), a sell-off to a 10-day low, a
    three-day bounce on light volume, then the signal day: up to the 21-day EMA, back under it, red, bottom half.
    `after` adds that many sessions sliding lower."""
    c = np.r_[np.linspace(150, 112, 150), np.linspace(112, 108.5, 90)]
    if kind == "wide":
        c = np.linspace(150, 100, 240)
    if kind == "up":
        c = np.linspace(80, 120, 240)
    k0 = len(c)
    c = np.r_[c, np.linspace(c[-1], c[-1] * 0.94, 6)[1:]]
    b = c[-1]
    c = np.r_[c, b * 1.02, b * 1.04, b * 1.055]
    vol = np.full(len(c), 1e6)
    vol[k0:k0 + 5] = 2.0e6
    vol[-3:] = 0.6e6 if kind != "heavy" else 2.5e6
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.008, "low": np.minimum(o, c) * 0.992, "close": c,
                       "volume": vol}, index=IDX[:len(c)])
    e21 = df["close"].ewm(span=21, min_periods=21).mean()
    so = max(c[-1], e21.iloc[-1]) * 1.002
    sc = e21.iloc[-1] * (0.98 if kind != "closeup" else 1.01)
    row = pd.DataFrame({"open": [so], "close": [sc], "volume": [0.7e6 if kind != "heavy" else 2.5e6],
                        "high": [0.0], "low": [0.0]}, index=[IDX[len(c)]])
    df = pd.concat([df, row])
    e21 = df["close"].ewm(span=21, min_periods=21).mean()
    if kind != "closeup":
        df.loc[df.index[-1], ["high", "low"]] = [max(e21.iloc[-1] * 1.002, so) * 1.001, min(so, sc) * 0.996]
    else:
        df.loc[df.index[-1], ["high", "low"]] = [sc * 1.004, so * 0.995]
    for k in range(after):
        p = df["close"].iloc[-1]
        df = pd.concat([df, pd.DataFrame({"open": [p * 0.995], "high": [p * 0.998], "low": [p * 0.975], "close": [p * 0.98],
                                          "volume": [1.2e6]}, index=[IDX[len(df)]])])
    return df


def panel(dfs):
    return {k: pd.DataFrame({n: d[k] for n, d in dfs.items()}) for k in ("open", "high", "low", "close", "volume")}


def parts_last(df):
    P = panel({"X": df})
    o, h, l, c, v = (P[k].astype(float) for k in ("open", "high", "low", "close", "volume"))
    S = L.br_states(o, h, l, c, v, pd.DataFrame(np.nan, index=c.index, columns=c.columns))
    fp = L.br_fade_parts(o, h, l, c, v, S)
    return {k: x.iloc[-1, 0] for k, x in fp.items()}, S, fp


print("the rules, one at a time")
f, S, fp = parts_last(plant("fade"))
check("the planted chart passes every rule: weak, converging, a bounce, light volume, a rejection",
      all(bool(f[k]) for k in ("weak", "conv", "bounce", "light", "touched", "reject", "setup")), f)
check("weak = under the 50-day EMA, the 21 under the 50, both falling",
      S["e21"].iloc[-1, 0] < S["e50"].iloc[-1, 0] and S["e50"].iloc[-1, 0] < S["e50"].iloc[-11, 0])
check("converging = the 21 and 50 within one ATR", f["spread_atr"] <= 1.0 and abs(S["e50"].iloc[-1, 0] - S["e21"].iloc[-1, 0])
      <= S["atr14"].iloc[-1, 0])
check("a heavy-volume bounce isn't weak: no setup", not parts_last(plant("heavy"))[0]["setup"])
check("EMAs far apart (a steady slide): not converging, no setup", not parts_last(plant("wide"))[0]["conv"]
      and not parts_last(plant("wide"))[0]["setup"])
check("an uptrend isn't weak: no setup", not parts_last(plant("up"))[0]["weak"])
fc = parts_last(plant("closeup"))[0]
check("a close back over the 21-day EMA isn't a rejection (the setup is there, the price is testing)",
      fc["setup"] and fc["touched"] and not fc["reject"])

print("the market gate")
spy_down = pd.Series(np.r_[np.linspace(400, 500, 230), np.linspace(500, 470, 70)], index=IDX)
spy_up = pd.Series(np.linspace(400, 520, 300), index=IDX)
mp_d, mp_u = L.br_market_pullback(spy_down), L.br_market_pullback(spy_up)
check("SPY under its 21-day EMA or 3%+ off its 20-day high = a pullback; a steady rise isn't",
      bool(mp_d["pullback"].iloc[-1]) and not mp_u["pullback"].iloc[-30:].any())
dfs = {"FADE": plant("fade"), "HEAVY": plant("heavy"), "WIDE": plant("wide"), "UP": plant("up"), "TEST": plant("closeup")}
P = panel(dfs)
o, h, l, c, v = (P[k].astype(float) for k in ("open", "high", "low", "close", "volume"))
S2 = L.br_states(o, h, l, c, v, L.lg_rs_rating(c))
sd = L.br_signals(o, h, l, c, v, S2, None, 15, "bear", None, mp_d["pullback"])
su = L.br_signals(o, h, l, c, v, S2, None, 15, "bear", None, mp_u["pullback"])
d0 = dfs["FADE"].index[-1]
check("the rejection day fires both versions in a pullback, only the any-market one when SPY is rising",
      bool(sd["br:ema_reject"].at[d0, "FADE"]) and bool(sd["br:luk_fade"].at[d0, "FADE"])
      and bool(su["br:ema_reject"].at[d0, "FADE"]) and not su["br:luk_fade"].at[d0, "FADE"])
check("none of the failing variants fire", not any(bool(sd["br:ema_reject"][n].loc[dfs[n].index[-1]]) for n in ("HEAVY", "WIDE", "UP", "TEST")))
check("no market series: only the any-market version", "br:luk_fade" not in L.br_signals(o, h, l, c, v, S2, None, 15, "bear"))

print("the bear ledger scores it")
d_after = {"FADE": plant("fade", after=12), "FLAT": plant("up", after=0)}
Pl = panel(d_after)
Pl["close"]["SPY"] = spy_down.reindex(Pl["close"].index)
for k in ("open", "high", "low"):
    Pl[k]["SPY"] = Pl["close"]["SPY"]
Pl["volume"]["SPY"] = 5e7
prm = {"horizon": 5, "cooldown": 5, "min_price": 5.0, "min_dv": 1.0, "mode": "next_open", "win": 1, "tgt": 1.5, "cap": 3.0,
       "cost": 10.0, "iv_mult": 1.15, "skew": 0.5, "opt_cost": 0.03, "mrv_thr": 15.0, "base_step": 5, "warmup": 100}
run = L.br_run(Pl, Pl["close"]["SPY"], None, prm, "planted")
ev = run["ev"]
e = ev[(ev["setup"] == "br:luk_fade") & (ev["ticker"] == "FADE")]
sig_day = plant("fade").index[-1]
nxt = d_after["FADE"].index[d_after["FADE"].index.get_loc(sig_day) + 1]
check("the ledger has the fade on the rejection day only, stop at that day's high, shorted at the next open",
      len(e) == 1 and e["date"].iloc[0] == sig_day and abs(e["stop_plan"].iloc[0] - d_after["FADE"]["high"].loc[sig_day]) < 1e-6
      and abs(e["entry"].iloc[0] / d_after["FADE"]["open"].loc[nxt] - 1) < 1e-6,   # the ledger stores prices as float32
      e[["date", "stop_plan", "entry"]] if len(e) else ev["setup"].value_counts())
check("the slow grind before the sell-off isn't a bounce (no any-market fade there either)",
      not len(ev[(ev["setup"] == "br:ema_reject") & (ev["ticker"] == "FADE") & (ev["date"] < sig_day)]))
check("the slide after it pays the short", float(e["r"].iloc[0]) > 0 and e["outcome"].iloc[0] in (0, 2))
check("both versions in the setup list, labelled", {"br:luk_fade", "br:ema_reject"} <= set(L.BR_SETUPS)
      and "Luk" in L.BR_SETUPS["br:luk_fade"][1] and L.BR_SETUPS["br:luk_fade"][2] == "day_hi")

print("the Fade screen")
tday = (dfs["FADE"].index[-1] + pd.offsets.BDay(1)).date()
rows, info = L.lk_fade(P, spy_down, tday)
check("REJECTED: trigger = the rejection day's low, stop = its high", "FADE" in rows.index and rows.at["FADE", "status"] == "REJECTED"
      and abs(rows.at["FADE", "trigger"] - dfs["FADE"]["low"].iloc[-1]) < 1e-9 and abs(rows.at["FADE", "stop"] - dfs["FADE"]["high"].iloc[-1]) < 1e-9,
      rows[["status", "trigger", "stop"]] if len(rows) else rows)
check("TESTING: the setup is there, the price is at the EMA, no rejection yet", rows.at["TEST", "status"] == "TESTING")
check("the failing variants aren't listed; rejections sort first", not ({"HEAVY", "WIDE", "UP"} & set(rows.index))
      and rows["status"].iloc[0] == "REJECTED")
check("the market condition comes along", info["pullback"] is True and info["vs21"] < 0)
Lv = pd.DataFrame({"last": [rows.at["FADE", "trigger"] * 0.99]}, index=["FADE"])
rl, _ = L.lk_fade(P, spy_down, tday, Lv)
check("live: trading under the trigger is flagged", bool(rl.at["FADE", "triggered"]))
P3 = panel({"FADE": plant("fade", after=1)})
r3, _ = L.lk_fade(P3, spy_down, (P3["close"].index[-1] + pd.offsets.BDay(1)).date())
check("a rejection whose low has since been broken: TRIGGERED SINCE", r3.at["FADE", "status"] == "TRIGGERED SINCE", r3)
check("risk = stop over trigger; flagged when within his 5%", abs(rows.at["FADE", "risk"] - (rows.at["FADE", "stop"] / rows.at["FADE", "trigger"] - 1)) < 1e-12
      and rows.at["FADE", "in_range"] == (rows.at["FADE", "risk"] <= 0.05))

print()
print(f"{PASS} passed, {len(FAIL)} failed" + (f": {FAIL}" if FAIL else ""))
