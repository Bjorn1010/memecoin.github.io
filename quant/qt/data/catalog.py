"""The data lake: append-only Parquet + DuckDB query layer.

Design rules that matter for research validity:

1. **Raw is immutable.** Files under the lake are written once per (dataset, venue,
   symbol, month) partition and never edited in place. If a venue restates history we
   write a new partition file and keep the old one alongside; nothing silently
   rewrites the past under a backtest that already ran.
2. **Everything is timestamped in UTC milliseconds** at the close of the observation.
3. **Reads are explicitly bounded in time.** `read()` takes start/end so that a
   research script physically cannot touch data outside its window — the cheapest
   possible guard against look-ahead.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from ..config import CONFIG
from . import schemas


def _month_key(ts_ms: int) -> str:
    dt = pd.Timestamp(ts_ms, unit="ms", tz="UTC")
    return f"{dt.year:04d}-{dt.month:02d}"


@dataclass(frozen=True)
class Partition:
    dataset: str
    venue: str
    symbol: str
    month: str
    path: Path


class Catalog:
    """Parquet-backed store with a DuckDB front end for ad-hoc research queries."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else CONFIG.lake_dir
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ paths
    def dir_for(self, dataset: str, venue: str, symbol: str) -> Path:
        return self.root / dataset / venue / symbol.upper()

    def path_for(self, dataset: str, venue: str, symbol: str, month: str) -> Path:
        return self.dir_for(dataset, venue, symbol) / f"{month}.parquet"

    # ------------------------------------------------------------------ write
    def write(self, dataset: str, venue: str, symbol: str, df: pd.DataFrame) -> list[Partition]:
        """Normalise then write a frame, split into monthly partitions.

        Existing partitions are merged with the incoming rows (union on `ts`, last
        print wins) so that re-downloading an overlapping range is idempotent.
        """
        if df is None or df.empty:
            return []
        norm = schemas.normalise(df, dataset)
        norm["_month"] = [_month_key(t) for t in norm["ts"].to_numpy()]
        written: list[Partition] = []
        for month, chunk in norm.groupby("_month", sort=True):
            chunk = chunk.drop(columns="_month")
            path = self.path_for(dataset, venue, symbol, str(month))
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                prior = pd.read_parquet(path)
                chunk = schemas.normalise(pd.concat([prior, chunk], ignore_index=True), dataset)
            tmp = path.with_suffix(".parquet.tmp")
            chunk.to_parquet(tmp, index=False, compression="zstd")
            tmp.replace(path)
            written.append(Partition(dataset, venue, symbol.upper(), str(month), path))
        return written

    # ------------------------------------------------------------------- read
    def months(self, dataset: str, venue: str, symbol: str) -> list[str]:
        d = self.dir_for(dataset, venue, symbol)
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.parquet"))

    def has(self, dataset: str, venue: str, symbol: str, month: str) -> bool:
        return self.path_for(dataset, venue, symbol, month).exists()

    def read(
        self,
        dataset: str,
        venue: str,
        symbol: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        columns: Iterable[str] | None = None,
    ) -> pd.DataFrame:
        """Read a bounded time slice. Returns an empty, correctly-typed frame if absent."""
        d = self.dir_for(dataset, venue, symbol)
        cols = schemas.columns_for(dataset)
        if not d.exists():
            return schemas.normalise(pd.DataFrame(columns=cols), dataset)

        start_ms = _to_ms(start) if start is not None else None
        end_ms = _to_ms(end) if end is not None else None

        frames = []
        for path in sorted(d.glob("*.parquet")):
            # Cheap partition pruning on the month encoded in the filename.
            if start_ms is not None or end_ms is not None:
                m_start = pd.Timestamp(path.stem + "-01", tz="UTC")
                m_end = m_start + pd.offsets.MonthEnd(1) + pd.Timedelta(days=1)
                if start_ms is not None and m_end.value // 10**6 < start_ms:
                    continue
                if end_ms is not None and m_start.value // 10**6 > end_ms:
                    continue
            frames.append(pd.read_parquet(path))

        if not frames:
            return schemas.normalise(pd.DataFrame(columns=cols), dataset)

        out = schemas.normalise(pd.concat(frames, ignore_index=True), dataset)
        if start_ms is not None:
            out = out[out["ts"] >= start_ms]
        if end_ms is not None:
            out = out[out["ts"] <= end_ms]
        out = out.reset_index(drop=True)
        if columns is not None:
            keep = [c for c in columns if c in out.columns]
            out = out[keep]
        return out

    def read_indexed(self, *args, **kwargs) -> pd.DataFrame:
        """`read()` with a UTC DatetimeIndex attached — the form research code wants."""
        return schemas.to_datetime_index(self.read(*args, **kwargs))

    # --------------------------------------------------------------- querying
    def sql(self, query: str):
        """Run DuckDB SQL over the lake.

        Inside the query, reference data with `lake('dataset','venue','SYMBOL')`;
        it is rewritten to the matching parquet glob. Example:

            catalog.sql("SELECT count(*) FROM lake('klines','binance','BTCUSDT')")
        """
        import re

        import duckdb

        def _repl(m: re.Match) -> str:
            ds, venue, sym = (g.strip().strip("'\"") for g in m.groups())
            glob = self.dir_for(ds, venue, sym) / "*.parquet"
            return f"read_parquet('{glob}')"

        rewritten = re.sub(
            r"lake\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)", _repl, query, flags=re.IGNORECASE
        )
        con = duckdb.connect()
        try:
            return con.execute(rewritten).fetchdf()
        finally:
            con.close()

    # ------------------------------------------------------------- inventory
    def inventory(self) -> pd.DataFrame:
        """What is actually on disk: rows, byte size and covered range per symbol."""
        rows = []
        for path in sorted(self.root.rglob("*.parquet")):
            rel = path.relative_to(self.root)
            if len(rel.parts) != 4:
                continue
            dataset, venue, symbol, fname = rel.parts
            try:
                df = pd.read_parquet(path, columns=["ts"])
            except Exception:  # pragma: no cover - corrupted partition
                continue
            rows.append(
                {
                    "dataset": dataset,
                    "venue": venue,
                    "symbol": symbol,
                    "month": Path(fname).stem,
                    "rows": len(df),
                    "start": pd.Timestamp(int(df["ts"].min()), unit="ms", tz="UTC") if len(df) else pd.NaT,
                    "end": pd.Timestamp(int(df["ts"].max()), unit="ms", tz="UTC") if len(df) else pd.NaT,
                    "mb": round(path.stat().st_size / 1e6, 3),
                }
            )
        return pd.DataFrame(rows)

    def drop(self, dataset: str, venue: str, symbol: str) -> None:
        d = self.dir_for(dataset, venue, symbol)
        if d.exists():
            shutil.rmtree(d)


def _to_ms(value: str | pd.Timestamp | int) -> int:
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return int(value)
    ts = pd.Timestamp(value)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    return int(ts.value // 10**6)
