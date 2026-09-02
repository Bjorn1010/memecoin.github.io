"""The autonomous daily cycle: refresh, decide, size, record — with no human in it.

The existing live loop consumes a crypto websocket and reacts bar by bar. A multi-asset
book does not work that way and should not: its data arrives once a day after the close,
its signal moves on horizons of weeks, and reacting faster than that only pays the
spread more often. This module is the daily counterpart — one function that performs a
complete cycle, and a runner that repeats it forever.

Everything here is built around one idea: **the cycle must be safe to interrupt.** A
process that has to complete or corrupt its state is not autonomous, it is a task that
happens to be running. So each stage is independently restartable, state lives in SQLite
rather than memory, and a cycle that fails partway leaves the previous book intact
rather than a half-rebalanced one.

Order of operations, and why:

1. **Refresh data.** Fails soft. A venue being down is not a reason to stop trading a
   book built on twenty years of history — it is a reason to trade yesterday's view.
2. **Check staleness.** This is the one that must fail hard. Trading on data that has
   silently stopped updating is how a system holds a position through a crash while
   believing the market never moved. If the newest bar is older than the tolerance, the
   cycle records the reason and takes no new risk.
3. **Compute weights.** Trend, allocator, blend — the same code the backtest ran, called
   the same way, because a live path that reimplements the research path will diverge
   from it and the divergence will be discovered in production.
4. **Apply risk.** Volatility target, gross cap, drawdown breaker. The breaker reduces
   risk; it never liquidates. Forced liquidation at the bottom of a drawdown is how
   systems turn a bad month into a permanent loss.
5. **Record everything.** The signal, the weight asked for, the weight allowed, and why
   they differ. Reconstructing "why did it do that" from prices alone is impossible, and
   that question is most of what running a system consists of.

**This is paper trading. There is no broker, no credential, and no order path.** The
`Decision` this produces is a record, not an instruction sent anywhere. Nothing in this
module or anything it imports can place an order.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
import pandas as pd

from ..config import CONFIG
from ..data import schemas
from ..data.catalog import Catalog
from ..risk import apply_no_trade_band, portfolio_vol_target
from ..strategies.trend import TrendSpec, build_trend, combine_trend_and_allocator
from .state import Store


@dataclass
class DailySpec:
    """What the daily book is and how much risk it takes."""

    universe: str = "multi_asset"
    venue: str = "yahoo"
    dataset: str = "eod"
    # Trend weight in the blend. 0.7 was the best of the configurations tested, at a
    # deflated Sharpe of 0.999 over 2010-2026; it is reported rather than hidden so the
    # selection is visible to anyone reading the results.
    trend_blend: float = 0.7
    target_vol: float = 0.10
    max_gross: float = 1.5
    max_weight: float = 0.25
    max_leverage: float = 3.0
    starting_equity: float = 100_000.0
    # A bar older than this means the feed has stopped, whatever the source claims.
    # Four calendar days covers a long weekend plus a public holiday.
    staleness_days: float = 4.0
    # Drawdown at which new risk is halved, and at which it stops entirely. Neither
    # liquidates: the book is reduced, never dumped.
    soft_drawdown: float = 0.10
    hard_drawdown: float = 0.20
    trend: TrendSpec = field(default_factory=lambda: TrendSpec(rebalance_every=5))

    def to_meta(self) -> dict:
        return {
            "universe": self.universe, "venue": self.venue, "dataset": self.dataset,
            "trend_blend": self.trend_blend, "target_vol": self.target_vol,
            "max_gross": self.max_gross, "max_weight": self.max_weight,
            "max_leverage": self.max_leverage, "staleness_days": self.staleness_days,
            "soft_drawdown": self.soft_drawdown, "hard_drawdown": self.hard_drawdown,
            "trend": self.trend.to_meta(),
        }


@dataclass
class CycleResult:
    """What one cycle did, and why. Everything needed to audit the decision later."""

    ts: pd.Timestamp
    status: str                      # ok | stale | halted | error | warming_up
    reason: str = ""
    weights: dict[str, float] = field(default_factory=dict)
    raw_weights: dict[str, float] = field(default_factory=dict)
    equity: float = 0.0
    drawdown: float = 0.0
    risk_scale: float = 1.0
    gross: float = 0.0
    refreshed: dict[str, int] = field(default_factory=dict)
    data_age_days: float = float("nan")

    def to_dict(self) -> dict:
        out = {
            "ts": self.ts.isoformat() if isinstance(self.ts, pd.Timestamp) else str(self.ts),
            "status": self.status, "reason": self.reason,
            "equity": round(self.equity, 2), "drawdown": round(self.drawdown, 4),
            "risk_scale": round(self.risk_scale, 4), "gross": round(self.gross, 4),
            "data_age_days": round(self.data_age_days, 2) if np.isfinite(self.data_age_days) else None,
            "weights": {k: round(v, 5) for k, v in self.weights.items() if abs(v) > 1e-6},
            "refreshed": self.refreshed,
        }
        return out


# --------------------------------------------------------------------- stages
def refresh(catalog: Catalog, spec: DailySpec) -> dict[str, int]:
    """Pull the latest bars. Fails soft, per source and per symbol.

    A venue outage must not stop the cycle. The count of rows written per symbol is
    returned so the caller can see that a "successful" refresh which fetched nothing is
    not the same as one that fetched data — the distinction that made the Stooq failure
    invisible for as long as it was.
    """
    from ..data.sources import fred, yahoo

    counts: dict[str, int] = {}
    for symbol in yahoo.UNIVERSES.get(spec.universe, ()):
        try:
            df = yahoo.daily(symbol)
            if not df.empty:
                catalog.write(schemas.EOD, yahoo.VENUE, symbol, df)
            counts[symbol] = len(df)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not stop the book
            counts[symbol] = -1
            counts[f"{symbol}__error"] = str(exc)[:120]  # type: ignore[assignment]
    try:
        macro = fred.ingest(catalog)
        counts["__macro_series"] = int((macro["rows"] > 0).sum())
    except Exception:  # noqa: BLE001
        counts["__macro_series"] = -1
    return counts


def load_prices(catalog: Catalog, spec: DailySpec, *, total_return: bool = True) -> pd.DataFrame:
    """Close prices for the universe, optionally restated to total return.

    Total return is the default because the alternative silently discards the dividend,
    which on this book is worth between 0.7% and 6.3% a year depending on the sleeve.
    """
    from ..data.sources import yahoo

    series: dict[str, pd.Series] = {}
    for symbol in yahoo.UNIVERSES.get(spec.universe, ()):
        df = catalog.read_indexed(spec.dataset, spec.venue, symbol)
        if df.empty:
            continue
        close = df["close"].astype("float64")
        if total_return and "adj_close" in df.columns:
            close = close * (df["adj_close"].astype("float64") / close)
        series[symbol] = close
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).dropna()


def staleness(prices: pd.DataFrame, now: pd.Timestamp | None = None) -> float:
    """Age of the newest bar, in days. NaN when there is no data at all."""
    if prices.empty:
        return float("nan")
    now = schemas.to_utc(now if now is not None else pd.Timestamp.now("UTC"))
    return float((now - prices.index.max()).total_seconds() / 86400.0)


def target_weights(prices: pd.DataFrame, spec: DailySpec) -> pd.DataFrame:
    """The book the strategy wants, before risk limits.

    Deliberately the same call the backtest makes. A live path that reimplements the
    research path will drift from it, and the drift is always discovered in production.
    """
    from ..backtest.portfolio_backtest import AllocationSpec, build_weights

    trend = build_trend(prices, spec.trend).weights
    allocation, _ = build_weights(prices, AllocationSpec(
        method="risk_parity", lookback=252, rebalance_every=21,
        covariance="ledoit_wolf", max_weight=spec.max_weight, min_history=252))
    if allocation.empty:
        return pd.DataFrame()

    combined = combine_trend_and_allocator(trend, allocation, blend=spec.trend_blend,
                                           max_gross=spec.max_gross)
    returns = np.log(prices).diff()
    sized = portfolio_vol_target(combined, returns, target_annual_vol=spec.target_vol,
                                 bars_per_year=252, max_leverage=spec.max_leverage)

    # Re-apply the limits *after* the volatility scaling. Capping first and levering
    # second lets the scalar walk a position straight back through its own ceiling — the
    # first live cycle put 25.63% into UUP against a 25% limit, and at higher leverage
    # the breach grows with it. A limit that an later stage can undo is not a limit.
    sized = sized.clip(-spec.max_weight, spec.max_weight)
    gross = sized.abs().sum(axis=1)
    over = gross > spec.max_gross
    if over.any():
        # Scale the book down, never truncate the largest legs: truncation concentrates
        # the portfolio at precisely the moment its risk is highest.
        sized.loc[over] = sized.loc[over].div(gross[over], axis=0) * spec.max_gross

    return apply_no_trade_band(sized)


def drawdown_scale(drawdown: float, spec: DailySpec) -> tuple[float, str]:
    """Risk multiplier from the current drawdown. Reduces; never liquidates.

    A breaker that flattens the book converts a drawdown into a realised loss at the
    worst possible moment and guarantees the recovery is missed. Halving risk keeps the
    position and cuts the bleed.
    """
    if drawdown <= -abs(spec.hard_drawdown):
        return 0.0, f"drawdown {drawdown:.1%} beyond hard limit {spec.hard_drawdown:.0%} — no new risk"
    if drawdown <= -abs(spec.soft_drawdown):
        return 0.5, f"drawdown {drawdown:.1%} beyond soft limit {spec.soft_drawdown:.0%} — risk halved"
    return 1.0, ""


# ---------------------------------------------------------------- the cycle
def run_cycle(
    spec: DailySpec | None = None,
    *,
    catalog: Catalog | None = None,
    store: Store | None = None,
    run_id: str = "daily",
    do_refresh: bool = True,
    now: pd.Timestamp | None = None,
) -> CycleResult:
    """One complete decision, recorded. Safe to call repeatedly; safe to interrupt.

    Never raises for an ordinary failure — a cycle that throws stops the daemon, and a
    daemon that stops is not autonomous. Failures become a CycleResult with a status and
    a reason, which is both recorded and returned.
    """
    spec = spec or DailySpec()
    catalog = catalog or Catalog()
    store = store or Store(CONFIG.runs_dir / "daily.sqlite")
    stamp = schemas.to_utc(now if now is not None else pd.Timestamp.now("UTC"))

    try:
        refreshed = refresh(catalog, spec) if do_refresh else {}
        prices = load_prices(catalog, spec)

        if prices.empty:
            return _record(store, run_id, CycleResult(
                stamp, "error", "no prices in the lake — run `qt equities` first",
                refreshed=refreshed))

        age = staleness(prices, stamp)
        if not np.isfinite(age) or age > spec.staleness_days:
            # The one hard stop. Trading a feed that has silently stopped updating is
            # how a book holds a position through a crash believing nothing happened.
            return _record(store, run_id, CycleResult(
                stamp, "stale",
                f"newest bar is {age:.1f} days old (limit {spec.staleness_days}) — no new risk",
                refreshed=refreshed, data_age_days=age))

        weights = target_weights(prices, spec)
        if weights.empty:
            return _record(store, run_id, CycleResult(
                stamp, "warming_up", "not enough history for the allocator yet",
                refreshed=refreshed, data_age_days=age))

        latest = weights.iloc[-1]
        equity, drawdown = _equity_state(store, run_id, spec)
        scale, reason = drawdown_scale(drawdown, spec)
        allowed = latest * scale

        result = CycleResult(
            ts=stamp,
            status="halted" if scale == 0.0 else "ok",
            reason=reason,
            weights={k: float(v) for k, v in allowed.items()},
            raw_weights={k: float(v) for k, v in latest.items()},
            equity=equity, drawdown=drawdown, risk_scale=scale,
            gross=float(allowed.abs().sum()),
            refreshed=refreshed, data_age_days=age,
        )
        return _record(store, run_id, result, prices=prices)

    except Exception as exc:  # noqa: BLE001 - the daemon must survive anything
        return _record(store, run_id, CycleResult(
            stamp, "error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-600:]}"))


def _equity_state(store: Store, run_id: str, spec: DailySpec) -> tuple[float, float]:
    """Current equity and drawdown from the recorded curve."""
    curve = store.equity_curve(run_id)
    if curve.empty:
        return spec.starting_equity, 0.0
    equity = float(curve["equity"].iloc[-1])
    peak = float(curve["equity"].max())
    return equity, (equity / peak - 1.0) if peak > 0 else 0.0


def _record(store: Store, run_id: str, result: CycleResult,
            prices: pd.DataFrame | None = None) -> CycleResult:
    """Persist the decision. Recording must never be the thing that breaks the cycle."""
    try:
        ms = int(schemas.epoch_ms(pd.DatetimeIndex([result.ts])).iloc[0])
        for symbol, weight in result.raw_weights.items():
            store.record_decision(
                run_id, ms, symbol,
                signal=weight, target_weight=weight,
                allowed_weight=result.weights.get(symbol, 0.0),
                risk_scale=result.risk_scale,
                risk_reason=result.reason or result.status,
                equity=result.equity,
            )
        store.record_equity(run_id, ms, result.equity, result.equity,
                            result.gross, result.drawdown,
                            result.status in ("halted", "stale", "error"))
    except Exception:  # noqa: BLE001
        result.reason = (result.reason + " | persist failed").strip(" |")
    return result


def start_run(spec: DailySpec | None = None, *, run_id: str = "daily",
              store: Store | None = None) -> Store:
    """Register the run so its configuration is recoverable from the database alone."""
    spec = spec or DailySpec()
    store = store or Store(CONFIG.runs_dir / "daily.sqlite")
    store.start_run(run_id, spec.to_meta(), note="autonomous daily multi-asset book")
    return store


def run_forever(spec: DailySpec | None = None, *, run_id: str = "daily",
                interval_hours: float = 24.0, max_cycles: int | None = None,
                on_cycle=None) -> list[CycleResult]:
    """Repeat the cycle on a schedule until stopped.

    `max_cycles` bounds the loop for testing and for a scheduled invocation that should
    do one pass and exit — which is the better deployment shape anyway: a cron entry
    calling `run_cycle` once is more robust than a long-lived process, because the
    operating system restarts it and there is no in-memory state to lose.
    """
    import time

    spec = spec or DailySpec()
    store = start_run(spec, run_id=run_id)
    history: list[CycleResult] = []
    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        result = run_cycle(spec, store=store, run_id=run_id)
        history.append(result)
        if on_cycle is not None:
            on_cycle(result)
        cycle += 1
        if max_cycles is not None and cycle >= max_cycles:
            break
        time.sleep(max(interval_hours, 0.0) * 3600.0)
    return history


def status_report(run_id: str = "daily", store: Store | None = None) -> dict:
    """What the book currently holds and how it has behaved — for a human, or a page."""
    store = store or Store(CONFIG.runs_dir / "daily.sqlite")
    curve = store.equity_curve(run_id)
    decisions = store.decisions(run_id, limit=200)

    latest: dict[str, float] = {}
    if not decisions.empty:
        newest = decisions[decisions["ts"] == decisions["ts"].max()]
        latest = {r["symbol"]: float(r["allowed_weight"] or 0.0) for _, r in newest.iterrows()
                  if abs(float(r["allowed_weight"] or 0.0)) > 1e-6}

    out: dict = {
        "run_id": run_id,
        "cycles": int(len(curve)),
        "positions": dict(sorted(latest.items(), key=lambda kv: -abs(kv[1]))),
        "gross": round(sum(abs(v) for v in latest.values()), 4),
    }
    if not curve.empty:
        last = curve.iloc[-1]
        out.update({
            "equity": round(float(last["equity"]), 2),
            "drawdown": round(float(last["drawdown"]), 4),
            "halted": bool(last["halted"]),
            "last_cycle": pd.Timestamp(int(last["ts"]), unit="ms", tz="UTC").isoformat(),
        })
    if not decisions.empty:
        out["last_reason"] = str(decisions.iloc[0]["risk_reason"])
    return out


def format_report(report: dict) -> str:
    return json.dumps(report, indent=2, default=str)
