"""Feed resilience and health monitoring.

The failure that actually ends paper-trading runs is not a bad signal — it is a
WebSocket that dropped at 3am and a process that sat there for nine hours holding a
position and believing the last price it saw. Everything in this module exists to make
that impossible:

* **Reconnection with exponential backoff and jitter.** Jitter matters: without it,
  every client reconnects at the same instant after a venue restarts, and the
  thundering herd gets them all rejected again.
* **Staleness detection.** A connection that is open but silent is more dangerous than
  one that is closed, because nothing raises. `StalenessMonitor` treats "no data for
  longer than expected" as a fault, which is what it is.
* **A health record the risk layer can act on.** A degraded feed should shrink the book,
  not be logged and ignored. `HealthMonitor.trading_allowed` is the switch the loop
  consults before taking new risk.

The design principle throughout: **an unhealthy system takes no new risk**. It does not
guess, does not carry on with stale data, and does not need a human awake to notice.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

import pandas as pd


@dataclass
class HealthStatus:
    healthy: bool
    reason: str
    last_data_age_seconds: float
    consecutive_failures: int
    total_reconnects: int
    uptime_seconds: float
    bars_received: int

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "reason": self.reason,
            "last_data_age_seconds": round(self.last_data_age_seconds, 1),
            "consecutive_failures": self.consecutive_failures,
            "total_reconnects": self.total_reconnects,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "bars_received": self.bars_received,
        }


class HealthMonitor:
    """Tracks feed liveness and decides whether the system may take new risk."""

    def __init__(
        self,
        *,
        stale_after_seconds: float = 300.0,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[HealthStatus], None] | None = None,
    ) -> None:
        self.stale_after = stale_after_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self.on_status_change = on_status_change

        self.started_at = time.monotonic()
        self.last_data_at = time.monotonic()
        self.consecutive_failures = 0
        self.total_reconnects = 0
        self.bars_received = 0
        self.errors: list[dict] = []
        self._last_healthy: bool | None = None

    # ------------------------------------------------------------------ events
    def record_data(self) -> None:
        self.last_data_at = time.monotonic()
        self.consecutive_failures = 0
        self.bars_received += 1
        self._emit()

    def record_failure(self, error: Exception | str) -> None:
        self.consecutive_failures += 1
        self.errors.append(
            {
                "ts": pd.Timestamp.now("UTC"),
                "error": str(error),
                "type": type(error).__name__ if isinstance(error, Exception) else "str",
            }
        )
        self.errors = self.errors[-100:]
        self._emit()

    def record_reconnect(self) -> None:
        self.total_reconnects += 1
        self._emit()

    # ------------------------------------------------------------------ status
    def status(self) -> HealthStatus:
        age = time.monotonic() - self.last_data_at
        healthy, reason = True, "ok"

        if self.consecutive_failures >= self.max_consecutive_failures:
            healthy = False
            reason = f"{self.consecutive_failures} consecutive feed failures"
        elif age > self.stale_after:
            # An open-but-silent connection is the dangerous case: nothing raised, and
            # the last price is being treated as current.
            healthy = False
            reason = f"no data for {age:.0f}s (stale after {self.stale_after:.0f}s)"

        return HealthStatus(
            healthy=healthy,
            reason=reason,
            last_data_age_seconds=age,
            consecutive_failures=self.consecutive_failures,
            total_reconnects=self.total_reconnects,
            uptime_seconds=time.monotonic() - self.started_at,
            bars_received=self.bars_received,
        )

    @property
    def trading_allowed(self) -> bool:
        """The switch the loop consults before taking NEW risk.

        Deliberately asymmetric: an unhealthy feed blocks new positions but never forces
        a liquidation, because flattening on stale prices is its own way to lose money.
        Existing positions stay under the risk engine's normal limits.
        """
        return self.status().healthy

    def _emit(self) -> None:
        if self.on_status_change is None:
            return
        current = self.status()
        if self._last_healthy is None or current.healthy != self._last_healthy:
            self._last_healthy = current.healthy
            try:
                self.on_status_change(current)
            except Exception:
                pass  # a broken alert hook must never take down the loop

    def report(self) -> dict:
        out = self.status().to_dict()
        out["recent_errors"] = self.errors[-5:]
        return out


@dataclass
class ReconnectPolicy:
    """Exponential backoff with jitter and a ceiling."""

    initial_seconds: float = 1.0
    max_seconds: float = 300.0
    multiplier: float = 2.0
    jitter: float = 0.3  # +/- this fraction, to avoid synchronised reconnect storms
    max_attempts: int | None = None  # None = retry forever

    def delay(self, attempt: int) -> float:
        base = min(self.initial_seconds * (self.multiplier**attempt), self.max_seconds)
        spread = base * self.jitter
        return max(base + random.uniform(-spread, spread), 0.1)

    def should_retry(self, attempt: int) -> bool:
        return self.max_attempts is None or attempt < self.max_attempts


class ResilientFeed:
    """Wraps any feed so a disconnection reconnects instead of ending the run.

    Also enforces staleness: if the wrapped feed goes quiet for longer than
    `stale_after_seconds` the iterator is cancelled and restarted, because a silent
    WebSocket looks identical to a healthy one from the outside and will happily hang
    forever.
    """

    def __init__(
        self,
        feed_factory: Callable[[], object],
        *,
        policy: ReconnectPolicy | None = None,
        monitor: HealthMonitor | None = None,
        stale_after_seconds: float = 300.0,
        verbose: bool = True,
    ) -> None:
        self.feed_factory = feed_factory
        self.policy = policy or ReconnectPolicy()
        self.monitor = monitor or HealthMonitor(stale_after_seconds=stale_after_seconds)
        self.stale_after = stale_after_seconds
        self.verbose = verbose
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def bars(self) -> AsyncIterator[dict]:
        attempt = 0
        while not self._stop.is_set():
            try:
                feed = self.feed_factory()
                iterator = feed.bars().__aiter__()

                while not self._stop.is_set():
                    try:
                        bar = await asyncio.wait_for(iterator.__anext__(), timeout=self.stale_after)
                    except StopAsyncIteration:
                        break  # feed ended cleanly; reconnect below
                    except asyncio.TimeoutError as exc:
                        self.monitor.record_failure(
                            f"feed silent for {self.stale_after:.0f}s — treating as dead"
                        )
                        raise ConnectionError("feed went silent") from exc

                    self.monitor.record_data()
                    attempt = 0  # a delivered bar proves the connection is healthy
                    yield bar

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.monitor.record_failure(exc)
                if not self.policy.should_retry(attempt):
                    if self.verbose:
                        print(f"[feed] giving up after {attempt} attempts: {exc}")
                    return
                delay = self.policy.delay(attempt)
                if self.verbose:
                    print(
                        f"[feed] {type(exc).__name__}: {exc} — reconnecting in {delay:.1f}s "
                        f"(attempt {attempt + 1})"
                    )
                self.monitor.record_reconnect()
                attempt += 1
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    return  # stop was requested during the backoff
                except asyncio.TimeoutError:
                    continue

            if self._stop.is_set():
                return
            # Clean end of the underlying feed: back off before reopening it, otherwise
            # a feed that ends immediately becomes a busy loop.
            delay = self.policy.delay(attempt)
            self.monitor.record_reconnect()
            attempt += 1
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return
            except asyncio.TimeoutError:
                continue


class CrossVenueCheck:
    """Compares the same instrument across two venues and flags disagreement.

    A price that diverges from an independent venue by more than a tolerance is
    virtually always a bad print or a stalled feed, not an arbitrage. Trading on it is
    how a system takes a large position on a number that never existed — so the
    honest response is to stand down until they agree again.
    """

    def __init__(self, tolerance_bps: float = 50.0, max_age_seconds: float = 120.0) -> None:
        self.tolerance_bps = tolerance_bps
        self.max_age_seconds = max_age_seconds
        self.prices: dict[str, tuple[float, float]] = {}  # venue -> (price, monotonic ts)

    def update(self, venue: str, price: float) -> None:
        if price > 0:
            self.prices[venue] = (float(price), time.monotonic())

    def check(self) -> dict:
        now = time.monotonic()
        fresh = {v: p for v, (p, ts) in self.prices.items() if now - ts <= self.max_age_seconds}
        if len(fresh) < 2:
            return {"agree": True, "reason": "fewer than two fresh venues — no check possible",
                    "n_venues": len(fresh)}

        values = list(fresh.values())
        lo, hi = min(values), max(values)
        mid = (lo + hi) / 2
        spread_bps = (hi - lo) / mid * 1e4 if mid > 0 else float("inf")
        agree = spread_bps <= self.tolerance_bps
        return {
            "agree": bool(agree),
            "spread_bps": float(spread_bps),
            "tolerance_bps": self.tolerance_bps,
            "prices": fresh,
            "n_venues": len(fresh),
            "reason": "ok" if agree else (
                f"venues disagree by {spread_bps:.0f}bps — assume a bad print and stand down"
            ),
        }


def console_alert(status: HealthStatus) -> None:
    """Default alert hook: print a status transition.

    Swap for a webhook, an email, or anything else. Transitions only, never every bar —
    an alert that fires constantly is one nobody reads.
    """
    marker = "OK" if status.healthy else "DEGRADED"
    print(f"[health] {marker}: {status.reason} (uptime {status.uptime_seconds:.0f}s, "
          f"{status.bars_received} bars, {status.total_reconnects} reconnects)")
