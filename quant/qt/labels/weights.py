"""Sample weights for overlapping labels.

Standard supervised learning assumes observations are IID. Financial labels are not
even close: a label at 10:00 spanning the next 24 hours shares 23 of those hours with
the label at 11:00. Treating them as independent inflates the effective sample size by
an order of magnitude, which is precisely why models look significant in-sample and
evaporate out of it — the significance was borrowed from data counted many times over.

Three corrections, all from López de Prado ch. 4, applied together:

* **Uniqueness** — weight each label by the inverse of how many other labels were live
  at the same time. Overlapping labels get down-weighted toward the information they
  actually add.
* **Return attribution** — weight by the magnitude of the return earned over the
  label's life, spread across its span. A label that resolved with a 5% move carries
  more information than one that drifted 0.05%.
* **Time decay** — optionally decay older samples, since market structure is
  non-stationary and 2019 is a weaker guide to today than last month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def num_concurrent_events(bar_index: pd.DatetimeIndex, t1: pd.Series) -> pd.Series:
    """For each bar, how many labels are simultaneously live."""
    if t1.empty:
        return pd.Series(0.0, index=bar_index)
    t1 = t1.dropna()
    starts = bar_index.searchsorted(t1.index, side="left")
    ends = bar_index.searchsorted(t1.to_numpy(), side="right")
    counts = np.zeros(len(bar_index) + 1, dtype="float64")
    np.add.at(counts, starts, 1.0)
    np.add.at(counts, np.minimum(ends, len(bar_index)), -1.0)
    return pd.Series(np.cumsum(counts[:-1]), index=bar_index)


def average_uniqueness(bar_index: pd.DatetimeIndex, t1: pd.Series) -> pd.Series:
    """Mean of 1/concurrency over each label's lifetime, in (0, 1]."""
    if t1.empty:
        return pd.Series(dtype="float64")
    conc = num_concurrent_events(bar_index, t1).replace(0.0, np.nan)
    inv = 1.0 / conc
    cum = np.concatenate([[0.0], np.nancumsum(inv.to_numpy())])
    starts = bar_index.searchsorted(t1.index, side="left")
    ends = np.minimum(bar_index.searchsorted(t1.to_numpy(), side="right"), len(bar_index))
    span = np.maximum(ends - starts, 1)
    return pd.Series((cum[ends] - cum[starts]) / span, index=t1.index).clip(0.0, 1.0)


def return_attribution_weights(
    bar_index: pd.DatetimeIndex, t1: pd.Series, close: pd.Series
) -> pd.Series:
    """Weight by |sum of concurrency-adjusted log returns| over each label's life."""
    if t1.empty:
        return pd.Series(dtype="float64")
    conc = num_concurrent_events(bar_index, t1).replace(0.0, np.nan)
    log_ret = np.log(close.reindex(bar_index).astype("float64")).diff().fillna(0.0)
    adjusted = (log_ret / conc).fillna(0.0)
    cum = np.concatenate([[0.0], np.cumsum(adjusted.to_numpy())])
    starts = bar_index.searchsorted(t1.index, side="left")
    ends = np.minimum(bar_index.searchsorted(t1.to_numpy(), side="right"), len(bar_index))
    w = np.abs(cum[ends] - cum[starts])
    out = pd.Series(w, index=t1.index)
    total = out.sum()
    # Normalise to mean 1 so that weighting never silently rescales the loss function.
    return out * (len(out) / total) if total > 0 else pd.Series(1.0, index=t1.index)


def time_decay(uniqueness: pd.Series, last_weight: float = 0.5) -> pd.Series:
    """Linear decay in cumulative uniqueness, oldest sample -> `last_weight`.

    `last_weight` in (0, 1] fades old data; 1.0 disables decay; a negative value
    erases the oldest portion of the sample entirely.
    """
    if uniqueness.empty:
        return uniqueness
    cum = uniqueness.sort_index().cumsum()
    total = cum.iloc[-1]
    if total <= 0:
        return pd.Series(1.0, index=uniqueness.index)
    if last_weight >= 0:
        slope = (1.0 - last_weight) / total
    else:
        slope = 1.0 / ((last_weight + 1) * total)
    const = 1.0 - slope * total
    decay = const + slope * cum
    decay[decay < 0] = 0.0
    return decay.reindex(uniqueness.index)


def build_sample_weights(
    bar_index: pd.DatetimeIndex,
    events: pd.DataFrame,
    close: pd.Series,
    *,
    use_return_attribution: bool = True,
    decay_last_weight: float = 1.0,
) -> pd.DataFrame:
    """Combine the three corrections into one weight per label.

    Returns a frame with the individual components alongside the final `weight`, so
    that a surprising training result can be traced back to which correction caused it.
    """
    if events.empty:
        return pd.DataFrame(columns=["uniqueness", "attribution", "decay", "weight"])

    t1 = events["t1"].dropna()
    uniq = average_uniqueness(bar_index, t1)
    attribution = (
        return_attribution_weights(bar_index, t1, close)
        if use_return_attribution
        else pd.Series(1.0, index=t1.index)
    )
    decay = time_decay(uniq, decay_last_weight) if decay_last_weight != 1.0 else pd.Series(1.0, index=uniq.index)

    weight = (uniq * attribution * decay).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    total = weight.sum()
    if total > 0:
        weight = weight * (len(weight) / total)  # mean 1

    return pd.DataFrame(
        {"uniqueness": uniq, "attribution": attribution, "decay": decay, "weight": weight}
    ).reindex(events.index)
