"""Tests for the leveraged funds (Stocks > Leveraged): the name parser on real fund names (index, sector, single stock,
inverse, aliases, the typo'd and foreign ones) and on look-alikes that aren't leveraged; the fund pick (leverage caps,
liquidity, daily reset, the liquidity override); the variance drag against a simulation; the plan in the fund; the
tracking check; a screener CSV; the saved list; the Brief card's line.
Run: python test_lev.py"""
import os
import tempfile
import warnings
from pathlib import Path

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


print("The parser")
cases = {   # ticker, name -> (lev, under, kind, reset)
    ("SOXL", "Direxion Daily Semiconductor Bull 3X ETF"): (3, "SOXX", "sector", "daily"),
    ("SQQQ", "ProShares UltraPro Short QQQ"): (-3, "QQQ", "index", "daily"),
    ("QLD", "ProShares Ultra QQQ"): (2, "QQQ", "index", "daily"),
    ("SH", "ProShares Short S&P500"): (-1, "SPY", "index", "daily"),
    ("NVDL", "GraniteShares ETF Trust GraniteShares 2x Long NVDA Daily ETF"): (2, "NVDA", "single stock", "daily"),
    ("NVDX", "T-Rex 2X Long NVIDIA Daily Target ETF"): (2, "NVDA", "single stock", "daily"),
    ("TSLZ", "T-Rex 2X Inverse Tesla Daily Target ETF"): (-2, "TSLA", "single stock", "daily"),
    ("MUU", "Direxion Shares ETF Trust Direxion Daily MU Bull 2X ETF"): (2, "MU", "single stock", "daily"),
    ("PLTD", "Direxion Shares ETF Trust Direxion Dailly PLTR Bear 1X ETF"): (-1, "PLTR", "single stock", "daily"),
    ("MSTX", "Tidal Trust II Defiance Daily Target 2x Long MSTR ETF"): (2, "MSTR", "single stock", "daily"),
    ("MIC", "Corgi MU 2x Daily ETF"): (2, "MU", "single stock", "daily"),
    ("BRKL", "Corgi BRKB 2x Daily ETF"): (2, "BRK.B", "single stock", "daily"),
    ("USMX", "Corgi U.S. Mid-Cap 2x Daily ETF"): (2, "MDY", "index", "daily"),
    ("CCPX", "Corgi China 2x Daily ETF"): (2, "FXI", "intl", "daily"),
    ("SKUU", "GraniteShares 2x Long SK Hynix Daily ETF"): (2, "", "single stock", "daily"),
    ("NVDS", "Investment Managers Series Trust II Tradr 1.5X Short NVDA Daily ETF"): (-1.5, "NVDA", "single stock", "daily"),
    ("MQQQ", "Investment Managers Series Trust II Tradr 2X Long Innovation 100 Monthly ETF"): (2, "QQQ", "index", "monthly"),
    ("SPYQ", "Tradr 2X Long SPY Quarterly ETF"): (2, "SPY", "index", "quarterly"),
    ("UGLD", "DIREXION DAILY GOLD BULL 2X ETF"): (2, "GLD", "commodity", "daily"),
    ("RAM", "Roundhill T-REX 2X Long DRAM Daily Target ETF"): (2, "DRAM", "sector", "daily"),
    ("UVXY", "ProShares Ultra VIX Short-Term Futures ETF"): (1.5, "VIXY", "vol", "daily"),
    ("SVXY", "ProShares Short VIX Short-Term Futures ETF"): (-0.5, "VIXY", "vol", "daily"),
    ("SVIX", "-1x Short VIX Futures ETF"): (-1, "VIXY", "vol", "daily"),
    ("TBT", "ProShares Trust UltraShort Lehman 20+ Year Treasury"): (-2, "TLT", "rates", "daily"),
    ("SDD", "ProShares UltraShort SmallCap600"): (-2, "IJR", "index", "daily"),
    ("EFO", "ProShares Ultra MSCI EAFE"): (2, "EFA", "intl", "daily"),
    ("GDXD", "MicroSectors Gold Miners -3x Inverse Leveraged ETN"): (-3, "GDX", "sector", "daily"),
    ("JNUG", "Direxion Daily Junior Gold Miners Index Bull 2X ETF"): (2, "GDXJ", "sector", "daily"),
    ("SPYU", "MAX S&P 500 4x Leveraged ETN"): (4, "SPY", "index", "daily"),
    ("BITX", "2x Bitcoin ETF"): (2, "IBIT", "crypto", "daily"),
    ("WEBL", "Direxion Daily Dow Jones Internet Bull 3X ETF"): (3, "FDN", "sector", "daily"),
    ("UDOW", "ProShares UltraPro Dow 30"): (3, "DIA", "index", "daily"),
}
bad = []
for (t, nm), (lev, under, kind, reset) in cases.items():
    p = L.lev_parse(t, nm)
    if p is None or abs(p["lev"] - lev) > 1e-12 or p["under"] != under or p["kind"] != kind or p["reset"] != reset:
        bad.append((t, None if p is None else (p["lev"], p["under"], p["kind"], p["reset"])))
