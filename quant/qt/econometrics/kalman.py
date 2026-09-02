"""Kalman filtering — estimating a relationship that moves.

The problem with a rolling-window regression is that it has to choose between being
slow (long window, stale hedge ratio) and being noisy (short window, hedge ratio that
jumps around). A Kalman filter dissolves that trade-off: it treats the coefficient as a
hidden state that evolves, and updates it optimally at every observation, weighting new
information by how surprising it is relative to the noise you told it to expect.

Two uses here, both central to relative-value trading:

* `KalmanHedge` — a time-varying hedge ratio for a pair. Cointegration relationships
  drift (supply changes, one asset's narrative shifts) and a static OLS beta fitted
  once on the full sample is both stale and, in a backtest, a look-ahead: it used the
  whole history to set a number applied from day one. The filter's beta at time t uses
  only data up to t, which is why it is the version that can honestly be backtested.
* `kalman_smooth_level` — a local-level model, i.e. an adaptive trend estimate that
  responds fast to real level shifts and ignores noise, with no lag-inducing window.

The one parameter that matters is `delta`, the ratio of state noise to observation
noise: how fast you believe the relationship can genuinely move. Small values mean a
nearly-static hedge; large values track every wiggle. It is a modelling choice, not
something to optimise on the backtest's Sharpe.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class KalmanResult:
    beta: pd.DataFrame  # state estimates over time (slope, intercept)
    spread: pd.Series  # observation minus prediction — the tradeable residual
    prediction_error: pd.Series
    prediction_variance: pd.Series

    def zscore(self, min_periods: int = 30) -> pd.Series:
        """Prediction error scaled by its own forecast standard deviation.

        This is the natural signal from a Kalman filter and it is better behaved than a
        rolling z-score of the spread: the denominator is the model's own uncertainty,
        so the signal automatically shrinks when the filter is unsure — right after a
        regime change, for instance.
        """
        sd = np.sqrt(self.prediction_variance)
        z = self.prediction_error / sd.replace(0.0, np.nan)
        z.iloc[:min_periods] = np.nan  # the filter needs time to converge
        return z.rename("kalman_z")


class KalmanHedge:
    """Time-varying linear relationship y_t = beta_t * x_t + alpha_t + noise.

    State: [slope, intercept], following a random walk.
    Observation: y, with x entering the observation matrix.

    Strictly causal: every estimate at t is produced from observations up to t only.
    """

    def __init__(self, delta: float = 1e-4, observation_var: float = 1e-3, with_intercept: bool = True) -> None:
        self.delta = delta
        self.observation_var = observation_var
        self.with_intercept = with_intercept

    def run(self, y: pd.Series, x: pd.Series) -> KalmanResult:
        df = pd.concat([y.rename("y"), x.rename("x")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
        if len(df) < 10:
            empty = pd.Series(dtype="float64")
            return KalmanResult(pd.DataFrame(), empty, empty, empty)

        yv = df["y"].to_numpy(dtype="float64")
        xv = df["x"].to_numpy(dtype="float64")
        n = yv.size
        dim = 2 if self.with_intercept else 1

        # State-transition noise. delta/(1-delta) is the standard parameterisation
        # (Chan): it maps a single intuitive number onto the state covariance.
        wt = self.delta / max(1 - self.delta, 1e-12) * np.eye(dim)
        vt = self.observation_var

        beta = np.zeros(dim)
        P = np.eye(dim) * 1.0  # diffuse prior: we start out ignorant

        betas = np.zeros((n, dim))
        errors = np.zeros(n)
        variances = np.zeros(n)

        for t in range(n):
            H = np.array([xv[t], 1.0])[:dim]  # observation matrix

            # Predict: the state random-walks, so only its covariance changes.
            P_pred = P + wt

            # Observe.
            y_hat = float(H @ beta)
            error = yv[t] - y_hat
            S = float(H @ P_pred @ H.T) + vt  # forecast variance of the observation

            # Update.
            K = (P_pred @ H.T) / S  # Kalman gain
            beta = beta + K * error
            P = P_pred - np.outer(K, H) @ P_pred

            betas[t] = beta
            errors[t] = error
            variances[t] = S

        cols = ["slope", "intercept"][:dim]
        return KalmanResult(
            beta=pd.DataFrame(betas, index=df.index, columns=cols),
            spread=pd.Series(errors, index=df.index, name="spread"),
            prediction_error=pd.Series(errors, index=df.index, name="error"),
            prediction_variance=pd.Series(variances, index=df.index, name="variance"),
        )


def kalman_smooth_level(series: pd.Series, delta: float = 1e-5, observation_var: float = 1e-3) -> pd.DataFrame:
    """Local-level model: an adaptive estimate of the current 'true' level.

    Compared with a moving average, this has no fixed window and therefore no fixed
    lag: it adapts fast after a genuine level shift and stays quiet through noise. The
    returned `deviation` (observation minus filtered level, scaled by the filter's own
    uncertainty) is a mean-reversion signal that self-calibrates.
    """
    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < 5:
        return pd.DataFrame()

    values = x.to_numpy(dtype="float64")
    n = values.size
    q = delta / max(1 - delta, 1e-12)

    level = values[0]
    P = 1.0
    levels = np.zeros(n)
    deviations = np.zeros(n)
    variances = np.zeros(n)

    for t in range(n):
        P_pred = P + q
        error = values[t] - level
        S = P_pred + observation_var
        K = P_pred / S
        level = level + K * error
        P = (1 - K) * P_pred

        levels[t] = level
        deviations[t] = error / np.sqrt(S)
        variances[t] = S

    return pd.DataFrame(
        {"level": levels, "deviation": deviations, "variance": variances}, index=x.index
    )


def rolling_ols_beta(y: pd.Series, x: pd.Series, window: int = 168) -> pd.Series:
    """Rolling-window OLS slope — the thing the Kalman filter replaces.

    Kept for comparison. Run both on the same pair and the difference is visible
    immediately: the rolling beta steps whenever an old observation falls out of the
    window, which is an artefact of the window rather than anything the market did.
    """
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    mp = max(window // 4, 10)
    cov = df["y"].rolling(window, min_periods=mp).cov(df["x"])
    var = df["x"].rolling(window, min_periods=mp).var(ddof=0)
    return (cov / var.replace(0.0, np.nan)).rename("rolling_beta")
