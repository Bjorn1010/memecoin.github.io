"""Conditional volatility models — GARCH and friends, fitted by maximum likelihood.

Returns are almost unpredictable. Their *variance* is not: volatility clusters, and
that clustering is one of the most robust empirical regularities in finance. Modelling
it properly is worth more than another return feature, because everything downstream —
position size, barrier widths, risk limits, option value — is a function of forecast
volatility.

Three models, in increasing order of realism:

* **EWMA (RiskMetrics)** — one parameter, no fitting, surprisingly hard to beat at
  short horizons. The honest baseline; if a fitted GARCH does not beat it out of
  sample, use this.
* **GARCH(1,1)** — variance reverts to a long-run level, so forecasts mean-revert
  instead of extrapolating the last shock forever. This is what EWMA cannot do.
* **GJR-GARCH** — adds a leverage term: negative returns raise future variance more
  than positive ones of the same size. In equities this asymmetry is large and
  well-documented; in crypto it is present but weaker, and the fitted gamma says
  how much of it is actually in your sample rather than assuming it.

Implemented by direct MLE with scipy rather than pulling in another dependency, and
`forecast` gives the multi-step variance path, which is what a horizon-h position
actually needs — not the one-step number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize


@dataclass
class GarchFit:
    kind: str
    params: dict[str, float]
    loglikelihood: float
    aic: float
    bic: float
    conditional_vol: pd.Series  # per-period sigma, in return units
    persistence: float
    long_run_vol: float
    converged: bool
    n_obs: int
    scale: float = 1.0
    _last_variance: float = field(default=np.nan, repr=False)
    _last_resid: float = field(default=np.nan, repr=False)

    def forecast(self, horizon: int = 24) -> pd.Series:
        """Multi-step-ahead variance forecast, converted back to per-period sigma.

        GARCH forecasts decay geometrically toward the long-run variance at rate
        `persistence`. A model with persistence 0.99 barely reverts within any horizon
        you care about; one at 0.85 is back to normal within days. That number is the
        single most informative output here.
        """
        if not np.isfinite(self._last_variance):
            return pd.Series(dtype="float64")

        p = self.params
        omega = p.get("omega", 0.0)
        alpha = p.get("alpha", 0.0)
        beta = p.get("beta", 0.0)
        gamma = p.get("gamma", 0.0)
        # At h > 1 the sign of the future shock is unknown, so the leverage term
        # contributes its unconditional expectation of one half.
        eff_alpha = alpha + gamma / 2.0

        var = self._last_variance
        resid2 = self._last_resid**2
        indicator = 1.0 if self._last_resid < 0 else 0.0

        out = []
        for h in range(1, horizon + 1):
            if h == 1:
                var = omega + (alpha + gamma * indicator) * resid2 + beta * var
            else:
                var = omega + (eff_alpha + beta) * var
            out.append(var)

        sigma = np.sqrt(np.asarray(out)) / self.scale
        return pd.Series(sigma, index=pd.RangeIndex(1, horizon + 1, name="horizon"), name="sigma")

    def annualised_vol(self, periods_per_year: float = 365 * 24) -> pd.Series:
        return self.conditional_vol * np.sqrt(periods_per_year)

    @property
    def near_integrated(self) -> bool:
        """True when alpha+beta is so close to 1 that the long-run level is unreliable.

        Hourly crypto routinely fits at persistence > 0.99. The long-run variance is
        omega/(1-persistence), so at 0.997 that denominator is 0.003 and the implied
        long-run volatility becomes wildly sensitive to a third-decimal change in the
        fit — it is not a number to trade on. The conditional volatility path and the
        short-horizon forecast remain perfectly usable; it is specifically the
        *long-run* level that is not identified. This is the well-known IGARCH effect,
        not a bug in the fit.
        """
        return bool(np.isfinite(self.persistence) and self.persistence > 0.99)

    def summary(self) -> dict:
        return {
            "kind": self.kind,
            **{k: round(float(v), 6) for k, v in self.params.items()},
            "persistence": round(self.persistence, 4),
            "long_run_annual_vol": round(self.long_run_vol * np.sqrt(365 * 24), 4),
            "long_run_reliable": not self.near_integrated,
            "half_life_of_shock_bars": (
                round(float(np.log(0.5) / np.log(self.persistence)), 1)
                if 0 < self.persistence < 1
                else float("inf")
            ),
            "loglikelihood": round(self.loglikelihood, 2),
            "aic": round(self.aic, 2),
            "bic": round(self.bic, 2),
            "converged": self.converged,
            "n_obs": self.n_obs,
        }


def _prepare(returns: pd.Series) -> tuple[np.ndarray, pd.Index, float]:
    """Clean returns and rescale them.

    Financial returns are ~1e-3, and squaring them gives ~1e-6, which puts the
    likelihood surface in a range where the optimiser's default tolerances are
    meaningless. Rescaling by 100 (i.e. working in percent) is the standard fix and is
    undone when the fit is reported.
    """
    r = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    scale = 100.0
    return r.to_numpy(dtype="float64") * scale, r.index, scale


def _garch_recursion(
    params: np.ndarray, r: np.ndarray, leverage: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Variance path for GARCH(1,1) or GJR-GARCH(1,1,1)."""
    if leverage:
        mu, omega, alpha, gamma, beta = params
    else:
        mu, omega, alpha, beta = params
        gamma = 0.0

    resid = r - mu
    n = resid.size
    var = np.empty(n)
    var[0] = resid.var() if n > 1 else 1.0
    for t in range(1, n):
        prev = resid[t - 1]
        shock = (alpha + (gamma if prev < 0 else 0.0)) * prev**2
        var[t] = omega + shock + beta * var[t - 1]
        if not np.isfinite(var[t]) or var[t] <= 0:
            var[t] = 1e-12
    return var, resid


