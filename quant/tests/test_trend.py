"""Trend signal, portfolio volatility targeting, and the no-trade band.

The assertions that matter here are about causality and about silence. A sizing rule that
peeks at the bar it is sizing produces a beautiful curve and no error; a trend system
whose short side never engages is a long-only book wearing a costume, and it also
produces no error.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.risk import apply_no_trade_band, portfolio_vol_target
from qt.strategies.trend import TrendSpec, build_trend, combine_trend_and_allocator, trend_score


@pytest.fixture
def trending_prices() -> pd.DataFrame:
    """Three assets: one rising, one falling, one flat noise."""
    n = 1200
    index = pd.date_range("2015-01-01", periods=n, freq="B", tz="UTC")
    rng = np.random.default_rng(4)
    noise = rng.standard_normal((n, 3)) * 0.006
    drift = np.array([0.0006, -0.0006, 0.0])
    return pd.DataFrame(100 * np.exp(np.cumsum(noise + drift, axis=0)),
                        index=index, columns=["UP", "DOWN", "FLAT"])


def test_trend_signs_follow_the_trend(trending_prices):
    signal = trend_score(trending_prices, TrendSpec()).dropna()
    assert signal["UP"].mean() > 0.3
    assert signal["DOWN"].mean() < -0.3
    assert abs(signal["FLAT"].mean()) < abs(signal["UP"].mean())


def test_signal_is_causal(trending_prices):
    """Truncating the future must not change any past value.

    Every look-ahead bug in this codebase has been of this shape: a value computed from
    the whole sample that happens to sit on a historical timestamp.
    """
    full = trend_score(trending_prices, TrendSpec())
    truncated = trend_score(trending_prices.iloc[:800], TrendSpec())
    common = truncated.index
    pd.testing.assert_frame_equal(full.loc[common], truncated, check_freq=False)


def test_short_side_actually_engages(trending_prices):
    """A trend system that is never short is long-only, and silently so."""
    result = build_trend(trending_prices, TrendSpec(allow_short=True))
    assert 0.1 < result.diagnostics["pct_long"] < 0.95
    assert result.diagnostics["mean_gross"] > 0.0, "the book is never invested"


def test_long_only_spec_never_shorts(trending_prices):
    weights = build_trend(trending_prices, TrendSpec(allow_short=False)).weights
    assert (weights >= -1e-12).all().all()


def test_gross_cap_scales_rather_than_truncates(trending_prices):
    """Truncating the largest legs concentrates the book exactly when risk is highest."""
    spec = TrendSpec(max_gross=0.30, max_weight=1.0, rebalance_every=1)
    weights = build_trend(trending_prices, spec).weights
    gross = weights.abs().sum(axis=1)
    assert gross.max() <= 0.30 + 1e-9

    # Composition must be preserved where the cap binds: the ratio between legs is
    # unchanged by a pure scaling.
    uncapped = build_trend(trending_prices, TrendSpec(max_gross=1e9, max_weight=1.0,
                                                     rebalance_every=1)).weights
    binding = gross[gross >= 0.30 - 1e-9].index
    assert len(binding) > 0, "fixture never hits the cap — the test proves nothing"
    row = binding[len(binding) // 2]
    a, b = weights.loc[row], uncapped.loc[row]
    ratio = (a / b).replace([np.inf, -np.inf], np.nan).dropna()
    assert ratio.std() == pytest.approx(0.0, abs=1e-9), "legs were rescaled unequally"


def test_rebalance_schedule_reduces_turnover(trending_prices):
    daily = build_trend(trending_prices, TrendSpec(rebalance_every=1)).weights
    monthly = build_trend(trending_prices, TrendSpec(rebalance_every=21)).weights
    assert monthly.diff().abs().sum(axis=1).mean() < daily.diff().abs().sum(axis=1).mean()


def test_portfolio_vol_target_is_causal(trending_prices):
    """The scale applied at bar t must not use bar t's return.

    Sizing a position with knowledge of the move it is about to capture is the single
    most flattering bug available, and it leaves the curve looking merely excellent.
    """
    returns = np.log(trending_prices).diff()
    weights = pd.DataFrame(0.1, index=trending_prices.index, columns=trending_prices.columns)

    scaled = portfolio_vol_target(weights, returns, target_annual_vol=0.10,
                                  bars_per_year=252, smooth=0, update_every=0)

    # Perturbing one bar's return must leave that bar's weight unchanged.
    poisoned = returns.copy()
    row = scaled.index[len(scaled) // 2]
    poisoned.loc[row] = poisoned.loc[row] * 50.0
    after = portfolio_vol_target(weights, poisoned, target_annual_vol=0.10,
                                 bars_per_year=252, smooth=0, update_every=0)
    assert after.loc[row].equals(scaled.loc[row]), "the scale at t saw t's own return"


def test_portfolio_vol_target_moves_realised_vol_toward_the_target(trending_prices):
    returns = np.log(trending_prices).diff()
    weights = pd.DataFrame(0.05, index=trending_prices.index, columns=trending_prices.columns)

    def realised(w):
        port = (w.shift(1) * returns.reindex_like(w)).sum(axis=1)
        return float(port.std(ddof=0) * np.sqrt(252))

    base = realised(weights)
    scaled = portfolio_vol_target(weights, returns, target_annual_vol=0.10,
                                  bars_per_year=252, max_leverage=10.0)
    assert abs(realised(scaled) - 0.10) < abs(base - 0.10)


def test_vol_target_respects_max_leverage(trending_prices):
    returns = np.log(trending_prices).diff()
    weights = pd.DataFrame(0.01, index=trending_prices.index, columns=trending_prices.columns)
    scaled = portfolio_vol_target(weights, returns, target_annual_vol=5.0,
                                  bars_per_year=252, max_leverage=2.0)
    assert (scaled.abs() <= 0.01 * 2.0 + 1e-12).all().all()


def test_no_trade_band_holds_position_through_small_moves():
    index = pd.date_range("2020-01-01", periods=100, freq="B", tz="UTC")
    rng = np.random.default_rng(9)
    target = pd.DataFrame({"A": 0.20 + rng.standard_normal(100) * 0.001}, index=index)

    held = apply_no_trade_band(target, absolute=0.005, relative=0.15)
    assert held["A"].nunique() < target["A"].nunique() / 5, "the band is not holding"
    assert held.diff().abs().sum().sum() < target.diff().abs().sum().sum()


def test_no_trade_band_lets_a_real_change_through():
    index = pd.date_range("2020-01-01", periods=40, freq="B", tz="UTC")
    target = pd.Series(0.10, index=index)
    target.iloc[20:] = -0.30  # a full reversal
    held = apply_no_trade_band(pd.DataFrame({"A": target}), absolute=0.005, relative=0.15)
    assert held["A"].iloc[-1] == pytest.approx(-0.30)


def test_blend_interpolates_between_allocator_and_trend(trending_prices):
    trend = build_trend(trending_prices, TrendSpec()).weights
    allocation = pd.DataFrame(1.0 / 3, index=trend.index, columns=trend.columns)

    pure = combine_trend_and_allocator(trend, allocation, blend=0.0)
    pd.testing.assert_frame_equal(pure, allocation.fillna(0.0), check_freq=False)

    timed = combine_trend_and_allocator(trend, allocation, blend=1.0)
    assert not timed.equals(pure)
    # With blend=1 the sign must follow the trend wherever the trend is non-zero.
    live = trend.abs() > 1e-9
    assert (np.sign(timed[live].fillna(0)) == np.sign(trend[live].fillna(0))).all().all()


def test_deflated_sharpe_refuses_to_claim_significance_without_dispersion():
    """sr_variance defaulted to zero, which made the benchmark zero and the deflation a
    no-op — while the verdict still read "significant after deflation"."""
    from qt.validation import deflated_sharpe_ratio

    rng = np.random.default_rng(1)
    rets = pd.Series(rng.standard_normal(1000) * 0.01 + 0.0008)

    blind = deflated_sharpe_ratio(rets, n_trials=50, periods_per_year=252)
    assert np.isnan(blind["deflated_sharpe"])
    assert "NOT DEFLATED" in blind["verdict"]

    informed = deflated_sharpe_ratio(rets, n_trials=50, sr_variance=0.25,
                                     periods_per_year=252)
    assert np.isfinite(informed["deflated_sharpe"])
    assert informed["benchmark_sharpe"] > 0
