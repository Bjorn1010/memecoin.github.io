"""Price, return and momentum features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import log_returns, register, rolling_rank, safe_div, zscore

# Horizons in bars. On 1h bars these span 1 hour to ~1 month, which brackets the
# horizons at which momentum and reversal are documented to coexist with opposite
# signs — short-term reversal, medium-term momentum, long-term reversal.
RETURN_HORIZONS = (1, 2, 4, 8, 12, 24, 48, 72, 168, 336, 720)
MA_WINDOWS = (8, 24, 72, 168, 336, 720)


@register("ret", description="Log returns over multiple horizons", warmup=720, tags=("price", "core"))
def returns(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"].astype("float64")
    log_close = np.log(close)
    out = {}
    for h in RETURN_HORIZONS:
        out[f"h{h}"] = log_close.diff(h)
    # Scale each horizon by its own realised vol: a 1% move is a different event at
    # 20% annualised than at 120%, and unscaled returns make a model relearn that
    # from scratch in every regime.
    r1 = log_close.diff()
    vol = r1.ewm(span=168, min_periods=24).std()
    for h in (1, 4, 24, 72):
        out[f"h{h}_vol_adj"] = safe_div(out[f"h{h}"], vol * np.sqrt(h))
    return pd.DataFrame(out, index=bars.index)


@register("mom", description="Momentum, trend position and rank", warmup=720, tags=("price", "core"))
def momentum(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"].astype("float64")
    out = {}
    for w in MA_WINDOWS:
        ma = close.rolling(w, min_periods=max(w // 4, 3)).mean()
        out[f"px_over_ma{w}"] = safe_div(close, ma) - 1.0
        out[f"ma{w}_slope"] = safe_div(ma.diff(max(w // 4, 1)), ma)
    # Classic dual-horizon trend agreement: fast above slow, normalised by price.
    fast = close.ewm(span=24, min_periods=8).mean()
    slow = close.ewm(span=168, min_periods=48).mean()
    out["ema_fast_slow"] = safe_div(fast - slow, close)
    # Time-series momentum sign consistency: fraction of the last N bars that were up.
    r = log_returns(close)
    for w in (24, 72, 168):
        out[f"up_ratio_{w}"] = (r > 0).rolling(w, min_periods=max(w // 4, 3)).mean()
    for w in (168, 720):
        out[f"rank_{w}"] = rolling_rank(close, w)
    return pd.DataFrame(out, index=bars.index)


@register("range", description="Position inside recent ranges and drawdown state", warmup=720, tags=("price",))
def range_state(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"].astype("float64")
    high = bars["high"].astype("float64")
    low = bars["low"].astype("float64")
    out = {}
    for w in (24, 72, 168, 720):
        hh = high.rolling(w, min_periods=max(w // 4, 3)).max()
        ll = low.rolling(w, min_periods=max(w // 4, 3)).min()
        out[f"pos_{w}"] = safe_div(close - ll, hh - ll)  # 0 at range low, 1 at range high
        out[f"width_{w}"] = safe_div(hh - ll, close)
        out[f"dist_high_{w}"] = safe_div(close, hh) - 1.0
        out[f"dist_low_{w}"] = safe_div(close, ll) - 1.0
    # Running drawdown from the trailing peak — a state variable, not a return.
    peak = close.cummax()
    out["drawdown"] = safe_div(close, peak) - 1.0
    for w in (168, 720):
        rpeak = close.rolling(w, min_periods=max(w // 4, 3)).max()
        out[f"drawdown_{w}"] = safe_div(close, rpeak) - 1.0
    # Candle geometry of the latest bar: where it closed inside its own range, and
    # how much of the bar was body vs wick (exhaustion vs continuation).
    rng = (high - low).replace(0.0, np.nan)
    out["close_in_bar"] = safe_div(close - low, rng)
    out["body_ratio"] = safe_div((close - bars["open"].astype("float64")).abs(), rng)
    out["upper_wick"] = safe_div(high - np.maximum(close, bars["open"]), rng)
    out["lower_wick"] = safe_div(np.minimum(close, bars["open"]) - low, rng)
    return pd.DataFrame(out, index=bars.index)


@register("rev", description="Short-horizon reversal and overextension", warmup=336, tags=("price",))
def reversal(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"].astype("float64")
    r = log_returns(close)
    out = {}
    for w in (12, 24, 72, 168):
        out[f"z_{w}"] = zscore(close, w)
        out[f"ret_z_{w}"] = zscore(r.rolling(w, min_periods=max(w // 4, 3)).sum(), w)
    # Consecutive same-signed bars — a streak is the crudest and most durable
    # reversal signal there is.
    sign = np.sign(r).fillna(0.0)
    streak = sign.groupby((sign != sign.shift()).cumsum()).cumcount() + 1
    out["streak"] = (streak * sign).astype("float64")
    # Distance from VWAP, when the bar carries the volume needed to compute it.
    if "vwap" in bars.columns:
        out["px_over_vwap"] = safe_div(close, bars["vwap"].astype("float64")) - 1.0
        for w in (24, 168):
            anchored = safe_div(
                bars["quote_volume"].rolling(w, min_periods=3).sum()
                if "quote_volume" in bars.columns
                else close.rolling(w, min_periods=3).sum(),
                bars["volume"].rolling(w, min_periods=3).sum()
                if "volume" in bars.columns
                else pd.Series(1.0, index=bars.index),
            )
            out[f"px_over_vwap{w}"] = safe_div(close, anchored) - 1.0
    return pd.DataFrame(out, index=bars.index)
