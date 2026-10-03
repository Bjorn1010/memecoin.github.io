"""Market regimes, labelled causally, and the strategy's behaviour inside each.

Labels at day t use data up to t only — a regime classifier fitted on the full sample
"knows" when 2008 ended, and a strategy filtered by it inherits that knowledge.

Four independent axes, all computed on an equal-weight index of the asset class:
* direction: bull / bear / sideways (price vs a rising/falling 200-day average);
* volatility: high / normal / low (20-day realised vol percentile in a 3-year window);
* crisis: 20 % below the 1-year high while volatility is high;
* character: trending / mean-reverting / neutral (60-day efficiency ratio percentile).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import sharpe


def class_index(returns_by_symbol: pd.DataFrame) -> pd.Series:
    return (1 + returns_by_symbol.mean(axis=1, skipna=True).fillna(0.0)).cumprod()


def label_regimes(index: pd.Series) -> pd.DataFrame:
    p = index
    ma = p.rolling(200, min_periods=150).mean()
    slope = ma.diff(20)
    direction = np.where((p > ma) & (slope > 0), "bull", np.where((p < ma) & (slope < 0), "bear", "sideways"))
    r = np.log(p).diff()
    vol = r.rolling(20, min_periods=15).std()
    pct = vol.rolling(756, min_periods=252).rank(pct=True)
    volreg = np.where(pct > 0.7, "high_vol", np.where(pct < 0.3, "low_vol", "normal_vol"))
    dd = p / p.rolling(252, min_periods=60).max() - 1
    crisis = np.where((dd < -0.20) & (pct > 0.7), "crisis", "no_crisis")
    move = (p - p.shift(60)).abs()
    path = p.diff().abs().rolling(60, min_periods=40).sum()
    er = move / path
    er_pct = er.rolling(756, min_periods=252).rank(pct=True)
    char = np.where(er_pct > 0.7, "trending", np.where(er_pct < 0.3, "mean_reverting", "neutral"))
    out = pd.DataFrame({"direction": direction, "volatility": volreg, "crisis": crisis, "character": char},
                       index=p.index)
    # Before enough history exists the label is unknown, not "sideways".
    out.loc[ma.isna(), "direction"] = "unknown"
    out.loc[pct.isna(), ["volatility", "crisis"]] = "unknown"
    out.loc[er_pct.isna(), "character"] = "unknown"
    return out


def regime_performance(strategy_returns: pd.Series, labels: pd.DataFrame, ppy: int) -> dict:
    """Sharpe, mean return and share of days per regime, plus a dependency verdict.

    Labels are lagged one bar: the regime known at yesterday's close is the one a
    strategy could have conditioned on when it traded today.
    """
    lab = labels.shift(1).reindex(strategy_returns.index)
    out: dict = {}
    dependent_axes = []
    for axis in lab.columns:
        rows = {}
        for reg, grp in strategy_returns.groupby(lab[axis]):
            if reg == "unknown" or len(grp) < 60:
                continue
            rows[reg] = {"sharpe": sharpe(grp, ppy), "mean_bp": float(grp.mean() * 1e4),
                         "share_days": float(len(grp) / len(strategy_returns)), "pnl": float(grp.sum())}
        out[axis] = rows
        pnl = {k: v["pnl"] for k, v in rows.items()}
        total = sum(v for v in pnl.values() if v > 0)
        if total > 0 and len(pnl) >= 2:
            top = max(pnl, key=pnl.get)
            others_negative = all(v <= 0 for k, v in pnl.items() if k != top)
            if pnl[top] / total > 0.8 and others_negative:
                dependent_axes.append(f"{axis}:{top}")
    positive = sum(1 for axis in out.values() for v in axis.values() if np.isfinite(v["sharpe"]) and v["sharpe"] > 0)
    total_regs = sum(len(axis) for axis in out.values())
    out["dependency"] = dependent_axes
    out["regime_diversity"] = positive / total_regs if total_regs else float("nan")
    return out
