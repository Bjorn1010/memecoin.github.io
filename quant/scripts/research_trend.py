"""Multi-asset trend: does the timing layer earn its costs, at a comparable risk level?

Two questions this run exists to answer honestly.

**Is the comparison fair?** A strategy running at 2.4% annualised volatility cannot be
compared to buy-and-hold SPY at 17% by looking at CAGR — the first is barely invested.
Every book here is scaled to the same 10% portfolio volatility target before anything is
measured, so the differences that remain are differences in skill rather than in size.

**Do the costs eat it?** The raw trend signal turned over 7.1x a year and spent 7.8% of
its gross return on execution. A no-trade band is not an optimisation, it is the
difference between a signal and a strategy.

Run:  .venv/bin/python -u scripts/research_trend.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qt.backtest import BacktestConfig, buy_and_hold, compare
from qt.backtest.engine import run_backtest
from qt.backtest.portfolio_backtest import AllocationSpec, build_weights
from qt.config import CostModel
from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES
from qt.risk import apply_no_trade_band, portfolio_vol_target
from qt.strategies.trend import TrendSpec, build_trend, combine_trend_and_allocator
from qt.validation import deflated_sharpe_ratio

pd.set_option("display.width", 240)

ETF_COSTS = CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=1.5)
START = "2010-01-01"
TARGET_VOL = 0.10
# Every distinct configuration evaluated while building this, counted honestly. The
# Deflated Sharpe Ratio is only meaningful if this number is not understated, and
# understating it is the most common way a research report lies without a false statement
# in it.
TRIALS = 12


def load_total_return(catalog: Catalog, symbols) -> dict[str, pd.DataFrame]:
    """Bars restated to total return, so the book collects the dividends it earns."""
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = catalog.read_indexed("eod", "yahoo", symbol)
        if df.empty:
            continue
        ratio = df["adj_close"].astype("float64") / df["close"].astype("float64")
        df = df.loc[START:].copy()
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype("float64") * ratio.loc[df.index]
        out[symbol] = df
    return out


def main() -> None:
    cat = Catalog()
    bars = load_total_return(cat, UNIVERSES["multi_asset"])
    prices = pd.DataFrame({s: b["close"] for s, b in bars.items()}).dropna()
    bars = {s: b.loc[prices.index] for s, b in bars.items()}
    returns = np.log(prices).diff()

    cfg = BacktestConfig(bars_per_year=252, costs=ETF_COSTS, allow_short=True,
                         signal_is_weight=True, max_weight_per_symbol=0.60)

    def targeted(weights: pd.DataFrame, band: bool = True) -> pd.DataFrame:
        w = portfolio_vol_target(weights, returns, target_annual_vol=TARGET_VOL,
                                 bars_per_year=252, max_leverage=3.0)
        return apply_no_trade_band(w) if band else w

    def run(weights: pd.DataFrame):
        aligned = {s: b.loc[b.index.intersection(weights.index)] for s, b in bars.items()}
        return run_backtest(aligned, weights, cfg)

    trend = build_trend(prices, TrendSpec())
    allocation, _ = build_weights(prices, AllocationSpec(
        method="risk_parity", lookback=252, rebalance_every=21,
        covariance="ledoit_wolf", max_weight=0.25, min_history=252))

    results = {
        "trend": run(targeted(trend.weights)),
        "risk_parity": run(targeted(allocation)),
    }
    # Rebalance frequency is a structural choice, not a fitted parameter, and it is the
    # single largest determinant of whether a trend book survives its costs. The signal
    # moves on horizons of 32 to 256 days; rebalancing daily pays to re-express the same
    # view over and over.
    for every, label in ((1, "daily"), (5, "weekly"), (21, "monthly")):
        w = build_trend(prices, TrendSpec(rebalance_every=every)).weights
        results[f"trend {label}"] = run(targeted(w))
    for blend in (0.3, 0.5, 0.7):
        combined = combine_trend_and_allocator(trend.weights, allocation, blend=blend)
        results[f"rp+trend {int(blend * 100)}%"] = run(targeted(combined))
    results["buy_hold_SPY"] = buy_and_hold(bars["SPY"], cfg)

    table = compare(results, 252)
    keep = [c for c in ("cagr", "annual_vol", "sharpe", "sortino", "max_drawdown",
                        "calmar", "turnover_annual", "cost_share_of_gross", "n_trades")
            if c in table.columns]

    print("\n=== every book scaled to the same 10% volatility target ===")
    print("Now CAGR is comparable: the strategies are no longer being penalised for")
    print("running a fraction of the benchmark's risk.\n")
    print(table[keep].sort_values("sharpe", ascending=False).to_string())

    print("\n=== is the best Sharpe real, or the best of several tries? ===\n")
    candidates = table.drop("buy_hold_SPY", errors="ignore")
    best = candidates["sharpe"].astype("float64").idxmax()
    curve = results[best].equity
    rets = curve.pct_change().dropna()

    # The Sharpes of every configuration actually evaluated. Passing these is what makes
    # the deflation real: without a dispersion estimate the function cannot deflate
    # anything, and it now says so rather than reporting an undeflated number as
    # significant.
    trial_sharpes = candidates["sharpe"].astype("float64")
    dsr = deflated_sharpe_ratio(rets, n_trials=max(TRIALS, len(trial_sharpes)),
                                trial_sharpes=trial_sharpes, periods_per_year=252)
    print(f"best strategy       : {best}")
    print(f"configurations tried: {TRIALS} (Sharpes of {len(trial_sharpes)} shown above)")
    for key, value in dsr.items():
        print(f"  {key:22s} {value}")
    print("\nA deflated Sharpe near 0.5 means the result is indistinguishable from the")
    print("best of that many random tries. Near 1.0, it survives the selection.")

    print("\n=== trend diagnostics ===\n")
    for key, value in trend.summary().items():
        print(f"  {key:22s} {value}")


if __name__ == "__main__":
    main()
