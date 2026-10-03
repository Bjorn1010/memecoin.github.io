"""Monte Carlo on the trade list: the distribution a backtest is one draw from.

A deterministic backtest reports the drawdown that happened to occur. The trades could
have arrived in another order, a few could have been missed, costs could have been
higher, each trade's outcome is itself noisy. Each path here applies all of that at
once:

* resample the trades with replacement (order and composition);
* drop a share of them (missed signals, platform down);
* multiply costs by a random factor in the configured range;
* add noise to each trade's gross result.

Outputs are distributions — CAGR, max drawdown, Sharpe, longest recovery, longest
losing streak — and the probability of crossing given drawdown levels ("ruin" is
defined by the caller: 25 % for the research gate, the prop firm's limit elsewhere).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def trade_monte_carlo(
    trades: pd.DataFrame,
    *,
    years: float,
    n_paths: int = 2000,
    seed: int = 0,
    cost_range: tuple[float, float] = (1.0, 1.5),
    drop_rate: float = 0.10,
    noise_sd_fraction: float = 0.25,
    ruin_levels: tuple[float, ...] = (0.10, 0.20, 0.25, 0.35, 0.50),
) -> dict:
    if trades is None or len(trades) < 10 or years <= 0:
        return {"n_paths": 0}
    rng = np.random.default_rng(seed)
    gross = trades["gross"].to_numpy(dtype="float64")
    cost = trades["cost"].to_numpy(dtype="float64")
    n = len(gross)
    sd = gross.std(ddof=1) * noise_sd_fraction
    cagr, mdd, shp, rec, streak = [], [], [], [], []
    hits = {lvl: 0 for lvl in ruin_levels}
    for _ in range(n_paths):
        pick = rng.integers(n, size=n)
        keep = rng.random(n) >= drop_rate
        g = gross[pick][keep] + rng.normal(0.0, sd, keep.sum())
        c = cost[pick][keep] * rng.uniform(*cost_range)
        net = g - c
        if len(net) < 2:
            continue
        eq = np.cumprod(1 + net)
        if eq[-1] <= 0:
            eq = np.maximum(eq, 1e-9)
        peak = np.maximum.accumulate(eq)
        dd = eq / peak - 1
        m = dd.min()
        mdd.append(m)
        cagr.append(eq[-1] ** (1 / years) - 1)
        tpy = len(net) / years
        shp.append(net.mean() / net.std(ddof=1) * np.sqrt(tpy) if net.std(ddof=1) > 0 else np.nan)
        under = dd < -1e-12
        runs = np.diff(np.flatnonzero(np.concatenate([[True], ~under, [True]]))) - 1
        rec.append(int(runs.max()) if len(runs) else 0)
        best = cur = 0
        for x in net:
            cur = cur + 1 if x < 0 else 0
            best = max(best, cur)
        streak.append(best)
        for lvl in ruin_levels:
            if m <= -lvl:
                hits[lvl] += 1
    k = len(mdd)

    def q(x):
        a = np.asarray(x, dtype="float64")
        return {p: float(np.nanquantile(a, p)) for p in (0.05, 0.25, 0.5, 0.75, 0.95)}

    return {
        "n_paths": k,
        "cagr": q(cagr),
        "max_drawdown": q(mdd),
        "sharpe_trade_based": q(shp),
        "recovery_trades": q(rec),
        "losing_streak": q(streak),
        "prob_drawdown_beyond": {f"{int(l * 100)}%": hits[l] / k for l in ruin_levels} if k else {},
        "prob_loss": float(np.mean(np.asarray(cagr) < 0)) if k else float("nan"),
    }


def block_monte_carlo(returns: pd.Series, *, ppy: int, n_paths: int = 2000, block: int = 21, seed: int = 0,
                      ruin_levels: tuple[float, ...] = (0.10, 0.20, 0.25, 0.35, 0.50)) -> dict:
    """For portfolio strategies without discrete trades: block bootstrap of daily returns."""
    r = returns.dropna().to_numpy()
    n = len(r)
    if n < block * 4:
        return {"n_paths": 0}
    rng = np.random.default_rng(seed)
    years = n / ppy
    mdd, cagr = [], []
    hits = {lvl: 0 for lvl in ruin_levels}
    nb = int(np.ceil(n / block))
    for _ in range(n_paths):
        starts = rng.integers(0, n - block, nb)
        path = np.concatenate([r[s:s + block] for s in starts])[:n]
        eq = np.cumprod(1 + path)
        m = (eq / np.maximum.accumulate(eq) - 1).min()
        mdd.append(m)
        cagr.append(max(eq[-1], 1e-9) ** (1 / years) - 1)
        for lvl in ruin_levels:
            if m <= -lvl:
                hits[lvl] += 1
    q = lambda x: {p: float(np.quantile(x, p)) for p in (0.05, 0.25, 0.5, 0.75, 0.95)}  # noqa: E731
    return {"n_paths": n_paths, "cagr": q(cagr), "max_drawdown": q(mdd),
            "prob_drawdown_beyond": {f"{int(l * 100)}%": hits[l] / n_paths for l in ruin_levels},
            "prob_loss": float(np.mean(np.asarray(cagr) < 0))}
