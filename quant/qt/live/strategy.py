"""Strategies for the live loop.

A strategy's only job is to turn bar history into a conviction in [-1, 1]. It does not
size, does not know the equity, and cannot place an order. Sizing belongs to
`risk.sizing`, permission belongs to `risk.limits`, and execution belongs to the
broker — so a bug in a strategy can produce a wrong opinion but never an oversized or
unauthorised position.

Both implementations compute their signal from *exactly* the same feature code the
research pipeline uses. That is the entire reason `features` is a library rather than a
notebook: train-serve skew, where the live feature differs subtly from the trained one,
is invisible from the outside and reliably destroys live performance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd

from .. import alphas as A
from .. import features as F
from ..models.model import QuantModel


class Strategy(Protocol):
    name: str
    warmup_bars: int

    def signal(self, bars: pd.DataFrame, symbol: str) -> float: ...

    def diagnostics(self) -> dict: ...


@dataclass
class AlphaEnsembleStrategy:
    """Rule-based ensemble. No training, no model file, no staleness."""

    name: str = "alpha_ensemble"
    warmup_bars: int = 1000
    alpha_names: tuple[str, ...] | None = None
    weights: dict[str, float] | None = None  # fixed weights; equal if None
    feature_groups: tuple[str, ...] | None = None
    _last: dict = field(default_factory=dict)

    def signal(self, bars: pd.DataFrame, symbol: str) -> float:
        if len(bars) < self.warmup_bars:
            self._last = {"reason": f"warming up ({len(bars)}/{self.warmup_bars} bars)"}
            return 0.0

        fm = F.build_features(bars, symbol=symbol, groups=self.feature_groups)
        if fm.X.empty:
            self._last = {"reason": "no features"}
            return 0.0

        sig = A.compute_all(bars, fm.X, self.alpha_names, warn_missing=False)
        if sig.empty:
            return 0.0
        latest = sig.iloc[-1].dropna()
        if latest.empty:
            self._last = {"reason": "all alphas NaN on latest bar"}
            return 0.0

        if self.weights:
            w = pd.Series({k: self.weights.get(k, 0.0) for k in latest.index})
            total = w.abs().sum()
            combined = float((latest * w).sum() / total) if total > 0 else 0.0
        else:
            combined = float(latest.mean())

        self._last = {
            "contributions": {k: round(float(v), 4) for k, v in latest.items()},
            "combined": combined,
            "n_alphas": int(len(latest)),
        }
        return float(np.clip(combined, -1.0, 1.0))

    def diagnostics(self) -> dict:
        return dict(self._last)


@dataclass
class ModelStrategy:
    """Scores the latest bar with a trained model from the registry.

    Refuses to produce a signal when the live feature matrix does not carry every
    feature the model was trained on. Returning 0.0 and saying why is strictly better
    than scoring a matrix with silently median-imputed columns, which is what an
    unchecked pipeline would do.
    """

    model: QuantModel
    name: str = "model"
    warmup_bars: int = 1000
    feature_groups: tuple[str, ...] | None = None
    threshold: float = 0.0  # ignore edges smaller than this
    _last: dict = field(default_factory=dict)

    def signal(self, bars: pd.DataFrame, symbol: str) -> float:
        if len(bars) < self.warmup_bars:
            self._last = {"reason": f"warming up ({len(bars)}/{self.warmup_bars} bars)"}
            return 0.0

        fm = F.build_features(bars, symbol=symbol, groups=self.feature_groups)
        if fm.X.empty:
            self._last = {"reason": "no features"}
            return 0.0

        expected = list(self.model.meta.get("features", []))
        missing = [c for c in expected if c not in fm.X.columns]
        if missing:
            self._last = {
                "reason": "feature schema mismatch — refusing to score",
                "missing": missing[:10],
                "n_missing": len(missing),
            }
            return 0.0

        row = fm.X.iloc[[-1]]
        edge = float(self.model.edge(row).iloc[0])
        proba = self.model.predict_proba(row).iloc[0].to_dict()
        self._last = {
            "edge": edge,
            "probabilities": {int(k): round(float(v), 4) for k, v in proba.items()},
            "model_trained_to": self.model.meta.get("train_end"),
        }
        if abs(edge) < self.threshold:
            return 0.0
        return float(np.clip(edge, -1.0, 1.0))

    def diagnostics(self) -> dict:
        return dict(self._last)


@dataclass
class FlatStrategy:
    """Always flat. The control group, and the thing to switch to when unsure."""

    name: str = "flat"
    warmup_bars: int = 0

    def signal(self, bars: pd.DataFrame, symbol: str) -> float:
        return 0.0

    def diagnostics(self) -> dict:
        return {"reason": "flat by construction"}
