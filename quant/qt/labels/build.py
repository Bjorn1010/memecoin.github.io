"""End-to-end label construction: bars -> events -> labels -> sample weights."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..bars.filters import cusum_events, daily_volatility
from .triple_barrier import drop_rare_labels, triple_barrier_labels
from .weights import build_sample_weights


@dataclass
class LabelSpec:
    """Every choice that defines what the model is being asked to predict.

    These are the knobs that matter most and that are easiest to overfit by trying
    dozens of combinations, so they are grouped into one object that gets recorded
    alongside every backtest — a result is meaningless without the label definition
    that produced it.
    """

    horizon_bars: int = 24  # vertical barrier
    pt_sl: tuple[float, float] = (2.0, 1.0)  # profit / stop in units of volatility
    vol_span: int = 100  # EWMA span of the volatility estimate
    vol_horizon: str = "1D"  # window the volatility is measured over
    cusum_multiplier: float = 1.0  # event filter threshold, in units of volatility
    min_target: float = 0.0005  # ignore events where vol is degenerate
    zero_on_vertical: bool = False
    use_return_attribution: bool = True
    decay_last_weight: float = 1.0

    def to_meta(self) -> dict:
        return {
            "horizon_bars": self.horizon_bars,
            "pt_sl": list(self.pt_sl),
            "vol_span": self.vol_span,
            "vol_horizon": self.vol_horizon,
            "cusum_multiplier": self.cusum_multiplier,
            "min_target": self.min_target,
            "zero_on_vertical": self.zero_on_vertical,
        }


@dataclass
class LabelSet:
    events: pd.DataFrame  # t1, target, side, ret, bin
    weights: pd.DataFrame  # uniqueness, attribution, decay, weight
    volatility: pd.Series
    spec: LabelSpec

    @property
    def y(self) -> pd.Series:
        return self.events["bin"]

    @property
    def w(self) -> pd.Series:
        return self.weights["weight"]

    def summary(self) -> dict:
        counts = self.events["bin"].value_counts().to_dict()
        return {
            "n_events": int(len(self.events)),
            "class_counts": {int(k): int(v) for k, v in counts.items()},
            "mean_ret": float(self.events["ret"].mean()) if len(self.events) else float("nan"),
            "mean_uniqueness": float(self.weights["uniqueness"].mean()) if len(self.weights) else float("nan"),
            "avg_hold_bars": float(
                pd.Series(self.events["t1"].to_numpy() - self.events.index.to_numpy()).dt.total_seconds().mean()
                / 3600.0
            )
            if len(self.events)
            else float("nan"),
        }


def make_labels(
    bars: pd.DataFrame,
    spec: LabelSpec | None = None,
    *,
    side: pd.Series | None = None,
    events: pd.DatetimeIndex | None = None,
) -> LabelSet:
    """Build the label set for one instrument.

    * `side=None` -> a direction model (labels -1/0/+1).
    * `side=<series of +1/-1>` -> meta-labelling: the labels become "was that call
      right" (0/1), and the model's job is sizing, not direction.
    * `events=None` -> sample on CUSUM events; pass an explicit index to label
      specific timestamps instead (e.g. the entries a rule-based alpha generated).
    """
    spec = spec or LabelSpec()
    close = bars["close"].astype("float64")
    if not isinstance(close.index, pd.DatetimeIndex):
        close.index = pd.to_datetime(bars["ts"], unit="ms", utc=True)

    vol = daily_volatility(close, span=spec.vol_span, horizon=spec.vol_horizon)
    if events is None:
        threshold = (vol * spec.cusum_multiplier).fillna(vol.median())
        events = cusum_events(close, threshold)

    ev = triple_barrier_labels(
        close,
        pd.DatetimeIndex(events),
        vol,
        pt_sl=spec.pt_sl,
        horizon=spec.horizon_bars,
        min_target=spec.min_target,
        side=side,
        zero_on_vertical=spec.zero_on_vertical,
    )
    if side is None and not ev.empty:
        ev = drop_rare_labels(ev)

    weights = build_sample_weights(
        close.index,
        ev,
        close,
        use_return_attribution=spec.use_return_attribution,
        decay_last_weight=spec.decay_last_weight,
    )
    return LabelSet(ev, weights, vol, spec)


def forward_return(close: pd.Series, horizon: int = 24, vol_scaled: bool = True) -> pd.Series:
    """Plain forward return target, for regression models and for diagnostics.

    Deliberately shifted by -horizon, i.e. this IS a future-looking series by
    construction. It is a target, never a feature; anything that consumes it must
    align it the way the CV splitters in `qt.validation` do.
    """
    fwd = np.log(close).shift(-horizon) - np.log(close)
    if not vol_scaled:
        return fwd
    vol = np.log(close).diff().ewm(span=168, min_periods=48).std() * np.sqrt(horizon)
    return (fwd / vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
