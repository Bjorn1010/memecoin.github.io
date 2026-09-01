"""Feature pipeline: from bars (plus context) to a model-ready matrix.

Responsibilities, in order:

1. compute every registered time-series feature group;
2. attach cross-sectional features from the panel, if one is supplied;
3. attach external context (macro, implied vol) and perpetual funding;
4. drop the warm-up region where features are not yet defined;
5. drop degenerate columns (all-NaN, constant, or near-duplicate) — a constant column
   is free capacity for a model to overfit on and adds nothing;
6. record the exact column list and a hash of it, so that a model can refuse to score
   a matrix whose schema has drifted from the one it was trained on.

Point 6 matters more than it sounds. Silent feature-order or feature-set drift between
training and inference is one of the most common production failures in ML trading and
it is completely invisible: the model keeps returning confident numbers, they are just
about a different universe.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import base, cross_sectional, external
from . import microstructure, price, regime, statistical, technical, volatility  # noqa: F401  (registers groups)


@dataclass
class FeatureMatrix:
    """A feature matrix together with everything needed to reproduce it."""

    X: pd.DataFrame
    symbol: str
    groups: tuple[str, ...]
    schema_hash: str
    dropped: tuple[str, ...] = field(default_factory=tuple)

    @property
    def columns(self) -> list[str]:
        return list(self.X.columns)

    def to_meta(self) -> dict:
        return {
            "symbol": self.symbol,
            "groups": list(self.groups),
            "schema_hash": self.schema_hash,
            "n_features": self.X.shape[1],
            "n_rows": self.X.shape[0],
            "columns": list(self.X.columns),
        }


def schema_hash(columns) -> str:
    payload = json.dumps(sorted(map(str, columns))).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def drop_unavailable(X: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Drop columns that are structurally unavailable, and nothing else.

    A column that is entirely NaN means the feature cannot be computed for this
    instrument at all (the venue does not publish the input). Removing it is a
    statement about data availability, not about the data's content, so it is safe to
    decide on the whole sample.

    Anything that depends on the *values* — near-constant columns, correlated pairs,
    low-variance filters — is deliberately NOT done here. Those decisions look at the
    target period and must be fitted on the training slice only; see
    `models.dataset.FeatureCleaner`.
    """
    out = X.replace([np.inf, -np.inf], np.nan)
    empty = out.columns[out.isna().all()].tolist()
    return out.drop(columns=empty), empty


def build_features(
    bars: pd.DataFrame,
    *,
    symbol: str = "",
    groups=None,
    panel_features: pd.DataFrame | None = None,
    macro: dict[str, pd.DataFrame] | None = None,
    funding: pd.DataFrame | None = None,
    do_clean: bool = True,
) -> FeatureMatrix:
    """Assemble the full feature matrix for one instrument."""
    if bars.empty:
        return FeatureMatrix(pd.DataFrame(), symbol, tuple(), schema_hash([]))

    if not isinstance(bars.index, pd.DatetimeIndex):
        bars = bars.copy()
        bars.index = pd.to_datetime(bars["ts"], unit="ms", utc=True)
        bars.index.name = "dt"

    used_groups = tuple(groups) if groups is not None else tuple(sorted(base.registry()))
    parts = [base.build(bars, used_groups, drop_warmup=False)]

    if panel_features is not None and not panel_features.empty:
        parts.append(panel_features.reindex(bars.index))
    if macro:
        parts.append(external.macro_features(bars, macro))
    if funding is not None and not funding.empty:
        parts.append(external.funding_features(bars, funding))

    X = pd.concat([p for p in parts if p is not None and not p.empty], axis=1)
    X = X.loc[:, ~X.columns.duplicated()]

    # Drop the warm-up region: rows before the longest feature is defined.
    warmup = max((g.warmup for n, g in base.registry().items() if n in used_groups), default=0)
    if warmup:
        X = X.iloc[warmup:]

    dropped: list[str] = []
    if do_clean:
        X, dropped = drop_unavailable(X)

    return FeatureMatrix(X, symbol, used_groups, schema_hash(X.columns), tuple(dropped))


def build_panel(
    panel: dict[str, pd.DataFrame],
    *,
    groups=None,
    macro: dict[str, pd.DataFrame] | None = None,
    funding: dict[str, pd.DataFrame] | None = None,
    with_cross_sectional: bool = True,
) -> dict[str, FeatureMatrix]:
    """Build feature matrices for a whole universe, sharing cross-sectional context.

    Returned matrices are *not* forced onto a common column set: an instrument whose
    venue lacks aggressor data legitimately has fewer features. Aligning them is the
    caller's job (see models.dataset), and doing it explicitly is what stops a silent
    column mismatch at training time.
    """
    xs = cross_sectional.build_panel_features(panel) if with_cross_sectional else {}
    out: dict[str, FeatureMatrix] = {}
    for symbol, bars in panel.items():
        out[symbol] = build_features(
            bars,
            symbol=symbol,
            groups=groups,
            panel_features=xs.get(symbol),
            macro=macro,
            funding=(funding or {}).get(symbol),
        )
    return out


def align_columns(matrices: dict[str, FeatureMatrix]) -> dict[str, FeatureMatrix]:
    """Restrict every matrix to the intersection of their columns, in a stable order."""
    if not matrices:
        return {}
    common = set.intersection(*(set(m.columns) for m in matrices.values()))
    ordered = sorted(common)
    out = {}
    for symbol, m in matrices.items():
        out[symbol] = FeatureMatrix(m.X[ordered], symbol, m.groups, schema_hash(ordered), m.dropped)
    return out
