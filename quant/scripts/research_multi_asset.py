"""Multi-asset research run: diversification, allocators and trend, honestly costed.

This is the run that answers "does the portfolio machinery do anything, or does it only
look sophisticated". On ten crypto pairs it could not: they are one bet wearing ten
tickers, so every optimiser produced roughly the same book and the comparison was
meaningless. A fifteen-instrument multi-asset book spanning equities, duration, credit,
commodities, the dollar and real estate is the first universe here with genuine
structure to exploit.

Run:  .venv/bin/python scripts/research_multi_asset.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qt.backtest import BacktestConfig
from qt.backtest.portfolio_backtest import AllocationSpec, compare_allocations
from qt.config import CostModel
from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES
from qt.portfolio.covariance import marchenko_pastur_bounds
from qt.portfolio.risk import effective_number_of_bets

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

# Retail US ETF costs, and they are genuinely different from crypto. Commission is zero
# at every major US broker on US-listed ETFs, which makes the spread the entire cost.
# 1.5bp half-spread is a blend: SPY and QQQ quote inside a quarter of a basis point,
# while DBC, UUP and USO are several. Using the crypto default of 5bp taker plus 1bp
# half-spread would overstate the cost of this book by roughly an order of magnitude and
# reject strategies that are in fact viable.
ETF_COSTS = CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=1.5)

START = "2010-01-01"  # UUP and HYG both exist from 2007; 2010 gives a clean common window


def load(catalog: Catalog, symbols, *, total_return: bool = False) -> dict[str, pd.DataFrame]:
    """Bars keyed by symbol.

    The engine prices fills off `close` and never credits a dividend, so a book of ETFs
    yielding 2-6% is measured short by exactly that much every year — on HYG, 6.33% a
    year, which is more than the strategy's entire return. `total_return=True` swaps the
    OHLC for the dividend-adjusted series so the equity curve reflects what a holder
    actually received.

    That swap is not free of assumptions. Yahoo's adjusted series is restated backwards
    every time a dividend is paid, so today's adjusted 2010 price embeds information from
    2011 onwards. It is safe here because this engine sizes positions as a *fraction of
    equity*: only the ratios between consecutive prices enter, and those are correct.
    It would not be safe for dollar-denominated sizing, a price threshold, or an impact
    model calibrated on price level.
    """
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = catalog.read_indexed("eod", "yahoo", symbol)
        if df.empty:
            continue
        df = df.loc[START:].copy()
        if total_return and "adj_close" in df.columns:
            ratio = df["adj_close"].astype("float64") / df["close"].astype("float64")
            for col in ("open", "high", "low", "close"):
                df[col] = df[col].astype("float64") * ratio
        out[symbol] = df
    return out


def diversification(returns: pd.DataFrame, periods: float) -> dict:
    cov = returns.cov() * periods
    weights = pd.Series(1.0 / returns.shape[1], index=returns.columns)
    corr = returns.corr().to_numpy()
    eigenvalues = np.linalg.eigvalsh(corr)[::-1]
    _, upper = marchenko_pastur_bounds(len(returns), returns.shape[1])
    return {
        "assets": returns.shape[1],
        "observations": len(returns),
        "effective_bets": round(float(effective_number_of_bets(weights, cov)), 2),
        "mp_factors": int((eigenvalues > upper).sum()),
        "mean_correlation": round(float(corr[np.triu_indices(returns.shape[1], 1)].mean()), 3),
    }


def main() -> None:
    cat = Catalog()

    # ---------------------------------------------------------- diversification
    prices = load(cat, UNIVERSES["multi_asset"])
    rets = pd.DataFrame(
        {s: np.log(df["adj_close"].astype("float64")).diff() for s, df in prices.items()}
    ).dropna()

    crypto = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
              "LTCUSDT", "DOGEUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT"]
    crypto_rets = pd.DataFrame({
        s: np.log(cat.read_indexed("klines_1d", "binance", s)["close"].astype("float64")).diff()
        for s in crypto
        if not cat.read_indexed("klines_1d", "binance", s).empty
    }).dropna()

    table = pd.DataFrame([
        {"book": "multi-asset ETF", **diversification(rets, 252)},
        {"book": "crypto", **diversification(crypto_rets, 365)},
    ])
    print("\n=== diversification ===")
    print("effective_bets is the number of independent bets the book actually holds.")
    print("mp_factors counts eigenvalues above the Marchenko-Pastur noise bound.\n")
    print(table.to_string(index=False))

    # --------------------------------------------------------------- allocators
    cfg = BacktestConfig(bars_per_year=252, costs=ETF_COSTS, target_annual_vol=0.10)
    spec = AllocationSpec(lookback=252, rebalance_every=21, covariance="ledoit_wolf",
                          max_weight=0.25, min_history=252)

    keep = ["cagr", "annual_vol", "sharpe", "max_drawdown",
            "turnover_annual", "cost_share_of_gross", "n_trades"]

    print("\n=== allocators, traded with costs, TOTAL RETURN (dividends credited) ===")
    print("Read turnover_annual and cost_share_of_gross next to sharpe. An optimiser")
    print("that wins gross and churns the book has not won.\n")
    total = compare_allocations(load(cat, UNIVERSES["multi_asset"], total_return=True),
                                spec=spec, config=cfg)
    cols = [c for c in keep if c in total.columns]
    print(total[cols].sort_values("sharpe", ascending=False).to_string())

    print("\n=== the same book on raw closes (price return only) ===")
    print("The difference between these two tables is the dividend. It is not a detail:")
    print("HYG yields 6.33% a year, LQD 4.35%, TLT 3.50%. A backtest on raw closes")
    print("discards all of it and reports the strategy as that much worse.\n")
    price = compare_allocations(prices, spec=spec, config=cfg)
    print(price[cols].sort_values("sharpe", ascending=False).to_string())

    gap = pd.DataFrame({
        "cagr_total_return": total["cagr"],
        "cagr_price_only": price["cagr"],
        "dividend_contribution": total["cagr"] - price["cagr"],
        "sharpe_total_return": total["sharpe"],
        "sharpe_price_only": price["sharpe"],
    }).sort_values("dividend_contribution", ascending=False)
    print("\n=== what ignoring dividends costs ===\n")
    print(gap.to_string())


if __name__ == "__main__":
    main()
