"""The paper-trading loop.

One pass per closed bar, in a fixed order that mirrors the backtester exactly:

    bar closes -> append to history -> features -> strategy signal -> vol-target size
    -> risk engine -> broker rebalance -> mark to market -> persist

The ordering is the contract. The signal is computed from the bar that just *closed*,
and the fill happens at the next observed price — never at the close that produced the
decision. This is the same rule the backtester enforces structurally, which is what
makes a paper run and a backtest of the same period comparable. When they disagree,
one of them has a bug, and that comparison is the loop's most valuable output.

The loop is defensive by construction: a feed exception, a NaN signal, or a strategy
that raises never takes the process down or leaves a position unmanaged. Anything it
cannot understand results in *no new risk*, not in a guess.
"""

from __future__ import annotations

import asyncio
import signal as os_signal
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..config import CONFIG, CostModel, RiskLimits
from ..risk.limits import RiskEngine
from ..risk.sizing import volatility_target_weight
from .broker import PaperBroker
from .feed import LiveFeed
from .state import Store
from .strategy import Strategy


@dataclass
class LoopConfig:
    symbols: tuple[str, ...] = ("BTC-USD",)
    interval: str = "1m"
    starting_equity: float = 100_000.0
    bars_per_year: float = 365 * 24 * 60  # 1m bars; recomputed from `interval`
    target_annual_vol: float = 0.20
    vol_span: int = 168
    # Bounds the per-bar cost: the full 255-feature matrix takes ~0.6s over 1500 bars
    # and ~2.9s over 5000, and the longest feature warm-up is 720 bars, so more history
    # buys nothing but latency. Raise it only if you add a longer-lookback feature.
    max_history_bars: int = 1500
    rebalance_band: float = 0.02
    rebalance_band_relative: float = 0.25
    costs: CostModel = field(default_factory=CostModel)
    risk: RiskLimits = field(default_factory=RiskLimits)
    persist: bool = True
    verbose: bool = True

    def __post_init__(self) -> None:
        seconds = pd.Timedelta(self.interval).total_seconds()
        if seconds > 0:
            self.bars_per_year = 365 * 24 * 3600 / seconds

    def to_meta(self) -> dict:
        return {
            "symbols": list(self.symbols),
            "interval": self.interval,
            "starting_equity": self.starting_equity,
            "target_annual_vol": self.target_annual_vol,
            "bars_per_year": self.bars_per_year,
            "taker_fee_bps": self.costs.taker_fee_bps,
            "max_drawdown": self.risk.max_drawdown,
            "max_daily_loss": self.risk.max_daily_loss,
            "max_gross_leverage": self.risk.max_gross_leverage,
        }


