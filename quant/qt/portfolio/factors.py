"""Factor models — separating "the market went up" from "I picked well".

Most of what looks like alpha in a long crypto book is beta. An asset that returned
40% while the market returned 35% did not deliver 40% of skill; it delivered 5% of
skill and a lot of exposure. Factor models make that split explicit, and they answer
three questions a raw return series cannot:

* **What is my portfolio actually exposed to?** (`pca_factors`) Principal components
  extracted from the panel are the market's own factor structure, discovered rather
  than assumed. In crypto the first component is essentially "crypto beta".
* **Is this signal paid?** (`fama_macbeth`) The standard test for whether a
  characteristic earns a return premium cross-sectionally, with the
  autocorrelation-robust standard errors the method exists to provide.
* **What is left after removing the factors?** (`residualise`) The idiosyncratic
  return stream, which is what a market-neutral strategy is actually trading.

Fama-MacBeth deserves a note on why it is a two-pass procedure rather than one big
regression. Pooling all assets and periods into a single regression treats every
observation as independent, which they are not: in any given period all assets share
the market shock, so the errors are heavily cross-correlated and the t-statistics come
out several times too large. Fama-MacBeth runs one cross-sectional regression *per
period*, then treats the sequence of slope estimates as the sample. The resulting
standard error accounts for the cross-sectional correlation automatically, because it
is computed across time rather than across observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def pca_factors(returns: pd.DataFrame, n_factors: int = 3, standardise: bool = True) -> dict:
    """Extract statistical factors from a return panel.

    `standardise=True` runs PCA on the correlation matrix rather than the covariance,
    so a single high-volatility asset cannot define the first component by itself.
    """
    r = returns.dropna()
    if r.shape[1] < 2 or len(r) < 30:
        return {}

    x = r.to_numpy()
    mean = x.mean(axis=0)
    centred = x - mean
    scale = centred.std(axis=0, ddof=1) if standardise else np.ones(x.shape[1])
    scale = np.where(scale > 0, scale, 1.0)
    z = centred / scale

    cov = np.cov(z, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]

    k = min(n_factors, len(eigvals))
    loadings = pd.DataFrame(
        eigvecs[:, :k], index=r.columns, columns=[f"PC{i + 1}" for i in range(k)]
    )
    scores = pd.DataFrame(z @ eigvecs[:, :k], index=r.index, columns=loadings.columns)

    return {
        "loadings": loadings,
        "factor_returns": scores,
        "explained_variance_ratio": pd.Series(
            eigvals[:k] / eigvals.sum(), index=loadings.columns, name="explained"
        ),
        "cumulative_variance": float(eigvals[:k].sum() / eigvals.sum()),
        "eigenvalues": eigvals,
        # The first component's share is the honest measure of how one-dimensional the
        # panel is. Above ~0.7 there is very little to diversify between.
        "market_factor_share": float(eigvals[0] / eigvals.sum()),
    }


def eigen_portfolios(returns: pd.DataFrame, n_factors: int = 3) -> pd.DataFrame:
    """Weights of the principal-component portfolios, normalised to sum to one.

    The first eigen-portfolio is the market. The second and beyond are the tradeable
    relative-value structures the panel actually contains, discovered rather than
    guessed — a far better starting point for a pairs search than picking two names
    that "should" be related.
    """
    pca = pca_factors(returns, n_factors)
    if not pca:
        return pd.DataFrame()
    loadings = pca["loadings"]
    weights = loadings / loadings.abs().sum()
    return weights


def residualise(
    returns: pd.DataFrame, factors: pd.DataFrame | pd.Series, *, window: int | None = None
) -> pd.DataFrame:
    """Strip factor exposure out of each asset's returns.

    With `window`, betas are estimated on trailing data only and the residuals are
    usable in a backtest. Without it, betas are full-sample — fine for a diagnostic,
    a look-ahead in a strategy.
    """
    f = factors.to_frame() if isinstance(factors, pd.Series) else factors
    common = returns.index.intersection(f.index)
    r, f = returns.loc[common], f.loc[common]

    if window is None:
        design = np.column_stack([f.to_numpy(), np.ones(len(f))])
        residuals = {}
        for col in r.columns:
            y = r[col].to_numpy()
            mask = np.isfinite(y) & np.isfinite(design).all(axis=1)
            if mask.sum() < 10:
                residuals[col] = pd.Series(np.nan, index=r.index)
                continue
            beta, *_ = np.linalg.lstsq(design[mask], y[mask], rcond=None)
            resid = np.full(len(y), np.nan)
            resid[mask] = y[mask] - design[mask] @ beta
            residuals[col] = pd.Series(resid, index=r.index)
        return pd.DataFrame(residuals)

    mp = max(window // 4, 20)
    out = {}
    for col in r.columns:
        resid = r[col].copy()
        for fac in f.columns:
            cov = resid.rolling(window, min_periods=mp).cov(f[fac])
            var = f[fac].rolling(window, min_periods=mp).var(ddof=0)
            beta = (cov / var.replace(0.0, np.nan)).shift(1)  # beta known before the bar
            resid = resid - beta * f[fac]
        out[col] = resid
    return pd.DataFrame(out)


def fama_macbeth(
    returns: pd.DataFrame,
    characteristics: dict[str, pd.DataFrame],
    *,
    forward_periods: int = 1,
    newey_west_lags: int | None = None,
) -> pd.DataFrame:
    """Two-pass Fama-MacBeth regression of forward returns on characteristics.

    `characteristics` maps a factor name to a (time x asset) frame of its values —
    exactly the shape `features.cross_sectional` produces.

    The output row for each characteristic is the average cross-sectional slope (the
    factor's estimated premium per period) with its t-statistic. A t-statistic above 2
    is the conventional bar, and given how many characteristics get tested in practice,
    3 is the honest one.

    Newey-West standard errors correct for autocorrelation in the sequence of slopes,
    which is present whenever the characteristic itself is persistent — as momentum
    and value both are.
    """
    if not characteristics:
        return pd.DataFrame()

    names = list(characteristics)
    # Forward returns: the characteristic at t is regressed against the return earned
    # AFTER t. Shifting the wrong way here is the classic Fama-MacBeth error.
    fwd = returns.shift(-forward_periods)

    slopes: dict[str, list[float]] = {name: [] for name in names}
    slopes["intercept"] = []
    dates = []

    for date in returns.index:
        y = fwd.loc[date] if date in fwd.index else None
        if y is None:
            continue
        cols = []
        for name in names:
            frame = characteristics[name]
            cols.append(frame.loc[date] if date in frame.index else pd.Series(dtype="float64"))

        panel = pd.concat([y.rename("y")] + [c.rename(n) for c, n in zip(cols, names)], axis=1)
        panel = panel.replace([np.inf, -np.inf], np.nan).dropna()
        if len(panel) < max(len(names) + 2, 4):
            continue

        design = np.column_stack([panel[names].to_numpy(), np.ones(len(panel))])
        try:
            beta, *_ = np.linalg.lstsq(design, panel["y"].to_numpy(), rcond=None)
        except np.linalg.LinAlgError:
            continue
        for i, name in enumerate(names):
            slopes[name].append(float(beta[i]))
        slopes["intercept"].append(float(beta[-1]))
        dates.append(date)

    if not dates:
        return pd.DataFrame()

    series = pd.DataFrame(slopes, index=pd.DatetimeIndex(dates))
    lags = newey_west_lags if newey_west_lags is not None else int(4 * (len(series) / 100) ** (2 / 9))

    rows = []
    for name in series.columns:
        s = series[name].dropna()
        n = len(s)
        if n < 10:
            continue
        mean = float(s.mean())
        se = _newey_west_se(s.to_numpy(), lags)
        t_stat = mean / se if se > 0 else np.nan
        rows.append(
            {
                "factor": name,
                "premium_per_period": mean,
                "std_error": se,
                "t_statistic": t_stat,
                "pvalue": float(2 * (1 - stats.norm.cdf(abs(t_stat)))) if np.isfinite(t_stat) else np.nan,
                "n_periods": n,
                "significant_at_2": bool(np.isfinite(t_stat) and abs(t_stat) > 2),
                "significant_at_3": bool(np.isfinite(t_stat) and abs(t_stat) > 3),
            }
        )

    out = pd.DataFrame(rows).set_index("factor")
    out.attrs["slope_series"] = series
    out.attrs["newey_west_lags"] = lags
    return out


def _newey_west_se(x: np.ndarray, lags: int) -> float:
    """Heteroskedasticity- and autocorrelation-consistent standard error of a mean."""
    n = x.size
    if n < 3:
        return float("nan")
    demeaned = x - x.mean()
    gamma0 = float(demeaned @ demeaned) / n
    variance = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1.0 - lag / (lags + 1.0)  # Bartlett kernel
        gamma = float(demeaned[lag:] @ demeaned[:-lag]) / n
        variance += 2 * weight * gamma
    variance = max(variance, 1e-18)
    return float(np.sqrt(variance / n))


def information_coefficient_report(
    signal: pd.DataFrame, returns: pd.DataFrame, forward_periods: int = 1
) -> dict:
    """Cross-sectional IC of a signal: its rank correlation with subsequent returns.

    The IC is the natural score for a cross-sectional signal, and its *stability* over
    time matters more than its level. An IC of 0.03 that is positive in 60% of periods
    is a real, tradeable factor; an IC of 0.08 driven by three periods is not.

    The information ratio here (mean IC / std IC) is what converts an IC into an
    expected Sharpe via the fundamental law of active management.
    """
    fwd = returns.shift(-forward_periods)
    common = signal.index.intersection(fwd.index)

    ics = []
    for date in common:
        s = signal.loc[date]
        r = fwd.loc[date]
        panel = pd.concat([s.rename("s"), r.rename("r")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
        if len(panel) < 4:
            continue
        ic = panel["s"].corr(panel["r"], method="spearman")
        if np.isfinite(ic):
            ics.append({"date": date, "ic": float(ic)})

    if not ics:
        return {"mean_ic": np.nan, "n_periods": 0}

    series = pd.DataFrame(ics).set_index("date")["ic"]
    mean_ic, std_ic = float(series.mean()), float(series.std(ddof=1))
    return {
        "mean_ic": mean_ic,
        "std_ic": std_ic,
        "ic_information_ratio": mean_ic / std_ic if std_ic > 0 else np.nan,
        "hit_rate": float((series > 0).mean()),
        "t_statistic": mean_ic / (std_ic / np.sqrt(len(series))) if std_ic > 0 else np.nan,
        "n_periods": len(series),
        "series": series,
    }
