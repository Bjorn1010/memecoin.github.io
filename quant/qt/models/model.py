"""The predictive model: gradient boosting first, and honestly.

Choice of estimator, and why it is not a neural network. On tabular financial data
with a few thousand labelled events and a signal-to-noise ratio near zero, gradient-
boosted trees beat deep learning essentially always: they need no scaling, handle
missing values and monotone transforms natively, are robust to irrelevant features,
train in seconds (so the anti-overfitting machinery can actually be run), and — most
importantly — expose which features they used. A sequence model earns its place only
once there is a genuine sequential structure that bar features cannot express, and
only after the boosted baseline has been beaten honestly.

Three deliberate design points:

* **Sample weights are always applied.** Overlapping labels are not independent
  observations, and training as if they were is the fastest route to a model that
  looks brilliant and is worthless (see labels/weights.py).
* **Predictions are probabilities, and they are calibrated.** A model that says 0.8
  must be right 80% of the time, otherwise position sizing built on it is meaningless.
  Calibration is fitted on inner out-of-fold predictions, never on training fits.
* **`edge()` is the only output the rest of the system consumes** — a signed number in
  [-1, 1]. The backtester and the risk engine never see raw class probabilities, so a
  change of model type cannot silently change the meaning of a signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..validation.cv import PurgedKFold
from .dataset import Dataset, FeatureCleaner


@dataclass
class ModelSpec:
    kind: str = "lgbm"  # lgbm | logistic | random_forest
    params: dict = field(default_factory=dict)
    calibrate: bool = True
    calibration_method: str = "isotonic"
    cleaner: FeatureCleaner = field(default_factory=FeatureCleaner)
    random_state: int = 0

    def to_meta(self) -> dict:
        return {
            "kind": self.kind,
            "params": dict(self.params),
            "calibrate": self.calibrate,
            "calibration_method": self.calibration_method,
            "random_state": self.random_state,
        }


# Conservative defaults. Shallow trees, heavy regularisation, high minimum leaf size:
# with a few thousand noisy events, capacity is the enemy. These are chosen to
# underfit slightly rather than to maximise in-sample fit.
DEFAULT_LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "max_depth": 4,
    "min_child_samples": 60,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.6,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "verbosity": -1,
}


def _make_estimator(spec: ModelSpec, n_classes: int):
    params = dict(spec.params)
    if spec.kind == "lgbm":
        from lightgbm import LGBMClassifier

        merged = {**DEFAULT_LGBM_PARAMS, **params, "random_state": spec.random_state}
        if n_classes > 2:
            merged["objective"] = "multiclass"
            merged["num_class"] = n_classes
        return LGBMClassifier(**merged)
    if spec.kind == "logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        merged = {"C": 0.1, "max_iter": 2000, "random_state": spec.random_state, **params}
        return Pipeline(
            [("scale", StandardScaler()), ("clf", LogisticRegression(**merged))]
        )
    if spec.kind == "random_forest":
        from sklearn.ensemble import RandomForestClassifier

        merged = {
            "n_estimators": 400,
            "max_depth": 6,
            "min_samples_leaf": 40,
            "max_features": "sqrt",
            "n_jobs": -1,
            "random_state": spec.random_state,
            **params,
        }
        return RandomForestClassifier(**merged)
    raise ValueError(f"unknown model kind {spec.kind!r}")


class QuantModel:
    """A fitted classifier plus its cleaner, calibrator and provenance."""

    def __init__(self, spec: ModelSpec | None = None) -> None:
        self.spec = spec or ModelSpec()
        self.estimator = None
        self.cleaner: FeatureCleaner | None = None
        self.classes_: np.ndarray | None = None
        self.calibrators_: dict[int, object] = {}
        self.meta: dict = {}

    # ------------------------------------------------------------------ fit
    def fit(self, ds: Dataset, *, calibration_cv: int = 3, embargo_pct: float = 0.01) -> "QuantModel":
        if len(ds) < 50:
            raise ValueError(f"refusing to fit on {len(ds)} samples; that is noise, not a dataset")

        self.cleaner = FeatureCleaner(**{
            k: v
            for k, v in vars(self.spec.cleaner).items()
            if k in {"max_nan_frac", "min_unique", "corr_threshold", "winsorise_quantile"}
        })
        X = self.cleaner.fit_transform(ds.X)
        y = ds.y.to_numpy()
        w = ds.w.to_numpy()
        self.classes_ = np.unique(y)

        self.estimator = _make_estimator(self.spec, len(self.classes_))
        self._fit_estimator(self.estimator, X, y, w)

        if self.spec.calibrate:
            self._fit_calibration(ds, X, y, w, calibration_cv, embargo_pct)

        self.meta = {
            "n_samples": len(ds),
            "n_features": X.shape[1],
            "features": list(X.columns),
            "classes": [int(c) for c in self.classes_],
            "train_start": str(ds.X.index.min()),
            "train_end": str(ds.X.index.max()),
            "spec": self.spec.to_meta(),
        }
        return self

    def _fit_estimator(self, est, X: pd.DataFrame, y: np.ndarray, w: np.ndarray) -> None:
        try:
            est.fit(X, y, sample_weight=w)
        except TypeError:
            # sklearn Pipelines need the step-prefixed parameter name.
            est.fit(X, y, **{"clf__sample_weight": w})

    def _fit_calibration(
        self, ds: Dataset, X: pd.DataFrame, y: np.ndarray, w: np.ndarray, n_splits: int, embargo_pct: float
    ) -> None:
        """Fit per-class calibrators on purged out-of-fold predictions.

        Calibrating on in-sample fits would map an overconfident model onto an equally
        overconfident curve and change nothing. The folds are purged for exactly the
        same reason the outer CV is.
        """
        from sklearn.isotonic import IsotonicRegression
        from sklearn.linear_model import LogisticRegression

        oof = np.full((len(X), len(self.classes_)), np.nan)
        cv = PurgedKFold(n_splits=n_splits, t1=ds.t1, embargo_pct=embargo_pct)
        for train_idx, test_idx in cv.split(ds.X):
            if len(train_idx) < 30 or len(np.unique(y[train_idx])) < 2:
                continue
            est = _make_estimator(self.spec, len(self.classes_))
            self._fit_estimator(est, X.iloc[train_idx], y[train_idx], w[train_idx])
            proba = est.predict_proba(X.iloc[test_idx])
            for j, cls in enumerate(self.classes_):
                if cls in est.classes_:
                    oof[test_idx, j] = proba[:, list(est.classes_).index(cls)]

        for j, cls in enumerate(self.classes_):
            col = oof[:, j]
            mask = np.isfinite(col)
            target = (y[mask] == cls).astype(int)
            if mask.sum() < 50 or target.sum() < 5 or target.sum() == mask.sum():
                continue
            if self.spec.calibration_method == "isotonic":
                cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
                cal.fit(col[mask], target)
            else:
                cal = LogisticRegression(max_iter=1000)
                cal.fit(col[mask].reshape(-1, 1), target)
            self.calibrators_[int(cls)] = cal

    # -------------------------------------------------------------- predict
    def predict_proba(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.estimator is None or self.cleaner is None:
            raise RuntimeError("model is not fitted")
        Xc = self.cleaner.transform(X)
        raw = self.estimator.predict_proba(Xc)
        cols = list(self.estimator.classes_)
        out = pd.DataFrame(raw, index=X.index, columns=[int(c) for c in cols])

        if self.calibrators_:
            for cls, cal in self.calibrators_.items():
                if cls not in out.columns:
                    continue
                v = out[cls].to_numpy()
                out[cls] = (
                    cal.predict(v)
                    if hasattr(cal, "out_of_bounds")
                    else cal.predict_proba(v.reshape(-1, 1))[:, 1]
                )
            # Renormalise: independent per-class calibration does not preserve the
            # simplex, and downstream code assumes probabilities sum to one.
            total = out.sum(axis=1).replace(0.0, np.nan)
            out = out.div(total, axis=0).fillna(1.0 / out.shape[1])
        return out

    def edge(self, X: pd.DataFrame) -> pd.Series:
        """Signed conviction in [-1, 1].

        Direction model (classes -1/0/+1): P(up) - P(down), so 0 means genuinely no
        opinion rather than a coin flip in disguise.
        Meta model (classes 0/1): P(take the trade), rescaled to [0, 1]; the sign comes
        from the primary model, which the caller applies.
        """
        proba = self.predict_proba(X)
        if set(proba.columns) <= {0, 1}:
            return proba.get(1, pd.Series(0.0, index=X.index)).rename("edge")
        up = proba.get(1, pd.Series(0.0, index=X.index))
        down = proba.get(-1, pd.Series(0.0, index=X.index))
        return (up - down).rename("edge")


def cross_val_edges(
    ds: Dataset,
    spec: ModelSpec | None = None,
    *,
    n_splits: int = 6,
    embargo_pct: float = 0.02,
    calibrate: bool = False,
) -> pd.DataFrame:
    """Purged out-of-fold edges for the whole dataset.

    This is the only prediction series that may be fed to the backtester for an
    in-sample period: every prediction was made by a model that never saw that row,
    nor any row whose label overlapped it.

    Inner calibration is off by default here — it triples training cost and the
    quantity being measured (rank quality of the edge) is invariant to a monotone
    recalibration.
    """
    spec = spec or ModelSpec()
    cv = PurgedKFold(n_splits=n_splits, t1=ds.t1, embargo_pct=embargo_pct)

    rows = []
    for fold, (train_idx, test_idx) in enumerate(cv.split(ds.X)):
        train, test = ds.subset(train_idx), ds.subset(test_idx)
        if len(train) < 50 or train.y.nunique() < 2:
            continue
        model_spec = ModelSpec(
            kind=spec.kind,
            params=dict(spec.params),
            calibrate=calibrate,
            calibration_method=spec.calibration_method,
            random_state=spec.random_state,
        )
        model = QuantModel(model_spec).fit(train)
        edge = model.edge(test.X)
        rows.append(
            pd.DataFrame(
                {
                    "edge": edge,
                    "y": test.y,
                    "ret": test.ret,
                    "t1": test.t1,
                    "weight": test.w,
                    "fold": fold,
                }
            )
        )

    if not rows:
        return pd.DataFrame(columns=["edge", "y", "ret", "t1", "weight", "fold"])
    return pd.concat(rows).sort_index()
