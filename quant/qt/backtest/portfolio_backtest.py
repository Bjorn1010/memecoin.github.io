"""Multi-asset portfolio backtest — the optimisers, actually traded.

Until now the optimisers in `qt/portfolio` produced weights and nothing consumed them:
you could compute a risk-parity allocation but not find out what it would have earned
after rebalancing costs. That gap matters more than it sounds, because the *whole*
difference between optimisers shows up in turnover. On paper, minimum variance looks
better than equal weight on almost every panel. Traded monthly with real costs, its
advantage frequently disappears, because it churns a concentrated book every time the
covariance estimate moves.

This module closes the loop: estimate the covariance on trailing data only, allocate,
rebalance on a schedule, charge the costs, and report what actually survived.

Every estimate is trailing. The covariance used to allocate at time t comes from a
window ending at t, and the weights are executed on the following bar. Fitting the
covariance on the full sample — which is what almost every published optimiser
comparison does — makes minimum variance look spectacular for the obvious reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import CostModel, RiskLimits
from ..portfolio import covariance as cov_mod
from ..portfolio import optimisers as opt
from ..portfolio.risk import effective_number_of_bets, risk_contributions
from .engine import BacktestConfig, run_backtest


@dataclass
class AllocationSpec:
    """How the book is built and how often."""

    method: str = "risk_parity"  # any key in ALLOCATORS
    lookback: int = 720  # bars of history for the covariance estimate
    rebalance_every: int = 168  # bars between reallocations
    covariance: str = "ledoit_wolf"  # sample | ewma | ledoit_wolf | denoised
    max_weight: float = 0.35
    allow_short: bool = False
    min_history: int = 200

    def to_meta(self) -> dict:
        return {
            "method": self.method,
            "lookback": self.lookback,
            "rebalance_every": self.rebalance_every,
            "covariance": self.covariance,
            "max_weight": self.max_weight,
        }


ALLOCATORS = {
    "equal_weight": lambda cov, **kw: opt.equal_weight(cov.index),
    "inverse_vol": lambda cov, **kw: opt.inverse_volatility(cov),
    "risk_parity": lambda cov, **kw: opt.risk_parity(cov),
    "min_variance": lambda cov, **kw: opt.minimum_variance(
        cov, allow_short=kw.get("allow_short", False), max_weight=kw.get("max_weight", 1.0)
    ),
    "max_diversification": lambda cov, **kw: opt.maximum_diversification(
        cov, allow_short=kw.get("allow_short", False), max_weight=kw.get("max_weight", 1.0)
    ),
    "hrp": lambda cov, **kw: opt.hierarchical_risk_parity(cov),
}

COVARIANCE_ESTIMATORS = {
    "sample": lambda r: cov_mod.sample_covariance(r),
    "ewma": lambda r: cov_mod.ewma_covariance(r),
    "ledoit_wolf": lambda r: cov_mod.ledoit_wolf_covariance(r)[0],
    "denoised": lambda r: cov_mod.denoise_covariance(r)["covariance"],
}


@dataclass
class PortfolioBacktestResult:
    weights: pd.DataFrame  # target weights through time
    backtest: object  # the BacktestResult from the engine
    diagnostics: pd.DataFrame  # per-rebalance risk diagnostics
    spec: AllocationSpec
    metrics: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "method": self.spec.method,
            **self.metrics,
            "mean_effective_bets": float(self.diagnostics["effective_bets"].mean())
            if not self.diagnostics.empty
            else np.nan,
            "n_rebalances": int(len(self.diagnostics)),
        }


def build_weights(
    prices: pd.DataFrame, spec: AllocationSpec | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trailing-window weights and per-rebalance diagnostics.

    Between rebalances the target weights are held constant (forward-filled), which is
    what a real book does — it does not re-optimise every bar, and pretending otherwise
    understates the drift the engine has to trade back.
    """
    spec = spec or AllocationSpec()
    if spec.method not in ALLOCATORS:
        raise KeyError(f"unknown allocation method {spec.method!r}; known: {sorted(ALLOCATORS)}")
    if spec.covariance not in COVARIANCE_ESTIMATORS:
        raise KeyError(f"unknown covariance estimator {spec.covariance!r}")

    px = prices.replace([np.inf, -np.inf], np.nan).dropna(how="all").ffill().dropna()
    rets = np.log(px).diff().dropna()
    n = len(rets)

    weights = pd.DataFrame(np.nan, index=rets.index, columns=px.columns)
    rows = []

    allocator = ALLOCATORS[spec.method]
    estimator = COVARIANCE_ESTIMATORS[spec.covariance]

    for anchor in range(spec.min_history, n, spec.rebalance_every):
        # Strictly trailing: the window ends at `anchor`, exclusive.
        window = rets.iloc[max(0, anchor - spec.lookback) : anchor]
        if len(window) < spec.min_history:
            continue
        try:
            cov = estimator(window)
            w = allocator(cov, allow_short=spec.allow_short, max_weight=spec.max_weight)
        except Exception:
            continue  # a failed optimisation means hold the previous book, not crash

        w = w.reindex(px.columns).fillna(0.0)
        total = w.abs().sum()
        if total > 0:
            w = w / total
        weights.iloc[anchor] = w.to_numpy()

        rows.append(
            {
                "ts": rets.index[anchor],
                "max_weight": float(w.max()),
                "herfindahl": float((w**2).sum()),
                "effective_assets": float(1.0 / (w**2).sum()) if (w**2).sum() > 0 else np.nan,
                "effective_bets": effective_number_of_bets(w, cov),
                "max_risk_contribution": float(risk_contributions(w, cov).abs().max()),
                "condition_number": cov_mod.condition_number(cov),
            }
        )

    weights = weights.ffill().fillna(0.0)
    diagnostics = pd.DataFrame(rows).set_index("ts") if rows else pd.DataFrame()
    return weights, diagnostics


