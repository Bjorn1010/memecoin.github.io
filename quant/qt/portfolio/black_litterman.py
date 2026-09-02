"""Black-Litterman — combining a market prior with your own views.

The failure of naive mean-variance is that it demands an expected return for every
asset, and you do not have one. You have a *few* opinions ("ETH will outperform BTC by
5% annualised, and I am moderately confident"), and no view at all about most of the
book. Feeding a full vector of noisy estimates into an optimiser produces the
error-maximising behaviour that gives the technique its bad name.

Black-Litterman inverts the problem. Start from the returns that would make the market
portfolio optimal — implied equilibrium returns, obtained by *reverse* optimisation —
and treat those as a prior. Then update the prior with only the views you actually
hold, weighted by how confident you are. Assets you have no view on keep their
equilibrium return, so they neither dominate nor disappear.

The result is a posterior return vector that is stable, that reduces to the market
portfolio when you have no views, and that tilts sensibly and proportionately when you
do. It is the only way I know to use a return forecast in an optimiser without the
optimiser exploding.

Views come in two forms, both supported:
* **Absolute** — "BTC returns 20% annualised".
* **Relative** — "ETH outperforms BTC by 5%". Usually the honest form: relative views
  are what a cross-sectional model actually produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .covariance import nearest_positive_definite


@dataclass
class View:
    """A single opinion.

    `assets` maps asset -> coefficient. {"ETH": 1, "BTC": -1} with value 0.05 means
    "ETH outperforms BTC by 5%". {"BTC": 1} with value 0.20 means "BTC returns 20%".

    `confidence` in (0, 1]: 1.0 means the view is held with certainty (the posterior
    will match it exactly), 0.1 means it barely moves the prior.
    """

    assets: dict[str, float]
    value: float
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not 0 < self.confidence <= 1:
            raise ValueError("confidence must be in (0, 1]")


@dataclass
class BlackLittermanResult:
    posterior_returns: pd.Series
    equilibrium_returns: pd.Series
    posterior_cov: pd.DataFrame
    weights: pd.Series
    market_weights: pd.Series
    views: list[View] = field(default_factory=list)

    def tilt(self) -> pd.Series:
        """How far the posterior weights moved from the market portfolio."""
        return (self.weights - self.market_weights).rename("tilt")

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "equilibrium_return": self.equilibrium_returns,
                "posterior_return": self.posterior_returns,
                "view_impact": self.posterior_returns - self.equilibrium_returns,
                "market_weight": self.market_weights,
                "posterior_weight": self.weights,
                "tilt": self.tilt(),
            }
        )


def implied_equilibrium_returns(
    market_weights: pd.Series, cov: pd.DataFrame, risk_aversion: float = 2.5
) -> pd.Series:
    """Reverse optimisation: mu = lambda * Σ * w_market.

    The returns that would make the observed market portfolio optimal. This is the
    trick that makes the whole method work — instead of estimating expected returns
    (hopeless), it reads them off the market's own positioning, which is at least an
    equilibrium of many participants' views rather than one noisy sample mean.
    """
    w = market_weights.reindex(cov.index).fillna(0.0).to_numpy()
    return pd.Series(risk_aversion * (cov.to_numpy() @ w), index=cov.index, name="equilibrium_return")


def black_litterman(
    cov: pd.DataFrame,
    market_weights: pd.Series,
    views: list[View] | None = None,
    *,
    risk_aversion: float = 2.5,
    tau: float = 0.05,
    allow_short: bool = False,
    max_weight: float = 1.0,
) -> BlackLittermanResult:
    """Posterior expected returns and the portfolio they imply.

    `tau` scales the uncertainty of the prior itself; 0.025-0.05 is the usual range.
    Its effect is mostly to set how much a view of given confidence moves the answer,
    so it is a modelling dial rather than something to fit.
    """
    from .optimisers import mean_variance

    sigma = nearest_positive_definite(cov)
    assets = list(sigma.index)
    w_mkt = market_weights.reindex(assets).fillna(0.0)
    if w_mkt.sum() > 0:
        w_mkt = w_mkt / w_mkt.sum()

    pi = implied_equilibrium_returns(w_mkt, sigma, risk_aversion)
    views = views or []

    if not views:
        # No views: the posterior IS the prior, and the optimal portfolio is the
        # market portfolio. That this falls out automatically is the property that
        # makes the method safe to use.
        weights = w_mkt.rename("black_litterman")
        return BlackLittermanResult(pi.rename("posterior_return"), pi, sigma, weights, w_mkt, views)

    k = len(views)
    n = len(assets)
    P = np.zeros((k, n))
    Q = np.zeros(k)
    omega_diag = np.zeros(k)

    sigma_np = sigma.to_numpy()
    for i, view in enumerate(views):
        for asset, coef in view.assets.items():
            if asset not in assets:
                raise KeyError(f"view references unknown asset {asset!r}")
            P[i, assets.index(asset)] = coef
        Q[i] = view.value
        # Omega: uncertainty of the view. Idzorek's approach ties it to the view's
        # own variance under the prior, scaled by (1 - confidence)/confidence, so a
        # confidence of 1 gives ~zero uncertainty and the posterior matches the view.
        view_var = float(P[i] @ (tau * sigma_np) @ P[i].T)
        omega_diag[i] = max(view_var * (1 - view.confidence) / view.confidence, 1e-10)

    omega = np.diag(omega_diag)
    tau_sigma = tau * sigma_np

    # Posterior mean (the standard closed form).
    try:
        inv_tau_sigma = np.linalg.inv(tau_sigma)
        inv_omega = np.linalg.inv(omega)
        posterior_cov_inv = inv_tau_sigma + P.T @ inv_omega @ P
        posterior_cov_m = np.linalg.inv(posterior_cov_inv)
        mu_post = posterior_cov_m @ (inv_tau_sigma @ pi.to_numpy() + P.T @ inv_omega @ Q)
    except np.linalg.LinAlgError:
        mu_post = pi.to_numpy()
        posterior_cov_m = tau_sigma

    posterior_returns = pd.Series(mu_post, index=assets, name="posterior_return")
    # The covariance used for optimisation is the prior plus posterior parameter
    # uncertainty — ignoring the second term overstates confidence in the tilt.
    posterior_cov = pd.DataFrame(sigma_np + posterior_cov_m, index=assets, columns=assets)

    weights = mean_variance(
        posterior_returns, posterior_cov, risk_aversion=risk_aversion,
        allow_short=allow_short, max_weight=max_weight,
    ).rename("black_litterman")

    return BlackLittermanResult(posterior_returns, pi, posterior_cov, weights, w_mkt, views)


def views_from_signal(
    signal: pd.Series, cov: pd.DataFrame, *, annual_scale: float = 0.10, confidence: float = 0.3
) -> list[View]:
    """Turn a cross-sectional model score into relative Black-Litterman views.

    A model that ranks assets produces exactly what Black-Litterman wants: relative
    views. Each asset's score is converted into a view of it against the panel average,
    scaled so that a maximal score corresponds to `annual_scale` of outperformance.

    `confidence` should be low. A backtested cross-sectional signal with an information
    coefficient of 0.05 justifies a confidence far below 0.5, and setting it high is
    how a modest edge turns into a concentrated bet.
    """
    s = signal.reindex(cov.index).dropna()
    if s.empty or s.abs().max() == 0:
        return []
    normalised = s / s.abs().max()
    demeaned = normalised - normalised.mean()

    views = []
    others = len(demeaned) - 1
    if others < 1:
        return []
    for asset, score in demeaned.items():
        if abs(score) < 1e-6:
            continue
        # Asset versus an equal-weight basket of everything else.
        legs = {asset: 1.0}
        for other in demeaned.index:
            if other != asset:
                legs[other] = -1.0 / others
        views.append(View(legs, float(score * annual_scale), confidence))
    return views
