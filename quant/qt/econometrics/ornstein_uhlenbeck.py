"""Ornstein-Uhlenbeck — the model behind every mean-reversion trade.

    dX = theta * (mu - X) dt + sigma dW

Three parameters with direct trading meaning:

* **mu** — the level the spread returns to. Where fair value is.
* **theta** — the speed it returns at. Half-life = ln(2)/theta, which sets the holding
  period and therefore whether the trade survives costs at all.
* **sigma** — the noise around the path. Sets the entry threshold: entering at 1 sigma
  when sigma is large means entering on nothing.

Fitting matters because the naive approach — eyeball a z-score, enter at ±2, exit at 0 —
leaves the two decisions that determine profitability unexamined. Given the fitted
process, the optimal entry and exit levels can be *derived* rather than guessed, and
`optimal_thresholds` does that with transaction costs included (following Bertram's
treatment of optimal trading of an OU process).

The result is frequently sobering: for many pairs, once realistic costs enter, the
optimal entry threshold is so wide that the trade almost never triggers, and the
expected profit per unit time is negative at every threshold. That is a genuine answer,
and it is far better to get it from the model in a second than from six months of live
trading.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, stats


@dataclass
class OUFit:
    mu: float  # long-run mean
    theta: float  # mean-reversion speed, per bar
    sigma: float  # instantaneous volatility, per sqrt(bar)
    half_life: float  # bars
    equilibrium_std: float  # stationary standard deviation of the process
    n_obs: int
    r_squared: float

    @property
    def is_mean_reverting(self) -> bool:
        return np.isfinite(self.theta) and self.theta > 0

    def zscore(self, series: pd.Series) -> pd.Series:
        """Deviation from the fitted mean, in units of the process's own equilibrium sd."""
        if not np.isfinite(self.equilibrium_std) or self.equilibrium_std <= 0:
            return pd.Series(np.nan, index=series.index)
        return (series - self.mu) / self.equilibrium_std

    def expected_reversion_time(self, z: float) -> float:
        """Expected bars to return to the mean from a deviation of z equilibrium sds.

        For an OU process the expected first-passage time to the mean scales roughly
        linearly in log-deviation; this is the standard approximation and is accurate
        enough to answer "will this resolve inside my horizon".
        """
        if not self.is_mean_reverting or z == 0:
            return float("inf") if not self.is_mean_reverting else 0.0
        return float(np.log(abs(z) + 1.0) / self.theta)

    def summary(self) -> dict:
        return {
            "mu": self.mu,
            "theta": self.theta,
            "sigma": self.sigma,
            "half_life_bars": self.half_life,
            "equilibrium_std": self.equilibrium_std,
            "r_squared": self.r_squared,
            "mean_reverting": self.is_mean_reverting,
            "n_obs": self.n_obs,
        }


