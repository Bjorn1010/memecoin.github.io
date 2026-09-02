"""The volatility surface: what the options market thinks, expressed as a tradeable object.

A single implied-volatility number is not enough. Implied vol varies with strike (the
smile/skew) and with maturity (the term structure), and the *shape* carries information
that the level does not:

* **Skew** — the price of downside protection relative to upside. Crypto's skew flips
  sign, unlike equities: in a bull market calls can be bid above puts. A skew that
  steepens to the downside is the market paying up for crash protection, and it is one
  of the few genuinely forward-looking positioning indicators available.
* **Term structure** — front-month implied above back-month (backwardation) means the
  market expects near-term turbulence. It inverts before events and normalises after,
  and the shape is a cleaner regime signal than the level of vol itself.
* **Variance risk premium** — implied variance minus subsequent realised variance. It
  is positive on average because someone is being paid to insure, and its size varies
  hugely with regime.

`SVIParams` implements the Stochastic Volatility Inspired parameterisation, which is
the industry standard for fitting a smile. Its value over a polynomial fit is that it
is arbitrage-free by construction when its parameters satisfy simple constraints — a
polynomial fit through five quotes will happily produce a surface implying negative
probability density, and any model built on it inherits that nonsense.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize

from .black_scholes import implied_volatility


@dataclass
class SVIParams:
    """Raw SVI: w(k) = a + b * (rho*(k-m) + sqrt((k-m)^2 + sigma^2))

    where w is total implied variance (sigma^2 * T) and k is log-moneyness log(K/F).

    * a — overall variance level
    * b — slope of the wings (how fast vol rises away from the money)
    * rho — asymmetry, in [-1, 1]. Negative means downside skew.
    * m — horizontal shift of the smile's minimum
    * sigma — curvature at the minimum (how rounded the smile is)
    """

    a: float
    b: float
    rho: float
    m: float
    sigma: float
    T: float

    def total_variance(self, k: np.ndarray | float) -> np.ndarray | float:
        k = np.asarray(k, dtype="float64")
        return self.a + self.b * (self.rho * (k - self.m) + np.sqrt((k - self.m) ** 2 + self.sigma**2))

    def implied_vol(self, k: np.ndarray | float) -> np.ndarray | float:
        w = self.total_variance(k)
        w = np.maximum(w, 1e-12)
        return np.sqrt(w / self.T) if self.T > 0 else np.full_like(np.asarray(w, dtype="float64"), np.nan)

    def is_arbitrage_free(self) -> dict:
        """Check the standard no-butterfly-arbitrage conditions on the parameters."""
        checks = {
            "b_non_negative": self.b >= 0,
            "rho_in_range": abs(self.rho) <= 1,
            "sigma_positive": self.sigma > 0,
            # a + b*sigma*sqrt(1-rho^2) >= 0 keeps total variance non-negative
            # everywhere, which is the minimum condition for a valid density.
            "variance_non_negative": self.a + self.b * self.sigma * np.sqrt(max(1 - self.rho**2, 0)) >= 0,
            # Durrleman's condition (necessary form): wings cannot be steeper than 4.
            "wing_slope_bounded": self.b * (1 + abs(self.rho)) <= 4.0 / max(self.T, 1e-9) if self.T > 0 else True,
        }
        return {"arbitrage_free": all(checks.values()), **checks}

    def skew(self, k: float = 0.0) -> float:
        """d(implied vol)/d(log-moneyness) at k — the local slope of the smile."""
        eps = 1e-4
        return float((self.implied_vol(k + eps) - self.implied_vol(k - eps)) / (2 * eps))

    def to_dict(self) -> dict:
        return {"a": self.a, "b": self.b, "rho": self.rho, "m": self.m, "sigma": self.sigma, "T": self.T}


def fit_svi(
    log_moneyness: np.ndarray, implied_vols: np.ndarray, T: float, *, weights: np.ndarray | None = None
) -> SVIParams:
    """Fit a raw-SVI smile to observed implied volatilities.

    Weighted least squares on *total variance* rather than on vol, because that is the
    quantity SVI is linear-ish in and it avoids over-weighting the far wings where
    quotes are least reliable.
    """
    k = np.asarray(log_moneyness, dtype="float64")
    iv = np.asarray(implied_vols, dtype="float64")
    mask = np.isfinite(k) & np.isfinite(iv) & (iv > 0)
    k, iv = k[mask], iv[mask]
    if k.size < 5:
        raise ValueError(f"SVI needs at least 5 valid quotes, got {k.size}")

    w_obs = iv**2 * T  # observed total variance
    weight = np.ones_like(k) if weights is None else np.asarray(weights, dtype="float64")[mask]

    def residuals(params):
        a, b, rho, m, sigma = params
        model = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma**2))
        return (model - w_obs) * weight

    atm_var = float(np.median(w_obs))
    x0 = np.array([atm_var * 0.5, 0.1, -0.3, 0.0, 0.1])
    bounds = (
        [-np.inf, 0.0, -0.999, -2.0, 1e-6],
        [np.inf, 10.0, 0.999, 2.0, 5.0],
    )
    result = optimize.least_squares(residuals, x0, bounds=bounds, max_nfev=5000)
    a, b, rho, m, sigma = result.x
    return SVIParams(float(a), float(b), float(rho), float(m), float(sigma), float(T))


def build_surface(quotes: pd.DataFrame, spot: float, r: float = 0.0) -> dict:
    """Fit an SVI smile per maturity from a table of option quotes.

    `quotes` needs columns: strike, expiry_years, price, option ('call'/'put').
    Implied vols are solved per quote, then a smile is fitted per expiry.

    Quotes whose implied vol cannot be recovered (arbitrage-violating or stale) are
    dropped and counted, not silently skipped — a maturity where half the quotes fail
    to invert is telling you the feed is broken, not that the smile is unusual.
    """
    required = {"strike", "expiry_years", "price", "option"}
    missing = required - set(quotes.columns)
    if missing:
        raise KeyError(f"quotes is missing columns: {sorted(missing)}")

    rows = []
    for _, q in quotes.iterrows():
        iv = implied_volatility(
            float(q["price"]), spot, float(q["strike"]), float(q["expiry_years"]), r, str(q["option"])
        )
        forward = spot * np.exp(r * float(q["expiry_years"]))
        rows.append(
            {
                "strike": float(q["strike"]),
                "expiry_years": float(q["expiry_years"]),
                "log_moneyness": float(np.log(q["strike"] / forward)) if forward > 0 else np.nan,
                "implied_vol": iv,
                "option": q["option"],
            }
        )
    table = pd.DataFrame(rows)
    valid = table.dropna(subset=["implied_vol", "log_moneyness"])

    smiles = {}
    for T, group in valid.groupby("expiry_years"):
        if len(group) < 5:
            continue
        try:
            smiles[float(T)] = fit_svi(
                group["log_moneyness"].to_numpy(), group["implied_vol"].to_numpy(), float(T)
            )
        except (ValueError, RuntimeError):
            continue

    return {
        "quotes": table,
        "n_quotes": len(table),
        "n_inverted": len(valid),
        "n_failed": len(table) - len(valid),
        "smiles": smiles,
        "expiries": sorted(smiles),
        "term_structure": term_structure(smiles),
    }


def term_structure(smiles: dict[float, SVIParams]) -> pd.DataFrame:
    """At-the-money implied vol and skew by maturity."""
    rows = []
    for T in sorted(smiles):
        svi = smiles[T]
        rows.append(
            {
                "expiry_years": T,
                "expiry_days": T * 365,
                "atm_vol": float(svi.implied_vol(0.0)),
                "skew": svi.skew(0.0),
                "arbitrage_free": svi.is_arbitrage_free()["arbitrage_free"],
            }
        )
    out = pd.DataFrame(rows)
    if len(out) >= 2:
        # Backwardation: front vol above back vol. Signals expected near-term stress.
        out.attrs["backwardated"] = bool(out["atm_vol"].iloc[0] > out["atm_vol"].iloc[-1])
        out.attrs["slope"] = float(out["atm_vol"].iloc[-1] - out["atm_vol"].iloc[0])
    return out


def variance_swap_strike(
    smile: SVIParams, *, forward: float = 1.0, n_points: int = 800, width: float = 2.0
) -> float:
    """Fair strike of a variance swap, by static replication in the option strip.

    This is the Carr-Madan / Demeterfi result that VIX and DVOL are built on:

        K_var = (2/T) * [ ∫_0^F P(K)/K² dK + ∫_F^∞ C(K)/K² dK ]

    i.e. a portfolio of out-of-the-money options weighted by 1/K². The 1/K² weighting
    is what makes it *variance* rather than a directional bet, and it is why the far
    downside wing matters so much: those puts are cheap in absolute terms but carry
    enormous weight in the integral.

    This is the right thing to compare realised volatility against — better than ATM
    implied vol, which ignores the wings where most of the variance premium sits.

    `width` truncates the strip at ±`width` in log-moneyness, and **the result is
    genuinely sensitive to where you cut**: on a smile whose wings rise steeply, the
    strike keeps climbing as the strip widens, because the 1/K² weight keeps finding
    variance out there. Set `width` to the range where real quotes exist (typically
    ±1 to ±1.5 for crypto, roughly the 10-delta wings) rather than integrating into
    the region where the smile is pure extrapolation and the number becomes an
    artefact of the fit rather than a market price.

    Sanity check built into the tests: on a flat smile the result equals the flat
    volatility exactly, which is the identity this replication must satisfy.

    Returns the fair *volatility*, i.e. sqrt of the variance strike.
    """
    if smile.T <= 0 or forward <= 0:
        return float("nan")

    from .black_scholes import black_scholes_price

    # Strike grid, log-spaced so the 1/K² weight is sampled evenly in log-moneyness.
    k = np.linspace(-width, width, n_points)
    strikes = forward * np.exp(k)

    # Price each OTM option off the smile, discounting at zero since we work off the
    # forward directly (the forward already carries the rate).
    prices = np.empty_like(strikes)
    for i, (strike, log_m) in enumerate(zip(strikes, k)):
        iv = float(smile.implied_vol(log_m))
        if not np.isfinite(iv) or iv <= 0:
            prices[i] = 0.0
            continue
        option = "put" if strike < forward else "call"
        prices[i] = black_scholes_price(forward, float(strike), smile.T, 0.0, iv, option)

    integrand = prices / strikes**2
    integral = float(np.trapezoid(integrand, strikes))
    variance_strike = 2.0 / smile.T * integral
    return float(np.sqrt(max(variance_strike, 0.0)))


def variance_risk_premium(
    implied_vol: pd.Series, realised_vol: pd.Series, *, forward_periods: int = 720
) -> pd.DataFrame:
    """Implied volatility minus the volatility that subsequently realised.

    The alignment is the whole point and the easiest thing to get wrong: implied vol at
    time t is a forecast of the volatility between t and t+horizon, so it must be
    compared with *forward* realised volatility, not with trailing. Comparing implied
    against trailing realised produces a series that looks predictive and is not.

    A persistently positive premium means volatility sellers are paid — which they
    historically are, in exchange for occasionally catastrophic losses.
    """
    iv = pd.Series(implied_vol).dropna()
    rv = pd.Series(realised_vol).reindex(iv.index)
    forward_rv = rv.shift(-forward_periods)

    out = pd.DataFrame({"implied_vol": iv, "forward_realised_vol": forward_rv})
    out["vrp"] = out["implied_vol"] - out["forward_realised_vol"]
    out["vrp_ratio"] = out["implied_vol"] / out["forward_realised_vol"].replace(0.0, np.nan)
    out.attrs["mean_vrp"] = float(out["vrp"].mean())
    out.attrs["pct_positive"] = float((out["vrp"] > 0).mean())
    out.attrs["note"] = (
        "implied at t is compared against realised over t..t+horizon, not trailing "
        "realised — the trailing comparison looks predictive and is an artefact"
    )
    return out


def realised_volatility(
    returns: pd.Series, window: int = 720, periods_per_year: float = 365 * 24
) -> pd.Series:
    """Trailing annualised realised volatility, to compare against implied."""
    return returns.rolling(window, min_periods=max(window // 4, 20)).std(ddof=1) * np.sqrt(periods_per_year)
