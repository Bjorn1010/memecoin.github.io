"""Position sizing, evaluated separately from the signal.

The same unit-size return stream is re-sized five ways. The signal does not change, so
any difference in the outcome is the sizing's alone — which is how sizing should be
judged. Full Kelly is not offered: with an estimated edge, full Kelly over-bets whenever
the estimate is high, and the estimate is always noisy (qt/sizing/ruin.py measures it).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import compute


def compare_sizing(unit_returns: pd.Series, ppy: int, *, target_vol: float = 0.10, lookback: int = 63,
                   kelly_fraction: float = 0.25, max_leverage: float = 3.0, risk_per_trade: float = 1.0) -> dict:
    r = unit_returns.fillna(0.0)
    trailing_vol = r.rolling(lookback, min_periods=lookback // 2).std().shift(1) * np.sqrt(ppy)
    trailing_mu = r.rolling(252, min_periods=126).mean().shift(1) * ppy
    trailing_var = (r.rolling(252, min_periods=126).std().shift(1) * np.sqrt(ppy)) ** 2
    schemes = {
        "fixed_fractional": pd.Series(risk_per_trade, index=r.index),
        "volatility_target": (target_vol / trailing_vol).clip(upper=max_leverage),
        # Kelly from a trailing estimate, a quarter of it, never short when the
        # estimate turns negative (a negative Kelly says "do not trade", not "reverse").
        "fractional_kelly": (kelly_fraction * trailing_mu / trailing_var).clip(lower=0.0, upper=max_leverage),
    }
    out = {}
    for name, lev in schemes.items():
        sized = (lev.fillna(0.0) * r)
        m = compute(sized, None, ppy)
        m["avg_leverage"] = float(lev.fillna(0.0).mean())
        out[name] = m
    out["note"] = ("ATR / volatilité par instrument et parité de risque entre instruments sont déjà appliqués "
                   "dans le flux unitaire (chaque instrument dimensionné à 10 % de vol, pondération égale en risque).")
    return out
