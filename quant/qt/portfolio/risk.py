"""Portfolio risk decomposition and tail measures.

Two questions this module answers that a single volatility number cannot:

**Where is my risk actually coming from?** Capital weights are not risk weights. A book
with 10% in a 200%-vol altcoin and 90% in cash has 10% of its capital and essentially
100% of its risk in one place. `risk_contributions` decomposes portfolio variance into
per-asset shares that sum to one, and `effective_number_of_bets` reduces the whole
picture to a single honest number — usually far smaller than the position count.

**How bad is the bad case?** Volatility describes the middle of the distribution and
financial returns are not normal there or anywhere else. VaR gives a quantile; CVaR
(expected shortfall) gives the average loss *given* that the quantile is breached,
which is the number that matters because it is sensitive to how fat the tail is. Three
estimators are provided because they disagree, and the disagreement is the information:
if historical CVaR is far worse than parametric, the distribution has a tail the normal
assumption does not see.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------- decomposition
def portfolio_volatility(weights: pd.Series, cov: pd.DataFrame) -> float:
    w = weights.reindex(cov.index).fillna(0.0).to_numpy()
    return float(np.sqrt(max(w @ cov.to_numpy() @ w, 0.0)))


def marginal_risk_contributions(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """d(portfolio vol) / d(weight): how much risk one more unit of each asset adds."""
    w = weights.reindex(cov.index).fillna(0.0).to_numpy()
    sigma = cov.to_numpy()
    port_vol = np.sqrt(max(w @ sigma @ w, 1e-18))
    return pd.Series((sigma @ w) / port_vol, index=cov.index, name="marginal_risk")


def risk_contributions(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Each asset's share of total portfolio risk. Sums to one.

    This is the number to look at instead of the weights. It routinely reveals that a
    'diversified' ten-asset book has 60% of its risk in one position.
    """
    w = weights.reindex(cov.index).fillna(0.0)
    mrc = marginal_risk_contributions(w, cov)
    contrib = w * mrc
    total = contrib.sum()
    return (contrib / total if total != 0 else contrib).rename("risk_contribution")


def effective_number_of_bets(weights: pd.Series, cov: pd.DataFrame) -> float:
    """Diversification measured in the eigenbasis, not in tickers.

    Rotates the portfolio into uncorrelated principal components, computes each
    component's share of variance, and returns the entropy-based count. Holding ten
    assets that are all 0.9 correlated gives an answer near 1: you have one bet in ten
    wrappers. This is the single most deflating and most useful diversification number.

    One caveat that matters when reading small numbers: the measure is defined in the
    eigenbasis, and when several eigenvalues are nearly equal that basis is close to
    arbitrary — any rotation of the degenerate subspace is equally valid, and the
    computed value depends on which one the eigensolver happened to return. The extreme
    case is a perfectly isotropic covariance (identical variances, zero correlation),
    where the answer is genuinely undefined rather than N. In real panels the
    eigenvalues are well separated and this does not arise; on synthetic data it does.
    """
    w = weights.reindex(cov.index).fillna(0.0).to_numpy()
    sigma = cov.to_numpy()
    eigvals, eigvecs = np.linalg.eigh(sigma)
    positive = eigvals > 1e-14
    if not positive.any():
        return 0.0
    exposures = eigvecs.T @ w  # portfolio loading on each principal component
    variances = (exposures**2) * eigvals
    variances = variances[positive]
    total = variances.sum()
    if total <= 0:
        return 0.0
    p = variances / total
    p = p[p > 0]
    return float(np.exp(-(p * np.log(p)).sum()))


def diversification_ratio(weights: pd.Series, cov: pd.DataFrame) -> float:
    """Weighted average volatility divided by portfolio volatility. 1.0 = no benefit."""
    w = weights.reindex(cov.index).fillna(0.0).to_numpy()
    vols = np.sqrt(np.diag(cov.to_numpy()))
    port_vol = portfolio_volatility(weights, cov)
    return float((w @ vols) / port_vol) if port_vol > 0 else np.nan