def fit_ou(series: pd.Series, dt: float = 1.0) -> OUFit:
    """Fit an OU process by OLS on the discretised (AR(1)) form.

    The exact discretisation is X_{t+1} = X_t * exp(-theta*dt) + mu*(1-exp(-theta*dt))
    + noise, i.e. an AR(1). Fitting by OLS and inverting is equivalent to maximum
    likelihood here and is far more numerically robust than optimising directly.
    """
    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(x)
    if n < 30:
        return OUFit(np.nan, np.nan, np.nan, np.nan, np.nan, n, np.nan)

    y = x.to_numpy(dtype="float64")
    lagged, current = y[:-1], y[1:]

    design = np.column_stack([lagged, np.ones(lagged.size)])
    coef, *_ = np.linalg.lstsq(design, current, rcond=None)
    a, b = float(coef[0]), float(coef[1])
    resid = current - design @ coef

    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((current - current.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    # a = exp(-theta*dt). a >= 1 means no mean reversion; a <= 0 means oscillation
    # too fast for this sampling frequency to represent.
    if a <= 0 or a >= 1:
        return OUFit(float(np.mean(y)), np.nan, float(np.std(resid, ddof=1)), float("inf"),
                     float(np.std(y, ddof=1)), n, r2)

    theta = -np.log(a) / dt
    mu = b / (1 - a)
    resid_sd = float(np.std(resid, ddof=2)) if resid.size > 2 else np.nan
    # Convert the residual sd of the discrete model back to the continuous sigma.
    sigma = resid_sd * np.sqrt(2 * theta / (1 - a**2)) if resid_sd and theta > 0 else np.nan
    equilibrium_std = sigma / np.sqrt(2 * theta) if sigma and theta > 0 else np.nan

    return OUFit(
        mu=float(mu),
        theta=float(theta),
        sigma=float(sigma) if sigma is not None else np.nan,
        half_life=float(np.log(2) / theta),
        equilibrium_std=float(equilibrium_std) if equilibrium_std is not None else np.nan,
        n_obs=n,
        r_squared=float(r2),
    )


def _threshold_result(*, reason: str, curve=None, **overrides) -> dict:
    """Every exit path returns the same keys.

    Two return paths with different schemas is how a caller ends up with a KeyError on
    exactly the branch that says "do not trade this" — the branch that most needs to be
    read rather than crashed on.
    """
    base = {
        "entry_z": np.nan,
        "exit_z": 0.0,
        "expected_profit_per_trade": np.nan,
        "expected_trades_per_bar": np.nan,
        "expected_profit_per_bar": np.nan,
        "expected_annual_return": np.nan,
        "expected_trades_per_year": np.nan,
        "viable": False,
        "at_grid_boundary": False,
        "boundary_entry_z": np.nan,
        "curve": curve if curve is not None else pd.DataFrame(),
        "reason": reason,
    }
    base.update(overrides)
    return base


def optimal_thresholds(
    fit: OUFit,
    cost: float,
    *,
    max_entry_z: float = 4.0,
    n_grid: int = 200,
) -> dict:
    """Entry/exit thresholds maximising expected profit per unit time, net of costs.

    The trade-off being solved: a wide entry threshold captures more profit per trade
    but trades rarely, so profit *per unit time* falls; a narrow one trades constantly
    and gives everything to costs. The optimum is interior and depends on theta and
    sigma — it is not "±2 sigma" for any particular reason.

    `cost` is the round-trip cost expressed in the same units as the spread (for a
    log-price spread, roughly the round-trip cost in decimal, e.g. 0.0012 for 12 bps).

    Exit at the mean is assumed. That is not exactly optimal but it is very close for
    symmetric OU, and the loss from the approximation is far smaller than the error in
    any real estimate of theta.
    """
    if not fit.is_mean_reverting or not np.isfinite(fit.equilibrium_std) or fit.equilibrium_std <= 0:
        return _threshold_result(reason="process is not mean-reverting")

    sd = fit.equilibrium_std
    grid = np.linspace(0.1, max_entry_z, n_grid)

    best = None
    rows = []
    for z in grid:
        # Gross profit of a round trip: travel from z sds away back to the mean.
        gross = z * sd
        net = gross - cost
        # Expected time for a full cycle: reach the entry level, then revert. Both
        # legs approximated by the OU first-passage scaling.
        time_to_entry = np.log(z + 1.0) / fit.theta
        time_to_revert = np.log(z + 1.0) / fit.theta
        cycle = time_to_entry + time_to_revert
        if cycle <= 0:
            continue
        profit_rate = net / cycle
        rows.append(
            {
                "entry_z": float(z),
                "gross_per_trade": float(gross),
                "net_per_trade": float(net),
                "cycle_bars": float(cycle),
                "profit_per_bar": float(profit_rate),
            }
        )
        if net > 0 and (best is None or profit_rate > best["profit_per_bar"]):
            best = rows[-1]

    curve = pd.DataFrame(rows)
    if best is None:
        return _threshold_result(
            curve=curve,
            reason=(
                f"no entry threshold clears the {cost:.4f} round-trip cost — the spread's "
                f"equilibrium sd is {sd:.5f}, so even a {max_entry_z} sd move is worth "
                f"{max_entry_z * sd:.5f}"
            ),
        )

    # An optimum sitting on the edge of the search grid is not an optimum — it means
    # the true one is outside the range, and the reported numbers are an artefact of
    # where the grid was cut. Report it as such rather than as a result.
    at_boundary = abs(best["entry_z"] - max_entry_z) < (max_entry_z / n_grid) * 1.5
    # At the boundary the expected-return figures are artefacts of where the grid was
    # cut, not forecasts, and they come out large and enticing. Reporting them as
    # numbers next to `viable: False` invites exactly the mistake this module exists to
    # prevent, so they are suppressed rather than merely flagged.
    return {
        "entry_z": best["entry_z"] if not at_boundary else np.nan,
        "exit_z": 0.0,
        "expected_profit_per_trade": best["net_per_trade"] if not at_boundary else np.nan,
        "expected_trades_per_bar": (1.0 / best["cycle_bars"]) if not at_boundary else np.nan,
        "expected_profit_per_bar": best["profit_per_bar"] if not at_boundary else np.nan,
        "expected_annual_return": (best["profit_per_bar"] * 365 * 24) if not at_boundary else np.nan,
        "expected_trades_per_year": (365 * 24 / best["cycle_bars"]) if not at_boundary else np.nan,
        "viable": bool(not at_boundary),
        "at_grid_boundary": bool(at_boundary),
        "boundary_entry_z": best["entry_z"] if at_boundary else np.nan,
        "curve": curve,
        "reason": (
            f"optimum sits at the grid edge (entry_z={max_entry_z}); profit is still "
            "increasing in the threshold, which usually means the spread is too slow "
            "or too small relative to costs to trade — widen max_entry_z to confirm"
            if at_boundary
            else "interior optimum found"
        ),
    }


def ou_signal(
    spread: pd.Series,
    *,
    lookback: int = 720,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    refit_every: int = 168,
) -> pd.DataFrame:
    """Rolling OU fit and the resulting position signal, strictly causal.

    The process is refitted periodically on trailing data only, and the signal at t
    uses the fit from the last refit before t. Fitting once on the whole sample and
    trading the resulting z-score is the standard way pairs backtests get inflated:
    the mean being reverted to was computed using the future.
    """
    x = pd.Series(spread).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(x)
    out = pd.DataFrame(index=x.index, columns=["mu", "theta", "half_life", "z", "position"], dtype="float64")
    if n < lookback + 10:
        return out

    position = 0.0
    fit: OUFit | None = None
    for i in range(lookback, n):
        if fit is None or (i - lookback) % refit_every == 0:
            fit = fit_ou(x.iloc[i - lookback : i])  # strictly past data

        if fit is None or not fit.is_mean_reverting or not np.isfinite(fit.equilibrium_std):
            out.iloc[i] = [np.nan, np.nan, np.nan, np.nan, 0.0]
            position = 0.0
            continue

        z = (x.iloc[i] - fit.mu) / fit.equilibrium_std
        # Hysteresis: enter beyond entry_z, hold until the spread comes back inside
        # exit_z. Without the band the position flickers around the threshold and
        # pays costs on every flicker.
        if position == 0.0:
            if z > entry_z:
                position = -1.0  # spread rich: short it
            elif z < -entry_z:
                position = 1.0
        else:
            if abs(z) < exit_z or np.sign(z) == np.sign(-position) * -1 and abs(z) > entry_z * 2:
                position = 0.0

        out.iloc[i] = [fit.mu, fit.theta, fit.half_life, z, position]

    return out


def johansen_spread_ou(prices: pd.DataFrame, **kwargs) -> dict:
    """Convenience: build a Johansen basket spread and fit an OU process to it."""
    from .cointegration import johansen

    joh = johansen(prices, **kwargs)
    if not joh.get("cointegrated"):
        return {"cointegrated": False, "johansen": joh}
    fit = fit_ou(joh["spread"])
    return {"cointegrated": True, "johansen": joh, "ou": fit, "summary": fit.summary()}
