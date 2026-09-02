"""Binance public data archive — https://data.binance.vision

This is the single most valuable free dataset in crypto and it needs no API key:

* **klines** from 2017 at 1s/1m/…/1d granularity, and crucially with the
  `taker_buy_base` split, which gives signed order flow for free — most "free" OHLCV
  sources throw that column away and with it most of the microstructure signal.
* **aggTrades**: every aggressed trade, with the maker/taker flag, i.e. true tick
  data for volume/dollar bars and for order-flow imbalance.
* **bookTicker**: best bid/ask updates (USD-M futures), i.e. the real spread to charge
  in a backtest instead of a guessed constant.
* **fundingRate**: the actual perpetual carry, needed to make a perp backtest honest.

Layout of the archive:
    /data/{spot|futures/um|futures/cm}/{monthly|daily}/{kind}/{SYMBOL}/[interval/]FILE.zip

Monthly files appear a few days after month end, so we fall back to daily files for
the tail of the range. Files are immutable, hence cached forever on disk.
"""

from __future__ import annotations

import io
import zipfile
from typing import Iterable, Iterator, Literal

import pandas as pd

from .. import schemas
from ..http import cached_download

BASE = "https://data.binance.vision/data"

Market = Literal["spot", "um", "cm"]

_MARKET_PATH = {"spot": "spot", "um": "futures/um", "cm": "futures/cm"}

VENUE = {"spot": "binance", "um": "binance-um", "cm": "binance-cm"}

