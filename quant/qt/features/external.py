"""External context: macro, implied volatility and perpetual funding.

Joining lower-frequency external series onto an intraday bar index is where
look-ahead sneaks in most easily, so there is exactly one join primitive here and it
is strictly backward: a bar at time t sees the last external observation whose
timestamp is <= t, and never the one that is about to print. Daily series are stamped
at 23:59:59 UTC of their session (see sources/stooq.py), so today's close cannot
contaminate today's intraday bars.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import safe_div, zscore


def asof_join(bars: pd.DataFrame, external: pd.DataFrame, prefix: str, columns=("close",)) -> pd.DataFrame:
    """Backward as-of join of `external` onto the bar index."""
    if bars.empty or external is None or external.empty:
        return pd.DataFrame(index=bars.index)

    left = pd.DataFrame(index=bars.index).reset_index().rename(columns={bars.index.name or "index": "dt"})
    right = external.copy()
    if not isinstance(right.index, pd.DatetimeIndex):
        right.index = pd.to_datetime(right["ts"], unit="ms", utc=True)
    right = right[[c for c in columns if c in right.columns]].copy()
    right = right.sort_index().reset_index().rename(columns={right.index.name or "index": "dt"})
    right.columns = ["dt"] + [f"{prefix}_{c}" for c in right.columns[1:]]

    merged = pd.merge_asof(
        left.sort_values("dt"), right.sort_values("dt"), on="dt", direction="backward"
    )
    merged = merged.set_index("dt")
    merged.index.name = bars.index.name
    return merged.reindex(bars.index)


def macro_features(bars: pd.DataFrame, series: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Derive features from a dict of external daily/hourly series.

    `series` maps a short name (e.g. "spx", "vix", "dvol") to a frame with a `close`
    column. Levels are never used raw — they are non-stationary and a model will
    happily learn "2021 was bullish". Only returns, z-scores and spreads survive.
    """
    if bars.empty or not series:
        return pd.DataFrame(index=bars.index)

    frames = []
    for name, ext in series.items():
        joined = asof_join(bars, ext, name, columns=("close",))
        col = f"{name}_close"
        if col not in joined.columns:
            continue
        level = joined[col].astype("float64")
        feat = pd.DataFrame(index=bars.index)
        # Multi-horizon changes. On an hourly bar index against a daily series these
        # are step functions, which is correct: the information only updates daily.
        for h, label in ((24, "1d"), (120, "5d"), (480, "20d")):
            feat[f"{name}_ret_{label}"] = np.log(level).diff(h)
        feat[f"{name}_z"] = zscore(level, 720)
        feat[f"{name}_pct"] = level.rolling(2160, min_periods=240).rank(pct=True)
        frames.append(feat)

    if not frames:
        return pd.DataFrame(index=bars.index)
    out = pd.concat(frames, axis=1)

    # Implied-minus-realised vol spread: the volatility risk premium. Positive and
    # wide means options are expensive relative to what the market actually delivers,
    # which historically favours short-vol and, for a directional book, holding risk.
    if "dvol" in series:
        dvol = asof_join(bars, series["dvol"], "dvol", columns=("close",))["dvol_close"].astype("float64")
        realised = np.log(bars["close"].astype("float64")).diff().rolling(168, min_periods=48).std(
            ddof=0
        ) * np.sqrt(365 * 24) * 100
        out["vrp"] = dvol - realised
        out["vrp_z"] = zscore(out["vrp"], 720)
    return out


def funding_features(bars: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    """Features from realised perpetual funding prints.

    Funding is the cleanest positioning gauge that exists in crypto: it is the price
    longs pay shorts to keep the perp pinned to spot. Persistently high funding means
    the long side is crowded and paying for the privilege, which is both a carry cost
    for a long position and a well-documented precursor to liquidation cascades.
    """
    if bars.empty or funding is None or funding.empty:
        return pd.DataFrame(index=bars.index)

    joined = asof_join(bars, funding, "fund", columns=("rate",))
    rate = joined.get("fund_rate")
    if rate is None:
        return pd.DataFrame(index=bars.index)
    rate = rate.astype("float64")

    out = pd.DataFrame(index=bars.index)
    out["funding_rate"] = rate
    # Annualised: 3 payments a day on Binance.
    out["funding_annual"] = rate * 3 * 365
    for w in (24, 72, 168, 720):
        out[f"funding_mean_{w}"] = rate.rolling(w, min_periods=max(w // 8, 2)).mean()
    out["funding_z"] = zscore(rate, 720)
    out["funding_pct"] = rate.rolling(2160, min_periods=240).rank(pct=True)
    # Sign flips are informative on their own — the moment the crowd switches side.
    out["funding_flip"] = (np.sign(rate) != np.sign(rate.shift(1))).astype("float64")
    # Carry-adjusted momentum: a rally that costs 100% annualised to hold is not the
    # same trade as the same rally with funding at zero.
    ret_24 = np.log(bars["close"].astype("float64")).diff(24)
    out["carry_adj_mom"] = ret_24 - out["funding_mean_24"].fillna(0.0) * 3
    return out
