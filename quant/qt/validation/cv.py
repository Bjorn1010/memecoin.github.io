"""Cross-validation that does not leak.

Plain K-fold on financial data is worse than useless — it is actively misleading.
Two mechanisms:

* **Overlap.** A label at 10:00 covering the next 24 hours overlaps labels at 11:00,
  12:00, and so on. Put 10:00 in the training fold and 11:00 in the test fold, and the
  model has already seen most of the answer.
* **Serial correlation.** Even without overlap, neighbouring observations are close to
  duplicates; a random split scatters near-copies of the same information across train
  and test, so the test set is not out of sample in any meaningful sense.

The fix is purging and embargoing (López de Prado ch. 7): remove from the training set
every observation whose label lifetime overlaps the test set (purge), and additionally
drop a buffer of observations immediately after the test set (embargo), because the
features of those observations were built from windows that reach back into it.

Also here: **combinatorial purged CV**, which produces many backtest paths instead of
one. A single walk-forward path gives one Sharpe with no distribution to compare it
against; CPCV gives an empirical distribution, which is what makes it possible to ask
whether the result is distinguishable from luck.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterator, Sequence

import numpy as np
import pandas as pd


def purged_train_indices(
    t1: pd.Series,
    test_times: pd.DatetimeIndex,
    embargo_pct: float = 0.01,
) -> pd.Index:
    """Training labels that survive purging and embargo against `test_times`.

    `t1` maps each label's start time to the time its outcome is known.
    """
    if len(test_times) == 0:
        return t1.index

    test_start, test_end = test_times.min(), test_times.max()
    # Purge: a training label overlaps the test window if it starts before the test
    # ends AND resolves after the test starts.
    starts = t1.index
    ends = pd.DatetimeIndex(t1.to_numpy())
    overlaps = (starts <= test_end) & (ends >= test_start)

    # Embargo: additionally drop labels starting shortly after the test window, since
    # their features were computed from windows that reach back into it.
    embargo_span = pd.Timedelta(0)
    if embargo_pct > 0:
        total = t1.index.max() - t1.index.min()
        embargo_span = total * float(embargo_pct)
    embargoed = (starts > test_end) & (starts <= test_end + embargo_span)

    keep = ~(overlaps | embargoed)
    return t1.index[keep]


@dataclass
class PurgedKFold:
    """K contiguous test folds with purging and embargo. sklearn-splitter compatible."""

    n_splits: int = 5
    t1: pd.Series | None = None
    embargo_pct: float = 0.01

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits

    def split(self, X: pd.DataFrame, y=None, groups=None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        if self.t1 is None:
            raise ValueError("PurgedKFold needs `t1` (label end times) to purge")
        t1 = self.t1.reindex(X.index).dropna()
        if len(t1) != len(X):
            raise ValueError("t1 must cover every row of X (label end time per sample)")

        idx = np.arange(len(X))
        folds = np.array_split(idx, self.n_splits)
        for fold in folds:
            if fold.size == 0:
                continue
            test_times = X.index[fold]
            train_labels = purged_train_indices(t1, test_times, self.embargo_pct)
            train_mask = X.index.isin(train_labels)
            train_idx = idx[train_mask]
            # A fold whose training set has been purged to nothing is not usable.
            if train_idx.size == 0:
                continue
            yield train_idx, fold


@dataclass
class CombinatorialPurgedCV:
    """Combinatorial purged cross-validation (CPCV).

    Splits the sample into `n_groups` contiguous groups and tests on every combination
    of `n_test_groups` of them, purging and embargoing the rest for training. With
    N=6, k=2 that is 15 splits which reassemble into 5 complete backtest paths — an
    empirical distribution of performance rather than a single number.
    """

    n_groups: int = 6
    n_test_groups: int = 2
    t1: pd.Series | None = None
    embargo_pct: float = 0.01

    def n_paths(self) -> int:
        from math import comb

        return comb(self.n_groups - 1, self.n_test_groups - 1)

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        from math import comb

        return comb(self.n_groups, self.n_test_groups)

    def split(self, X: pd.DataFrame, y=None, groups=None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        if self.t1 is None:
            raise ValueError("CombinatorialPurgedCV needs `t1`")
        t1 = self.t1.reindex(X.index).dropna()
        idx = np.arange(len(X))
        group_idx = np.array_split(idx, self.n_groups)

        for combo in combinations(range(self.n_groups), self.n_test_groups):
            test_idx = np.sort(np.concatenate([group_idx[g] for g in combo]))
            test_times = X.index[test_idx]
            # Purge against each contiguous test block separately: the blocks may be
            # far apart, and purging against their union would delete the middle of
            # the sample for no reason.
            keep = pd.Index(t1.index)
            for g in combo:
                block_times = X.index[group_idx[g]]
                keep = keep.intersection(purged_train_indices(t1, block_times, self.embargo_pct))
            train_mask = X.index.isin(keep)
            train_idx = idx[train_mask & ~np.isin(idx, test_idx)]
            if train_idx.size == 0:
                continue
            yield train_idx, test_idx


def walk_forward_splits(
    index: pd.DatetimeIndex,
    train_size: int,
    test_size: int,
    *,
    step: int | None = None,
    anchored: bool = False,
    embargo: int = 0,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Classic walk-forward: train on a window, test on the block right after it.

    `anchored=True` grows the training window from the start of the sample (more data,
    slower adaptation); `False` rolls a fixed window (adapts to regime change, forgets
    old regimes). `embargo` inserts a gap of that many bars between train and test.

    This is the honest simulation of how a model is actually run in production, and
    the only validation whose result maps directly onto "what would this have earned".
    """
    step = step or test_size
    n = len(index)
    out: list[tuple[np.ndarray, np.ndarray]] = []
    start = 0
    while True:
        train_end = start + train_size
        test_start = train_end + embargo
        test_end = test_start + test_size
        if test_end > n:
            break
        train_start = 0 if anchored else start
        out.append((np.arange(train_start, train_end), np.arange(test_start, test_end)))
        start += step
    return out


def train_test_time_split(
    index: pd.DatetimeIndex, split_at: str | pd.Timestamp, embargo: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """One hard chronological split, with an embargo gap.

    Kept for the final, single out-of-sample evaluation. It should be run exactly once,
    at the end: every extra look at a held-out set converts it a little more into a
    training set.
    """
    cut = pd.Timestamp(split_at, tz="UTC") if pd.Timestamp(split_at).tz is None else pd.Timestamp(split_at)
    pos = index.searchsorted(cut)
    train = np.arange(0, max(pos - embargo, 0))
    test = np.arange(pos, len(index))
    return train, test


def describe_splits(index: pd.DatetimeIndex, splits: Sequence[tuple[np.ndarray, np.ndarray]]) -> pd.DataFrame:
    """Human-readable table of what each split covers — worth eyeballing once."""
    rows = []
    for i, (tr, te) in enumerate(splits):
        rows.append(
            {
                "split": i,
                "train_n": len(tr),
                "train_start": index[tr[0]] if len(tr) else pd.NaT,
                "train_end": index[tr[-1]] if len(tr) else pd.NaT,
                "test_n": len(te),
                "test_start": index[te[0]] if len(te) else pd.NaT,
                "test_end": index[te[-1]] if len(te) else pd.NaT,
            }
        )
    return pd.DataFrame(rows)
