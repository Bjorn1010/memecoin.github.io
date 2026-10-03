"""Order management: the layer that makes "send an order" safe.

Guarantees (each one tested in tests/test_execution.py):

* **No duplicate orders.** Client order ids are deterministic. Before resending after a
  transport failure the manager asks the broker whether it already holds that id; a
  second submission of the same intent returns the first order.
* **Bounded retries.** Transport failures are retried a fixed number of times, then the
  kill switch trips for the account. A loop that retries forever is how one network
  blip becomes forty orders.
* **Rejections are terminal for the order and counted for the account.**
* **Partial fills** are tracked; the unfilled remainder of a stale order is cancelled.
* **Stale orders** (open longer than `stale_after`) are cancelled.
* **Fill sanity:** a fill far from the reference price trips the kill switch.
* **Local state vs broker state** is reconciled; any mismatch trips the kill switch and
  nothing is "fixed" automatically — a position nobody can explain is a human's call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..brokers.interface import BrokerConnectionError, BrokerInterface
from ..brokers.models import Order, OrderIntent, OrderStatus
from .kill_switch import KillSwitch


@dataclass
class SubmitResult:
    ok: bool
    order: Order | None = None
    reason: str = ""
    retries: int = 0


@dataclass
class OrderManager:
    broker: BrokerInterface
    kill_switch: KillSwitch
    account_id: str
    max_retries: int = 2
    stale_after: timedelta = timedelta(minutes=5)
    position_tolerance: float = 1e-6
    orders: dict[str, Order] = field(default_factory=dict)  # by client_order_id
    expected_positions: dict[str, float] = field(default_factory=dict)
    _seen_filled: dict[str, float] = field(default_factory=dict)
    log: list[dict] = field(default_factory=list)

    def _note(self, event: str, **kw) -> None:
        self.log.append({"event": event, "at": datetime.now(timezone.utc).isoformat(), **kw})

    # ---------------------------------------------------------------- submit
    def submit(self, intent: OrderIntent, reference_price: float) -> SubmitResult:
        scope = self.account_id
        if self.kill_switch.is_tripped(scope):
            return SubmitResult(False, reason=f"kill switch : {self.kill_switch.reason(scope)}")
        if not self.kill_switch.check_price(scope, intent.symbol, reference_price):
            return SubmitResult(False, reason="prix de référence invalide")
        if not intent.client_order_id:
            return SubmitResult(False, reason="client_order_id obligatoire (idempotence)")
        known = self.orders.get(intent.client_order_id)
        if known is not None and known.status != OrderStatus.REJECTED:
            self._note("duplicate_blocked", client_order_id=intent.client_order_id)
            return SubmitResult(True, known, reason="déjà soumis : ordre existant renvoyé")

        retries = 0
        while True:
            try:
                order = self.broker.place_order(intent)
                self.kill_switch.api_success(scope)
                break
            except BrokerConnectionError as exc:
                self.kill_switch.api_failure(scope, str(exc))
                self._note("transport_error", error=str(exc), retries=retries)
                found = self._lookup(intent.client_order_id)
                if found is not None:
                    order = found
                    self._note("recovered_after_transport_error", order_id=found.order_id)
                    break
                if self.kill_switch.is_tripped(scope) or retries >= self.max_retries:
                    return SubmitResult(False, reason=f"échec transport après {retries} relances : {exc}",
                                        retries=retries)
                retries += 1

        self.orders[intent.client_order_id] = order
        if order.status == OrderStatus.REJECTED:
            self.kill_switch.rejected(scope, order.reject_reason)
            self._note("rejected", reason=order.reject_reason)
            return SubmitResult(False, order, reason=f"rejeté : {order.reject_reason}", retries=retries)
        self.kill_switch.accepted(scope)
        self._absorb(order, reference_price)
        return SubmitResult(True, order, retries=retries)

    def _lookup(self, client_order_id: str) -> Order | None:
        for _ in range(self.max_retries + 1):
            try:
                found = self.broker.get_orders(open_only=False, client_order_id=client_order_id)
                return found[0] if found else None
            except BrokerConnectionError as exc:
                self.kill_switch.api_failure(self.account_id, f"requête d'ordre : {exc}")
                if self.kill_switch.is_tripped(self.account_id):
                    return None
        return None

    def _absorb(self, order: Order, reference_price: float | None = None) -> None:
        """Book newly filled quantity into the local expected position."""
        cid = order.intent.client_order_id
        prev = self._seen_filled.get(cid, 0.0)
        new = order.filled_qty - prev
        if new > 1e-12:
            sym = order.intent.symbol
            self.expected_positions[sym] = self.expected_positions.get(sym, 0.0) + order.intent.side * new
            self._seen_filled[cid] = order.filled_qty
            if reference_price:
                self.kill_switch.check_slippage(self.account_id, reference_price, order.avg_fill_price,
                                                order.intent.side)

    # ---------------------------------------------------------------- maintenance
    def sync(self, now: datetime | None = None) -> list[str]:
        """Refresh orders from the broker, cancel stale ones, detect duplicates."""
        now = now or datetime.now(timezone.utc)
        events = []
        try:
            broker_orders = self.broker.get_orders(open_only=False)
        except BrokerConnectionError as exc:
            self.kill_switch.api_failure(self.account_id, f"sync : {exc}")
            return [f"sync impossible : {exc}"]
        by_cid: dict[str, list[Order]] = {}
        for o in broker_orders:
            by_cid.setdefault(o.intent.client_order_id, []).append(o)
        for cid, lst in by_cid.items():
            if len(lst) > 1:
                self.kill_switch.trip("duplicate_orders", f"{len(lst)} ordres pour {cid}", self.account_id)
                events.append(f"doublon détecté : {cid}")
            o = lst[0]
            if cid not in self.orders:
                # An order this manager never sent: someone (or something) else is
                # trading the account. Not ours to explain away.
                self.kill_switch.trip("position_mismatch", f"ordre inconnu du gestionnaire : {o.order_id}",
                                      self.account_id)
                events.append(f"ordre inconnu : {o.order_id}")
            self.orders[cid] = o
            self._absorb(o)
            if o.status.is_open and now - o.created_at > self.stale_after:
                try:
                    self.broker.cancel_order(o.order_id)
                    events.append(f"ordre périmé annulé : {o.order_id} (rempli {o.filled_qty}/{o.intent.quantity})")
                    self._note("stale_cancelled", order_id=o.order_id, filled=o.filled_qty)
                except BrokerConnectionError as exc:
                    self.kill_switch.api_failure(self.account_id, f"annulation : {exc}")
        return events

    def reconcile(self) -> list[dict]:
        """Compare expected positions with the broker's. Any mismatch trips the switch."""
        try:
            broker = {p.symbol: p.quantity for p in self.broker.get_positions()}
        except BrokerConnectionError as exc:
            self.kill_switch.api_failure(self.account_id, f"réconciliation : {exc}")
            return [{"error": str(exc)}]
        mismatches = []
        for sym in set(broker) | set(self.expected_positions):
            local = self.expected_positions.get(sym, 0.0)
            remote = broker.get(sym, 0.0)
            if abs(local - remote) > self.position_tolerance:
                mismatches.append({"symbol": sym, "local": local, "broker": remote})
        if mismatches:
            self.kill_switch.trip("position_mismatch", f"{mismatches}", self.account_id)
            self._note("position_mismatch", detail=mismatches)
        return mismatches

    def flatten(self, reason: str) -> list[SubmitResult]:
        """Close everything the broker says is open. Allowed even when the switch is
        tripped — reducing risk is the one action a kill switch must never block."""
        out = []
        try:
            positions = self.broker.get_positions()
        except BrokerConnectionError as exc:
            return [SubmitResult(False, reason=f"positions inconnues : {exc}")]
        for p in positions:
            intent = OrderIntent(account_id=self.account_id, symbol=p.symbol, side=-1 if p.quantity > 0 else 1,
                                 quantity=abs(p.quantity), reduce_only=True,
                                 client_order_id=f"flat-{self.account_id}-{p.symbol}-{len(self.log)}",
                                 strategy=f"flatten:{reason}")
            try:
                o = self.broker.place_order(intent)
                self.orders[intent.client_order_id] = o
                self._absorb(o)
                out.append(SubmitResult(o.status != OrderStatus.REJECTED, o))
            except BrokerConnectionError as exc:
                out.append(SubmitResult(False, reason=str(exc)))
        return out
