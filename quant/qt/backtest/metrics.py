"""Performance metrics.

Sharpe alone is not a description of a strategy. Two books with identical Sharpe can
have completely different characters: one grinds out small wins and occasionally gives
back a year, the other is flat for months and makes everything in three days. Which one
is survivable depends on facts Sharpe cannot express — drawdown depth, drawdown
*duration*, tail ratio, and how much of the return survives costs.

The metrics below are grouped so that the ones that decide whether a strategy is
tradable are not buried under the ones that decide whether it is impressive:

* **Return & risk** — CAGR, annual vol, Sharpe, Sortino.
* **Drawdown** — depth, duration, recovery, Calmar. Duration is the one that ends
  careers: a 15% drawdown lasting three months is easier to hold than an 8% one
  lasting two years.
* **Distribution** — skew, kurtosis, tail ratio, worst day/week, VaR and CVaR.
* **Trading** — turnover, cost drag, hit rate, profit factor, average holding period.
  Cost drag as a share of gross return is the single most informative number for
  deciding whether an edge is real or an artefact of a friction-free simulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def drawdown_series(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return equity / peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    return float(drawdown_series(equity).min())


def drawdown_stats(equity: pd.Series) -> dict:
    """Depth, duration in bars, and whether the worst drawdown was ever recovered."""
    if equity.empty:
        return {"max_drawdown": np.nan, "max_dd_duration": np.nan, "current_drawdown": np.nan,
                "recovered": False, "time_underwater_pct": np.nan}
    dd = drawdown_series(equity)
    underwater = dd < -1e-12
    # Longest consecutive underwater run.
    groups = (~underwater).cumsum()
    runs = underwater.groupby(groups).sum()
    longest = int(runs.max()) if len(runs) else 0

    trough_idx = dd.idxmin()
    after = equity.loc[trough_idx:]
    peak_before = equity.loc[:trough_idx].max()
    recovered = bool((after >= peak_before).any())

    return {
        "max_drawdown": float(dd.min()),
        "max_dd_duration": longest,
        "current_drawdown": float(dd.iloc[-1]),
        "recovered": recovered,
        "time_underwater_pct": float(underwater.mean()),
    }


def performance_metrics(result, bars_per_year: float = 365 * 24) -> dict:
    """Full metric set for a BacktestResult (or anything with equity/returns/trades)."""
    equity = getattr(result, "equity", pd.Series(dtype="float64"))
    returns = getattr(result, "returns", pd.Series(dtype="float64"))
    if equity.empty or len(equity) < 3:
        return {}

    r = returns.replace([np.inf, -np.inf], np.nan).dropna()
    n = len(r)
    years = n / bars_per_year if bars_per_year > 0 else np.nan

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0) if years and years > 0 else np.nan
    vol = float(r.std(ddof=1) * np.sqrt(bars_per_year)) if n > 1 else np.nan
    sharpe = float(r.mean() / r.std(ddof=1) * np.sqrt(bars_per_year)) if n > 1 and r.std(ddof=1) > 0 else np.nan

    downside = r[r < 0]
    dstd = downside.std(ddof=1) if len(downside) > 1 else np.nan
    sortino = float(r.mean() / dstd * np.sqrt(bars_per_year)) if dstd and dstd > 0 else np.nan

    dd = drawdown_stats(equity)
    calmar = float(cagr / abs(dd["max_drawdown"])) if dd["max_drawdown"] and dd["max_drawdown"] < 0 else np.nan

    # Tail behaviour. Ratio of the 95th to the 5th percentile in absolute terms: > 1
    # means the good tail is fatter than the bad one.
    q05, q95 = (float(r.quantile(0.05)), float(r.quantile(0.95))) if n > 20 else (np.nan, np.nan)
    tail_ratio = float(abs(q95 / q05)) if q05 and q05 != 0 else np.nan
    var95 = q05
    cvar95 = float(r[r <= q05].mean()) if n > 20 and np.isfinite(q05) else np.nan

    out = {
        "total_return": total_return,
        "cagr": cagr,
        "annual_vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": dd["max_drawdown"],
        "max_dd_duration_bars": dd["max_dd_duration"],
        "time_underwater_pct": dd["time_underwater_pct"],
        "recovered_from_max_dd": dd["recovered"],
        "skew": float(r.skew()) if n > 3 else np.nan,
        "kurtosis": float(r.kurtosis()) if n > 3 else np.nan,
        "tail_ratio": tail_ratio,
        "var_95": var95,
        "cvar_95": cvar95,
        "best_bar": float(r.max()),
        "worst_bar": float(r.min()),
        "positive_bars_pct": float((r > 0).mean()),
        "n_bars": int(n),
        "years": float(years) if np.isfinite(years) else np.nan,
    }

    weights = getattr(result, "weights", None)
    if weights is not None and not weights.empty:
        turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
        out["avg_gross_exposure"] = float(weights.abs().sum(axis=1).mean())
        out["max_gross_exposure"] = float(weights.abs().sum(axis=1).max())
        out["turnover_per_bar"] = float(turnover.mean())
        out["turnover_annual"] = float(turnover.mean() * bars_per_year)

    costs = getattr(result, "costs", None)
    if costs is not None and not costs.empty and equity.iloc[0] > 0:
        total_costs = float(costs.sum())
        out["total_costs"] = total_costs
        out["cost_drag_return"] = total_costs / float(equity.iloc[0])
        gross = total_return + out["cost_drag_return"]
        # The number that decides whether an edge is real: how much of the gross
        # result the frictions consumed.
        out["cost_share_of_gross"] = float(out["cost_drag_return"] / gross) if gross > 0 else np.nan

    funding = getattr(result, "funding", None)
    if funding is not None and not funding.empty:
        out["total_funding"] = float(funding.sum())

    trades = getattr(result, "trades", None)
    if trades is not None and not trades.empty:
        out["n_trades"] = int(len(trades))
        out["avg_trade_notional"] = float(trades["notional"].mean())
        out["avg_slippage_bps"] = float(trades["slippage_bps"].mean())
        out["trades_per_year"] = float(len(trades) / years) if years and years > 0 else np.nan

    return out


def trade_statistics(result, prices: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Round-trip level statistics, reconstructed from the fill log.

    A "round trip" is a position going from flat to flat in one symbol. This is what a
    trader means by a trade, as opposed to the individual rebalancing fills the engine
    records.
    """
    trades = getattr(result, "trades", pd.DataFrame())
    if trades.empty:
        return pd.DataFrame()

    rows = []
    for symbol, group in trades.groupby("symbol"):
        position = 0.0
        cost_basis = 0.0
        entry_ts = None
        for ts, row in group.iterrows():
            qty = row["qty"]
            if position == 0.0:
                entry_ts = ts
                cost_basis = 0.0
            prior = position
            position += qty
            cost_basis += qty * row["price"] + row["commission"]
            # Flat again (or flipped through zero): close the round trip.
            if prior != 0.0 and (position == 0.0 or np.sign(position) != np.sign(prior)):
                exit_value = -prior * row["price"]
                pnl = exit_value - cost_basis + (position * row["price"] if position != 0 else 0.0)
                rows.append(
                    {
                        "symbol": symbol,
                        "entry": entry_ts,
                        "exit": ts,
                        "bars_held": None,
                        "pnl": pnl,
                        "side": "long" if prior > 0 else "short",
                    }
                )
                cost_basis = position * row["price"] if position != 0 else 0.0
                entry_ts = ts if position != 0 else None

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["win"] = out["pnl"] > 0
    return out


def summarise_round_trips(round_trips: pd.DataFrame) -> dict:
    if round_trips.empty:
        return {}
    wins = round_trips[round_trips["pnl"] > 0]["pnl"]
    losses = round_trips[round_trips["pnl"] <= 0]["pnl"]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "n_round_trips": int(len(round_trips)),
        "hit_rate": float((round_trips["pnl"] > 0).mean()),
        "avg_win": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss": float(losses.mean()) if len(losses) else np.nan,
        "payoff_ratio": float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) and losses.mean() != 0 else np.nan,
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.nan,
        "expectancy": float(round_trips["pnl"].mean()),
    }


def compare(results: dict[str, object], bars_per_year: float = 365 * 24) -> pd.DataFrame:
    """Side-by-side metric table for several backtests, including the benchmark."""
    rows = {}
    for name, res in results.items():
        metrics = getattr(res, "metrics", None) or performance_metrics(res, bars_per_year)
        rows[name] = metrics
    df = pd.DataFrame(rows).T
    preferred = [
        "cagr", "annual_vol", "sharpe", "sortino", "calmar", "max_drawdown",
        "max_dd_duration_bars", "turnover_annual", "cost_share_of_gross", "n_trades",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    return df[cols]
