"""Optimal execution — the trade-off between paying impact and bearing risk.

You need to sell 100 BTC. Sell it all now and you walk the book down, paying large
temporary impact. Sell it over a week and you pay almost no impact but you are exposed
to a week of price risk on a position you have already decided to exit. Neither extreme
is right, and the correct answer depends on your risk aversion and on the market's
depth — which is exactly what Almgren-Chriss formalises.

The solution has a closed form. Define kappa from the ratio of risk aversion times
volatility squared to temporary impact; then the optimal remaining position decays as
sinh(kappa*(T-t))/sinh(kappa*T) — an exponential-ish glide that is front-loaded when
you are risk-averse or the asset is volatile, and flat (i.e. TWAP) when you are
risk-neutral.

Two limits worth internalising, because they are the sanity check on any execution
schedule:

* risk aversion -> 0 gives **TWAP**: with no risk aversion, spread the trade evenly and
  minimise impact.
* risk aversion -> infinity gives **immediate execution**: dump it and accept the cost.

The efficient frontier here is between expected cost and the *variance* of cost, and it
is a real frontier: there is no schedule that improves both.

Also in this module: the standard schedules (TWAP, VWAP, POV) that most orders actually
use, and implementation-shortfall attribution, which decomposes what an execution
actually cost into delay, impact and timing so the next one can be better.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _sinh_ratio(a: np.ndarray, b: float) -> np.ndarray:
    """sinh(a)/sinh(b), computed without overflowing.

    A risk-averse trader gives a large kappa*T, and sinh of a large number overflows to
    inf, so the naive ratio becomes inf/inf = NaN and the whole schedule silently turns
    into nothing. Rewriting as exp(a-b) * (1-exp(-2a))/(1-exp(-2b)) keeps every
    exponent negative and is exact for the same inputs.
    """
    a = np.asarray(a, dtype="float64")
    if b < 30.0:
        return np.sinh(a) / np.sinh(b)
    return np.exp(a - b) * (1.0 - np.exp(-2.0 * a)) / (1.0 - np.exp(-2.0 * b))


@dataclass
class ExecutionSchedule:
    """A trading trajectory: how much to hold, and to trade, at each step."""

    holdings: pd.Series  # remaining position at each time step
    trades: pd.Series  # amount traded in each interval
    expected_cost: float  # expected implementation shortfall, in currency
    cost_variance: float
    kappa: float
    strategy: str

    @property
    def cost_std(self) -> float:
        return float(np.sqrt(max(self.cost_variance, 0.0)))

    def summary(self) -> dict:
        return {
            "strategy": self.strategy,
            "n_steps": len(self.trades),
            "expected_cost": self.expected_cost,
            "cost_std": self.cost_std,
            "kappa": self.kappa,
            # Fraction executed in the first half — the practical read on urgency.
            "front_loading": float(
                self.trades.iloc[: len(self.trades) // 2].abs().sum() / self.trades.abs().sum()
            )
            if self.trades.abs().sum() > 0
            else np.nan,
        }


def almgren_chriss(
    total_quantity: float,
    n_steps: int,
    *,
    volatility: float,
    temporary_impact: float,
    permanent_impact: float = 0.0,
    risk_aversion: float = 1e-6,
    step_seconds: float = 60.0,
) -> ExecutionSchedule:
    """Optimal trajectory for liquidating `total_quantity` over `n_steps`.

    **Everything is expressed per step**, and mixing that with wall-clock seconds is
    the mistake that makes this model produce nonsense:
    * `volatility` — price standard deviation over ONE step, in currency per unit.
    * `temporary_impact` (eta) — price concession per unit traded, per step.
    * `permanent_impact` (gamma) — permanent price move per unit traded.
    * `risk_aversion` (lambda) — currency of expected cost you will pay to remove one
      unit of cost variance. Zero gives TWAP.

    The internal time unit is therefore the step (tau = 1, T = n_steps), so kappa*T is
    a pure number and lambda has a stable, interpretable scale. Measuring time in
    seconds here instead would multiply kappa*T by 60 or 3600 and drive every schedule
    to immediate liquidation regardless of lambda, which is what an earlier version of
    this function did. `step_seconds` survives only as metadata for annualising.

    eta and lambda are dimensional, and a lambda that makes sense for a $1m order is
    meaningless for a $1000 one. Use `calibrate_impact` to get eta from observed fills
    rather than guessing it.
    """
    if n_steps < 1:
        raise ValueError("n_steps must be >= 1")

    tau = 1.0  # one step is the unit of time; see the note above
    T = float(n_steps)
    eta_hat = temporary_impact - 0.5 * permanent_impact * tau
    if eta_hat <= 0:
        eta_hat = temporary_impact  # degenerate parameters: fall back to pure temporary

    times = np.arange(n_steps + 1) * tau

    if risk_aversion <= 0:
        # Risk-neutral limit: TWAP.
        holdings = total_quantity * (1 - times / T)
        kappa = 0.0
    else:
        kappa_squared = risk_aversion * volatility**2 / eta_hat
        kappa = float(np.sqrt(max(kappa_squared, 0.0)))
        if kappa * T < 1e-8:
            holdings = total_quantity * (1 - times / T)
        else:
            holdings = total_quantity * _sinh_ratio(kappa * (T - times), kappa * T)

    trades = -np.diff(holdings)  # positive = sold in that interval

    # Expected cost: permanent impact on the whole order plus temporary impact of each
    # slice; variance from holding the residual position through price moves.
    expected = (
        0.5 * permanent_impact * total_quantity**2
        + eta_hat * float(np.sum(trades**2)) / tau
    )
    variance = volatility**2 * tau * float(np.sum(holdings[1:] ** 2))

    index = pd.RangeIndex(n_steps + 1, name="step")
    return ExecutionSchedule(
        holdings=pd.Series(holdings, index=index, name="holdings"),
        trades=pd.Series(trades, index=pd.RangeIndex(1, n_steps + 1, name="step"), name="trades"),
        expected_cost=float(expected),
        cost_variance=float(variance),
        kappa=kappa,
        strategy="almgren_chriss" if risk_aversion > 0 else "twap (risk-neutral limit)",
    )


def efficient_frontier(
    total_quantity: float,
    n_steps: int,
    *,
    volatility: float,
    temporary_impact: float,
    permanent_impact: float = 0.0,
    risk_aversions: np.ndarray | None = None,
    step_seconds: float = 60.0,
) -> pd.DataFrame:
    """Expected cost against cost standard deviation, across risk aversions.

    This is the object the whole theory produces, and it is worth plotting once: it
    shows there is no free lunch in execution. Every reduction in the variance of your
    outcome is bought with expected cost, and the only question is where on the curve
    your mandate sits.
    """
    risk_aversions = (
        risk_aversions if risk_aversions is not None else np.logspace(-9, -3, 25)
    )
    rows = []
    for lam in risk_aversions:
        sched = almgren_chriss(
            total_quantity, n_steps, volatility=volatility, temporary_impact=temporary_impact,
            permanent_impact=permanent_impact, risk_aversion=float(lam), step_seconds=step_seconds,
        )
        rows.append(
            {
                "risk_aversion": float(lam),
                "expected_cost": sched.expected_cost,
                "cost_std": sched.cost_std,
                "kappa": sched.kappa,
                "half_life_steps": float(np.log(2) / sched.kappa) if sched.kappa > 0 else np.inf,
                **{"front_loading": sched.summary()["front_loading"]},
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Standard schedules
# ---------------------------------------------------------------------------
def twap_schedule(total_quantity: float, n_steps: int) -> pd.Series:
    """Equal slices. The risk-neutral optimum and the default everyone benchmarks to."""
    return pd.Series(
        np.repeat(total_quantity / n_steps, n_steps),
        index=pd.RangeIndex(1, n_steps + 1, name="step"),
        name="twap",
    )


def vwap_schedule(total_quantity: float, volume_profile: pd.Series) -> pd.Series:
    """Slices proportional to expected volume.

    Trading in proportion to the market's own activity keeps participation constant,
    which minimises impact for a given horizon: you are a fixed fraction of flow rather
    than a large fraction of a quiet period.

    `volume_profile` is typically the average volume by time-of-day, estimated from
    history — in crypto the U-shape is driven by the Asia/Europe/US session handovers.
    """
    profile = pd.Series(volume_profile).astype("float64").clip(lower=0.0)
    total = profile.sum()
    if total <= 0:
        return twap_schedule(total_quantity, len(profile))
    return (profile / total * total_quantity).rename("vwap")


def pov_schedule(
    total_quantity: float, volume_forecast: pd.Series, participation_rate: float = 0.1
) -> pd.DataFrame:
    """Percentage-of-volume: trade a fixed share of whatever actually trades.

    The advantage over VWAP is adaptivity — if volume dries up, you trade less rather
    than becoming an ever-larger share of a thinning market. The cost is horizon
    uncertainty: the order may not complete. The returned frame shows exactly when (or
    whether) it finishes, which is the number to check before choosing this.
    """
    volume = pd.Series(volume_forecast).astype("float64").clip(lower=0.0)
    remaining = abs(total_quantity)
    sign = np.sign(total_quantity)

    rows = []
    for step, vol in volume.items():
        slice_qty = min(vol * participation_rate, remaining)
        remaining -= slice_qty
        rows.append(
            {
                "step": step,
                "market_volume": float(vol),
                "trade": float(sign * slice_qty),
                "remaining": float(sign * remaining),
                "participation": float(slice_qty / vol) if vol > 0 else 0.0,
            }
        )
        if remaining <= 1e-12:
            break

    out = pd.DataFrame(rows).set_index("step")
    out.attrs["completed"] = bool(remaining <= 1e-12)
    out.attrs["unfilled"] = float(sign * remaining)
    out.attrs["steps_used"] = len(out)
    return out


# ---------------------------------------------------------------------------
# Post-trade analysis
# ---------------------------------------------------------------------------
def implementation_shortfall(
    fills: pd.DataFrame, decision_price: float, arrival_price: float | None = None,
    final_price: float | None = None, side: int = 1,
) -> dict:
    """Decompose what an execution actually cost, against the decision price.

    Implementation shortfall is the honest measure of execution quality: the gap
    between the paper portfolio you decided on and the one you actually got. Beating
    VWAP means nothing if the price ran away before you started.

    The decomposition separates the parts that are someone's fault:

    * **delay cost** — the market moved between deciding and starting. This is the
      cost of slow plumbing, and it is invisible to a VWAP benchmark.
    * **execution cost** — the gap between the average fill and the arrival price. This
      is impact and spread, i.e. the part the execution algorithm controls.
    * **opportunity cost** — the value of whatever did not get filled.

    `fills` needs columns `price` and `quantity`. `side` is +1 buy / -1 sell.
    """
    if fills.empty:
        return {"total_shortfall_bps": np.nan, "reason": "no fills"}

    qty = fills["quantity"].abs()
    filled = float(qty.sum())
    if filled <= 0 or decision_price <= 0:
        return {"total_shortfall_bps": np.nan, "reason": "no filled quantity"}

    avg_fill = float((fills["price"] * qty).sum() / filled)
    arrival = arrival_price if arrival_price is not None else decision_price

    # Costs are signed so that positive always means "worse for the trader".
    delay = side * (arrival - decision_price) / decision_price
    execution = side * (avg_fill - arrival) / decision_price
    total = side * (avg_fill - decision_price) / decision_price

    out = {
        "avg_fill_price": avg_fill,
        "decision_price": decision_price,
        "arrival_price": arrival,
        "filled_quantity": filled,
        "delay_cost_bps": float(delay * 1e4),
        "execution_cost_bps": float(execution * 1e4),
        "total_shortfall_bps": float(total * 1e4),
        "n_fills": int(len(fills)),
    }

    if final_price is not None and "target_quantity" in fills.attrs:
        unfilled = float(fills.attrs["target_quantity"]) - filled
        if unfilled > 1e-12:
            opportunity = side * (final_price - decision_price) / decision_price * (unfilled / filled)
            out["unfilled_quantity"] = unfilled
            out["opportunity_cost_bps"] = float(opportunity * 1e4)
            out["total_shortfall_bps"] += out["opportunity_cost_bps"]
    return out


def calibrate_impact(
    trades: pd.DataFrame, *, notional_col: str = "notional", return_col: str = "return",
    volume_col: str = "bar_notional",
) -> dict:
    """Estimate the square-root impact coefficient from observed executions.

    Fits |return| = coeff * sigma * sqrt(participation) by regressing on the square
    root of participation. Estimating this from your own fills is strictly better than
    adopting a literature value, because it captures your actual venue, order type and
    size distribution — and because the coefficient is the single input that determines
    a strategy's capacity.
    """
    df = trades.replace([np.inf, -np.inf], np.nan).dropna(subset=[notional_col, return_col, volume_col])
    df = df[(df[volume_col] > 0) & (df[notional_col] > 0)]
    if len(df) < 30:
        return {"coefficient": np.nan, "n": len(df), "reason": "need >=30 executions"}

    participation = (df[notional_col] / df[volume_col]).clip(upper=1.0)
    x = np.sqrt(participation).to_numpy()
    y = df[return_col].abs().to_numpy()

    # Through the origin: zero size must imply zero impact.
    coeff = float((x @ y) / (x @ x)) if (x @ x) > 0 else np.nan
    predicted = coeff * x
    ss_res = float(np.sum((y - predicted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))

    return {
        "coefficient": coeff,
        "coefficient_bps": coeff * 1e4,
        "r_squared": 1 - ss_res / ss_tot if ss_tot > 0 else np.nan,
        "n": len(df),
        "median_participation": float(participation.median()),
        "note": "impact_bps = coefficient * 1e4 * sqrt(participation); feed into CostModel",
    }
