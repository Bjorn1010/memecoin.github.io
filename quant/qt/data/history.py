"""Full-history ingestion — everything each venue will give, back to listing.

The default of "download from 2021" is a quiet methodological choice, and a bad one.
A model validated on 2021-2024 has seen exactly one regime transition; it is being
tested against *one* market, not against markets. Backtests over such a window
systematically overstate robustness, because whatever worked in that regime is the
thing the search selected for.

This module finds each symbol's actual listing date by probing the archive and pulls
everything from there. Practical depths, verified against the live endpoints:

    Bitstamp        BTC daily from 2011 — two cycles Binance never saw
    Binance Vision  BTCUSDT from August 2017, its first month of existence
    Coinbase        from 2015
    FRED            decades of macro: VIX from 1990, the 10-year from 1962

Probing rather than hardcoding matters because listing dates differ per symbol, are not
published in a machine-readable form, and quietly change when a venue relists a pair.
"""

from __future__ import annotations

import pandas as pd

from . import schemas
from .sources import binance_vision as bv
from .sources import bitstamp, coinbase, fred


def find_first_month(
    symbol: str, interval: str = "1d", market: str = "spot",
    earliest: str = "2017-07", latest: str | None = None,
) -> str | None:
    """Binary-search the Binance archive for a symbol's first published month.

    Linear probing from 2017 would cost ~100 requests per symbol against a rate-limited
    public endpoint; the archive is monotone (nothing before listing, everything after),
    so bisection finds the boundary in about seven.
    """
    start = pd.Timestamp(earliest + "-01", tz="UTC")
    end = pd.Timestamp(latest + "-01", tz="UTC") if latest else pd.Timestamp.now("UTC").normalize()

    months = pd.date_range(start, end, freq="MS", tz="UTC")
    if len(months) == 0:
        return None

    def exists(month: pd.Timestamp) -> bool:
        stamp = f"{month.year:04d}-{month.month:02d}"
        url = bv._urls(market, "klines", symbol, interval, stamp, "monthly")
        from .http import request

        # HEAD would be cheaper but the archive does not answer it reliably; a GET that
        # we immediately discard is the honest way to probe.
        resp = request("GET", url, min_gap=0.15, allow_status=(403, 404))
        return resp.status_code == 200

    # Monthly archives appear a few days after month end, so the newest one or two
    # months are routinely absent for a perfectly live symbol. Walk back to the most
    # recent month that does exist before bisecting, otherwise every probe returns
    # None on the first few days of a month.
    hi = len(months) - 1
    while hi >= 0 and not exists(months[hi]):
        hi -= 1
    if hi < 0:
        return None  # nothing at all, at any point
    lo = 0

    # Invariant: months[hi] exists, months[lo] is unknown. Converge on the boundary.
    while lo < hi:
        mid = (lo + hi) // 2
        if exists(months[mid]):
            hi = mid
        else:
            lo = mid + 1
    return f"{months[lo].year:04d}-{months[lo].month:02d}"


def ingest_full_history(
    catalog,
    symbols,
    *,
    interval: str = "1d",
    market: str = "spot",
    venue: str | None = None,
    probe: bool = True,
    fallback_start: str = "2017-08-01",
) -> pd.DataFrame:
    """Download every bar a venue has for each symbol, back to its listing date."""
    venue = venue or bv.VENUE[market]
    rows = []
    for symbol in symbols:
        first = find_first_month(symbol, interval, market) if probe else None
        start = f"{first}-01" if first else fallback_start
        df = bv.klines(symbol, interval=interval, start=start, market=market)
        dataset = f"{schemas.KLINES}_{interval}"
        catalog.write(dataset, venue, symbol, df)
        rows.append(
            {
                "symbol": symbol,
                "venue": venue,
                "listing_month": first or f"(probe off, from {fallback_start})",
                "rows": len(df),
                "start": pd.Timestamp(int(df["ts"].min()), unit="ms", tz="UTC") if len(df) else None,
                "end": pd.Timestamp(int(df["ts"].max()), unit="ms", tz="UTC") if len(df) else None,
                "years": round(len(df) / _bars_per_year(interval), 2) if len(df) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def ingest_deep_crypto(catalog, *, interval: str = "1d") -> pd.DataFrame:
    """Pull the deepest free crypto history available, from Bitstamp.

    This is the part that reaches back before Binance existed. For BTC it adds the 2013
    and 2017 cycles, whose microstructure — no perpetuals, no institutional flow, far
    thinner books — makes them a much harder test than anything after 2020.
    """
    return bitstamp.ingest(catalog, interval=interval, start="2011-01-01")


def ingest_macro(catalog, *, start: str = "1990-01-01") -> pd.DataFrame:
    """Cross-asset context, from FRED, with as much history as each series carries.

    This used to read Stooq. Stooq now answers with a JavaScript browser-verification
    challenge instead of CSV, and the source's "unparseable response means no data"
    branch turned that into a silent zero-row success — every macro alpha then computed
    on nothing. FRED is the Federal Reserve's own publication: no anti-bot layer, no
    key, and longer histories (the VIX from 1990, the 10-year from 1962).
    """
    return fred.ingest(catalog, start=start)


def coverage_report(catalog) -> pd.DataFrame:
    """What the lake actually holds, per symbol, with its span in years.

    Read the `years` column before trusting any backtest: a Sharpe measured over 1.5
    years of one regime is not evidence about anything, however good it looks.
    """
    inv = catalog.inventory()
    if inv.empty:
        return pd.DataFrame()

    grouped = (
        inv.groupby(["dataset", "venue", "symbol"])
        .agg(rows=("rows", "sum"), start=("start", "min"), end=("end", "max"), mb=("mb", "sum"))
        .reset_index()
    )
    span = (grouped["end"] - grouped["start"]).dt.total_seconds() / (365.25 * 24 * 3600)
    grouped["years"] = span.round(2)
    grouped["regimes_covered"] = grouped["start"].apply(_regimes_since)
    return grouped.sort_values("years", ascending=False).reset_index(drop=True)


def _regimes_since(start) -> str:
    """Which crypto cycles a start date actually covers.

    Blunt, and useful: a dataset beginning in 2021 has seen one bear market and one
    bull, so 'it works out of sample' means 'it worked in the second half of a single
    cycle'.
    """
    if pd.isna(start):
        return "unknown"
    year = pd.Timestamp(start).year
    cycles = []
    if year <= 2013:
        cycles.append("2013 cycle")
    if year <= 2017:
        cycles.append("2017 cycle")
    if year <= 2021:
        cycles.append("2021 cycle")
    if year <= 2024:
        cycles.append("2024 cycle")
    return ", ".join(cycles) if cycles else "partial current cycle"


def _bars_per_year(interval: str) -> float:
    seconds = pd.Timedelta(interval).total_seconds()
    return 365.25 * 24 * 3600 / max(seconds, 1.0)
