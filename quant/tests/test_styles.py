"""Style premia: carry, value, defensive, and how they combine with trend.

The interesting assertions are the negative ones. A style with no data must contribute
*nothing* rather than a confident zero — averaging a NaN-filled style as if it said "no
view everywhere" dilutes the styles that do have data, silently, while the report still
lists four. And a value signal built on too short a window is short-term reversal wearing
a different name; it correlates with trend instead of diversifying it, which is the whole
point of running more than one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.strategies.styles import (
    StyleSpec,
    build_styles,
    carry_signal,
    cross_sectional_z,
    defensive_signal,
    time_series_z,
    value_signal,
)


@pytest.fixture
def prices() -> pd.DataFrame:
    """Six assets with distinct behaviour: two trending, one mean-reverting, three noise."""
    n = 1800
    index = pd.bdate_range("2012-01-02", periods=n, tz="UTC")
    rng = np.random.default_rng(17)
    noise = rng.standard_normal((n, 6)) * 0.008
    drift = np.array([0.0005, -0.0005, 0.0, 0.0002, -0.0002, 0.0])
    frame = pd.DataFrame(100 * np.exp(np.cumsum(noise + drift, axis=0)),
                         index=index, columns=list("ABCDEF"))
    return frame


def test_cross_sectional_z_is_neutral_across_assets(prices):
    """Each row must sum to roughly zero — that is what makes it a relative statement."""
    z = cross_sectional_z(np.log(prices).diff(20)).dropna()
    assert abs(float(z.sum(axis=1).mean())) < 1e-9


def test_time_series_z_is_causal(prices):
    """Standardising against the full-sample mean encodes the answer into the signal."""
    signal = np.log(prices).diff(20)
    full = time_series_z(signal)
    truncated = time_series_z(signal.iloc[:1200])
    common = truncated.index
    pd.testing.assert_frame_equal(full.loc[common], truncated, check_freq=False)


def test_a_style_without_data_contributes_nothing(prices):
    """Not zero. Zero is a confident "no view" that dilutes the others by a quarter."""
    signal = carry_signal(prices, StyleSpec())  # no yields supplied
    assert signal.isna().all().all()

    spec = StyleSpec(weights={"trend": 1.0, "carry": 1.0, "value": 1.0, "defensive": 1.0})
    result = build_styles(prices, spec)
    assert "carry" in result.diagnostics["styles_skipped"]
    assert "carry" not in result.diagnostics["styles_used"]
    assert set(result.diagnostics["styles_used"]) == {"trend", "value", "defensive"}


def test_carry_uses_supplied_yields(prices):
    yields = pd.DataFrame(
        np.tile(np.array([0.06, 0.04, 0.0, 0.02, 0.0, 0.01]), (len(prices), 1)),
        index=prices.index, columns=prices.columns,
    )
    signal = carry_signal(prices, StyleSpec(mode="cross_sectional"), yields=yields).dropna()
    assert not signal.empty
    # The highest-yielding asset must score highest.
    assert signal.iloc[-1].idxmax() == "A"
    assert signal.iloc[-1].idxmin() in ("C", "E")


def test_value_is_contrarian(prices):
    """What has risen most over the anchor window must score lowest."""
    spec = StyleSpec(value_window=756, mode="cross_sectional")
    signal = value_signal(prices, spec).dropna()
    total = np.log(prices).diff(756).dropna()
    common = signal.index.intersection(total.index)
    row = common[-1]
    assert signal.loc[row].idxmax() == total.loc[row].idxmin()


def test_value_window_must_be_long_enough_to_differ_from_trend(prices):
    """A short anchor makes 'value' into short-term reversal, which cancels trend.

    This is the trap the signal always falls into, and it is invisible: the book still
    trades, it simply has one style fighting another.
    """
    from qt.strategies.styles import trend_signal

    trend = trend_signal(prices, StyleSpec(mode="cross_sectional"))

    def corr_with_trend(window: int) -> float:
        v = value_signal(prices, StyleSpec(value_window=window, mode="cross_sectional"))
        joined = pd.DataFrame({"t": trend.stack(future_stack=True),
                               "v": v.stack(future_stack=True)}).dropna()
        return abs(float(joined.corr().iloc[0, 1]))

    assert corr_with_trend(60) > corr_with_trend(1260), (
        "a short value window must correlate more with trend than a long one"
    )


def test_defensive_prefers_low_beta(prices):
    """Compare against beta over the *same trailing window* the signal uses.

    A full-sample beta is a different quantity, and asserting against it would make this
    test fail for a correct implementation — the rolling estimate is the causal one and
    is the whole point.
    """
    spec = StyleSpec(mode="cross_sectional", beta_window=252)
    signal = defensive_signal(prices, spec).dropna()
    returns = np.log(prices).diff()
    market = returns.mean(axis=1)

    row = signal.index[-1]
    window = returns.loc[:row].tail(spec.beta_window)
    mkt = market.loc[window.index]
    beta = {c: float(window[c].cov(mkt) / mkt.var()) for c in window.columns}

    assert signal.loc[row].idxmax() == min(beta, key=beta.get)
    assert signal.loc[row].idxmin() == max(beta, key=beta.get)


def test_weights_respect_the_caps(prices):
    spec = StyleSpec(max_weight=0.10, max_gross=0.8)
    weights = build_styles(prices, spec).weights
    assert weights.abs().to_numpy().max() <= 0.10 + 1e-9
    assert weights.abs().sum(axis=1).max() <= 0.8 + 1e-9


def test_gross_exposure_breathes_with_conviction(prices):
    """Normalising by gross forces the book fully invested whatever the signals say.

    That silently discards the most valuable property a signal has — being small when it
    has no view — and it cost 0.6 of Sharpe when this module first did it.
    """
    weights = build_styles(prices, StyleSpec()).weights
    gross = weights.abs().sum(axis=1)
    live = gross[gross > 0]
    assert live.std() > 0, "gross exposure is constant — conviction is being discarded"
    assert live.max() / max(live.min(), 1e-9) > 1.5


def test_default_spec_runs_only_the_style_that_measured_an_edge(prices):
    """Shipping the textbook four-style default would ship a losing configuration."""
    result = build_styles(prices, StyleSpec())
    assert set(result.diagnostics["styles_used"]) == {"trend"}


def test_correlation_matrix_reports_when_styles_are_one_bet(prices):
    spec = StyleSpec(weights={"trend": 1.0, "carry": 0.0, "value": 1.0, "defensive": 1.0},
                     mode="cross_sectional")
    result = build_styles(prices, spec)
    corr = result.correlation()
    assert not corr.empty
    assert set(corr.columns) >= {"trend", "value", "defensive"}
    assert result.diagnostics["max_style_correlation"] is not None


def test_no_usable_style_reports_rather_than_returning_a_book(prices):
    spec = StyleSpec(weights={k: 0.0 for k in ("trend", "carry", "value", "defensive")})
    result = build_styles(prices, spec)
    assert (result.weights == 0).all().all()
    assert "warning" in result.diagnostics
