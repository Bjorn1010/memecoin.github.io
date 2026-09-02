"""Stochastic volatility and jumps — models that can actually produce a smile.

Black-Scholes assumes volatility is a constant. That assumption implies every strike
should trade at the same implied vol, i.e. that the smile does not exist. The smile
does exist, in every market, and it is the most visible evidence that the model is
wrong. Two extensions fix the two things Black-Scholes is missing:

* **Heston** — volatility is itself a mean-reverting stochastic process, correlated
  with the spot. The correlation `rho` produces skew (negative rho makes downside vol
  higher, which is what equity markets show), and the vol-of-vol `sigma` produces the
  curvature of the smile. It explains the *shape* at longer maturities.
* **Merton jump-diffusion** — the price occasionally jumps. This is what generates the
  steep short-dated smile that a pure diffusion model cannot: over one week a diffusion
  simply cannot reach a strike 30% away with meaningful probability, so it prices deep
  wings near zero, while the market prices them well above that because everyone knows
  crypto gaps.

Together they cover the two mechanisms behind the shape of a real surface, and both are
priced here by **Fourier inversion of the characteristic function** (Carr-Madan /
Lewis). The characteristic function is available in closed form for both models even
though the density is not — which is the entire reason this technique exists, and why
a numerical-methods reference is the right source for it.

Practical use in a spot-only system: fit these to the observed surface and the fitted
parameters *are* the read on the market. A large negative rho means the market is
paying for crash protection; a high jump intensity means it expects gaps.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, optimize


# ---------------------------------------------------------------------------
# Heston
# ---------------------------------------------------------------------------
@dataclass
class HestonParams:
    """Heston (1993) stochastic volatility.

        dS = mu*S dt + sqrt(v)*S dW1
        dv = kappa*(theta - v) dt + sigma*sqrt(v) dW2,   corr(dW1, dW2) = rho

    * `v0` — current instantaneous variance (today's vol squared)
    * `kappa` — speed of mean reversion of variance
    * `theta` — long-run variance
    * `sigma` — vol of vol; drives the smile's curvature
    * `rho` — spot/vol correlation; drives the skew. Negative = downside skew.
    """

    v0: float
    kappa: float
    theta: float
    sigma: float
    rho: float

    @property
    def feller_satisfied(self) -> bool:
        """2*kappa*theta > sigma^2 keeps variance strictly positive.

        Violated fits are common and not fatal for pricing, but they mean the variance
        process can touch zero, so simulation needs a scheme that handles it and the
        parameters should be treated as a fitting device rather than a description.
        """
        return 2 * self.kappa * self.theta > self.sigma**2

    def to_dict(self) -> dict:
        return {
            "v0": self.v0, "kappa": self.kappa, "theta": self.theta,
            "sigma": self.sigma, "rho": self.rho,
            "long_run_vol": float(np.sqrt(max(self.theta, 0.0))),
            "current_vol": float(np.sqrt(max(self.v0, 0.0))),
            "feller_satisfied": self.feller_satisfied,
        }


def heston_characteristic_function(
    u: complex | np.ndarray, S: float, T: float, r: float, params: HestonParams, q: float = 0.0
):
    """E[exp(i*u*log(S_T))] under the risk-neutral measure.

    Uses the "little Heston trap" formulation (Albrecher et al.): mathematically
    equivalent to the original but numerically stable for long maturities, where the
    original branch of the complex logarithm crosses a cut and the price silently
    becomes garbage.
    """
    v0, kappa, theta, sigma, rho = params.v0, params.kappa, params.theta, params.sigma, params.rho
    x = np.log(S)
    a = kappa * theta

    d = np.sqrt((rho * sigma * 1j * u - kappa) ** 2 + sigma**2 * (1j * u + u**2))
    # g2 (rather than g1) is the stable branch.
    g = (kappa - rho * sigma * 1j * u - d) / (kappa - rho * sigma * 1j * u + d)

    exp_dt = np.exp(-d * T)
    C = (r - q) * 1j * u * T + (a / sigma**2) * (
        (kappa - rho * sigma * 1j * u - d) * T - 2 * np.log((1 - g * exp_dt) / (1 - g))
    )
    D = ((kappa - rho * sigma * 1j * u - d) / sigma**2) * ((1 - exp_dt) / (1 - g * exp_dt))
    return np.exp(C + D * v0 + 1j * u * x)


def _carr_madan_price(
    char_fn, S: float, K: float, T: float, r: float, alpha: float = 1.5, n: int = 4096, eta: float = 0.25
) -> float:
    """Carr-Madan FFT-style pricing of a European call via the characteristic function.

    `alpha` is the damping factor that makes the modified call price integrable; 1.5 is
    the standard choice and the result is insensitive to it over a wide range.
    """
    k = np.log(K)
    u = np.arange(n) * eta
    # Shift by (alpha+1)i: the damping that makes the Fourier transform well-defined.
    denominator = alpha**2 + alpha - u**2 + 1j * (2 * alpha + 1) * u
    psi = np.exp(-r * T) * char_fn(u - (alpha + 1) * 1j) / denominator

    # Simpson weights for the quadrature.
    weights = np.ones(n)
    weights[1:-1:2] = 4.0
    weights[2:-1:2] = 2.0
    weights = weights * eta / 3.0

    integrand = np.real(np.exp(-1j * u * k) * psi * weights)
    price = np.exp(-alpha * k) / np.pi * integrand.sum()
    return float(max(price, 0.0))


def heston_price(
    S: float, K: float, T: float, r: float, params: HestonParams, option: str = "call", q: float = 0.0
) -> float:
    """European option price under Heston."""
    if T <= 0:
        return float(max(S - K, 0.0) if option == "call" else max(K - S, 0.0))

    call = _carr_madan_price(
        lambda u: heston_characteristic_function(u, S, T, r, params, q), S, K, T, r
    )
    if option == "call":
        return call
    # Put-call parity rather than a second integration: fewer numerical artefacts.
    return float(call - S * np.exp(-q * T) + K * np.exp(-r * T))


def heston_implied_vol(
    S: float, K: float, T: float, r: float, params: HestonParams, q: float = 0.0
) -> float:
    """Heston price converted back to a Black-Scholes implied vol.

    This is how a stochastic-vol model is compared with the market: price under Heston,
    invert through Black-Scholes, and you have the smile the model implies.
    """
    from .black_scholes import implied_volatility

    price = heston_price(S, K, T, r, params, "call", q)
    return implied_volatility(price, S, K, T, r, "call", q)


def heston_smile(
    S: float, T: float, r: float, params: HestonParams, log_moneyness=None, q: float = 0.0
) -> "object":
    """The implied-vol smile the model generates, across log-moneyness."""
    import pandas as pd

    k = np.linspace(-0.5, 0.5, 21) if log_moneyness is None else np.asarray(log_moneyness)
    forward = S * np.exp((r - q) * T)
    rows = []
    for log_m in k:
        strike = forward * np.exp(log_m)
        rows.append(
            {
                "log_moneyness": float(log_m),
                "strike": float(strike),
                "implied_vol": heston_implied_vol(S, strike, T, r, params, q),
            }
        )
    return pd.DataFrame(rows)


def calibrate_heston(
    strikes, market_vols, S: float, T: float, r: float, q: float = 0.0, *, x0=None
) -> HestonParams:
    """Fit Heston parameters to an observed smile by least squares on implied vol.

    Fitting on vol rather than on price is deliberate: prices vary by orders of
    magnitude across strikes, so a price-space fit is dominated by the near-the-money
    options and ignores the wings, which are the part that carries the skew
    information you are trying to capture.
    """
    strikes = np.asarray(strikes, dtype="float64")
    market_vols = np.asarray(market_vols, dtype="float64")
    mask = np.isfinite(strikes) & np.isfinite(market_vols) & (market_vols > 0)
    strikes, market_vols = strikes[mask], market_vols[mask]
    if strikes.size < 5:
        raise ValueError(f"Heston calibration needs >=5 quotes, got {strikes.size}")

    atm_var = float(np.median(market_vols) ** 2)
    x0 = x0 if x0 is not None else np.array([atm_var, 2.0, atm_var, 0.5, -0.5])

    def residuals(x):
        params = HestonParams(*x)
        model = np.array([heston_implied_vol(S, float(k), T, r, params, q) for k in strikes])
        model = np.nan_to_num(model, nan=1e3)  # penalise parameter sets that fail to price
        return model - market_vols

    bounds = (
        [1e-6, 0.01, 1e-6, 1e-3, -0.999],
        [4.0, 20.0, 4.0, 5.0, 0.999],
    )
    result = optimize.least_squares(residuals, x0, bounds=bounds, max_nfev=300, xtol=1e-8)
    return HestonParams(*[float(v) for v in result.x])


# ---------------------------------------------------------------------------
# Merton jump-diffusion
# ---------------------------------------------------------------------------
@dataclass
class MertonJumpParams:
    """Merton (1976) jump-diffusion: diffusion plus a compound Poisson jump process.

    * `sigma` — diffusive volatility
    * `lam` — jump intensity, expected jumps per year
    * `mu_j` — mean log jump size (negative = crashes more likely than melt-ups)
    * `sigma_j` — jump size volatility

    This is the model that explains the *short-dated* smile. A pure diffusion cannot
    reach a far strike in a week, so it prices the wings near zero; the market does not,
    because everyone knows the price can gap. Jump intensity fitted to a crypto surface
    comes out high, which is simply the market saying so.
    """

    sigma: float
    lam: float
    mu_j: float
    sigma_j: float

    @property
    def expected_jumps_per_year(self) -> float:
        return self.lam

    @property
    def annual_jump_variance(self) -> float:
        return self.lam * (self.mu_j**2 + self.sigma_j**2)

    def to_dict(self) -> dict:
        total_var = self.sigma**2 + self.annual_jump_variance
        return {
            "sigma": self.sigma, "lambda": self.lam, "mu_j": self.mu_j, "sigma_j": self.sigma_j,
            "total_vol": float(np.sqrt(total_var)),
            # How much of total variance comes from jumps rather than diffusion —
            # the single most informative number the fit produces.
            "jump_share_of_variance": float(self.annual_jump_variance / total_var) if total_var > 0 else np.nan,
        }


def merton_price(
    S: float, K: float, T: float, r: float, params: MertonJumpParams, option: str = "call",
    q: float = 0.0, n_terms: int = 60,
) -> float:
    """Merton jump-diffusion price, as a Poisson-weighted sum of Black-Scholes prices.

    Conditional on exactly n jumps occurring, the price is Black-Scholes with adjusted
    drift and volatility; the unconditional price is the Poisson-weighted average. The
    series converges fast — 60 terms is far more than enough for any realistic lambda*T.
    """
    from .black_scholes import black_scholes_price

    if T <= 0:
        return float(max(S - K, 0.0) if option == "call" else max(K - S, 0.0))

    sigma, lam, mu_j, sigma_j = params.sigma, params.lam, params.mu_j, params.sigma_j
    # Compensator: keeps the discounted price a martingale despite the jumps.
    kappa = np.exp(mu_j + 0.5 * sigma_j**2) - 1.0
    lam_prime = lam * (1.0 + kappa)

    total = 0.0
    log_factorial = 0.0
    for n in range(n_terms):
        if n > 0:
            log_factorial += np.log(n)
        log_weight = -lam_prime * T + n * np.log(max(lam_prime * T, 1e-300)) - log_factorial
        weight = np.exp(log_weight)
        if weight < 1e-12 and n > 5:
            break
        sigma_n = np.sqrt(sigma**2 + n * sigma_j**2 / T) if T > 0 else sigma
        r_n = r - lam * kappa + n * (mu_j + 0.5 * sigma_j**2) / T
        total += weight * black_scholes_price(S, K, T, r_n, sigma_n, option, q)
    return float(max(total, 0.0))


def merton_implied_vol(
    S: float, K: float, T: float, r: float, params: MertonJumpParams, q: float = 0.0
) -> float:
    from .black_scholes import implied_volatility

    price = merton_price(S, K, T, r, params, "call", q)
    return implied_volatility(price, S, K, T, r, "call", q)


def calibrate_merton(
    strikes, market_vols, S: float, T: float, r: float, q: float = 0.0
) -> MertonJumpParams:
    """Fit jump-diffusion parameters to an observed smile."""
    strikes = np.asarray(strikes, dtype="float64")
    market_vols = np.asarray(market_vols, dtype="float64")
    mask = np.isfinite(strikes) & np.isfinite(market_vols) & (market_vols > 0)
    strikes, market_vols = strikes[mask], market_vols[mask]
    if strikes.size < 4:
        raise ValueError(f"Merton calibration needs >=4 quotes, got {strikes.size}")

    atm_vol = float(np.median(market_vols))
    x0 = np.array([atm_vol * 0.8, 1.0, -0.05, 0.15])

    def residuals(x):
        params = MertonJumpParams(*x)
        model = np.array([merton_implied_vol(S, float(k), T, r, params, q) for k in strikes])
        model = np.nan_to_num(model, nan=1e3)
        return model - market_vols

    bounds = ([1e-3, 0.0, -1.0, 1e-4], [5.0, 100.0, 1.0, 2.0])
    result = optimize.least_squares(residuals, x0, bounds=bounds, max_nfev=300, xtol=1e-8)
    return MertonJumpParams(*[float(v) for v in result.x])


def simulate_heston(
    S0: float, T: float, r: float, params: HestonParams, *, n_paths: int = 10_000,
    n_steps: int = 252, seed: int = 0, q: float = 0.0,
):
    """Monte Carlo simulation of Heston paths (full-truncation Euler).

    Full truncation — using max(v, 0) wherever variance is needed while letting the
    variance state itself go negative — is the standard fix for the fact that a naive
    Euler discretisation of the CIR variance process regularly produces negative
    variance and then NaN. It has the lowest bias of the simple schemes.

    Useful for pricing path-dependent payoffs and for generating realistic synthetic
    price paths with a *stochastic* vol structure, which is a much better stress test
    for a strategy than Gaussian noise.
    """
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    v0, kappa, theta, sigma, rho = params.v0, params.kappa, params.theta, params.sigma, params.rho

    log_s = np.full(n_paths, np.log(S0))
    v = np.full(n_paths, v0)
    paths = np.empty((n_steps + 1, n_paths))
    paths[0] = S0

    for t in range(1, n_steps + 1):
        z1 = rng.standard_normal(n_paths)
        z2 = rho * z1 + np.sqrt(max(1 - rho**2, 0.0)) * rng.standard_normal(n_paths)
        v_pos = np.maximum(v, 0.0)
        log_s += (r - q - 0.5 * v_pos) * dt + np.sqrt(v_pos * dt) * z1
        v = v + kappa * (theta - v_pos) * dt + sigma * np.sqrt(v_pos * dt) * z2
        paths[t] = np.exp(log_s)

    return paths
