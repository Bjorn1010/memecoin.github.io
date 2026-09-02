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


def portfolio_vol_target(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    target_annual_vol: float = 0.10,
    window: int = 60,
    bars_per_year: float = 252.0,
    max_leverage: float = 3.0,
    min_periods: int | None = None,
    vol_floor: float = 1e-6,
    smooth: int = 21,
    update_every: int = 21,
) -> pd.DataFrame:
    """Scale a whole book so its *realised portfolio* volatility hits a target.

    An allocator decides how risk is spread between instruments; nothing in it decides
    how much risk to take in total. Without this step the book runs at whatever
    volatility the weights happen to imply — a diversified fifteen-asset book summing to
    gross 0.5 came out at 2.4% annualised against a 10% target, which makes every Sharpe
    comparison against a benchmark meaningless: the strategy was not underperforming, it
    was barely invested.

    The estimate must be built from the volatility of the *portfolio*, not the average
    of the instruments' volatilities. Those differ by exactly the diversification the
    book was constructed to capture, and using the average throws it away.

    Causality: the scale applied at bar *t* is computed from portfolio returns up to
    t-1. Using the same bar's return would size the position with knowledge of the move
    it is about to profit from — the most flattering look-ahead bug there is, and one
    that leaves the equity curve looking merely excellent rather than absurd.

    `max_leverage` is a hard cap, and it binds in calm markets: a book at 2% realised
    volatility needs 5x to reach a 10% target, which is real leverage with real funding
    and gap risk, not a free scaling factor.
    """
    if weights.empty or returns.empty:
        return weights

    aligned_returns = returns.reindex(index=weights.index, columns=weights.columns)
    # Portfolio return of the book actually held: yesterday's weights on today's returns.
    port = (weights.shift(1) * aligned_returns).sum(axis=1)

    mp = min_periods if min_periods is not None else max(window // 2, 10)
    realised = port.rolling(window, min_periods=mp).std(ddof=0) * np.sqrt(bars_per_year)
    # .shift(1) is the causality guarantee: bar t is scaled by an estimate that ends at
    # t-1 and therefore cannot contain t's own return.
    scale = (target_annual_vol / realised.clip(lower=vol_floor)).shift(1)
    scale = scale.replace([np.inf, -np.inf], np.nan)

    # A leverage scalar recomputed every bar is a turnover pump. The raw multi-asset
    # trend book turned over 7.1x a year; rescaling it daily took that to 26.7x and
    # handed 9.5% of the gross return to the broker, for a risk target that a monthly
    # update tracks just as well. Volatility is persistent enough that the scalar barely
    # moves over a month, so smoothing costs nothing in risk control and saves most of
    # the turnover. Every desk that runs volatility targeting does this.
    if smooth and smooth > 1:
        scale = scale.ewm(span=smooth, min_periods=1).mean()
    if update_every and update_every > 1:
        # Hold the scalar between scheduled updates rather than drifting continuously.
        step = pd.Series(np.arange(len(scale)) // update_every, index=scale.index)
        scale = scale.groupby(step).transform("first")

    scale = scale.clip(upper=max_leverage)

    # Before the window fills there is no estimate. Leaving the weights unscaled there
    # would silently run the early sample at a different risk level than the rest.
    scaled = weights.mul(scale, axis=0)
    return scaled.dropna(how="all").fillna(0.0)


def apply_no_trade_band(weights: pd.DataFrame, *, absolute: float = 0.005,
                        relative: float = 0.15) -> pd.DataFrame:
    """Hold the previous weight until the target moves enough to be worth the cost.

    A trend signal is continuous, so without a band the book is rebalanced every single
    bar on noise: the raw multi-asset trend system turned over 7.1x a year and spent
    7.8% of its gross return on costs. The band is the larger of an absolute floor and a
    fraction of the target, which is the standard construction — an absolute-only band
    is a no-op on large positions and a full flip on small ones.
    """
    if weights.empty:
        return weights

    target = weights.to_numpy(dtype="float64")
    held = np.zeros_like(target)
    current = np.zeros(target.shape[1])
    for i in range(target.shape[0]):
        want = target[i]
        threshold = np.maximum(absolute, relative * np.abs(want))
        move = np.abs(want - current) >= threshold
        current = np.where(move, want, current)
        held[i] = current
    return pd.DataFrame(held, index=weights.index, columns=weights.columns)
