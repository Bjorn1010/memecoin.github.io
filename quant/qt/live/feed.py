"""Live market data feeds and incremental bar construction.

Two feeds, both free and keyless:

* **Coinbase WebSocket** — every executed trade with its aggressor side, so live bars
  carry the same signed-flow column the Binance archive provides for history. This is
  what lets the live features be the *same* features the model trained on. A live feed
  without aggressor information would silently zero out the microstructure group and
  the model would be scoring a different world than the one it learned.
* **Hyperliquid REST** — polled candles and funding. Lower resolution, but it works
  where WebSockets are blocked and it covers perpetuals.

`BarBuilder` accumulates ticks into bars identical in shape to the historical ones,
and emits a bar only when its interval has *closed*. Emitting a partial bar would feed
the model an incomplete observation — the live equivalent of look-ahead's mirror image,
and just as damaging.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Iterable

import pandas as pd

from ..data.sources import coinbase, hyperliquid, kraken


@dataclass
class Tick:
    ts: int  # ms
    symbol: str
    price: float
    qty: float
    is_buyer_maker: bool


@dataclass
class BarBuilder:
    """Accumulates ticks into closed bars of a fixed interval."""

    interval_ms: int = 60_000
    _current: dict[str, dict] = field(default_factory=dict)

    def _bucket(self, ts: int) -> int:
        return (ts // self.interval_ms) * self.interval_ms

    def add(self, tick: Tick) -> dict | None:
        """Add a tick; return a completed bar when this tick belongs to a new interval."""
        bucket = self._bucket(tick.ts)
        cur = self._current.get(tick.symbol)

        closed = None
        if cur is not None and bucket > cur["bucket"]:
            closed = self._finalise(cur)
            cur = None

        if cur is None:
            cur = {
                "bucket": bucket,
                "symbol": tick.symbol,
                "open": tick.price,
                "high": tick.price,
                "low": tick.price,
                "close": tick.price,
                "volume": 0.0,
                "quote_volume": 0.0,
                "trades": 0.0,
                "buy_volume": 0.0,
            }
            self._current[tick.symbol] = cur

        cur["high"] = max(cur["high"], tick.price)
        cur["low"] = min(cur["low"], tick.price)
        cur["close"] = tick.price
        cur["volume"] += tick.qty
        cur["quote_volume"] += tick.qty * tick.price
        cur["trades"] += 1.0
        if not tick.is_buyer_maker:  # aggressor was the buyer
            cur["buy_volume"] += tick.qty
        return closed

    def _finalise(self, cur: dict) -> dict:
        return {
            # Stamp at the CLOSE of the interval — same convention as the archive.
            "ts": cur["bucket"] + self.interval_ms,
            "start_ts": cur["bucket"],
            "symbol": cur["symbol"],
            "open": cur["open"],
            "high": cur["high"],
            "low": cur["low"],
            "close": cur["close"],
            "vwap": cur["quote_volume"] / cur["volume"] if cur["volume"] > 0 else cur["close"],
            "volume": cur["volume"],
            "quote_volume": cur["quote_volume"],
            "trades": cur["trades"],
            "buy_volume": cur["buy_volume"],
            "sell_volume": cur["volume"] - cur["buy_volume"],
        }

    def force_close(self, symbol: str) -> dict | None:
        """Close a bar that has gone quiet (no ticks in the following interval)."""
        cur = self._current.pop(symbol, None)
        return self._finalise(cur) if cur else None

    def pending(self) -> dict[str, dict]:
        return dict(self._current)


class LiveFeed:
    """Base interface: an async iterator of closed bars."""

    async def bars(self) -> AsyncIterator[dict]:  # pragma: no cover - interface
        raise NotImplementedError
        yield {}


class CoinbaseTradeFeed(LiveFeed):
    """Trade-driven bars from the Coinbase WebSocket."""

    def __init__(self, products: Iterable[str], interval_ms: int = 60_000) -> None:
        self.products = list(products)
        self.builder = BarBuilder(interval_ms)

    async def bars(self) -> AsyncIterator[dict]:
        async for trade in coinbase.stream_trades(self.products):
            tick = Tick(
                ts=trade["ts"],
                symbol=trade["symbol"],
                price=trade["price"],
                qty=trade["qty"],
                is_buyer_maker=trade["is_buyer_maker"],
            )
            bar = self.builder.add(tick)
            if bar is not None:
                yield bar


class PollingCandleFeed(LiveFeed):
    """Polls a REST candle endpoint and emits each newly *closed* candle exactly once.

    The dedupe on last-emitted timestamp is what makes this safe: REST endpoints happily
    return the in-progress candle, and acting on one is trading on an observation that
    has not finished happening.
    """

    def __init__(
        self,
        symbols: Iterable[str],
        interval: str = "1m",
        venue: str = "hyperliquid",
        poll_seconds: float = 20.0,
    ) -> None:
        self.symbols = list(symbols)
        self.interval = interval
        self.venue = venue
        self.poll_seconds = poll_seconds
        self._last_emitted: dict[str, int] = defaultdict(int)

    def _fetch(self, symbol: str) -> pd.DataFrame:
        lookback = pd.Timestamp.utcnow() - pd.Timedelta(hours=6)
        if self.venue == "hyperliquid":
            return hyperliquid.candles(symbol, self.interval, start=lookback)
        if self.venue == "coinbase":
            return coinbase.candles(symbol, self.interval, start=lookback)
        if self.venue == "kraken":
            return kraken.ohlc(symbol, self.interval)
        raise ValueError(f"unknown venue {self.venue!r}")

    async def bars(self) -> AsyncIterator[dict]:
        now_ms = int(pd.Timestamp.utcnow().value // 10**6)
        while True:
            for symbol in self.symbols:
                try:
                    df = await asyncio.to_thread(self._fetch, symbol)
                except Exception as exc:  # a feed hiccup must not kill the loop
                    print(f"[feed] {symbol}: {type(exc).__name__}: {exc}")
                    continue
                if df.empty:
                    continue
                now_ms = int(pd.Timestamp.utcnow().value // 10**6)
                for _, row in df.iterrows():
                    ts = int(row["ts"])
                    # Only closed candles, and only ones not already emitted.
                    if ts > now_ms or ts <= self._last_emitted[symbol]:
                        continue
                    self._last_emitted[symbol] = ts
                    yield {
                        "ts": ts,
                        "symbol": symbol,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "vwap": float(row["close"]),
                        "volume": float(row["volume"]),
                        "quote_volume": float(row.get("quote_volume", 0.0) or 0.0),
                        "trades": float(row.get("trades", 0.0) or 0.0),
                        "buy_volume": float("nan"),
                        "sell_volume": float("nan"),
                    }
            await asyncio.sleep(self.poll_seconds)


class ReplayFeed(LiveFeed):
    """Replays historical bars as if they were arriving live.

    The single most useful testing tool in the whole live stack: it exercises the exact
    code path the real loop takes — same bar builder, same feature computation, same
    broker — against data whose outcome is already known. A discrepancy between a
    replay run and a backtest of the same period is a bug in one of them, and finding
    it here costs nothing.
    """

    def __init__(self, bars: pd.DataFrame, symbol: str, delay: float = 0.0) -> None:
        # Named `history`, not `bars`: the feed interface exposes `bars()` as a method,
        # and an attribute of the same name would shadow it.
        self.history = bars
        self.symbol = symbol
        self.delay = delay

    async def bars_iter(self) -> AsyncIterator[dict]:
        for ts, row in self.history.iterrows():
            if self.delay:
                await asyncio.sleep(self.delay)
            yield {
                "ts": int(row["ts"]) if "ts" in row else int(pd.Timestamp(ts).value // 10**6),
                "symbol": self.symbol,
                **{
                    c: float(row[c])
                    for c in ("open", "high", "low", "close", "volume", "quote_volume",
                              "trades", "buy_volume", "sell_volume", "vwap")
                    if c in row
                },
            }

    async def bars(self) -> AsyncIterator[dict]:
        async for bar in self.bars_iter():
            yield bar


def make_feed(venue: str, symbols: Iterable[str], interval: str = "1m") -> LiveFeed:
    """Pick a feed by venue name."""
    interval_ms = int(pd.Timedelta(interval).value // 10**6)
    if venue == "coinbase_ws":
        return CoinbaseTradeFeed(symbols, interval_ms)
    if venue in ("hyperliquid", "coinbase", "kraken"):
        return PollingCandleFeed(symbols, interval, venue)
    raise ValueError(f"unknown feed venue {venue!r}")
