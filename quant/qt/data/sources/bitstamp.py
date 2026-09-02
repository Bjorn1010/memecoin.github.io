"""Bitstamp public API — the deepest free crypto history that exists.

Bitstamp has been running since 2011 and publishes its full OHLC history without a
key. For BTC that is roughly six years of data that predates Binance entirely, and it
covers two complete cycles (2013 and 2017) that no Binance-only dataset contains.

Why that matters beyond bragging about sample size: a model trained only on 2021-2024
has seen exactly one regime transition. Backtests over such a window are testing
whether a strategy survives *one* market, not whether it survives markets. The 2013
and 2017 cycles have completely different microstructure — no perpetuals, no
institutional flow, far thinner books — which is precisely why they are a harder and
more informative test.

The API caps a response at 1000 candles, so history is paginated backwards.
"""

from __future__ import annotations

import pandas as pd

from .. import schemas
from ..http import get_json

REST = "https://www.bitstamp.net/api/v2"
VENUE = "bitstamp"

# Bitstamp expresses granularity in seconds.
_STEP = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "3d": 259200,
}
_MAX_LIMIT = 1000

# Bitstamp uses lowercase concatenated pairs.
DEEP_HISTORY_PAIRS = ["btcusd", "ethusd", "xrpusd", "ltcusd", "bchusd"]


def _normalise_pair(symbol: str) -> str:
    """Accept BTCUSDT / BTC-USD / btcusd and return Bitstamp's form."""
    s = symbol.lower().replace("-", "").replace("/", "").replace("_", "")
    # Bitstamp quotes in USD, not USDT; treat them as the same quote asset.
    if s.endswith("usdt"):
        s = s[:-1]
    return s


def candles(
    symbol: str = "btcusd",
    interval: str = "1d",
    start: str | pd.Timestamp = "2011-01-01",
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Paginated OHLC history in canonical kline schema.

    Pages backwards from `end` because the API returns the most recent candles when a
    window is larger than the limit, so walking forwards silently skips history.
    """
    step = _STEP.get(interval)
    if step is None:
        raise ValueError(f"unsupported interval {interval!r}; use {sorted(_STEP)}")

    pair = _normalise_pair(symbol)
    start_s = int(schemas.to_utc(start).value // 10**9)
    end_s = int(schemas.to_utc(end or pd.Timestamp.now("UTC")).value // 10**9)

    frames = []
    cursor = end_s
    seen_oldest = None
    while cursor > start_s:
        window_start = max(cursor - step * _MAX_LIMIT, start_s)
        payload = get_json(
            f"{REST}/ohlc/{pair}/",
            params={
                "step": step,
                "limit": _MAX_LIMIT,
                "start": window_start,
                "end": cursor,
            },
            min_gap=0.6,
        )
        rows = (payload or {}).get("data", {}).get("ohlc", [])
        if not rows:
            break
        frames.append(pd.DataFrame(rows))

        oldest = min(int(r["timestamp"]) for r in rows)
        # No forward progress means the archive has run out; stop rather than loop.
        if seen_oldest is not None and oldest >= seen_oldest:
            break
        seen_oldest = oldest
        cursor = oldest - step

    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.KLINES)

    raw = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame(
        {
            # Bitstamp stamps the candle OPEN, so add one step to reach the close.
            "ts": (pd.to_numeric(raw["timestamp"]) + step) * 1000,
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "volume": raw["volume"],
            "quote_volume": pd.to_numeric(raw["volume"]) * pd.to_numeric(raw["close"]),
            "trades": 0,
            "taker_buy_base": float("nan"),  # not published
            "taker_buy_quote": float("nan"),
        }
    )
    out = schemas.normalise(out, schemas.KLINES)
    lo = int(schemas.to_utc(start).value // 10**6)
    return out[out["ts"] >= lo].reset_index(drop=True)


def first_available(symbol: str = "btcusd", interval: str = "1d") -> pd.Timestamp | None:
    """Earliest candle Bitstamp will serve for this pair — its true listing date."""
    df = candles(symbol, interval, start="2011-01-01")
    if df.empty:
        return None
    return pd.Timestamp(int(df["ts"].min()), unit="ms", tz="UTC")


def ingest(catalog, symbols=None, interval: str = "1d", start: str = "2011-01-01",
           end: str | None = None) -> pd.DataFrame:
    rows = []
    for symbol in symbols or DEEP_HISTORY_PAIRS:
        df = candles(symbol, interval=interval, start=start, end=end)
        pair = _normalise_pair(symbol).upper()
        catalog.write(f"{schemas.KLINES}_{interval}", VENUE, pair, df)
        rows.append(
            {
                "symbol": pair,
                "rows": len(df),
                "start": pd.Timestamp(int(df["ts"].min()), unit="ms", tz="UTC") if len(df) else None,
                "end": pd.Timestamp(int(df["ts"].max()), unit="ms", tz="UTC") if len(df) else None,
            }
        )
    return pd.DataFrame(rows)
