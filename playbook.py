#!/usr/bin/env python3
"""
playbook.py
===========
The expectancy playbook: trade only what has passed the lab's tests, and keep score against what it should pay.

    python playbook.py              # opens the app with the War Room theme (or: streamlit run playbook.py)
    python playbook.py nightly      # rebuilds the ledgers on your list, then tonight's signals and the tracker
    python playbook.py nightly --source demo

The lab (alpha_options_lab.py) stays the research bench. This file reads what it saves in data/ and adds:

1. Playbook. Setups proposed from the ledgers (PROVEN and surviving the deflated Sharpe, scored under your trim and
   trail plan; spread setups by the spread's own return on risk), admitted by you, each with its expectation frozen
   on the day it went in, its rules and a half-Kelly risk per trade.
2. Tonight. The last session's signals from playbook setups only: entry, stop, 1R in dollars, size.
3. Journal. Every trade from plan to exit, with a deviation tag when it didn't follow the plan.
4. Edge tracker. Each trade against the ledger's own version of the same signal: the gap split into entry cost and
   the rest; your picks against every playbook signal (selection) and your execution against the ledger's on the
   same picks (implementation); skipped signals; each setup's live record against the band its frozen expectation
   predicts, with a sequential test that says when the edge looks gone.
5. Review. Weeks and months: R, the implementation gap, discipline, chasing, and what each deviation cost.

Files (data/, or $PLAYBOOK_DATA): playbook.json (setups, frozen expectations, plan, account), playbook_journal.csv
(trades), playbook_tonight.csv and playbook_report.md (nightly), playbook_ledger_plan.parquet (the Setup ledger
re-run under your plan, cached). It reads setup_ledger.parquet and setup_ledger_verdicts.json (the lab's Setup
ledger), bull/bear_ledger.parquet, _candidates.parquet and _ledger_meta.json (the lab's Bull and Bear spreads) and
book_positions.csv (the Book). Every write is atomic (.tmp, then os.replace).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import uuid
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import alpha_options_lab as L                                    # noqa: E402

HERE = Path(__file__).resolve().parent

# ── files ────────────────────────────────────────────────────────────────────────────────────────────────────────
def pb_dir() -> Path:
    return Path(os.getenv("PLAYBOOK_DATA") or (HERE / "data"))


def f_playbook() -> Path: return pb_dir() / "playbook.json"
def f_journal() -> Path: return pb_dir() / "playbook_journal.csv"
def f_tonight() -> Path: return pb_dir() / "playbook_tonight.csv"
def f_report() -> Path: return pb_dir() / "playbook_report.md"
def f_plan_ledger(slot: str = "") -> Path: return pb_dir() / f"playbook_ledger_plan{'_' + slot if slot else ''}.parquet"
def f_ledger(kind: str) -> Path: return pb_dir() / ("setup_ledger.parquet" if kind == "setup" else f"{kind}_ledger.parquet")
def f_meta(kind: str) -> Path: return pb_dir() / ("setup_ledger_verdicts.json" if kind == "setup" else f"{kind}_ledger_meta.json")
def f_cands(kind: str) -> Path: return pb_dir() / f"{kind}_candidates.parquet"
def f_book() -> Path: return pb_dir() / "book_positions.csv"


def _atomic_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _atomic_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ── what the playbook knows ──────────────────────────────────────────────────────────────────────────────────────
PB_LEDGERS = {"setup": "Setup ledger", "bull": "Bull spreads", "bear": "Bear spreads"}
PB_BOOKS = {"shares": "Shares", "debit": "Debit spread", "credit": "Credit spread"}
PB_METRIC = {"shares": "r", "debit": "db_follow", "credit": "cr_follow"}
PB_DEVIATIONS = ["", "chased", "entered early", "entered late", "moved the stop", "exited early", "held past the exit",
                 "skipped the trim", "sized up", "sized down", "other"]
PB_STATUS = ["planned", "open", "closed", "skipped", "cancelled"]
JOURNAL_COLS = ["id", "status", "ticker", "key", "ledger", "setup", "book", "side", "signal_date", "plan_entry", "plan_stop",
                "plan_size", "entry_date", "entry_px", "size", "init_stop", "max_risk", "trim_date", "trim_px", "trim_qty",
                "exit_date", "exit_px", "deviation", "notes"]
PB_TXT_COLS = ("id", "status", "ticker", "key", "ledger", "setup", "book", "side", "signal_date", "entry_date",
               "trim_date", "exit_date", "deviation", "notes")
PB_PLAN_DEFAULT = {"kind": "trim", "trim_r": 2.0, "frac": 1 / 3, "frac_lbl": "1/3", "stop": "be", "runner": "ema21",
                   "closes": 1, "fail_n": 5, "fail_r": 0.0, "fail_once": True, "be_r": 0.0, **L.SIM_SIG_DEFAULT}
# The exit lab: your plan against exit signals on the same trades (same entries, same initial stops).
PB_EXIT_VARIANTS = {"yours": "Your plan", "trim_sig": "Trim at the target, exit signals take the rest",
                    "sig_only": "No target: exit signals take the whole trade"}
PB_EXIT_SHORT = {"yours": "your plan", "trim_sig": "trim + signals", "sig_only": "signals only"}
PB_EXIT_T = 2.0                            # a variant beats your plan at a paired t of 2+ (and q 0.10 or less per setup)
PB_EXIT_Q = 0.10
PB_EXIT_MIN = 30                           # fewer common trades than this: too few to call
PB_DEFAULT = {"setups": {}, "plan": dict(PB_PLAN_DEFAULT),
              "account": {"equity": 100000.0, "max_risk_pct": 1.0, "kelly_frac": 0.5},
              "bar": {"dsr": 0.95, "t_spread": 2.5}, "updated": ""}
PB_Z90 = 1.645
PB_SPRT = math.log(9.0)                    # Wald's bounds at alpha = beta = 0.10


def pb_key(ledger: str, sid: str, book: str) -> str:
    return f"{ledger}|{sid}|{book}"


def pb_split(key: str) -> Tuple[str, str, str]:
    a, b, c = (key.split("|") + ["", "", ""])[:3]
    return a, b, c


def pb_setup_label(ledger: str, sid: str) -> str:
    tab = L.LG_SETUPS if ledger == "setup" else (L.BL_SETUPS if ledger == "bull" else L.BR_SETUPS)
    return tab.get(sid, ("", sid, ""))[1]


def pb_side(ledger: str, book: str) -> str:
    return "short" if (ledger == "bear" and book == "shares") else "long"


def pb_key_label(key: str) -> str:
    ledger, sid, book = pb_split(key)
    side = " (short)" if pb_side(ledger, book) == "short" else ""
    bk = {"debit": " · put debit" if ledger == "bear" else " · call debit",
          "credit": " · call credit" if ledger == "bear" else " · put credit"}.get(book, "")
    return f"{pb_setup_label(ledger, sid)}{side}{bk}"


def pb_sig_txt(p: Dict[str, Any]) -> str:
    """The exit signals in words, with their thresholds."""
    p = {**PB_PLAN_DEFAULT, **p}
    nc = int(p.get("closes", 1))
    return (f"{'a close' if nc <= 1 else f'{nc} closes in a row'} under the 10-day EMA, a distribution day "
            f"(down {float(p['dist_drop']):g}%+ on {float(p['dist_vol']):g}x+ the 50-day volume) or a climax "
            f"({float(p['climax_ext']):g}%+ over the 50-day SMA)")


def pb_plan_tag(plan: Dict[str, Any]) -> str:
    p = {**PB_PLAN_DEFAULT, **plan}
    lvl = "breakeven" if float(p["fail_r"]) == 0 else f"{float(p['fail_r']):+g}R"
    cut = f", cut by session {int(p['fail_n'])} if under {lvl}" if int(p.get("fail_n", 0)) else ""
    sig = p["runner"] == "signals"
    out_ = (f"the first exit signal: {pb_sig_txt(p)}" if sig
            else f"the {L.SIM_RUNNER_SHORT.get(p['runner'], p['runner'])}")
    if not float(p["trim_r"]) > 0:
        return f"no target: the whole trade out on {out_}{cut}"
    return (f"trim {p['frac_lbl']} at {float(p['trim_r']):g}R, stop to {L.SIM_TRIM_STOPS.get(p['stop'], p['stop'])}, "
            f"the rest out on {out_}{cut}" if sig else
            f"trim {p['frac_lbl']} at {float(p['trim_r']):g}R, stop to {L.SIM_TRIM_STOPS.get(p['stop'], p['stop'])}, "
            f"the rest out on the {L.SIM_RUNNER_SHORT.get(p['runner'], p['runner'])}{cut}")


def pb_load() -> Dict[str, Any]:
    d = _read_json(f_playbook(), None) or {}
    out = json.loads(json.dumps(PB_DEFAULT))
    for k, v in d.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def pb_save(pb: Dict[str, Any]) -> None:
    pb = dict(pb)
    pb["updated"] = datetime.now().isoformat(timespec="seconds")
    f_playbook().parent.mkdir(parents=True, exist_ok=True)
    L.atomic_write_json(f_playbook(), json.loads(json.dumps(pb, default=_json_default)))


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (pd.Timestamp, date, datetime)):
        return str(o)[:10]
    return str(o)


# ── the ledgers ──────────────────────────────────────────────────────────────────────────────────────────────────
def pb_ledger_prm(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The Setup ledger's parameters: the full set the lab saves with its verdicts, else the lab's defaults with the
    few the verdict file always carries."""
    d = L.LG_DEFAULTS
    prm = {"mode": d["lg_mode"], "win": int(d["lg_win"]), "tgt": float(d["lg_tgt"]), "horizon": int(d["lg_h"]),
           "cost": float(d["lg_cost"]), "cost_mode": d["lg_cost_mode"], "spread_m": d["lg_spread_m"],
           "cooldown": int(d["lg_cd"]), "cap": float(d["lg_cap"]), "min_price": float(d["lg_px"]),
           "min_dv": float(d["lg_dv"]), "base_step": int(d["lg_base_step"]), "warmup": L.LG_WARMUP,
           "tl_mode": d["lg_tl_mode"], "tl": int(d["lg_tl"]), "tl_fam": tuple(sorted(L.LG_TL_SEED.items())),
           "exit_mode": d["lg_exit_mode"], "trail": d["lg_trail"], "trail_k": float(d["lg_trail_k"]),
           "trail_ma": int(d["lg_trail_ma"]), "mark_open": bool(d["lg_open"]),
           "exit_fam": tuple(sorted(L.LG_EXIT_SEED.items()))}
    meta = meta or {}
    full = meta.get("prm_full") or {}
    for k, v in full.items():
        prm[k] = tuple(tuple(x) if isinstance(x, list) else x for x in v) if isinstance(v, list) else v
    for k, v in (meta.get("params") or {}).items():
        if k in prm and not full:
            prm[k] = v
    return prm


