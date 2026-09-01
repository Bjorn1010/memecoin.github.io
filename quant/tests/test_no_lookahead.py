"""The tests that matter most: proving the system cannot see the future.

Every other test checks that a component computes what it claims. These check the one
property whose violation invalidates everything else at once, and whose violation is
otherwise completely invisible — a leaking backtest does not crash, it just prints a
number you would happily bet on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt import features as F
from qt.backtest import BacktestConfig, run_backtest
from qt.config import CostModel, RiskLimits


def _zero_cost_config(**kw) -> BacktestConfig:
    """Costs off, limits wide: isolates timing behaviour from everything else."""
    return BacktestConfig(
        costs=CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=0.0, impact_coeff=0.0),
        risk=RiskLimits(
            target_annual_vol=1e9, max_gross_leverage=1.0, max_position_weight=1.0,
            max_daily_loss=1e9, max_drawdown=1e9, max_positions=10,
        ),
        target_annual_vol=1e9,
        rebalance_threshold=1e-6,
        rebalance_threshold_relative=0.0,
        use_estimated_spread=False,
        **kw,
    )


def test_every_feature_is_causal(bars):
    """Recomputing on truncated history must not change any earlier feature value.

    This is the whole registry at once. Any use of centred windows, negative shifts, or
    a fit over the full sample changes the early values and fails here.
    """
    F.assert_causal(bars, cut=0.6)


# Timing convention under test. The engine reads the signal stamped at bar t and
# fills at bar t+1's OPEN. In continuously-traded markets open[t+1] == close[t], so:
#
#   * a signal that knows bar t's own return is worthless — by the time it can trade,
#     that move has already happened;
#   * a signal that knows bar t+1's return is a true oracle and should print money.
#
# `_current_bar_oracle` and `_next_bar_oracle` encode exactly that pair, and the two
# tests below are only meaningful together: the first proves the engine cannot cheat,
# the second proves it is capable of trading at all.
def _current_bar_oracle(bars: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"X": np.sign(bars["close"].pct_change()).fillna(0.0)}, index=bars.index)


def _next_bar_oracle(bars: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"X": np.sign(bars["close"].pct_change().shift(-1)).fillna(0.0)}, index=bars.index
    )


def test_perfect_knowledge_of_the_current_bar_earns_nothing(bars):
    """Knowing the bar that just closed must not be profitable."""
    res = run_backtest({"X": bars}, _current_bar_oracle(bars), _zero_cost_config())
    total = res.equity.iloc[-1] / res.equity.iloc[0] - 1.0
    assert abs(total) < 2.0, f"suspicious return {total:.2%} from knowing only the current bar"


def test_perfect_foresight_does_earn(bars):
    """Control: a genuine one-bar-ahead oracle must be enormously profitable."""
    res = run_backtest({"X": bars}, _next_bar_oracle(bars), _zero_cost_config())
    total = res.equity.iloc[-1] / res.equity.iloc[0] - 1.0
    assert total > 5.0, f"a true oracle only made {total:.2%}; the engine may not be trading"


def test_no_position_before_the_first_execution(bars):
    """Flat on the first bar: nothing can be held before the first open."""
    signal = pd.DataFrame({"X": 1.0}, index=bars.index)
    res = run_backtest({"X": bars}, signal, _zero_cost_config())

    assert res.weights.iloc[0]["X"] == 0.0
    assert res.returns.iloc[0] == 0.0
    # Sizing needs a volatility estimate (~40 bars of warm-up) before it can size
    # anything, so the position appears shortly after the start rather than at bar 1.
    assert abs(res.weights.iloc[:150]["X"]).max() > 0.0


def test_shifting_a_signal_later_destroys_its_edge(bars):
    """Delaying the oracle by one bar must collapse its performance.

    A leaking engine would still profit from a stale signal, because it would be
    reading prices the signal already reflects.
    """
    fresh = _next_bar_oracle(bars)
    delayed = pd.DataFrame({"X": fresh["X"].shift(1).fillna(0.0)}, index=bars.index)

    cfg = _zero_cost_config()
    r_fresh = run_backtest({"X": bars}, fresh, cfg).equity.iloc[-1]
    r_delayed = run_backtest({"X": bars}, delayed, cfg).equity.iloc[-1]
    assert r_fresh > 5 * r_delayed


def test_labels_never_resolve_beyond_the_sample(bars):
    """Triple-barrier events whose horizon runs past the data must be dropped, not clipped."""
    from qt.labels import LabelSpec, make_labels

    ls = make_labels(bars, LabelSpec(horizon_bars=48))
    assert not ls.events.empty
    assert ls.events["t1"].max() <= bars.index.max()
    assert ls.events["t1"].notna().all()
    # And every label resolves strictly after it starts.
    assert (ls.events["t1"] > ls.events.index).all()


def test_purged_cv_removes_overlapping_labels(bars):
    """No training label may overlap the test window in time."""
    from qt.labels import LabelSpec, make_labels
    from qt.validation import PurgedKFold

    ls = make_labels(bars, LabelSpec(horizon_bars=48))
    X = pd.DataFrame({"f": 1.0}, index=ls.events.index)
    t1 = ls.events["t1"]

    cv = PurgedKFold(n_splits=4, t1=t1, embargo_pct=0.01)
    n_checked = 0
    for train_idx, test_idx in cv.split(X):
        test_start, test_end = X.index[test_idx].min(), X.index[test_idx].max()
        train_starts = X.index[train_idx]
        train_ends = pd.DatetimeIndex(t1.iloc[train_idx].to_numpy())
        overlapping = (train_starts <= test_end) & (train_ends >= test_start)
        assert not overlapping.any(), f"{overlapping.sum()} training labels overlap the test window"
        n_checked += 1
    assert n_checked >= 2


def test_feature_matrix_and_labels_align_on_event_times(bars):
    """A dataset row's features must be stamped at or before its label's start."""
    from qt.labels import LabelSpec, make_labels
    from qt.models import build_dataset

    fm = F.build_features(bars, symbol="X", groups=["ret", "mom", "vol", "flow"])
    ls = make_labels(bars, LabelSpec(horizon_bars=24))
    ds = build_dataset(fm.X, ls, "X")
    if len(ds) == 0:
        pytest.skip("no overlapping events on this synthetic sample")
    assert (ds.X.index == ds.y.index).all()
    assert (ds.t1 > ds.X.index).all()