check(f"{len(cases)} real fund names: leverage, side, what it levers, the kind and the reset", not bad, bad)
check("the foreign single stock keeps its name", L.lev_parse("SKUU", "GraniteShares 2x Long SK Hynix Daily ETF")["under_label"] == "SK hynix (Korea)")
not_lev = ["JPMorgan Ultra-Short Income ETF", "Innovator U.S. Equity Ultra Buffer ETF - April", "Vanguard Short-Term Bond ETF",
           "PIMCO Enhanced Short Maturity Active Exchange-Traded Fund", "Invesco BulletShares 2030 Corporate Bond ETF",
           "First Trust Long/Short Equity ETF", "YieldMax Ultra Option Income Strategy ETF", "UPAR Ultra Risk Parity ETF",
           "ProShares VIX Short-Term Futures ETF", "Invesco S&P Ultra Dividend Revenue ETF", "AB Ultra Short Income ETF",
           "F/m Ultrashort Treasury Inflation-Protected Security (TIPS) ETF", "TrueShares Quarterly Bull Hedge ETF",
           "AdvisorShares Active Bear ETF", "IncomeSTKd 1x Bitcoin & 1x Gold Premium ETF", "WisdomTree Bloomberg U.S. Dollar Bullish Fund",
           "Simplify Bond Bull ETF", "Angel Oak UltraShort Income ETF", "EA Bridgeway Ultra-Small Company Market ETF",
           "Defiance Leveraged Long Income MSTR ETF", "State Street SPDR S&P Leveraged Loan ETF", "iShares Core S&P 500 ETF"]
hits = [nm for nm in not_lev if L.lev_parse("X", nm) is not None]
check(f"{len(not_lev)} look-alikes (ultra-short bonds, buffers, long/short, 1x long, option income) are not leveraged", not hits, hits)
S = L.lev_seed()
check("the built-in list parses every fund in it", len(S) == len(L.LEV_SEED.splitlines()) and set(L.LEV_COLS) <= set(S.columns))

print("The pick")
cat = pd.DataFrame([
    {"ticker": "AA3", "lev": 3.0, "under": "QQQ", "kind": "index", "side": "long", "reset": "daily", "dv_m": 100.0},
    {"ticker": "AA2", "lev": 2.0, "under": "QQQ", "kind": "index", "side": "long", "reset": "daily", "dv_m": 250.0},
    {"ticker": "AAM", "lev": 3.0, "under": "QQQ", "kind": "index", "side": "long", "reset": "monthly", "dv_m": 900.0},
    {"ticker": "AAS", "lev": -3.0, "under": "QQQ", "kind": "index", "side": "short", "reset": "daily", "dv_m": 50.0},
    {"ticker": "BB2", "lev": 2.0, "under": "XYZ", "kind": "single stock", "side": "long", "reset": "daily", "dv_m": 3.0},
    {"ticker": "BB3", "lev": 3.0, "under": "XYZ", "kind": "single stock", "side": "long", "reset": "daily", "dv_m": 40.0},
    {"ticker": "BBL", "lev": 1.5, "under": "XYZ", "kind": "single stock", "side": "long", "reset": "daily", "dv_m": 20.0},
])
check("the highest leverage under the cap, daily reset only (the monthly fund is skipped)", L.lev_pick(cat, "QQQ")["ticker"] == "AA3")
cat2 = cat.assign(dv_m=np.where(cat["ticker"] == "AA2", 400.0, cat["dv_m"]))
check("a lower leverage that trades over 3x as much wins", L.lev_pick(cat2, "QQQ")["ticker"] == "AA2")
cat3 = pd.concat([cat, pd.DataFrame([{"ticker": "AS1", "lev": -1.0, "under": "QQQ", "kind": "index", "side": "short", "reset": "daily", "dv_m": 900.0}])])
check("liquidity never trades a 3x inverse down to 1x", L.lev_pick(cat3, "QQQ", "short")["ticker"] == "AAS")
check("max 2x on index funds when set", L.lev_pick(cat, "QQQ", max_lev=2.0)["ticker"] == "AA2")
check("single stocks capped at 2x; under the liquidity floor is skipped (2x at $3M), so 1.5x",
      L.lev_pick(cat, "XYZ", min_dv=5.0, single_max=2.0)["ticker"] == "BBL")
check("the inverse side", L.lev_pick(cat, "QQQ", "short")["ticker"] == "AAS" and L.lev_pick(cat, "ABC") is None)
M = L.lev_map(cat.assign(name="", issuer="", under_label="", asof="", src=""), ["QQQ", "XYZ", "ABC"])
check("the map per name", M.at["QQQ", "lev_long"] == "AA3" and M.at["QQQ", "lev_short"] == "AAS" and M.at["ABC", "lev_long"] == ""
      and M.at["QQQ", "lev_txt"] == "AA3 3x", M.to_dict("index"))

