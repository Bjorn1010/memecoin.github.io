"""TradingView — what is and is not possible, and the part that is.

**There is no free TradingView historical-data API, and there cannot be one.**
TradingView does not own most of the data it displays: it licenses feeds from exchanges
and vendors under agreements that forbid redistribution. Verified against their public
endpoints: the symbol-search endpoint returns 403, the documented data endpoints return
404, and the one open endpoint (`scanner.tradingview.com`) serves screener *snapshots* —
current values for a list of tickers, no history at all.

Unofficial scrapers exist. They breach the terms of service, break whenever the private
protocol changes, and would put the account they authenticate with at risk. This module
does not implement one, and the deep-history need is better served elsewhere:

    Bitstamp        BTC from 2011  — deeper than TradingView's own crypto coverage
    Binance Vision  from Aug 2017  — the first month BTCUSDT ever traded
    Stooq           decades of equities, indices, FX

What IS legitimate, and what this module does:

1. **Import CSVs you exported yourself.** TradingView's chart export ("Export chart
   data...") gives you the data you already have a licence to use. `read_csv` handles
   its format, including the several date conventions it emits.
2. **Read the live screener snapshot.** The scanner endpoint is public and returns
   current prices and metrics across a market — useful for universe construction, and
   honest about being a snapshot rather than history.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import schemas
from ..http import post_json

SCANNER = "https://scanner.tradingview.com"
VENUE = "tradingview"

# Column names TradingView emits, mapped to the canonical schema.
_ALIASES = {
    "time": "ts", "date": "ts", "datetime": "ts", "timestamp": "ts",
    "open": "open", "high": "high", "low": "low", "close": "close",
    "volume": "volume", "vol": "volume",
}


def read_csv(path: str | Path, *, symbol: str | None = None, catalog=None,
             interval: str = "1d", venue: str = VENUE) -> pd.DataFrame:
    """Load a CSV exported from a TradingView chart into the canonical schema.

    Handles the date formats TradingView emits — unix seconds, unix milliseconds, and
    ISO strings — by detecting rather than assuming, because getting this wrong shifts
    an entire history by a factor of 1000 and the result still looks like a price
    series. (That exact class of bug already cost this codebase a debugging session;
    see qt.data.schemas.epoch_ms.)

    Pass `catalog` to write the result straight into the lake.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no such file: {path}")

    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    renamed = {c: _ALIASES[c] for c in raw.columns if c in _ALIASES}
    df = raw.rename(columns=renamed)

    missing = [c for c in ("ts", "open", "high", "low", "close") if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing {missing}. Expected a TradingView chart export "
            f"with time/open/high/low/close columns; found {list(raw.columns)}"
        )

    df["ts"] = _parse_time_column(df["ts"])
    for col in ("volume", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"):
        if col not in df.columns:
            df[col] = float("nan") if col.startswith("taker") else 0.0

    out = schemas.normalise(df, schemas.KLINES)
    if catalog is not None:
        name = symbol or path.stem.upper()
        catalog.write(f"{schemas.KLINES}_{interval}", venue, name, out)
    return out


def _parse_time_column(series: pd.Series) -> pd.Series:
    """Epoch milliseconds from whatever time format the export used."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all():
        median = float(numeric.median())
        # Distinguish by magnitude: ~1.7e9 is seconds, ~1.7e12 is milliseconds.
        if median > 1e14:
            return (numeric // 1000).astype("int64")
        if median > 1e11:
            return numeric.astype("int64")
        return (numeric * 1000).astype("int64")

    parsed = pd.to_datetime(series, utc=True, errors="coerce", format="mixed")
    if parsed.isna().all():
        raise ValueError("could not parse the time column as epoch or as dates")
    return schemas.epoch_ms(parsed)


def import_directory(directory: str | Path, catalog, *, interval: str = "1d") -> pd.DataFrame:
    """Import every TradingView CSV in a directory.

    Filenames are used as symbols, so `BINANCE_BTCUSDT, 1D.csv` becomes BTCUSDT — the
    exchange prefix and the interval suffix TradingView adds are stripped.
    """
    directory = Path(directory)
    rows = []
    for path in sorted(directory.glob("*.csv")):
        symbol = path.stem.split(",")[0].strip()
        if "_" in symbol:
            symbol = symbol.split("_", 1)[1]  # drop the exchange prefix
        try:
            df = read_csv(path, symbol=symbol.upper(), catalog=catalog, interval=interval)
        except Exception as exc:
            rows.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        rows.append(
            {
                "file": path.name,
                "symbol": symbol.upper(),
                "rows": len(df),
                "start": pd.Timestamp(int(df["ts"].min()), unit="ms", tz="UTC") if len(df) else None,
                "end": pd.Timestamp(int(df["ts"].max()), unit="ms", tz="UTC") if len(df) else None,
            }
        )
    return pd.DataFrame(rows)


def screener_snapshot(market: str = "crypto", limit: int = 100) -> pd.DataFrame:
    """Current screener values from TradingView's public scanner endpoint.

    A *snapshot*, not history — this is the one TradingView endpoint that is genuinely
    open, and all it gives is the present. Useful for building a universe by liquidity
    rank; useless for backtesting, and it is important not to confuse the two.
    """
    body = {
        "columns": ["name", "close", "change", "volume", "market_cap_basic"],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, int(limit)],
    }
    payload = post_json(f"{SCANNER}/{market}/scan", body, min_gap=1.0)
    rows = (payload or {}).get("data", [])
    if not rows:
        return pd.DataFrame()
    records = []
    for row in rows:
        values = row.get("d", [])
        records.append(dict(zip(body["columns"], values)))
    out = pd.DataFrame(records)
    out.attrs["note"] = "live snapshot only — TradingView publishes no free history API"
    return out