def _neg_loglik(params: np.ndarray, r: np.ndarray, leverage: bool) -> float:
    """Gaussian negative log-likelihood, with the stationarity constraint enforced."""
    if leverage:
        _, omega, alpha, gamma, beta = params
        persistence = alpha + gamma / 2.0 + beta
    else:
        _, omega, alpha, beta = params
        gamma = 0.0
        persistence = alpha + beta

    if omega <= 0 or alpha < 0 or beta < 0 or (leverage and alpha + gamma < 0):
        return 1e10
    if persistence >= 0.9999:  # non-stationary: variance would explode
        return 1e10

    var, resid = _garch_recursion(params, r, leverage)
    if not np.all(np.isfinite(var)) or np.any(var <= 0):
        return 1e10
    ll = -0.5 * np.sum(np.log(2 * np.pi) + np.log(var) + resid**2 / var)
    return -ll if np.isfinite(ll) else 1e10


def fit_garch(returns: pd.Series, leverage: bool = False) -> GarchFit:
    """Fit GARCH(1,1), or GJR-GARCH(1,1,1) with `leverage=True`."""
    r, index, scale = _prepare(returns)
    n = r.size
    if n < 100:
        raise ValueError(f"GARCH needs at least ~100 observations, got {n}")

    var_r = float(r.var())
    if leverage:
        # (mu, omega, alpha, gamma, beta)
        x0 = np.array([r.mean(), var_r * 0.05, 0.03, 0.04, 0.90])
        bounds = [(-10, 10), (1e-8, var_r * 10), (0.0, 0.5), (-0.2, 0.5), (0.0, 0.999)]
    else:
        x0 = np.array([r.mean(), var_r * 0.05, 0.06, 0.90])
        bounds = [(-10, 10), (1e-8, var_r * 10), (0.0, 0.5), (0.0, 0.999)]

    res = optimize.minimize(
        _neg_loglik, x0, args=(r, leverage), method="L-BFGS-B", bounds=bounds,
        options={"maxiter": 1000, "ftol": 1e-9},
    )
    var, resid = _garch_recursion(res.x, r, leverage)

    if leverage:
        mu, omega, alpha, gamma, beta = res.x
        names = {"mu": mu / scale, "omega": omega, "alpha": alpha, "gamma": gamma, "beta": beta}
        persistence = alpha + gamma / 2.0 + beta
    else:
        mu, omega, alpha, beta = res.x
        gamma = 0.0
        names = {"mu": mu / scale, "omega": omega, "alpha": alpha, "beta": beta}
        persistence = alpha + beta

    k = len(res.x)
    ll = -res.fun
    long_run_var = omega / max(1 - persistence, 1e-9)

    return GarchFit(
        kind="GJR-GARCH(1,1,1)" if leverage else "GARCH(1,1)",
        params=names,
        loglikelihood=float(ll),
        aic=float(2 * k - 2 * ll),
        bic=float(k * np.log(n) - 2 * ll),
        conditional_vol=pd.Series(np.sqrt(var) / scale, index=index, name="sigma"),
        persistence=float(persistence),
        long_run_vol=float(np.sqrt(long_run_var) / scale),
        converged=bool(res.success),
        n_obs=n,
        scale=scale,
        _last_variance=float(var[-1]),
        _last_resid=float(resid[-1]),
    )


