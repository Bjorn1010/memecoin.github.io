"""Deribit public API — implied volatility index (DVOL), keyless.

DVOL is the crypto VIX. Implied vol carries information spot prices do not: the
implied-minus-realised spread is a well-documented risk premium, and its level is one
of the cleanest regime classifiers available for free.
"""

from __future__ import annotations

import pandas as pd

from .. import schemas
from ..http import get_json

REST = "https://www.deribit.com/api/v2/public"
VENUE = "deribit"

_MAX_ROWS = 1000  # API cap per request


def dvol(
    currency: str = "BTC",
    start: str | pd.Timestamp = "2023-01-01",
    end: str | pd.Timestamp | None = None,
    resolution_seconds: int = 3600,
) -> pd.DataFrame:
    """Implied volatility index history as OHLC bars (values in vol points, e.g. 55.2)."""
    start_ms = int(schemas.to_utc(start).value // 10**6)
    end_ms = int(schemas.to_utc(end or pd.Timestamp.now("UTC")).value // 10**6)
    step = resolution_seconds * 1000 * _MAX_ROWS

    frames = []
    cursor = start_ms
    while cursor < end_ms:
        window_end = min(cursor + step, end_ms)
        payload = get_json(
            f"{REST}/get_volatility_index_data",
            params={
                "currency": currency,
                "start_timestamp": cursor,
                "end_timestamp": window_end,
                "resolution": resolution_seconds,
            },
            min_gap=0.3,
        )
        data = (payload or {}).get("result", {}).get("data", [])
        if data:
            frames.append(pd.DataFrame(data, columns=["ts", "open", "high", "low", "close"]))
        cursor = window_end

    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)
    raw = pd.concat(frames, ignore_index=True)
    raw["ts"] = pd.to_numeric(raw["ts"]) + resolution_seconds * 1000  # stamp at bar close
    raw["volume"] = 0.0
    return schemas.normalise(raw, schemas.EOD)


def ingest(catalog, currencies=("BTC", "ETH"), start: str = "2023-01-01", end: str | None = None):
    rows = []
    for cur in currencies:
        df = dvol(cur, start=start, end=end)
        catalog.write(schemas.EOD, VENUE, f"DVOL{cur}", df)
        rows.append({"symbol": f"DVOL{cur}", "rows": len(df)})
    return pd.DataFrame(rows)
