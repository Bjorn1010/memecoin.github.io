"""Component tests: data lake, bars, labels, costs, risk and the broker."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas


# ------------------------------------------------------------------ data lake
def test_catalog_roundtrip_and_time_bounds(tmp_catalog, bars):
    k = bars[["ts", "open", "high", "low", "close", "volume", "quote_volume", "trades"]].copy()
    k["taker_buy_base"] = bars["buy_volume"]
    k["taker_buy_quote"] = bars["buy_volume"] * bars["close"]

    tmp_catalog.write("klines_1h", "test", "SYM", k)
    full = tmp_catalog.read("klines_1h", "test", "SYM")
    assert len(full) == len(k)

    mid = pd.Timestamp(int(k["ts"].iloc[len(k) // 2]), unit="ms", tz="UTC")
    sliced = tmp_catalog.read("klines_1h", "test", "SYM", start=mid)
    assert len(sliced) < len(full)
    assert sliced["ts"].min() >= int(mid.value // 10**6)


def test_writes_are_idempotent(tmp_catalog, small_bars):
    k = small_bars[["ts", "open", "high", "low", "close", "volume"]]
    tmp_catalog.write("klines_1h", "test", "SYM", k)
    tmp_catalog.write("klines_1h", "test", "SYM", k)
    assert len(tmp_catalog.read("klines_1h", "test", "SYM")) == len(k)


def test_trades_keep_duplicate_timestamps(trades):
    """Bar datasets dedupe on ts; trades must not — the tape shares timestamps."""
    dup = pd.concat([trades.head(10), trades.head(10)])
    out = schemas.normalise(dup, schemas.TRADES)
    assert len(out) == 20
    klines = schemas.normalise(
        pd.DataFrame({"ts": [1, 1, 2], "close": [1.0, 2.0, 3.0]}), schemas.KLINES
    )
    assert len(klines) == 2
    assert klines["close"].iloc[0] == 2.0  # last print wins


# ----------------------------------------------------------------------- bars
def test_dollar_bars_have_roughly_constant_notional(trades):
    from qt.bars import build_bars

    out = build_bars(trades, kind="dollar", target_bars_per_day=50)
    assert len(out) > 5
    # Every completed bar must have crossed the threshold, so the spread of bar
    # notional should be far tighter than that of time bars.
    cv = out["quote_volume"].std() / out["quote_volume"].mean()
    assert cv < 0.5, f"dollar bars are not equal-notional (cv={cv:.2f})"
    assert (out["high"] >= out["low"]).all()
    assert (out["ts"] > out["start_ts"]).all() or (out["ts"] >= out["start_ts"]).all()


def test_bar_ohlc_is_internally_consistent(trades):
    from qt.bars import build_bars

    out = build_bars(trades, kind="volume", target_bars_per_day=40)
    assert (out["high"] >= out[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (out["low"] <= out[["open", "close"]].min(axis=1) + 1e-9).all()
    assert np.isclose(out["buy_volume"] + out["sell_volume"], out["volume"]).all()


def test_cusum_fires_and_is_monotone_in_threshold(bars):
    from qt.bars import cusum_events

    close = bars["close"]
    many = cusum_events(close, 0.005)
    few = cusum_events(close, 0.05)
    assert len(many) > len(few)
    assert len(few) >= 0
    assert set(few).issubset(set(close.index))


# --------------------------------------------------------------------- labels
def test_triple_barrier_on_a_known_path():
    """A hand-built path: up 5% then down. With a 3% profit barrier it must hit profit."""
    from qt.labels.triple_barrier import triple_barrier_labels

    idx = pd.date_range("2024-01-01", periods=20, freq="1h", tz="UTC")
    path = np.concatenate([np.linspace(100, 105, 10), np.linspace(105, 95, 10)])
    close = pd.Series(path, index=idx)
    target = pd.Series(0.03, index=idx)

    ev = triple_barrier_labels(
        close, pd.DatetimeIndex([idx[0]]), target, pt_sl=(1.0, 1.0), horizon=15
    )
    assert len(ev) == 1
    assert ev["bin"].iloc[0] == 1
    assert ev["ret"].iloc[0] > 0.03
    assert ev["t1"].iloc[0] < idx[15]  # touched early, before the vertical barrier


def test_triple_barrier_stop_loss_side():
    from qt.labels.triple_barrier import triple_barrier_labels

    idx = pd.date_range("2024-01-01", periods=20, freq="1h", tz="UTC")
    close = pd.Series(np.linspace(100, 90, 20), index=idx)
    target = pd.Series(0.02, index=idx)
    ev = triple_barrier_labels(close, pd.DatetimeIndex([idx[0]]), target, pt_sl=(1.0, 1.0), horizon=15)
    assert ev["bin"].iloc[0] == -1
    assert ev["ret"].iloc[0] < 0


def test_short_side_flips_the_label():
    from qt.labels.triple_barrier import triple_barrier_labels

    idx = pd.date_range("2024-01-01", periods=20, freq="1h", tz="UTC")
    close = pd.Series(np.linspace(100, 90, 20), index=idx)
    target = pd.Series(0.02, index=idx)
    side = pd.Series(-1.0, index=idx)
    ev = triple_barrier_labels(close, pd.DatetimeIndex([idx[0]]), target, pt_sl=(1.0, 1.0),
                               horizon=15, side=side)
    # A falling market is a win for a short: meta-label 1.
    assert ev["bin"].iloc[0] == 1
    assert ev["ret"].iloc[0] > 0


def test_uniqueness_is_one_when_labels_do_not_overlap():
    from qt.labels.weights import average_uniqueness

    idx = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    starts = idx[::10]
    t1 = pd.Series([idx[i + 9] for i in range(0, 90, 10)], index=starts[:9])
    uniq = average_uniqueness(idx, t1)
    assert np.allclose(uniq.to_numpy(), 1.0, atol=1e-9)


def test_uniqueness_falls_when_labels_overlap():
    from qt.labels.weights import average_uniqueness

    idx = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    starts = idx[:50]
    t1 = pd.Series([idx[i + 40] for i in range(50)], index=starts)
    uniq = average_uniqueness(idx, t1)
    assert uniq.mean() < 0.5, "heavily overlapping labels should be down-weighted"


# ---------------------------------------------------------------------- costs
def test_costs_always_move_the_fill_against_the_trader():
    from qt.backtest.costs import CostEngine

    engine = CostEngine()
    buy = engine.fill(reference_price=100.0, notional=10_000, side=1, bar_notional=1e6, volatility_bps=100)
    sell = engine.fill(reference_price=100.0, notional=10_000, side=-1, bar_notional=1e6, volatility_bps=100)
    assert buy.price > 100.0
    assert sell.price < 100.0
    assert buy.commission > 0 and buy.total_cost > 0


def test_impact_grows_with_participation_but_sublinearly():
    from qt.backtest.costs import CostEngine

    engine = CostEngine()
    small = engine.fill(reference_price=100, notional=1_000, side=1, bar_notional=1e6, volatility_bps=100)
    big = engine.fill(reference_price=100, notional=4_000, side=1, bar_notional=1e6, volatility_bps=100)
    assert big.impact_cost > small.impact_cost
    # 4x the size at sqrt impact => ~2x the per-unit impact, not 4x.
    ratio = (big.impact_cost / 4_000) / (small.impact_cost / 1_000)
    assert 1.5 < ratio < 2.5


def test_higher_fees_strictly_reduce_equity(bars):
    from qt.backtest import BacktestConfig, run_backtest
    from qt.config import CostModel

    signal = pd.DataFrame({"X": np.sign(np.sin(np.arange(len(bars)) / 20))}, index=bars.index)
    finals = []
    for fee in (0.0, 5.0, 25.0):
        cfg = BacktestConfig(costs=CostModel(taker_fee_bps=fee, half_spread_bps=0.0, impact_coeff=0.0))
        finals.append(run_backtest({"X": bars}, signal, cfg).equity.iloc[-1])
    assert finals[0] > finals[1] > finals[2]


# ----------------------------------------------------------------------- risk
def test_daily_loss_breaker_halts_then_resumes_next_session():
    from qt.config import RiskLimits
    from qt.risk import RiskEngine

    eng = RiskEngine(RiskLimits(max_daily_loss=0.03, max_drawdown=0.5), starting_equity=100.0)
    day1 = pd.Timestamp("2024-01-01 00:00", tz="UTC")
    eng.mark(100.0, day1)
    assert not eng.apply(pd.Series({"X": 0.2}), timestamp=day1, equity=100.0).halted

    decision = eng.apply(pd.Series({"X": 0.2}), timestamp=day1.replace(hour=12), equity=95.0)
    assert decision.halted
    assert (decision.weights == 0).all()

    # New session: the daily halt lifts by itself.
    day2 = pd.Timestamp("2024-01-02 00:00", tz="UTC")
    resumed = eng.apply(pd.Series({"X": 0.2}), timestamp=day2, equity=95.0)
    assert not resumed.halted


def test_drawdown_breaker_requires_manual_reset():
    from qt.config import RiskLimits
    from qt.risk import RiskEngine

    eng = RiskEngine(RiskLimits(max_drawdown=0.2, max_daily_loss=0.9), starting_equity=100.0)
    eng.mark(100.0, pd.Timestamp("2024-01-01", tz="UTC"))
    eng.apply(pd.Series({"X": 0.1}), timestamp=pd.Timestamp("2024-01-05", tz="UTC"), equity=75.0)
    assert eng.state.halted

    # A later session does NOT clear it.
    later = eng.apply(pd.Series({"X": 0.1}), timestamp=pd.Timestamp("2024-02-01", tz="UTC"), equity=75.0)
    assert later.halted
    eng.reset()
    assert not eng.apply(
        pd.Series({"X": 0.1}), timestamp=pd.Timestamp("2024-02-02", tz="UTC"), equity=75.0
    ).halted


def test_limits_can_only_reduce_exposure():
    from qt.config import RiskLimits
    from qt.risk import RiskEngine

    eng = RiskEngine(RiskLimits(max_gross_leverage=1.0, max_position_weight=0.3), starting_equity=100.0)
    eng.mark(100.0, pd.Timestamp("2024-01-01", tz="UTC"))
    asked = pd.Series({"A": 0.9, "B": -0.9, "C": 0.9})
    got = eng.apply(asked, timestamp=pd.Timestamp("2024-01-01", tz="UTC"), equity=100.0).weights
    assert (got.abs() <= 0.3 + 1e-9).all()
    assert got.abs().sum() <= 1.0 + 1e-9
    assert (got.abs() <= asked.abs() + 1e-9).all()


def test_vol_targeting_scales_inversely_with_volatility():
    from qt.risk import volatility_target_weight

    signal = pd.Series([1.0, 1.0])
    low_vol = pd.Series([0.002, 0.002])
    high_vol = pd.Series([0.02, 0.02])
    w_low = volatility_target_weight(signal, low_vol, target_annual_vol=0.2, max_leverage=100)
    w_high = volatility_target_weight(signal, high_vol, target_annual_vol=0.2, max_leverage=100)
    assert w_low.iloc[0] > w_high.iloc[0]
    assert np.isclose(w_low.iloc[0] / w_high.iloc[0], 10.0, rtol=0.01)


# --------------------------------------------------------------------- broker
def test_broker_average_cost_accounting():
    from qt.live.state import Position

    pos = Position("X")
    pos.apply_fill(10, 100.0)
    pos.apply_fill(10, 120.0)
    assert np.isclose(pos.avg_price, 110.0)
    realised = pos.apply_fill(-10, 130.0)
    assert np.isclose(realised, 10 * (130.0 - 110.0))
    assert np.isclose(pos.qty, 10.0)


def test_broker_equity_conserved_when_costs_are_zero():
    from qt.config import CostModel
    from qt.live.broker import PaperBroker

    free = CostModel(taker_fee_bps=0, maker_fee_bps=0, half_spread_bps=0, impact_coeff=0)
    broker = PaperBroker("t", 100_000.0, free)
    broker.rebalance({"X": 0.5}, {"X": 100.0}, ts=0)
    # Trading at a price with no costs cannot change equity.
    assert np.isclose(broker.mark_to_market({"X": 100.0}), 100_000.0)
    # And a price move flows straight through to equity at the held weight.
    assert np.isclose(broker.mark_to_market({"X": 110.0}), 105_000.0, rtol=1e-6)


def test_broker_costs_reduce_equity():
    from qt.live.broker import PaperBroker

    broker = PaperBroker("t", 100_000.0)
    broker.rebalance({"X": 0.5}, {"X": 100.0}, ts=0)
    assert broker.mark_to_market({"X": 100.0}) < 100_000.0
    assert broker.total_costs > 0


def test_flatten_closes_everything():
    from qt.live.broker import PaperBroker

    broker = PaperBroker("t", 100_000.0)
    broker.rebalance({"X": 0.5}, {"X": 100.0}, ts=0)
    assert broker.state.position("X").qty != 0
    broker.flatten({"X": 100.0}, ts=1)
    assert broker.state.position("X").qty == 0.0


# ----------------------------------------------------------------- statistics
def test_deflated_sharpe_punishes_many_trials():
    from qt.validation import deflated_sharpe_ratio

    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.0005, 0.01, 2000))
    one = deflated_sharpe_ratio(returns, n_trials=1, sr_variance=0.5)
    many = deflated_sharpe_ratio(returns, n_trials=500, sr_variance=0.5)
    assert many["benchmark_sharpe"] > one["benchmark_sharpe"]
    assert many["deflated_sharpe"] <= one["deflated_sharpe"]


def test_pbo_flags_an_edge_that_exists_only_in_the_first_half():
    """The textbook overfit: a configuration that worked, then stopped.

    This is what PBO is for. A selection procedure that picks the first-half winner is
    picking something that reverses out of sample, and PBO should be high.
    """
    from qt.validation import probability_of_backtest_overfitting

    rng = np.random.default_rng(3)
    n = 600
    perf = pd.DataFrame(rng.normal(0, 0.01, (n, 8)))
    half = n // 2
    perf.iloc[:half, 0] += 0.006   # looks brilliant early
    perf.iloc[half:, 0] -= 0.006   # and gives it all back
    out = probability_of_backtest_overfitting(perf, n_splits=8)
    assert out["pbo"] > 0.5, f"PBO failed to flag a regime-reversing config: {out['pbo']}"


def test_pbo_is_low_when_one_configuration_genuinely_wins():
    from qt.validation import probability_of_backtest_overfitting

    rng = np.random.default_rng(2)
    perf = pd.DataFrame(rng.normal(0, 0.01, (600, 8)))
    perf = perf - perf.mean()
    perf[0] = perf[0] + 0.004  # a real, persistent edge
    out = probability_of_backtest_overfitting(perf, n_splits=8)
    assert out["pbo"] < 0.2


def test_frac_diff_is_causal_and_reduces_nonstationarity():
    from qt.features.statistical import frac_diff

    rng = np.random.default_rng(2)
    walk = pd.Series(np.cumsum(rng.standard_normal(3000)) + 100)
    fd = frac_diff(walk, d=0.4)

    # Causal: the value at i does not change when later data is removed.
    partial = frac_diff(walk.iloc[:2000], d=0.4)
    shared = partial.dropna().index
    assert np.allclose(fd.loc[shared], partial.loc[shared], equal_nan=True)

    # And it is much less persistent than the raw level.
    assert fd.dropna().autocorr(1) < walk.autocorr(1)


# --------------------------------------------------- timestamp resolution guard
@pytest.mark.parametrize("rule", ["4h", "1D"])
def test_resampling_preserves_epoch_milliseconds(bars, rule):
    """Regression: pandas keeps a DatetimeIndex's own unit, so `astype("int64")` is
    NOT nanoseconds for a ms- or us-backed index. Dividing by 1e6 there silently
    produced timestamps ~10^6 times too small, which surfaced as absurd Sharpe
    ratios rather than as an error. See qt.data.schemas.epoch_ms.
    """
    from qt.bars import bars_from_klines

    out = bars_from_klines(bars, rule)
    assert not out.empty
    # A plausible epoch-ms value for a date in this century.
    assert out["ts"].min() > 1_500_000_000_000
    assert out["ts"].max() < 3_000_000_000_000
    expected_step = int(pd.Timedelta(rule).total_seconds() * 1000)
    assert int(out["ts"].diff().median()) == expected_step
    assert (out["ts"] - out["start_ts"] == expected_step).all()


def test_resampling_preserves_signed_flow(bars):
    """Downsampled bars must keep buy/sell volume, or every flow feature goes NaN."""
    from qt.bars import bars_from_klines

    out = bars_from_klines(bars, "4h")
    assert out["buy_volume"].notna().any()
    assert np.isclose(out["buy_volume"] + out["sell_volume"], out["volume"]).all()


def test_epoch_ms_is_resolution_independent():
    from qt.data.schemas import epoch_ms

    target = 1_609_545_600_000
    from_ms = pd.to_datetime(pd.Series([target]), unit="ms", utc=True)
    from_str = pd.to_datetime(pd.Series(["2021-01-02 00:00:00"]), utc=True)
    assert int(epoch_ms(from_ms).iloc[0]) == target
    assert int(epoch_ms(from_str).iloc[0]) == target
    # A tz-naive index is assumed UTC rather than silently shifted.
    assert int(epoch_ms(pd.DatetimeIndex(["2021-01-02"])).iloc[0]) == target
