"""Stooq free end-of-day data — equities, ETFs, indices, FX, commodities.

Why this belongs in a crypto-capable quant stack: cross-asset context is one of the
few sources of genuinely *orthogonal* information. Crypto trend and vol regimes are
conditioned by equity risk appetite, real rates and the dollar. Free, keyless, and
deep enough for daily-frequency regime features.

Useful tickers (Stooq symbology):
    ^spx   S&P 500            ^ndx   Nasdaq 100        ^vix   VIX
    ^dji   Dow                spy.us / qqq.us / tlt.us / gld.us / hyg.us
    dxy    Dollar index       xauusd  Gold spot         cl.f   WTI front
"""

from __future__ import annotations

import io

import pandas as pd

from .. import schemas
from ..http import get_text

URL = "https://stooq.com/q/d/l/"
VENUE = "stooq"

DEFAULT_CONTEXT = [
    "^spx",  # equity risk appetite
    "^vix",  # implied equity vol — the risk-off switch
    "^ndx",  # tech beta, the closest listed cousin of crypto
    "tlt.us",  # long duration / real rates
    "gld.us",  # store-of-value competitor
    "hyg.us",  # credit spreads
    "dxy",  # dollar
]


def daily(symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Fetch the full daily history for `symbol`, optionally clipped to a window."""
    text = get_text(URL, params={"s": symbol, "i": "d"}, min_gap=1.0)
    if not text or "Date" not in text.split("\n", 1)[0]:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)
    raw = pd.read_csv(io.StringIO(text))
    raw.columns = [c.strip().lower() for c in raw.columns]
    dt = pd.to_datetime(raw["date"], utc=True)
    # Stamp the bar at the session close instant (23:59:59.999 UTC of that date) so it
    # can never be joined against an intraday bar that precedes it.
    ts = schemas.epoch_ms(dt + pd.Timedelta(hours=23, minutes=59, seconds=59))
    out = pd.DataFrame(
        {
            "ts": ts,
            "open": raw.get("open"),
            "high": raw.get("high"),
            "low": raw.get("low"),
            "close": raw.get("close"),
            "volume": raw.get("volume", 0.0),
        }
    )
    out = schemas.normalise(out, schemas.EOD)
    if start is not None:
        out = out[out["ts"] >= int(schemas.to_utc(start).value // 10**6)]
    if end is not None:
        out = out[out["ts"] <= int(schemas.to_utc(end).value // 10**6)]
    return out.reset_index(drop=True)


def ingest(catalog, symbols=None, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    rows = []
    for symbol in symbols or DEFAULT_CONTEXT:
        df = daily(symbol, start=start, end=end)
        catalog.write(schemas.EOD, VENUE, symbol.replace("^", "idx_"), df)
        rows.append({"symbol": symbol, "rows": len(df)})
    return pd.DataFrame(rows)
