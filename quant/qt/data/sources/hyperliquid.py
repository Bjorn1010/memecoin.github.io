"""Hyperliquid public API — perp candles, funding and open interest, keyless.

Reachable where Binance's live REST is geo-blocked, so this doubles as the live
price source for the paper-trading loop and as a cross-venue sanity check on the
Binance archive (a silent difference between two independent venues is how you catch
a corrupt download before it poisons a model).
"""

from __future__ import annotations

import pandas as pd

from .. import schemas
from ..http import post_json

URL = "https://api.hyperliquid.xyz/info"
VENUE = "hyperliquid"

# The API caps a candle snapshot at 5000 rows per call.
_MAX_ROWS = 5000

_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def universe() -> pd.DataFrame:
    """All listed perps with their size decimals and max leverage."""
    meta = post_json(URL, {"type": "meta"})
    return pd.DataFrame(meta.get("universe", []))


def candles(
    coin: str,
    interval: str = "1h",
    start: str | pd.Timestamp = "2023-01-01",
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Paginated candle history in canonical kline schema."""
    step = _INTERVAL_MS.get(interval)
    if step is None:
        raise ValueError(f"unsupported interval {interval!r}")
    start_ms = int(schemas.to_utc(start).value // 10**6)
    end_ms = int(schemas.to_utc(end or pd.Timestamp.now("UTC")).value // 10**6)

    frames = []
    cursor = start_ms
    while cursor < end_ms:
        window_end = min(cursor + step * _MAX_ROWS, end_ms)
        payload = {
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": interval, "startTime": cursor, "endTime": window_end},
        }
        rows = post_json(URL, payload, min_gap=0.35) or []
        if not rows:
            break
        frames.append(pd.DataFrame(rows))
        last_open = int(rows[-1]["t"])
        nxt = last_open + step
        if nxt <= cursor:  # no forward progress; stop rather than spin
            break
        cursor = nxt

    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.KLINES)

    raw = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame(
        {
            "ts": pd.to_numeric(raw["T"]) + 1,  # close time, stamped at the close instant
            "open": raw["o"],
            "high": raw["h"],
            "low": raw["l"],
            "close": raw["c"],
            "volume": raw["v"],
            "quote_volume": pd.to_numeric(raw["v"]) * pd.to_numeric(raw["c"]),
            "trades": raw.get("n", 0),
            "taker_buy_base": float("nan"),  # not published by this venue
            "taker_buy_quote": float("nan"),
        }
    )
    return schemas.normalise(out, schemas.KLINES)


def funding_context() -> pd.DataFrame:
    """Current funding rate, open interest and mark price for every listed perp.

    A live snapshot, not history — used by the paper loop as a carry feature and as a
    crowding gauge (open interest jumping while funding is extreme is the classic
    pre-liquidation-cascade signature).
    """
    meta, ctxs = post_json(URL, {"type": "metaAndAssetCtxs"})
    names = [u["name"] for u in meta["universe"]]
    rows = []
    for name, ctx in zip(names, ctxs):
        rows.append(
            {
                "coin": name,
                "funding": float(ctx.get("funding", "nan")),
                "open_interest": float(ctx.get("openInterest", "nan")),
                "mark": float(ctx.get("markPx", "nan")),
                "oracle": float(ctx.get("oraclePx", "nan")),
                "day_volume": float(ctx.get("dayNtlVlm", "nan")),
                "premium": float(ctx.get("premium") or "nan"),
            }
        )
    out = pd.DataFrame(rows)
    out["ts"] = int(pd.Timestamp.now("UTC").value // 10**6)
    return out


def ingest(catalog, coins, interval: str = "1h", start: str = "2023-01-01", end: str | None = None):
    rows = []
    for coin in coins:
        df = candles(coin, interval=interval, start=start, end=end)
        catalog.write(f"{schemas.KLINES}_{interval}", VENUE, coin, df)
        rows.append({"symbol": coin, "rows": len(df)})
    return pd.DataFrame(rows)
