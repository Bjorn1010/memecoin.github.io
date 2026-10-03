"""BrokerInterface — the only thing the execution layer knows about a broker.

STRATEGY ≠ BROKER. Every broker or prop-firm platform gets an adapter implementing
these seven methods; the OrderManager above drives any of them identically.

Contract every adapter must honour (tested against SimulatedBroker):
* `place_order` is idempotent on `intent.client_order_id`: sending the same id twice
  returns the existing order, never a second one.
* `get_orders(client_order_id=...)` finds an order by that id, so a caller that lost
  the response to a network error can ask before retrying.
* Network problems raise `BrokerConnectionError`; a refusal by the broker is an order
  with status REJECTED, not an exception.
* Credentials come from the environment or a secret manager, never from arguments
  that could be logged, and never from files in the repository.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AccountSnapshot, Order, OrderIntent, Position


class BrokerError(RuntimeError):
    pass


class BrokerConnectionError(BrokerError):
    """Transport failure: the request may or may not have reached the broker."""


class BrokerInterface(ABC):
    name: str = "abstract"

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def get_account(self) -> AccountSnapshot: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_orders(self, *, open_only: bool = True, client_order_id: str | None = None) -> list[Order]: ...

    @abstractmethod
    def place_order(self, intent: OrderIntent) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order: ...

    @abstractmethod
    def modify_order(self, order_id: str, **changes) -> Order: ...
