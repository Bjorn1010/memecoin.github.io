"""Kill switch — independent of every model, latching, reset by a human only.

It does not ask the strategy whether stopping is a good idea. Any trigger trips it; a
tripped switch blocks every new order in its scope (one account, or everything) until
someone calls `reset` with a name and a reason. Automatic re-arming would turn a
detected fault back into a live one.

Triggers: excessive daily loss, critical drawdown, API failures, position mismatch,
abnormal slippage, abnormal volatility, duplicate orders, broker errors, invalid data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

TRIGGERS = ("daily_loss", "drawdown", "api_failure", "position_mismatch", "abnormal_slippage",
            "abnormal_volatility", "duplicate_orders", "broker_errors", "invalid_data", "manual")

GLOBAL = "*"


@dataclass
class Trip:
    scope: str
    trigger: str
    detail: str
    at: datetime


@dataclass
class KillSwitch:
    max_api_failures: int = 3
    max_consecutive_rejects: int = 3
    max_slippage_bps: float = 50.0
    max_volatility_multiple: float = 4.0  # bar range vs its recent median
    trips: dict[str, Trip] = field(default_factory=dict)
    history: list[Trip] = field(default_factory=list)
    _api_failures: dict[str, int] = field(default_factory=dict)
    _rejects: dict[str, int] = field(default_factory=dict)

    def trip(self, trigger: str, detail: str, scope: str = GLOBAL) -> Trip:
        if trigger not in TRIGGERS:
            raise ValueError(f"déclencheur inconnu {trigger}")
        t = Trip(scope, trigger, detail, datetime.now(timezone.utc))
        self.trips.setdefault(scope, t)  # the first cause is the one that matters
        self.history.append(t)
        return t

    def is_tripped(self, scope: str = GLOBAL) -> bool:
        return GLOBAL in self.trips or scope in self.trips

    def reason(self, scope: str = GLOBAL) -> str:
        t = self.trips.get(GLOBAL) or self.trips.get(scope)
        return f"{t.trigger}: {t.detail}" if t else ""

    def reset(self, scope: str, *, by: str, reason: str) -> None:
        if not by or not reason:
            raise ValueError("un reset exige un nom et une raison")
        self.trips.pop(scope, None)
        self._api_failures.pop(scope, None)
        self._rejects.pop(scope, None)
        self.history.append(Trip(scope, "manual", f"reset par {by} : {reason}", datetime.now(timezone.utc)))

    # ---------------------------------------------------------------- counters
    def api_failure(self, scope: str, detail: str) -> None:
        self._api_failures[scope] = self._api_failures.get(scope, 0) + 1
        if self._api_failures[scope] >= self.max_api_failures:
            self.trip("api_failure", f"{self._api_failures[scope]} échecs API : {detail}", scope)

    def api_success(self, scope: str) -> None:
        self._api_failures[scope] = 0

    def rejected(self, scope: str, detail: str) -> None:
        self._rejects[scope] = self._rejects.get(scope, 0) + 1
        if self._rejects[scope] >= self.max_consecutive_rejects:
            self.trip("broker_errors", f"{self._rejects[scope]} rejets consécutifs : {detail}", scope)

    def accepted(self, scope: str) -> None:
        self._rejects[scope] = 0

    def check_slippage(self, scope: str, reference: float, fill: float, side: int) -> None:
        if reference > 0:
            slip = side * (fill - reference) / reference * 1e4
            if slip > self.max_slippage_bps:
                self.trip("abnormal_slippage", f"{slip:.0f} bp contre {self.max_slippage_bps:.0f} bp autorisés", scope)

    def check_volatility(self, scope: str, bar_range: float, median_range: float) -> None:
        if median_range > 0 and bar_range / median_range > self.max_volatility_multiple:
            self.trip("abnormal_volatility", f"range = {bar_range / median_range:.1f} × la médiane", scope)

    def check_price(self, scope: str, symbol: str, price) -> bool:
        ok = isinstance(price, (int, float)) and price == price and price > 0 and price != float("inf")
        if not ok:
            self.trip("invalid_data", f"prix invalide pour {symbol}: {price!r}", scope)
        return ok
