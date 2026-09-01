"""Alpha protocol: an independent, testable opinion about the future.

An *alpha* here is a function from (bars, features) to a signal series in [-1, 1],
where the sign is the direction and the magnitude is conviction. Deliberately not a
strategy: an alpha does not know about position sizing, costs, or the rest of the
portfolio. Those belong to the risk engine and the backtester, and keeping them out
means every alpha is comparable to every other on exactly the same footing.

Why keep a library of explicit, hand-written alphas at all when there is an ML model?
Three reasons that matter:

1. **They are interpretable priors.** A boosted tree on 250 features will find
   *something*; whether that something is momentum, a calendar artefact or a
   data-vendor quirk is not obvious from the model. A momentum alpha with a known
   economic rationale is a benchmark the model has to beat.
2. **They are the primary model in meta-labelling.** The ML layer works best when it
   is asked "should I take this specific trade" rather than "what will the market do".
3. **They degrade gracefully.** When the model's feature schema breaks or its
   training window goes stale, a rule still produces a defensible signal.

Every alpha declares the *rationale* it rests on. An alpha with no rationale beyond
"it backtested well" is a data-mining result, and it is labelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np
import pandas as pd

SignalFn = Callable[[pd.DataFrame, pd.DataFrame], pd.Series]

_ALPHAS: dict[str, "Alpha"] = {}


@dataclass(frozen=True)
class Alpha:
    name: str
    fn: SignalFn
    family: str  # momentum | reversion | breakout | carry | flow | volatility | seasonal
    rationale: str  # WHY this should work, in economic terms
    horizon_bars: int = 24
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __call__(self, bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
        # Features are warm-up trimmed and so are shorter than bars. Aligning here,
        # once, means every alpha can mix the two freely without each one having to
        # remember to reindex — a mismatch that otherwise surfaces as a cryptic
        # comparison error deep inside one signal.
        bars_aligned, features_aligned = align(bars, features)
        sig = self.fn(bars_aligned, features_aligned)
        if sig is None:
            return pd.Series(0.0, index=features_aligned.index, name=self.name)
        return sig.reindex(features_aligned.index).clip(-1, 1).rename(self.name)


def register_alpha(
    name: str, *, family: str, rationale: str, horizon_bars: int = 24, tags: Iterable[str] = ()
) -> Callable[[SignalFn], SignalFn]:
    def deco(fn: SignalFn) -> SignalFn:
        if name in _ALPHAS:
            raise ValueError(f"alpha {name!r} already registered")
        _ALPHAS[name] = Alpha(name, fn, family, rationale, horizon_bars, tuple(tags))
        return fn

    return deco


def registry() -> dict[str, Alpha]:
    return dict(_ALPHAS)


def by_family(family: str) -> list[Alpha]:
    return [a for a in _ALPHAS.values() if a.family == family]


def align(bars: pd.DataFrame, features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Restrict both frames to their common timestamps, in order."""
    common = bars.index.intersection(features.index)
    return bars.loc[common], features.loc[common]


def compute_all(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    names: Iterable[str] | None = None,
    *,
    warn_missing: bool = True,
) -> pd.DataFrame:
    """Run every alpha and return a timestamp x alpha signal matrix."""
    selected = list(names) if names is not None else sorted(_ALPHAS)
    _, features_aligned = align(bars, features)
    reset_missing_features()
    cols = {}
    for name in selected:
        alpha = _ALPHAS.get(name)
        if alpha is None:
            raise KeyError(f"unknown alpha {name!r}; known: {sorted(_ALPHAS)}")
        cols[name] = alpha(bars, features)

    if warn_missing and _MISSING:
        import warnings

        warnings.warn(
            "alphas requested features not present in the matrix, and are running "
            f"degraded: {sorted(_MISSING)}. Supply the missing feature groups "
            "(panel/macro/funding context) or expect those alphas to be flat.",
            RuntimeWarning,
            stacklevel=2,
        )

    if not cols:
        return pd.DataFrame(index=features_aligned.index)
    return pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan)


def describe() -> pd.DataFrame:
    rows = [
        {
            "name": a.name,
            "family": a.family,
            "horizon_bars": a.horizon_bars,
            "rationale": a.rationale,
            "tags": ", ".join(a.tags),
        }
        for a in _ALPHAS.values()
    ]
    return pd.DataFrame(rows).sort_values(["family", "name"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# shared shaping helpers
# --------------------------------------------------------------------------
def squash(series: pd.Series, scale: float = 1.0) -> pd.Series:
    """Map an unbounded score to [-1, 1] smoothly.

    tanh rather than clipping: a signal three standard deviations out is stronger than
    one at two, but not three times as strong, and clipping throws that ordering away.
    """
    return np.tanh(series.astype("float64") / max(scale, 1e-9))


_MISSING: set[str] = set()


def feature_col(features: pd.DataFrame, name: str, default: float = np.nan) -> pd.Series:
    """Fetch a feature column, returning a NaN series when the group is unavailable.

    Missing lookups are recorded rather than swallowed. An alpha silently reduced to a
    constant zero because a feature was renamed is indistinguishable from an alpha with
    no edge — a class of bug that will otherwise sit in the codebase for months.
    """
    if name in features.columns:
        return features[name].astype("float64")
    _MISSING.add(name)
    return pd.Series(default, index=features.index, dtype="float64")


def missing_features() -> set[str]:
    """Feature names alphas asked for and did not find, since the last reset."""
    return set(_MISSING)


def reset_missing_features() -> None:
    _MISSING.clear()


def gate(signal: pd.Series, condition: pd.Series, *, weight_when_false: float = 0.0) -> pd.Series:
    """Scale a signal down where `condition` is false — a regime filter.

    Most alphas are regime-conditional; expressing that as an explicit gate keeps the
    condition visible and testable instead of buried inside the signal's arithmetic.
    """
    cond = condition.reindex(signal.index).fillna(False).astype(bool)
    return signal.where(cond, signal * weight_when_false)