# ------------------------------------------------------------------ tail risk
def value_at_risk(
    returns: pd.Series, confidence: float = 0.95, method: str = "historical",
    horizon: int = 1,
) -> float:
    """Loss threshold breached with probability (1 - confidence). Returned as a
    negative number.

    * `historical` — the empirical quantile. Makes no distributional assumption and is
      the default, but cannot produce a loss larger than the worst one ever observed.
    * `parametric` — normal. Fast, and understates crypto tail risk substantially.
    * `cornish_fisher` — normal quantile adjusted for the sample's skew and excess
      kurtosis. The pragmatic middle: it keeps the parametric form while acknowledging
      that the distribution is not normal.
    """
    r = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 30:
        return float("nan")
    alpha = 1 - confidence
    scale = np.sqrt(horizon)  # square-root-of-time; assumes IID, which is optimistic

    if method == "historical":
        return float(r.quantile(alpha) * scale)
    if method == "parametric":
        return float((r.mean() + stats.norm.ppf(alpha) * r.std(ddof=1)) * scale)
    if method == "cornish_fisher":
        z = stats.norm.ppf(alpha)
        s = float(stats.skew(r, bias=False))
        k = float(stats.kurtosis(r, fisher=True, bias=False))
        z_cf = (
            z
            + (z**2 - 1) * s / 6
            + (z**3 - 3 * z) * k / 24
            - (2 * z**3 - 5 * z) * s**2 / 36
        )
        return float((r.mean() + z_cf * r.std(ddof=1)) * scale)
    raise ValueError(f"unknown VaR method {method!r}")


def conditional_value_at_risk(returns: pd.Series, confidence: float = 0.95, horizon: int = 1) -> float:
    """Expected shortfall: the average loss given that VaR is breached.

    Preferable to VaR for two reasons. It is sensitive to the shape of the tail beyond
    the threshold, where VaR is blind to it — two portfolios with identical VaR can
    have wildly different worst cases. And it is a coherent risk measure (VaR is not),
    meaning combining two portfolios can never make it look better than the parts.
    """
    r = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 30:
        return float("nan")
    var = r.quantile(1 - confidence)
    tail = r[r <= var]
    return float(tail.mean() * np.sqrt(horizon)) if len(tail) else float(var * np.sqrt(horizon))


def risk_report(
    weights: pd.Series, cov: pd.DataFrame, returns: pd.DataFrame | None = None,
    periods_per_year: float = 365 * 24, confidence: float = 0.95,
) -> dict:
    """Everything worth knowing about a book's risk, in one call."""
    w = weights.reindex(cov.index).fillna(0.0)
    port_vol = portfolio_volatility(w, cov)
    rc = risk_contributions(w, cov)

    out = {
        "portfolio_vol_per_bar": port_vol,
        "portfolio_vol_annual": port_vol * np.sqrt(periods_per_year),
        "gross_exposure": float(w.abs().sum()),
        "net_exposure": float(w.sum()),
        "n_positions": int((w.abs() > 1e-9).sum()),
        "effective_n_assets": float(1.0 / (w**2).sum()) if (w**2).sum() > 0 else 0.0,
        "effective_n_bets": effective_number_of_bets(w, cov),
        "diversification_ratio": diversification_ratio(w, cov),
        "risk_contributions": rc.sort_values(ascending=False),
        "largest_risk_contributor": rc.abs().idxmax() if len(rc) else None,
        "largest_risk_share": float(rc.abs().max()) if len(rc) else np.nan,
    }

    if returns is not None and not returns.empty:
        port_returns = (returns.reindex(columns=w.index).fillna(0.0) * w).sum(axis=1)
        out["portfolio_returns"] = port_returns
        out["var_historical"] = value_at_risk(port_returns, confidence, "historical")
        out["var_parametric"] = value_at_risk(port_returns, confidence, "parametric")
        out["var_cornish_fisher"] = value_at_risk(port_returns, confidence, "cornish_fisher")
        out["cvar"] = conditional_value_at_risk(port_returns, confidence)
        # If historical CVaR is much worse than parametric VaR, the tail is fatter
        # than a normal distribution can express and any normal-based limit is wrong.
        if np.isfinite(out["var_parametric"]) and out["var_parametric"] != 0:
            out["tail_fatness"] = float(out["cvar"] / out["var_parametric"])
        out["realised_vol_annual"] = float(port_returns.std(ddof=1) * np.sqrt(periods_per_year))
    return out


