"""Event filters — deciding *when* the model is allowed to have an opinion.

A model that is asked for a prediction on every single bar spends most of its
capacity learning noise, because most bars carry no news. The CUSUM filter samples
only bars where cumulative return since the last event has run far enough to be
unlikely under the recent volatility. Downstream, the model trains and predicts on
those events alone: fewer, cleaner, more balanced observations.

The filter is one-sided-symmetric: it fires on a run up OR a run down, and resets the
relevant accumulator on each fire, so it does not fire repeatedly on one move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cusum_events(prices: pd.Series, threshold: float | pd.Series) -> pd.DatetimeIndex:
    """Symmetric CUSUM filter on log prices.

    `threshold` may be a scalar or a per-timestamp series (pass a rolling volatility
    estimate to make the filter regime-adaptive — the usual choice).
    Returns the index positions at which an event fires.
    """
    if prices.empty:
        return pd.DatetimeIndex([])

    log_p = np.log(prices.astype("float64"))
    diff = log_p.diff().fillna(0.0)

    if isinstance(threshold, pd.Series):
        thr = threshold.reindex(prices.index).ffill()
    else:
        thr = pd.Series(float(threshold), index=prices.index)

    events = []
    s_pos = 0.0
    s_neg = 0.0
    values = diff.to_numpy()
    thresholds = thr.to_numpy()
    for i in range(1, values.size):
        h = thresholds[i]
        if not np.isfinite(h) or h <= 0:
            continue
        s_pos = max(0.0, s_pos + values[i])
        s_neg = min(0.0, s_neg + values[i])
        if s_pos > h:
            s_pos = 0.0
            events.append(prices.index[i])
        elif s_neg < -h:
            s_neg = 0.0
            events.append(prices.index[i])

    return pd.DatetimeIndex(events)


def daily_volatility(prices: pd.Series, span: int = 100, horizon: str = "1D") -> pd.Series:
    """EWMA volatility of returns measured over `horizon`, aligned to the bar index.

    This is the standard scale for both CUSUM thresholds and triple-barrier widths:
    a 2% move means something very different in a 15%-vol regime than in a 90%-vol
    one, and barriers set in absolute terms silently change meaning over time.
    """
    if prices.empty:
        return pd.Series(dtype="float64")

    idx = prices.index
    # For each bar, find the bar closest to `horizon` earlier.
    shifted = idx - pd.Timedelta(horizon)
    pos = idx.searchsorted(shifted, side="right") - 1
    valid = pos >= 0
    ret = pd.Series(np.nan, index=idx, dtype="float64")
    if valid.any():
        prev_prices = prices.to_numpy()[pos[valid]]
        ret.iloc[np.flatnonzero(valid)] = prices.to_numpy()[valid] / prev_prices - 1.0
    return ret.ewm(span=span, min_periods=max(span // 4, 2)).std()


def sample_on_events(df: pd.DataFrame, events: pd.DatetimeIndex) -> pd.DataFrame:
    """Restrict a feature frame to event timestamps, keeping alignment intact."""
    if len(events) == 0:
        return df.iloc[0:0]
    return df.loc[df.index.intersection(events)]
