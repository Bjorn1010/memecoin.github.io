"""The full metric set for a return stream and its trades.

No single number here selects a strategy. Sharpe, CAGR and win rate are each easy to
inflate on their own (a strategy that sells far out-of-the-money options has a 95% win
rate right up to the day it does not), which is why the decision in pipeline.py reads
them together with robustness, significance and cost sensitivity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sharpe(r: pd.Series, ppy: int) -> float:
    r = pd.Series(r).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(ppy)) if len(r) > 2 and sd > 0 else float("nan")


def drawdown(r: pd.Series) -> pd.Series:
    eq = (1 + r.fillna(0.0)).cumprod()
    return eq / eq.cummax() - 1.0


def longest_recovery(r: pd.Series) -> int:
    """Longest number of bars spent below a previous equity peak."""
    under = drawdown(r) < -1e-12
    runs = under.groupby((~under).cumsum()).sum()
    return int(runs.max()) if len(runs) else 0


def losing_streak(trade_net: pd.Series) -> int:
    best = cur = 0
    for x in trade_net:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def compute(r: pd.Series, trades: pd.DataFrame | None, ppy: int, position: pd.Series | None = None) -> dict:
    r = pd.Series(r).fillna(0.0)
    n = len(r)
    if n < 3:
        return {"n_bars": n}
    years = n / ppy
    eq_end = float((1 + r).prod())
    dd = drawdown(r)
    mdd = float(dd.min())
    cagr = eq_end ** (1 / years) - 1 if years > 0 and eq_end > 0 else float("nan")
    downside = r[r < 0].std(ddof=1)
    q05 = float(r.quantile(0.05))
    out = {
        "total_return": eq_end - 1,
        "cagr": cagr,
        "volatility": float(r.std(ddof=1) * np.sqrt(ppy)),
        "sharpe": sharpe(r, ppy),
        "sortino": float(r.mean() / downside * np.sqrt(ppy)) if downside and downside > 0 else float("nan"),
        "calmar": float(cagr / abs(mdd)) if mdd < 0 and np.isfinite(cagr) else float("nan"),
        "max_drawdown": mdd,
        "avg_drawdown": float(dd[dd < 0].mean()) if (dd < 0).any() else 0.0,
        "recovery_bars": longest_recovery(r),
        "skew": float(r.skew()),
        "kurtosis": float(r.kurtosis()),
        "tail_loss_cvar5": float(r[r <= q05].mean()) if (r <= q05).any() else float("nan"),
        "t_stat": float(r.mean() / r.std(ddof=1) * np.sqrt(n)) if r.std(ddof=1) > 0 else float("nan"),
        "years": years,
        "n_bars": n,
    }
    if position is not None and len(position):
        out["exposure"] = float((position.reindex(r.index).fillna(0.0).abs() > 1e-12).mean())
    if trades is not None and len(trades) and "net" in trades:
        t = trades["net"].astype("float64")
        wins, losses = t[t > 0], t[t < 0]
        out.update({
            "n_trades": int(len(t)),
            "trades_per_year": float(len(t) / years) if years > 0 else float("nan"),
            "win_rate": float((t > 0).mean()),
            "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
            "expectancy": float(t.mean()),
            "avg_trade": float(t.mean()),
            "median_trade": float(t.median()),
            "avg_win": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss": float(losses.mean()) if len(losses) else 0.0,
            "losing_streak": losing_streak(t),
            "avg_bars_held": float(trades["bars"].mean()) if "bars" in trades else float("nan"),
            # Share of the gross result consumed by frictions. Above 1 the frictions ate
            # more than everything the signal earned.
            "cost_share": float(trades["cost"].sum() / trades["gross"].sum()) if trades["gross"].sum() > 0 else float("nan"),
        })
    elif trades is not None:
        out["n_trades"] = 0
    return out


def by_year_sharpe(r: pd.Series, ppy: int) -> pd.Series:
    return r.groupby(r.index.year).apply(lambda x: sharpe(x, ppy))
