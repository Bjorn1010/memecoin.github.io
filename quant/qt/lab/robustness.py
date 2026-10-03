"""Robustness engine: try to break the strategy before the market does.

Each perturbation re-runs the strategy on the research window with one thing made
worse or slightly different. A real edge degrades gracefully; a fitted one falls off a
cliff, because it was a property of the exact parameters rather than of the market.

Perturbations (from configs/research_protocol.yaml):
* every numeric parameter moved ±5 %, ±10 %, ±20 % (one at a time; integers rounded,
  and a move that rounds back to the original value is skipped, not counted as a pass);
* costs × 1.25 and × 1.5, extra slippage;
* entry delayed one bar, exit delayed one bar;
* signal noise: a share of the target series randomly zeroed;
* removal of the best 5 % / 10 % of trades (is the result a few lucky trades?).

A strategy whose optimum is a sharp peak — great at one value, poor at its neighbours —
is treated as suspect, whatever its Sharpe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .metrics import sharpe


@dataclass
class Perturbation:
    name: str
    kind: str
    sharpe: float
    passed: bool


def perturb_params(params: dict, frac: float) -> list[tuple[str, dict]]:
    out = []
    for key, val in params.items():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        for sign in (+1, -1):
            new = val * (1 + sign * frac)
            if isinstance(val, int):
                new = int(round(new))
                if new == val:
                    new = val + sign  # the smallest real move for an integer parameter
                if new < 1:
                    continue
            cfg = {**params, key: new}
            out.append((f"{key} {'+' if sign > 0 else '−'}{int(frac * 100)} %", cfg))
    return out


def run_robustness(
    params: dict,
    run: Callable[..., tuple[pd.Series, pd.DataFrame]],
    window: tuple[pd.Timestamp, pd.Timestamp],
    ppy: int,
    protocol: dict,
    *,
    seed: int = 0,
) -> dict:
    """`run(params, cost_mult=1, extra_slip=0, entry_delay=0, exit_delay=0, noise=0, seed=0)`
    returns (full-history returns, trades with 'net' and 'exit_ts')."""
    lo, hi = window

    def window_sharpe(r: pd.Series) -> float:
        return sharpe(r.loc[lo:hi], ppy)

    base_r, base_trades = run(params)
    base = window_sharpe(base_r)
    results: list[Perturbation] = []

    def judge(name: str, kind: str, r: pd.Series) -> None:
        s = window_sharpe(r)
        # Passing means: still positive, and keeps at least half the baseline Sharpe.
        ok = bool(np.isfinite(s) and s > 0 and (not np.isfinite(base) or base <= 0 or s >= 0.5 * base))
        results.append(Perturbation(name, kind, s, ok))

    for frac in protocol["param_perturbations"]:
        for label, cfg in perturb_params(params, frac):
            judge(label, "paramètre", run(cfg)[0])
    for mult in protocol["cost_multipliers"]:
        judge(f"coûts × {mult}", "coûts", run(params, cost_mult=mult)[0])
    judge(f"slippage + {protocol['extra_slippage_bps']} bp", "coûts",
          run(params, extra_slip=protocol["extra_slippage_bps"])[0])
    judge("entrée retardée d'1 barre", "exécution", run(params, entry_delay=protocol["entry_delay_bars"])[0])
    judge("sortie retardée d'1 barre", "exécution", run(params, exit_delay=protocol["exit_delay_bars"])[0])
    judge(f"signal bruité ({protocol['signal_noise_rate']:.0%})", "signal",
          run(params, noise=protocol["signal_noise_rate"], seed=seed)[0])

    # Trade removal works on the trade list: drop the best trades and rebuild the stream.
    t = base_trades
    if t is not None and len(t) and "exit_ts" in t:
        tw = t[(t["exit_ts"] >= lo) & (t["exit_ts"] <= hi)]
        for share in protocol["trade_removal_top"]:
            k = int(np.ceil(share * len(tw)))
            if k == 0:
                continue
            top = tw.nlargest(k, "net")
            adj = base_r.copy()
            for _, row in top.iterrows():
                if row["exit_ts"] in adj.index:
                    adj.loc[row["exit_ts"]] -= row["net"]
            judge(f"sans les {share:.0%} meilleurs trades", "dépendance", adj)

    table = pd.DataFrame([p.__dict__ for p in results])
    param_rows = table[table["kind"] == "paramètre"]
    # Sharp-peak detector: neighbours' median Sharpe relative to the chosen point.
    neighbour_ratio = (float(param_rows["sharpe"].median() / base)
                       if len(param_rows) and np.isfinite(base) and base > 0 else float("nan"))
    return {
        "base_sharpe": base,
        "score": float(table["passed"].mean()) if len(table) else float("nan"),
        "n_perturbations": int(len(table)),
        "neighbour_ratio": neighbour_ratio,
        "sharp_peak": bool(np.isfinite(neighbour_ratio) and neighbour_ratio < 0.5),
        "table": table,
    }
