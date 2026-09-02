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
    """Backward as-of join of `external` onto the bar index.

    Both key columns are forced to nanosecond resolution first. Since pandas 2 a
    DatetimeIndex carries its own unit, and the two sides here reliably disagree:
    `pd.date_range` yields microseconds while a series decoded from the lake's epoch-ms
    column yields milliseconds. `merge_asof` refuses mismatched units outright
    (MergeError, "must be the same type"), so every macro feature would have failed the
    moment real macro data met an hourly bar index. Widening to ns is lossless from
    either side.
    """
    if bars.empty or external is None or external.empty:
        return pd.DataFrame(index=bars.index)

    left = pd.DataFrame(index=bars.index).reset_index().rename(columns={bars.index.name or "index": "dt"})
    right = external.copy()
    if not isinstance(right.index, pd.DatetimeIndex):
        right.index = pd.to_datetime(right["ts"], unit="ms", utc=True)
    right = right[[c for c in columns if c in right.columns]].copy()
    right = right.sort_index().reset_index().rename(columns={right.index.name or "index": "dt"})
    right.columns = ["dt"] + [f"{prefix}_{c}" for c in right.columns[1:]]

    left["dt"] = pd.DatetimeIndex(left["dt"]).as_unit("ns")
    right["dt"] = pd.DatetimeIndex(right["dt"]).as_unit("ns")

    merged = pd.merge_asof(
        left.sort_values("dt"), right.sort_values("dt"), on="dt", direction="backward"
    )
    merged = merged.set_index("dt")
    merged.index = merged.index.as_unit(bars.index.unit)
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

        # Log returns are only defined for a strictly positive series. Several macro
        # series legitimately are not: the 10y-2y slope was negative on 551 days during
        # the 2022-23 inversion, and WTI printed -$37 on 20 April 2020. `np.log` of those
        # yields NaN and -inf without raising, which then propagates through every
        # horizon and quietly removes the series from the model. Detect rather than
        # maintain a list, so a series added later cannot reintroduce the bug.
        #
        # The naming difference is deliberate: a 0.5 point move in a yield spread is a
        # change, not a return, and calling it `_ret_` would invite it to be compared
        # against equity returns as if the units matched.
        positive = bool((level.dropna() > 0).all()) and not level.dropna().empty
        kind = "ret" if positive else "chg"
        base_level = np.log(level) if positive else level

        # Multi-horizon changes. On an hourly bar index against a daily series these
        # are step functions, which is correct: the information only updates daily.
        for h, label in ((24, "1d"), (120, "5d"), (480, "20d")):
            feat[f"{name}_{kind}_{label}"] = base_level.diff(h)
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
