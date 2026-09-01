"""Feature registry and the causality guarantee.

The single most expensive bug in quantitative research is look-ahead: a feature that,
somewhere in its computation, touches a value from the future. It never raises an
error; it just produces a beautiful backtest that loses money live.

This module makes causality structural rather than a matter of care:

* every feature is a registered function `(bars) -> DataFrame` indexed identically to
  its input;
* `assert_causal` recomputes a feature on truncated history and requires the
  overlapping values to match bit-for-bit. Any use of future data — `center=True`,
  a negative shift, a full-sample mean, a fit on the whole series — changes the
  earlier values and fails the check;
* the test suite runs that check over the entire registry, so a feature added later
  cannot quietly break the property.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np
import pandas as pd

FeatureFn = Callable[[pd.DataFrame], pd.DataFrame]

_REGISTRY: dict[str, "FeatureGroup"] = {}


@dataclass(frozen=True)
class FeatureGroup:
    name: str
    fn: FeatureFn
    description: str = ""
    # Bars of history the group needs before its outputs are trustworthy.
    warmup: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __call__(self, bars: pd.DataFrame) -> pd.DataFrame:
        return self.fn(bars)


def register(
    name: str, *, description: str = "", warmup: int = 0, tags: Iterable[str] = ()
) -> Callable[[FeatureFn], FeatureFn]:
    def deco(fn: FeatureFn) -> FeatureFn:
        if name in _REGISTRY:
            raise ValueError(f"feature group {name!r} already registered")
        _REGISTRY[name] = FeatureGroup(name, fn, description or (fn.__doc__ or "").strip(), warmup, tuple(tags))
        return fn

    return deco


def registry() -> dict[str, FeatureGroup]:
    return dict(_REGISTRY)


def group_names(tags: Iterable[str] | None = None) -> list[str]:
    if not tags:
        return sorted(_REGISTRY)
    wanted = set(tags)
    return sorted(n for n, g in _REGISTRY.items() if wanted & set(g.tags))


def build(
    bars: pd.DataFrame,
    groups: Iterable[str] | None = None,
    *,
    drop_warmup: bool = True,
) -> pd.DataFrame:
    """Compute the requested feature groups and concatenate them.

    `bars` must be indexed by UTC timestamp (bar close) and carry at least
    open/high/low/close/volume. Optional columns (quote_volume, trades, buy_volume,
    sell_volume) unlock the microstructure groups; those degrade to NaN when absent
    rather than raising, so the same pipeline runs on venues with poorer data.
    """
    if bars.empty:
        return pd.DataFrame(index=bars.index)

    names = list(groups) if groups is not None else sorted(_REGISTRY)
    frames: list[pd.DataFrame] = []
    warmup = 0
    for name in names:
        grp = _REGISTRY.get(name)
        if grp is None:
            raise KeyError(f"unknown feature group {name!r}; known: {sorted(_REGISTRY)}")
        out = grp(bars)
        if out is None or out.empty:
            continue
        out = out.reindex(bars.index)
        # Prefix unconditionally. A "only prefix if not already prefixed" shortcut
        # makes the final column name depend on whether the inner name happens to
        # start with the group name, which silently produces two naming conventions
        # in one matrix — and a downstream lookup that misses is not an error, just a
        # feature that is quietly always NaN.
        out.columns = [f"{name}_{c}" for c in out.columns]
        frames.append(out)
        warmup = max(warmup, grp.warmup)

    if not frames:
        return pd.DataFrame(index=bars.index)

    feats = pd.concat(frames, axis=1)
    feats = feats.replace([np.inf, -np.inf], np.nan)
    if drop_warmup and warmup > 0:
        feats = feats.iloc[warmup:]
    return feats


def assert_causal(bars: pd.DataFrame, groups: Iterable[str] | None = None, cut: float = 0.7) -> None:
    """Raise if any feature changes when future bars are removed.

    Recomputes on the first `cut` fraction of the sample and compares against the
    same rows of the full-sample computation.
    """
    n = len(bars)
    k = max(int(n * cut), 10)
    full = build(bars, groups, drop_warmup=False)
    part = build(bars.iloc[:k], groups, drop_warmup=False)
    shared_cols = [c for c in part.columns if c in full.columns]
    a = full.loc[part.index, shared_cols]
    b = part[shared_cols]
    diff = ~(
        np.isclose(a.to_numpy(dtype="float64"), b.to_numpy(dtype="float64"), equal_nan=True, rtol=1e-9, atol=1e-12)
    )
    if diff.any():
        bad = sorted({shared_cols[j] for _, j in zip(*np.where(diff))})
        raise AssertionError(f"look-ahead detected in features: {bad[:20]}")


# --------------------------------------------------------------------------
# shared numeric helpers used across feature modules
# --------------------------------------------------------------------------
def safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    out = a / b.replace(0.0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def zscore(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """Rolling z-score. Causal by construction (trailing window only)."""
    mp = min_periods or max(window // 4, 3)
    mean = series.rolling(window, min_periods=mp).mean()
    std = series.rolling(window, min_periods=mp).std(ddof=0)
    return safe_div(series - mean, std)


def rolling_rank(series: pd.Series, window: int) -> pd.Series:
    """Where the latest value sits inside its own trailing distribution, in [0, 1].

    Scale-free and robust to the fat tails that wreck z-scores in crypto.
    """
    return series.rolling(window, min_periods=max(window // 4, 3)).apply(
        lambda x: (x[-1] > x[:-1]).mean() if x.size > 1 else np.nan, raw=True
    )


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close.astype("float64")).diff()
