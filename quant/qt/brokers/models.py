"""Order, fill, position and account objects shared by every broker adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

    @property
    def is_open(self) -> bool:
        return self in (OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_client_order_id(account_id: str, strategy: str, signal_id: str, symbol: str, side: int) -> str:
    """Deterministic: the same intent always produces the same id, so a retry after a
    network failure can ask the broker "do you already have this?" instead of sending
    a second order."""
    raw = f"{account_id}|{strategy}|{signal_id}|{symbol}|{side}"
    return "q-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


@dataclass(frozen=True)
class OrderIntent:
    account_id: str
    symbol: str
    side: int  # +1 buy, -1 sell
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    protective_stop: float | None = None
    client_order_id: str = ""
    strategy: str = ""
    reduce_only: bool = False

    def __post_init__(self) -> None:
        if self.side not in (-1, 1):
            raise ValueError("order side must be +1 or -1")
        if not self.quantity > 0:
            raise ValueError("order quantity must be > 0")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit order needs limit_price")
        if self.order_type == OrderType.STOP and self.stop_price is None:
            raise ValueError("stop order needs stop_price")


@dataclass
class Order:
    order_id: str
    intent: OrderIntent
    status: OrderStatus = OrderStatus.NEW
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    reject_reason: str = ""

    @property
    def remaining(self) -> float:
        return max(self.intent.quantity - self.filled_qty, 0.0)

    def copy(self) -> "Order":
        return replace(self)


@dataclass(frozen=True)
class Fill:
    order_id: str
    client_order_id: str
    symbol: str
    side: int
    quantity: float
    price: float
    commission: float
    timestamp: datetime


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float  # signed
    avg_price: float


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    balance: float
    equity: float
    currency: str = "USD"
    timestamp: datetime = field(default_factory=utcnow)