print("The drag")
rng = np.random.default_rng(1)
sig, days, n = 0.03, 20, 40000
r = rng.normal(0, sig, (n, days))
for lev in (2.0, 3.0):
    under_log = np.log1p(r).sum(axis=1)
    fund_log = np.log1p(lev * r).sum(axis=1)
    sim = float(np.mean(fund_log - lev * under_log))
    model = np.log1p(L.lev_drag(lev, sig, days))
    check(f"{lev:g}x: the drag formula matches a simulation of daily resets ({model:.4f} vs {sim:.4f})", abs(model - sim) < 0.12 * abs(sim), (model, sim))
check("no drag at 1x; the inverse fund has drag too", abs(L.lev_drag(1.0, sig, days)) < 1e-15 and L.lev_drag(-1.0, sig, days) < 0)
check("by hand: 2x at 3% a day over 10 sessions = exp(-0.0009 x 10) - 1", abs(L.lev_drag(2, 0.03, 10) - (np.exp(-0.009) - 1)) < 1e-15)

print("The plan in the fund")
pl = L.lev_plan(100.0, 95.0, 2.0, 40.0, 500.0)
check("a 5% stop on the stock is 10% in a 2x fund", abs(pl["fund_risk_pct"] - 10.0) < 1e-9 and abs(pl["fund_stop"] - 36.0) < 1e-9)
check("the same $500 risk: 100 shares of the stock ($10,000) or 125 of the fund ($5,000), half the capital",
      pl["stock_shares"] == 100 and pl["fund_shares"] == 125 and abs(pl["fund_capital"] - 5000) < 1e-9 and pl["capital_frac"] == 0.5)
check("a stop above the entry has no plan", L.lev_plan(100, 105, 2, 40, 500) == {})

print("The tracking check")
idx = pd.bdate_range("2025-01-01", periods=200)
u = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 200))), index=idx)
f = pd.Series(20 * (1 + 2 * u.pct_change().fillna(0)).cumprod(), index=idx)
tk = L.lev_tracking(f, u, 2.0, 60)
check("a perfect 2x daily fund: beta 2, no tracking error", abs(tk["beta"] - 2) < 1e-9 and tk["te"] < 1e-9)
check("its gap against 2x held is the compounding (it can be either sign), near the drag the volatility predicts",
      abs(tk["fund_ret"] - (f.iloc[-1] / f.iloc[-61] - 1)) < 1e-12 and abs(tk["gap"]) < 0.25)
fd = L.lev_demo_fund(u, 2.0)
tk2 = L.lev_tracking(fd, u, 2.0, 120)
check("the demo fund (fee and noise): beta near 2, small tracking error", abs(tk2["beta"] - 2) < 0.05 and tk2["te"] < 0.02, tk2)

print("A screener CSV, the saved list, the Brief's line")
csv = pd.DataFrame({"Symbol": ["TQQQ", "NVDL", "SPY", "VGSH"], "Name": ["ProShares UltraPro QQQ", "GraniteShares 2x Long NVDA Daily ETF",
                                                                      "SPDR S&P 500 ETF Trust", "Vanguard Short-Term Treasury ETF"],
                    "Dollar Volume": [4.5e9, 1.2e9, 3e10, 1e8]})
C = L.lev_from_csv(csv)
check("a financecharts-style export: the two leveraged funds kept, with $M a day", list(C["ticker"]) == ["TQQQ", "NVDL"]
      and abs(C.set_index("ticker").at["TQQQ", "dv_m"] - 4500) < 1e-9)
tmp = Path(tempfile.mkdtemp(prefix="lev_")) / "lev_funds.csv"
L.LEV_FILE = tmp
check("with nothing saved, the built-in list", len(L.lev_catalog()) == len(S))
L.lev_save(C)
check("a saved list is read back", list(L.lev_catalog()["ticker"]) == ["TQQQ", "NVDL"] and not tmp.with_suffix(".tmp").exists())
tmp.unlink()
line = L.lev_line("NVDA", 100.0, 95.0, 500.0, 4.0, dict(L.LEV_DEFAULTS))
check("the Brief's line names the fund, the stop in it and the drag", line.startswith("Leveraged: NVDL (2x NVDA") and "10.0% in the fund" in line
      and "50% of the capital" in line and "drag over 10 sessions" in line, line)
check("no fund, no line", L.lev_line("ZZZZ", 100.0, 95.0, 500.0, 4.0) == "")
row = pd.Series({"ticker": "NVDA", "trigger": 100.0, "stop": 95.0, "risk_pct": 5.0, "trig_why": "x", "stop_why": "y", "status": "today"})
plan = L.su_plan(row, {"risk": "Medium", "cond": "OK"}, 1.0, 100000.0, pd.Series({"adr20": 4.0, "atr": 3.0}))
check("the Brief card's plan carries the line when using funds is on", any(x.startswith("Leveraged: NVDL") for x in plan), plan)

print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
