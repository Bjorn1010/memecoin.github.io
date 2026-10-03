"""Internal research score — a way to ORDER the research queue, not a forecast.

Nine dimensions, each mapped to [0, 1]. The composite is a plain average; it is never a
gate on its own (the gates in the protocol are) and it says nothing about future
performance. A strategy with a high score and a failed gate is still rejected.
"""

from __future__ import annotations

import numpy as np


def _c(x, lo=0.0, hi=1.0):
    return float(np.clip(x, lo, hi)) if x is not None and np.isfinite(x) else 0.0


def research_score(*, wf_sharpe, positive_years, robustness, mc_p95_dd, cost_ratio, param_stability,
                   capacity_usd, regime_diversity, dsr) -> dict:
    dims = {
        "edge": _c(wf_sharpe / 1.0),
        "robustness": _c(robustness),
        "oos_stability": _c(positive_years),
        "drawdown": _c(1 - abs(mc_p95_dd) / 0.5) if mc_p95_dd is not None and np.isfinite(mc_p95_dd) else 0.0,
        "cost_sensitivity": _c(cost_ratio),
        "parameter_stability": _c(param_stability),
        "capacity": _c(np.log10(capacity_usd) / 7.0) if capacity_usd else 0.5,
        "regime_diversity": _c(regime_diversity),
        "statistical_confidence": _c(dsr),
    }
    dims["composite"] = float(np.mean(list(dims.values())))
    return dims
