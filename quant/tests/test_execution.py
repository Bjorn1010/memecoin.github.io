"""Order management against a broker that fails the way real brokers fail."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from qt.brokers.models import OrderIntent, OrderStatus, OrderType, make_client_order_id
from qt.brokers.simulated import SimulatedBroker
from qt.oms.kill_switch import GLOBAL, KillSwitch
from qt.oms.order_manager import OrderManager


def setup(**ks):
    b = SimulatedBroker("A1", 100_000)
    b.connect()
    b.set_price("ES", 5000.0)
    k = KillSwitch(**ks)
    return b, k, OrderManager(b, k, "A1")


def intent(qty=1.0, side=1, sig="s1", **kw):
    return OrderIntent("A1", "ES", side, qty, client_order_id=make_client_order_id("A1", "strat", sig, "ES", side), **kw)


def test_market_order_fills_and_books_position():
    b, k, m = setup()
    r = m.submit(intent(), 5000.0)
    assert r.ok and r.order.status == OrderStatus.FILLED
    assert m.expected_positions["ES"] == 1.0
    assert m.reconcile() == []


def test_same_intent_twice_is_one_order():
    b, k, m = setup()
    m.submit(intent(), 5000.0)
    r2 = m.submit(intent(), 5000.0)
    assert r2.ok and "déjà soumis" in r2.reason
    assert b.send_count == 1
    assert m.expected_positions["ES"] == 1.0


def test_lost_response_after_send_does_not_duplicate():
    b, k, m = setup()
    b.inject("disconnect_after_send")
    r = m.submit(intent(), 5000.0)
    assert r.ok
    assert b.send_count == 1  # recovered by asking the broker, not by resending
    assert m.expected_positions["ES"] == 1.0
    assert m.reconcile() == []


def test_disconnect_before_send_is_retried():
    b, k, m = setup()
    b.inject("disconnect_before_send")
    r = m.submit(intent(), 5000.0)
    assert r.ok and r.retries == 1
    assert b.send_count == 1


def test_repeated_api_failure_trips_the_kill_switch():
    b, k, m = setup(max_api_failures=3)
    b.inject("disconnect_before_send", times=10)
    r = m.submit(intent(), 5000.0)
    assert not r.ok
    assert k.is_tripped("A1")
    assert m.submit(intent(sig="s2"), 5000.0).reason.startswith("kill switch")


def test_rejections_are_counted_and_trip_after_a_streak():
    b, k, m = setup(max_consecutive_rejects=2)
    b.inject("reject", times=2)
    assert not m.submit(intent(sig="a"), 5000.0).ok
    assert not k.is_tripped("A1")
    assert not m.submit(intent(sig="b"), 5000.0).ok
    assert k.is_tripped("A1")


def test_partial_fill_is_tracked_and_stale_remainder_cancelled():
    b, k, m = setup()
    b.inject("partial_fill")
    r = m.submit(intent(qty=2.0), 5000.0)
    assert r.order.status == OrderStatus.PARTIALLY_FILLED
    assert m.expected_positions["ES"] == 1.0
    events = m.sync(now=datetime.now(timezone.utc) + timedelta(minutes=10))
    assert any("périmé" in e for e in events)
    assert b.orders[r.order.order_id].status == OrderStatus.CANCELLED
    assert m.reconcile() == []


def test_resting_limit_order_fill_is_picked_up_by_sync():
    b, k, m = setup()
    r = m.submit(intent(order_type=OrderType.LIMIT, limit_price=4990.0), 5000.0)
    assert r.order.status == OrderStatus.ACCEPTED
    b.set_price("ES", 4989.0)
    m.sync()
    assert m.expected_positions["ES"] == 1.0
    assert m.reconcile() == []


def test_aberrant_fill_price_trips_the_switch():
    b, k, m = setup(max_slippage_bps=50)
    b.inject("bad_price")
    m.submit(intent(), 5000.0)
    assert k.is_tripped("A1")
    assert "abnormal_slippage" in k.reason("A1")


def test_invalid_reference_price_is_refused():
    b, k, m = setup()
    assert not m.submit(intent(), float("nan")).ok
    assert "invalid_data" in k.reason("A1")


def test_position_appearing_outside_the_oms_trips_the_switch():
    b, k, m = setup()
    m.submit(intent(), 5000.0)
    b.force_position("ES", 3.0, 5000.0)
    mism = m.reconcile()
    assert mism and mism[0]["broker"] == 3.0
    assert "position_mismatch" in k.reason("A1")


def test_flatten_still_works_when_the_switch_is_tripped():
    b, k, m = setup()
    m.submit(intent(qty=2.0), 5000.0)
    k.trip("manual", "test")
    results = m.flatten("kill switch")
    assert all(r.ok for r in results)
    assert b.get_positions() == []


def test_global_trip_blocks_every_account_and_reset_needs_a_reason():
    b, k, m = setup()
    k.trip("drawdown", "portefeuille", GLOBAL)
    assert m.submit(intent(), 5000.0).reason.startswith("kill switch")
    with pytest.raises(ValueError):
        k.reset(GLOBAL, by="", reason="")
    k.reset(GLOBAL, by="opérateur", reason="cause identifiée")
    assert m.submit(intent(), 5000.0).ok


def test_unknown_order_at_the_broker_is_flagged():
    b, k, m = setup()
    b.place_order(OrderIntent("A1", "ES", 1, 1.0, client_order_id="someone-else"))
    events = m.sync()
    assert any("inconnu" in e for e in events)
    assert k.is_tripped("A1")


def test_abnormal_volatility_trigger():
    k = KillSwitch(max_volatility_multiple=4.0)
    k.check_volatility("A1", bar_range=50.0, median_range=10.0)
    assert "abnormal_volatility" in k.reason("A1")
