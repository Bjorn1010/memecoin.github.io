"""Was the best strategy of the cycle better than zero, or only the best of many?

White's Reality Check (2000) and Hansen's Superior Predictive Ability test (2005) both
answer that question for a *set* of strategies tested on the same data: they bootstrap
the whole matrix of return streams together, so the correlation between strategies and
the act of picking the maximum are both inside the null distribution.

SPA studentises each strategy and drops hopeless ones from the recentring, which makes
it less conservative than the Reality Check when the set contains many poor strategies
— exactly the situation of a retail-strategy screen. Both are reported.

The deflated Sharpe ratio and PBO live in qt.validation.statistics and are reused.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def stationary_bootstrap_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano stationary bootstrap: blocks of geometric length, wrapping."""
    p = 1.0 / max(mean_block, 1.0)
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    new_block = rng.random(n) < p
    starts = rng.integers(n, size=n)
    for t in range(1, n):
        idx[t] = starts[t] if new_block[t] else (idx[t - 1] + 1) % n
    return idx


def reality_check_spa(
    returns: pd.DataFrame,
    benchmark: pd.Series | None = None,
    *,
    n_boot: int = 1000,
    mean_block: float = 10.0,
    seed: int = 0,
) -> dict:
    """p-values of White's RC and Hansen's SPA (consistent version) against `benchmark`
    (zero — staying flat — by default)."""
    X = returns.fillna(0.0).to_numpy(dtype="float64")
    if benchmark is not None:
        X = X - benchmark.reindex(returns.index).fillna(0.0).to_numpy()[:, None]
    n, k = X.shape
    if n < 50 or k < 1:
        return {"rc_pvalue": float("nan"), "spa_pvalue": float("nan"), "n_models": k, "n_obs": n}
    rng = np.random.default_rng(seed)
    mean = X.mean(axis=0)
    boot_means = np.empty((n_boot, k))
    for b in range(n_boot):
        idx = stationary_bootstrap_indices(n, mean_block, rng)
        boot_means[b] = X[idx].mean(axis=0)

    sqn = np.sqrt(n)
    # Reality Check: non-studentised, recentred on the sample mean.
    v = np.max(sqn * mean)
    v_star = np.max(sqn * (boot_means - mean), axis=1)
    rc_p = float((v_star >= v).mean())

    # SPA: studentised; models far below zero are not recentred (Hansen's g_c).
    omega = np.sqrt(n) * boot_means.std(axis=0, ddof=1)
    omega = np.where(omega > 0, omega, np.nan)
    t_stat = sqn * mean / omega
    T = max(np.nanmax(t_stat), 0.0)
    threshold = -np.sqrt(2 * np.log(np.log(n)))
    g = np.where(t_stat >= threshold, mean, 0.0)
    z_star = sqn * (boot_means - g) / omega
    t_star = np.maximum(np.nanmax(z_star, axis=1), 0.0)
    spa_p = float((t_star >= T).mean())
    best = int(np.nanargmax(t_stat))
    return {
        "rc_pvalue": rc_p,
        "spa_pvalue": spa_p,
        "n_models": int(k),
        "n_obs": int(n),
        "best_model": str(returns.columns[best]),
        "best_t_stat": float(t_stat[best]),
    }
