"""Coinbase Exchange public market data (REST + WebSocket), keyless.

Its WebSocket is the live feed for the paper-trading loop: `matches` gives every
executed trade with an explicit aggressor side, and `ticker` gives best bid/ask. That
is enough to build real-time volume/dollar bars and a true spread estimate.
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Iterable

import pandas as pd

from .. import schemas
from ..http import get_json

REST = "https://api.exchange.coinbase.com"
WS = "wss://ws-feed.exchange.coinbase.com"
VENUE = "coinbase"

_GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
_MAX_ROWS = 300  # hard API cap per request


def products() -> pd.DataFrame:
    return pd.DataFrame(get_json(f"{REST}/products"))


def candles(
    product: str,
    interval: str = "1h",
    start: str | pd.Timestamp = "2023-01-01",
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    gran = _GRANULARITY.get(interval)
    if gran is None:
        raise ValueError(f"unsupported interval {interval!r}; use {sorted(_GRANULARITY)}")
    start_ts = schemas.to_utc(start)
    end_ts = schemas.to_utc(end or pd.Timestamp.now("UTC"))

    frames = []
    cursor = start_ts
    span = pd.Timedelta(seconds=gran * _MAX_ROWS)
    while cursor < end_ts:
        chunk_end = min(cursor + span, end_ts)
        rows = get_json(
            f"{REST}/products/{product}/candles",
            params={
                "granularity": gran,
                "start": cursor.isoformat(),
                "end": chunk_end.isoformat(),
            },
            min_gap=0.3,
        )
        if rows:
            frames.append(pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"]))
        cursor = chunk_end

    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.KLINES)
    raw = pd.concat(frames, ignore_index=True)
    close_ms = (pd.to_numeric(raw["time"]) + gran) * 1000  # open time -> close instant
    out = pd.DataFrame(
        {
            "ts": close_ms,
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "volume": raw["volume"],
            "quote_volume": pd.to_numeric(raw["volume"]) * pd.to_numeric(raw["close"]),
            "trades": 0,
            "taker_buy_base": float("nan"),
            "taker_buy_quote": float("nan"),
        }
    )
    return schemas.normalise(out, schemas.KLINES)


async def stream_trades(products_: Iterable[str]) -> AsyncIterator[dict]:
    """Yield normalised live trades: {ts, symbol, price, qty, is_buyer_maker}.

    Coinbase reports the resting order's side in `side`; a `sell` match means the
    resting order was a sell, i.e. the aggressor was a BUYER. We invert accordingly so
    that `is_buyer_maker` carries the same meaning as in the Binance archive.
    """
    import websockets

    sub = {
        "type": "subscribe",
        "product_ids": list(products_),
        "channels": ["matches", "heartbeat"],
    }
    async with websockets.connect(WS, ping_interval=20, max_queue=1024) as ws:
        await ws.send(json.dumps(sub))
        async for message in ws:
            try:
                msg = json.loads(message)
            except (TypeError, ValueError):
                continue
            if msg.get("type") not in ("match", "last_match"):
                continue
            aggressor_is_buyer = msg.get("side") == "sell"
            yield {
                "ts": int(pd.Timestamp(msg["time"]).value // 10**6),
                "symbol": msg["product_id"],
                "price": float(msg["price"]),
                "qty": float(msg["size"]),
                "is_buyer_maker": not aggressor_is_buyer,
            }


def ingest(catalog, symbols, interval: str = "1h", start: str = "2023-01-01", end: str | None = None):
    rows = []
    for symbol in symbols:
        df = candles(symbol, interval=interval, start=start, end=end)
        catalog.write(f"{schemas.KLINES}_{interval}", VENUE, symbol, df)
        rows.append({"symbol": symbol, "rows": len(df)})
    return pd.DataFrame(rows)