def stress_test(
    weights: pd.Series, returns: pd.DataFrame, scenarios: dict[str, tuple[str, str]] | None = None
) -> pd.DataFrame:
    """Replay the book through historical crisis windows.

    Historical stress testing beats hypothetical shocks because the correlations are
    real: in the actual event, the diversification you were counting on disappeared,
    and a hand-built scenario almost never captures that.

    Default windows are the crypto-relevant ones. Any window absent from the data is
    skipped rather than silently reported as zero.
    """
    scenarios = scenarios or {
        "covid_crash_2020": ("2020-03-08", "2020-03-20"),
        "may_2021_deleveraging": ("2021-05-12", "2021-05-24"),
        "luna_collapse_2022": ("2022-05-07", "2022-05-16"),
        "ftx_collapse_2022": ("2022-11-06", "2022-11-14"),
        "bank_stress_2023": ("2023-03-08", "2023-03-15"),
        "august_2024_unwind": ("2024-08-02", "2024-08-08"),
    }
    w = weights.reindex(returns.columns).fillna(0.0)

    rows = []
    for name, (start, end) in scenarios.items():
        window = returns.loc[str(start) : str(end)]
        if window.empty:
            continue
        port = (window.fillna(0.0) * w).sum(axis=1)
        cumulative = float((1 + port).prod() - 1)
        equity = (1 + port).cumprod()
        drawdown = float((equity / equity.cummax() - 1).min())
        rows.append(
            {
                "scenario": name,
                "start": start,
                "end": end,
                "n_bars": len(window),
                "total_return": cumulative,
                "max_drawdown": drawdown,
                "worst_bar": float(port.min()),
                "realised_vol": float(port.std(ddof=1)) if len(port) > 1 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("total_return") if rows else pd.DataFrame()


def factor_risk_decomposition(returns: pd.DataFrame, weights: pd.Series, n_factors: int = 3) -> dict:
    """Decompose portfolio variance into principal components.

    In crypto the first component is 'the market' and typically explains 60-80% of a
    panel's variance. Reading the portfolio's loading on it answers the question that
    matters most: how much of what looks like a diversified multi-asset book is
    actually just beta to the same thing?
    """
    r = returns.dropna()
    if r.shape[1] < 2 or len(r) < 30:
        return {}

    w = weights.reindex(r.columns).fillna(0.0).to_numpy()
    cov = r.cov().to_numpy()
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]

    exposures = eigvecs.T @ w
    variances = (exposures**2) * eigvals
    total = variances.sum()

    k = min(n_factors, len(eigvals))
    rows = []
    for i in range(k):
        rows.append(
            {
                "factor": f"PC{i + 1}",
                "eigenvalue_share": float(eigvals[i] / eigvals.sum()),
                "portfolio_exposure": float(exposures[i]),
                "variance_share": float(variances[i] / total) if total > 0 else np.nan,
                "top_assets": ", ".join(
                    pd.Series(eigvecs[:, i], index=r.columns).abs().nlargest(3).index
                ),
            }
        )
    return {
        "table": pd.DataFrame(rows),
        "market_factor_variance_share": float(variances[0] / total) if total > 0 else np.nan,
        "idiosyncratic_share": float(variances[k:].sum() / total) if total > 0 and len(variances) > k else 0.0,
        "loadings": pd.DataFrame(eigvecs[:, :k], index=r.columns, columns=[f"PC{i+1}" for i in range(k)]),
    }
