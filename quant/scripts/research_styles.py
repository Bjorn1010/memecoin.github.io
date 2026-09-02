"""Do four styles beat one? Measured, at a matched risk level, after costs.

Trend alone is a bet on one phenomenon, and trend has decade-long droughts — 2011 to 2019
was the worst stretch in its recorded history and it nearly emptied the industry. The
question this run answers is whether the other three styles diversify it in practice or
only in theory.

The number to read first is the style correlation matrix. Styles correlating above
roughly 0.5 are one bet counted four times, and any improvement in the combined book is
then just leverage. Below that, the combination is real.

Run:  .venv/bin/python -u scripts/research_styles.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qt.backtest import BacktestConfig, buy_and_hold, compare
from qt.backtest.engine import run_backtest
from qt.config import CostModel
from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES
from qt.risk import apply_no_trade_band, portfolio_vol_target
from qt.strategies.styles import StyleSpec, build_styles, dividend_yields
from qt.validation import deflated_sharpe_ratio

pd.set_option("display.width", 240)

ETF_COSTS = CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=1.5)
TARGET_VOL = 0.10
# Configurations evaluated across this whole project's multi-asset work, counted
# honestly. Understating this is the commonest way a research report misleads without
# containing a false statement.
TRIALS = 20


def main() -> None:
    cat = Catalog()
    symbols = UNIVERSES["multi_asset"]

    bars: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = cat.read_indexed("eod", "yahoo", symbol)
        if df.empty:
            continue
        # Total return: the engine must trade the series a holder actually experienced,
        # or the whole bond and credit sleeve is measured short by its coupon.
        ratio = df["adj_close"].astype("float64") / df["close"].astype("float64")
        df = df.copy()
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype("float64") * ratio
        bars[symbol] = df

    prices = pd.DataFrame({s: b["close"] for s, b in bars.items()}).dropna()
    bars = {s: b.loc[prices.index] for s, b in bars.items()}
    returns = np.log(prices).diff()
    yields = dividend_yields(cat, symbols)

    cfg = BacktestConfig(bars_per_year=252, costs=ETF_COSTS, allow_short=True,
                         signal_is_weight=True, max_weight_per_symbol=0.60)

    def dress(weights: pd.DataFrame) -> pd.DataFrame:
        sized = portfolio_vol_target(weights, returns, target_annual_vol=TARGET_VOL,
                                     bars_per_year=252, max_leverage=3.0)
        return apply_no_trade_band(sized)

    def run(weights: pd.DataFrame):
        w = dress(weights)
        return run_backtest({s: b.loc[b.index.intersection(w.index)] for s, b in bars.items()},
                            w, cfg)

    full = build_styles(prices, StyleSpec(), yields=yields)

    print("\n=== are the four styles actually different bets? ===")
    print("Above roughly 0.5 they are one bet counted four times.\n")
    print(full.correlation().round(3).to_string())
    print(f"\nlargest off-diagonal correlation: {full.diagnostics['max_style_correlation']}")

    results = {"all four (directional)": run(full.weights)}
    xs = build_styles(prices, StyleSpec(mode="cross_sectional"), yields=yields)
    results["all four (market-neutral)"] = run(xs.weights)
    # Each style alone, at the same risk level, so the comparison is about signal
    # rather than size.
    for name in ("trend", "carry", "value", "defensive"):
        spec = StyleSpec(weights={k: (1.0 if k == name else 0.0)
                                  for k in ("trend", "carry", "value", "defensive")})
        solo = build_styles(prices, spec, yields=yields)
        results[f"{name} only"] = run(solo.weights)
    results["buy_hold_SPY"] = buy_and_hold(bars["SPY"], cfg)

    table = compare(results, 252)
    keep = [c for c in ("cagr", "annual_vol", "sharpe", "sortino", "max_drawdown",
                        "calmar", "turnover_annual", "cost_share_of_gross", "n_trades")
            if c in table.columns]

    print("\n=== every book at the same 10% volatility target, after costs ===\n")
    print(table[keep].sort_values("sharpe", ascending=False).to_string())

    combined = float(table.loc["all four (directional)", "sharpe"])
    solos = [float(table.loc[f"{n} only", "sharpe"]) for n in
             ("trend", "carry", "value", "defensive")]
    print(f"\ncombined Sharpe {combined:.3f} vs best single style {max(solos):.3f}")
    print("A combination that does not beat its best component is not diversifying,")
    print("it is averaging — and the simpler single style should be preferred.")

    print("\n=== is it real, or the best of many tries? ===\n")
    candidates = table.drop("buy_hold_SPY", errors="ignore")
    rets = results["all four (directional)"].equity.pct_change().dropna()
    dsr = deflated_sharpe_ratio(rets, n_trials=TRIALS,
                                trial_sharpes=candidates["sharpe"].astype("float64"),
                                periods_per_year=252)
    for key, value in dsr.items():
        print(f"  {key:22s} {value}")

    print("\n=== diagnostics ===\n")
    for key, value in full.diagnostics.items():
        print(f"  {key:24s} {value}")


if __name__ == "__main__":
    main()
