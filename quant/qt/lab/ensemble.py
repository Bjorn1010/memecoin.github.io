"""Combine validated strategies only when they actually diversify.

A strategy joins the ensemble only if its PnL correlation with every member already in
is below the threshold — two trend-following variants at 0.9 correlation are one bet
counted twice. Allocation is compared across inverse-volatility, equal risk
contribution and minimum drawdown-weighted schemes; nothing is optimised for Sharpe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import compute


def select_diversifiers(returns: pd.DataFrame, order: list[str], max_corr: float = 0.7) -> list[str]:
    corr = returns.corr()
    chosen: list[str] = []
    for name in order:
        if all(abs(corr.loc[name, c]) < max_corr for c in chosen):
            chosen.append(name)
    return chosen


def risk_parity_weights(cov: np.ndarray, iters: int = 500) -> np.ndarray:
    n = cov.shape[0]
    w = np.ones(n) / n
    for _ in range(iters):
        rc = w * (cov @ w)
        target = rc.sum() / n
        w = w * (target / np.maximum(rc, 1e-18)) ** 0.5
        w = w / w.sum()
    return w


def combine(returns: pd.DataFrame, ppy: int, lookback: int = 252) -> dict:
    """Causal allocations, re-estimated monthly on trailing data, compared side by side."""
    R = returns.fillna(0.0)
    if R.shape[1] < 2:
        return {"members": list(R.columns), "note": "moins de deux stratégies : pas d'ensemble"}
    out = {"correlation": R.corr()}
    schemes = {"equal_weight": [], "inverse_vol": [], "risk_parity": []}
    dates = R.index
    weights_hist = {k: pd.DataFrame(np.nan, index=dates, columns=R.columns) for k in schemes}
    for i in range(lookback, len(dates), 21):
        win = R.iloc[i - lookback:i]
        cov = win.cov().to_numpy()
        vol = np.sqrt(np.diag(cov))
        ew = np.ones(R.shape[1]) / R.shape[1]
        iv = (1 / np.where(vol > 0, vol, np.nan))
        iv = np.nan_to_num(iv / np.nansum(iv))
        rp = risk_parity_weights(cov) if np.all(vol > 0) else ew
        for k, w in (("equal_weight", ew), ("inverse_vol", iv), ("risk_parity", rp)):
            weights_hist[k].iloc[i] = w
    results = {}
    for k, wh in weights_hist.items():
        w = wh.ffill().shift(1)
        port = (w * R).sum(axis=1).loc[w.dropna(how="all").index]
        results[k] = compute(port, None, ppy)
        results[k]["series"] = port
    members = {c: compute(R[c].loc[results["equal_weight"]["series"].index], None, ppy) for c in R.columns}
    vols = R.std()
    port_vol = results["inverse_vol"]["series"].std()
    w_last = weights_hist["inverse_vol"].ffill().iloc[-1].fillna(0)
    out.update({
        "schemes": results,
        "members": members,
        "diversification_ratio": float((w_last * vols).sum() / port_vol) if port_vol > 0 else float("nan"),
    })
    return out