class PaperTradingLoop:
    def __init__(
        self,
        feed: LiveFeed,
        strategy: Strategy,
        config: LoopConfig | None = None,
        *,
        run_id: str | None = None,
        store: Store | None = None,
    ) -> None:
        self.feed = feed
        self.strategy = strategy
        self.config = config or LoopConfig()
        self.run_id = run_id or f"{self.strategy.name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
        self.store = store if store is not None else (Store(CONFIG.state_db) if self.config.persist else None)
        self.broker = PaperBroker(
            self.run_id, self.config.starting_equity, self.config.costs, self.store
        )
        self.risk = RiskEngine(self.config.risk, self.config.starting_equity)
        self.history: dict[str, pd.DataFrame] = {}
        self.last_prices: dict[str, float] = {}
        self.n_bars = 0
        self.errors: list[str] = []
        self._stop = asyncio.Event()

        if self.store is not None:
            self.store.start_run(
                self.run_id,
                {**self.config.to_meta(), "strategy": self.strategy.name},
                note="paper trading — no real orders are placed by this system",
            )

    # -------------------------------------------------------------- backfill
    def seed_history(self, symbol: str, bars: pd.DataFrame) -> None:
        """Preload historical bars so the strategy is warm from the first live bar.

        Without this, a restarted loop spends its entire warm-up window (hundreds of
        bars — days or weeks of wall-clock time) flat and blind, and every restart
        throws that away again. Backfilling from the lake is what a real system does,
        and it costs one feature computation instead of hundreds.

        Seeded bars are history only: no decisions, fills or equity points are recorded
        for them, so they cannot contaminate the run's performance record.
        """
        if bars is None or bars.empty:
            return
        df = bars.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df.index.name = "dt"
        df = df.iloc[-self.config.max_history_bars :]
        self.history[symbol] = df
        if "close" in df.columns and len(df):
            self.last_prices[symbol] = float(df["close"].iloc[-1])

    # ------------------------------------------------------------------- run
    async def run(self, max_bars: int | None = None) -> dict:
        """Consume bars until stopped, the feed ends, or `max_bars` is reached."""
        self._install_signal_handlers()
        try:
            async for bar in self.feed.bars():
                try:
                    self.on_bar(bar)
                except Exception as exc:  # one bad bar must not end the session
                    msg = f"{type(exc).__name__}: {exc}"
                    self.errors.append(msg)
                    if self.config.verbose:
                        print(f"[loop] error on bar: {msg}\n{traceback.format_exc()}")
                self.n_bars += 1
                if max_bars is not None and self.n_bars >= max_bars:
                    break
                if self._stop.is_set():
                    break
        finally:
            if self.store is not None:
                self.store.finish_run(self.run_id, "stopped")
        return self.status()

    def _install_signal_handlers(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            for sig in (os_signal.SIGINT, os_signal.SIGTERM):
                loop.add_signal_handler(sig, self._stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # not available on every platform / already running

    def stop(self) -> None:
        self._stop.set()

    # -------------------------------------------------------------- per bar
    def on_bar(self, bar: dict) -> None:
        symbol = bar["symbol"]
        ts = int(bar["ts"])
        self._append(symbol, bar)
        self.last_prices[symbol] = float(bar["close"])

        if self.store is not None:
            self.store.record_bar(self.run_id, symbol, bar)

        equity = self.broker.mark_to_market(self.last_prices)
        self.risk.mark(equity, pd.Timestamp(ts, unit="ms", tz="UTC"))

        # A tripped breaker flattens the book and stops taking risk. Checked before the
        # strategy runs, so a halted system does no work and cannot be talked out of it.
        halt = self.risk.check_breakers()
        if halt:
            fills = self.broker.flatten(self.last_prices, ts, reason=f"risk halt: {halt}")
            if fills and self.config.verbose:
                print(f"[loop] HALTED ({halt}) — flattened {len(fills)} position(s)")
            self._persist_equity(ts, halted=True)
            return

        raw_signal = self._safe_signal(symbol)
        vol = self._volatility(symbol)
        target_weight = 0.0
        if np.isfinite(raw_signal) and vol is not None and np.isfinite(vol) and vol > 0:
            target_weight = float(
                volatility_target_weight(
                    pd.Series([raw_signal]),
                    pd.Series([vol]),
                    target_annual_vol=self.config.target_annual_vol,
                    bars_per_year=self.config.bars_per_year,
                    max_leverage=self.config.risk.max_gross_leverage,
                ).iloc[0]
            )

        decision = self.risk.apply(
            pd.Series({symbol: target_weight}),
            timestamp=pd.Timestamp(ts, unit="ms", tz="UTC"),
            equity=equity,
        )
        allowed = float(decision.weights.get(symbol, 0.0))

        fills = self.broker.rebalance(
            {symbol: allowed},
            self.last_prices,
            ts=ts,
            bar_notional={symbol: float(bar.get("quote_volume") or 0.0) or None},
            volatility_bps={symbol: self._bar_range_bps(bar)},
            band=self.config.rebalance_band,
            band_relative=self.config.rebalance_band_relative,
            reason=self.strategy.name,
        )

        if self.store is not None:
            self.store.record_decision(
                self.run_id, ts, symbol,
                signal=raw_signal,
                target_weight=target_weight,
                allowed_weight=allowed,
                risk_scale=decision.scale,
                risk_reason="; ".join(decision.reasons),
                equity=equity,
            )
        self._persist_equity(ts, halted=False)

        if self.config.verbose and (fills or self.n_bars % 60 == 0):
            print(
                f"[{pd.Timestamp(ts, unit='ms', tz='UTC'):%Y-%m-%d %H:%M}] {symbol} "
                f"px={bar['close']:.2f} signal={raw_signal:+.3f} target={target_weight:+.3f} "
                f"allowed={allowed:+.3f} equity={self.broker.state.equity:,.0f} "
                f"fills={len(fills)}"
            )

    # --------------------------------------------------------------- helpers
    def _append(self, symbol: str, bar: dict) -> None:
        row = {k: v for k, v in bar.items() if k != "symbol"}
        df = self.history.get(symbol)
        new = pd.DataFrame([row])
        new.index = pd.to_datetime(new["ts"], unit="ms", utc=True)
        new.index.name = "dt"
        if df is None:
            df = new
        else:
            if new.index[0] in df.index:
                df.loc[new.index[0]] = new.iloc[0]
            else:
                df = pd.concat([df, new])
        if len(df) > self.config.max_history_bars:
            df = df.iloc[-self.config.max_history_bars :]
        self.history[symbol] = df

    def _safe_signal(self, symbol: str) -> float:
        bars = self.history.get(symbol)
        if bars is None or bars.empty:
            return 0.0
        try:
            value = self.strategy.signal(bars, symbol)
        except Exception as exc:
            msg = f"strategy raised: {type(exc).__name__}: {exc}"
            self.errors.append(msg)
            if self.config.verbose:
                print(f"[loop] {msg}")
            return 0.0  # a broken strategy takes no new risk
        if value is None or not np.isfinite(value):
            return 0.0
        return float(np.clip(value, -1.0, 1.0))

    def _volatility(self, symbol: str) -> float | None:
        bars = self.history.get(symbol)
        if bars is None or len(bars) < 30:
            return None
        r = np.log(bars["close"].astype("float64")).diff()
        vol = r.ewm(span=self.config.vol_span, min_periods=20).std()
        value = vol.iloc[-1]
        return float(value) if np.isfinite(value) else None

    @staticmethod
    def _bar_range_bps(bar: dict) -> float:
        try:
            close = float(bar["close"])
            if close <= 0:
                return 100.0
            return max((float(bar["high"]) - float(bar["low"])) / close * 1e4, 1.0)
        except (KeyError, TypeError, ValueError):
            return 100.0

    def _persist_equity(self, ts: int, halted: bool) -> None:
        if self.store is None:
            return
        equity = self.broker.state.equity
        self.store.record_equity(
            self.run_id, ts, equity, self.broker.state.cash,
            self.broker.gross_exposure(self.last_prices),
            self.risk.state.drawdown, halted,
        )

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        return {
            "run_id": self.run_id,
            "strategy": self.strategy.name,
            "bars_processed": self.n_bars,
            "broker": self.broker.snapshot(self.last_prices),
            "risk": self.risk.status(),
            "diagnostics": self.strategy.diagnostics(),
            "errors": self.errors[-10:],
            "n_errors": len(self.errors),
            "paper_only": True,
        }
