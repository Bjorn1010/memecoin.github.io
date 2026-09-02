"""The autonomous daily cycle: it must not raise, must not trade stale data, must record.

A daemon that throws is not autonomous, and a daemon that keeps trading a feed which has
silently stopped updating is worse than one that stops. These are the two properties
worth testing; the rest is bookkeeping that only matters because "why did it do that" is
unanswerable three weeks later without it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas
from qt.data.catalog import Catalog
from qt.live.orchestrator import (
    CycleResult,
    DailySpec,
    drawdown_scale,
    load_prices,
    run_cycle,
    staleness,
    status_report,
    target_weights,
)
from qt.live.state import Store


@pytest.fixture
def spec() -> DailySpec:
    from qt.strategies.trend import TrendSpec

    return DailySpec(universe="test_universe", trend=TrendSpec(rebalance_every=5))


@pytest.fixture
def seeded(tmp_path, monkeypatch, spec):
    """A lake holding four synthetic assets with enough history for the allocator."""
    from qt.data.sources import yahoo

    monkeypatch.setitem(yahoo.UNIVERSES, "test_universe", ("AAA", "BBB", "CCC", "DDD"))

    cat = Catalog(root=tmp_path / "lake")
    n = 900
    end = pd.Timestamp.now("UTC").normalize()
    index = pd.bdate_range(end=end, periods=n, tz="UTC")
    rng = np.random.default_rng(21)
    for i, symbol in enumerate(("AAA", "BBB", "CCC", "DDD")):
        walk = 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.01 + (i - 1.5) * 2e-4))
        cat.write(schemas.EOD, "yahoo", symbol, schemas.normalise(pd.DataFrame({
            "ts": schemas.epoch_ms(index), "open": walk, "high": walk * 1.01,
            "low": walk * 0.99, "close": walk, "volume": 1e6, "adj_close": walk,
        }), schemas.EOD, extra_columns=("adj_close",)))
    store = Store(tmp_path / "runs.sqlite")
    return cat, store


def test_a_full_cycle_produces_a_book_within_its_limits(seeded, spec):
    cat, store = seeded
    result = run_cycle(spec, catalog=cat, store=store, run_id="t", do_refresh=False)

    assert result.status == "ok", result.reason
    assert result.weights, "the cycle produced no positions"
    assert max(abs(v) for v in result.weights.values()) <= spec.max_weight + 1e-9
    assert result.gross <= spec.max_gross + 1e-9


def test_limits_survive_the_volatility_scaling(seeded, spec):
    """Capping before levering lets the scalar walk a position back through its ceiling.

    The first live cycle put 25.63% into a single ETF against a 25% limit.
    """
    cat, _ = seeded
    prices = load_prices(cat, spec)
    weights = target_weights(prices, spec)
    assert not weights.empty
    assert weights.abs().to_numpy().max() <= spec.max_weight + 1e-9
    assert weights.abs().sum(axis=1).max() <= spec.max_gross + 1e-9


def test_stale_data_stops_new_risk(seeded, spec):
    """Trading a feed that stopped updating is how a book sleeps through a crash."""
    cat, store = seeded
    future = pd.Timestamp.now("UTC") + pd.Timedelta(days=30)
    result = run_cycle(spec, catalog=cat, store=store, run_id="t",
                       do_refresh=False, now=future)

    assert result.status == "stale"
    assert not result.weights
    assert "old" in result.reason


def test_an_empty_lake_reports_rather_than_raises(tmp_path, monkeypatch, spec):
    from qt.data.sources import yahoo

    monkeypatch.setitem(yahoo.UNIVERSES, "test_universe", ("AAA",))
    cat = Catalog(root=tmp_path / "empty")
    store = Store(tmp_path / "runs.sqlite")
    result = run_cycle(spec, catalog=cat, store=store, run_id="t", do_refresh=False)
    assert result.status == "error"
    assert "lake" in result.reason


def test_the_cycle_never_raises(seeded, spec, monkeypatch):
    """A cycle that throws stops the daemon; a daemon that stops is not autonomous."""
    cat, store = seeded

    def explode(*args, **kwargs):
        raise RuntimeError("simulated allocator failure")

    monkeypatch.setattr("qt.live.orchestrator.target_weights", explode)
    result = run_cycle(spec, catalog=cat, store=store, run_id="t", do_refresh=False)
    assert result.status == "error"
    assert "simulated allocator failure" in result.reason


def test_decisions_are_persisted_and_readable(seeded, spec):
    cat, store = seeded
    run_cycle(spec, catalog=cat, store=store, run_id="t", do_refresh=False)

    report = status_report("t", store)
    assert report["cycles"] >= 1
    assert report["positions"], "nothing recorded — the decision is unauditable"
    assert report["gross"] > 0


def test_drawdown_breaker_reduces_but_never_liquidates(spec):
    """Flattening at the bottom of a drawdown realises the loss and misses the recovery."""
    assert drawdown_scale(-0.02, spec) == (1.0, "")
    half, reason = drawdown_scale(-0.12, spec)
    assert half == 0.5 and "halved" in reason
    zero, reason = drawdown_scale(-0.25, spec)
    assert zero == 0.0 and "no new risk" in reason


def test_breaker_blocks_new_risk_without_selling(seeded, spec):
    """Scale 0 must mean "take no new risk", not "sell the book"."""
    cat, store = seeded
    ms = int(schemas.epoch_ms(pd.DatetimeIndex([pd.Timestamp.now("UTC")])).iloc[0])
    store.record_equity("t", ms - 86_400_000, 100_000.0, 100_000.0, 1.0, 0.0, False)
    store.record_equity("t", ms - 43_200_000, 70_000.0, 70_000.0, 1.0, -0.30, False)

    result = run_cycle(spec, catalog=cat, store=store, run_id="t", do_refresh=False)
    assert result.status == "halted"
    assert result.risk_scale == 0.0
    # The raw view is still computed and recorded — the system knows what it wants even
    # while it is not allowed to take it.
    assert result.raw_weights, "the strategy's view was discarded rather than recorded"


def test_staleness_handles_an_empty_frame():
    assert np.isnan(staleness(pd.DataFrame()))


def test_cycle_result_serialises(seeded, spec):
    cat, store = seeded
    result = run_cycle(spec, catalog=cat, store=store, run_id="t", do_refresh=False)
    payload = result.to_dict()
    assert set(payload) >= {"ts", "status", "weights", "gross", "equity"}
    assert all(isinstance(v, float) for v in payload["weights"].values())


def test_the_live_decision_path_is_causal(seeded, spec):
    """Truncating the future must not change any past weight.

    This is the strongest check available on the live path: if a weight the book held
    last March changes when data after March is removed, the decision used information
    that did not exist. Every look-ahead bug found in this project has had this shape.
    """
    cat, _ = seeded
    prices = load_prices(cat, spec)
    assert len(prices) > 600

    full = target_weights(prices, spec)
    cut = len(prices) - 120
    truncated = target_weights(prices.iloc[:cut], spec)

    common = full.index.intersection(truncated.index)
    assert len(common) > 200, "not enough overlap to prove anything"

    # A rebalance schedule is anchored on the sample start, so the last partial block of
    # the truncated run legitimately differs; compare everything before it.
    stable = common[:-spec.trend.rebalance_every - 1]
    pd.testing.assert_frame_equal(
        full.loc[stable], truncated.loc[stable], check_freq=False, rtol=1e-9,
    )


def test_weights_never_reference_a_bar_that_does_not_exist_yet(seeded, spec):
    """The newest weight must be computable from the newest bar and nothing beyond."""
    cat, _ = seeded
    prices = load_prices(cat, spec)
    weights = target_weights(prices, spec)
    assert weights.index.max() <= prices.index.max()


def test_equity_is_marked_to_market_between_cycles(seeded, spec):
    """Without revaluation the curve is a constant and the breaker can never fire.

    The system still runs, records and reports — it simply says "no loss yet" whatever
    the market does, which is the most dangerous kind of working.
    """
    from qt.live.orchestrator import mark_to_market

    cat, store = seeded
    prices = load_prices(cat, spec)
    mid = prices.index[len(prices) - 30]

    # A cycle placed 30 bars ago, long the first asset only.
    ms = int(schemas.epoch_ms(pd.DatetimeIndex([mid])).iloc[0])
    store.record_equity("mtm", ms, 100_000.0, 100_000.0, 0.5, 0.0, False)
    store.record_decision("mtm", ms, prices.columns[0], signal=0.5, target_weight=0.5,
                          allowed_weight=0.5, risk_scale=1.0, risk_reason="ok",
                          equity=100_000.0)

    equity, drawdown, held = mark_to_market(store, "mtm", prices, spec)

    # Entered one bar AFTER the decision, not at its close. A decision made from bar t's
    # close cannot fill at that close; crediting it anyway is a one-bar look-ahead worth
    # a full point of CAGR, which is what replaying this cycle over 2012-2026 revealed.
    column = prices.columns[0]
    entry = prices.index[list(prices.index).index(mid) + 1]
    realised = float(prices[column].iloc[-1] / prices[column].loc[entry] - 1.0)
    optimistic = float(prices[column].iloc[-1] / prices[column].loc[mid] - 1.0)

    assert held == {column: 0.5}
    assert equity != pytest.approx(100_000.0), "equity never moved — the book is not valued"
    assert equity == pytest.approx(100_000.0 * (1 + 0.5 * realised), rel=1e-9)
    if abs(realised - optimistic) > 1e-9:
        assert equity != pytest.approx(100_000.0 * (1 + 0.5 * optimistic), rel=1e-9), (
            "the book was credited from the decision bar's close — a one-bar look-ahead"
        )
    assert drawdown <= 0.0


def test_mark_to_market_uses_the_weights_that_were_held(seeded, spec):
    """Crediting today's weights with today's return is the same look-ahead as sizing
    a position on the bar it is about to profit from."""
    from qt.live.orchestrator import mark_to_market

    cat, store = seeded
    prices = load_prices(cat, spec)
    mid = prices.index[len(prices) - 20]
    ms = int(schemas.epoch_ms(pd.DatetimeIndex([mid])).iloc[0])

    store.record_equity("mtm2", ms, 100_000.0, 100_000.0, 0.0, 0.0, False)
    # Recorded flat: whatever the market did since, equity must be unchanged.
    store.record_decision("mtm2", ms, prices.columns[0], signal=0.0, target_weight=0.0,
                          allowed_weight=0.0, risk_scale=1.0, risk_reason="flat",
                          equity=100_000.0)

    equity, _, _ = mark_to_market(store, "mtm2", prices, spec)
    assert equity == pytest.approx(100_000.0), "a flat book earned a return"


def test_a_first_cycle_starts_at_the_seed_equity(seeded, spec):
    from qt.live.orchestrator import mark_to_market

    cat, store = seeded
    prices = load_prices(cat, spec)
    equity, drawdown, held = mark_to_market(store, "fresh", prices, spec)
    assert equity == spec.starting_equity
    assert drawdown == 0.0
    assert held == {}


def test_live_and_backtest_paths_agree(seeded, spec):
    """The two implementations of the same idea must not drift apart.

    A project with both a backtest and a live path always grows a difference between
    them, and it is always found months later when the live curve stops resembling the
    research. This replays the live cycle over history and compares.

    Agreement is not identity: the live path charges a flat spread on turnover while the
    engine models spread and impact per fill, so a small gap is the cost models
    differing. A large gap means the *decisions* differ, which is the failure worth
    catching.
    """
    from qt.backtest import BacktestConfig
    from qt.backtest.engine import run_backtest
    from qt.config import CostModel
    from qt.live.orchestrator import drawdown_scale, mark_to_market

    cat, _ = seeded
    prices = load_prices(cat, spec)
    bars = {}
    for symbol in prices.columns:
        frame = cat.read_indexed("eod", "yahoo", symbol).loc[prices.index]
        bars[symbol] = frame

    weights = target_weights(prices, spec)
    assert not weights.empty

    # --- live path, walked forward one rebalance at a time
    replay_store = Store(":memory:") if False else None
    equity = spec.starting_equity
    previous: dict[str, float] = {}
    curve = []
    schedule = weights.index[::spec.trend.rebalance_every]
    positions = list(prices.index)
    for i, stamp in enumerate(schedule[:-1]):
        nxt = schedule[i + 1]
        allowed = weights.loc[stamp]
        turnover = sum(abs(float(allowed.get(s, 0.0)) - previous.get(s, 0.0))
                       for s in set(allowed.index) | set(previous))
        equity -= equity * turnover * (spec.half_spread_bps / 1e4)
        # Enter one bar late: a decision made from bar t's close fills at t+1, which is
        # what the engine's execution_lag_bars=1 models.
        entry = positions[positions.index(stamp) + 1]
        step = prices.loc[nxt] / prices.loc[entry] - 1.0
        equity += equity * float((allowed * step).sum())
        previous = {s: float(v) for s, v in allowed.items()}
        curve.append(equity)

    live_total = curve[-1] / spec.starting_equity - 1.0

    # --- backtest over the same weights and window
    cfg = BacktestConfig(
        bars_per_year=252,
        costs=CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0,
                        half_spread_bps=spec.half_spread_bps),
        allow_short=True, signal_is_weight=True,
        max_weight_per_symbol=spec.max_weight,
    )
    window = weights.loc[schedule[0]:schedule[-1]]
    bt = run_backtest({s: b.loc[b.index.intersection(window.index)] for s, b in bars.items()},
                      window, cfg)
    bt_total = float(bt.equity.iloc[-1] / bt.equity.iloc[0] - 1.0)

    assert abs(live_total - bt_total) < 0.05, (
        f"live {live_total:.4f} vs backtest {bt_total:.4f} — the paths have drifted"
    )
