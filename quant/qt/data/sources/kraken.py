"""Kraken public REST — recent OHLC and spread, keyless.

Kraken only serves the last ~720 candles per interval, so it is not a history source.
It earns its place as an independent live/recent cross-check: when two venues
disagree on the last close by more than a tick, something is wrong with the feed and
the paper loop should refuse to trade rather than act on a bad print.
"""

from __future__ import annotations

import pandas as pd

from .. import schemas
from ..http import get_json

REST = "https://api.kraken.com/0/public"
VENUE = "kraken"

_INTERVAL_MIN = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def ohlc(pair: str = "XBTUSD", interval: str = "1h") -> pd.DataFrame:
    minutes = _INTERVAL_MIN.get(interval)
    if minutes is None:
        raise ValueError(f"unsupported interval {interval!r}")
    payload = get_json(f"{REST}/OHLC", params={"pair": pair, "interval": minutes}, min_gap=1.0)
    if payload.get("error"):
        raise RuntimeError(f"kraken error: {payload['error']}")
    result = payload["result"]
    key = next(k for k in result if k != "last")
    raw = pd.DataFrame(
        result[key],
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"],
    )
    out = pd.DataFrame(
        {
            "ts": (pd.to_numeric(raw["time"]) + minutes * 60) * 1000,
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "volume": raw["volume"],
            "quote_volume": pd.to_numeric(raw["volume"]) * pd.to_numeric(raw["vwap"]),
            "trades": raw["count"],
            "taker_buy_base": float("nan"),
            "taker_buy_quote": float("nan"),
        }
    )
    return schemas.normalise(out, schemas.KLINES)


def spread(pair: str = "XBTUSD") -> pd.DataFrame:
    """Recent best bid/ask prints — a real, observed spread for the cost model."""
    payload = get_json(f"{REST}/Spread", params={"pair": pair}, min_gap=1.0)
    result = payload["result"]
    key = next(k for k in result if k != "last")
    raw = pd.DataFrame(result[key], columns=["time", "bid", "ask"])
    out = pd.DataFrame(
        {
            "ts": pd.to_numeric(raw["time"]) * 1000,
            "bid": raw["bid"],
            "bid_qty": float("nan"),
            "ask": raw["ask"],
            "ask_qty": float("nan"),
        }
    )
    return schemas.normalise(out, schemas.QUOTES)
