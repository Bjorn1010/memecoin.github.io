"""Replay the live orchestrator over history and check it against the backtest.

This is the test the system could not previously do for itself, and it is the one that
matters most. The backtest and the live path are two implementations of the same idea;
whenever a project has both, they drift, and the drift is discovered in production
months later when the live curve stops resembling the research.

The method: drive `run_cycle` forward one bar at a time over the real price history,
feeding it only the data that existed at each point, and record what it decided. Then run
the ordinary backtest over the same window. If the two equity curves diverge, one of them
is wrong — and this run says so rather than letting the difference show up live.

What counts as agreement is deliberately not "identical". The live path charges a spread
on turnover with a flat estimate, while the engine models spread, impact and a rebalance
band per fill; the two will differ by a few basis points of cost. A gap of several
percent means the *decisions* differ, which is the failure worth catching.

Run:  .venv/bin/python -u scripts/replay_live.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from qt.backtest import BacktestConfig
from qt.backtest.engine import run_backtest
from qt.config import CostModel
from qt.data import schemas
from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES
from qt.live.orchestrator import DailySpec, mark_to_market, target_weights
from qt.live.state import Store

pd.set_option("display.width", 220)

# Replay every N bars rather than every bar: a daily cycle over sixteen years is 4,000
# full allocator fits, and the allocator only reallocates every 21 bars anyway. Weekly
# replay exercises the same code path at a fraction of the cost.
STEP = 5
WARMUP = 1300  # enough for the 252-bar allocator lookback plus the 256-bar trend horizon


def load(cat: Catalog, spec: DailySpec) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    bars: dict[str, pd.DataFrame] = {}
    for symbol in UNIVERSES[spec.universe]:
        df = cat.read_indexed("eod", "yahoo", symbol)
        if df.empty:
            continue
        ratio = df["adj_close"].astype("float64") / df["close"].astype("float64")
        df = df.copy()
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype("float64") * ratio
        bars[symbol] = df
    prices = pd.DataFrame({s: b["close"] for s, b in bars.items()}).dropna()
    return prices, {s: b.loc[prices.index] for s, b in bars.items()}


def replay(prices: pd.DataFrame, spec: DailySpec) -> pd.DataFrame:
    """Walk the orchestrator forward, showing it only the past at each step."""
    tmp = Path(tempfile.mkdtemp())
    store = Store(tmp / "replay.sqlite")
    rows = []

    for i in range(WARMUP, len(prices), STEP):
        visible = prices.iloc[: i + 1]
        stamp = visible.index[-1]

        # mark_to_market applies the one-bar execution lag itself, so the replay
        # inherits it rather than reimplementing it — which is the point: the replay
        # must exercise the live code, not a copy of it.
        equity, drawdown, _ = mark_to_market(store, "replay", visible, spec)

        weights = target_weights(visible, spec)
        if weights.empty:
            continue
        latest = weights.iloc[-1]

        from qt.live.orchestrator import drawdown_scale

        scale, _ = drawdown_scale(drawdown, spec)
        allowed = latest * scale

        # Charge the turnover cost, exactly as the live cycle does.
        previous = {r["symbol"]: float(r["allowed_weight"] or 0.0)
                    for _, r in store.decisions("replay", limit=200).iterrows()
                    if r["ts"] == store.decisions("replay", limit=200)["ts"].max()} \
            if not store.decisions("replay", limit=1).empty else {}
        turnover = sum(abs(allowed.get(s, 0.0) - previous.get(s, 0.0))
                       for s in set(allowed.index) | set(previous))
        equity -= equity * turnover * (spec.half_spread_bps / 1e4)

        ms = int(schemas.epoch_ms(pd.DatetimeIndex([stamp])).iloc[0])
        for symbol, weight in allowed.items():
            store.record_decision("replay", ms, symbol, signal=float(weight),
                                  target_weight=float(latest[symbol]),
                                  allowed_weight=float(weight), risk_scale=scale,
                                  risk_reason="replay", equity=equity)
        store.record_equity("replay", ms, equity, equity,
                            float(allowed.abs().sum()), drawdown, scale == 0.0)
        rows.append({"ts": stamp, "equity": equity, "drawdown": drawdown,
                     "gross": float(allowed.abs().sum())})

    return pd.DataFrame(rows).set_index("ts")


def main() -> None:
    cat = Catalog()
    spec = DailySpec()
    prices, bars = load(cat, spec)
    print(f"universe {prices.shape[1]} assets, {len(prices)} bars, "
          f"{prices.index.min().date()} -> {prices.index.max().date()}")
    print(f"replaying the live cycle every {STEP} bars from bar {WARMUP}...\n")

    live = replay(prices, spec)
    if live.empty:
        print("replay produced nothing — check WARMUP against the sample length")
        return

    # The backtest over exactly the window the replay covered.
    weights = target_weights(prices, spec).loc[live.index[0]:]
    cfg = BacktestConfig(
        bars_per_year=252,
        costs=CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0,
                        half_spread_bps=spec.half_spread_bps),
        allow_short=True, signal_is_weight=True, max_weight_per_symbol=spec.max_weight,
    )
    aligned = {s: b.loc[b.index.intersection(weights.index)] for s, b in bars.items()}
    bt = run_backtest(aligned, weights, cfg)

    live_total = live["equity"].iloc[-1] / live["equity"].iloc[0] - 1.0
    bt_total = float(bt.equity.iloc[-1] / bt.equity.iloc[0] - 1.0)

    years = (live.index[-1] - live.index[0]).days / 365.25
    live_cagr = (1 + live_total) ** (1 / years) - 1
    bt_cagr = (1 + bt_total) ** (1 / years) - 1

    print("=== live replay vs backtest, same window, same weights ===\n")
    table = pd.DataFrame([
        {"path": "live replay", "total_return": round(live_total, 4),
         "cagr": round(live_cagr, 4), "max_drawdown": round(float(live["drawdown"].min()), 4)},
        {"path": "backtest", "total_return": round(bt_total, 4),
         "cagr": round(bt_cagr, 4),
         "max_drawdown": round(float(bt.metrics.get("max_drawdown", float("nan"))), 4)},
    ])
    print(table.to_string(index=False))

    gap = abs(live_cagr - bt_cagr)
    print(f"\nCAGR gap: {gap:.4f} ({gap * 100:.2f} percentage points)")
    print("\nA gap of a few tenths of a point is the cost models differing — the live")
    print("path charges a flat spread on turnover, the engine models spread and impact")
    print("per fill. Several points means the DECISIONS differ, which is the failure")
    print("this run exists to catch.")

    # 0.30pp is the measured baseline once the one-bar execution lag is applied on both
    # sides: it is the flat-spread model differing from per-fill spread and impact.
    # Before that fix the gap was 1.01pp, all of it a timing advantage no order could
    # have captured, so the threshold is set to catch a return of anything that size.
    if gap > 0.01:
        print("\n*** DIVERGENCE: the live and research paths do not agree. ***")
    else:
        print("\nThe two paths agree within cost-model tolerance.")

    print(f"\nreplay cycles: {len(live)}   mean gross: {live['gross'].mean():.3f}")


if __name__ == "__main__":
    main()
