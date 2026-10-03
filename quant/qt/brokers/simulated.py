"""Paper broker with fault injection.

Used for paper trading and for testing the execution layer against the failures a
real broker produces: disconnects (before or after the order reached the server),
rejections, partial fills, duplicate acknowledgements, stale quotes, bad prices.

A fault is armed by name and fires on the next matching call, so a test reads like the
incident it reproduces:

    broker.inject("disconnect_after_send")   # order reaches the server, response is lost
    manager.submit(intent)                   # must NOT produce a second order
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import replace

from .interface import BrokerConnectionError, BrokerInterface
from .models import AccountSnapshot, Fill, Order, OrderIntent, OrderStatus, OrderType, Position, utcnow

FAULTS = ("disconnect_before_send", "disconnect_after_send", "reject", "partial_fill", "no_fill",
          "duplicate_ack", "bad_price", "disconnect_on_query")


class SimulatedBroker(BrokerInterface):
    name = "simulated"

    def __init__(self, account_id: str, balance: float, *, commission_per_unit: float = 0.0,
                 slippage_bps: float = 0.0) -> None:
        self.account_id = account_id
        self.balance = float(balance)
        self.commission_per_unit = commission_per_unit
        self.slippage_bps = slippage_bps
        self.connected = False
        self.prices: dict[str, float] = {}
        self.orders: dict[str, Order] = {}
        self.by_client_id: dict[str, str] = {}
        self.positions: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # qty, avg
        self.fills: list[Fill] = []
        self._faults: list[str] = []
        self._ids = itertools.count(1)
        self.send_count = 0  # orders the server actually received

    # ------------------------------------------------------------------ test hooks
    def inject(self, fault: str, times: int = 1) -> None:
        if fault not in FAULTS:
            raise ValueError(f"fault inconnue {fault}; connues : {FAULTS}")
        self._faults.extend([fault] * times)

    def _take(self, fault: str) -> bool:
        if fault in self._faults:
            self._faults.remove(fault)
            return True
        return False

    def set_price(self, symbol: str, price: float) -> None:
        self.prices[symbol] = float(price)
        self._work_resting_orders(symbol)

    # ------------------------------------------------------------------ interface
    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def _require(self) -> None:
        if not self.connected:
            raise BrokerConnectionError("non connecté")

    def get_account(self) -> AccountSnapshot:
        self._require()
        upnl = sum(q * (self.prices.get(s, avg) - avg) for s, (q, avg) in self.positions.items())
        return AccountSnapshot(self.account_id, self.balance, self.balance + upnl)

    def get_positions(self) -> list[Position]:
        self._require()
        if self._take("disconnect_on_query"):
            raise BrokerConnectionError("coupure pendant la requête")
        return [Position(s, q, avg) for s, (q, avg) in self.positions.items() if abs(q) > 1e-12]

    def get_orders(self, *, open_only: bool = True, client_order_id: str | None = None) -> list[Order]:
        self._require()
        if self._take("disconnect_on_query"):
            raise BrokerConnectionError("coupure pendant la requête")
        if client_order_id is not None:
            oid = self.by_client_id.get(client_order_id)
            return [self.orders[oid].copy()] if oid else []
        return [o.copy() for o in self.orders.values() if (o.status.is_open or not open_only)]

    def place_order(self, intent: OrderIntent) -> Order:
        self._require()
        if self._take("disconnect_before_send"):
            raise BrokerConnectionError("coupure avant l'envoi")
        # Idempotency: the same client id returns the order already on file.
        if intent.client_order_id and intent.client_order_id in self.by_client_id:
            return self.orders[self.by_client_id[intent.client_order_id]].copy()
        self.send_count += 1
        oid = f"SIM-{next(self._ids)}"
        order = Order(order_id=oid, intent=intent, status=OrderStatus.ACCEPTED)
        self.orders[oid] = order
        if intent.client_order_id:
            self.by_client_id[intent.client_order_id] = oid
        if self._take("reject"):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "rejeté par le courtier (simulé)"
        elif intent.symbol not in self.prices:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "pas de prix pour l'instrument"
        elif intent.order_type == OrderType.MARKET and not self._take("no_fill"):
            qty = intent.quantity / 2 if self._take("partial_fill") else intent.quantity
            self._fill(order, qty)
        lost = self._take("disconnect_after_send")
        dup = self._take("duplicate_ack")
        if lost:
            raise BrokerConnectionError("réponse perdue après l'envoi")
        result = order.copy()
        if dup:
            # A duplicated acknowledgement: same order id delivered twice to the client.
            self._dup_ack = result
        return result

    def cancel_order(self, order_id: str) -> Order:
        self._require()
        o = self.orders[order_id]
        if o.status.is_open:
            o.status = OrderStatus.CANCELLED
            o.updated_at = utcnow()
        return o.copy()

    def modify_order(self, order_id: str, **changes) -> Order:
        self._require()
        o = self.orders[order_id]
        if not o.status.is_open:
            return o.copy()
        o.intent = replace(o.intent, **changes)
        o.updated_at = utcnow()
        self._work_resting_orders(o.intent.symbol)
        return o.copy()

    # ------------------------------------------------------------------ matching
    def _fill(self, order: Order, qty: float, price: float | None = None) -> None:
        ref = price if price is not None else self.prices[order.intent.symbol]
        if self._take("bad_price"):
            ref = ref * 10  # an aberrant print — the OMS must notice
        side = order.intent.side
        px = ref * (1 + side * self.slippage_bps / 1e4)
        qty = min(qty, order.remaining)
        if qty <= 0:
            return
        commission = self.commission_per_unit * qty
        pos = self.positions[order.intent.symbol]
        q0, avg0 = pos
        q1 = q0 + side * qty
        if q0 == 0 or (q0 > 0) == (side > 0):
            avg1 = (abs(q0) * avg0 + qty * px) / abs(q1) if q1 else 0.0
        else:
            closed = min(abs(q0), qty)
            self.balance += closed * (px - avg0) * (1 if q0 > 0 else -1)
            avg1 = avg0 if abs(q1) > 0 and (q1 > 0) == (q0 > 0) else (px if q1 else 0.0)
        pos[0], pos[1] = q1, avg1
        self.balance -= commission
        order.avg_fill_price = (order.avg_fill_price * order.filled_qty + px * qty) / (order.filled_qty + qty)
        order.filled_qty += qty
        order.status = OrderStatus.FILLED if order.remaining <= 1e-12 else OrderStatus.PARTIALLY_FILLED
        order.updated_at = utcnow()
        self.fills.append(Fill(order.order_id, order.intent.client_order_id, order.intent.symbol, side, qty, px,
                               commission, utcnow()))

    def _work_resting_orders(self, symbol: str) -> None:
        price = self.prices.get(symbol)
        if price is None:
            return
        for o in self.orders.values():
            if o.intent.symbol != symbol or not o.status.is_open or o.intent.order_type == OrderType.MARKET:
                continue
            it = o.intent
            if it.order_type == OrderType.LIMIT and ((it.side > 0 and price <= it.limit_price)
                                                     or (it.side < 0 and price >= it.limit_price)):
                self._fill(o, o.remaining, it.limit_price)
            elif it.order_type == OrderType.STOP and ((it.side > 0 and price >= it.stop_price)
                                                      or (it.side < 0 and price <= it.stop_price)):
                self._fill(o, o.remaining, price)

    # ------------------------------------------------------------------ for tests
    def force_position(self, symbol: str, qty: float, avg: float) -> None:
        """Simulate a position appearing outside the OMS (manual trade, broker error)."""
        self.positions[symbol] = [qty, avg]
