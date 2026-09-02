"""Structural breaks and explosive behaviour — detecting when the rules changed.

Every model here assumes the relationship it learned still holds. That assumption fails
regularly and without warning: a listing, a regulatory change, a leverage unwind, a
protocol upgrade. A system with no break detection keeps trading a dead relationship
with full confidence, which is how a strategy goes from working to catastrophic without
passing through "slightly worse".

Three tools:

* **SADF (supremum ADF)** — Phillips, Shi & Yu's test for *explosive* behaviour, i.e.
  bubbles. It flips the usual unit-root logic: instead of testing for stationarity it
  tests for a root greater than one, and takes the supremum over expanding windows so
  it can date the start of the episode in real time. Bubbles are the one regime where
  momentum is strongest and mean reversion is most dangerous, so knowing you are in one
  is directly actionable.
* **CUSUM of squares** — detects a change in *variance* rather than in level. Volatility
  regime shifts break position sizing before they break the signal.
* **Chow test** — tests whether a regression's coefficients differ across a known
  break date. Used to check whether a fitted hedge ratio survived a specific event.

All are computed on trailing data so they can run live, not only in post-mortem.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _adf_stat(y: np.ndarray, lags: int = 1) -> float:
    """t-statistic on the lagged-level coefficient of an ADF regression.

    Written directly rather than via statsmodels because SADF calls it thousands of
    times over expanding windows, and the library's overhead dominates there.
    """
    n = y.size
    if n < lags + 10:
        return np.nan
    dy = np.diff(y)
    lagged_level = y[:-1]

    cols = [lagged_level, np.ones(lagged_level.size)]
    for k in range(1, lags + 1):
        col = np.concatenate([np.zeros(k), dy[:-k]]) if k <= dy.size else np.zeros(dy.size)
        cols.append(col[: lagged_level.size])
    design = np.column_stack(cols)

    if design.shape[0] <= design.shape[1]:
        return np.nan
    try:
        beta, residuals, rank, _ = np.linalg.lstsq(design, dy, rcond=None)
    except np.linalg.LinAlgError:
        return np.nan
    if rank < design.shape[1]:
        return np.nan

    resid = dy - design @ beta
    dof = design.shape[0] - design.shape[1]
    if dof <= 0:
        return np.nan
    sigma2 = float(resid @ resid) / dof
    try:
        xtx_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        return np.nan
    se = np.sqrt(sigma2 * xtx_inv[0, 0])
    return float(beta[0] / se) if se > 0 else np.nan


def sadf(
    series: pd.Series,
    *,
    min_window: int = 100,
    lags: int = 1,
    use_log: bool = True,
    stride: int = 1,
) -> pd.Series:
    """Supremum ADF: rolling test for explosive (bubble) dynamics.

    At each point t, the ADF statistic is computed over every backward-expanding window
    ending at t, and the supremum is taken. A *high* value is evidence of a root above
    one — an explosive, self-reinforcing move — which is the opposite of what a normal
    ADF test looks for.

    Reading it: SADF above roughly +1 to +2 marks an explosive episode. During one,
    momentum strategies do unusually well and mean-reversion strategies get run over,
    so this is a useful gate on which family of alpha is allowed to size up.
    """
    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if use_log:
        x = np.log(x[x > 0])
    values = x.to_numpy(dtype="float64")
    n = values.size

    out = np.full(n, np.nan)
    if n < min_window + 10:
        return pd.Series(out, index=x.index, name="sadf")

    for end in range(min_window, n, stride):
        best = -np.inf
        # Expanding backward windows; step coarsely, since neighbouring start points
        # give near-identical statistics and the supremum is insensitive to the grid.
        step = max((end - min_window) // 25, 1)
        for start in range(0, end - min_window + 1, step):
            stat = _adf_stat(values[start : end + 1], lags)
            if np.isfinite(stat) and stat > best:
                best = stat
        out[end] = best if np.isfinite(best) else np.nan

    result = pd.Series(out, index=x.index, name="sadf")
    return result.ffill(limit=stride - 1) if stride > 1 else result


def cusum_squares_test(residuals: pd.Series, alpha: float = 0.05) -> dict:
    """Brown-Durbin-Evans CUSUM of squares: detects a change in variance.

    The statistic walks from 0 to 1 across the sample; under stability it stays inside
    a band around the diagonal. Excursions outside mark the point where the variance
    regime changed — which usually precedes the level relationship breaking, and is
    therefore an early warning rather than a post-mortem.
    """
    r = pd.Series(residuals).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(r)
    if n < 30:
        return {"break_detected": False, "reason": "insufficient data"}

    squares = r.to_numpy() ** 2
    total = squares.sum()
    if total <= 0:
        return {"break_detected": False, "reason": "degenerate residuals"}

    cusum = np.cumsum(squares) / total
    expected = np.arange(1, n + 1) / n
    deviation = cusum - expected

    # Critical band (approximate, Edgerton-Wells): c0 / sqrt(n/2 - 1).
    c0 = {0.10: 1.224, 0.05: 1.358, 0.01: 1.628}.get(alpha, 1.358)
    band = c0 / np.sqrt(n / 2 - 1) if n > 2 else np.inf

    breaches = np.abs(deviation) > band
    idx = int(np.argmax(np.abs(deviation)))
    return {
        "break_detected": bool(breaches.any()),
        "break_index": r.index[idx] if breaches.any() else None,
        "max_deviation": float(np.abs(deviation).max()),
        "critical_band": float(band),
        "statistic": pd.Series(deviation, index=r.index, name="cusum_sq"),
        "n_breaches": int(breaches.sum()),
    }


def chow_test(y: pd.Series, x: pd.Series, break_point, alpha: float = 0.05) -> dict:
    """Chow test: did a regression's coefficients change at a known date?

    Use it when you have a specific event in mind ("did our hedge ratio survive the FTX
    collapse?"). It requires the break date to be known in advance — testing every
    possible date and keeping the most significant one is exactly the multiple-testing
    error this whole codebase is built to avoid, and SADF or CUSUM is the right tool
    when the date is unknown.
    """
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 40:
        return {"break_detected": False, "reason": "insufficient data"}

    bp = pd.Timestamp(break_point) if not isinstance(break_point, pd.Timestamp) else break_point
    if bp.tzinfo is None and getattr(df.index, "tz", None) is not None:
        bp = bp.tz_localize(df.index.tz)

    before = df[df.index < bp]
    after = df[df.index >= bp]
    if len(before) < 20 or len(after) < 20:
        return {"break_detected": False, "reason": "one side of the break is too short"}

    def _rss(sub: pd.DataFrame) -> float:
        design = np.column_stack([sub["x"].to_numpy(), np.ones(len(sub))])
        beta, *_ = np.linalg.lstsq(design, sub["y"].to_numpy(), rcond=None)
        resid = sub["y"].to_numpy() - design @ beta
        return float(resid @ resid)

    rss_pooled = _rss(df)
    rss_split = _rss(before) + _rss(after)
    k = 2  # slope and intercept
    n = len(df)
    dof = n - 2 * k
    if dof <= 0 or rss_split <= 0:
        return {"break_detected": False, "reason": "degenerate regression"}

    f_stat = ((rss_pooled - rss_split) / k) / (rss_split / dof)
    pvalue = float(1 - stats.f.cdf(f_stat, k, dof))
    return {
        "break_detected": bool(pvalue < alpha),
        "f_statistic": float(f_stat),
        "pvalue": pvalue,
        "break_point": bp,
        "n_before": len(before),
        "n_after": len(after),
        "interpretation": (
            "the relationship changed at this date — refit or retire the model"
            if pvalue < alpha
            else "no detectable change in the relationship at this date"
        ),
    }


def rolling_break_monitor(
    y: pd.Series, x: pd.Series, *, window: int = 336, alpha: float = 0.05
) -> pd.DataFrame:
    """Live monitor: rolling regression stability for a pair relationship.

    Reports the trailing hedge ratio, the R-squared and a standardised drift measure of
    the beta. A hedge ratio drifting several of its own standard deviations is the
    practical signal to stop trading the pair — before the spread stops reverting and
    teaches you the same thing at a cost.
    """
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    mp = max(window // 4, 20)
    cov = df["y"].rolling(window, min_periods=mp).cov(df["x"])
    var = df["x"].rolling(window, min_periods=mp).var(ddof=0)
    beta = cov / var.replace(0.0, np.nan)
    corr = df["y"].rolling(window, min_periods=mp).corr(df["x"])

    beta_mean = beta.rolling(window, min_periods=mp).mean()
    beta_std = beta.rolling(window, min_periods=mp).std(ddof=0)
    drift = (beta - beta_mean) / beta_std.replace(0.0, np.nan)

    return pd.DataFrame(
        {
            "beta": beta,
            "r_squared": corr**2,
            "beta_drift_z": drift,
            "unstable": (drift.abs() > 2.0) | (corr**2 < 0.3),
        }
    )
