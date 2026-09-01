"""Transaction costs — where most backtested edges actually die.

An hourly strategy that turns over its book once a day pays roughly 0.05% x 2 x 365 =
36% a year in taker fees alone, before spread and impact. Any backtest that ignores
this is not optimistic, it is fiction. The default parameters here are public retail
rates, deliberately not the VIP tier, because assuming a fee schedule you do not have
is the same error in a different coat.

Four components, each modelled separately so their contributions can be inspected:

* **Commission** — exchange fee on notional, maker or taker.
* **Spread** — half the bid/ask, paid on every aggressive fill. Estimated from the
  data (Corwin-Schultz) when available, otherwise a fixed floor.
* **Impact** — the strategy's own footprint, as a square-root function of
  participation rate. The square root is the standard empirical form: doubling order
  size costs about 1.4x, not 2x, and the exponent matters enormously for the capacity
  question ("how much can this run before the edge is gone").
* **Funding** — for perpetuals, the actual realised funding series, charged against
  the position held at each funding stamp.

`capacity_curve` answers the question every backtest should be made to answer and
almost never is: at what size does this strategy stop working?
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import CostModel


@dataclass
class FillResult:
    price: float  # effective fill price after spread + impact
    commission: float  # currency units
    spread_cost: float
    impact_cost: float
    slippage_bps: float  # total cost vs the reference price, in bps

    @property
    def total_cost(self) -> float:
        return self.commission + self.spread_cost + self.impact_cost


class CostEngine:
    """Applies a `CostModel` to individual fills and to whole return series."""

    def __init__(self, model: CostModel | None = None) -> None:
        self.model = model or CostModel()

    def fill(
        self,
        *,
        reference_price: float,
        notional: float,
        side: int,
        bar_notional: float | None = None,
        spread_bps: float | None = None,
        volatility_bps: float | None = None,
        is_maker: bool = False,
    ) -> FillResult:
        """Effective fill price and itemised costs for one order.

        `notional` is the absolute order size in quote currency; `side` is +1 buy /
        -1 sell; `bar_notional` is what the whole market traded in that bar, which sets
        the participation rate driving impact; `volatility_bps` is that bar's own
        volatility (its high-low range works well), which sets the impact scale.
        """
        if notional <= 0 or reference_price <= 0:
            return FillResult(reference_price, 0.0, 0.0, 0.0, 0.0)

        m = self.model
        fee_bps = m.maker_fee_bps if is_maker else m.taker_fee_bps
        commission = notional * fee_bps / 1e4

        # A maker order does not cross the spread; it earns the queue instead.
        half_spread_bps = 0.0 if is_maker else (spread_bps / 2 if spread_bps is not None else m.half_spread_bps)
        spread_cost = notional * half_spread_bps / 1e4

        impact_bps = 0.0
        if bar_notional and bar_notional > 0:
            participation = min(notional / bar_notional, 1.0)
            # Square-root law: impact = coeff * sigma * sqrt(participation). Falls back
            # to a 100 bps volatility reference when the caller has no estimate.
            sigma_bps = volatility_bps if volatility_bps and volatility_bps > 0 else 100.0
            impact_bps = m.impact_coeff * sigma_bps * np.sqrt(participation)
        impact_cost = notional * impact_bps / 1e4

        # Costs always move the fill against the trader, regardless of direction.
        adverse_bps = half_spread_bps + impact_bps
        price = reference_price * (1 + side * adverse_bps / 1e4)
        total_bps = (commission + spread_cost + impact_cost) / notional * 1e4
        return FillResult(price, commission, spread_cost, impact_cost, total_bps)

    def turnover_cost(
        self,
        weights: pd.Series,
        equity: pd.Series,
        prices: pd.Series,
        bar_notional: pd.Series | None = None,
        spread_bps: pd.Series | None = None,
        volatility_bps: pd.Series | None = None,
    ) -> pd.Series:
        """Vectorised cost of rebalancing a single-instrument weight series."""
        traded_notional = weights.diff().abs().fillna(weights.abs()) * equity
        m = self.model
        fee = traded_notional * m.taker_fee_bps / 1e4
        half = (spread_bps / 2 if spread_bps is not None else pd.Series(m.half_spread_bps, index=weights.index))
        spread = traded_notional * half / 1e4
        if bar_notional is not None:
            participation = (traded_notional / bar_notional.replace(0.0, np.nan)).clip(upper=1.0)
            sigma = (
                volatility_bps
                if volatility_bps is not None
                else pd.Series(100.0, index=weights.index)
            )
            impact_bps = m.impact_coeff * sigma * np.sqrt(participation).fillna(0.0)
            impact = traded_notional * impact_bps / 1e4
        else:
            impact = pd.Series(0.0, index=weights.index)
        return (fee + spread + impact).fillna(0.0)

    def funding_cost(self, weights: pd.Series, equity: pd.Series, funding_rate: pd.Series) -> pd.Series:
        """Funding paid (positive) or received (negative) on a perp position.

        A long pays when funding is positive. Sign convention: the returned series is a
        cost, so it is subtracted from PnL.
        """
        if not self.model.apply_funding or funding_rate is None or funding_rate.empty:
            return pd.Series(0.0, index=weights.index)
        rate = funding_rate.reindex(weights.index).fillna(0.0)
        return weights * equity * rate

    def borrow_cost(self, weights: pd.Series, equity: pd.Series, bars_per_year: float) -> pd.Series:
        """Financing charged on short exposure for non-perp instruments."""
        rate_per_bar = self.model.short_borrow_annual / bars_per_year
        shorts = (-weights).clip(lower=0.0)
        return shorts * equity * rate_per_bar


def capacity_curve(
    gross_return_per_bar: float,
    turnover_per_bar: float,
    avg_bar_notional: float,
    model: CostModel | None = None,
    sizes: np.ndarray | None = None,
    volatility_bps: float = 100.0,
) -> pd.DataFrame:
    """Net edge as a function of deployed capital.

    Fees and spread scale linearly with size and so leave the *per-unit* edge
    unchanged; impact grows as sqrt(size), so it eventually eats everything. The
    break-even capital is where net return crosses zero — the strategy's capacity, and
    the number that decides whether a result is a business or a curiosity.
    """
    m = model or CostModel()
    sizes = sizes if sizes is not None else np.logspace(3, 8, 40)
    rows = []
    for capital in sizes:
        traded = capital * turnover_per_bar
        participation = min(traded / avg_bar_notional, 1.0) if avg_bar_notional > 0 else 1.0
        fee_bps = m.taker_fee_bps + m.half_spread_bps
        impact_bps = m.impact_coeff * volatility_bps * np.sqrt(participation)
        cost_return = turnover_per_bar * (fee_bps + impact_bps) / 1e4
        rows.append(
            {
                "capital": capital,
                "participation": participation,
                "gross_per_bar": gross_return_per_bar,
                "cost_per_bar": cost_return,
                "net_per_bar": gross_return_per_bar - cost_return,
            }
        )
    return pd.DataFrame(rows)


def spread_from_quotes(quotes: pd.DataFrame, bar_index: pd.DatetimeIndex) -> pd.Series:
    """True bid-ask spread in bps per bar, from top-of-book quote data.

    This is the correct way to cost the spread, and it is free: the Binance archive
    publishes `bookTicker` for USD-M futures (see data/sources/binance_vision.py),
    which is every best bid/ask update. Everything else on this page is an estimator
    standing in for this measurement.
    """
    if quotes is None or quotes.empty:
        return pd.Series(np.nan, index=bar_index)
    q = quotes.copy()
    if not isinstance(q.index, pd.DatetimeIndex):
        q.index = pd.to_datetime(q["ts"], unit="ms", utc=True)
    mid = (q["ask"] + q["bid"]) / 2.0
    spread_bps = ((q["ask"] - q["bid"]) / mid.replace(0.0, np.nan)) * 1e4
    # Mean spread within each bar, then aligned onto the bar grid.
    binned = spread_bps.groupby(bar_index.searchsorted(spread_bps.index, side="left")).mean()
    out = pd.Series(np.nan, index=bar_index)
    valid = binned.index[(binned.index >= 0) & (binned.index < len(bar_index))]
    out.iloc[valid] = binned.loc[valid].to_numpy()
    return out.ffill()


def estimate_spread_bps(
    bars: pd.DataFrame, window: int = 168, floor_bps: float = 0.5, cap_bps: float = 25.0
) -> pd.Series:
    """Corwin-Schultz spread estimate from high/low. Use with care on intraday bars.

    **Known bias, and it is large.** Corwin-Schultz assumes the bar's high and low are
    transaction prices bracketing a bid-ask bounce. That holds reasonably on daily
    equity bars. On hourly crypto bars the range is dominated by real volatility rather
    than by the spread, so the estimator saturates: it returns ~16 bps median on hourly
    BTCUSDT, where the actual top-of-book spread is under 1 bp — a 20x overstatement,
    easily enough to declare a genuinely profitable strategy dead.

    Consequently this is NOT the backtester's default. Prefer, in order:
      1. `spread_from_quotes` on the free bookTicker archive (a measurement);
      2. a fixed conservative constant for liquid majors (`CostModel.half_spread_bps`);
      3. this estimator, for illiquid instruments with no quote data, where its upward
         bias is at least conservative in the right direction.

    Capped at `cap_bps` so a single violent bar cannot make a period untradable.
    """
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    beta = (np.log(h / l) ** 2).rolling(2, min_periods=2).sum()
    h2 = h.rolling(2, min_periods=2).max()
    l2 = l.rolling(2, min_periods=2).min()
    gamma = np.log(h2 / l2) ** 2
    denom = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / denom - np.sqrt(gamma / denom)
    spread = (2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))).clip(lower=0) * 1e4
    smoothed = spread.rolling(window, min_periods=max(window // 8, 4)).median()
    return smoothed.fillna(floor_bps).clip(lower=floor_bps, upper=cap_bps)
