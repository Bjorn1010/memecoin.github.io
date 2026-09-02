"""Black-Scholes pricing, greeks and implied volatility.

Why a spot-only, paper-only system carries an options module at all: the options market
is where volatility is *priced*, and that price is information a spot trader cannot get
any other way. Three uses that need nothing but the formulas below:

* **Implied vs realised** — the variance risk premium. Implied volatility exceeds
  subsequent realised volatility on average, and the size of that gap is one of the
  cleanest regime indicators available for free (Deribit publishes DVOL).
* **Skew as positioning** — when downside puts are bid relative to upside calls, the
  market is paying for crash protection. Skew steepening has historically preceded
  spot weakness more reliably than any price-based indicator.
* **Greeks as a risk language** — delta, gamma and vega are how a professional book
  describes its exposure, and they are the right vocabulary even for a linear
  portfolio: a stop-loss is short gamma, a vol-targeted position is short vega.

The implied-volatility solver uses Brent on a bracketed interval rather than
Newton-Raphson. Newton is faster and fails exactly where it matters — deep out-of-the-
money options, where vega approaches zero and the update step explodes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, stats


@dataclass
class Greeks:
    price: float
    delta: float  # d(price)/d(spot)
    gamma: float  # d(delta)/d(spot)
    vega: float  # d(price)/d(vol), per 1 vol point (0.01)
    theta: float  # d(price)/d(time), per day
    rho: float  # d(price)/d(rate), per 1% rate

    def to_dict(self) -> dict:
        return {
            "price": self.price, "delta": self.delta, "gamma": self.gamma,
            "vega": self.vega, "theta": self.theta, "rho": self.rho,
        }


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return np.nan, np.nan
    vol_sqrt_t = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def black_scholes_price(
    S: float, K: float, T: float, r: float, sigma: float, option: str = "call", q: float = 0.0
) -> float:
    """European option price. `q` is the continuous dividend / borrow yield.

    At expiry (T <= 0) returns intrinsic value, which is the correct limit and avoids
    a division by zero that would otherwise propagate NaN through a whole book.
    """
    if T <= 0:
        intrinsic = max(S - K, 0.0) if option == "call" else max(K - S, 0.0)
        return float(intrinsic)
    if sigma <= 0:
        forward = S * np.exp(-q * T) - K * np.exp(-r * T)
        return float(max(forward, 0.0) if option == "call" else max(-forward, 0.0))

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    if option == "call":
        return float(S * np.exp(-q * T) * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2))
    if option == "put":
        return float(K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * np.exp(-q * T) * stats.norm.cdf(-d1))
    raise ValueError(f"option must be 'call' or 'put', got {option!r}")


def greeks(
    S: float, K: float, T: float, r: float, sigma: float, option: str = "call", q: float = 0.0
) -> Greeks:
    """Full first- and second-order sensitivities.

    Vega is reported per volatility *point* (a 0.01 move) and theta per calendar day,
    which is how they are quoted on a desk — the raw per-unit-of-sigma and per-year
    forms are off by factors that make them useless for sizing.
    """
    price = black_scholes_price(S, K, T, r, sigma, option, q)
    if T <= 0 or sigma <= 0:
        delta = (1.0 if S > K else 0.0) if option == "call" else (-1.0 if S < K else 0.0)
        return Greeks(price, delta, 0.0, 0.0, 0.0, 0.0)

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    pdf_d1 = stats.norm.pdf(d1)
    disc_q, disc_r = np.exp(-q * T), np.exp(-r * T)
    sqrt_t = np.sqrt(T)

    if option == "call":
        delta = disc_q * stats.norm.cdf(d1)
        theta = (
            -S * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
            - r * K * disc_r * stats.norm.cdf(d2)
            + q * S * disc_q * stats.norm.cdf(d1)
        )
        rho = K * T * disc_r * stats.norm.cdf(d2) / 100.0
    else:
        delta = -disc_q * stats.norm.cdf(-d1)
        theta = (
            -S * disc_q * pdf_d1 * sigma / (2 * sqrt_t)
            + r * K * disc_r * stats.norm.cdf(-d2)
            - q * S * disc_q * stats.norm.cdf(-d1)
        )
        rho = -K * T * disc_r * stats.norm.cdf(-d2) / 100.0

    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf_d1 * sqrt_t / 100.0  # per 1 vol point

    return Greeks(price, float(delta), float(gamma), float(vega), float(theta / 365.0), float(rho))


def implied_volatility(
    price: float, S: float, K: float, T: float, r: float, option: str = "call", q: float = 0.0,
    lower: float = 1e-4, upper: float = 10.0,
) -> float:
    """Back out the volatility that reproduces an observed option price.

    Brent's method on a bracketed interval: robust where Newton-Raphson is not. If the
    observed price is outside the no-arbitrage bounds — which happens constantly with
    stale quotes and wide spreads — this returns NaN rather than a fabricated number.
    """
    if T <= 0 or price <= 0 or S <= 0 or K <= 0:
        return float("nan")

    intrinsic = (
        max(S * np.exp(-q * T) - K * np.exp(-r * T), 0.0)
        if option == "call"
        else max(K * np.exp(-r * T) - S * np.exp(-q * T), 0.0)
    )
    upper_bound = S * np.exp(-q * T) if option == "call" else K * np.exp(-r * T)
    if price < intrinsic - 1e-10 or price > upper_bound + 1e-10:
        return float("nan")  # arbitrage-violating quote: do not invent a vol for it

    def objective(sigma: float) -> float:
        return black_scholes_price(S, K, T, r, sigma, option, q) - price

    try:
        if objective(lower) * objective(upper) > 0:
            return float("nan")  # no root in the bracket
        return float(optimize.brentq(objective, lower, upper, xtol=1e-8, maxiter=200))
    except (ValueError, RuntimeError):
        return float("nan")


def put_call_parity_check(
    call_price: float, put_price: float, S: float, K: float, T: float, r: float, q: float = 0.0,
    tolerance: float = 0.01,
) -> dict:
    """C - P = S*e^(-qT) - K*e^(-rT). A violation is either arbitrage or bad data.

    In practice it is almost always bad data — a stale quote on one leg — and this is
    the cheapest possible sanity check on an options feed before anything is derived
    from it.
    """
    lhs = call_price - put_price
    rhs = S * np.exp(-q * T) - K * np.exp(-r * T)
    diff = lhs - rhs
    relative = abs(diff) / S if S > 0 else np.inf
    return {
        "call_minus_put": float(lhs),
        "forward_minus_strike": float(rhs),
        "violation": float(diff),
        "relative_violation": float(relative),
        "holds": bool(relative < tolerance),
        "interpretation": (
            "parity holds" if relative < tolerance
            else "parity violated — check for a stale quote before assuming arbitrage"
        ),
    }


def delta_to_strike(delta: float, S: float, T: float, sigma: float, r: float = 0.0,
                    option: str = "call", q: float = 0.0) -> float:
    """Strike corresponding to a given delta — how option desks actually quote.

    A "25-delta put" is a fixed *moneyness in risk terms* rather than a fixed price
    level, so a skew measured between 25-delta wings is comparable across time and
    across volatility regimes. Measuring skew at fixed strikes is not.
    """
    if T <= 0 or sigma <= 0:
        return float("nan")
    target = abs(delta)
    d1 = stats.norm.ppf(target * np.exp(q * T)) if option == "call" else -stats.norm.ppf(target * np.exp(q * T))
    return float(S * np.exp((r - q + 0.5 * sigma**2) * T - d1 * sigma * np.sqrt(T)))


def portfolio_greeks(positions: list[dict], S: float, r: float = 0.0) -> dict:
    """Aggregate greeks across a book of options.

    Each position is {"K", "T", "sigma", "option", "quantity"}. Aggregating is the
    point: individually harmless positions can add up to a large short-gamma exposure,
    which is invisible until the market moves and then is the only thing that matters.
    """
    totals = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "value": 0.0}
    for pos in positions:
        g = greeks(S, pos["K"], pos["T"], r, pos["sigma"], pos.get("option", "call"))
        qty = float(pos.get("quantity", 1.0))
        totals["value"] += g.price * qty
        totals["delta"] += g.delta * qty
        totals["gamma"] += g.gamma * qty
        totals["vega"] += g.vega * qty
        totals["theta"] += g.theta * qty

    totals["delta_notional"] = totals["delta"] * S
    # What a 1% spot move does to the book's delta — the practical read on gamma.
    totals["gamma_pnl_1pct"] = 0.5 * totals["gamma"] * (S * 0.01) ** 2
    totals["short_gamma"] = totals["gamma"] < 0
    return totals
