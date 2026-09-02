"""Multi-asset trend following — the timing layer the portfolio module lacks.

An allocator answers "how much of each", never "should I hold this at all". Feed
`risk_parity` a market that has fallen 40% and it will keep holding it at the weight its
covariance estimate implies. Every managed-futures programme that has survived since the
1980s pairs a risk allocator with a *timing* signal, and this module is that signal.

The construction is the standard one, and the reasons each piece exists matter more than
the formulas:

**Multiple horizons, not one.** A single 200-day moving average is a bet on one holding
period, and which horizon works shifts between decades — fast trend dominated the 1970s
and 2008, slow trend the 1990s. Averaging across horizons is not a hedge against
ignorance, it is the honest admission that the right horizon is unknowable in advance
and that the choice of one is the single largest fitted parameter in most trend research.

**Volatility-scaled, always.** The raw signal says direction; position size must come
from risk. Holding the same notional in TLT (6% vol) and USO (35% vol) means the oil
position dominates the book's variance and the bond position is decorative. Scaling each
leg to a common risk budget is what makes a fifteen-asset book actually fifteen bets
rather than three.

**Skewed toward long, deliberately not long-only.** Equities and bonds have a positive
risk premium; commodities and the dollar do not. A trend system that cannot go short
gives up most of what made trend following worth running — the 2008 and 2022 crises are
where the strategy earned its reputation, and it earned it short.

**No parameter was searched.** The horizons (32/64/128/256 days) are the standard
geometric ladder, the volatility window is 60 days, and the caps are risk limits rather
than tuned values. That is the point: a trend system whose parameters were optimised on
the sample is not evidence of trend, it is evidence of optimisation. The Deflated Sharpe
Ratio in `qt.validation` exists to price exactly that distinction, and it can only do so
honestly if the number of trials it is told about is the real one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class TrendSpec:
    """Trend configuration. The defaults are conventional, not fitted."""

    # Geometric ladder of horizons, in bars. Each contributes equally.
    horizons: tuple[int, ...] = (32, 64, 128, 256)
    vol_window: int = 60          # bars for the volatility estimate used in sizing
    vol_floor: float = 1e-6
    target_vol: float = 0.10      # annualised, for the whole book
    max_weight: float = 0.25      # per instrument
    max_gross: float = 1.5        # sum of |weights|
    allow_short: bool = True
    # Squash the raw z-score through tanh rather than clipping. A linear signal keeps
    # scaling with the strength of a move, so the largest position is always taken at the
    # most extended point of a trend — precisely where reversals happen. tanh saturates.
    response: str = "tanh"
    scale: float = 1.0            # divisor inside tanh; larger = slower saturation
    bars_per_year: float = 252.0
    # Bars between rebalances. Daily is not the neutral choice it looks like: on a
    # fifteen-asset ETF book it handed roughly 10% of the gross return to execution,
    # while the signal's own horizons are 32 to 256 days. Rebalancing far faster than
    # the signal changes is paying to re-express the same view. 5 = weekly.
    rebalance_every: int = 5

    def to_meta(self) -> dict:
        return {
            "horizons": list(self.horizons), "vol_window": self.vol_window,
            "target_vol": self.target_vol, "max_weight": self.max_weight,
            "max_gross": self.max_gross, "allow_short": self.allow_short,
            "response": self.response, "scale": self.scale,
        }


def _ewm_vol(returns: pd.DataFrame, window: int, bars_per_year: float) -> pd.DataFrame:
    """Annualised EWMA volatility. Causal: uses only data up to and including each bar."""
    return returns.ewm(span=window, min_periods=max(window // 2, 5)).std(bias=False) * np.sqrt(bars_per_year)


def trend_score(prices: pd.DataFrame, spec: TrendSpec | None = None) -> pd.DataFrame:
    """Signal in roughly [-1, 1] per instrument, averaged across horizons.

    Each horizon contributes a normalised momentum: the log return over that horizon
    divided by the volatility of a return over that same horizon. Dividing by
    `vol * sqrt(h)` rather than by `vol` is what makes horizons comparable — a 5% move
    over 32 days and a 5% move over 256 days are not the same evidence, and an unscaled
    average silently weights the slow horizons far more heavily.
    """
    spec = spec or TrendSpec()
    log_prices = np.log(prices.astype("float64"))
    returns = log_prices.diff()
    daily_vol = returns.ewm(span=spec.vol_window,
                            min_periods=max(spec.vol_window // 2, 5)).std(bias=False)

    parts = []
    for h in spec.horizons:
        move = log_prices.diff(h)
        # Volatility of an h-bar move under a random walk.
        scale = daily_vol.clip(lower=spec.vol_floor) * np.sqrt(h)
        z = move / scale
        parts.append(z)

    raw = sum(parts) / len(parts)
    if spec.response == "tanh":
        signal = np.tanh(raw / max(spec.scale, 1e-9))
    else:
        signal = raw.clip(-1.0, 1.0)

    if not spec.allow_short:
        signal = signal.clip(lower=0.0)
    # A horizon needs its full lookback before it means anything; the longest one governs.
    return signal.where(log_prices.diff(max(spec.horizons)).notna())


def trend_weights(prices: pd.DataFrame, spec: TrendSpec | None = None) -> pd.DataFrame:
    """Portfolio weights: direction from trend, size from inverse volatility.

    The weight for each instrument is `signal * (target_vol / n) / instrument_vol`, so
    every leg contributes the same risk budget when fully invested. Two caps then apply:
    a per-instrument ceiling, and a gross ceiling on the sum of absolute weights.

    The gross cap is applied by *scaling the whole book down*, never by truncating the
    largest positions. Truncating changes the relative composition — it silently converts
    a diversified book into a concentrated one at exactly the moment risk is highest.
    """
    spec = spec or TrendSpec()
    signal = trend_score(prices, spec)
    returns = np.log(prices.astype("float64")).diff()
    ann_vol = _ewm_vol(returns, spec.vol_window, spec.bars_per_year)

    n = prices.shape[1]
    budget = spec.target_vol / max(n, 1)
    weights = signal * (budget / ann_vol.clip(lower=spec.vol_floor))
    weights = weights.clip(-spec.max_weight, spec.max_weight)

    gross = weights.abs().sum(axis=1)
    over = gross > spec.max_gross
    if over.any():
        # Scale, do not truncate: preserve the book's composition.
        weights.loc[over] = weights.loc[over].div(gross[over], axis=0) * spec.max_gross

    weights = weights.fillna(0.0)

    if spec.rebalance_every and spec.rebalance_every > 1:
        # Hold the book between rebalances. Forward-filling from the scheduled bar is
        # causal — each block carries the weights computed at its own start, never a
        # later one.
        step = pd.Series(np.arange(len(weights)) // spec.rebalance_every, index=weights.index)
        weights = weights.groupby(step).transform("first")

    return weights


@dataclass
class TrendResult:
    weights: pd.DataFrame
    signal: pd.DataFrame
    spec: TrendSpec
    diagnostics: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {**self.spec.to_meta(), **self.diagnostics}


def build_trend(prices: pd.DataFrame, spec: TrendSpec | None = None) -> TrendResult:
    """Weights plus the diagnostics you need to know the signal is alive.

    `mean_gross` near zero means the system is never invested; `pct_long` near 1.0 means
    the short side never engages and the strategy is long-only wearing a trend costume.
    Both are silent failures — the backtest still runs and still produces a curve.
    """
    spec = spec or TrendSpec()
    signal = trend_score(prices, spec)
    weights = trend_weights(prices, spec)
    live = weights[weights.abs().sum(axis=1) > 0]

    diagnostics = {
        "bars": int(len(weights)),
        "bars_invested": int(len(live)),
        "mean_gross": round(float(weights.abs().sum(axis=1).mean()), 4),
        # Named apart from the spec's `max_gross` cap: merging both into one summary
        # dict silently overwrote the configured limit with the realised value, so the
        # summary reported a cap that had never been set.
        "realised_max_gross": round(float(weights.abs().sum(axis=1).max()), 4),
        "pct_long": round(float((weights > 0).sum().sum() / max((weights != 0).sum().sum(), 1)), 4),
        "mean_abs_signal": round(float(signal.abs().mean().mean()), 4),
        "turnover_daily": round(float(weights.diff().abs().sum(axis=1).mean()), 4),
    }
    return TrendResult(weights, signal, spec, diagnostics)


def combine_trend_and_allocator(
    trend: pd.DataFrame, allocation: pd.DataFrame, *, blend: float = 0.5,
    max_gross: float = 1.5, strict: bool = True,
) -> pd.DataFrame:
    """Overlay a timing signal on a risk allocation.

    `blend` is the weight on trend: 0.0 is the static allocator, 1.0 is pure trend. The
    two are combined multiplicatively on the sign of trend and the magnitude of the
    allocation, which is the standard "risk allocation, timed" construction — the
    allocator decides how the risk is spread, the trend decides how much of it to take.

    **`trend` must be a signal in [-1, 1] — `trend_score`, not `trend_weights`.** Both
    are DataFrames of the same shape and index, so passing the wrong one raises nothing
    and produces a plausible book. It happened: every caller passed `.weights`, whose
    typical magnitude is 0.03 against the signal's 0.53, so the timing term came out
    seventeen times too small and the result was a scaled-down allocator wearing a trend
    label. The visible symptom was a positive weight on bonds whose trend signal was
    -0.5. `strict` refuses that input rather than letting it through quietly.
    """
    if strict and not trend.empty:
        typical = float(trend.abs().stack(future_stack=True).median(skipna=True))
        if np.isfinite(typical) and typical < 0.05:
            raise ValueError(
                f"`trend` looks like weights, not a signal: median |value| is {typical:.4f}. "
                "Pass trend_score(prices, spec), which is bounded in [-1, 1]; "
                "trend_weights() is already risk-sized and multiplying it by an "
                "allocation makes the timing term vanish. Pass strict=False to override."
            )

    trend, allocation = trend.align(allocation, join="inner", axis=1)
    trend, allocation = trend.align(allocation, join="inner", axis=0)
    timed = allocation.abs() * trend
    combined = (1.0 - blend) * allocation + blend * timed

    gross = combined.abs().sum(axis=1)
    over = gross > max_gross
    if over.any():
        combined.loc[over] = combined.loc[over].div(gross[over], axis=0) * max_gross
    return combined.fillna(0.0)


def sign_flip_threshold(blend: float) -> float:
    """The trend value at which this blend actually reverses a position's direction.

    `(1-b)·w + b·|w|·s` changes sign only where `s < -(1-b)/b`. Since `s` comes from a
    tanh and is bounded in [-1, 1], **any blend at or below 0.5 can never go short**: the
    timing layer modulates size and nothing else, and the book stays on the allocator's
    side however negative the trend gets.

    That is not a defect — the measured best blend is 0.3, where the book is risk parity
    scaled between 0.7x and 1.3x — but it is invisible from the weights alone. A reader
    seeing a +0.11 weight on TLT next to a -0.53 trend signal deserves to know the
    construction made any other outcome impossible, rather than concluding the signal was
    ignored.

    Returns the required trend value, or -inf when no attainable value can flip it.
    """
    if blend <= 0.0:
        return float("-inf")
    threshold = -(1.0 - blend) / blend
    return threshold if threshold >= -1.0 else float("-inf")
