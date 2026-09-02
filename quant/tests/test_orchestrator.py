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