# Column layouts of the raw CSVs (they carry no header in older files).
_KLINE_RAW = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
]
_AGGTRADE_RAW = [
    "agg_id",
    "price",
    "qty",
    "first_id",
    "last_id",
    "ts",
    "is_buyer_maker",
    "best_match",
]
_BOOKTICKER_RAW = [
    "update_id",
    "bid",
    "bid_qty",
    "ask",
    "ask_qty",
    "transaction_time",
    "event_time",
]
_FUNDING_RAW = ["calc_time", "funding_interval_hours", "last_funding_rate"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _months(start: pd.Timestamp, end: pd.Timestamp) -> Iterator[pd.Timestamp]:
    cur = pd.Timestamp(year=start.year, month=start.month, day=1, tz="UTC")
    last = pd.Timestamp(year=end.year, month=end.month, day=1, tz="UTC")
    while cur <= last:
        yield cur
        cur = cur + pd.offsets.MonthBegin(1)


def _days(start: pd.Timestamp, end: pd.Timestamp) -> Iterator[pd.Timestamp]:
    cur = start.normalize()
    while cur <= end:
        yield cur
        cur = cur + pd.Timedelta(days=1)


def _as_utc(value) -> pd.Timestamp:
    """Delegates to the shared converter; kept as a local name for readability."""
    return schemas.to_utc(value)


def _read_zip_csv(path, names: list[str]) -> pd.DataFrame:
    """Read the single CSV inside a Binance zip, tolerating the optional header row."""
    with zipfile.ZipFile(path) as z:
        member = z.namelist()[0]
        raw = z.read(member)
    if not raw.strip():
        return pd.DataFrame(columns=names)
    first_line = raw.split(b"\n", 1)[0].decode("utf-8", "replace")
    first_field = first_line.split(",")[0].strip()
    has_header = True
    try:
        float(first_field)
        has_header = False
    except ValueError:
        has_header = True
    df = pd.read_csv(
        io.BytesIO(raw),
        header=0 if has_header else None,
        names=None if has_header else names,
    )
    if has_header:
        # Newer archives use the same order but snake_case-ish names; trust position.
        df.columns = names[: len(df.columns)]
    return df


def _timestamp_unit(series: pd.Series) -> str:
    """Binance switched some 2025 files to microsecond timestamps. Detect, don't assume."""
    if series.empty:
        return "ms"
    v = float(pd.to_numeric(series.iloc[0], errors="coerce"))
    if v > 1e17:
        return "ns"
    if v > 1e14:
        return "us"
    return "ms"


def _to_ms(series: pd.Series) -> pd.Series:
    unit = _timestamp_unit(series)
    v = pd.to_numeric(series, errors="coerce")
    if unit == "us":
        return (v // 1000).astype("int64")
    if unit == "ns":
        return (v // 1_000_000).astype("int64")
    return v.astype("int64")


def _urls(market: Market, kind: str, symbol: str, interval: str | None, stamp: str, freq: str) -> str:
    mp = _MARKET_PATH[market]
    sym = symbol.upper()
    if interval:
        return f"{BASE}/{mp}/{freq}/{kind}/{sym}/{interval}/{sym}-{interval}-{stamp}.zip"
    return f"{BASE}/{mp}/{freq}/{kind}/{sym}/{sym}-{kind}-{stamp}.zip"


def _fetch_range(
    market: Market,
    kind: str,
    symbol: str,
    interval: str | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    names: list[str],
) -> list[pd.DataFrame]:
    """Fetch monthly archives, falling back to daily files where a month is missing."""
    frames: list[pd.DataFrame] = []
    for month in _months(start, end):
        stamp = f"{month.year:04d}-{month.month:02d}"
        path = cached_download(_urls(market, kind, symbol, interval, stamp, "monthly"), subdir="binance")
        if path is not None:
            frames.append(_read_zip_csv(path, names))
            continue
        # Month not published yet (or not available): try the daily files inside it.
        m_start = max(month, start)
        m_end = min(month + pd.offsets.MonthEnd(1), end)
        for day in _days(m_start, m_end):
            dstamp = day.strftime("%Y-%m-%d")
            dpath = cached_download(
                _urls(market, kind, symbol, interval, dstamp, "daily"), subdir="binance"
            )
            if dpath is not None:
                frames.append(_read_zip_csv(dpath, names))
    return frames


# ---------------------------------------------------------------------------
# public loaders — each returns a frame in canonical schema
# ---------------------------------------------------------------------------
def klines(
    symbol: str,
    interval: str = "1h",
    start: str | pd.Timestamp = "2020-01-01",
    end: str | pd.Timestamp | None = None,
    market: Market = "spot",
) -> pd.DataFrame:
    start_ts, end_ts = _as_utc(start), _as_utc(end or pd.Timestamp.now("UTC"))
    frames = _fetch_range(market, "klines", symbol, interval, start_ts, end_ts, _KLINE_RAW)
    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.KLINES)
    raw = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame(
        {
            # Stamp the bar at its CLOSE. `close_time` is inclusive-exclusive by one ms
            # in the archive, so +1 makes it the true close instant.
            "ts": _to_ms(raw["close_time"]) + 1,
            "open": raw["open"],
            "high": raw["high"],
            "low": raw["low"],
            "close": raw["close"],
            "volume": raw["volume"],
            "quote_volume": raw["quote_volume"],
            "trades": raw["trades"],
            "taker_buy_base": raw["taker_buy_base"],
            "taker_buy_quote": raw["taker_buy_quote"],
        }
    )
    out = schemas.normalise(out, schemas.KLINES)
    lo, hi = int(start_ts.value // 10**6), int(end_ts.value // 10**6)
    return out[(out["ts"] >= lo) & (out["ts"] <= hi)].reset_index(drop=True)


def agg_trades(
    symbol: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp | None = None,
    market: Market = "spot",
) -> pd.DataFrame:
    """Tick-level aggressed trades. Warning: ~1-3 GB per liquid symbol per month."""
    start_ts, end_ts = _as_utc(start), _as_utc(end or pd.Timestamp.now("UTC"))
    frames = _fetch_range(market, "aggTrades", symbol, None, start_ts, end_ts, _AGGTRADE_RAW)
    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.TRADES)
    raw = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame(
        {
            "ts": _to_ms(raw["ts"]),
            "price": raw["price"],
            "qty": raw["qty"],
            "is_buyer_maker": raw["is_buyer_maker"].astype(str).str.lower().isin(["true", "1"]),
        }
    )
    # Trades share timestamps by the thousand: keep every print, so bypass the
    # dedup-on-ts that `normalise` applies to bar-like datasets.
    out = out.sort_values("ts", kind="mergesort").reset_index(drop=True)
    lo, hi = int(start_ts.value // 10**6), int(end_ts.value // 10**6)
    return out[(out["ts"] >= lo) & (out["ts"] <= hi)].reset_index(drop=True)


def book_ticker(
    symbol: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Best bid/ask updates (USD-M futures only in the archive)."""
    start_ts, end_ts = _as_utc(start), _as_utc(end or pd.Timestamp.now("UTC"))
    frames = _fetch_range("um", "bookTicker", symbol, None, start_ts, end_ts, _BOOKTICKER_RAW)
    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.QUOTES)
    raw = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame(
        {
            "ts": _to_ms(raw["transaction_time"]),
            "bid": raw["bid"],
            "bid_qty": raw["bid_qty"],
            "ask": raw["ask"],
            "ask_qty": raw["ask_qty"],
        }
    )
    return schemas.normalise(out, schemas.QUOTES)


def funding(
    symbol: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Realised perpetual funding prints (USD-M)."""
    start_ts, end_ts = _as_utc(start), _as_utc(end or pd.Timestamp.now("UTC"))
    frames = _fetch_range("um", "fundingRate", symbol, None, start_ts, end_ts, _FUNDING_RAW)
    if not frames:
        return schemas.normalise(pd.DataFrame(), schemas.FUNDING)
    raw = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame({"ts": _to_ms(raw["calc_time"]), "rate": raw["last_funding_rate"]})
    return schemas.normalise(out, schemas.FUNDING)


def ingest(
    catalog,
    symbols: Iterable[str],
    interval: str = "1h",
    start: str = "2021-01-01",
    end: str | None = None,
    market: Market = "spot",
    with_funding: bool = False,
) -> pd.DataFrame:
    """Download and persist klines (and optionally funding) for a set of symbols."""
    venue = VENUE[market]
    rows = []
    for symbol in symbols:
        df = klines(symbol, interval=interval, start=start, end=end, market=market)
        dataset = f"{schemas.KLINES}_{interval}"
        catalog.write(dataset, venue, symbol, df)
        rows.append({"symbol": symbol, "dataset": dataset, "rows": len(df)})
        if with_funding and market == "um":
            fdf = funding(symbol, start=start, end=end)
            catalog.write(schemas.FUNDING, venue, symbol, fdf)
            rows.append({"symbol": symbol, "dataset": schemas.FUNDING, "rows": len(fdf)})
    return pd.DataFrame(rows)
