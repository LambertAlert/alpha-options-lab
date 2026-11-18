"""The lab with EP 9M names planted into the Brief's week, for apptest_ep9m.py (the demo data has no live EP 9M in
the last five sessions). Not for trading: it rewrites the EP 9M readings of a few demo names."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import alpha_options_lab as L

_orig = L.ep9m_last


def _planted(P, look=20):
    X = _orig(P, 20)
    last = P["close"].iloc[-1].reindex(X.index)
    ok = X["ep9_age"].notna() & (last > X["ep9_lo"])
    X.loc[ok, "ep9_age"] = np.where(np.arange(int(ok.sum())) % 2 == 0, 0, 2)
    X.loc[ok, "ep9_hi_since"] = np.maximum(X.loc[ok, "ep9_hi"], last[ok] * 1.01)
    t0 = ok & (X["ep9_age"] == 0)
    X.loc[t0, "ep9_lo"], X.loc[t0, "ep9_hi"] = last[t0] * 0.94, last[t0] * 1.005
    return X.where(X["ep9_age"] <= look, axis=0)


L.ep9m_last = _planted
L.main()