def run_portfolio_backtest(
    prices: dict[str, pd.DataFrame],
    spec: AllocationSpec | None = None,
    config: BacktestConfig | None = None,
) -> PortfolioBacktestResult:
    """Allocate on a schedule and trade the resulting book through the engine.

    `prices` maps symbol -> bars, exactly as `run_backtest` expects. The weights become
    the engine's signal, so every cost, limit and circuit breaker applies unchanged —
    the portfolio path and a single-instrument path go through the same code, which is
    the only way to know the comparison is fair.
    """
    spec = spec or AllocationSpec()
    config = config or BacktestConfig()

    closes = pd.DataFrame({s: df["close"] for s, df in prices.items()}).dropna(how="all")
    weights, diagnostics = build_weights(closes, spec)
    if weights.empty:
        raise ValueError("no weights produced — check lookback and min_history against the sample length")

    # The engine applies its own volatility targeting on top of the signal. Feed it the
    # weights directly and disable that scaling, otherwise the allocation is silently
    # rescaled and the optimiser comparison measures the wrong thing.
    cfg = BacktestConfig(
        starting_equity=config.starting_equity,
        bars_per_year=config.bars_per_year,
        target_annual_vol=config.target_annual_vol,
        execution_lag_bars=config.execution_lag_bars,
        rebalance_threshold=config.rebalance_threshold,
        rebalance_threshold_relative=config.rebalance_threshold_relative,
        allow_short=spec.allow_short,
        vol_span=config.vol_span,
        costs=config.costs,
        risk=config.risk,
        use_estimated_spread=config.use_estimated_spread,
        max_weight_per_symbol=spec.max_weight,
    )

    aligned = {s: df.loc[df.index.intersection(weights.index)] for s, df in prices.items()}
    bt = run_backtest(aligned, weights, cfg)

    result = PortfolioBacktestResult(weights, bt, diagnostics, spec)
    result.metrics = dict(bt.metrics)
    return result


def compare_allocations(
    prices: dict[str, pd.DataFrame],
    methods=None,
    *,
    spec: AllocationSpec | None = None,
    config: BacktestConfig | None = None,
) -> pd.DataFrame:
    """Backtest every allocator on the same data, with costs.

    The comparison that matters, and the one that is almost never run: the column to
    read is not `sharpe` but `turnover_annual` next to `cost_share_of_gross`. An
    optimiser that wins before costs and churns the book has not won.
    """
    base = spec or AllocationSpec()
    methods = methods or list(ALLOCATORS)

    rows = []
    for method in methods:
        s = AllocationSpec(
            method=method,
            lookback=base.lookback,
            rebalance_every=base.rebalance_every,
            covariance=base.covariance,
            max_weight=base.max_weight,
            allow_short=base.allow_short,
            min_history=base.min_history,
        )
        try:
            res = run_portfolio_backtest(prices, s, config)
        except Exception as exc:
            rows.append({"method": method, "error": f"{type(exc).__name__}: {exc}"})
            continue
        m = res.metrics
        rows.append(
            {
                "method": method,
                "cagr": m.get("cagr"),
                "annual_vol": m.get("annual_vol"),
                "sharpe": m.get("sharpe"),
                "max_drawdown": m.get("max_drawdown"),
                "turnover_annual": m.get("turnover_annual"),
                "cost_share_of_gross": m.get("cost_share_of_gross"),
                "n_trades": m.get("n_trades"),
                "mean_effective_bets": float(res.diagnostics["effective_bets"].mean())
                if not res.diagnostics.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows).set_index("method")
