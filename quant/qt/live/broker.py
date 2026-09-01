"""Paper broker.

This system is paper-only by design: there is no venue adapter, no API key handling,
no order-signing code anywhere in the repository. That is a deliberate constraint, not
an unfinished feature — it means a bug can cost time and nothing else.

What the broker does model, because getting these wrong is what makes paper results
meaningless:

* fills at the *next observed price*, never at the price that triggered the decision;
* the same cost model the backtester uses, so a live paper run and a backtest of the
  same period are directly comparable — if they diverge, one of them is wrong and you
  want to know;
* realised and unrealised PnL tracked separately, with average-cost accounting;
* every fill persisted with its reason.

Because it shares `CostEngine` with the backtester, the paper loop is a continuous
validation of the backtest's cost assumptions rather than a separate implementation
that quietly disagrees.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..backtest.costs import CostEngine
from ..config import CostModel
from .state import LiveState, Position, Store


@dataclass
class Order:
    symbol: str
    side: int  # +1 buy, -1 sell
    notional: float
    reason: str = ""


@dataclass
class Fill:
    symbol: str
    side: str
    qty: float
    price: float
    reference_price: float
    notional: float
    commission: float
    spread_cost: float
    impact_cost: float
    slippage_bps: float
    reason: str
    ts: int

    def to_dict(self) -> dict:
        """Fill fields excluding symbol/ts, which callers pass positionally."""
        return {
            "side": self.side, "qty": self.qty, "price": self.price,
            "reference_price": self.reference_price, "notional": self.notional,
            "commission": self.commission, "spread_cost": self.spread_cost,
            "impact_cost": self.impact_cost, "slippage_bps": self.slippage_bps,
            "reason": self.reason,
        }


@dataclass
class PaperBroker:
    run_id: str
    starting_equity: float = 100_000.0
    costs: CostModel = field(default_factory=CostModel)
    store: Store | None = None
    min_trade_notional: float = 10.0

    def __post_init__(self) -> None:
        self.cost_engine = CostEngine(self.costs)
        self.state = LiveState(self.run_id, self.starting_equity, self.starting_equity)
        self.realised_pnl = 0.0
        self.total_costs = 0.0
        self.fills: list[Fill] = []
        if self.store is not None:
            restored = self.store.load_positions(self.run_id)
            if restored:
                self.state.positions = restored

    # ------------------------------------------------------------ accounting
    def mark_to_market(self, prices: dict[str, float]) -> float:
        """Recompute equity from cash plus marked positions."""
        mtm = 0.0
        for symbol, pos in self.state.positions.items():
            price = prices.get(symbol)
            if price is not None and pos.qty != 0:
                mtm += pos.qty * price
        self.state.equity = self.state.cash + mtm
        return self.state.equity

    def gross_exposure(self, prices: dict[str, float]) -> float:
        if self.state.equity <= 0:
            return 0.0
        gross = sum(
            abs(pos.qty * prices.get(symbol, 0.0)) for symbol, pos in self.state.positions.items()
        )
        return gross / self.state.equity

    def current_weights(self, prices: dict[str, float]) -> dict[str, float]:
        if self.state.equity <= 0:
            return {s: 0.0 for s in self.state.positions}
        return {
            symbol: pos.qty * prices.get(symbol, 0.0) / self.state.equity
            for symbol, pos in self.state.positions.items()
        }

    # ---------------------------------------------------------------- trading
    def rebalance(
        self,
        target_weights: dict[str, float],
        prices: dict[str, float],
        *,
        ts: int,
        bar_notional: dict[str, float] | None = None,
        spread_bps: dict[str, float] | None = None,
        volatility_bps: dict[str, float] | None = None,
        band: float = 0.02,
        band_relative: float = 0.25,
        reason: str = "",
    ) -> list[Fill]:
        """Move the book toward `target_weights`, respecting the no-trade band."""
        self.mark_to_market(prices)
        equity = self.state.equity
        if equity <= 0:
            return []

        current = self.current_weights(prices)
        out: list[Fill] = []

        for symbol, target in target_weights.items():
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue
            now = current.get(symbol, 0.0)
            delta_w = target - now
            threshold = max(band, band_relative * abs(target))
            if abs(delta_w) < threshold:
                continue
            notional = abs(delta_w) * equity
            if notional < self.min_trade_notional:
                continue
            side = 1 if delta_w > 0 else -1
            fill = self.execute(
                Order(symbol, side, notional, reason),
                price,
                ts=ts,
                bar_notional=(bar_notional or {}).get(symbol),
                spread_bps=(spread_bps or {}).get(symbol),
                volatility_bps=(volatility_bps or {}).get(symbol),
            )
            if fill is not None:
                out.append(fill)

        self.mark_to_market(prices)
        if self.store is not None:
            self.store.save_positions(self.run_id, self.state.positions, ts)
        return out

    def execute(
        self,
        order: Order,
        reference_price: float,
        *,
        ts: int,
        bar_notional: float | None = None,
        spread_bps: float | None = None,
        volatility_bps: float | None = None,
    ) -> Fill | None:
        """Simulate one fill and book it."""
        if order.notional < self.min_trade_notional or reference_price <= 0:
            return None

        result = self.cost_engine.fill(
            reference_price=reference_price,
            notional=order.notional,
            side=order.side,
            bar_notional=bar_notional,
            spread_bps=spread_bps,
            volatility_bps=volatility_bps,
        )
        qty = order.side * order.notional / result.price
        pos = self.state.position(order.symbol)
        realised = pos.apply_fill(qty, result.price)

        self.state.cash -= qty * result.price
        self.state.cash -= result.commission
        self.realised_pnl += realised
        self.total_costs += result.total_cost

        fill = Fill(
            symbol=order.symbol,
            side="buy" if order.side > 0 else "sell",
            qty=qty,
            price=result.price,
            reference_price=reference_price,
            notional=order.notional,
            commission=result.commission,
            spread_cost=result.spread_cost,
            impact_cost=result.impact_cost,
            slippage_bps=result.slippage_bps,
            reason=order.reason,
            ts=ts,
        )
        self.fills.append(fill)
        if self.store is not None:
            self.store.record_fill(self.run_id, ts, order.symbol, **fill.to_dict())
        return fill

    def flatten(self, prices: dict[str, float], ts: int, reason: str = "flatten") -> list[Fill]:
        """Close everything, by quantity. Called by the risk engine's circuit breakers.

        Closing by *quantity* rather than by target weight matters: a weight-based
        close computes a notional from the pre-trade mark and then fills at a
        cost-adjusted price, which leaves a small residual position behind. When a
        circuit breaker fires, "flat" has to mean flat.
        """
        out: list[Fill] = []
        for symbol, pos in list(self.state.positions.items()):
            if pos.qty == 0:
                continue
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue
            side = -1 if pos.qty > 0 else 1
            fill = self.execute(
                Order(symbol, side, abs(pos.qty) * price, reason), price, ts=ts
            )
            if fill is not None:
                out.append(fill)
            # Any residue is the cost wedge between the mark and the fill price; the
            # position is closed, so book it as such rather than leaving dust.
            if pos.qty != 0:
                self.state.cash += pos.qty * price
                pos.qty = 0.0
                pos.avg_price = 0.0
        self.mark_to_market(prices)
        if self.store is not None:
            self.store.save_positions(self.run_id, self.state.positions, ts)
        return out

    # ---------------------------------------------------------------- reports
    def snapshot(self, prices: dict[str, float]) -> dict:
        equity = self.mark_to_market(prices)
        positions = []
        for symbol, pos in self.state.positions.items():
            if pos.qty == 0:
                continue
            price = prices.get(symbol, pos.avg_price)
            positions.append(
                {
                    "symbol": symbol,
                    "qty": pos.qty,
                    "avg_price": pos.avg_price,
                    "mark": price,
                    "notional": pos.qty * price,
                    "weight": pos.qty * price / equity if equity else 0.0,
                    "unrealised_pnl": (price - pos.avg_price) * pos.qty,
                }
            )
        return {
            "run_id": self.run_id,
            "equity": equity,
            "cash": self.state.cash,
            "realised_pnl": self.realised_pnl,
            "unrealised_pnl": sum(p["unrealised_pnl"] for p in positions),
            "total_costs": self.total_costs,
            "gross_exposure": self.gross_exposure(prices),
            "n_positions": len(positions),
            "n_fills": len(self.fills),
            "positions": positions,
        }

    def fills_frame(self) -> pd.DataFrame:
        if not self.fills:
            return pd.DataFrame()
        df = pd.DataFrame([{"symbol": f.symbol, "ts": f.ts, **f.to_dict()} for f in self.fills])
        df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df
