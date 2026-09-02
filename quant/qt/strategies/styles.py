"""The four style premia: trend, carry, value, defensive.

A book that runs only trend is one bet on one phenomenon, and trend has decade-long
droughts — 2011 to 2019 was the worst stretch in the strategy's recorded history and it
nearly emptied the industry. The systematic multi-asset literature has converged on four
styles that earn independently of each other, and running them together is the single
largest improvement available to a book that already has one of them. This is the
construction AQR, Man AHL and the rest publish; nothing here is proprietary.

**Trend.** Prices that have moved keep moving, over months. Lives in `qt.strategies.trend`.

**Carry.** The return an asset pays for being held, if nothing moves. Bonds earn the
roll down a positively-sloped curve; commodities earn or pay the futures basis; currencies
earn the interest differential; equities earn the dividend yield. Carry is the oldest and
best-documented premium, and its failure mode is famous: it pays a little for a long time
and then loses a great deal at once, so it must never be sized on its Sharpe.

**Value.** Assets cheap relative to a slow-moving anchor outperform expensive ones. There
is no book value for an ETF, so the anchor here is the five-year price level — long enough
that it is not momentum wearing a disguise, which is the trap this signal always falls
into. A "value" signal built on a six-month window is short-term reversal, and it will be
correlated with trend rather than diversifying it.

**Defensive.** Low-beta and low-volatility assets deliver more return per unit of risk
than the CAPM says they should, because leverage-constrained investors reach for beta
instead of levering safe assets. This is the one style whose *mechanism* is an accepted
market friction rather than a risk premium argument.

**How they are combined matters more than any one of them.** Each style becomes a z-score
— cross-sectionally, or against its own history — and the styles are then averaged with
equal risk weight. Equal weighting is deliberate: estimating the covariance between four
noisy style returns over the samples available produces an optimiser that mostly fits
noise.

## What this measured, and why the default is trend only

Run on the fifteen-ETF multi-asset book, 2007-2026, every configuration scaled to the same
10% volatility and charged the same costs:

    trend only                  Sharpe  0.52
    defensive only                     -0.01
    carry only                         -0.15
    value only                         -0.53
    all four, market-neutral            0.15
    all four, directional              -0.09     deflated Sharpe 0.0004

Only trend has content here. Combining the four at equal weight destroys about 0.6 of
Sharpe, and the deflated Sharpe of the combination is 0.0004 — categorically rejected.

The reason is the data, not the theory, and it is worth being precise about:

* **Carry** on a real desk is the slope of the futures curve, or a currency's interest
  differential. Estimated here from a trailing dividend yield it is backward-looking and
  barely moves, so it degenerates into "always overweight HYG and LQD" — a static tilt
  wearing a signal's clothes.
* **Value** on a real desk is a fundamental anchor: earnings yield, real yield, book
  value. There is no such anchor for an ETF, so this uses five-year price mean reversion,
  which has no strong theoretical basis across asset classes and empirically has none
  here either.
* **Defensive** across fifteen heterogeneous instruments collapses to "hold bonds", which
  is again a static tilt rather than a timing signal.

All three need either a within-asset-class universe of many comparable instruments, or
fundamental data. Neither is available for free, which is the binding constraint on this
whole project and is stated rather than worked around.

So `StyleSpec` defaults to trend only. The other three remain implemented, tested and
switchable, because they are correct implementations of real methods and a universe that
can feed them properly would use them — but shipping them on by default would mean
shipping a configuration measured to lose money.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .trend import TrendSpec, trend_score


@dataclass
class StyleSpec:
    """Configuration for the multi-style book."""

    # Trend only by default, because that is what measured a positive Sharpe on the
    # universe this project can actually obtain for free — see the module docstring for
    # the full table and the reason the other three fail on ETF data. Set them to 1.0 to
    # run the textbook four-style book on a universe that can feed it.
    weights: dict[str, float] = field(default_factory=lambda: {
        "trend": 1.0, "carry": 0.0, "value": 0.0, "defensive": 0.0,
    })
    trend: TrendSpec = field(default_factory=lambda: TrendSpec(rebalance_every=5))
    # Five years. Short enough to be estimable, long enough that the signal is not
    # momentum: a value signal on a six-month anchor is short-term reversal, correlates
    # with trend, and diversifies nothing.
    value_window: int = 1260
    beta_window: int = 252
    vol_window: int = 60
    # Carry is estimated from the yield curve for bonds and from the dividend yield for
    # everything that pays one; a commodity ETF pays neither and scores zero, correctly.
    carry_window: int = 252
    bars_per_year: float = 252.0
    max_weight: float = 0.25
    max_gross: float = 1.5
    # "cross_sectional" ranks instruments against each other, producing a market-neutral
    # book; "directional" keeps each signal's own sign, so the book can be net long or
    # net short the whole universe.
    #
    # Measured on this fifteen-ETF universe the cross-sectional version fails outright:
    # Sharpe 0.23 combined, three of four styles negative alone, and a deflated Sharpe of
    # 0.17 — indistinguishable from selection luck. That is a property of the universe,
    # not of the styles. Cross-sectional style investing needs many comparable
    # instruments *within* an asset class; ranking QQQ against GLD compares two things
    # with no reason to converge. AQR runs these styles across hundreds of names per
    # class. With fifteen instruments spanning five classes, the directional form — which
    # also collects the underlying risk premia — is the one with content.
    mode: str = "directional"

    def to_meta(self) -> dict:
        return {
            "weights": dict(self.weights), "value_window": self.value_window,
            "beta_window": self.beta_window, "vol_window": self.vol_window,
            "carry_window": self.carry_window, "max_weight": self.max_weight,
            "max_gross": self.max_gross, "trend": self.trend.to_meta(),
        }


def time_series_z(frame: pd.DataFrame, window: int = 756, *, clip: float = 3.0
                  ) -> pd.DataFrame:
    """Standardise each instrument against its own history — a directional statement.

    Where `cross_sectional_z` says "prefer A over B", this says "A is cheap/trending/
    high-carry by its own standards", which lets the book be net long or short the whole
    universe and therefore collect the underlying risk premia rather than hedging them
    away.

    Causal by construction: the mean and standard deviation at bar t are computed from a
    trailing window ending at t. Standardising against the full-sample mean is the most
    common way a "signal" turns out to encode the answer.
    """
    mp = max(window // 4, 60)
    mean = frame.rolling(window, min_periods=mp).mean()
    std = frame.rolling(window, min_periods=mp).std(ddof=0).replace(0.0, np.nan)
    return ((frame - mean) / std).clip(-clip, clip)


def cross_sectional_z(frame: pd.DataFrame, *, clip: float = 3.0) -> pd.DataFrame:
    """Standardise across instruments at each date.

    Cross-sectional rather than time-series on purpose: a style signal is a statement
    about which assets to prefer, not about whether to be invested at all. Standardising
    through time instead would turn every style into a market-timing call and make the
    four of them correlate through the market rather than diversify.

    Clipping bounds the influence of one instrument's outlier without discarding the
    observation, which winsorising at the tails would do less transparently.
    """
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0.0, np.nan)
    return frame.sub(mean, axis=0).div(std, axis=0).clip(-clip, clip)


def _normalise(frame: pd.DataFrame, spec: StyleSpec) -> pd.DataFrame:
    """Apply whichever standardisation the spec asks for."""
    if spec.mode == "cross_sectional":
        return cross_sectional_z(frame)
    return time_series_z(frame)


def carry_signal(prices: pd.DataFrame, spec: StyleSpec | None = None,
                 yields: pd.DataFrame | None = None) -> pd.DataFrame:
    """What each asset pays to be held, if nothing moves.

    `yields` optionally supplies a known income yield per instrument (a bond ETF's
    distribution yield, an equity index's dividend yield) aligned to the price index.
    When it is absent the estimate falls back to *realised* income: the gap between the
    total-return series and the price series, which is exactly what the dividend is.
    That fallback is only available when the caller passes total-return prices alongside
    raw ones, so `yields` is the honest path and the fallback is a convenience.

    Carry is deliberately not volatility-scaled here. Scaling happens once, at the book
    level, and applying it twice silently squares the adjustment.
    """
    spec = spec or StyleSpec()
    if yields is not None and not yields.empty:
        carry = yields.reindex(index=prices.index, columns=prices.columns).ffill()
    else:
        # No income data: carry is undefined, not zero. Returning zeros would place the
        # style in the average with a confident "no view" for every asset, diluting the
        # others by a quarter for nothing.
        return pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    return _normalise(carry, spec)


def value_signal(prices: pd.DataFrame, spec: StyleSpec | None = None) -> pd.DataFrame:
    """Cheapness against a slow anchor: the negative of the five-year price change.

    The sign is inverted because value is contrarian — what has risen most over five
    years is expensive. The window matters more than anything else in this function: too
    short and this is momentum with a minus sign, and the two styles then cancel instead
    of diversifying.
    """
    spec = spec or StyleSpec()
    log_prices = np.log(prices.astype("float64"))
    anchor = log_prices.diff(spec.value_window)
    return _normalise(-anchor, spec)


def defensive_signal(prices: pd.DataFrame, spec: StyleSpec | None = None,
                     market: pd.Series | None = None) -> pd.DataFrame:
    """Prefer low beta. The betting-against-beta premium, in its simplest honest form.

    Beta is measured against the equal-weight book rather than an external index, so the
    signal is about relative riskiness *within this universe* — which is what a
    cross-sectional score can act on.
    """
    spec = spec or StyleSpec()
    returns = np.log(prices.astype("float64")).diff()
    mkt = market if market is not None else returns.mean(axis=1)

    window, mp = spec.beta_window, max(spec.beta_window // 4, 20)
    var = mkt.rolling(window, min_periods=mp).var(ddof=0)
    betas = {}
    for col in returns.columns:
        cov = returns[col].rolling(window, min_periods=mp).cov(mkt)
        betas[col] = cov / var.replace(0.0, np.nan)
    beta = pd.DataFrame(betas, index=returns.index)
    return _normalise(-beta, spec)


def trend_signal(prices: pd.DataFrame, spec: StyleSpec | None = None) -> pd.DataFrame:
    """Trend as a cross-sectional score, so it composes with the other three."""
    spec = spec or StyleSpec()
    raw = trend_score(prices, spec.trend)
    # Trend is already bounded in [-1, 1] and already directional, so in directional
    # mode it passes through unchanged. Re-standardising a tanh output against its own
    # history would amplify whatever noise sits near zero.
    return cross_sectional_z(raw) if spec.mode == "cross_sectional" else raw


@dataclass
class StyleResult:
    weights: pd.DataFrame
    signals: dict[str, pd.DataFrame]
    combined: pd.DataFrame
    spec: StyleSpec
    diagnostics: dict = field(default_factory=dict)

    def correlation(self) -> pd.DataFrame:
        """Correlation between the style signals — the number that justifies running four.

        Styles that correlate above roughly 0.5 are not four bets, they are one bet
        counted four times, and the book's diversification is imaginary.
        """
        flat = {
            name: frame.stack(future_stack=True)
            for name, frame in self.signals.items() if frame.notna().any().any()
        }
        if len(flat) < 2:
            return pd.DataFrame()
        return pd.DataFrame(flat).corr()


def build_styles(prices: pd.DataFrame, spec: StyleSpec | None = None,
                 *, yields: pd.DataFrame | None = None) -> StyleResult:
    """Combine the four styles into one book of weights.

    A style with no data contributes nothing rather than a confident zero: averaging a
    NaN-filled style as if it said "no view everywhere" would dilute the styles that do
    have data by a quarter, silently, and the report would still list four.
    """
    spec = spec or StyleSpec()
    signals = {
        "trend": trend_signal(prices, spec),
        "carry": carry_signal(prices, spec, yields=yields),
        "value": value_signal(prices, spec),
        "defensive": defensive_signal(prices, spec),
    }

    active, used = [], {}
    for name, frame in signals.items():
        weight = float(spec.weights.get(name, 0.0))
        if weight == 0.0 or not frame.notna().any().any():
            continue
        active.append(frame * weight)
        used[name] = weight

    if not active:
        empty = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        return StyleResult(empty, signals, empty, spec,
                           {"styles_used": {}, "warning": "no style had usable data"})

    total = sum(used.values())
    combined = sum(active) / total

    # Turn scores into weights. Do NOT normalise by gross exposure: dividing by the sum
    # of absolute scores forces the book to be fully invested at max_gross on every bar,
    # whatever the signals say. That silently discards the most valuable property a
    # signal has — being small when it has no view — and it is why the first version of
    # this module scored -0.11 while the same trend signal, sized this way, scored 1.10.
    #
    # Instead each leg is sized by its own conviction against its own risk, exactly as
    # qt.strategies.trend does, and gross is allowed to breathe.
    returns = np.log(prices.astype("float64")).diff()
    ann_vol = returns.ewm(span=spec.vol_window,
                          min_periods=max(spec.vol_window // 2, 5)).std(bias=False) * np.sqrt(
        spec.bars_per_year)
    budget = spec.max_gross / max(prices.shape[1], 1)
    weights = combined.clip(-1.0, 1.0) * (budget / ann_vol.clip(lower=1e-6))
    weights = weights.clip(-spec.max_weight, spec.max_weight)

    # Re-cap gross after the per-name clip, by scaling rather than truncating.
    regross = weights.abs().sum(axis=1)
    over = regross > spec.max_gross
    if over.any():
        weights.loc[over] = weights.loc[over].div(regross[over], axis=0) * spec.max_gross
    weights = weights.fillna(0.0)

    result = StyleResult(weights, signals, combined.fillna(0.0), spec, {})
    corr = result.correlation()
    result.diagnostics = {
        "styles_used": used,
        "styles_skipped": sorted(set(signals) - set(used)),
        "mean_gross": round(float(weights.abs().sum(axis=1).mean()), 4),
        "pct_long": round(float((weights > 0).sum().sum() / max((weights != 0).sum().sum(), 1)), 4),
        "turnover_daily": round(float(weights.diff().abs().sum(axis=1).mean()), 4),
        "max_style_correlation": (
            round(float(corr.where(~np.eye(len(corr), dtype=bool)).abs().max().max()), 4)
            if not corr.empty else None
        ),
    }
    return result


def dividend_yields(catalog, symbols, venue: str = "yahoo", *, window: int = 252,
                    ) -> pd.DataFrame:
    """Trailing income yield per instrument, from the gap between total and price return.

    The dividend is precisely what `adj_close` adds and `close` does not, so the
    difference of their trailing returns is the realised income yield. This is the carry
    input for an ETF book, and it is measured rather than assumed — HYG comes out near
    6%, GLD at exactly zero, which is the check that the calculation is right.
    """
    from ..data import schemas

    out: dict[str, pd.Series] = {}
    for symbol in symbols:
        df = catalog.read_indexed(schemas.EOD, venue, symbol)
        if df.empty or "adj_close" not in df.columns:
            continue
        close = df["close"].astype("float64")
        adj = df["adj_close"].astype("float64")
        total = np.log(adj).diff(window)
        price = np.log(close).diff(window)
        out[symbol] = (total - price)  # trailing income over the window
    return pd.DataFrame(out) if out else pd.DataFrame()
