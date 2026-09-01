"""Position sizing — converting an opinion into an amount of money.

Sizing is where most of the realised Sharpe actually comes from, and it is chronically
under-thought relative to signal research. Two ideas do most of the work:

**Volatility targeting.** Hold a constant *risk* rather than a constant *notional*.
A fixed position size means risk swings with the market: the same 1 BTC is a modest
position at 30% annualised vol and a reckless one at 120%. Scaling exposure inversely
to forecast volatility flattens that out, and it is the single most reliable
improvement to a trend-following book — it raises Sharpe and cuts drawdown at the same
time, which almost nothing else does.

**Fractional Kelly.** Full Kelly maximises long-run growth, and its drawdowns are
unbearable: with any estimation error at all it overbets, and estimation error in
financial edges is enormous. Half Kelly gives ~75% of the growth at ~half the
volatility; quarter Kelly is the practical default here. Kelly is also *not* used as a
standalone sizer — it caps the vol-targeted size rather than replacing it, because a
Kelly fraction computed from a misestimated edge is unbounded nonsense.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def volatility_target_weight(
    signal: pd.Series,
    volatility: pd.Series,
    *,
    target_annual_vol: float = 0.20,
    bars_per_year: float = 365 * 24,
    max_leverage: float = 2.0,
    vol_floor: float = 1e-6,
) -> pd.Series:
    """Scale a signal in [-1, 1] to a portfolio weight targeting constant risk.

    `volatility` is the per-bar forecast standard deviation of returns (causal, e.g. an
    EWMA of realised vol). The resulting weight is signal x (target vol / forecast vol),
    capped at `max_leverage`.
    """
    ann_vol = volatility.astype("float64") * np.sqrt(bars_per_year)
    scale = (target_annual_vol / ann_vol.clip(lower=vol_floor)).replace([np.inf, -np.inf], np.nan)
    weight = signal.astype("float64") * scale
    return weight.clip(-max_leverage, max_leverage).fillna(0.0)


def kelly_from_probability(prob_win: pd.Series | float, payoff_ratio: float = 1.0) -> pd.Series | float:
    """Kelly fraction for a binary bet: f = p - (1-p)/b.

    `payoff_ratio` is the ratio of average win to average loss — for a triple-barrier
    label with pt_sl=(2, 1), b = 2. Negative results mean the bet is unfavourable and
    the correct size is zero, not a short (the sign belongs to the signal).
    """
    p = prob_win if isinstance(prob_win, (int, float)) else prob_win.astype("float64")
    b = max(payoff_ratio, 1e-9)
    f = p - (1 - p) / b
    if isinstance(f, float):
        return max(f, 0.0)
    return f.clip(lower=0.0)


def kelly_from_edge(edge: pd.Series, volatility: pd.Series, bars_per_year: float = 365 * 24) -> pd.Series:
    """Continuous Kelly: f = expected excess return / variance.

    `edge` here is interpreted as an expected per-bar return forecast. In practice the
    model's edge output is a conviction score, not a return forecast, so this is used
    with a scaling calibrated on out-of-sample data — never on the raw score.
    """
    var = (volatility.astype("float64") ** 2).replace(0.0, np.nan)
    return (edge.astype("float64") / var).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def size_position(
    signal: pd.Series,
    volatility: pd.Series,
    *,
    target_annual_vol: float = 0.20,
    kelly_fraction: float = 0.25,
    prob_win: pd.Series | None = None,
    payoff_ratio: float = 1.0,
    bars_per_year: float = 365 * 24,
    max_leverage: float = 2.0,
    max_position_weight: float = 0.35,
) -> pd.Series:
    """The house sizing rule: vol-targeted, Kelly-capped, hard-limited.

    Order of operations matters. Vol targeting sets the base size, Kelly can only
    *reduce* it (never increase), and the per-instrument cap is applied last so it can
    never be argued away by an upstream estimate.
    """
    base = volatility_target_weight(
        signal,
        volatility,
        target_annual_vol=target_annual_vol,
        bars_per_year=bars_per_year,
        max_leverage=max_leverage,
    )
    if prob_win is not None:
        kelly = kelly_from_probability(prob_win.reindex(base.index), payoff_ratio) * kelly_fraction
        # Kelly attenuates; it never levers up.
        base = base * kelly.clip(0.0, 1.0).fillna(0.0)
    return base.clip(-max_position_weight, max_position_weight)


def inverse_vol_weights(volatilities: pd.DataFrame, *, floor: float = 1e-8) -> pd.DataFrame:
    """Risk-parity weights across instruments: each contributes equal risk."""
    inv = 1.0 / volatilities.astype("float64").clip(lower=floor)
    total = inv.sum(axis=1).replace(0.0, np.nan)
    return inv.div(total, axis=0).fillna(0.0)


def correlation_adjusted_leverage(
    weights: pd.DataFrame, returns: pd.DataFrame, window: int = 336, target_annual_vol: float = 0.20,
    bars_per_year: float = 365 * 24, max_leverage: float = 2.0,
) -> pd.Series:
    """Scale the whole book so that *portfolio* vol hits target, not the sum of parts.

    Summing individually vol-targeted positions overshoots badly when the book is
    correlated — and a crypto book is essentially one factor, so ten "independent"
    positions can carry three times the intended risk. This computes realised portfolio
    volatility on a trailing window and rescales.
    """
    aligned = returns.reindex(columns=weights.columns).fillna(0.0)
    port_ret = (weights.shift(1).fillna(0.0) * aligned).sum(axis=1)
    realised = port_ret.rolling(window, min_periods=max(window // 4, 20)).std(ddof=0) * np.sqrt(bars_per_year)
    scale = (target_annual_vol / realised.replace(0.0, np.nan)).clip(upper=max_leverage)
    return scale.fillna(1.0)
