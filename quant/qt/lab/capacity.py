"""Capacity: at what account size does the edge disappear into market impact?

Fees and spread scale linearly with size and leave the per-trade edge unchanged; impact
grows with the square root of participation and eventually eats everything. For each
size the strategy's average trade is charged

    impact_bps = coeff × daily_vol_bps × sqrt(order_notional / average_daily_volume)

per side (the square-root law, coefficient ≈ 1). "Capacity" is reported as the size at
which the net edge per trade halves and the size at which it reaches zero — both
approximate. "Scalable to infinity" is not an engineering assumption.

FX spot has no consolidated volume; its capacity is not measurable from this data and
is reported as such rather than invented.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def capacity_table(trades: pd.DataFrame, bars: dict[str, pd.DataFrame], sizes: list[float],
                   *, n_symbols: int, impact_coeff: float = 1.0, lookback_days: int = 756) -> dict:
    if trades is None or not len(trades) or "symbol" not in trades:
        return {"measurable": False, "reason": "aucun trade"}
    adv, vol_bps = {}, {}
    for s, b in bars.items():
        tail = b.iloc[-lookback_days:]
        dollar = (tail["volume"] * tail["raw_close"]).replace(0.0, np.nan)
        if dollar.notna().mean() < 0.5:
            continue
        adv[s] = float(dollar.median())
        vol_bps[s] = float(np.log(tail["close"]).diff().std() * 1e4)
    if not adv:
        return {"measurable": False, "reason": "pas de volume consolidé (marché OTC) : capacité non mesurable avec ces données"}
    t = trades[trades["symbol"].isin(adv)]
    if not len(t):
        return {"measurable": False, "reason": "aucun trade sur un instrument avec volume"}
    # Edge per trade in bps of the position's notional, before impact.
    edge_bps = float((t["net"] / t["size"]).mean() * 1e4)
    avg_size = float(t["size"].mean())
    rows = []
    for cap in sizes:
        imp = []
        for s in t["symbol"].unique():
            notional = cap * avg_size / n_symbols
            part = min(notional / adv[s], 1.0)
            imp.append(impact_coeff * vol_bps[s] * np.sqrt(part))
        impact = 2 * float(np.mean(imp))  # entry and exit
        rows.append({"capital": cap, "impact_bps_round_trip": impact, "net_edge_bps": edge_bps - impact,
                     "participation_max": max(cap * avg_size / n_symbols / v for v in adv.values())})
    table = pd.DataFrame(rows)
    half = table.loc[table["net_edge_bps"] <= edge_bps / 2, "capital"]
    zero = table.loc[table["net_edge_bps"] <= 0, "capital"]
    return {
        "measurable": True,
        "edge_bps_per_trade": edge_bps,
        "capacity_half_edge": float(half.iloc[0]) if len(half) and edge_bps > 0 else None,
        "capacity_zero_edge": float(zero.iloc[0]) if len(zero) and edge_bps > 0 else None,
        "table": table,
    }
