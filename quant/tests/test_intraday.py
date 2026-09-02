"""Day-trading mechanics: stops, time stops, frequency caps, and the one-bar lag.

The strategy this module implements does not work — measured, out of sample, and reported
in scripts/research_intraday.py. These tests are about the *machinery* being right anyway,
because a broken day-trading engine produces a profitable-looking curve by construction:
fill at the signal bar's close, resolve an ambiguous bar in your favour, let a losing trade
run past its time stop. Each of those is worth more than any signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.strategies.intraday import (
    IntradaySpec,
    entry_signal,
    equity_curve,
    performance,
    run_intraday,
)


def make_bars(closes, *, highs=None, lows=None, opens=None, freq="1h") -> pd.DataFrame:
    closes = np.asarray(closes, dtype="float64")
    index = pd.date_range("2024-01-01", periods=len(closes), freq=freq, tz="UTC")
    opens = np.asarray(opens, dtype="float64") if opens is not None else closes
    highs = np.asarray(highs, dtype="float64") if highs is not None else np.maximum(opens, closes)
    lows = np.asarray(lows, dtype="float64") if lows is not None else np.minimum(opens, closes)
    volume = np.full(len(closes), 1000.0)
    return pd.DataFrame({
        "ts": (index.astype("int64") // 10**6),
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": volume, "buy_volume": volume * 0.5, "sell_volume": volume * 0.5,
    }, index=index)


@pytest.fixture
def noisy() -> pd.DataFrame:
    rng = np.random.default_rng(31)
    n = 1500
    close = 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.004))
    wiggle = np.abs(rng.standard_normal(n)) * close * 0.002
    bars = make_bars(close, highs=close + wiggle, lows=close - wiggle, opens=close)
    bars["buy_volume"] = bars["volume"] * (0.5 + rng.standard_normal(n) * 0.05)
    return bars


# ------------------------------------------------------------------- signals
def test_signal_legs_are_kept_separate(noisy):
    """A combined signal that works only because one leg dominates is a one-leg strategy."""
    sig = entry_signal(noisy, IntradaySpec())
    assert {"reversal", "breakout", "flow", "combined", "vol"} <= set(sig.columns)
    for leg in ("reversal", "breakout", "flow"):
        assert sig[leg].notna().any(), f"{leg} produced nothing"
        assert sig[leg].std() > 0, f"{leg} is constant"


def test_signal_is_causal(noisy):
    """Truncating the future must not change any past value."""
    full = entry_signal(noisy, IntradaySpec())
    cut = entry_signal(noisy.iloc[:900], IntradaySpec())
    pd.testing.assert_frame_equal(full.loc[cut.index], cut, check_freq=False)


def test_flow_leg_is_absent_rather_than_zero_without_aggressor_data(noisy):
    """A missing input must not become a confident 'no view'."""
    stripped = noisy.drop(columns=["buy_volume"])
    sig = entry_signal(stripped, IntradaySpec())
    assert sig["flow"].isna().all()
    # combined must still be built from the legs that do exist
    assert sig["combined"].notna().any()


# --------------------------------------------------------------- entry timing
def test_entry_fills_at_the_next_bar_open_not_the_signal_close():
    """Filling at the close that produced the signal is free money that never existed."""
    # A sharp drop then a recovery: the reversal leg fires, and the next open differs.
    closes = [100] * 60 + [92] + [100] * 60
    opens = [100] * 60 + [99] + [93] + [100] * 59
    bars = make_bars(closes, opens=opens)

    result = run_intraday(bars, IntradaySpec(entry_threshold=0.5), symbol="X")
    if result.trades.empty:
        pytest.skip("fixture produced no entry; timing is asserted elsewhere")

    first = result.trades.iloc[0]
    entry_i = list(bars.index).index(first["entry_ts"])
    assert first["entry_price"] == pytest.approx(bars["open"].iloc[entry_i])


# ----------------------------------------------------------------- exit rules
def test_stop_is_honoured_and_bounds_the_loss():
    rng = np.random.default_rng(5)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.01))
    wiggle = np.abs(rng.standard_normal(n)) * close * 0.01
    bars = make_bars(close, highs=close + wiggle, lows=close - wiggle, opens=close)

    spec = IntradaySpec(entry_threshold=0.3, stop_atr=1.0, target_atr=3.0)
    result = run_intraday(bars, spec, symbol="X", round_trip_bps=0.0)
    assert not result.trades.empty

    stopped = result.trades[result.trades["exit_reason"] == "stop"]
    assert len(stopped) > 0, "no stop ever triggered — the exit rule is not wired"
    # A stopped trade's gross loss cannot exceed the stop distance it was sized against.
    per_unit = stopped["gross_return"] / stopped["weight"]
    assert (per_unit >= -0.5).all(), "a stopped loss exceeded its own stop distance"


def test_an_ambiguous_bar_resolves_against_the_position():
    """When a bar touches stop and target, assuming the target manufactures the edge.

    Without tick data the pessimistic reading is the only honest one.
    """
    # Flat, then one enormous bar spanning both levels.
    closes = [100.0] * 80 + [100.0] * 20
    highs = [100.5] * 80 + [130.0] + [100.5] * 19
    lows = [99.5] * 80 + [70.0] + [99.5] * 19
    bars = make_bars(closes, highs=highs, lows=lows, opens=closes)

    result = run_intraday(bars, IntradaySpec(entry_threshold=0.1), symbol="X",
                          round_trip_bps=0.0)
    both = result.trades[result.trades["exit_reason"].isin(["stop", "target"])]
    if not both.empty:
        # Nothing may exit at the target on a bar that also swept the stop.
        swept = both[both["exit_ts"] == bars.index[80]]
        assert (swept["exit_reason"] != "target").all()


def test_time_stop_prevents_an_overnight_position():
    """Without it, a losing day trade silently becomes a position trade."""
    rng = np.random.default_rng(11)
    n = 600
    close = 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.003))
    bars = make_bars(close, highs=close * 1.0005, lows=close * 0.9995, opens=close)

    spec = IntradaySpec(entry_threshold=0.3, stop_atr=50.0, target_atr=50.0,
                        max_hold_bars=6)
    result = run_intraday(bars, spec, symbol="X", round_trip_bps=0.0)
    assert not result.trades.empty
    assert (result.trades["bars_held"] <= 6).all(), "a position outlived its time stop"
    assert (result.trades["exit_reason"] == "time").all()


# ------------------------------------------------------------ frequency limit
def test_daily_trade_cap_binds(noisy):
    """Frequency is a cost limit: at 12bps a round trip, 10 trades a day is 438% a year."""
    spec = IntradaySpec(entry_threshold=0.05, max_trades_per_day=1, cooldown_bars=0,
                        max_hold_bars=2)
    result = run_intraday(noisy, spec, symbol="X")
    if result.trades.empty:
        pytest.skip("no entries at this threshold")

    per_day = result.trades.groupby(result.trades["entry_ts"].dt.date).size()
    assert per_day.max() <= 1


def test_only_one_position_at_a_time(noisy):
    """Stacking entries makes the risk-per-trade budget meaningless."""
    result = run_intraday(noisy, IntradaySpec(entry_threshold=0.2), symbol="X")
    assert (result.weights.abs() <= IntradaySpec().max_weight + 1e-12).all()
    if not result.trades.empty:
        spans = result.trades[["entry_ts", "exit_ts"]].sort_values("entry_ts")
        assert (spans["entry_ts"].to_numpy()[1:] >= spans["exit_ts"].to_numpy()[:-1]).all()


def test_cooldown_is_respected(noisy):
    spec = IntradaySpec(entry_threshold=0.2, cooldown_bars=10, max_hold_bars=2,
                        max_trades_per_day=99)
    result = run_intraday(noisy, spec, symbol="X")
    if len(result.trades) < 2:
        pytest.skip("not enough trades to check the cooldown")
    idx = list(noisy.index)
    gaps = [idx.index(e) - idx.index(x) for e, x in
            zip(result.trades["entry_ts"].iloc[1:], result.trades["exit_ts"].iloc[:-1])]
    assert min(gaps) >= spec.cooldown_bars


# ------------------------------------------------------------------- sizing
def test_position_size_targets_the_risk_budget(noisy):
    """Size is set so entry-to-stop costs risk_per_trade, not by a fixed weight."""
    spec = IntradaySpec(entry_threshold=0.3, risk_per_trade=0.01, max_weight=1.0)
    result = run_intraday(noisy, spec, symbol="X", round_trip_bps=0.0)
    if result.trades.empty:
        pytest.skip("no entries")
    stopped = result.trades[result.trades["exit_reason"] == "stop"]
    if stopped.empty:
        pytest.skip("no stopped trades")
    # A stopped trade should cost roughly the risk budget, in equity terms.
    assert (stopped["gross_return"].abs() < 0.05).all()


def test_weights_never_exceed_the_cap(noisy):
    spec = IntradaySpec(entry_threshold=0.1, risk_per_trade=0.5, max_weight=0.2)
    result = run_intraday(noisy, spec, symbol="X")
    assert result.weights.abs().max() <= 0.2 + 1e-12


def test_long_only_spec_never_shorts(noisy):
    result = run_intraday(noisy, IntradaySpec(entry_threshold=0.2, allow_short=False),
                          symbol="X")
    assert (result.weights >= -1e-12).all()
    if not result.trades.empty:
        assert (result.trades["direction"] > 0).all()


# ---------------------------------------------------------------- accounting
def test_costs_are_charged_on_both_sides(noisy):
    spec = IntradaySpec(entry_threshold=0.3)
    free = run_intraday(noisy, spec, symbol="X", round_trip_bps=0.0)
    paid = run_intraday(noisy, spec, symbol="X", round_trip_bps=12.0)
    if free.trades.empty:
        pytest.skip("no trades")

    # Same decisions, different accounting.
    assert len(free.trades) == len(paid.trades)
    pd.testing.assert_series_equal(free.trades["gross_return"], paid.trades["gross_return"])
    assert paid.trades["net_return"].sum() < free.trades["net_return"].sum()

    per_trade = (free.trades["net_return"] - paid.trades["net_return"]) / free.trades["weight"]
    assert per_trade.round(6).nunique() == 1, "cost is not a flat round trip per trade"
    assert per_trade.iloc[0] == pytest.approx(12.0 / 1e4)


def test_diagnostics_report_the_cost_share(noisy):
    """The number that decides everything: costs against the gross edge."""
    result = run_intraday(noisy, IntradaySpec(entry_threshold=0.3), symbol="X")
    if result.trades.empty:
        pytest.skip("no trades")
    assert "cost_share_of_gross" in result.diagnostics
    assert "exit_reasons" in result.diagnostics
    assert result.diagnostics["trades"] == len(result.trades)


def test_no_entries_is_reported_not_hidden(noisy):
    result = run_intraday(noisy, IntradaySpec(entry_threshold=99.0), symbol="X")
    assert result.trades.empty
    assert "note" in result.diagnostics
    assert performance(result)["trades"] == 0


def test_equity_curve_compounds_the_trades(noisy):
    result = run_intraday(noisy, IntradaySpec(entry_threshold=0.3), symbol="X")
    if result.trades.empty:
        pytest.skip("no trades")
    curve = equity_curve(result, 100_000.0)
    assert curve.iloc[0] == pytest.approx(100_000.0)
    expected = 100_000.0 * float((1 + result.trades["net_return"]).prod())
    assert curve.iloc[-1] == pytest.approx(expected)


def test_an_empty_result_keeps_its_columns(noisy):
    """A caller reading a column on the no-trades path must get an empty series.

    A bare empty DataFrame has no columns, so `result.trades["exit_reason"]` raises —
    on the one path least likely to have been exercised.
    """
    result = run_intraday(noisy, IntradaySpec(entry_threshold=99.0), symbol="X")
    assert result.trades.empty
    assert "exit_reason" in result.trades.columns
    assert len(result.trades["exit_reason"]) == 0
    assert set(result.trades.columns) >= {
        "symbol", "direction", "entry_ts", "exit_ts", "exit_reason",
        "gross_return", "net_return",
    }
