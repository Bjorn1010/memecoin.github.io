"""Imbalance and run bars — sampling when order flow becomes one-sided.

Standard activity bars (tick/volume/dollar) sample when *a lot* happens. Imbalance
bars sample when what happens is *directional*: they close as soon as the cumulative
signed flow exceeds what the recent past says is normal. That makes them fire right
at the moments an informed participant is working an order, which is exactly where a
short-horizon edge lives — and it is why they tend to front-run the breakout that a
time bar only reveals afterwards.

Both thresholds are adaptive (EWMA of the recent bar length and of the recent
imbalance), so the bar count stays stable when the regime changes instead of
collapsing to one bar a week in quiet markets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .build import _aggregate


def tick_signs(price: np.ndarray, aggressor_buy: np.ndarray | None = None) -> np.ndarray:
    """Signed trade direction, +1 buy-initiated / -1 sell-initiated.

    Uses the venue's aggressor flag when available (exact). Falls back to the tick
    rule — sign of the price change, carrying the previous sign through zero-change
    ticks — which is the standard estimator when only prices are published.
    """
    if aggressor_buy is not None:
        return np.where(aggressor_buy, 1.0, -1.0)
    diff = np.diff(price, prepend=price[0])
    signs = np.sign(diff)
    # Carry the last non-zero sign forward across flat ticks.
    idx = np.where(signs != 0, np.arange(signs.size), 0)
    np.maximum.accumulate(idx, out=idx)
    signs = signs[idx]
    signs[signs == 0] = 1.0
    return signs


def _ewma(prev: float, value: float, alpha: float) -> float:
    return value if not np.isfinite(prev) else alpha * value + (1 - alpha) * prev


def build_imbalance_bars(
    trades: pd.DataFrame,
    kind: str = "dollar",
    warmup_ticks: int = 1_000,
    ewma_span: int = 50,
    max_bar_ticks: int | None = None,
) -> pd.DataFrame:
    """Imbalance bars over ticks ('tick'), volume ('volume') or notional ('dollar').

    A bar closes when |cumulative signed flow| >= E[bar length] * |E[signed flow per
    unit]|, with both expectations tracked by EWMA over completed bars.
    """
    if trades is None or trades.empty:
        return _aggregate(np.array([]), np.array([]), np.array([]), np.array([]), np.array([], dtype="int64"))

    df = trades.sort_values("ts", kind="mergesort")
    ts = df["ts"].to_numpy(dtype="int64")
    price = df["price"].to_numpy(dtype="float64")
    qty = df["qty"].to_numpy(dtype="float64")
    buy = ~df["is_buyer_maker"].to_numpy(dtype="bool")
    signs = tick_signs(price, buy)

    if kind == "tick":
        weight = np.ones_like(qty)
    elif kind == "volume":
        weight = qty
    elif kind == "dollar":
        weight = price * qty
    else:
        raise ValueError(f"unknown imbalance bar kind {kind!r}")

    signed = signs * weight
    alpha = 2.0 / (ewma_span + 1.0)

    # Warm up expectations on the first `warmup_ticks` prints so the first bars are
    # not produced from an uninformed threshold.
    n_warm = min(warmup_ticks, signed.size)
    exp_ticks = float(n_warm) if n_warm else 1.0
    exp_imb = float(np.abs(signed[:n_warm]).mean()) if n_warm else 1.0

    edges: list[int] = []
    running = 0.0
    count = 0
    for i in range(signed.size):
        running += signed[i]
        count += 1
        threshold = exp_ticks * abs(exp_imb)
        hit_cap = max_bar_ticks is not None and count >= max_bar_ticks
        if (threshold > 0 and abs(running) >= threshold) or hit_cap:
            edges.append(i + 1)
            exp_ticks = _ewma(exp_ticks, float(count), alpha)
            exp_imb = _ewma(exp_imb, abs(running) / max(count, 1), alpha)
            running = 0.0
            count = 0

    out = _aggregate(ts, price, qty, buy, np.asarray(edges, dtype="int64"))
    if not out.empty:
        # Signed flow of the bar itself is a first-class feature, not a by-product.
        out["imbalance"] = out["buy_volume"] - out["sell_volume"]
    return out


def build_run_bars(
    trades: pd.DataFrame,
    warmup_ticks: int = 1_000,
    ewma_span: int = 50,
    max_bar_ticks: int | None = 50_000,
) -> pd.DataFrame:
    """Run bars: close when a one-directional *sequence* of flow exceeds expectation.

    Where imbalance bars look at the net, run bars look at the longest one-sided run,
    which is more sensitive to a single participant sweeping the book repeatedly.
    """
    if trades is None or trades.empty:
        return _aggregate(np.array([]), np.array([]), np.array([]), np.array([]), np.array([], dtype="int64"))

    df = trades.sort_values("ts", kind="mergesort")
    ts = df["ts"].to_numpy(dtype="int64")
    price = df["price"].to_numpy(dtype="float64")
    qty = df["qty"].to_numpy(dtype="float64")
    buy = ~df["is_buyer_maker"].to_numpy(dtype="bool")
    signs = tick_signs(price, buy)
    notional = price * qty

    alpha = 2.0 / (ewma_span + 1.0)
    n_warm = min(warmup_ticks, signs.size)
    exp_ticks = float(n_warm) if n_warm else 1.0
    exp_run = float(np.abs(notional[:n_warm]).sum()) / 2.0 if n_warm else 1.0

    edges: list[int] = []
    buy_run = 0.0
    sell_run = 0.0
    count = 0
    for i in range(signs.size):
        if signs[i] > 0:
            buy_run += notional[i]
        else:
            sell_run += notional[i]
        count += 1
        threshold = exp_ticks * max(exp_run, 1e-12) / max(exp_ticks, 1.0)
        hit_cap = max_bar_ticks is not None and count >= max_bar_ticks
        if max(buy_run, sell_run) >= threshold or hit_cap:
            edges.append(i + 1)
            exp_ticks = _ewma(exp_ticks, float(count), alpha)
            exp_run = _ewma(exp_run, max(buy_run, sell_run), alpha)
            buy_run = sell_run = 0.0
            count = 0

    return _aggregate(ts, price, qty, buy, np.asarray(edges, dtype="int64"))
