"""Canonical dataset schemas.

Every venue adapter normalises into these columns. Downstream code (bars, features,
backtest) never sees a venue-specific field, which is what makes the same research
run unchanged across Binance archives, Kraken, Coinbase or Hyperliquid.

Time convention, applied without exception across the codebase:
    `ts` is the UTC millisecond timestamp of the *close* of the observation.
    A bar stamped 12:00 contains information available at 12:00 and not one
    microsecond later. Every feature is a function of bars up to and including the
    current one; every trade decision is executed on the *next* bar.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Dataset names used as directory names in the lake.
# ---------------------------------------------------------------------------
KLINES = "klines"  # OHLCV + taker-buy split (order flow!) at a fixed interval
TRADES = "trades"  # tick-level aggressed trades
QUOTES = "quotes"  # top-of-book best bid/ask snapshots
FUNDING = "funding"  # perpetual funding rate prints
EOD = "eod"  # daily bars for cross-asset / macro context

KLINE_COLUMNS = [
    "ts",  # int64, ms, bar CLOSE time
    "open",
    "high",
    "low",
    "close",
    "volume",  # base asset units
    "quote_volume",  # quote currency units traded
    "trades",  # number of individual trades in the bar
    "taker_buy_base",  # base volume where the buyer was the aggressor
    "taker_buy_quote",
]

TRADE_COLUMNS = [
    "ts",  # int64, ms
    "price",
    "qty",
    "is_buyer_maker",  # bool: True => the AGGRESSOR was a seller (sell-side print)
]

QUOTE_COLUMNS = ["ts", "bid", "bid_qty", "ask", "ask_qty"]

FUNDING_COLUMNS = ["ts", "rate"]

EOD_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]

_SCHEMAS = {
    KLINES: KLINE_COLUMNS,
    TRADES: TRADE_COLUMNS,
    QUOTES: QUOTE_COLUMNS,
    FUNDING: FUNDING_COLUMNS,
    EOD: EOD_COLUMNS,
}

_DTYPES = {
    "ts": "int64",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "quote_volume": "float64",
    "trades": "int64",
    "taker_buy_base": "float64",
    "taker_buy_quote": "float64",
    "price": "float64",
    "qty": "float64",
    "is_buyer_maker": "bool",
    "bid": "float64",
    "bid_qty": "float64",
    "ask": "float64",
    "ask_qty": "float64",
    "rate": "float64",
}


def base_dataset(dataset: str) -> str:
    """Strip a frequency suffix: 'klines_1h' and 'klines_1m' share the klines schema.

    Datasets are stored per frequency (they are different data), but a frequency never
    changes the columns, so the schema lookup is on the base name.
    """
    if dataset in _SCHEMAS:
        return dataset
    head = dataset.split("_", 1)[0]
    if head in _SCHEMAS:
        return head
    raise KeyError(f"unknown dataset {dataset!r}; known: {sorted(_SCHEMAS)} (+ '_<interval>')")


def columns_for(dataset: str) -> list[str]:
    return list(_SCHEMAS[base_dataset(dataset)])


def normalise(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Coerce a venue frame into the canonical schema.

    Sorts by `ts`, drops duplicate timestamps (keeping the last print, which is the
    corrected one on every venue we support) and enforces dtypes. Missing optional
    columns are filled with NaN rather than silently dropped so that a dataset from a
    poorer venue stays *shape-compatible* with a richer one.
    """
    cols = columns_for(dataset)
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = pd.NA
    out = out[cols]
    for c in cols:
        dtype = _DTYPES[c]
        if dtype == "int64":
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype("int64")
        elif dtype == "bool":
            out[c] = out[c].fillna(False).astype("bool")
        else:
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
    out = out.sort_values("ts", kind="mergesort")
    if base_dataset(dataset) != TRADES:
        # Bar-like datasets have one row per timestamp; a duplicate is a restatement,
        # so the last print wins. Trades legitimately share timestamps by the
        # thousand — deduplicating them would silently delete most of the tape.
        out = out.drop_duplicates(subset="ts", keep="last")
    return out.reset_index(drop=True)


def epoch_ms(values) -> pd.Series:
    """Epoch milliseconds from any datetime Series/Index, whatever its resolution.

    Do not write `index.astype("int64") // 10**6`. Since pandas 2, a DatetimeIndex
    carries its own unit — `pd.to_datetime(x, unit="ms")` yields ms-resolution and
    parsing strings yields us — and `astype("int64")` returns the value in *that* unit.
    Dividing by 1e6 therefore silently produces garbage for anything that is not
    nanosecond-backed, and the failure looks like corrupt data rather than a bug.

    (`Timestamp.value` and `Timedelta.value` are always nanoseconds and are safe.)
    """
    idx = pd.DatetimeIndex(values)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    return pd.Series(idx.as_unit("ms").astype("int64"))


def to_utc(value) -> pd.Timestamp:
    """A UTC Timestamp from anything, whether or not it already carries a timezone.

    `pd.Timestamp(x, tz="UTC")` raises when x is already tz-aware, and
    `pd.Timestamp.now("UTC")` returns tz-aware on pandas 3 — so the common idiom
    `pd.Timestamp(end or pd.Timestamp.now("UTC"), tz="UTC")` works until the caller
    omits `end`, and then throws. Localise or convert depending on what arrived.
    """
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")


def to_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """Attach a UTC DatetimeIndex derived from `ts`, keeping `ts` as a column."""
    out = df.copy()
    out.index = pd.to_datetime(out["ts"], unit="ms", utc=True)
    out.index.name = "dt"
    return out
