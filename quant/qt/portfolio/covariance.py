"""Covariance estimation — the input that decides whether an optimiser helps or hurts.

Markowitz optimisation has a bad reputation it does not deserve. The theory is correct;
what fails is the *input*. A sample covariance matrix estimated from T observations of
N assets has enormous error when T is not much larger than N, and the optimiser is an
error-maximising machine: it puts the most weight exactly where the estimate is most
wrong, because a spuriously low estimated variance looks like a free lunch.

Three fixes, in increasing sophistication:

* **Shrinkage (Ledoit-Wolf)** — pull the sample matrix toward a structured target
  (constant correlation, or a scaled identity). The optimal shrinkage intensity has a
  closed form and needs no tuning. This is the single highest-value line of code in
  portfolio construction and it is one function call.
* **EWMA** — weight recent observations more. Correlations move, especially in crisis,
  and a five-year equal-weight estimate describes a market that no longer exists.
* **RMT denoising (Marchenko-Pastur)** — random matrix theory says that for a matrix of
  pure noise, the eigenvalues fall inside a known band. Eigenvalues inside that band
  are indistinguishable from noise and are replaced by their average, keeping only the
  eigenvalues that carry real structure. This is what practitioners do at scale.

`condition_number` and `effective_rank` are diagnostics worth reading before trusting
any optimiser output: a condition number in the thousands means the matrix is nearly
singular and the "optimal" weights are numerical noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sample_covariance(returns: pd.DataFrame, *, annualise: float | None = None) -> pd.DataFrame:
    """Plain sample covariance. The baseline, and rarely the right choice."""
    cov = returns.cov()
    return cov * annualise if annualise else cov


def ewma_covariance(
    returns: pd.DataFrame, *, halflife: int = 168, annualise: float | None = None, min_periods: int = 30
) -> pd.DataFrame:
    """Exponentially weighted covariance — recent observations count for more."""
    r = returns.dropna(how="all")
    if len(r) < min_periods:
        return sample_covariance(r, annualise=annualise)
    lam = 0.5 ** (1.0 / halflife)
    weights = lam ** np.arange(len(r))[::-1]
    weights = weights / weights.sum()
    x = r.fillna(0.0).to_numpy()
    mean = weights @ x
    centred = x - mean
    cov = (centred * weights[:, None]).T @ centred / (1 - np.sum(weights**2))
    out = pd.DataFrame(cov, index=r.columns, columns=r.columns)
    return out * annualise if annualise else out


def ledoit_wolf_covariance(
    returns: pd.DataFrame, *, annualise: float | None = None
) -> tuple[pd.DataFrame, float]:
    """Ledoit-Wolf shrinkage toward a constant-correlation target.

    Returns (covariance, shrinkage_intensity). The intensity is informative in itself:
    close to 0 means the sample estimate is trustworthy (long history, few assets),
    close to 1 means it is mostly noise and the optimiser should not be believed.
    """
    from sklearn.covariance import LedoitWolf

    r = returns.dropna()
    if len(r) < 10 or r.shape[1] < 2:
        return sample_covariance(r, annualise=annualise), 0.0
    lw = LedoitWolf(assume_centered=False).fit(r.to_numpy())
    cov = pd.DataFrame(lw.covariance_, index=r.columns, columns=r.columns)
    return (cov * annualise if annualise else cov), float(lw.shrinkage_)


def marchenko_pastur_bounds(n_obs: int, n_assets: int, sigma2: float = 1.0) -> tuple[float, float]:
    """Eigenvalue band inside which a correlation matrix is indistinguishable from noise."""
    q = n_obs / max(n_assets, 1)
    if q <= 1:
        # More assets than observations: the matrix is singular and denoising cannot
        # rescue it. Signal that by returning a degenerate band.
        return 0.0, sigma2 * (1 + 1 / np.sqrt(max(q, 1e-9))) ** 2
    lambda_minus = sigma2 * (1 - np.sqrt(1 / q)) ** 2
    lambda_plus = sigma2 * (1 + np.sqrt(1 / q)) ** 2
    return float(lambda_minus), float(lambda_plus)


def denoise_covariance(
    returns: pd.DataFrame, *, annualise: float | None = None, keep_market_factor: bool = True
) -> dict:
    """Random-matrix-theory denoising: keep only eigenvalues outside the noise band.

    Procedure: convert to correlation, eigendecompose, replace every eigenvalue inside
    the Marchenko-Pastur band with their common average (preserving the trace), and
    reconstruct. The largest eigenvalue is the market factor and is always kept — in a
    crypto panel it typically explains 60-80% of total variance, and removing it would
    discard the single most important thing about the panel.

    Returns the denoised covariance plus diagnostics: how many factors survived, and
    what share of variance the market factor carries.
    """
    r = returns.dropna()
    n_obs, n_assets = r.shape
    if n_obs < 20 or n_assets < 2:
        return {"covariance": sample_covariance(r, annualise=annualise), "n_factors": 0}

    std = r.std(ddof=1)
    corr = r.corr().to_numpy()
    eigvals, eigvecs = np.linalg.eigh(corr)
    order = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]

    _, lambda_plus = marchenko_pastur_bounds(n_obs, n_assets, sigma2=1.0)
    signal = eigvals > lambda_plus
    if keep_market_factor:
        signal[0] = True

    cleaned = eigvals.copy()
    noise_mask = ~signal
    if noise_mask.any():
        # Replace the noise eigenvalues by their mean, preserving the trace so the
        # total variance of the matrix is unchanged.
        cleaned[noise_mask] = eigvals[noise_mask].mean()

    corr_clean = eigvecs @ np.diag(cleaned) @ eigvecs.T
    # Force unit diagonal: numerical error otherwise leaves it slightly off, which
    # then propagates into every correlation derived from it.
    d = np.sqrt(np.diag(corr_clean))
    corr_clean = corr_clean / np.outer(d, d)

    cov = pd.DataFrame(
        corr_clean * np.outer(std.to_numpy(), std.to_numpy()), index=r.columns, columns=r.columns
    )
    return {
        "covariance": cov * annualise if annualise else cov,
        "n_factors": int(signal.sum()),
        "n_assets": n_assets,
        "lambda_plus": lambda_plus,
        "eigenvalues": eigvals,
        "market_factor_share": float(eigvals[0] / eigvals.sum()),
        "noise_share": float(eigvals[noise_mask].sum() / eigvals.sum()) if noise_mask.any() else 0.0,
    }


def condition_number(cov: pd.DataFrame) -> float:
    """Ratio of largest to smallest eigenvalue.

    Above ~1000, the matrix is close to singular: inverting it (which every
    mean-variance optimiser does) amplifies estimation error enormously, and the
    resulting weights are not meaningfully different from noise.
    """
    eig = np.linalg.eigvalsh(cov.to_numpy())
    smallest = eig[eig > 0].min() if (eig > 0).any() else np.nan
    return float(eig.max() / smallest) if smallest and np.isfinite(smallest) else float("inf")


def effective_rank(cov: pd.DataFrame) -> float:
    """Entropy-based count of genuinely independent directions of risk.

    A ten-asset crypto portfolio routinely has an effective rank near 2: you think you
    hold ten positions, the market sees one and a half bets. This number is a far more
    honest description of diversification than the count of tickers.
    """
    eig = np.linalg.eigvalsh(cov.to_numpy())
    eig = eig[eig > 0]
    if eig.size == 0:
        return 0.0
    p = eig / eig.sum()
    return float(np.exp(-(p * np.log(p)).sum()))


def covariance_report(returns: pd.DataFrame, annualise: float | None = None) -> dict:
    """Compare estimators side by side, with the diagnostics that decide which to use."""
    rows = []
    estimators = {
        "sample": lambda: sample_covariance(returns, annualise=annualise),
        "ewma": lambda: ewma_covariance(returns, annualise=annualise),
        "ledoit_wolf": lambda: ledoit_wolf_covariance(returns, annualise=annualise)[0],
        "denoised": lambda: denoise_covariance(returns, annualise=annualise)["covariance"],
    }
    mats = {}
    for name, fn in estimators.items():
        try:
            cov = fn()
        except Exception as exc:
            rows.append({"estimator": name, "error": str(exc)})
            continue
        mats[name] = cov
        rows.append(
            {
                "estimator": name,
                "condition_number": round(condition_number(cov), 1),
                "effective_rank": round(effective_rank(cov), 2),
                "mean_variance": float(np.mean(np.diag(cov.to_numpy()))),
                "mean_correlation": float(
                    cov.to_numpy()[np.triu_indices_from(cov.to_numpy(), k=1)].mean()
                    / np.mean(np.diag(cov.to_numpy()))
                ),
            }
        )

    _, shrinkage = ledoit_wolf_covariance(returns, annualise=annualise)
    denoise = denoise_covariance(returns, annualise=annualise)
    return {
        "table": pd.DataFrame(rows),
        "matrices": mats,
        "shrinkage_intensity": shrinkage,
        "n_significant_factors": denoise.get("n_factors"),
        "market_factor_share": denoise.get("market_factor_share"),
        "n_assets": returns.shape[1],
        "n_obs": len(returns.dropna()),
    }


def nearest_positive_definite(cov: pd.DataFrame, epsilon: float = 1e-10) -> pd.DataFrame:
    """Clip negative eigenvalues so the matrix can be inverted and Cholesky-factored.

    Estimated covariance matrices routinely come back with tiny negative eigenvalues
    from numerical error, which makes every optimiser fail in a confusing way.
    """
    values = cov.to_numpy()
    eigvals, eigvecs = np.linalg.eigh((values + values.T) / 2)
    eigvals = np.maximum(eigvals, epsilon)
    fixed = eigvecs @ np.diag(eigvals) @ eigvecs.T
    return pd.DataFrame(fixed, index=cov.index, columns=cov.columns)
