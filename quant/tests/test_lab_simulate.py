"""The simulator's conventions, each one locked by a test that fails if it is broken."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.lab import strategies as S
from qt.lab.hypotheses import HYPOTHESES, active
from qt.lab.markets import CostProfile
from qt.lab.simulate import StrategyOutput, simulate, simulate_weights

FREE = CostProfile(0.0, 0.0, 0.0)


def daily_bars(n=800, seed=1, drift=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n, freq="B", tz="UTC")
    r = rng.normal(drift, 0.01, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = close * np.exp(rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    vol = rng.lognormal(10, 0.3, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol,
                         "raw_close": close}, index=idx)


def ann_sharpe(r):
    return r.mean() / r.std() * np.sqrt(252)


def test_knowing_todays_bar_earns_nothing():
    """Trading on today's close-to-close move, executed tomorrow, is worth nothing."""
    b = daily_bars()
    today = np.sign(b["close"].pct_change()).fillna(0.0)
    r = simulate(b, StrategyOutput(target=today), FREE).returns
    assert abs(ann_sharpe(r)) < 1.0


def test_an_oracle_on_the_next_bar_does_earn():
    """Control: the engine does trade. Knowing tomorrow's open-to-close is worth a lot."""
    b = daily_bars()
    tomorrow = np.sign(b["close"].shift(-1) / b["open"].shift(-1) - 1).fillna(0.0)
    r = simulate(b, StrategyOutput(target=tomorrow), FREE).returns
    # Held across the next overnight gap too, which the oracle does not know: still large.
    assert ann_sharpe(r) > 3


def test_delaying_the_oracle_destroys_it():
    b = daily_bars()
    tomorrow = np.sign(b["close"].shift(-1) / b["open"].shift(-1) - 1).fillna(0.0)
    r = simulate(b, StrategyOutput(target=tomorrow), FREE, entry_delay=1, exit_delay=1).returns
    assert abs(ann_sharpe(r)) < 1.5


def _after_warmup(b, n=16):
    t = pd.Series(1.0, index=b.index)
    t.iloc[:n] = 0.0
    return t


def _flat_bars(rows):
    idx = pd.date_range("2020-01-01", periods=len(rows), freq="B", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1.0)


def test_stop_and_target_in_same_bar_assumes_stop_first():
    b = _flat_bars([[100, 100, 100, 100]] * 20 + [[100, 100, 100, 100], [100, 120, 80, 100]])
    b.iloc[:20, 1] = 101
    b.iloc[:20, 2] = 99
    out = StrategyOutput(target=_after_warmup(b), stop_atr=1.0, target_atr=1.0)
    res = simulate(b, out, FREE)
    last = res.trades.iloc[-1]
    assert last["reason"] == "stop"


def test_gap_through_stop_fills_at_the_open_not_the_stop():
    rows = [[100, 101, 99, 100]] * 20 + [[100, 101, 99, 100], [90, 91, 89, 90]]
    b = _flat_bars(rows)
    res = simulate(b, StrategyOutput(target=_after_warmup(b), stop_atr=1.0), FREE)
    stop = res.trades[res.trades["reason"] == "stop"].iloc[0]
    assert stop["exit_px"] == pytest.approx(90.0)


def test_both_stop_entries_touched_takes_the_losing_side():
    rows = [[100, 101, 99, 100]] * 5 + [[100, 106, 94, 105]]  # both levels hit, closes high
    b = _flat_bars(rows)
    lvl_hi = pd.Series(103.0, index=b.index)
    lvl_lo = pd.Series(97.0, index=b.index)
    res = simulate(b, StrategyOutput(long_entry_level=lvl_hi, short_entry_level=lvl_lo,
                                     exit_same_bar_close=True), FREE)
    t = res.trades.iloc[-1]
    assert t["side"] == -1  # the short loses (97 → 105); the long would have won
    assert t["net"] < 0


def test_costs_are_charged_on_entry_and_exit():
    b = _flat_bars([[100, 100, 100, 100]] * 10)
    tgt = pd.Series([0, 1, 1, 0, 0, 0, 0, 0, 0, 0], index=b.index, dtype=float)
    res = simulate(b, StrategyOutput(target=tgt), CostProfile(1.0, 1.0, 1.0))
    assert res.trades.iloc[0]["cost"] == pytest.approx(2 * 3e-4)
    assert res.returns.sum() == pytest.approx(-6e-4)


def test_carry_is_charged_every_bar_held():
    b = _flat_bars([[100, 100, 100, 100]] * 30)
    tgt = pd.Series(1.0, index=b.index)
    res = simulate(b, StrategyOutput(target=tgt), CostProfile(0, 0, 0, holding_long_annual=0.252),
                   periods_per_year=252)
    assert res.returns.iloc[5] == pytest.approx(-0.001)


def test_no_reentry_on_the_same_signal_after_a_stop():
    rows = [[100, 101, 99, 100]] * 20 + [[100, 100, 90, 92]] + [[92, 93, 91, 92]] * 5
    b = _flat_bars(rows)
    res = simulate(b, StrategyOutput(target=_after_warmup(b), stop_atr=1.0), FREE)
    assert (res.trades["reason"] == "stop").sum() == 1
    assert len(res.trades) == 1


def test_weights_simulator_executes_next_open():
    b = daily_bars(300)
    oracle = np.sign(b["close"].shift(-1) / b["open"].shift(-1) - 1).fillna(0.0)
    w = pd.DataFrame({"X": oracle})
    r = simulate_weights({"X": b}, w, FREE).returns
    assert ann_sharpe(r) > 2
    same_bar = pd.DataFrame({"X": np.sign(b["close"] / b["open"] - 1)})
    r2 = simulate_weights({"X": b}, same_bar, FREE).returns
    assert abs(ann_sharpe(r2)) < 1.5


@pytest.mark.parametrize("h", [h for h in active() if h.kind == "trade"], ids=lambda h: h.name)
def test_every_strategy_is_causal(h):
    """Recomputing on a truncated history must reproduce the past exactly."""
    b = daily_bars(700, seed=3)
    full = h.func(b, **h.baseline)
    cut = h.func(b.iloc[:500], **h.baseline)
    for attr in ("target", "long_entry_offset", "short_entry_offset", "long_entry_level", "short_entry_level"):
        a, c = getattr(full, attr), getattr(cut, attr)
        if a is None:
            continue
        pd.testing.assert_series_equal(a.iloc[:500], c, check_names=False)


def test_pair_weights_are_causal():
    a, b = daily_bars(600, 4), daily_bars(600, 5)
    full = S.pair_weights(a, b, window=60)
    cut = S.pair_weights(a.iloc[:400], b.iloc[:400], window=60)
    pd.testing.assert_frame_equal(full.iloc[:400], cut)


def test_hypotheses_are_declared_completely():
    for h in HYPOTHESES:
        assert h.claim, h.name
        if h.kind == "deferred":
            assert h.deferred_reason
            continue
        assert all([h.signal, h.condition, h.horizon, h.target, h.risk, h.falsification]), h.name
        assert 1 <= len(h.configs()) <= 9, (h.name, len(h.configs()))
        assert h.configs()[0] == h.baseline


def test_no_entry_before_the_protective_stop_can_be_computed():
    b = _flat_bars([[100, 101, 99, 100]] * 30)
    res = simulate(b, StrategyOutput(target=pd.Series(1.0, index=b.index), stop_atr=2.0), FREE)
    assert res.position.iloc[:14].abs().sum() == 0
    assert res.position.iloc[-1] > 0
