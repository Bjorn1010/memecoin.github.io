"""Event-driven backtester.

The design rule that everything else follows from: **a signal computed from bar t's
close is executed at bar t+1's open**. Not at t's close, which is the most common
silent cheat in backtesting code — you cannot trade at a price that is only known
because the bar has already finished. The lag is enforced structurally in the loop
rather than by remembering to shift a series, because a forgotten shift is invisible
and turns a losing strategy into a spectacular one.

What is modelled:

* fills at the next bar's open, adjusted for spread and square-root impact;
* commission on every fill, at retail taker rates by default;
* funding on perpetual positions, from the venue's realised funding series;
* a rebalance threshold, so the book does not churn on noise;
* the risk engine sitting between the requested weights and the executed ones, with
  its circuit breakers live during the backtest exactly as they would be in the paper
  loop — so a backtest can and does get halted by its own drawdown limit.

What is not modelled, and should be understood as an optimistic assumption: the
strategy's own orders do not move the market for other participants, there are no
outages, and every order fills. Those matter at size; `costs.capacity_curve` is the
tool for asking where.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import CostModel, RiskLimits
from ..risk.limits import RiskEngine
from ..risk.sizing import volatility_target_weight
from .costs import CostEngine, estimate_spread_bps, spread_from_quotes
from .metrics import performance_metrics


@dataclass
class BacktestConfig:
    starting_equity: float = 100_000.0
    bars_per_year: float = 365 * 24
    target_annual_vol: float = 0.20
    execution_lag_bars: int = 1  # signal at t -> fill at t + lag (open)
    # No-trade band. A purely absolute threshold behaves badly across leverage levels:
    # the same 0.05 is a no-op for a 0.5 position and a full flip for a 0.04 one. The
    # band is therefore the larger of an absolute floor and a fraction of the target,
    # which is the standard construction — it stops the book churning on noise while
    # still allowing a genuine change of view through.
    rebalance_threshold: float = 0.02  # absolute floor, in weight units
    rebalance_threshold_relative: float = 0.25  # fraction of the target weight
    allow_short: bool = True
    vol_span: int = 168  # EWMA span for the volatility forecast used in sizing
    costs: CostModel = field(default_factory=CostModel)
    risk: RiskLimits = field(default_factory=RiskLimits)
    # Off by default: the Corwin-Schultz estimator is badly upward-biased on intraday
    # bars (see costs.estimate_spread_bps). Supply real quotes via `quotes=` instead,
    # or leave the conservative constant in CostModel.half_spread_bps.
    use_estimated_spread: bool = False
    max_weight_per_symbol: float | None = None  # defaults to risk.max_position_weight
    # Set when the incoming signal is already a portfolio weight rather than a view in
    # [-1, 1] — a portfolio allocator's output, for instance. Without it the engine
    # multiplies every weight by target_vol / instrument_vol, which turns each allocator
    # into a hybrid of itself and inverse-volatility. The optimisers then look far more
    # alike than they are, and gross exposure collapses: a book of 15 equal weights
    # summing to 1.0 came out running 3.4% realised volatility against a 10% target.
    signal_is_weight: bool = False

    def to_meta(self) -> dict:
        return {
            "starting_equity": self.starting_equity,
            "bars_per_year": self.bars_per_year,
            "target_annual_vol": self.target_annual_vol,
            "execution_lag_bars": self.execution_lag_bars,
            "rebalance_threshold": self.rebalance_threshold,
            "rebalance_threshold_relative": self.rebalance_threshold_relative,
            "allow_short": self.allow_short,
            "taker_fee_bps": self.costs.taker_fee_bps,
            "half_spread_bps": self.costs.half_spread_bps,
            "impact_coeff": self.costs.impact_coeff,
            "max_gross_leverage": self.risk.max_gross_leverage,
            "max_drawdown": self.risk.max_drawdown,
            "max_daily_loss": self.risk.max_daily_loss,
        }


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    target_weights: pd.DataFrame
    trades: pd.DataFrame
    costs: pd.Series
    funding: pd.Series
    risk_log: pd.DataFrame
    config: BacktestConfig
    metrics: dict = field(default_factory=dict)

    def summary(self) -> pd.Series:
        return pd.Series(self.metrics)

    @property
    def turnover(self) -> pd.Series:
        return self.weights.diff().abs().sum(axis=1).fillna(0.0)


def run_backtest(
    prices: dict[str, pd.DataFrame],
    signals: pd.DataFrame,
    config: BacktestConfig | None = None,
    *,
    funding: dict[str, pd.Series] | None = None,
    quotes: dict[str, pd.DataFrame] | None = None,
) -> BacktestResult:
    """Run a multi-instrument backtest.

    `prices` maps symbol -> bars (DatetimeIndex; open/high/low/close, optionally
    quote_volume for the impact model). `signals` is a timestamp x symbol matrix of
    conviction in [-1, 1], stamped at the bar whose close produced them.
    """
    config = config or BacktestConfig()
    if signals.empty or not prices:
        empty = pd.Series(dtype="float64")
        return BacktestResult(
            empty, empty, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), empty, empty,
            pd.DataFrame(), config, {},
        )

    symbols = [s for s in signals.columns if s in prices]
    if not symbols:
        raise ValueError("no overlap between signal columns and price symbols")

    # One shared timeline: the intersection of every instrument's bars with the signal
    # index. Union would require assuming a price where none was observed.
    index = signals.index
    for s in symbols:
        index = index.intersection(prices[s].index)
    index = index.sort_values()
    if len(index) < config.execution_lag_bars + 2:
        raise ValueError(f"only {len(index)} shared bars; not enough to simulate")

    opens = pd.DataFrame({s: prices[s]["open"].reindex(index) for s in symbols})
    closes = pd.DataFrame({s: prices[s]["close"].reindex(index) for s in symbols})
    notional = pd.DataFrame(
        {
            s: (
                prices[s]["quote_volume"].reindex(index)
                if "quote_volume" in prices[s].columns
                else prices[s]["volume"].reindex(index) * prices[s]["close"].reindex(index)
            )
            for s in symbols
        }
    )
    # Spread, in order of preference: measured from real quotes, then the (biased)
    # high-low estimator if explicitly asked for, then a conservative constant.
    spread_cols = {}
    for s in symbols:
        measured = (
            spread_from_quotes(quotes[s], index)
            if quotes and s in quotes and quotes[s] is not None
            else pd.Series(np.nan, index=index)
        )
        if measured.notna().any():
            spread_cols[s] = measured
        elif config.use_estimated_spread:
            spread_cols[s] = estimate_spread_bps(prices[s]).reindex(index)
        else:
            spread_cols[s] = pd.Series(config.costs.half_spread_bps * 2, index=index)
    spreads = pd.DataFrame(spread_cols)

    # Per-bar volatility forecast used for sizing — causal EWMA of realised returns.
    rets = np.log(closes).diff()
    vol = rets.ewm(span=config.vol_span, min_periods=max(config.vol_span // 4, 20)).std()

    # Bar volatility in bps, used to scale market impact. The high-low range is the
    # standard cheap proxy and, unlike a constant, it widens exactly when the strategy
    # is most likely to be trading.
    range_bps = pd.DataFrame(
        {
            s: (
                (prices[s]["high"].reindex(index) - prices[s]["low"].reindex(index))
                / prices[s]["close"].reindex(index)
            )
            * 1e4
            for s in symbols
        }
    ).fillna(100.0)

    sig = signals[symbols].reindex(index).fillna(0.0)
    if not config.allow_short:
        sig = sig.clip(lower=0.0)

    max_w = config.max_weight_per_symbol or config.risk.max_position_weight
    if config.signal_is_weight:
        # The caller sized the book already; only the per-instrument cap applies.
        desired = pd.DataFrame({s: sig[s].astype("float64").clip(-max_w, max_w) for s in symbols})
    else:
        desired = pd.DataFrame(
            {
                s: volatility_target_weight(
                    sig[s],
                    vol[s],
                    target_annual_vol=config.target_annual_vol,
                    bars_per_year=config.bars_per_year,
                    max_leverage=config.risk.max_gross_leverage,
                ).clip(-max_w, max_w)
                for s in symbols
            }
        )

    cost_engine = CostEngine(config.costs)
    risk_engine = RiskEngine(config.risk, config.starting_equity)

    cash = config.starting_equity
    qty = {s: 0.0 for s in symbols}
    equity_curve = np.full(len(index), np.nan)
    weight_hist = np.zeros((len(index), len(symbols)))
    target_hist = np.zeros((len(index), len(symbols)))
    cost_hist = np.zeros(len(index))
    funding_hist = np.zeros(len(index))
    trades: list[dict] = []

    lag = config.execution_lag_bars
    open_arr = opens.to_numpy()
    close_arr = closes.to_numpy()
    notional_arr = notional.fillna(0.0).to_numpy()
    spread_arr = spreads.fillna(config.costs.half_spread_bps * 2).to_numpy()
    range_arr = range_bps.to_numpy()
    desired_arr = desired.fillna(0.0).to_numpy()

    funding_arr = np.zeros((len(index), len(symbols)))
    if funding:
        for j, s in enumerate(symbols):
            if s in funding and funding[s] is not None and not funding[s].empty:
                funding_arr[:, j] = funding[s].reindex(index).fillna(0.0).to_numpy()

    for i, ts in enumerate(index):
        prices_now = close_arr[i]
        # Mark the book at this bar's close.
        mtm = float(np.nansum([qty[s] * prices_now[j] for j, s in enumerate(symbols)]))
        equity = cash + mtm
        equity_curve[i] = equity
        risk_engine.mark(equity, ts)

        # Funding on perp positions held into this bar's stamp.
        if funding:
            paid = 0.0
            for j, s in enumerate(symbols):
                rate = funding_arr[i, j]
                if rate != 0.0 and qty[s] != 0.0:
                    paid += qty[s] * prices_now[j] * rate
            if paid:
                cash -= paid
                funding_hist[i] = paid
                equity = cash + mtm
                equity_curve[i] = equity

        weight_hist[i] = [qty[s] * prices_now[j] / equity if equity > 0 else 0.0 for j, s in enumerate(symbols)]

        # The signal from bar i is executed at bar i+lag's open. Stop before the end.
        exec_i = i + lag
        if exec_i >= len(index):
            continue

        raw_target = pd.Series(desired_arr[i], index=symbols)
        target_hist[i] = raw_target.to_numpy()
        decision = risk_engine.apply(raw_target, timestamp=ts, equity=equity)
        target = decision.weights

        fill_prices = open_arr[exec_i]
        for j, s in enumerate(symbols):
            price = fill_prices[j]
            if not np.isfinite(price) or price <= 0:
                continue
            current_w = qty[s] * price / equity if equity > 0 else 0.0
            target_w = float(target[s])
            delta_w = target_w - current_w
            band = max(config.rebalance_threshold, config.rebalance_threshold_relative * abs(target_w))
            if abs(delta_w) < band:
                continue
            trade_notional = abs(delta_w) * equity
            if trade_notional < config.risk.min_trade_notional:
                continue
            side = 1 if delta_w > 0 else -1
            fill = cost_engine.fill(
                reference_price=price,
                notional=trade_notional,
                side=side,
                bar_notional=float(notional_arr[exec_i, j]) or None,
                spread_bps=float(spread_arr[exec_i, j]),
                volatility_bps=float(range_arr[exec_i, j]),
            )
            delta_qty = side * trade_notional / fill.price
            cash -= delta_qty * fill.price
            cash -= fill.commission
            qty[s] += delta_qty
            cost_hist[exec_i] += fill.commission + fill.spread_cost + fill.impact_cost
            trades.append(
                {
                    "ts": index[exec_i],
                    "symbol": s,
                    "side": "buy" if side > 0 else "sell",
                    "notional": trade_notional,
                    "price": fill.price,
                    "reference_price": price,
                    "qty": delta_qty,
                    "commission": fill.commission,
                    "spread_cost": fill.spread_cost,
                    "impact_cost": fill.impact_cost,
                    "slippage_bps": fill.slippage_bps,
                    "target_weight": target_w,
                    "prior_weight": current_w,
                    "risk_scale": decision.scale,
                    "risk_reason": "; ".join(decision.reasons),
                }
            )

    equity_series = pd.Series(equity_curve, index=index, name="equity").ffill()
    returns = equity_series.pct_change().fillna(0.0)
    weights_df = pd.DataFrame(weight_hist, index=index, columns=symbols)
    targets_df = pd.DataFrame(target_hist, index=index, columns=symbols)
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df = trades_df.set_index("ts")

    result = BacktestResult(
        equity=equity_series,
        returns=returns,
        weights=weights_df,
        target_weights=targets_df,
        trades=trades_df,
        costs=pd.Series(cost_hist, index=index, name="costs"),
        funding=pd.Series(funding_hist, index=index, name="funding"),
        risk_log=risk_engine.log_frame(),
        config=config,
    )
    result.metrics = performance_metrics(result, bars_per_year=config.bars_per_year)
    return result


def buy_and_hold(prices: pd.DataFrame, config: BacktestConfig | None = None) -> BacktestResult:
    """Benchmark: buy once at the first open, hold to the end.

    Every strategy result must be read against this. A crypto strategy with a Sharpe of
    1.0 in a year when simply holding BTC returned 150% has demonstrated nothing except
    an expensive way to underperform.

    Computed analytically rather than through the engine: one entry, one set of costs,
    no rebalancing, no risk limits. Fewer moving parts means the benchmark cannot
    itself be the thing that is wrong.
    """
    config = config or BacktestConfig()
    close = prices["close"].astype("float64").dropna()
    if close.empty:
        empty = pd.Series(dtype="float64")
        return BacktestResult(
            empty, empty, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), empty, empty,
            pd.DataFrame(), config, {},
        )

    entry_cost_bps = config.costs.taker_fee_bps + config.costs.half_spread_bps
    equity = config.starting_equity * (1 - entry_cost_bps / 1e4) * (close / close.iloc[0])
    equity.name = "equity"
    weights = pd.DataFrame(1.0, index=close.index, columns=["BENCH"])
    result = BacktestResult(
        equity=equity,
        returns=equity.pct_change().fillna(0.0),
        weights=weights,
        target_weights=weights,
        trades=pd.DataFrame(),
        costs=pd.Series(0.0, index=close.index),
        funding=pd.Series(0.0, index=close.index),
        risk_log=pd.DataFrame(),
        config=config,
    )
    result.metrics = performance_metrics(result, bars_per_year=config.bars_per_year)
    return result
