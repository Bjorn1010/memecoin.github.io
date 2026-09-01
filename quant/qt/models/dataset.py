"""Assembling (X, y, weights, t1) — the object every model and every splitter needs.

Alignment is the whole job here, and it is where silent errors live. The contract:

* `X.index == y.index == w.index == t1.index`, all event timestamps;
* row t of X contains only information available at t (guaranteed upstream by
  `features.assert_causal`);
* `t1[t]` is when that row's label is resolved — the splitters need it to purge, and
  the backtester needs it to know when the position closes.

`FeatureCleaner` handles the value-dependent filtering (constant columns, duplicates,
absurd outliers) that must be *fitted on the training fold only*. Doing it on the full
matrix — the default in most notebooks — leaks information about the test period into
the feature set, which is subtle, invisible, and enough to flip a conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..labels.build import LabelSet


@dataclass
class Dataset:
    X: pd.DataFrame
    y: pd.Series
    w: pd.Series
    t1: pd.Series
    ret: pd.Series
    symbol: str = ""
    meta: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.X)

    def subset(self, idx) -> "Dataset":
        return Dataset(
            self.X.iloc[idx],
            self.y.iloc[idx],
            self.w.iloc[idx],
            self.t1.iloc[idx],
            self.ret.iloc[idx],
            self.symbol,
            dict(self.meta),
        )

    def summary(self) -> dict:
        return {
            "symbol": self.symbol,
            "n_samples": len(self.X),
            "n_features": self.X.shape[1],
            "start": str(self.X.index.min()) if len(self.X) else None,
            "end": str(self.X.index.max()) if len(self.X) else None,
            "class_balance": {int(k): int(v) for k, v in self.y.value_counts().items()},
            **self.meta,
        }


def build_dataset(features: pd.DataFrame, labels: LabelSet, symbol: str = "") -> Dataset:
    """Intersect a feature matrix with a label set on their common timestamps."""
    events = labels.events
    common = features.index.intersection(events.index)
    if len(common) == 0:
        empty_x = features.iloc[0:0]
        empty_s = pd.Series(dtype="float64")
        return Dataset(empty_x, empty_s, empty_s, empty_s, empty_s, symbol)

    X = features.loc[common]
    y = events.loc[common, "bin"]
    w = labels.weights.loc[common, "weight"].fillna(1.0)
    t1 = events.loc[common, "t1"]
    ret = events.loc[common, "ret"]
    return Dataset(X, y, w, t1, ret, symbol, {"label_spec": labels.spec.to_meta()})


def stack_datasets(datasets: dict[str, Dataset]) -> Dataset:
    """Pool several instruments into one panel dataset.

    Pooling is usually the right call: ten instruments give ten times the events, and
    a factor that only works on one symbol is far more likely to be noise than a
    discovery. The instrument identity is deliberately NOT added as a feature — that
    would let the model memorise per-symbol quirks instead of learning the mechanism.
    """
    usable = {s: d for s, d in datasets.items() if len(d) > 0}
    if not usable:
        empty = pd.DataFrame()
        es = pd.Series(dtype="float64")
        return Dataset(empty, es, es, es, es, "panel")

    common_cols = sorted(set.intersection(*(set(d.X.columns) for d in usable.values())))
    Xs, ys, ws, t1s, rets, syms = [], [], [], [], [], []
    for symbol, d in usable.items():
        Xs.append(d.X[common_cols])
        ys.append(d.y)
        ws.append(d.w)
        t1s.append(d.t1)
        rets.append(d.ret)
        syms.append(pd.Series(symbol, index=d.X.index))

    X = pd.concat(Xs)
    order = np.argsort(X.index.to_numpy(), kind="mergesort")  # chronological, stable
    X = X.iloc[order]
    out = Dataset(
        X,
        pd.concat(ys).iloc[order],
        pd.concat(ws).iloc[order],
        pd.concat(t1s).iloc[order],
        pd.concat(rets).iloc[order],
        "panel",
        {"symbols": sorted(usable), "n_symbols": len(usable)},
    )
    out.meta["symbol_of_row"] = pd.concat(syms).iloc[order]
    return out


@dataclass
class FeatureCleaner:
    """Value-dependent feature filtering, fitted on training data only."""

    max_nan_frac: float = 0.3
    min_unique: int = 2
    corr_threshold: float | None = 0.995
    winsorise_quantile: float | None = 0.001

    keep_: list[str] = field(default_factory=list)
    medians_: pd.Series | None = None
    lower_: pd.Series | None = None
    upper_: pd.Series | None = None

    def fit(self, X: pd.DataFrame) -> "FeatureCleaner":
        Xc = X.replace([np.inf, -np.inf], np.nan)
        keep = Xc.columns[Xc.isna().mean() <= self.max_nan_frac]
        Xc = Xc[keep]
        nunique = Xc.nunique(dropna=True)
        keep = nunique[nunique >= self.min_unique].index
        Xc = Xc[keep]

        if self.corr_threshold is not None and Xc.shape[1] > 1:
            corr = Xc.corr().abs()
            upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
            drop = [c for c in upper.columns if (upper[c] > self.corr_threshold).any()]
            Xc = Xc.drop(columns=drop)

        self.keep_ = list(Xc.columns)
        self.medians_ = Xc.median()
        if self.winsorise_quantile:
            q = self.winsorise_quantile
            self.lower_ = Xc.quantile(q)
            self.upper_ = Xc.quantile(1 - q)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self.keep_:
            raise RuntimeError("FeatureCleaner used before fit()")
        missing = [c for c in self.keep_ if c not in X.columns]
        if missing:
            raise KeyError(f"features missing at transform time: {missing[:10]}")
        out = X[self.keep_].replace([np.inf, -np.inf], np.nan)
        if self.lower_ is not None and self.upper_ is not None:
            # Clip to the TRAINING distribution's tails. A live outlier beyond
            # anything ever seen in training gets pinned to the edge rather than
            # driving the model into a region it has no evidence about.
            out = out.clip(lower=self.lower_, upper=self.upper_, axis=1)
        return out.fillna(self.medians_)

    def fit_transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return self.fit(X).transform(X)