def pb_br_prm(side: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    d = L.BR_DEFAULTS
    prm = {"side": side, "horizon": int(d["h"]), "cooldown": int(d["cd"]), "min_price": float(d["px"]),
           "min_dv": float(d["dv"]), "mode": d["mode"], "win": 1, "tgt": float(d["tgt"]), "cap": 3.0,
           "cost": float(d["stock_bp"]), "iv_mult": float(d["ivm"]), "skew": float(d["skew"]),
           "opt_cost": float(d["cost"]) / 100.0, "mrv_thr": float(d["mrv"]), "base_step": 5, "cc_short": d["cc"],
           "warmup": L.BR_WARMUP}
    prm.update((meta or {}).get("prm") or {})
    return prm


def pb_read_ledgers() -> Dict[str, Dict[str, Any]]:
    """Whatever the lab (or the nightly run) saved: each ledger's events, its metadata and (spreads) today's
    candidates. Missing files come back empty, with the reason."""
    out = {}
    for kind in PB_LEDGERS:
        f = f_ledger(kind)
        rec: Dict[str, Any] = {"kind": kind, "ev": pd.DataFrame(), "meta": _read_json(f_meta(kind), {}) or {},
                               "cands": pd.DataFrame(), "mtime": 0.0, "file": str(f)}
        if f.exists():
            try:
                ev = pd.read_parquet(f)
                if "universe" in ev and (ev["universe"] == "list").any():
                    ev = ev[ev["universe"] == "list"]         # your list: the names you trade
                ev["date"] = pd.to_datetime(ev["date"])
                rec["ev"] = ev.reset_index(drop=True)
                rec["mtime"] = f.stat().st_mtime
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
        if kind != "setup" and f_cands(kind).exists():
            try:
                rec["cands"] = pd.read_parquet(f_cands(kind))
            except Exception:
                pass
        out[kind] = rec
    return out


def _relabel_stamp(ev: pd.DataFrame, P: Dict[str, pd.DataFrame], plan: Dict[str, Any], tag: str) -> str:
    return f"{tag}|{json.dumps(plan, sort_keys=True, default=str)}|{P['close'].index[-1]}|{len(ev)}"


def pb_relabel_cached(ev: pd.DataFrame, P: Optional[Dict[str, pd.DataFrame]], plan: Dict[str, Any], tag: str = "",
                      slot: str = "") -> bool:
    """Whether pb_relabel would read this plan's trades from disk (no re-run)."""
    if ev is None or not len(ev) or P is None:
        return False
    f = f_plan_ledger(slot)
    return f.exists() and (_read_json(f.with_suffix(".json"), {}) or {}).get("stamp") == _relabel_stamp(ev, P, plan, tag)


def pb_relabel(ev: pd.DataFrame, P: Dict[str, pd.DataFrame], prm: Dict[str, Any], plan: Dict[str, Any],
               tag: str = "", slot: str = "") -> pd.DataFrame:
    """The Setup ledger re-run under your trim-and-trail plan (same entries and stops, your exits), cached on disk
    under the ledger's file time, the plan and the last bar, so the app doesn't redo it on every start. `slot` keeps
    the exit lab's other plans in files of their own."""
    if ev is None or not len(ev):
        return pd.DataFrame()
    stamp = _relabel_stamp(ev, P, plan, tag)
    f = f_plan_ledger(slot)
    meta_f = f.with_suffix(".json")
    if f.exists() and (_read_json(meta_f, {}) or {}).get("stamp") == stamp:
        try:
            out = pd.read_parquet(f)
            out["date"] = pd.to_datetime(out["date"])
            return out
        except Exception:
            pass
    out = L.sim_relabel(P, ev, {**prm, "sim_plan": {**PB_PLAN_DEFAULT, **plan}})
    try:
        _atomic_parquet(out, f)
        L.atomic_write_json(meta_f, {"stamp": stamp, "built": datetime.now().isoformat(timespec="seconds")})
    except Exception:
        pass
    return out


def pb_scoreboards(led: Dict[str, Dict[str, Any]], ev_plan: Optional[pd.DataFrame], prm_setup: Dict[str, Any],
                   hold: float = 0.4) -> Dict[str, pd.DataFrame]:
    """The ledgers' own scoreboards (the Setup ledger's on the plan-relabelled trades, with the deflated Sharpe)."""
    sbs = {}
    if ev_plan is not None and len(ev_plan):
        sbs["setup"], _ = L.lg_score(ev_plan, "none", hold, int(prm_setup["horizon"]))
    for side in ("bull", "bear"):
        ev = led[side]["ev"]
        if len(ev):
            prm = pb_br_prm(side, led[side]["meta"])
            sbs[side], _ = L.br_score(ev, "none", float(led[side]["meta"].get("hold", hold)), int(prm["horizon"]), side)
    return sbs


def pb_exit_plans(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The exit lab's three plans: yours as set; trim at your target (2R if yours has none) with the exit signals on
    the rest; and no target, the exit signals on the whole trade. Everything else (the stop after the trim, the time
    stop, closes under the EMA, the signal thresholds) is yours in all three."""
    p = {**PB_PLAN_DEFAULT, **plan}
    tr = float(p["trim_r"]) if float(p["trim_r"]) > 0 else float(PB_PLAN_DEFAULT["trim_r"])
    return {"yours": p, "trim_sig": {**p, "runner": "signals", "trim_r": tr}, "sig_only": {**p, "runner": "signals", "trim_r": 0.0}}


def pb_exit_runs(ev: pd.DataFrame, P: Dict[str, pd.DataFrame], prm: Dict[str, Any], plan: Dict[str, Any],
                 tag: str = "", only_cached: bool = False) -> Optional[Dict[str, pd.DataFrame]]:
    """The Setup ledger's trades under each exit-lab plan (a plan identical to an earlier one reuses its run). With
    only_cached, None unless every run is already on disk."""
    plans = pb_exit_plans(plan)
    if only_cached and not all(pb_relabel_cached(ev, P, pl, tag, "" if v == "yours" else v) for v, pl in plans.items()
                               if not any(plans[u] == pl for u in list(plans)[:list(plans).index(v)])):
        return None
    out: Dict[str, pd.DataFrame] = {}
    for v, pl in plans.items():
        same = next((u for u in out if plans[u] == pl), None)
        out[v] = out[same] if same else pb_relabel(ev, P, prm, pl, tag=tag, slot="" if v == "yours" else v)
    return out


def _exit_stats(x: pd.DataFrame, horizon: int) -> Dict[str, float]:
    r = x["r"].to_numpy(float)
    if not len(r):
        return {"n": 0}
    oc = x["outcome"].to_numpy(int)
    sg = x["exit_sig"].to_numpy(int) if "exit_sig" in x else np.zeros(len(x), int)
    hold = x["hold"].to_numpy(float)
    win = r > 0
    dm = x.groupby("date")["r"].mean().sort_index().to_numpy()
    mu, se = L.lg_nw(dm, max(int(horizon), 1))
    top = np.sort(r)[::-1][: max(1, int(np.ceil(0.05 * len(r))))]
    return {"n": int(len(r)), "dates": int(len(dm)), "er": float(r.mean()), "er_date": float(mu),
            "t": float(mu / se) if se and np.isfinite(se) and se > 0 else np.nan, "win": float(win.mean()),
            "avg_win": float(r[win].mean()) if win.any() else np.nan, "avg_loss": float(r[~win].mean()) if (~win).any() else np.nan,
            "p_big": float((r >= L.SIM_BIG_R).mean()), "r_top5": float(top.mean()), "r_max": float(r.max()),
            "hold_win": float(np.median(hold[win])) if win.any() else np.nan,
            "hold_loss": float(np.median(hold[~win])) if (~win).any() else np.nan,
            "p_trim": float(x["trimmed"].astype(bool).mean()) if "trimmed" in x else 0.0,
            "p_stop": float((oc == 1).mean()), "p_trail": float((oc == 3).mean()), "p_cut": float((oc == 5).mean()),
            "p_target": float((oc == 0).mean()), "p_dist": float(((oc == 6) & ((sg & 1) > 0)).mean()),
            "p_climax": float(((oc == 6) & (sg == 2)).mean())}


def pb_exit_table(runs: Dict[str, pd.DataFrame], horizon: int, active: Sequence[str] = ()) -> pd.DataFrame:
    """One row per scope (every setup pooled, your active Setup-ledger setups pooled, each setup) and plan, on the
    trades every plan completed (same entries and initial stops; still-open trades are left out of all three).
    d_er / d_t: the plan's per-trade R less yours on the same trades, and the Newey-West t of its date averages;
    d_q: Benjamini-Hochberg across the per-setup comparisons. verdict: BETTER / WORSE at t 2 (q 0.10 per setup),
    else NO CLEAR DIFFERENCE, or TOO FEW under 30 trades."""
    if not runs or "yours" not in runs or not len(runs["yours"]):
        return pd.DataFrame()
    base = runs["yours"]
    keep = (base["status"] == 0) & ~base["setup"].astype(str).str.startswith("base:") & ~base["setup"].isin(L.RK_SKIP)
    for v, e in runs.items():
        keep &= (e["status"] == 0) & (e["outcome"] != 4) & np.isfinite(e["r"].astype(float))
    idx = base.index[keep.to_numpy()]
    if not len(idx):
        return pd.DataFrame()
    R = {v: e.loc[idx] for v, e in runs.items()}
    scopes = [("all", "Every setup", np.ones(len(idx), bool))]
    act = [s for s in active if s in set(base.loc[idx, "setup"])]
    if act:
        scopes.append(("active", "Your active setups", base.loc[idx, "setup"].isin(act).to_numpy()))
    for sid in sorted(base.loc[idx, "setup"].unique()):
        scopes.append((f"setup:{sid}", pb_setup_label("setup", sid), (base.loc[idx, "setup"] == sid).to_numpy()))
    rows = []
    for sk, lbl, m in scopes:
        for v in runs:
            x = R[v][m]
            st_ = _exit_stats(x, horizon)
            row = {"scope": sk, "scope_label": lbl, "variant": v, "variant_label": PB_EXIT_VARIANTS[v], **st_}
            if v != "yours" and len(x):
                d = pd.DataFrame({"date": x["date"].to_numpy(), "d": x["r"].to_numpy(float) - R["yours"][m]["r"].to_numpy(float)})
                dm = d.groupby("date")["d"].mean().sort_index().to_numpy()
                mu, se = L.lg_nw(dm, max(int(horizon), 1))
                tt = float(mu / se) if se and np.isfinite(se) and se > 0 else np.nan
                row.update({"d_er": float(d["d"].mean()), "d_t": tt,
                            "d_p": float(math.erfc(abs(tt) / math.sqrt(2))) if np.isfinite(tt) else np.nan})
            rows.append(row)
    T = pd.DataFrame(rows)
    for c in ("d_er", "d_t", "d_p"):
        if c not in T:
            T[c] = np.nan
    T["d_q"] = np.nan
    ps = T["scope"].str.startswith("setup:") & (T["variant"] != "yours")
    T.loc[ps, "d_q"] = L.lg_bh(T.loc[ps, "d_p"].to_numpy(float))

    def verdict(r_):
        if r_["variant"] == "yours":
            return ""
        if r_["n"] < PB_EXIT_MIN:
            return "TOO FEW"
        q_ok = (not str(r_["scope"]).startswith("setup:")) or (np.isfinite(r_["d_q"]) and r_["d_q"] <= PB_EXIT_Q)
        if np.isfinite(r_["d_t"]) and r_["d_t"] >= PB_EXIT_T and q_ok:
            return "BETTER"
        if np.isfinite(r_["d_t"]) and r_["d_t"] <= -PB_EXIT_T and q_ok:
            return "WORSE"
        return "NO CLEAR DIFFERENCE"
    T["verdict"] = T.apply(verdict, axis=1)
    return T


def pb_exit_wide(T: pd.DataFrame) -> pd.DataFrame:
    """Per setup, the three plans side by side: E[R] under each, the differences with their t and the verdicts."""
    if not len(T):
        return pd.DataFrame()
    rows = []
    for sk, g in T.groupby("scope", sort=False):
        g = g.set_index("variant")
        r_ = {"scope": sk, "setup": g["scope_label"].iloc[0], "n": int(g["n"].iloc[0])}
        for v in PB_EXIT_VARIANTS:
            if v in g.index:
                r_[f"er_{v}"] = g.at[v, "er"]
                if v != "yours":
                    r_[f"d_{v}"], r_[f"t_{v}"], r_[f"v_{v}"] = g.at[v, "d_er"], g.at[v, "d_t"], g.at[v, "verdict"]
        better = [v for v in ("trim_sig", "sig_only") if r_.get(f"v_{v}") == "BETTER"]
        r_["best"] = (max(better, key=lambda v: r_[f"er_{v}"]) if better else "yours")
        rows.append(r_)
    return pd.DataFrame(rows)


def pb_options(sbs: Dict[str, pd.DataFrame], bar: Dict[str, float]) -> pd.DataFrame:
    """Every setup x book the ledgers scored, with the bar it has to clear:
    - Setup ledger (shares, your exits): PROVEN and a deflated Sharpe of at least bar['dsr'].
    - Bull / Bear spreads, shares: PROVEN.
    - Bull / Bear spreads, debit or credit: the signal is PROVEN or PROMISING and the spread's own return on risk is
      positive at a Newey-West t of at least bar['t_spread'].
    PROPOSED = clears it; ON DECK = close (PROMISING, or a spread at t >= 2)."""
    rows = []
    for ledger, sb in sbs.items():
        if sb is None or not len(sb):
            continue
        a = sb[sb["split"] == "all"]
        for r in a.to_dict("records"):
            sid = r["setup_id"]
            if sid.startswith("base:") or sid in L.RK_SKIP:
                continue
            books = ["shares"] if ledger == "setup" else ["shares", "debit", "credit"]
            for book in books:
                m = PB_METRIC[book]
                v = r.get("verdict", "")
                rec = {"key": pb_key(ledger, sid, book), "ledger": ledger, "setup": sid, "book": book,
                       "label": pb_key_label(pb_key(ledger, sid, book)), "verdict": v, "events": r.get("events"),
                       "dates": r.get("dates"), "dsr": r.get("dsr", np.nan), "t_edge": r.get("t_xs"), "q": r.get("q")}
                if book == "shares":
                    rec["er"], rec["t_er"] = r.get("er_date"), r.get("t_r")
                    ok = v == "PROVEN" and (ledger != "setup" or L._n(r.get("dsr"), 0) >= bar["dsr"])
                    deck = v in ("PROVEN", "PROMISING")
                else:
                    rec["er"], rec["t_er"] = r.get(m), r.get(f"t_{m}")
                    good = L._n(rec["er"], -1) > 0
                    ok = v in ("PROVEN", "PROMISING") and good and L._n(rec["t_er"], 0) >= bar["t_spread"]
                    deck = good and L._n(rec["t_er"], 0) >= 2.0
                rec["proposal"] = "PROPOSED" if ok else ("ON DECK" if deck else "")
                rows.append(rec)
    return pd.DataFrame(rows)


def pb_kelly(x: np.ndarray, grid: int = 400) -> float:
    """The stake (share of equity lost at -1R) that maximizes the average log growth over these outcomes."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 20 or x.mean() <= 0:
        return 0.0
    worst = x.min()
    fmax = min(1.0, 0.999 / -worst) if worst < 0 else 1.0
    fs = np.linspace(0, fmax, grid)
    g = np.array([np.mean(np.log1p(f * x)) for f in fs])
    return float(fs[int(np.argmax(g))])


def pb_expect(ev: pd.DataFrame, sid: str, book: str, horizon: int, ledger_asof: str = "", plan: str = "") -> Dict[str, Any]:
    """A setup's expectation, frozen the day it's admitted: per-trade mean and spread of R (the book's own measure),
    the win rate, average win and loss, the date-averaged E[R] with its Newey-West t, and the full Kelly stake."""
    m = PB_METRIC[book]
    d = ev[(ev["setup"] == sid) & (ev["status"] == 0)] if len(ev) else ev
    x = d[m].to_numpy(float) if m in d else np.array([])
    ok = np.isfinite(x)
    x, dd = x[ok], d[ok] if len(d) else d
    if not len(x):
        return {"n": 0}
    dm = dd.groupby("date")[m].mean().sort_index()
    mu, se = L.lg_nw(dm.to_numpy(), max(int(horizon), 1))
    win, loss = x[x > 0], x[x <= 0]
    return {"n": int(len(x)), "dates": int(len(dm)), "mean": float(x.mean()), "sd": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
            "win": float((x > 0).mean()), "avg_win": float(win.mean()) if len(win) else 0.0,
            "avg_loss": float(loss.mean()) if len(loss) else 0.0,
            "payoff": float(win.mean() / abs(loss.mean())) if len(win) and len(loss) and loss.mean() < 0 else np.nan,
            "er_date": float(mu), "t": float(mu / se) if se and np.isfinite(se) and se > 0 else np.nan,
            "kelly": pb_kelly(x), "first": str(dd["date"].min())[:10], "last": str(dd["date"].max())[:10],
            "ledger_asof": ledger_asof, "plan": plan, "metric": m}


def pb_risk_pct(exp: Dict[str, Any], account: Dict[str, Any]) -> float:
    """Risk per trade, % of equity: the Kelly fraction you picked (half by default) of the setup's full Kelly,
    capped at your maximum."""
    k = L._n(exp.get("kelly"), 0.0) * float(account.get("kelly_frac", 0.5)) * 100.0
    return float(max(0.0, min(k, float(account.get("max_risk_pct", 1.0)))))


def pb_admit(pb: Dict[str, Any], key: str, ev: pd.DataFrame, horizon: int, ledger_asof: str, plan_tag: str,
             today: Optional[str] = None) -> Dict[str, Any]:
    ledger, sid, book = pb_split(key)
    exp = pb_expect(ev, sid, book, horizon, ledger_asof, plan_tag if ledger == "setup" else "the spread ledger's exits")
    pb["setups"][key] = {"ledger": ledger, "setup": sid, "book": book, "label": pb_key_label(key),
                         "admitted": today or date.today().isoformat(), "status": "active", "expect": exp}
    return pb


def pb_retire(pb: Dict[str, Any], key: str, why: str = "", today: Optional[str] = None) -> Dict[str, Any]:
    if key in pb["setups"]:
        pb["setups"][key]["status"] = "retired"
        pb["setups"][key]["retired"] = today or date.today().isoformat()
        pb["setups"][key]["why_retired"] = why
    return pb


def pb_active_setup_ids(pb: Dict[str, Any]) -> List[str]:
    """The Setup-ledger share setups in the playbook (what the exit lab's 'your active setups' pools)."""
    return [v["setup"] for v in pb_active(pb).values() if v.get("ledger") == "setup" and v.get("book") == "shares"]


def pb_active(pb: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {k: v for k, v in pb["setups"].items() if v.get("status") == "active"}


# ── tonight ──────────────────────────────────────────────────────────────────────────────────────────────────────
def pb_tonight(pb: Dict[str, Any], led: Dict[str, Dict[str, Any]], P: Optional[Dict[str, pd.DataFrame]],
               prm_setup: Dict[str, Any]) -> pd.DataFrame:
    """The ledgers' last-session signals from active playbook setups, each with its plan: entry, stop, the risk per
    share (or per spread), the risk in dollars at the playbook's sizing, and the size."""
    act = pb_active(pb)
    acc = pb["account"]
    eq = float(acc.get("equity", 0.0))
    rows = []
    ev = led["setup"]["ev"]
    keys_s = [k for k in act if pb_split(k)[0] == "setup"]
    if len(ev) and keys_s and P is not None:
        last = ev["date"].max()
        c = ev[(ev["date"] == last) & ev["setup"].isin([pb_split(k)[1] for k in keys_s])]
        C, H = P["close"], P["high"]
        cap = float(prm_setup.get("cap", 3.0))
        for r in c.to_dict("records"):
            key = pb_key("setup", r["setup"], "shares")
            t, d = r["ticker"], pd.Timestamp(r["date"])
            if t not in C.columns or d not in C.index:
                continue
            close, high = float(C.at[d, t]), float(H.at[d, t])
            k_atr = float(np.clip(L._n(r.get("plan_risk_atr"), np.nan), 0.5, cap))
            stop = close * (1 - k_atr * L._n(r.get("atr_pct"), np.nan) / 100.0)
            buy_stop = prm_setup.get("mode") == "buy_stop"
            ref = high * 1.0005 if buy_stop else close
            risk = ref - stop
            rp = pb_risk_pct(act[key]["expect"], acc)
            dollars = eq * rp / 100.0
            rows.append({"key": key, "ledger": "setup", "setup": r["setup"], "book": "shares", "side": "long",
                         "label": act[key]["label"], "ticker": t, "signal_date": str(d.date()), "close": close,
                         "entry_rule": (f"buy stop over {high:.2f} (the signal-day high), {int(prm_setup.get('win', 1))} "
                                        "session(s)" if buy_stop else
                                        "the ledger buys at the signal day's close: tomorrow, act in the last minutes "
                                        "when it fires (tonight's signal is past; the next open is the fallback)"
                                        if prm_setup.get("mode") == "close" else "buy at the next open"),
                         "plan_entry": ref, "plan_stop": stop, "risk_unit": risk, "risk_pct": rp, "risk_dollars": dollars,
                         "size": int(dollars // risk) if risk > 0 and dollars > 0 else 0,
                         "exp_r": act[key]["expect"].get("mean"), "legs": ""})
    for side in ("bull", "bear"):
        cands = led[side]["cands"]
        keys = [k for k in act if pb_split(k)[0] == side]
        if not len(cands) or not keys or "days_ago" not in cands:
            continue
        c = cands[cands["days_ago"] == cands["days_ago"].min()]
        for r in c.to_dict("records"):
            for book in ("shares", "debit", "credit"):
                key = pb_key(side, r["setup"], book)
                if key not in act:
                    continue
                rp = pb_risk_pct(act[key]["expect"], acc)
                dollars = eq * rp / 100.0
                s0, stp = L._n(r.get("signal_close"), np.nan), L._n(r.get("stop_plan"), np.nan)
                rec = {"key": key, "ledger": side, "setup": r["setup"], "book": book, "side": pb_side(side, book),
                       "label": act[key]["label"], "ticker": r["ticker"], "signal_date": str(pd.Timestamp(r["date"]).date()),
                       "close": s0, "risk_pct": rp, "risk_dollars": dollars, "exp_r": act[key]["expect"].get("mean")}
                if book == "shares":
                    risk = abs(s0 - stp)
                    rec.update({"entry_rule": f"{'sell short' if side == 'bear' else 'buy'} at the next open",
                                "plan_entry": s0, "plan_stop": stp, "risk_unit": risk, "legs": "",
                                "size": int(dollars // risk) if risk > 0 and dollars > 0 else 0})
                elif book == "debit":
                    deb = L._n(r.get("db_est"), np.nan)
                    rec.update({"entry_rule": "buy the debit spread", "legs": r.get("debit_legs", ""), "plan_entry": deb,
                                "plan_stop": np.nan, "risk_unit": deb * 100,
                                "size": int(dollars // (deb * 100)) if deb > 0 and dollars > 0 else 0})
                else:
                    cr, po = L._n(r.get("cr_est"), np.nan), L._n(r.get("cr_payoff"), np.nan)
                    ml = cr / po if po and np.isfinite(po) and po > 0 else np.nan
                    rec.update({"entry_rule": "sell the credit spread", "legs": r.get("credit_legs", ""), "plan_entry": cr,
                                "plan_stop": np.nan, "risk_unit": ml * 100 if np.isfinite(ml) else np.nan,
                                "size": int(dollars // (ml * 100)) if np.isfinite(ml) and ml > 0 and dollars > 0 else 0})
                rows.append(rec)
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["exp_r"], ascending=False).reset_index(drop=True)
    return out


# ── the journal ──────────────────────────────────────────────────────────────────────────────────────────────────
def jr_empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=object if c in PB_TXT_COLS else float) for c in JOURNAL_COLS})


def jr_clean(J: pd.DataFrame) -> pd.DataFrame:
    J = J.copy()
    for c in JOURNAL_COLS:
        if c not in J:
            J[c] = "" if c in PB_TXT_COLS else np.nan
    for c in JOURNAL_COLS:
        if c in PB_TXT_COLS:
            J[c] = J[c].astype(object).where(J[c].notna(), "").astype(str).replace({"nan": "", "None": "", "NaT": ""})
        else:
            J[c] = pd.to_numeric(J[c], errors="coerce")
    J["id"] = [i if i else uuid.uuid4().hex[:10] for i in J["id"]]
    J["ticker"] = J["ticker"].str.upper().str.strip()
    J["status"] = J["status"].where(J["status"].isin(PB_STATUS), "open")
    return J[JOURNAL_COLS].reset_index(drop=True)


def jr_load() -> pd.DataFrame:
    f = f_journal()
    if not f.exists():
        return jr_empty()
    try:
        return jr_clean(pd.read_csv(f, dtype={c: str for c in PB_TXT_COLS}, keep_default_na=False, na_values=[""]))
    except Exception:
        return jr_empty()


def jr_save(J: pd.DataFrame) -> None:
    _atomic_csv(jr_clean(J), f_journal())


def jr_new_rows(T: pd.DataFrame) -> pd.DataFrame:
    """Planned trades from tonight's rows."""
    if T is None or not len(T):
        return jr_empty()
    J = pd.DataFrame({"id": [uuid.uuid4().hex[:10] for _ in range(len(T))], "status": "planned", "ticker": T["ticker"],
                      "key": T["key"], "ledger": T["ledger"], "setup": T["setup"], "book": T["book"], "side": T["side"],
                      "signal_date": T["signal_date"], "plan_entry": T["plan_entry"], "plan_stop": T["plan_stop"],
                      "plan_size": T["size"], "notes": T.get("legs", "")})
    return jr_clean(J)


def jr_from_book(book: pd.DataFrame, J: pd.DataFrame) -> pd.DataFrame:
    """Open share positions from the Book that aren't in the journal yet (same ticker and entry date)."""
    if book is None or not len(book):
        return jr_empty()
    b = book[(book.get("sleeve", "shares") == "shares") & book["ticker"].notna()].copy()
    have = set(zip(J["ticker"], J["entry_date"])) if len(J) else set()
    rows = []
    for r in b.to_dict("records"):
        t, ed = str(r["ticker"]).upper().strip(), str(r.get("entry_date") or "")[:10]
        if (t, ed) in have or not np.isfinite(L._n(r.get("entry"), np.nan)):
            continue
        sid = L.pos_setup_id(str(r.get("setup") or "")) if str(r.get("setup") or "") else ""
        stop0 = L._n(r.get("init_stop"), np.nan)
        rows.append({"status": "open", "ticker": t, "key": pb_key("setup", sid, "shares") if sid else "",
                     "ledger": "setup" if sid else "", "setup": sid, "book": "shares", "side": "long", "entry_date": ed,
                     "entry_px": r.get("entry"), "size": r.get("shares"),
                     "init_stop": stop0 if np.isfinite(stop0) else r.get("stop"), "notes": str(r.get("note") or "")})
    return jr_clean(pd.DataFrame(rows)) if rows else jr_empty()


def jr_r(J: pd.DataFrame, last_close: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """Each trade's R on your own risk unit. Shares: P&L per share over the risk to the initial stop, with a trim at its
    price and the rest at the exit (open trades marked at the last close as r_open). Debit spreads: (exit value less
    the debit) over the max loss (the debit unless given). Credit spreads: (credit less the cost to close) over the max
    loss (the width less the credit, required)."""
    J = jr_clean(J)
    last_close = last_close or {}
    r, r_open, unit = [], [], []
    for x in J.to_dict("records"):
        e, sz = L._n(x["entry_px"], np.nan), L._n(x["size"], np.nan)
        tq = min(max(L._n(x["trim_qty"], 0.0), 0.0), sz) if np.isfinite(sz) else 0.0
        tp, xp = L._n(x["trim_px"], np.nan), L._n(x["exit_px"], np.nan)
        book = x["book"] or "shares"
        sg = -1.0 if (book == "shares" and x["side"] == "short") else 1.0
        if book == "shares":
            ru = sg * (e - L._n(x["init_stop"], np.nan))
        elif book == "debit":
            ru = L._n(x["max_risk"], np.nan)
            ru = e if not np.isfinite(ru) else ru
        else:
            ru = L._n(x["max_risk"], np.nan)
        unit.append(ru)

        def blend(rest_px):
            if not (np.isfinite(sz) and sz > 0 and np.isfinite(rest_px)):
                return np.nan
            if tq > 0 and np.isfinite(tp):
                return (tq * tp + (sz - tq) * rest_px) / sz
            return rest_px
        ok = np.isfinite(e) and np.isfinite(ru) and ru > 0
        if x["status"] == "closed" and ok:
            px = blend(xp)
            pnl = (px - e) * sg if book != "credit" else (e - px)
            r.append(pnl / ru if np.isfinite(px) else np.nan)
        else:
            r.append(np.nan)
        lc = L._n(last_close.get(x["ticker"]), np.nan)
        if x["status"] == "open" and ok and book == "shares" and np.isfinite(lc):
            r_open.append((blend(lc) - e) * sg / ru)
        else:
            r_open.append(np.nan)
    J["r"], J["r_open"], J["risk_unit"] = r, r_open, unit
    return J


# ── the edge tracker ─────────────────────────────────────────────────────────────────────────────────────────────
def pb_match(J: pd.DataFrame, evs: Dict[str, pd.DataFrame], look: int = 5) -> pd.DataFrame:
    """Each journal trade next to the ledger's own version of the same signal (same ledger, setup, ticker and signal
    date; without a signal date, the latest signal of that setup on that ticker in the `look` days up to the entry).
    Adds ledger_r (the book's measure), the ledger's entry and stop, whether the ledger trade is closed, the entry
    cost in R (what your fill cost against the ledger's, positive = worse), the gap (your R less the ledger's) and
    the rest of the gap (exits, trims, sizing of the stop)."""
    J = J.copy()
    cols = {c: np.full(len(J), np.nan) for c in ("ledger_r", "ledger_entry", "ledger_stop", "ledger_debit", "ledger_credit",
                                                 "ledger_risk", "entry_cost_r", "gap_r", "exit_r")}
    found = np.zeros(len(J), bool)
    lstat = np.full(len(J), "", object)
    sdate = J["signal_date"].astype(str).to_numpy().copy()
    for i, x in enumerate(J.to_dict("records")):
        ev = evs.get(x["ledger"])
        if ev is None or not len(ev) or not x["setup"]:
            continue
        g = ev[(ev["setup"] == x["setup"]) & (ev["ticker"] == x["ticker"])]
        if not len(g):
            continue
        if x["signal_date"]:
            g = g[g["date"] == pd.Timestamp(x["signal_date"])]
        elif x["entry_date"]:
            ed = pd.Timestamp(x["entry_date"])
            g = g[(g["date"] <= ed) & (g["date"] >= ed - pd.Timedelta(days=look))].sort_values("date").tail(1)
        if not len(g):
            continue
        e = g.iloc[0]
        found[i] = True
        sdate[i] = str(pd.Timestamp(e["date"]).date())
        m = PB_METRIC.get(x["book"] or "shares", "r")
        st0, oc = int(L._n(e.get("status"), 3)), int(L._n(e.get("outcome"), -1))
        lstat[i] = "closed" if (st0 == 0 and oc != 4) else ("open" if st0 == 0 else ("no fill" if st0 in (1, 2) else "pending"))
        cols["ledger_r"][i] = L._n(e.get(m), np.nan) if st0 == 0 else np.nan
        le, ls = L._n(e.get("entry"), np.nan), L._n(e.get("stop"), np.nan)
        cols["ledger_entry"][i], cols["ledger_stop"][i] = le, ls
        cols["ledger_debit"][i], cols["ledger_credit"][i] = L._n(e.get("db_debit"), np.nan), L._n(e.get("cr_credit"), np.nan)
        book = x["book"] or "shares"
        fill = L._n(x["entry_px"], np.nan)
        if book == "shares":
            sg = -1.0 if x["side"] == "short" else 1.0
            risk = abs(le - ls)
            cols["ledger_risk"][i] = risk
            cols["entry_cost_r"][i] = sg * (fill - le) / risk if risk > 0 else np.nan
        elif book == "debit":
            d0 = cols["ledger_debit"][i]
            cols["ledger_risk"][i] = d0
            cols["entry_cost_r"][i] = (fill - d0) / d0 if np.isfinite(d0) and d0 > 0 else np.nan
        else:
            c0, rk = cols["ledger_credit"][i], L._n(e.get("cr_risk"), np.nan)
            cols["ledger_risk"][i] = rk
            cols["entry_cost_r"][i] = (c0 - fill) / rk if np.isfinite(rk) and rk > 0 else np.nan
    for k, v in cols.items():
        J[k] = v
    J["matched"], J["ledger_status"], J["signal_date"] = found, lstat, sdate
    you = J["r"].to_numpy(float) if "r" in J else np.full(len(J), np.nan)
    J["gap_r"] = np.where(np.isfinite(you) & np.isfinite(J["ledger_r"].to_numpy(float)), you - J["ledger_r"].to_numpy(float), np.nan)
    J["exit_r"] = J["gap_r"] + J["entry_cost_r"].fillna(0.0)
    return J


def pb_decompose(Jm: pd.DataFrame, ev_all: pd.DataFrame, key: str, since: str) -> Dict[str, Any]:
    """Where your result comes from, for one playbook setup since it was admitted (your list only):
    - every signal: the ledger's average over all of the setup's completed signals;
    - your picks: the ledger's average over the signals you took (selection = picks less every signal);
    - you: your average on those same trades (implementation = you less your picks, trade by trade)."""
    ledger, sid, book = pb_split(key)
    m = PB_METRIC[book]
    out = {"key": key, "n_all": 0, "e_all": np.nan, "n_pick": 0, "e_pick": np.nan, "e_you": np.nan,
           "selection": np.nan, "implementation": np.nan}
    if ev_all is not None and len(ev_all) and m in ev_all:
        a = ev_all[(ev_all["setup"] == sid) & (ev_all["status"] == 0) & (ev_all["date"] >= pd.Timestamp(since))]
        if "outcome" in a:
            a = a[a["outcome"] != 4]
        x = a[m].to_numpy(float)
        x = x[np.isfinite(x)]
        out["n_all"], out["e_all"] = int(len(x)), float(x.mean()) if len(x) else np.nan
    if Jm is not None and len(Jm):
        j = Jm[(Jm["key"] == key) & Jm["matched"] & (Jm["ledger_status"] == "closed") & np.isfinite(Jm["r"].astype(float))
               & np.isfinite(Jm["ledger_r"].astype(float))]
        if len(j):
            out["n_pick"] = int(len(j))
            out["e_pick"] = float(j["ledger_r"].mean())
            out["e_you"] = float(j["r"].mean())
            out["implementation"] = out["e_you"] - out["e_pick"]
            if np.isfinite(out["e_all"]):
                out["selection"] = out["e_pick"] - out["e_all"]
    return out


def pb_live(x: Sequence[float], exp: Dict[str, Any]) -> Dict[str, Any]:
    """A setup's live record against its frozen expectation: the running total against n x E with a 90% band
    (+-1.645 x sd x sqrt(n)), its z, and Wald's sequential test of 'no edge' (mean 0) against the frozen edge
    (log-likelihood ratio on a normal approximation; 9 to 1 either way decides).
    Status: NEW (under 5 trades), RETIRE (the record fits no edge 9 to 1 better), REVIEW (under the band),
    WATCH (in the lower part of the band), KEEP (otherwise; 'confirmed' once the test favours the edge 9 to 1).
    Trades needed: about (2 sd / E)^2 before the live record alone would show the edge at t 2."""
    x = np.asarray([v for v in x if np.isfinite(v)], float)
    n = len(x)
    E, sd = L._n(exp.get("mean"), np.nan), L._n(exp.get("sd"), np.nan)
    out = {"n": n, "mean": float(x.mean()) if n else np.nan, "cum": float(x.sum()) if n else 0.0,
           "exp_cum": n * E if np.isfinite(E) else np.nan, "band": PB_Z90 * sd * math.sqrt(n) if n and np.isfinite(sd) else np.nan,
           "z": np.nan, "llr": np.nan, "needed": int(math.ceil((2 * sd / E) ** 2)) if np.isfinite(E) and E > 0 and np.isfinite(sd) else None,
           "status": "NEW", "confirmed": False}
    if n and np.isfinite(E) and np.isfinite(sd) and sd > 0:
        out["z"] = (out["cum"] - n * E) / (sd * math.sqrt(n))
        out["llr"] = (n * E * E - 2 * E * x.sum()) / (2 * sd * sd)
        out["confirmed"] = out["llr"] <= -PB_SPRT
    if n < 5:
        return out
    if np.isfinite(out["llr"]) and out["llr"] >= PB_SPRT:
        out["status"] = "RETIRE"
    elif np.isfinite(out["z"]) and out["z"] < -PB_Z90:
        out["status"] = "REVIEW"
    elif np.isfinite(out["z"]) and out["z"] < -1.0:
        out["status"] = "WATCH"
    else:
        out["status"] = "KEEP"
    return out


def pb_band_path(x: Sequence[float], exp: Dict[str, Any]) -> pd.DataFrame:
    """Trade by trade: your running total, the expected path and the 90% band."""
    x = [v for v in x if np.isfinite(v)]
    E, sd = L._n(exp.get("mean"), 0.0), L._n(exp.get("sd"), 0.0)
    n = np.arange(1, len(x) + 1)
    return pd.DataFrame({"trade": n, "you": np.cumsum(x), "expected": n * E,
                         "lo": n * E - PB_Z90 * sd * np.sqrt(n), "hi": n * E + PB_Z90 * sd * np.sqrt(n)})


def pb_skipped(ev: pd.DataFrame, J: pd.DataFrame, key: str, since: str) -> pd.DataFrame:
    """The setup's signals on your list since it was admitted that aren't in the journal, with what the ledger made
    on them (completed ones) or that they're still open."""
    ledger, sid, book = pb_split(key)
    if ev is None or not len(ev):
        return pd.DataFrame()
    m = PB_METRIC[book]
    s = ev[(ev["setup"] == sid) & (ev["date"] >= pd.Timestamp(since))].copy()
    if not len(s):
        return s
    took = set()
    if J is not None and len(J):
        j = J[J["key"] == key]
        took = set(zip(j["ticker"], j["signal_date"].astype(str)))
    s["signal_date"] = pd.DatetimeIndex(s["date"]).strftime("%Y-%m-%d")
    s = s[[(t, d) not in took for t, d in zip(s["ticker"], s["signal_date"])]]
    s["ledger_r"] = np.where(s["status"] == 0, s[m] if m in s else np.nan, np.nan)
    s["state"] = np.where(s["status"] == 0, np.where(s.get("outcome", 0) == 4, "open", "closed"), "pending or no fill")
    return s[["ticker", "signal_date", "state", "ledger_r"]].sort_values("signal_date", ascending=False).reset_index(drop=True)


def pb_tracker(pb: Dict[str, Any], Jm: pd.DataFrame, evs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per playbook setup (active and retired): live record, frozen expectation, decomposition, status."""
    rows = []
    for key, s in pb["setups"].items():
        exp = s.get("expect") or {}
        j = Jm[(Jm["key"] == key) & (Jm["status"] == "closed")] if len(Jm) else Jm
        lv = pb_live(j["r"].astype(float).tolist() if len(j) else [], exp)
        dc = pb_decompose(Jm, evs.get(s["ledger"]), key, s.get("admitted", "1900-01-01"))
        rows.append({"key": key, "label": s.get("label", pb_key_label(key)), "state": s.get("status"),
                     "admitted": s.get("admitted"), "exp_mean": exp.get("mean"), "exp_sd": exp.get("sd"),
                     "exp_n": exp.get("n"), **{f"live_{k}": v for k, v in lv.items()}, **{k: dc[k] for k in
                     ("n_all", "e_all", "n_pick", "e_pick", "e_you", "selection", "implementation")}})
    return pd.DataFrame(rows)


def pb_review(Jm: pd.DataFrame, freq: str = "W") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Closed trades by week (W) or month (M): trades, total and average R, the implementation gap, discipline (no
    deviation tag and an entry within 0.1R of the ledger's), chased entries (tagged, or 0.25R+ worse than the ledger);
    and what each deviation cost on average (your R less the ledger's)."""
    c = Jm[(Jm["status"] == "closed") & np.isfinite(Jm["r"].astype(float))].copy() if len(Jm) else pd.DataFrame()
    if not len(c):
        return pd.DataFrame(), pd.DataFrame()
    c["when"] = pd.to_datetime(c["exit_date"].replace("", np.nan), errors="coerce")
    c = c[c["when"].notna()]
    if not len(c):
        return pd.DataFrame(), pd.DataFrame()
    c["period"] = c["when"].dt.to_period("W-FRI" if freq == "W" else "M").astype(str)
    ec = c["entry_cost_r"].astype(float)
    c["disciplined"] = (c["deviation"] == "") & ((ec.abs() <= 0.1) | ec.isna())
    c["chased"] = (c["deviation"] == "chased") | (ec > 0.25)
    g = c.groupby("period")
    per = pd.DataFrame({"trades": g.size(), "total_r": g["r"].sum(), "mean_r": g["r"].mean(),
                        "gap_r": g["gap_r"].mean(), "entry_cost_r": g["entry_cost_r"].mean(),
                        "discipline": g["disciplined"].mean(), "chased": g["chased"].sum(),
                        "off_playbook": g["key"].apply(lambda s: int((s == "").sum()))}).reset_index().sort_values("period", ascending=False)
    d = c.assign(dev=c["deviation"].replace("", "followed the plan")).groupby("dev")
    dev = pd.DataFrame({"trades": d.size(), "mean_r": d["r"].mean(), "mean_gap_r": d["gap_r"].mean(),
                        "total_gap_r": d["gap_r"].sum()}).reset_index().rename(columns={"dev": "deviation"}).sort_values("total_gap_r")
    return per, dev


# ── loading everything ───────────────────────────────────────────────────────────────────────────────────────────
def pb_cfg(source: Optional[str] = None) -> Dict[str, Any]:
    """The lab's data settings without its sidebar: the source (Massive with a key, else Yahoo; LAB_SOURCE or the
    argument overrides), the universe file the lab finds, today's bar handling."""
    key = L._secret("MASSIVE_API_KEY") or L._secret("POLYGON_API_KEY")
    src = (source or os.getenv("LAB_SOURCE") or ("massive" if key else "yahoo")).lower()
    p = L.find_default_universe()
    if p is not None:
        uni, name = L.read_universe(p.read_bytes(), p.name), p.name
    else:
        uni, name = L.demo_universe(), "built-in demo list"
    uni = L.merge_themes(uni)
    return {"source": src, "key": key if src == "massive" else None, "strip": True, "uni": uni, "uni_name": name,
            "drop_partial": True, "price_neutral": True, "min_group": 5, "refuse": set(L.REFUSE_DEFAULT)}


def pb_bars(cfg: Dict[str, Any], progress=None) -> Tuple[Dict[str, pd.DataFrame], Optional[Dict[str, pd.DataFrame]]]:
    bars, _ = L.get_bars(list(cfg["uni"]["ticker"]), L.UNIVERSE_DAYS, cfg["source"], cfg["key"], cfg["drop_partial"], progress,
                         "Universe")
    P = L.panel_from_bars(bars) if len(bars) >= 2 else None
    return bars, P


def pb_state(pb: Dict[str, Any], P: Optional[Dict[str, pd.DataFrame]], led: Optional[Dict[str, Dict[str, Any]]] = None
             ) -> Dict[str, Any]:
    """Everything the pages and the nightly report read, from the saved files and the bars."""
    led = led or pb_read_ledgers()
    prm = pb_ledger_prm(led["setup"]["meta"])
    tag = pb_plan_tag(pb["plan"])
    ev_plan = pd.DataFrame()
    if len(led["setup"]["ev"]) and P is not None:
        ev_plan = pb_relabel(led["setup"]["ev"], P, prm, pb["plan"], tag=f"{led['setup']['mtime']}")
    sbs = pb_scoreboards(led, ev_plan, prm)
    opts = pb_options(sbs, pb["bar"])
    evs = {"setup": ev_plan, "bull": led["bull"]["ev"], "bear": led["bear"]["ev"]}
    last_close = {t: float(P["close"][t].dropna().iloc[-1]) for t in P["close"].columns
                  if P["close"][t].notna().any()} if P is not None else {}
    J = jr_r(jr_load(), last_close)
    Jm = pb_match(J, evs) if len(J) else J.assign(**{c: np.nan for c in ("ledger_r", "entry_cost_r", "gap_r", "exit_r")},
                                                  matched=False, ledger_status="")
    return {"led": led, "prm": prm, "plan_tag": tag, "ev_plan": ev_plan, "sbs": sbs, "opts": opts, "evs": evs,
            "J": Jm, "tonight": pb_tonight(pb, led, P, prm), "tracker": pb_tracker(pb, Jm, evs) if pb["setups"] else pd.DataFrame(),
            "last_close": last_close}


def pb_report(pb: Dict[str, Any], S: Dict[str, Any]) -> str:
    """The nightly report: the playbook, tonight's signals, the tracker, new proposals."""
    lines = [f"# Playbook report, {date.today().isoformat()}", ""]
    meta = S["led"]["setup"]["meta"]
    lines.append(f"Setup ledger as of {meta.get('asof', '?')} ({meta.get('source', 'source not recorded')}); "
                 f"your exits: {S['plan_tag']}.")
    act = pb_active(pb)
    lines += ["", f"## Active setups ({len(act)})"]
    T = S["tracker"]
    for k, s in act.items():
        tr = T[T["key"] == k].iloc[0] if len(T) and (T["key"] == k).any() else None
        e = s.get("expect") or {}
        st_ = f"{tr['live_status']}, {int(tr['live_n'])} live trades, {L._n(tr['live_cum'], 0):+.2f}R" if tr is not None else "no trades"
        lines.append(f"- {s['label']}: frozen E {L._n(e.get('mean'), np.nan):+.2f}R per trade (n {e.get('n', 0)}); {st_}")
    tn = S["tonight"]
    lines += ["", f"## Tonight ({len(tn)} signal{'s' if len(tn) != 1 else ''})"]
    for r in tn.to_dict("records"):
        lines.append(f"- {r['ticker']} · {r['label']}: {r['entry_rule']}, stop {L._n(r['plan_stop'], np.nan):.2f}, "
                     f"size {r['size']} at {r['risk_pct']:.2f}% risk")
    pro = S["opts"][S["opts"]["proposal"] == "PROPOSED"] if len(S["opts"]) else pd.DataFrame()
    pro = pro[~pro["key"].isin(list(pb["setups"]))] if len(pro) else pro
    lines += ["", f"## Proposed, not in the playbook yet ({len(pro)})"]
    for r in pro.to_dict("records"):
        lines.append(f"- {r['label']} ({PB_LEDGERS[r['ledger']]}): E {L._n(r['er'], np.nan):+.3f}, t {L._n(r['t_er'], np.nan):+.1f}")
    XT = S.get("exit_lab")
    if XT is not None and len(XT):
        lines += ["", "## Exit lab: your plan against exit signals (same trades)", f"Signals: {pb_sig_txt(pb['plan'])}."]
        for sk in ("active", "all"):
            g = XT[XT["scope"] == sk]
            if not len(g):
                continue
            bits = []
            for r in g.to_dict("records"):
                b_ = f"{PB_EXIT_SHORT[r['variant']]} {L._n(r['er'], np.nan):+.3f}R"
                if r["variant"] != "yours":
                    b_ += f" ({L._n(r['d_er'], np.nan):+.3f}, t {L._n(r['d_t'], np.nan):+.1f}: {r['verdict']})"
                bits.append(b_)
            lines.append(f"- {g['scope_label'].iloc[0]}, {int(g['n'].iloc[0]):,} trades: " + "; ".join(bits))
        W = pb_exit_wide(XT)
        W = W[W["scope"].str.startswith("setup:") & (W["best"] != "yours")] if len(W) else W
        for r in W.to_dict("records"):
            lines.append(f"- {r['setup']}: {PB_EXIT_SHORT[r['best']]} beats your plan by "
                         f"{L._n(r.get('d_' + r['best']), np.nan):+.3f}R a trade (t {L._n(r.get('t_' + r['best']), np.nan):+.1f}, {r['n']} trades)")
    return "\n".join(lines) + "\n"


def nightly(source: Optional[str] = None, limit: int = 0, log=print, exit_lab: bool = True) -> Dict[str, Any]:
    """Rebuild the Setup ledger and both spread ledgers on your list (the lab's code and defaults), save them where
    the lab does, then write tonight's signals and the report."""
    t0 = time.time()
    cfg = pb_cfg(source)
    if cfg["source"] == "massive" and not cfg["key"]:
        log("No Massive key: set MASSIVE_API_KEY or put it in .streamlit/secrets.toml (or use --source yahoo).")
        return {"ok": False}
    if limit:
        cfg["uni"] = cfg["uni"].head(int(limit))
    log(f"Source: {cfg['source']}; universe: {len(cfg['uni'])} names from {cfg['uni_name']}")
    bench, _ = L.get_bars(["SPY"], L.BENCH_DAYS, cfg["source"], cfg["key"], True)
    spy = bench["SPY"]["close"] if "SPY" in bench else None
    bars, P = pb_bars(cfg)
    if P is None:
        log("No bars loaded.")
        return {"ok": False}
    log(f"Bars for {len(bars)} names through {P['close'].index[-1].date()} ({time.time() - t0:.0f}s)")
    groups, _ = L.resolve_groups(cfg["uni"], 5)
    ab = L.alpha_block(bars, groups, True, 5)
    led_old = pb_read_ledgers()
    prm = pb_ledger_prm(led_old["setup"]["meta"])
    setting = (led_old["setup"]["meta"] or {}).get("setting", "12/26/9")
    run = L.lg_run(ab["P"], spy, None, tuple(L.LG_FAMILIES), setting, prm, "Your list", None,
                   extra={"alpha_pct": ab["composite"]})
    sb, _ = L.lg_score(run["ev"], "none", 0.4, int(prm["horizon"]))
    vmap = L.lg_verdict_map(sb, setting, "Your list", prm)
    vmap["source"] = cfg["source"]
    vmap["prm_full"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in prm.items()}
    _atomic_parquet(run["ev"].assign(universe="list").drop(columns=["outcome_txt", "status_txt"], errors="ignore"),
                    f_ledger("setup"))
    L.atomic_write_json(f_meta("setup"), json.loads(json.dumps(vmap, default=_json_default)))
    log(f"Setup ledger: {len(run['ev']):,} events ({time.time() - t0:.0f}s)")
    for side in ("bull", "bear"):
        prm_b = pb_br_prm(side, led_old[side]["meta"])
        Pb, _ = L.br_list_panel(cfg, ab, with_former=side == "bear")
        rb = L.br_run(Pb, spy, None, prm_b, "Your list + former leaders" if side == "bear" else "Your list")
        msg = L.br_save(side, {"run": rb, "which": "list"}, prm_b, cfg["source"], 0.4, folder=pb_dir())
        log(f"{PB_LEDGERS[side]}: {msg} ({time.time() - t0:.0f}s)")
    pb = pb_load()
    S = pb_state(pb, P)
    if exit_lab and len(S["led"]["setup"]["ev"]):
        runs = pb_exit_runs(S["led"]["setup"]["ev"], P, S["prm"], pb["plan"], tag=f"{S['led']['setup']['mtime']}")
        S["exit_lab"] = pb_exit_table(runs, int(S["prm"]["horizon"]), pb_active_setup_ids(pb))
        log(f"Exit lab: {len(S['exit_lab'])} rows ({time.time() - t0:.0f}s)")
    _atomic_csv(S["tonight"], f_tonight())
    _atomic_text(pb_report(pb, S), f_report())
    log(f"Tonight: {len(S['tonight'])} signal(s) from {len(pb_active(pb))} active setup(s); report in {f_report().name} "
        f"({time.time() - t0:.0f}s)")
    return {"ok": True, "state": S, "secs": time.time() - t0}


# ── the app ──────────────────────────────────────────────────────────────────────────────────────────────────────
PB_GUIDE = """
**The idea.** Edge first: only setups the lab's tests passed go in, each with what it should pay written down the
day it goes in. Then every trade is scored twice, once by you and once by the ledger on the exact same signal, so the
difference (what your entries, exits and choices did to the edge) shows up in weeks rather than the hundreds of trades
a live record needs on its own. It's how a professional bettor works: bet only with a measured edge, size it to
survive, and check every bet against the fair price.

**Admission.** The Setup ledger is re-run under your trim-and-trail plan (Settings) and scored by the lab's own
rules: PROVEN means the signal beats a random uptrend name at t 3+ with a false-discovery q of 0.10 or less, the
holdout agrees and it pays after costs; on top of that the deflated Sharpe has to reach 0.95 (it allows for how many
setups were tried). Spread setups from Bull and Bear spreads need the signal PROVEN or PROMISING and the spread's own
return on risk positive at t 2.5+. ON DECK is close. You confirm each one; admitting freezes its expectation (per-trade
mean, spread, win rate, payoff and the full Kelly stake) so the goalposts never move.

**Sizing.** Risk per trade = your Kelly fraction (half by default) of the setup's full Kelly stake, capped at your
maximum. Kelly here is the stake that maximizes average log growth over the setup's own outcomes.

**The tracker.**
- *Entry cost:* your fill against the ledger's on the same signal, in R. Positive means you paid more (chased).
- *Gap:* your R less the ledger's R; the rest after the entry cost is exits, trims and your stop.
- *Selection:* the ledger's average on the signals you took, less its average on every playbook signal since the
  setup was admitted. Positive means your choices add something; negative means take them all.
- *Implementation:* your average less the ledger's on the same trades.
- *Live record:* running R against the expected path and a 90% band. KEEP while it's inside; WATCH in the lower part;
  REVIEW under the band; RETIRE when Wald's sequential test finds the record fits no edge 9 to 1 better than the
  frozen one. A live record alone needs about (2 sd / E)^2 trades to show an edge at t 2: usually 50 to 200.

**Options.** Spread trades are scored on return on max risk and compared with the spread ledgers' own trades (their
exits follow the share trade's, not your trim and trail). Entry cost is your debit (or credit) against the ledger's
estimate.

**Files.** data/playbook.json, data/playbook_journal.csv; the nightly run (python playbook.py nightly) also writes
playbook_tonight.csv and playbook_report.md. The lab writes the ledgers this reads when you build them.
"""


def _app_state(pb: Dict[str, Any], source: str):
    import streamlit as st
    cfg = pb_cfg(source)
    stamp = (date.today().isoformat(), L.session_phase(), cfg["source"])
    ss = st.session_state
    if ss.get("_pb_bars_stamp") != stamp:
        prog = st.progress(0.0, text="Universe")
        bars, P = pb_bars(cfg, prog)
        prog.empty()
        ss["_pb_bars_stamp"], ss["_pb_P"], ss["_pb_cfg"] = stamp, P, cfg
    return ss["_pb_cfg"], ss["_pb_P"]


def app() -> None:
    import streamlit as st
    st.set_page_config(page_title="Playbook", page_icon="◈", layout="wide")
    L.md(L.CSS)
    ss = st.session_state
    sb = st.sidebar
    L.md("<div class='mast-title' style='font-size:.9rem'>PLAYBOOK</div>", sb)
    env_key = L._secret("MASSIVE_API_KEY") or L._secret("POLYGON_API_KEY")
    default_src = (os.getenv("LAB_SOURCE") or ("massive" if env_key else "yahoo")).lower()
    opts_src = ["massive", "yahoo", "demo"]
    source = sb.radio("Data source", opts_src, index=opts_src.index(default_src) if default_src in opts_src else 1,
                      format_func={"massive": "Massive (API key)", "yahoo": "Yahoo daily bars", "demo": "Demo (synthetic)"}.get)
    if sb.button("Reload the ledgers and bars"):
        L.clear_bar_store()
        ss.pop("_pb_bars_stamp", None)
    sb.caption(f"Data folder: {pb_dir()}")
    pb = pb_load()
    cfg, P = _app_state(pb, source)
    S = pb_state(pb, P)
    led = S["led"]
    meta = led["setup"]["meta"]
    L.md("<div class='mast'><div class='mast-title'>PLAYBOOK</div>"
         f"<div class='mast-meta'>Setup ledger as of {L._esc(meta.get('asof', 'not built'))}"
         f" · {L._esc(meta.get('source', 'source not recorded'))}<br/>Your exits: {L._esc(S['plan_tag'])}<br/>"
         f"Bars: {L._esc(cfg['source'])}, through {L._esc(str(P['close'].index[-1].date()) if P is not None else 'none')}</div></div>")
    if not len(led["setup"]["ev"]) and not len(led["bull"]["ev"]) and not len(led["bear"]["ev"]):
        L.warnbox("Playbook: no ledgers saved yet. Build the Setup ledger (Stocks) and Bull or Bear spreads (Options) in "
                  "the lab, or run `python playbook.py nightly`.")
    if meta.get("source") == "demo" or (led["bull"]["meta"] or {}).get("source") == "demo":
        L.warnbox("Playbook: a saved ledger was built on demo (synthetic) data. Rebuild it on Massive or Yahoo before "
                  "trusting anything here.")
    tabs = st.tabs(["Playbook", "Tonight", "Journal", "Edge tracker", "Exit lab", "Review"])
    with tabs[0]:
        _page_playbook(pb, S)
    with tabs[1]:
        _page_tonight(pb, S)
    with tabs[2]:
        _page_journal(pb, S)
    with tabs[3]:
        _page_tracker(pb, S)
    with tabs[4]:
        _page_exit_lab(pb, S, P)
    with tabs[5]:
        _page_review(pb, S)


def _P_():
    import streamlit as st
    return st.column_config.NumberColumn


def _page_playbook(pb: Dict[str, Any], S: Dict[str, Any]) -> None:
    import streamlit as st
    P_ = _P_()
    act = pb_active(pb)
    opts = S["opts"]
    pro = opts[(opts["proposal"] == "PROPOSED") & ~opts["key"].isin(list(pb["setups"]))] if len(opts) else opts
    deck = opts[(opts["proposal"] == "ON DECK") & ~opts["key"].isin(list(pb["setups"]))] if len(opts) else opts
    retired = {k: v for k, v in pb["setups"].items() if v.get("status") == "retired"}
    T = S["tracker"]
    L.kpi_row([L.kpi_html("Active setups", len(act), "in the playbook", "good" if act else ""),
               L.kpi_html("Proposed", len(pro), "clear the bar, not admitted yet", "warn" if len(pro) else ""),
               L.kpi_html("On deck", len(deck), "close to the bar"),
               L.kpi_html("Retired", len(retired), "kept with their record")])
    L.sec("1 · In the playbook")
    if not act:
        L.note("Nothing admitted yet. Admit from the proposals below (or add one by hand).")
    else:
        rows = []
        for k, s in act.items():
            e = s.get("expect") or {}
            tr = T[T["key"] == k].iloc[0].to_dict() if len(T) and (T["key"] == k).any() else {}
            rows.append({"retire": False, "setup": s["label"], "ledger": PB_LEDGERS.get(s["ledger"], s["ledger"]),
                         "admitted": s.get("admitted"), "exp_mean": e.get("mean"), "win": e.get("win"),
                         "payoff": e.get("payoff"), "exp_n": e.get("n"), "risk_pct": pb_risk_pct(e, pb["account"]),
                         "live_n": tr.get("live_n", 0), "live_cum": tr.get("live_cum", 0.0), "status": tr.get("live_status", "NEW"),
                         "plan": e.get("plan", ""), "key": k})
        A = pd.DataFrame(rows)
        ed = st.data_editor(A, hide_index=True, key="pb_act_ed", disabled=[c for c in A.columns if c != "retire"],
                            column_config={"retire": st.column_config.CheckboxColumn("retire"),
                                           "exp_mean": P_("frozen E (R)", format="%+.3f"), "win": P_("win rate", format="percent"),
                                           "payoff": P_("avg win / avg loss", format="%.2f"), "exp_n": P_("backtest trades"),
                                           "risk_pct": P_("risk per trade (% equity)", format="%.2f"),
                                           "live_n": P_("live trades"), "live_cum": P_("live total (R)", format="%+.2f"),
                                           "key": None})
        if st.button("Retire the ticked setups", key="pb_retire"):
            for k in ed.loc[ed["retire"], "key"]:
                pb_retire(pb, k, "retired by hand")
            pb_save(pb)
            st.rerun()
        stale = [s["label"] for s in act.values() if s["ledger"] == "setup" and (s.get("expect") or {}).get("plan") not in ("", S["plan_tag"])]
        if stale:
            L.warnbox("Playbook: " + ", ".join(stale) + (" was" if len(stale) == 1 else " were") + " admitted under a "
                      "different exit plan, so the frozen expectation no longer matches your exits. Retire and re-admit "
                      "to refreeze.")
    L.sec("2 · Proposed by the ledgers")
    if not len(opts):
        L.note("No scoreboards yet: the lab hasn't saved a Setup, Bull or Bear spreads ledger (or the bars are missing).")
    elif not len(pro):
        L.note("No setup clears the bar right now. That is a useful answer: nothing new goes in.")
    else:
        Pp = pro[["key", "label", "ledger", "book", "verdict", "er", "t_er", "dsr", "events", "dates"]].copy()
        Pp.insert(0, "admit", False)
        Pp["ledger"] = Pp["ledger"].map(PB_LEDGERS)
        Pp["book"] = Pp["book"].map(PB_BOOKS)
        ed2 = st.data_editor(Pp, hide_index=True, key="pb_pro_ed", disabled=[c for c in Pp.columns if c != "admit"],
                             column_config={"admit": st.column_config.CheckboxColumn("admit"), "label": "setup",
                                            "er": P_("E (R per trade, by date)", format="%+.3f"), "t_er": P_("t", format="%+.1f"),
                                            "dsr": P_("deflated Sharpe", format="%.2f"), "key": None})
        if st.button("Admit the ticked setups", key="pb_admit", type="primary"):
            for k in ed2.loc[ed2["admit"], "key"]:
                _admit_key(pb, S, k)
            pb_save(pb)
            st.rerun()
    with st.expander(f"On deck ({len(deck)}): close to the bar"):
        if len(deck):
            L.show_df(deck[["label", "ledger", "book", "verdict", "er", "t_er", "dsr", "events"]].assign(
                ledger=deck["ledger"].map(PB_LEDGERS), book=deck["book"].map(PB_BOOKS)),
                column_config={"er": P_("E", format="%+.3f"), "t_er": P_("t", format="%+.1f"), "dsr": P_("deflated Sharpe", format="%.2f")})
    with st.expander("Add a setup by hand (the override)"):
        allk = list(opts["key"]) if len(opts) else []
        allk = [k for k in allk if k not in act]
        if allk:
            pick = st.selectbox("Setup", allk, key="pb_manual", format_func=lambda k: f"{pb_key_label(k)} ({PB_LEDGERS[pb_split(k)[0]]})")
            row = opts[opts["key"] == pick].iloc[0]
            L.note(f"Verdict {row['verdict'] or 'none'}, E {L._n(row['er'], np.nan):+.3f}, t {L._n(row['t_er'], np.nan):+.1f}"
                   + (f", deflated Sharpe {L._n(row['dsr'], np.nan):.2f}" if row["ledger"] == "setup" else "")
                   + ". Admitting it freezes these numbers; the tracker will hold it to them.")
            if st.button("Admit it", key="pb_manual_go"):
                _admit_key(pb, S, pick)
                pb_save(pb)
                st.rerun()
        else:
            L.note("Every scored setup is already in the playbook, or nothing is scored yet.")
    if retired:
        with st.expander(f"Retired ({len(retired)})"):
            L.show_df(pd.DataFrame([{"setup": v["label"], "admitted": v.get("admitted"), "retired": v.get("retired"),
                                     "why": v.get("why_retired", "")} for v in retired.values()]))
    with st.expander("Settings: account, sizing and your exits"):
        acc = pb["account"]
        c = st.columns(3)
        eq = c[0].number_input("Account equity ($)", 0.0, 1e9, float(acc["equity"]), 1000.0, key="pb_eq")
        mx = c[1].number_input("Max risk per trade (% equity)", 0.05, 5.0, float(acc["max_risk_pct"]), 0.05, key="pb_mx")
        kf = c[2].selectbox("Kelly fraction", [0.25, 0.5, 1.0], index=[0.25, 0.5, 1.0].index(float(acc["kelly_frac"]))
                            if float(acc["kelly_frac"]) in (0.25, 0.5, 1.0) else 1, key="pb_kf",
                            format_func=lambda v: {0.25: "quarter", 0.5: "half", 1.0: "full"}[v])
        pl = pb["plan"]
        c2 = st.columns(4)
        trim_r = c2[0].number_input("Trim at (R, 0 = no target)", 0.0, 6.0, float(pl["trim_r"]), 0.25, key="pb_trim_r",
                                    help="0 = no target: the exit for the rest takes the whole trade.")
        frac_lbl = c2[1].selectbox("Trim size", list(L.SIM_TRIM_FRACS), index=list(L.SIM_TRIM_FRACS).index(pl.get("frac_lbl", "1/3"))
                                   if pl.get("frac_lbl", "1/3") in L.SIM_TRIM_FRACS else 1, key="pb_frac")
        stop_k = c2[2].selectbox("Stop on the rest", list(L.SIM_TRIM_STOPS), index=list(L.SIM_TRIM_STOPS).index(pl.get("stop", "be"))
                                 if pl.get("stop", "be") in L.SIM_TRIM_STOPS else 0, key="pb_stop", format_func=L.SIM_TRIM_STOPS.get)
        runner = c2[3].selectbox("Exit for the rest", list(L.SIM_RUNNERS), index=list(L.SIM_RUNNERS).index(pl.get("runner", "ema21"))
                                 if pl.get("runner", "ema21") in L.SIM_RUNNERS else 1, key="pb_runner", format_func=L.SIM_RUNNERS.get)
        c3 = st.columns(3)
        fail_n = c3[0].number_input("Cut a trade not working by session (0 = off)", 0, 30, int(pl.get("fail_n", 5)), 1, key="pb_fail_n")
        fail_r = c3[1].number_input("...when under entry + (R)", -1.0, 1.0, float(pl.get("fail_r", 0.0)), 0.25, key="pb_fail_r")
        closes = c3[2].number_input("Closes under the average to exit", 1, 3, int(pl.get("closes", 1)), 1, key="pb_closes")
        c4 = st.columns(3)
        dd = c4[0].number_input("Exit signal, distribution day: down (%)", 1.0, 15.0, float(pl.get("dist_drop", 3.0)), 0.5,
                                key="pb_dist_drop", help="Used by the exit signals (and the Exit lab): a day the close falls "
                                                         "at least this much...")
        dv = c4[1].number_input("...on volume (x the 50-day average)", 1.0, 5.0, float(pl.get("dist_vol", 1.5)), 0.25,
                                key="pb_dist_vol", help="...on at least this multiple of the 50 sessions before it.")
        ce = c4[2].number_input("Exit signal, climax: close over the 50-day SMA (%)", 5.0, 100.0, float(pl.get("climax_ext", 20.0)),
                                5.0, key="pb_climax_ext")
        if st.button("Save settings", key="pb_set_save"):
            pb["account"] = {"equity": float(eq), "max_risk_pct": float(mx), "kelly_frac": float(kf)}
            pb["plan"] = {**PB_PLAN_DEFAULT, "trim_r": float(trim_r), "frac": L.SIM_TRIM_FRACS[frac_lbl], "frac_lbl": frac_lbl,
                          "stop": stop_k, "runner": runner, "fail_n": int(fail_n), "fail_r": float(fail_r), "closes": int(closes),
                          "dist_drop": float(dd), "dist_vol": float(dv), "climax_ext": float(ce)}
            pb_save(pb)
            st.rerun()
        L.note("The Setup ledger is re-run under these exits before anything is scored, so admission, the frozen "
               "expectation and the same-signal comparison all use the exits you actually follow. Changing them "
               "flags setups frozen under the old plan.")
    with st.expander("How the playbook works"):
        st.markdown(PB_GUIDE)


def _admit_key(pb: Dict[str, Any], S: Dict[str, Any], key: str) -> None:
    ledger = pb_split(key)[0]
    ev = S["evs"][ledger]
    meta = S["led"][ledger]["meta"] or {}
    horizon = int(S["prm"]["horizon"]) if ledger == "setup" else int(pb_br_prm(ledger, meta)["horizon"])
    pb_admit(pb, key, ev, horizon, str(meta.get("asof", "")), S["plan_tag"])


def _page_tonight(pb: Dict[str, Any], S: Dict[str, Any]) -> None:
    import streamlit as st
    P_ = _P_()
    T = S["tonight"]
    act = pb_active(pb)
    L.sec("Tonight: the last session's signals from playbook setups")
    if not act:
        L.note("No active setups: admit some on the Playbook page first.")
        return
    if not len(T):
        L.note("No playbook setup fired on the ledgers' last session. Nothing to do is a position too.")
    else:
        L.kpi_row([L.kpi_html("Signals", len(T), f"from {T['key'].nunique()} setup(s)"),
                   L.kpi_html("Risk if all taken", f"{T['risk_pct'].sum():.2f}%", "of equity, before any overlap rule"),
                   L.kpi_html("Best expectation", f"{L._n(T['exp_r'].max(), np.nan):+.2f}R", T.iloc[0]["label"])])
        V = T.copy()
        V.insert(0, "log", False)
        ed = st.data_editor(V, hide_index=True, key="pb_tn_ed", disabled=[c for c in V.columns if c != "log"],
                            column_config={"log": st.column_config.CheckboxColumn("log as planned"), "label": "setup",
                                           "signal_date": "signal day", "entry_rule": "entry", "legs": "spread legs",
                                           "plan_entry": P_("entry (est.)", format="%.2f"), "plan_stop": P_("stop", format="%.2f"),
                                           "close": P_("signal close", format="%.2f"), "risk_unit": P_("risk per unit ($)", format="%.2f"),
                                           "risk_pct": P_("risk (% equity)", format="%.2f"), "risk_dollars": P_("risk ($)", format="%.0f"),
                                           "size": P_("size (shares or spreads)"), "exp_r": P_("frozen E (R)", format="%+.2f"),
                                           "key": None, "ledger": None, "setup": None})
        if st.button("Log the ticked signals as planned trades", key="pb_tn_log", type="primary"):
            new = jr_new_rows(T[ed["log"].to_numpy()])
            J = jr_load()
            have = set(zip(J["key"], J["ticker"], J["signal_date"])) if len(J) else set()
            new = new[[(k, t, d) not in have for k, t, d in zip(new["key"], new["ticker"], new["signal_date"])]]
            jr_save(pd.concat([J, new], ignore_index=True))
            st.rerun()
        L.note("Entries and stops come from the ledger's own rules at the signal close (the stop is the setup's ATR "
               "distance, clamped like the ledger's). Spread prices are the spread ledger's estimate at its IV proxy: "
               "check the chain before you trade. Size = the risk in dollars over the risk per share or per spread.")
    quiet = [s["label"] for k, s in act.items() if not len(T) or k not in set(T["key"])]
    if quiet:
        L.note("No signal tonight: " + ", ".join(quiet) + ".")


def _page_journal(pb: Dict[str, Any], S: Dict[str, Any]) -> None:
    import streamlit as st
    P_ = _P_()
    L.sec("Journal: every trade, plan to exit")
    J = jr_load()
    lab_of = {k: f"{pb_key_label(k)} ({PB_LEDGERS.get(pb_split(k)[0], '?')})"
              for k in list(pb["setups"]) + [k for k in J["key"] if k and k not in pb["setups"]]}
    key_of = {v: k for k, v in lab_of.items()}
    V = J.copy()
    V.insert(2, "playbook", V["key"].map(lambda k: lab_of.get(k, "") if k else ""))
    ed = st.data_editor(V, hide_index=True, num_rows="dynamic", key="pb_jr_ed", column_config={
        "id": None, "key": None, "ledger": None, "setup": None,
        "status": st.column_config.SelectboxColumn("status", options=PB_STATUS),
        "playbook": st.column_config.SelectboxColumn("playbook setup", options=[""] + list(lab_of.values()),
                                                     help="Blank = off-playbook (tracked, but outside the edge)."),
        "signal_date": "signal day", "entry_date": "entered", "trim_date": "trimmed", "exit_date": "exited",
        "book": st.column_config.SelectboxColumn("book", options=list(PB_BOOKS)),
        "side": st.column_config.SelectboxColumn("side", options=["long", "short"]),
        "deviation": st.column_config.SelectboxColumn("deviation", options=PB_DEVIATIONS,
                                                      help="The main way this trade didn't follow the plan (blank = it did)."),
        "plan_entry": P_("planned entry", format="%.2f"), "plan_stop": P_("planned stop", format="%.2f"),
        "entry_px": P_("entry (shares: price; spreads: debit or credit)", format="%.2f"),
        "init_stop": P_("initial stop (shares)", format="%.2f"),
        "max_risk": P_("max loss per spread (credit: width less credit)", format="%.2f"),
        "trim_px": P_("trim price", format="%.2f"), "exit_px": P_("exit (rest)", format="%.2f")})
    c = st.columns(3)
    if c[0].button("Save the journal", key="pb_jr_save", type="primary"):
        E = ed.copy()
        E["key"] = E["playbook"].map(lambda v: key_of.get(v, "") if isinstance(v, str) else "")
        E = E.drop(columns=["playbook"])
        for i, r in E.iterrows():                           # a playbook setup picked: fill its ledger, setup and book
            if r.get("key"):
                lg, sid, bk = pb_split(r["key"])
                E.at[i, "ledger"], E.at[i, "setup"], E.at[i, "book"] = lg, sid, bk
                if not r.get("side"):
                    E.at[i, "side"] = pb_side(lg, bk)
        jr_save(E)
        st.rerun()
    if c[1].button("Import open positions from the Book", key="pb_jr_book"):
        try:
            book = pd.read_csv(f_book())
        except Exception:
            book = pd.DataFrame()
        new = jr_from_book(book, J)
        if len(new):
            jr_save(pd.concat([J, new], ignore_index=True))
            st.rerun()
        else:
            L.note("Nothing new in the Book (or no Book file).")
    c[2].download_button("Download (CSV)", jr_clean(J).to_csv(index=False), "playbook_journal.csv", "text/csv")
    L.note("Planned rows come from Tonight. When you fill: status open, the entry date and price, the size and the "
           "initial stop. A trim: its date, price and quantity. The exit: its date and price for the rest, status "
           "closed. Spreads: the entry is the debit paid (or credit received) per spread, the exit what it closed for. "
           "Tag a deviation when the trade didn't follow the plan; the Review page shows what each one costs.")


def _page_tracker(pb: Dict[str, Any], S: Dict[str, Any]) -> None:
    import streamlit as st
    import altair as alt
    P_ = _P_()
    J, T = S["J"], S["tracker"]
    L.sec("Edge tracker: are you getting the edge?")
    closed = J[(J["status"] == "closed")] if len(J) else J
    on = closed[closed["key"] != ""] if len(closed) else closed
    m = on[np.isfinite(on["gap_r"].astype(float))] if len(on) else on
    sel = T["selection"].dropna() if len(T) else pd.Series(dtype=float)
    imp = T["implementation"].dropna() if len(T) else pd.Series(dtype=float)
    L.kpi_row([L.kpi_html("Closed trades", len(closed), f"{len(closed) - len(on)} off-playbook", ""),
               L.kpi_html("Your total", f"{L._n(closed['r'].sum() if len(closed) else 0, 0):+.2f}R",
                          f"average {L._n(closed['r'].mean() if len(closed) else np.nan, np.nan):+.2f}R"),
               L.kpi_html("Implementation", f"{L._n(m['gap_r'].mean() if len(m) else np.nan, np.nan):+.2f}R",
                          f"per trade vs the ledger, {len(m)} matched; entry cost {L._n(m['entry_cost_r'].mean() if len(m) else np.nan, np.nan):+.2f}R",
                          "bad" if len(m) and m["gap_r"].mean() < -0.1 else ("good" if len(m) and m["gap_r"].mean() >= 0 else "")),
               L.kpi_html("Selection", f"{L._n(sel.mean() if len(sel) else np.nan, np.nan):+.2f}R",
                          "your picks vs every playbook signal")])
    if not len(T):
        L.note("No playbook setups yet.")
    else:
        V = T[["label", "state", "live_status", "live_n", "live_cum", "live_exp_cum", "live_z", "live_llr", "exp_mean",
               "e_all", "n_all", "e_pick", "e_you", "selection", "implementation", "live_needed", "key"]].copy()
        L.show_df(V, column_config={
            "label": "setup", "live_status": "status", "live_n": P_("live trades"), "live_cum": P_("your total (R)", format="%+.2f"),
            "live_exp_cum": P_("expected (R)", format="%+.2f"), "live_z": P_("z vs expected", format="%+.2f"),
            "live_llr": P_("sequential test (LLR)", format="%+.2f", help="+2.2 or more: the record fits no edge 9:1 better (RETIRE); "
                                                                         "-2.2 or less: the frozen edge is confirmed."),
            "exp_mean": P_("frozen E", format="%+.3f"), "e_all": P_("ledger, every signal", format="%+.3f"), "n_all": P_("signals"),
            "e_pick": P_("ledger, your picks", format="%+.3f"), "e_you": P_("you, same trades", format="%+.3f"),
            "selection": P_("selection", format="%+.3f"), "implementation": P_("implementation", format="%+.3f"),
            "live_needed": P_("trades for t 2 alone"), "key": None})
        keys = list(T["key"])
        k = st.selectbox("One setup", keys, key="pb_tr_key", format_func=pb_key_label)
        s = pb["setups"][k]
        x = J[(J["key"] == k) & (J["status"] == "closed")]["r"].astype(float).tolist() if len(J) else []
        bp = pb_band_path(x, s.get("expect") or {})
        if len(bp):
            band = alt.Chart(bp).mark_area(opacity=0.18, color=L.C_ACCENT).encode(x=alt.X("trade:Q", title="trade"),
                                                                                    y=alt.Y("lo:Q", title="running total (R)"), y2="hi:Q")
            exp = alt.Chart(bp).mark_line(strokeDash=[4, 3], color=L.C_MUTED).encode(x="trade:Q", y="expected:Q")
            you = alt.Chart(bp).mark_line(point=True, color=L.C_GREEN).encode(x="trade:Q", y="you:Q",
                                                                              tooltip=["trade", alt.Tooltip("you:Q", format="+.2f")])
            L.show_chart((band + exp + you).properties(height=260, title=f"{s['label']}: you vs the frozen expectation (90% band)"))
        else:
            L.note("No closed trades on this setup yet.")
        sk = pb_skipped(S["evs"].get(s["ledger"]), J, k, s.get("admitted", "1900-01-01"))
        if len(sk):
            done = sk[sk["state"] == "closed"]
            L.note(f"Skipped since {s.get('admitted')}: {len(sk)} signals; the {len(done)} completed averaged "
                   f"{L._n(done['ledger_r'].mean() if len(done) else np.nan, np.nan):+.2f}R on the ledger.")
            with st.expander("Skipped signals"):
                L.show_df(sk, column_config={"ledger_r": P_("ledger R", format="%+.2f")})
    L.sec("Trade by trade: you against the ledger on the same signal")
    if len(J):
        W = J[["ticker", "key", "status", "signal_date", "entry_date", "exit_date", "r", "r_open", "ledger_r", "ledger_status",
               "gap_r", "entry_cost_r", "exit_r", "deviation"]].copy()
        W["key"] = W["key"].map(lambda k: pb_key_label(k) if k else "off-playbook")
        L.show_df(W.sort_values(["entry_date"], ascending=False), column_config={
            "key": "setup", "signal_date": "signal day", "entry_date": "entered", "exit_date": "exited",
            "ledger_status": "ledger trade", "r": P_("your R", format="%+.2f"), "r_open": P_("open R (marked)", format="%+.2f"),
            "ledger_r": P_("ledger R", format="%+.2f"), "gap_r": P_("gap (R)", format="%+.2f"),
            "entry_cost_r": P_("entry cost (R)", format="%+.2f", help="Your fill against the ledger's; positive = you paid more."),
            "exit_r": P_("exits and the rest (R)", format="%+.2f")})
    else:
        L.note("The journal is empty.")


PB_EXIT_GUIDE = """
**What it tests.** The Setup ledger's trades are re-run three ways on the same bars: same entries, same initial
stops, only the exits change. *Your plan* is the one in Settings. *Trim + signals* sells your trim at your target
and lets the exit signals take the rest. *Signals only* has no target: the whole position rides until the first
exit signal (or the stop, or your time stop). The exit signals are the first of: a close under the 10-day EMA, a
distribution day (a big down day on heavy volume) or a climax (a close far over the 50-day SMA). Each sells at that
close.

**How to read it.** The difference column is the plan's R less yours on the same trades, averaged by signal date,
with a Newey-West t (trades that overlap in time aren't independent). BETTER or WORSE needs t 2+; per setup it also
needs a false-discovery q of 0.10 or less, because many setups are tested at once. Signals only usually wins fewer
trades and holds winners longer: look at the 3R+ share, the best 5% and the hold columns, not just E[R].

**Before you switch.** Picking the best of three after seeing them is a mild form of fitting. Change the signal
thresholds only for a reason you'd have given beforehand; each change is another variant tried. Switching your plan
re-runs the ledger and flags setups frozen under the old one (re-admit them to refreeze).
"""


def _page_exit_lab(pb: Dict[str, Any], S: Dict[str, Any], P: Optional[Dict[str, pd.DataFrame]]) -> None:
    import streamlit as st
    import altair as alt
    P_ = _P_()
    ss = st.session_state
    ev = S["led"]["setup"]["ev"]
    L.sec("Exit lab: a target R against exit signals, on the same trades")
    if not len(ev) or P is None:
        L.note("Needs the Setup ledger (build it in the lab or run the nightly) and bars.")
        return
    plans = pb_exit_plans(pb["plan"])
    L.note("Plans compared. " + " ".join(f"{PB_EXIT_SHORT[v].capitalize()}: {pb_plan_tag(pl)}." for v, pl in plans.items()))
    tag = f"{S['led']['setup']['mtime']}"
    stamp = (tag, json.dumps(plans, sort_keys=True, default=str), str(P["close"].index[-1]))
    rec = ss.get("_pb_xl")
    if not (rec and rec.get("stamp") == stamp):
        runs = pb_exit_runs(ev, P, S["prm"], pb["plan"], tag=tag, only_cached=True)
        if runs is None:
            L.note("Each plan re-runs every Setup-ledger trade (the nightly run does it ahead of time).")
            if not st.button("Run the exit lab", key="pb_xl_go"):
                return
            with st.spinner("Re-running the ledger's trades under each plan"):
                runs = pb_exit_runs(ev, P, S["prm"], pb["plan"], tag=tag)
        rec = {"stamp": stamp, "T": pb_exit_table(runs, int(S["prm"]["horizon"]), pb_active_setup_ids(pb)), "runs": runs}
        ss["_pb_xl"] = rec
    T = rec["T"]
    if not len(T):
        L.note("No completed trades to compare.")
        return
    scopes = list(dict.fromkeys(T["scope"]))
    lbl = dict(zip(T["scope"], T["scope_label"]))
    dflt = "active" if "active" in scopes else "all"
    if ss.get("pb_xl_scope") not in scopes:
        ss["pb_xl_scope"] = dflt
    sk = st.selectbox("Trades from", scopes, key="pb_xl_scope", format_func=lambda k: lbl.get(k, k))
    g = T[T["scope"] == sk].set_index("variant")
    kp = []
    for v in PB_EXIT_VARIANTS:
        if v not in g.index:
            continue
        r_ = g.loc[v]
        if v == "yours":
            kp.append(L.kpi_html("Your plan: E[R]", f"{L._n(r_['er'], np.nan):+.3f}R",
                                 f"{int(r_['n']):,} trades; win {L._n(r_['win'], np.nan):.0%}"))
        else:
            tone = {"BETTER": "good", "WORSE": "bad"}.get(r_["verdict"], "")
            kp.append(L.kpi_html(f"{PB_EXIT_SHORT[v].capitalize()}: E[R]", f"{L._n(r_['er'], np.nan):+.3f}R",
                                 f"{L._n(r_['d_er'], np.nan):+.3f} vs yours, t {L._n(r_['d_t'], np.nan):+.1f}: {r_['verdict']}", tone))
    L.kpi_row(kp)
    meas = [("trades", "n", "{:,.0f}"), ("E[R] per trade", "er", "{:+.3f}R"), ("E[R], date-averaged (t)", None, None),
            ("vs your plan, per trade (t)", None, None), ("win", "win", "{:.0%}"), ("avg winner", "avg_win", "{:+.2f}R"),
            ("avg loser", "avg_loss", "{:+.2f}R"), (f"{L.SIM_BIG_R:g}R+ winners", "p_big", "{:.1%}"),
            ("best 5% of trades, avg", "r_top5", "{:+.2f}R"), ("best trade", "r_max", "{:+.2f}R"),
            ("median hold, winners (sessions)", "hold_win", "{:.0f}"), ("median hold, losers (sessions)", "hold_loss", "{:.0f}"),
            ("trimmed at the target", "p_trim", "{:.0%}"), ("first stop", "p_stop", "{:.0%}"),
            ("raised stop or EMA close", "p_trail", "{:.0%}"), ("distribution day", "p_dist", "{:.0%}"),
            ("climax", "p_climax", "{:.0%}"), ("cut, not working", "p_cut", "{:.0%}")]

    def cell(r_, col, fmt, name):
        if name == "E[R], date-averaged (t)":
            return f"{L._n(r_['er_date'], np.nan):+.3f}R (t {L._n(r_['t'], np.nan):+.1f})"
        if name == "vs your plan, per trade (t)":
            return "" if r_.name == "yours" else f"{L._n(r_['d_er'], np.nan):+.3f}R (t {L._n(r_['d_t'], np.nan):+.1f})"
        x = L._n(r_[col], np.nan)
        return fmt.format(x) if np.isfinite(x) else "n/a"
    W = pd.DataFrame({"measure": [m_[0] for m_ in meas],
                      **{PB_EXIT_SHORT[v]: [cell(g.loc[v], m_[1], m_[2], m_[0]) for m_ in meas] for v in PB_EXIT_VARIANTS
                         if v in g.index}})
    L.show_df(W, height=min(700, 40 + 35 * len(W)), column_config={"measure": st.column_config.TextColumn("", width="medium")})
    # cumulative R by exit date, one line per plan
    runs = rec.get("runs") or {}
    if runs:
        base = runs["yours"]
        T_all = []
        idx_ok = None
        for v, e in runs.items():
            ok_ = (e["status"] == 0) & (e["outcome"] != 4) & np.isfinite(e["r"].astype(float))
            idx_ok = ok_ if idx_ok is None else (idx_ok & ok_)
        m_ = idx_ok & ~base["setup"].astype(str).str.startswith("base:") & ~base["setup"].isin(L.RK_SKIP)
        if sk == "active":
            m_ &= base["setup"].isin(pb_active_setup_ids(pb))
        elif sk.startswith("setup:"):
            m_ &= base["setup"] == sk.split(":", 1)[1]
        for v, e in runs.items():
            x = e[m_.to_numpy()][["date", "r"]].sort_values("date")
            if len(x):
                cum = x.groupby("date")["r"].sum().cumsum()
                T_all.append(pd.DataFrame({"date": cum.index, "cum_r": cum.to_numpy(), "plan": PB_EXIT_SHORT[v]}))
        if T_all:
            D = pd.concat(T_all)
            ch = alt.Chart(D).mark_line(strokeWidth=1.6).encode(
                x=alt.X("date:T", title="signal date"), y=alt.Y("cum_r:Q", title="running total (R)"),
                color=alt.Color("plan:N", scale=alt.Scale(domain=list(PB_EXIT_SHORT.values()),
                                                          range=[L.C_MUTED, L.C_ACCENT, L.C_BLUE]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["plan", alt.Tooltip("date:T"), alt.Tooltip("cum_r:Q", format="+.1f")])
            L.show_chart(ch.properties(height=280, title=f"{lbl.get(sk, sk)}: running R under each plan, same trades"))
    L.sec("By setup")
    Wd = pb_exit_wide(T)
    Wd = Wd[Wd["scope"].str.startswith("setup:")] if len(Wd) else Wd
    if len(Wd):
        Wd = Wd.assign(best=Wd["best"].map(PB_EXIT_SHORT))
        L.show_df(Wd.drop(columns=["scope"]), column_config={
            "setup": st.column_config.TextColumn("setup", width="medium"), "n": P_("trades", format="%d"),
            "er_yours": P_("your plan", format="%+.3f"), "er_trim_sig": P_("trim + signals", format="%+.3f"),
            "er_sig_only": P_("signals only", format="%+.3f"),
            "d_trim_sig": P_("trim + signals vs yours", format="%+.3f"), "t_trim_sig": P_("t", format="%+.1f"),
            "v_trim_sig": st.column_config.TextColumn("verdict", width="small"),
            "d_sig_only": P_("signals only vs yours", format="%+.3f"), "t_sig_only": P_("t ", format="%+.1f"),
            "v_sig_only": st.column_config.TextColumn("verdict ", width="small"),
            "best": st.column_config.TextColumn("best supported", width="small")})
    c = st.columns(2)
    for i, v in enumerate(("trim_sig", "sig_only")):
        if plans[v] == plans["yours"]:
            c[i].caption(f"{PB_EXIT_SHORT[v].capitalize()} is already your plan.")
        elif c[i].button(f"Make {PB_EXIT_SHORT[v]} my plan", key=f"pb_xl_use_{v}"):
            pb["plan"] = {**plans[v]}
            pb_save(pb)
            ss.pop("_pb_xl", None)
            st.rerun()
    with st.expander("How the exit lab works"):
        st.markdown(PB_EXIT_GUIDE)


def _page_review(pb: Dict[str, Any], S: Dict[str, Any]) -> None:
    import streamlit as st
    P_ = _P_()
    L.sec("Review")
    freq = st.radio("By", ["W", "M"], horizontal=True, key="pb_rv_f", format_func={"W": "week", "M": "month"}.get)
    per, dev = pb_review(S["J"], freq)
    if not len(per):
        L.note("No closed trades with an exit date yet.")
        return
    L.show_df(per, column_config={"total_r": P_("total R", format="%+.2f"), "mean_r": P_("average R", format="%+.2f"),
                                  "gap_r": P_("vs the ledger (R)", format="%+.2f"), "entry_cost_r": P_("entry cost (R)", format="%+.2f"),
                                  "discipline": P_("followed the plan", format="percent"), "chased": P_("chased"),
                                  "off_playbook": P_("off-playbook")})
    L.sec("What each deviation cost")
    L.show_df(dev, column_config={"mean_r": P_("average R", format="%+.2f"), "mean_gap_r": P_("vs the ledger, per trade", format="%+.2f"),
                                  "total_gap_r": P_("vs the ledger, total", format="%+.2f")})
    L.note("Followed the plan = no deviation tag and an entry within 0.1R of the ledger's. Chased = tagged, or an "
           "entry 0.25R or more worse than the ledger's. The deviation table is the cheapest edge you have: the gap "
           "on trades where you went off-plan, against the ones where you didn't.")


def _launch() -> None:
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", str(Path(__file__).resolve())] + L.THEME_FLAGS + sys.argv[1:]
    sys.exit(stcli.main())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="app", choices=["app", "nightly"])
    ap.add_argument("--source", choices=["massive", "yahoo", "demo"], default=None)
    ap.add_argument("--limit", type=int, default=0, help="nightly: only the first N names (testing)")
    ap.add_argument("--no-exit-lab", action="store_true", help="nightly: skip the exit lab (two extra re-runs of the ledger)")
    a = ap.parse_args(argv)
    if a.command == "nightly":
        out = nightly(a.source, a.limit, exit_lab=not a.no_exit_lab)
        return 0 if out.get("ok") else 2
    _launch()
    return 0


if __name__ == "__main__":
    if L._in_streamlit():
        app()
    else:
        sys.exit(main())
