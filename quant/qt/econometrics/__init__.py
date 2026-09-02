"""Time-series econometrics: the statistical toolkit behind relative-value trading."""

from .breaks import chow_test, cusum_squares_test, rolling_break_monitor, sadf  # noqa: F401
from .cointegration import (  # noqa: F401
    CointegrationResult,
    engle_granger,
    johansen,
    screen_pairs,
)
from .garch import (  # noqa: F401
    GarchFit,
    compare_models,
    fit_ewma,
    fit_garch,
    volatility_forecast_score,
)
from .kalman import KalmanHedge, KalmanResult, kalman_smooth_level, rolling_ols_beta  # noqa: F401
from .ornstein_uhlenbeck import OUFit, fit_ou, optimal_thresholds, ou_signal  # noqa: F401
from .stationarity import (  # noqa: F401
    adf_test,
    find_min_ffd,
    half_life,
    kpss_test,
    stationarity_report,
    variance_ratio_test,
)
from .regime_switching import (  # noqa: F401
    RegimeFit,
    fit_regimes,
    regime_conditional_performance,
    regime_probabilities,
)
