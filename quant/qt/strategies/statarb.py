"""Statistical arbitrage — the strategy that ties the whole toolkit together.

Every piece of the econometrics module earns its place here:

1. **Screen** for cointegrated pairs (`econometrics.cointegration.screen_pairs`), with
   the multiple-testing correction, because searching 45 pairs at 5% significance
   produces two false positives by construction.
2. **Estimate the hedge ratio dynamically** with a Kalman filter rather than a static
   OLS beta — the relationship drifts, and a beta fitted once on the whole sample is
   both stale and a look-ahead.
3. **Fit the spread's Ornstein-Uhlenbeck process** to get the half-life, which decides
   the holding period and therefore whether costs leave anything behind.
4. **Derive entry and exit thresholds** from the fitted process and the actual cost,
   instead of defaulting to ±2 sigma for no reason.
5. **Monitor for structural breaks** and stand down when the relationship stops holding,
   rather than discovering it through the PnL.

Everything is strictly causal: the Kalman beta at time t uses only data up to t, the OU
parameters are refitted on trailing windows, and the position is executed on the bar
after the signal. The result is usually that a pair which looks beautifully
mean-reverting in-sample is not tradeable after costs — and getting that answer in
thirty seconds rather than after six months of live trading is what the machinery is
for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..econometrics.breaks import rolling_break_monitor
from ..econometrics.cointegration import engle_granger, screen_pairs
from ..econometrics.kalman import KalmanHedge
from ..econometrics.ornstein_uhlenbeck import fit_ou, optimal_thresholds


@dataclass
class PairSpec:
    """Everything that defines one pair trade."""

    asset_a: str
    asset_b: str
    lookback: int = 720  # bars used to refit the OU process
    refit_every: int = 168
    entry_z: float | None = None  # None = derive from the OU fit and costs
    exit_z: float = 0.5
    stop_z: float = 4.0  # abandon the trade if the spread runs this far against us
    max_half_life: float = 500.0
    kalman_delta: float = 1e-4
    round_trip_cost: float = 0.0012  # 12 bps both legs, both directions
    use_kalman: bool = True

    def to_meta(self) -> dict:
        return {
            "pair": f"{self.asset_a}/{self.asset_b}",
            "lookback": self.lookback,
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
            "stop_z": self.stop_z,
            "use_kalman": self.use_kalman,
            "round_trip_cost": self.round_trip_cost,
        }


@dataclass
class PairAnalysis:
    """Diagnostics that decide whether a pair is worth trading at all."""

    spec: PairSpec
    cointegrated: bool
    pvalue: float
    hedge_ratio: float
    half_life: float
    ou_fit: object
    thresholds: dict
    tradeable: bool
    reasons: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "pair": f"{self.spec.asset_a}/{self.spec.asset_b}",
            "cointegrated": self.cointegrated,
            "pvalue": self.pvalue,
            "hedge_ratio": self.hedge_ratio,
            "half_life_bars": self.half_life,
            "entry_z": self.thresholds.get("entry_z"),
            "expected_annual_return": self.thresholds.get("expected_annual_return"),
            "expected_trades_per_year": self.thresholds.get("expected_trades_per_year"),
            "tradeable": self.tradeable,
            "reasons": "; ".join(self.reasons),
        }


def analyse_pair(prices: pd.DataFrame, spec: PairSpec) -> PairAnalysis:
    """Full pre-trade analysis of one pair. Answers 'should this be traded' first.

    The checks are applied in the order that fails fastest and cheapest, and every
    rejection reason is recorded — a pair that fails only on half-life is a different
    situation from one that is not cointegrated at all.
    """
    a, b = spec.asset_a, spec.asset_b
    missing = [c for c in (a, b) if c not in prices.columns]
    if missing:
        raise KeyError(f"prices is missing {missing}")

    df = prices[[a, b]].replace([np.inf, -np.inf], np.nan).dropna()
    reasons: list[str] = []

    cg = engle_granger(df[a], df[b], name_a=a, name_b=b)
    if not cg.cointegrated:
        reasons.append(f"not cointegrated (p={cg.pvalue:.4f})")

    spread = cg.spread(df)
    ou = fit_ou(spread)

    if not ou.is_mean_reverting:
        reasons.append("OU fit shows no mean reversion")
    elif ou.half_life > spec.max_half_life:
        reasons.append(
            f"half-life {ou.half_life:.0f} bars exceeds the {spec.max_half_life:.0f} limit — "
            "this is a directional bet, not a mean-reversion trade"
        )

    thresholds = optimal_thresholds(ou, cost=spec.round_trip_cost)
    if not thresholds.get("viable"):
        reasons.append(f"no viable threshold: {thresholds.get('reason', 'unknown')}")

    return PairAnalysis(
        spec=spec,
        cointegrated=cg.cointegrated,
        pvalue=cg.pvalue,
        hedge_ratio=cg.hedge_ratio,
        half_life=ou.half_life,
        ou_fit=ou,
        thresholds=thresholds,
        tradeable=len(reasons) == 0,
        reasons=reasons,
    )


def pair_signal(prices: pd.DataFrame, spec: PairSpec) -> pd.DataFrame:
    """Causal position signal for one pair.

    Returns a frame with the hedge ratio, spread, z-score and the position in each leg.
    `position_a` is +1 when the spread is cheap (buy A, sell B scaled by the hedge
    ratio) and -1 when it is rich.

    Everything is trailing: the Kalman beta at t is filtered from data up to t, and the
    OU parameters come from the most recent refit strictly before t.
    """
    a, b = spec.asset_a, spec.asset_b
    df = prices[[a, b]].replace([np.inf, -np.inf], np.nan).dropna()
    log_a, log_b = np.log(df[a]), np.log(df[b])

    if spec.use_kalman:
        kalman = KalmanHedge(delta=spec.kalman_delta).run(log_a, log_b)
        beta = kalman.beta["slope"]
        spread = kalman.spread  # prediction error IS the spread
    else:
        # Rolling OLS beta, shifted so the beta in force at t was estimated before t.
        mp = max(spec.lookback // 4, 30)
        cov = log_a.rolling(spec.lookback, min_periods=mp).cov(log_b)
        var = log_b.rolling(spec.lookback, min_periods=mp).var(ddof=0)
        beta = (cov / var.replace(0.0, np.nan)).shift(1)
        spread = log_a - beta * log_b

    out = pd.DataFrame(index=df.index)
    out["beta"] = beta
    out["spread"] = spread

    # Rolling OU refit on trailing data only.
    n = len(out)
    z = np.full(n, np.nan)
    half_life = np.full(n, np.nan)
    entry = np.full(n, np.nan)

    spread_values = spread.to_numpy()
    fit = None
    derived_entry = spec.entry_z
    for i in range(spec.lookback, n):
        if fit is None or (i - spec.lookback) % spec.refit_every == 0:
            window = pd.Series(spread_values[i - spec.lookback : i])
            fit = fit_ou(window)
            if spec.entry_z is None and fit.is_mean_reverting:
                thr = optimal_thresholds(fit, cost=spec.round_trip_cost)
                derived_entry = thr["entry_z"] if thr.get("viable") else np.nan
        if fit is None or not fit.is_mean_reverting or not np.isfinite(fit.equilibrium_std):
            continue
        z[i] = (spread_values[i] - fit.mu) / fit.equilibrium_std
        half_life[i] = fit.half_life
        entry[i] = derived_entry if derived_entry is not None else np.nan

    out["z"] = z
    out["half_life"] = half_life
    out["entry_z"] = entry

    # Position with hysteresis: enter beyond entry_z, hold until inside exit_z, and
    # abandon at stop_z (the relationship has probably broken).
    position = np.zeros(n)
    current = 0.0
    for i in range(n):
        zi, ei = z[i], entry[i]
        if not np.isfinite(zi) or not np.isfinite(ei):
            current = 0.0
            position[i] = 0.0
            continue
        if current == 0.0:
            if zi > ei:
                current = -1.0  # spread rich -> short A, long B
            elif zi < -ei:
                current = 1.0
        else:
            if abs(zi) < spec.exit_z or abs(zi) > spec.stop_z:
                current = 0.0
        position[i] = current

    out["position_a"] = position
    out["position_b"] = -position * out["beta"]
    return out


def backtest_pair(
    prices: pd.DataFrame, spec: PairSpec, *, bars_per_year: float = 365 * 24
) -> dict:
    """Backtest a pair trade with costs charged on both legs.

    The position is shifted by one bar before being applied to returns, so a signal
    computed from bar t's close earns bar t+1's return — the same convention the main
    backtester enforces structurally.

    Costs are charged on turnover in *both* legs. A pair trade pays the round trip
    twice, which is the fact that kills most of them and the reason the analysis step
    above uses the doubled cost when deriving thresholds.
    """
    a, b = spec.asset_a, spec.asset_b
    df = prices[[a, b]].replace([np.inf, -np.inf], np.nan).dropna()
    signal = pair_signal(df, spec)

    ret_a = np.log(df[a]).diff()
    ret_b = np.log(df[b]).diff()

    pos_a = signal["position_a"].shift(1).fillna(0.0)
    pos_b = signal["position_b"].shift(1).fillna(0.0)

    gross = pos_a * ret_a + pos_b * ret_b
    turnover = pos_a.diff().abs().fillna(0.0) + pos_b.diff().abs().fillna(0.0)
    costs = turnover * (spec.round_trip_cost / 2.0)
    net = (gross - costs).fillna(0.0)

    equity = (1 + net).cumprod()
    n = len(net)
    sd = net.std(ddof=1)

    trades = int((signal["position_a"].diff().abs() > 0).sum())
    drawdown = equity / equity.cummax() - 1

    return {
        "signal": signal,
        "returns": net,
        "gross_returns": gross,
        "equity": equity,
        "total_return": float(equity.iloc[-1] - 1) if n else np.nan,
        "sharpe": float(net.mean() / sd * np.sqrt(bars_per_year)) if sd > 0 else np.nan,
        "gross_sharpe": float(gross.mean() / gross.std(ddof=1) * np.sqrt(bars_per_year))
        if gross.std(ddof=1) > 0
        else np.nan,
        "max_drawdown": float(drawdown.min()) if n else np.nan,
        "n_trades": trades,
        "total_costs": float(costs.sum()),
        "cost_drag_annual": float(costs.sum() / (n / bars_per_year)) if n else np.nan,
        "time_in_market": float((pos_a.abs() > 0).mean()),
        "spec": spec.to_meta(),
    }


def screen_and_analyse(
    prices: pd.DataFrame,
    *,
    round_trip_cost: float = 0.0012,
    max_half_life: float = 500.0,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Screen a whole panel and analyse every candidate that survives.

    Two stages on purpose. The screen applies the Bonferroni correction to the
    cointegration tests; the analysis then asks the economic question — half-life,
    thresholds, expected profit after costs — which rejects most of the statistically
    significant pairs. Statistical significance is necessary and nowhere near
    sufficient.
    """
    screen = screen_pairs(prices, alpha=alpha, max_half_life=max_half_life)
    rows = []
    for _, row in screen.iterrows():
        spec = PairSpec(
            asset_a=row["asset_a"], asset_b=row["asset_b"],
            round_trip_cost=round_trip_cost, max_half_life=max_half_life,
        )
        try:
            analysis = analyse_pair(prices, spec)
        except Exception as exc:
            rows.append({"pair": f"{row['asset_a']}/{row['asset_b']}", "error": str(exc)})
            continue
        rows.append(
            {
                **analysis.summary(),
                "passes_corrected": row["passes_corrected"],
                "raw_pvalue": row["pvalue"],
            }
        )

    out = pd.DataFrame(rows)
    out.attrs.update(screen.attrs)
    if "pvalue" in out.columns:
        out = out.sort_values("pvalue")
    return out.reset_index(drop=True)


def monitor_pair(prices: pd.DataFrame, spec: PairSpec, window: int = 336) -> pd.DataFrame:
    """Live stability monitor for a pair already being traded.

    A drifting beta or a collapsing R-squared is the signal to stand down. Waiting for
    the spread to stop reverting means learning the same thing from the PnL instead.
    """
    df = prices[[spec.asset_a, spec.asset_b]].dropna()
    return rolling_break_monitor(np.log(df[spec.asset_a]), np.log(df[spec.asset_b]), window=window)
