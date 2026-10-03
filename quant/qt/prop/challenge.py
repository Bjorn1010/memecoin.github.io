"""Would this strategy pass this prop program? A Monte Carlo answer, not a yes.

The strategy's daily return stream (at research size) is scaled to a risk level and
replayed through the program's rules — daily loss on the bar's worst intrabar mark,
static or trailing drawdown, profit target, minimum days, maximum days. Paths are
drawn by block bootstrap of the stream so that many start dates and orderings are
tried, not only the one history produced.

What this cannot see: intraday paths finer than the daily bar (the worst intrabar mark
is an approximation), the firm's own spreads and swaps, and rule changes. Read the
result as a ranking of risk levels, not as a pass probability to bet on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .rules import Program


def run_path(returns: np.ndarray, worst: np.ndarray, program: Program, scale: float) -> tuple[str, int]:
    size = program.account_size
    equity = size
    high = size
    dl = program.daily_loss_amount
    dd = program.total_drawdown_amount
    target = program.profit_target_amount
    max_days = program.max_calendar_days or len(returns)
    days_traded = 0
    for d in range(min(len(returns), max_days)):
        start = equity
        intrabar = start * (1 + scale * worst[d])
        equity = start * (1 + scale * returns[d])
        if returns[d] != 0:
            days_traded += 1
        low_point = min(intrabar, equity)
        if dl is not None and low_point <= start - dl:
            return "failed_daily", d + 1
        if program.drawdown_type == "trailing_intraday":
            floor = high - dd
            high = max(high, equity)
        else:
            floor = (high - dd) if program.drawdown_type == "trailing_eod" else size - dd
        if program.trailing_lock_at_start:
            floor = min(floor, size)
        if low_point <= floor:
            return "failed_drawdown", d + 1
        if program.drawdown_type == "trailing_eod":
            high = max(high, equity)
        if target is not None and equity - size >= target and days_traded >= program.min_trading_days:
            return "passed", d + 1
    return ("timeout" if target is not None else "survived"), min(len(returns), max_days)


def challenge_monte_carlo(returns: pd.Series, worst: pd.Series, program: Program, *,
                          scales=(0.25, 0.5, 0.75, 1.0, 1.5, 2.0), horizon_days: int = 252,
                          n_paths: int = 2000, block: int = 21, seed: int = 0) -> pd.DataFrame:
    r = returns.fillna(0.0).to_numpy()
    w = worst.reindex(returns.index).fillna(0.0).to_numpy()
    w = np.minimum(w, r)
    n = len(r)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(horizon_days / block))
    starts = rng.integers(0, max(n - block, 1), size=(n_paths, nb))
    rows = []
    for scale in scales:
        outcomes, days = [], []
        for p in range(n_paths):
            idx = np.concatenate([np.arange(s, s + block) for s in starts[p]])[:horizon_days]
            out, d = run_path(r[idx], w[idx], program, scale)
            outcomes.append(out)
            days.append(d)
        o = pd.Series(outcomes)
        rows.append({
            "risk_scale": scale,
            "p_pass": float((o == "passed").mean()),
            "p_fail_daily": float((o == "failed_daily").mean()),
            "p_fail_drawdown": float((o == "failed_drawdown").mean()),
            "p_timeout": float(o.isin(["timeout", "survived"]).mean()),
            "median_days_to_pass": float(np.median([d for d, x in zip(days, outcomes) if x == "passed"]))
            if (o == "passed").any() else float("nan"),
        })
    return pd.DataFrame(rows)
