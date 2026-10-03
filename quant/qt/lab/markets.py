"""Market universe, cost profiles and research data loading.

Each asset class is analysed on its own. Mixing FX and crypto in one sample would let
the crypto volatility dominate every statistic and hide whatever the FX result is.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..config import CONFIG

CONFIG_DIR = CONFIG.repo_root / "configs"


@dataclass(frozen=True)
class CostProfile:
    """Per-side trading costs in bps of notional, plus annual carry on |position|."""

    commission_bps: float
    half_spread_bps: float
    slippage_bps: float
    holding_long_annual: float = 0.0
    holding_short_annual: float = 0.0
    stop_slippage_multiplier: float = 2.0

    @property
    def per_side_bps(self) -> float:
        return self.commission_bps + self.half_spread_bps + self.slippage_bps

    def scaled(self, multiplier: float = 1.0, extra_slippage_bps: float = 0.0) -> "CostProfile":
        """Stress copy: every friction multiplied, optionally plus extra slippage."""
        return CostProfile(
            commission_bps=self.commission_bps * multiplier,
            half_spread_bps=self.half_spread_bps * multiplier,
            slippage_bps=self.slippage_bps * multiplier + extra_slippage_bps,
            holding_long_annual=self.holding_long_annual * multiplier,
            holding_short_annual=self.holding_short_annual * multiplier,
            stop_slippage_multiplier=self.stop_slippage_multiplier,
        )

    def describe(self) -> str:
        return (
            f"{self.per_side_bps:.2f} bp/côté (comm {self.commission_bps}, "
            f"demi-spread {self.half_spread_bps}, slippage {self.slippage_bps}), "
            f"portage {self.holding_long_annual:.1%} long / {self.holding_short_annual:.1%} short"
        )


@dataclass(frozen=True)
class AssetClass:
    name: str
    symbols: tuple[str, ...]
    costs: CostProfile
    periods_per_year: int
    has_volume: bool
    use_adjusted: bool = False
    description: str = ""
    notes: str = ""
    roll_proxies: dict = field(default_factory=dict)
    pairs: tuple[tuple[str, str], ...] = ()
    source: str = "yahoo"


def load_markets(path: Path | None = None) -> dict[str, AssetClass]:
    raw = yaml.safe_load((path or CONFIG_DIR / "markets.yaml").read_text())
    stop_mult = float(raw.get("stop_slippage_multiplier", 2.0))
    pairs = raw.get("pairs", {}) or {}
    out: dict[str, AssetClass] = {}
    for name, spec in raw["asset_classes"].items():
        hold = spec.get("holding_cost_annual", {}) or {}
        out[name] = AssetClass(
            name=name,
            symbols=tuple(spec["symbols"]),
            costs=CostProfile(
                commission_bps=float(spec["commission_bps"]),
                half_spread_bps=float(spec["half_spread_bps"]),
                slippage_bps=float(spec["slippage_bps"]),
                holding_long_annual=float(hold.get("long", 0.0)),
                holding_short_annual=float(hold.get("short", 0.0)),
                stop_slippage_multiplier=stop_mult,
            ),
            periods_per_year=int(spec["periods_per_year"]),
            has_volume=bool(spec.get("has_volume", True)),
            use_adjusted=bool(spec.get("use_adjusted", False)),
            description=spec.get("description", ""),
            notes=spec.get("notes", ""),
            roll_proxies=dict(spec.get("roll_proxies", {}) or {}),
            pairs=tuple(tuple(p) for p in pairs.get(name, [])),
            source=spec.get("source", "yahoo"),
        )
    return out


def load_protocol(path: Path | None = None) -> dict:
    return yaml.safe_load((path or CONFIG_DIR / "research_protocol.yaml").read_text())


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# --------------------------------------------------------------------------- data


def _cache_path(symbol: str) -> Path:
    safe = symbol.replace("^", "IDX_").replace("=", "_").replace("/", "_")
    return CONFIG.data_dir / "lab" / f"{safe}.parquet"


# Yahoo stamps a daily bar with the session open in UTC. Normalising that stamp to its
# UTC date — what qt.data.sources.yahoo does — is right for US and European markets and
# wrong for FX: the FX day opens at midnight London, which is 23:00 UTC during British
# summer time, so every summer Monday bar landed on Sunday and every bar from April to
# October was dated one day early. The audit caught it as ~700 "weekend" bars per pair.
# Shifting the stamp forward by six hours before taking the date puts every market's
# session on its own trading day (US opens 13:30-14:30 UTC, Europe 07:00-08:00, Tokyo
# 00:00, crypto 00:00, FX 23:00 or 00:00) without moving any of them across a day.
_SESSION_DATE_SHIFT = pd.Timedelta(hours=6)


def _yahoo_daily_raw(symbol: str) -> pd.DataFrame:
    import json

    from ..data.http import get_text

    text = get_text(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"period1": 0, "period2": 4_102_444_800, "interval": "1d"},
        min_gap=0.4,
    )
    result = json.loads(text)["chart"]["result"][0]
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
    when = pd.to_datetime(pd.Series(stamps), unit="s", utc=True)
    frame = pd.DataFrame({
        "open": quote.get("open"), "high": quote.get("high"), "low": quote.get("low"),
        "close": quote.get("close"), "volume": quote.get("volume"),
    })
    frame["adj_close"] = adj if adj is not None else frame["close"]
    frame.index = pd.DatetimeIndex((when + _SESSION_DATE_SHIFT).dt.normalize())
    # Halted sessions come back as nulls; dropping them keeps the real gap visible.
    return frame.dropna(subset=["close"]).astype("float64")


def fetch_daily(symbol: str, *, refresh: bool = False) -> pd.DataFrame:
    """Daily OHLCV for one symbol, cached on disk. Index: UTC trading dates."""
    path = _cache_path(symbol)
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    try:
        frame = _yahoo_daily_raw(symbol)
    except (KeyError, IndexError, TypeError, ValueError):
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "adj_close"])
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    return frame


def prepare_bars(raw: pd.DataFrame, *, use_adjusted: bool) -> pd.DataFrame:
    """Clean bars for research.

    For dividend-paying ETFs the whole OHLC is scaled by adj_close / close. Ratios —
    and every signal here is built from ratios or from levels compared with recent
    levels of the same series — are unaffected by the scaling, while returns become
    total returns. The raw close is kept for anything that needs a real printed price.
    """
    df = raw.copy()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    # Repair OHLC consistency: a high below the close is a bad print, not information.
    df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
    df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
    df["raw_close"] = df["close"]
    if use_adjusted and "adj_close" in df and df["adj_close"].notna().all():
        factor = (df["adj_close"] / df["close"]).replace([np.inf, -np.inf], np.nan).ffill().fillna(1.0)
        for c in ("open", "high", "low", "close"):
            df[c] = df[c] * factor
    df["volume"] = df.get("volume", pd.Series(0.0, index=df.index)).fillna(0.0)
    return df[["open", "high", "low", "close", "volume", "raw_close"]]


def fetch_binance_daily(symbol: str, *, refresh: bool = False) -> pd.DataFrame:
    """Daily bars of a Binance spot pair: a venue one can actually trade, unlike Yahoo's
    crypto aggregate, whose daily highs and lows produced breakout Sharpe ratios of
    2.5-3.7 that vanish on Binance's own daily and hourly bars
    (scripts/verify_intraday_breakout.py)."""
    path = _cache_path(f"binance_{symbol}_1d")
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    from ..data.sources.binance_vision import klines

    k = klines(symbol, "1d", start="2017-08-17")
    if k.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "adj_close"])
    k.index = pd.DatetimeIndex((pd.to_datetime(k["ts"], unit="ms", utc=True) - pd.Timedelta(days=1)).dt.normalize())
    frame = k[["open", "high", "low", "close", "quote_volume"]].rename(columns={"quote_volume": "volume"})
    frame = frame.astype("float64")
    frame["volume"] = frame["volume"] / frame["close"]  # base units, like every other source
    frame["adj_close"] = frame["close"]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    return frame


def fetch(ac: "AssetClass", symbol: str, *, refresh: bool = False) -> pd.DataFrame:
    return fetch_binance_daily(symbol, refresh=refresh) if ac.source == "binance" else fetch_daily(symbol, refresh=refresh)


def load_class(ac: AssetClass, *, refresh: bool = False) -> dict[str, pd.DataFrame]:
    out = {}
    for s in ac.symbols:
        try:
            raw = fetch(ac, s, refresh=refresh)
        except Exception:  # noqa: BLE001 — a dead source is recorded by the audit, not fatal
            continue
        if raw is None or raw.empty:
            continue
        out[s] = prepare_bars(raw, use_adjusted=ac.use_adjusted)
    return out


def content_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes())
    return h.hexdigest()[:16]
