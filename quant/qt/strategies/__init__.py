"""Strategies built from the quantitative toolkit."""

from .statarb import (  # noqa: F401
    PairAnalysis,
    PairSpec,
    analyse_pair,
    backtest_pair,
    monitor_pair,
    pair_signal,
    screen_and_analyse,
)
from .trend import (  # noqa: F401
    TrendResult,
    TrendSpec,
    build_trend,
    combine_trend_and_allocator,
    trend_score,
    trend_weights,
)