def fit_ewma(returns: pd.Series, lam: float = 0.94) -> GarchFit:
    """RiskMetrics EWMA: a GARCH(1,1) with omega=0 and alpha+beta constrained to 1.

    lam=0.94 is the RiskMetrics daily default. No parameters are estimated, so it
    cannot overfit — which is exactly why it is the benchmark a fitted model has to
    beat out of sample before it earns its place.
    """
    r, index, scale = _prepare(returns)
    n = r.size
    var = np.empty(n)
    var[0] = float(r.var()) if n > 1 else 1.0
    for t in range(1, n):
        var[t] = lam * var[t - 1] + (1 - lam) * r[t - 1] ** 2

    resid = r - r.mean()
    ll = -0.5 * np.sum(np.log(2 * np.pi) + np.log(var) + resid**2 / var)
    return GarchFit(
        kind=f"EWMA(lambda={lam})",
        params={"lambda": lam, "omega": 0.0, "alpha": 1 - lam, "beta": lam},
        loglikelihood=float(ll),
        aic=float(-2 * ll),
        bic=float(-2 * ll),
        conditional_vol=pd.Series(np.sqrt(var) / scale, index=index, name="sigma"),
        persistence=1.0,  # by construction: EWMA never mean-reverts
        long_run_vol=float(np.sqrt(r.var()) / scale),
        converged=True,
        n_obs=n,
        scale=scale,
        _last_variance=float(var[-1]),
        _last_resid=float(resid[-1]),
    )


def compare_models(returns: pd.Series) -> pd.DataFrame:
    """Fit the family and rank by BIC.

    BIC rather than AIC: it penalises parameters harder, which is the right bias when
    the sample is noisy and the cost of an over-parameterised model is a confident
    wrong forecast.
    """
    rows = []
    for name, fn in (
        ("ewma", lambda: fit_ewma(returns)),
        ("garch", lambda: fit_garch(returns, leverage=False)),
        ("gjr", lambda: fit_garch(returns, leverage=True)),
    ):
        try:
            fit = fn()
        except Exception as exc:  # a failed fit is information, not a crash
            rows.append({"model": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        rows.append({"model": name, **fit.summary()})
    return pd.DataFrame(rows).sort_values("bic", na_position="last").reset_index(drop=True)


def volatility_forecast_score(
    returns: pd.Series, fit: GarchFit, horizon: int = 1
) -> dict:
    """Score a volatility forecast against realised variance, in-sample.

    Uses QLIKE alongside MSE. MSE on variance is dominated by the few largest
    observations and will happily rank a model that is wrong everywhere but calm as
    the best. QLIKE is the loss function the volatility-forecasting literature settled
    on precisely because it is robust to that, and it is the one to read.
    """
    sigma = fit.conditional_vol.shift(horizon).dropna()
    r = pd.Series(returns).reindex(sigma.index).dropna()
    sigma = sigma.reindex(r.index)
    realised = r**2
    var = sigma**2
    # QLIKE contains log(realised/forecast), so a bar whose return was exactly zero
    # sends it to infinity. Those bars carry no information about forecast quality
    # anyway, so they are excluded from QLIKE while still counting toward MSE.
    finite = (var > 0) & np.isfinite(realised)
    if finite.sum() < 10:
        return {"mse": np.nan, "qlike": np.nan, "n": int(finite.sum())}

    mse = float(np.mean((realised[finite] - var[finite]) ** 2))
    positive = finite & (realised > 0)
    if positive.sum() < 10:
        qlike = np.nan
    else:
        ratio = realised[positive] / var[positive]
        qlike = float(np.mean(ratio - np.log(ratio) - 1))
    return {
        "mse": mse,
        "qlike": qlike,
        "n": int(finite.sum()),
        "n_zero_returns_excluded": int(finite.sum() - positive.sum()),
        "model": fit.kind,
    }
