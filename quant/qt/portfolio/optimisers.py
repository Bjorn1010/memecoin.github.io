"""Portfolio optimisers — turning views and a covariance matrix into weights.

Ordered roughly by how much they trust the inputs, which is the same as how badly they
fail when the inputs are wrong:

* **Equal weight (1/N)** — trusts nothing. Notoriously hard to beat out of sample
  (DeMiguel, Garlappi & Uppal showed the optimisers usually lose to it), and the
  benchmark every other method here has to clear.
* **Inverse volatility** — trusts only the diagonal. Ignores correlation, which is
  exactly what makes it robust: variances are estimated far more accurately than
  covariances.
* **Risk parity** — trusts the full matrix, but only to equalise risk *contributions*,
  never to forecast returns. Solves the failure mode of 1/N in a crypto book, where
  equal weights mean the highest-vol alt dominates the risk.
* **Minimum variance** — trusts the full matrix, and needs no return forecast at all.
  The best-behaved of the true optimisers, because expected returns are the input we
  estimate worst by an order of magnitude.
* **Maximum diversification** — maximises the ratio of weighted average volatility to
  portfolio volatility, i.e. explicitly buys decorrelation.
* **Mean-variance** — trusts everything, including expected returns. Included because
  it is the theoretical reference point, with a loud warning attached.
* **HRP** — Hierarchical Risk Parity (López de Prado): clusters assets by correlation
  and allocates down the tree. Never inverts the covariance matrix, so it is immune to
  the near-singularity that wrecks mean-variance on correlated panels.

All return weights summing to one, long-only unless `allow_short=True`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize

from .covariance import nearest_positive_definite


def equal_weight(assets) -> pd.Series:
    names = list(assets)
    return pd.Series(1.0 / len(names), index=names, name="equal_weight")


def inverse_volatility(cov: pd.DataFrame) -> pd.Series:
    vols = np.sqrt(np.diag(cov.to_numpy()))
    inv = 1.0 / np.where(vols > 0, vols, np.inf)
    total = inv.sum()
    return pd.Series(inv / total if total > 0 else inv, index=cov.index, name="inverse_vol")


def minimum_variance(cov: pd.DataFrame, *, allow_short: bool = False, max_weight: float = 1.0) -> pd.Series:
    """Minimise w'Σw subject to the weights summing to one.

    No expected-return input, which is the point: return forecasts carry so much error
    that the mean-variance solution is dominated by them, while the minimum-variance
    solution depends only on the covariance — estimated far more reliably.
    """
    n = cov.shape[0]
    sigma = nearest_positive_definite(cov).to_numpy()

    def objective(w):
        return float(w @ sigma @ w)

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(-max_weight, max_weight) if allow_short else (0.0, max_weight)] * n
    result = optimize.minimize(
        objective, np.repeat(1.0 / n, n), method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 500, "ftol": 1e-12},
    )
    w = result.x if result.success else np.repeat(1.0 / n, n)
    return pd.Series(w, index=cov.index, name="min_variance")


def maximum_diversification(cov: pd.DataFrame, *, allow_short: bool = False, max_weight: float = 1.0) -> pd.Series:
    """Maximise (w'σ) / sqrt(w'Σw) — the diversification ratio.

    Buys decorrelation explicitly: it prefers assets whose volatility does not show up
    in the portfolio's volatility. In a panel dominated by one factor it degenerates
    toward the least-correlated names, which is the correct behaviour and also a
    warning that the panel has little to diversify with.
    """
    n = cov.shape[0]
    sigma = nearest_positive_definite(cov).to_numpy()
    vols = np.sqrt(np.diag(sigma))

    def negative_ratio(w):
        port_vol = np.sqrt(max(w @ sigma @ w, 1e-18))
        return -float((w @ vols) / port_vol)

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(-max_weight, max_weight) if allow_short else (0.0, max_weight)] * n
    result = optimize.minimize(
        negative_ratio, np.repeat(1.0 / n, n), method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 500, "ftol": 1e-12},
    )
    w = result.x if result.success else np.repeat(1.0 / n, n)
    return pd.Series(w, index=cov.index, name="max_diversification")


def risk_parity(cov: pd.DataFrame, *, budget: pd.Series | None = None, max_iter: int = 2000) -> pd.Series:
    """Equal (or budgeted) risk contributions.

    Each asset contributes the same share of portfolio variance, rather than the same
    share of capital. In a book holding BTC and a small-cap alt, equal capital means
    the alt supplies most of the risk; equal risk is almost always what was actually
    intended.

    Solved by cyclical coordinate descent, which is stable and needs no matrix
    inversion.
    """
    sigma = nearest_positive_definite(cov).to_numpy()
    n = sigma.shape[0]
    target = (
        np.repeat(1.0 / n, n)
        if budget is None
        else (budget.reindex(cov.index).fillna(0.0).to_numpy() / max(budget.sum(), 1e-12))
    )

    w = np.repeat(1.0 / n, n)
    for _ in range(max_iter):
        w_prev = w.copy()
        for i in range(n):
            # Solve the quadratic in w_i that equalises its marginal risk contribution.
            others = sigma[i] @ w - sigma[i, i] * w[i]
            disc = others**2 + 4 * sigma[i, i] * target[i] * float(w @ sigma @ w)
            w[i] = (-others + np.sqrt(max(disc, 0.0))) / (2 * sigma[i, i]) if sigma[i, i] > 0 else 0.0
        w = np.abs(w)
        total = w.sum()
        w = w / total if total > 0 else np.repeat(1.0 / n, n)
        if np.max(np.abs(w - w_prev)) < 1e-10:
            break
    return pd.Series(w, index=cov.index, name="risk_parity")


def mean_variance(
    expected_returns: pd.Series,
    cov: pd.DataFrame,
    *,
    risk_aversion: float = 3.0,
    allow_short: bool = False,
    max_weight: float = 1.0,
) -> pd.Series:
    """Maximise w'mu - (lambda/2) w'Σw.

    **Use with suspicion.** Expected returns are estimated with error an order of
    magnitude larger than covariances, and this objective amplifies exactly that error:
    the optimiser concentrates in whichever asset happened to have the highest
    estimated mean, which is usually the one with the noisiest estimate. Michaud called
    it an error-maximiser and he was right.

    Included because it is the reference point everything else is defined against, and
    because it is correct when you genuinely have a return forecast you trust (e.g. a
    model edge, or Black-Litterman posterior means).
    """
    mu = expected_returns.reindex(cov.index).fillna(0.0).to_numpy()
    sigma = nearest_positive_definite(cov).to_numpy()
    n = len(mu)

    def objective(w):
        return -float(w @ mu - 0.5 * risk_aversion * (w @ sigma @ w))

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(-max_weight, max_weight) if allow_short else (0.0, max_weight)] * n
    result = optimize.minimize(
        objective, np.repeat(1.0 / n, n), method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 500, "ftol": 1e-12},
    )
    w = result.x if result.success else np.repeat(1.0 / n, n)
    return pd.Series(w, index=cov.index, name="mean_variance")


def maximum_sharpe(
    expected_returns: pd.Series, cov: pd.DataFrame, *, risk_free: float = 0.0,
    allow_short: bool = False, max_weight: float = 1.0,
) -> pd.Series:
    """Tangency portfolio: maximise (w'mu - rf) / sqrt(w'Σw). Same warning as above."""
    mu = expected_returns.reindex(cov.index).fillna(0.0).to_numpy()
    sigma = nearest_positive_definite(cov).to_numpy()
    n = len(mu)

    def negative_sharpe(w):
        excess = w @ mu - risk_free
        vol = np.sqrt(max(w @ sigma @ w, 1e-18))
        return -float(excess / vol)

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bounds = [(-max_weight, max_weight) if allow_short else (0.0, max_weight)] * n
    result = optimize.minimize(
        negative_sharpe, np.repeat(1.0 / n, n), method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 500, "ftol": 1e-12},
    )
    w = result.x if result.success else np.repeat(1.0 / n, n)
    return pd.Series(w, index=cov.index, name="max_sharpe")


# ---------------------------------------------------------------------------
# Hierarchical Risk Parity
# ---------------------------------------------------------------------------
def _quasi_diagonalise(link: np.ndarray, n: int) -> list[int]:
    """Reorder assets so correlated ones sit adjacent, following the cluster tree."""
    from scipy.cluster.hierarchy import to_tree

    tree = to_tree(link, rd=False)
    order: list[int] = []

    def walk(node):
        if node.is_leaf():
            order.append(node.id)
            return
        walk(node.get_left())
        walk(node.get_right())

    walk(tree)
    return order


def hierarchical_risk_parity(cov: pd.DataFrame, *, linkage_method: str = "single") -> pd.Series:
    """HRP (López de Prado 2016).

    Three steps: cluster assets by correlation distance, reorder the covariance matrix
    so related assets are adjacent, then split capital recursively down the tree in
    inverse proportion to each branch's variance.

    The reason it works: it never inverts the covariance matrix. Mean-variance requires
    Σ⁻¹, and on a panel where everything is 0.9 correlated — which describes crypto
    exactly — that inverse is numerically explosive and the resulting weights are
    dominated by estimation error. HRP only ever compares variances of sub-portfolios,
    an operation that stays stable however correlated the panel is.
    """
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform

    sigma = nearest_positive_definite(cov)
    n = sigma.shape[0]
    if n < 2:
        return pd.Series(1.0, index=sigma.index, name="hrp")

    std = np.sqrt(np.diag(sigma.to_numpy()))
    corr = sigma.to_numpy() / np.outer(std, std)
    corr = np.clip(corr, -1.0, 1.0)

    # Correlation distance: d = sqrt((1 - rho) / 2), which is a proper metric.
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2.0  # enforce exact symmetry for squareform

    link = linkage(squareform(dist, checks=False), method=linkage_method)
    order = _quasi_diagonalise(link, n)

    values = sigma.to_numpy()
    weights = pd.Series(1.0, index=range(n), dtype="float64")
    clusters = [order]

    while clusters:
        # Bisect every cluster, then allocate between the two halves.
        clusters = [
            part
            for cluster in clusters
            for part in (cluster[: len(cluster) // 2], cluster[len(cluster) // 2 :])
            if len(part) > 0
        ]
        for i in range(0, len(clusters), 2):
            if i + 1 >= len(clusters):
                break
            left, right = clusters[i], clusters[i + 1]
            var_left = _cluster_variance(values, left)
            var_right = _cluster_variance(values, right)
            total = var_left + var_right
            alpha = 1.0 - var_left / total if total > 0 else 0.5
            weights[left] *= alpha
            weights[right] *= 1.0 - alpha
        clusters = [c for c in clusters if len(c) > 1]

    out = pd.Series(weights.to_numpy(), index=sigma.index, name="hrp")
    return out / out.sum()


def _cluster_variance(cov: np.ndarray, members: list[int]) -> float:
    """Variance of a sub-portfolio weighted inverse to its own variances."""
    sub = cov[np.ix_(members, members)]
    diag = np.diag(sub)
    inv = 1.0 / np.where(diag > 0, diag, np.inf)
    w = inv / inv.sum() if inv.sum() > 0 else np.repeat(1.0 / len(members), len(members))
    return float(w @ sub @ w)


def compare_optimisers(
    returns: pd.DataFrame, cov: pd.DataFrame | None = None, expected_returns: pd.Series | None = None
) -> pd.DataFrame:
    """Run every optimiser on the same inputs and show what each one actually does.

    The comparison to look at is not which has the best in-sample Sharpe — they all
    look fine in sample — but the *concentration* and *effective number of bets*
    columns. An optimiser that puts 80% in one asset has not diversified; it has made
    a directional bet you did not ask for.
    """
    from .covariance import ledoit_wolf_covariance
    from .risk import effective_number_of_bets, risk_contributions

    if cov is None:
        cov, _ = ledoit_wolf_covariance(returns)

    candidates = {
        "equal_weight": lambda: equal_weight(cov.index),
        "inverse_vol": lambda: inverse_volatility(cov),
        "risk_parity": lambda: risk_parity(cov),
        "min_variance": lambda: minimum_variance(cov),
        "max_diversification": lambda: maximum_diversification(cov),
        "hrp": lambda: hierarchical_risk_parity(cov),
    }
    if expected_returns is not None:
        candidates["mean_variance"] = lambda: mean_variance(expected_returns, cov)
        candidates["max_sharpe"] = lambda: maximum_sharpe(expected_returns, cov)

    rows = []
    for name, fn in candidates.items():
        try:
            w = fn()
        except Exception as exc:
            rows.append({"optimiser": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        port_vol = float(np.sqrt(w.to_numpy() @ cov.to_numpy() @ w.to_numpy()))
        rc = risk_contributions(w, cov)
        rows.append(
            {
                "optimiser": name,
                "portfolio_vol": port_vol,
                "max_weight": float(w.max()),
                "min_weight": float(w.min()),
                "herfindahl": float((w**2).sum()),  # 1/N at best, 1.0 if all in one
                "effective_n_assets": float(1.0 / (w**2).sum()),
                "effective_n_bets": effective_number_of_bets(w, cov),
                "max_risk_contribution": float(rc.max()),
            }
        )
    return pd.DataFrame(rows).set_index("optimiser")
