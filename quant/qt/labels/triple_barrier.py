"""Triple-barrier labelling.

The naive way to label financial data is "the return over the next N bars, is it
positive?". It is also close to useless, for two reasons:

1. **It ignores the path.** A trade that drops 8% before finishing +1% is labelled a
   win, but no live position would have survived to collect it — the stop, or the
   trader's nerve, would have closed it. The model learns to predict outcomes that
   cannot actually be harvested.
2. **It ignores volatility.** A fixed +1% target is a coin flip in a calm week and a
   near-certainty in a violent one, so the label means something different in every
   regime and the model spends its capacity learning the regime instead of the signal.

The triple-barrier method fixes both: from each event, set a profit-taking barrier and
a stop-loss barrier scaled to *current* volatility, plus a vertical barrier (a time
limit). The label is whichever barrier is touched first. That is exactly the outcome a
real position with a real stop would have experienced.

`meta_label` implements the second stage: given a primary model (or rule) that says
*which side* to take, the meta-model predicts only whether that particular call will
work. Separating side from size this way is what lets you keep a mediocre-but-real
primary signal and profit by sizing it correctly — and a binary "act / stand aside"
target is a far easier learning problem than a three-way direction call.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def vertical_barriers(
    index: pd.DatetimeIndex,
    events: pd.DatetimeIndex,
    horizon: pd.Timedelta | int,
) -> pd.Series:
    """Time limit for each event: the first bar at or after `event + horizon`.

    `horizon` may be a Timedelta (wall-clock) or an int (number of bars). Events whose
    horizon runs past the end of the sample get NaT and are dropped downstream — they
    are unresolved, and labelling them with whatever happened to be available at the
    end of the file is a classic subtle leak.
    """
    if len(events) == 0:
        return pd.Series(dtype="datetime64[ns, UTC]")

    if isinstance(horizon, int):
        pos = index.searchsorted(events, side="left") + horizon
        valid = pos < len(index)
        out = pd.Series(pd.NaT, index=events, dtype="datetime64[ns, UTC]")
        out.loc[events[valid]] = index[pos[valid]]
        return out

    targets = events + horizon
    pos = index.searchsorted(targets, side="left")
    valid = pos < len(index)
    out = pd.Series(pd.NaT, index=events, dtype="datetime64[ns, UTC]")
    out.loc[events[valid]] = index[pos[valid]]
    return out


def apply_barriers(
    close: pd.Series,
    events: pd.DataFrame,
    pt_sl: tuple[float, float] = (1.0, 1.0),
) -> pd.DataFrame:
    """First-touch times for the profit and stop barriers.

    `events` must carry:
        t1      vertical barrier timestamp (NaT allowed => no time limit)
        target  barrier width as a *fraction* (typically the volatility estimate)
        side    +1 long / -1 short (from the primary model; use +1 for side-agnostic)

    `pt_sl` scales the (profit, stop) barriers relative to `target`; a 0 disables that
    barrier entirely.
    """
    pt = pt_sl[0] * events["target"] if pt_sl[0] > 0 else pd.Series(np.inf, index=events.index)
    sl = -pt_sl[1] * events["target"] if pt_sl[1] > 0 else pd.Series(-np.inf, index=events.index)

    index = close.index
    prices = close.to_numpy(dtype="float64")
    starts = index.searchsorted(events.index, side="left")
    end_times = events["t1"].fillna(index[-1]).to_numpy()
    ends = np.minimum(index.searchsorted(end_times, side="right"), len(index))

    t_pt: list = []
    t_sl: list = []
    for i, (a, b) in enumerate(zip(starts, ends)):
        if b <= a:
            t_pt.append(pd.NaT)
            t_sl.append(pd.NaT)
            continue
        # Returns along the path, expressed in the direction of the position.
        path = prices[a:b] / prices[a] - 1.0
        rets = path * events["side"].iat[i]
        hit_pt = np.flatnonzero(rets > pt.iat[i])
        hit_sl = np.flatnonzero(rets < sl.iat[i])
        t_pt.append(index[a + hit_pt[0]] if hit_pt.size else pd.NaT)
        t_sl.append(index[a + hit_sl[0]] if hit_sl.size else pd.NaT)

    return pd.DataFrame(
        {
            "t1": events["t1"],
            "t_pt": pd.to_datetime(pd.Series(t_pt, index=events.index), utc=True),
            "t_sl": pd.to_datetime(pd.Series(t_sl, index=events.index), utc=True),
        }
    )


def triple_barrier_labels(
    close: pd.Series,
    events: pd.DatetimeIndex,
    target: pd.Series,
    *,
    pt_sl: tuple[float, float] = (1.0, 1.0),
    horizon: pd.Timedelta | int = 24,
    min_target: float = 0.0,
    side: pd.Series | None = None,
    zero_on_vertical: bool = False,
) -> pd.DataFrame:
    """Label events by which barrier is touched first.

    Returns a frame indexed by event time with:
        t1       when the position was closed (first barrier touched)
        target   the volatility scale used for the barriers
        side     +1/-1 direction taken
        ret      realised return of the position, direction-adjusted
        bin      the label

    With `side` given (meta-labelling) `bin` is 1 if the call made money and 0 if not.
    Without it, `bin` is +1 / -1 for the profit / stop barrier, and either the sign of
    the return or 0 for a vertical-barrier exit, depending on `zero_on_vertical`.
    """
    target = target.reindex(events).astype("float64")
    keep = target > min_target
    events = events[keep.fillna(False).to_numpy()]
    if len(events) == 0:
        return pd.DataFrame(columns=["t1", "target", "side", "ret", "bin"])

    t1 = vertical_barriers(close.index, events, horizon)
    ev = pd.DataFrame(
        {
            "t1": t1.reindex(events),
            "target": target.reindex(events),
            "side": (side.reindex(events) if side is not None else pd.Series(1.0, index=events)),
        }
    )
    ev = ev[ev["side"].notna()]
    ev = ev[ev["t1"].notna()]  # unresolved events are not labelled
    if ev.empty:
        return pd.DataFrame(columns=["t1", "target", "side", "ret", "bin"])

    touches = apply_barriers(close, ev, pt_sl)
    # First touch across all three barriers.
    ev["t1"] = touches[["t1", "t_pt", "t_sl"]].min(axis=1, skipna=True)

    px_in = close.reindex(ev.index).to_numpy()
    px_out = close.reindex(ev["t1"]).to_numpy()
    ret = (px_out / px_in - 1.0) * ev["side"].to_numpy()
    ev["ret"] = ret

    if side is not None:
        # Meta-label: did the primary model's call pay?
        ev["bin"] = (ev["ret"] > 0).astype("int64")
    else:
        touched_pt = touches["t_pt"].reindex(ev.index).notna() & (
            touches["t_pt"].reindex(ev.index) == ev["t1"]
        )
        touched_sl = touches["t_sl"].reindex(ev.index).notna() & (
            touches["t_sl"].reindex(ev.index) == ev["t1"]
        )
        label = pd.Series(0, index=ev.index, dtype="int64")
        label[touched_pt] = 1
        label[touched_sl] = -1
        if not zero_on_vertical:
            vertical = ~(touched_pt | touched_sl)
            label[vertical] = np.sign(ev.loc[vertical, "ret"]).astype("int64")
        ev["bin"] = label

    return ev[["t1", "target", "side", "ret", "bin"]]


def drop_rare_labels(events: pd.DataFrame, min_count: int = 30, min_share: float = 0.05) -> pd.DataFrame:
    """Iteratively remove label classes too rare to learn.

    A class with 12 examples in 40,000 will not be learned; it will be memorised, and
    the model's confidence on it will be pure noise.
    """
    out = events.copy()
    while True:
        counts = out["bin"].value_counts()
        if len(counts) < 3:
            break
        share = counts / counts.sum()
        weakest = share.idxmin()
        if counts[weakest] >= min_count and share[weakest] >= min_share:
            break
        out = out[out["bin"] != weakest]
    return out
