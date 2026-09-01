"""Feature importance that survives scrutiny.

The importance number a boosted-tree library prints by default (MDI — how often a
feature was split on, weighted by gain) is computed in-sample and is biased toward
high-cardinality, noisy features: a column of random numbers will happily rank in the
top ten because there are many places to split it. It is fine for a rough look and
dangerous for feature selection.

**MDA** (mean decrease accuracy) is the honest measure: fit on the training fold,
score on the purged test fold, then shuffle one feature at a time in the *test* fold
and measure how much the score degrades. A feature whose destruction costs nothing was
contributing nothing, in the only sample that counts. It is ~n_features times slower,
which is why it is opt-in per feature subset.

**Clustered MDA** handles the case that makes plain MDA lie: when two features carry
the same information, shuffling either one alone changes nothing (the model leans on
its twin), so both look useless. Shuffling correlated groups together fixes it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

from ..validation.cv import PurgedKFold
from .dataset import Dataset
from .model import ModelSpec, QuantModel


def mdi_importance(model: QuantModel) -> pd.Series:
    """In-sample split-gain importance. Fast, biased — use for orientation only."""
    est = model.estimator
    booster = getattr(est, "feature_importances_", None)
    if booster is None:
        return pd.Series(dtype="float64")
    names = model.meta.get("features", [])
    s = pd.Series(booster, index=names[: len(booster)], dtype="float64")
    total = s.sum()
    return (s / total).sort_values(ascending=False) if total > 0 else s


def mda_importance(
    ds: Dataset,
    spec: ModelSpec | None = None,
    *,
    n_splits: int = 4,
    embargo_pct: float = 0.02,
    n_repeats: int = 3,
    features: list[str] | None = None,
    random_state: int = 0,
) -> pd.DataFrame:
    """Mean decrease accuracy on purged out-of-fold data.

    Returns mean/std of the score degradation per feature, in negative log-loss units.
    A feature with a mean at or below zero is not helping; a std comparable to the mean
    means the "help" is one lucky fold.
    """
    spec = spec or ModelSpec(calibrate=False)
    rng = np.random.default_rng(random_state)
    cv = PurgedKFold(n_splits=n_splits, t1=ds.t1, embargo_pct=embargo_pct)
    cols = features or list(ds.X.columns)

    scores: dict[str, list[float]] = {c: [] for c in cols}
    baselines: list[float] = []

    for train_idx, test_idx in cv.split(ds.X):
        train, test = ds.subset(train_idx), ds.subset(test_idx)
        if len(train) < 50 or train.y.nunique() < 2 or test.y.nunique() < 2:
            continue
        model = QuantModel(
            ModelSpec(kind=spec.kind, params=dict(spec.params), calibrate=False, random_state=spec.random_state)
        ).fit(train)
        labels = sorted(set(train.y.unique()) | set(test.y.unique()))
        base_proba = model.predict_proba(test.X)
        base = -log_loss(test.y, _align(base_proba, labels), labels=labels, sample_weight=test.w)
        baselines.append(base)

        for col in cols:
            if col not in test.X.columns:
                continue
            degradations = []
            for _ in range(n_repeats):
                shuffled = test.X.copy()
                shuffled[col] = rng.permutation(shuffled[col].to_numpy())
                proba = model.predict_proba(shuffled)
                score = -log_loss(test.y, _align(proba, labels), labels=labels, sample_weight=test.w)
                degradations.append(base - score)
            scores[col].append(float(np.mean(degradations)))

    rows = []
    for col, vals in scores.items():
        if not vals:
            continue
        arr = np.asarray(vals, dtype="float64")
        rows.append(
            {
                "feature": col,
                "mda_mean": float(arr.mean()),
                "mda_std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
                "n_folds": int(arr.size),
                # t-statistic across folds: is the improvement consistent, or one fold?
                "t_stat": float(arr.mean() / (arr.std(ddof=1) / np.sqrt(arr.size)))
                if arr.size > 1 and arr.std(ddof=1) > 0
                else np.nan,
            }
        )
    out = pd.DataFrame(rows).sort_values("mda_mean", ascending=False).reset_index(drop=True)
    out.attrs["baseline_score"] = float(np.mean(baselines)) if baselines else np.nan
    return out


def cluster_features(X: pd.DataFrame, threshold: float = 0.7) -> dict[int, list[str]]:
    """Group features by correlation, so redundant ones can be tested together."""
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    corr = X.corr().abs().fillna(0.0)
    distance = 1.0 - corr
    np.fill_diagonal(distance.values, 0.0)
    # Enforce exact symmetry: floating-point noise in corr() breaks squareform.
    distance = (distance + distance.T) / 2.0
    link = linkage(squareform(distance.to_numpy(), checks=False), method="average")
    labels = fcluster(link, t=1.0 - threshold, criterion="distance")
    out: dict[int, list[str]] = {}
    for col, lab in zip(X.columns, labels):
        out.setdefault(int(lab), []).append(col)
    return out


def clustered_mda(
    ds: Dataset,
    spec: ModelSpec | None = None,
    *,
    corr_threshold: float = 0.7,
    n_splits: int = 4,
    embargo_pct: float = 0.02,
    random_state: int = 0,
) -> pd.DataFrame:
    """MDA over correlated clusters instead of individual features."""
    spec = spec or ModelSpec(calibrate=False)
    clusters = cluster_features(ds.X, corr_threshold)
    rng = np.random.default_rng(random_state)
    cv = PurgedKFold(n_splits=n_splits, t1=ds.t1, embargo_pct=embargo_pct)

    scores: dict[int, list[float]] = {c: [] for c in clusters}
    for train_idx, test_idx in cv.split(ds.X):
        train, test = ds.subset(train_idx), ds.subset(test_idx)
        if len(train) < 50 or train.y.nunique() < 2 or test.y.nunique() < 2:
            continue
        model = QuantModel(
            ModelSpec(kind=spec.kind, params=dict(spec.params), calibrate=False, random_state=spec.random_state)
        ).fit(train)
        labels = sorted(set(train.y.unique()) | set(test.y.unique()))
        base = -log_loss(
            test.y, _align(model.predict_proba(test.X), labels), labels=labels, sample_weight=test.w
        )
        for cid, members in clusters.items():
            present = [m for m in members if m in test.X.columns]
            if not present:
                continue
            shuffled = test.X.copy()
            perm = rng.permutation(len(shuffled))
            for m in present:
                shuffled[m] = shuffled[m].to_numpy()[perm]
            score = -log_loss(
                test.y, _align(model.predict_proba(shuffled), labels), labels=labels, sample_weight=test.w
            )
            scores[cid].append(base - score)

    rows = []
    for cid, vals in scores.items():
        if not vals:
            continue
        arr = np.asarray(vals)
        rows.append(
            {
                "cluster": cid,
                "size": len(clusters[cid]),
                "members": ", ".join(clusters[cid][:6]) + ("..." if len(clusters[cid]) > 6 else ""),
                "mda_mean": float(arr.mean()),
                "mda_std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("mda_mean", ascending=False).reset_index(drop=True)


def _align(proba: pd.DataFrame, labels: list) -> np.ndarray:
    """Reindex a probability frame onto a fixed label order, filling absent classes."""
    out = proba.reindex(columns=labels, fill_value=0.0)
    total = out.sum(axis=1).replace(0.0, np.nan)
    out = out.div(total, axis=0).fillna(1.0 / max(len(labels), 1))
    return out.to_numpy()
