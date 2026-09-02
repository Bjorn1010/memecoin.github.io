"""Stationarity and memory: is this series something a model can learn from?

The first question a quant asks of any series is not "does it trend" but "is it
stationary". A model fitted on a non-stationary series learns the level, and the level
never comes back — which is why a model trained on 2021 BTC prices predicts nothing in
2024 no matter how good the fit looked.

The tests here are the standard battery, and they are used together because they answer
*different* questions and frequently disagree:

* **ADF** — null hypothesis: there IS a unit root (non-stationary). Rejecting it is
  evidence of stationarity. Low power against near-unit-root series.
* **KPSS** — null hypothesis: the series IS stationary. The mirror image, so running
  both gives four outcomes rather than two, and "both reject" (a common result) is
  informative: it usually means the series is fractionally integrated, which is exactly
  what `features.statistical.frac_diff` is for.
* **Variance ratio (Lo-MacKinlay)** — not a unit-root test but a random-walk test, with
  a directional reading: above 1 means trending, below 1 mean-reverting.
* **Hurst** — the same question in the frequency domain, robust to different things.

`find_min_ffd` answers the practical question directly: what is the *smallest* amount
of differencing that makes this series stationary? Differencing more than necessary
throws away memory that carries signal, and the standard practice of always taking
d=1 (i.e. returns) is over-differencing almost every price series.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TestResult:
    name: str
    statistic: float
    pvalue: float
    critical_values: dict[str, float]
    null_hypothesis: str
    reject_null: bool
    interpretation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "statistic": self.statistic,
            "pvalue": self.pvalue,
            "reject_null": self.reject_null,
            "interpretation": self.interpretation,
        }


def adf_test(series: pd.Series, alpha: float = 0.05, regression: str = "c") -> TestResult:
    """Augmented Dickey-Fuller. Null: a unit root is present (non-stationary)."""
    from statsmodels.tsa.stattools import adfuller

    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < 20:
        return TestResult("ADF", np.nan, np.nan, {}, "unit root present", False, "insufficient data")

    stat, pvalue, _, _, crit, _ = adfuller(x.to_numpy(), regression=regression, autolag="AIC")
    reject = pvalue < alpha
    return TestResult(
        "ADF",
        float(stat),
        float(pvalue),
        {k: float(v) for k, v in crit.items()},
        "unit root present (non-stationary)",
        reject,
        "stationary" if reject else "cannot reject a unit root — treat as non-stationary",
    )


def kpss_test(series: pd.Series, alpha: float = 0.05, regression: str = "c") -> TestResult:
    """KPSS. Null: the series IS stationary — the mirror of ADF."""
    import warnings

    from statsmodels.tsa.stattools import kpss

    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < 20:
        return TestResult("KPSS", np.nan, np.nan, {}, "stationary", False, "insufficient data")

    with warnings.catch_warnings():
        # statsmodels warns whenever the p-value is clipped at the table edge; that is
        # expected on strongly (non-)stationary series and is not an error.
        warnings.simplefilter("ignore")
        stat, pvalue, _, crit = kpss(x.to_numpy(), regression=regression, nlags="auto")
    reject = pvalue < alpha
    return TestResult(
        "KPSS",
        float(stat),
        float(pvalue),
        {k: float(v) for k, v in crit.items()},
        "series is stationary",
        reject,
        "non-stationary" if reject else "consistent with stationarity",
    )


def stationarity_report(series: pd.Series, alpha: float = 0.05) -> dict:
    """Run ADF and KPSS together and read the four-way outcome.

    Both tests agreeing is the easy case. The two disagreements are the informative
    ones, and the joint reading is why both are always run:

    | ADF rejects | KPSS rejects | reading                                        |
    |-------------|--------------|------------------------------------------------|
    | yes         | no           | stationary — safe to model directly            |
    | no          | yes          | non-stationary — difference it first           |
    | no          | no           | not enough data to tell; treat as inconclusive |
    | yes         | yes          | likely fractionally integrated — use frac_diff |
    """
    adf = adf_test(series, alpha)
    kpss_res = kpss_test(series, alpha)

    if adf.reject_null and not kpss_res.reject_null:
        verdict = "stationary"
        advice = "model the series directly"
    elif not adf.reject_null and kpss_res.reject_null:
        verdict = "non-stationary"
        advice = "difference it — try find_min_ffd() before defaulting to returns"
    elif adf.reject_null and kpss_res.reject_null:
        verdict = "fractionally integrated"
        advice = "use features.statistical.frac_diff with d between 0.2 and 0.6"
    else:
        verdict = "inconclusive"
        advice = "neither test resolves; get more data before trusting a model on this"

    return {"adf": adf.to_dict(), "kpss": kpss_res.to_dict(), "verdict": verdict, "advice": advice}


def variance_ratio_test(series: pd.Series, q: int = 4, use_log: bool = True) -> TestResult:
    """Lo-MacKinlay variance ratio with the heteroskedasticity-robust statistic.

    VR > 1: positive autocorrelation, i.e. trending — momentum should work.
    VR < 1: mean reversion — momentum should lose, reversal should work.
    VR = 1: random walk.

    The robust variant matters in crypto: the homoskedastic statistic rejects the
    random walk constantly purely because of volatility clustering, which has nothing
    to do with predictability.
    """
    from scipy import stats

    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if use_log:
        x = np.log(x[x > 0])
    r = x.diff().dropna().to_numpy()
    n = r.size
    if n < q * 10:
        return TestResult("VarianceRatio", np.nan, np.nan, {}, "random walk", False, "insufficient data")

    mu = r.mean()
    var1 = np.sum((r - mu) ** 2) / (n - 1)
    # Overlapping q-period returns: more efficient than non-overlapping blocks.
    rq = np.convolve(r, np.ones(q), mode="valid")
    m = q * (n - q + 1) * (1 - q / n)
    varq = np.sum((rq - q * mu) ** 2) / m
    vr = varq / var1 if var1 > 0 else np.nan

    # Heteroskedasticity-robust standard error (Lo & MacKinlay 1988, theorem 3).
    theta = 0.0
    dev = (r - mu) ** 2
    denom = dev.sum() ** 2
    for j in range(1, q):
        num = np.sum(dev[j:] * dev[:-j])
        delta = n * num / denom if denom > 0 else 0.0
        theta += (2 * (q - j) / q) ** 2 * delta
    se = np.sqrt(theta) if theta > 0 else np.nan
    z = (vr - 1) / se if se and np.isfinite(se) and se > 0 else np.nan
    pvalue = 2 * (1 - stats.norm.cdf(abs(z))) if np.isfinite(z) else np.nan

    if not np.isfinite(vr):
        reading = "undefined"
    elif vr > 1.05:
        reading = f"trending (VR={vr:.2f}) — favours momentum"
    elif vr < 0.95:
        reading = f"mean-reverting (VR={vr:.2f}) — favours reversal"
    else:
        reading = f"random walk (VR={vr:.2f}) — neither"

    return TestResult(
        "VarianceRatio",
        float(vr) if np.isfinite(vr) else np.nan,
        float(pvalue) if np.isfinite(pvalue) else np.nan,
        {},
        "series follows a random walk",
        bool(np.isfinite(pvalue) and pvalue < 0.05),
        reading,
    )


def find_min_ffd(
    series: pd.Series,
    d_values: np.ndarray | None = None,
    alpha: float = 0.05,
    threshold: float = 1e-4,
) -> dict:
    """Smallest fractional differencing order that achieves stationarity.

    Answers the question that matters in practice: how much memory can I keep and
    still have a series a model can learn from? Taking d=1 (plain returns) is what
    almost everyone does and it is over-differencing — it removes all memory of the
    level, and the level (position in range, distance from peak) is real information.

    Returns the chosen d, the correlation between the differenced series and the
    original (how much memory survived), and the full search path.
    """
    from ..features.statistical import frac_diff

    d_values = d_values if d_values is not None else np.linspace(0, 1, 11)
    x = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    x = np.log(x[x > 0]) if (x > 0).all() else x

    rows = []
    chosen = None
    for d in d_values:
        fd = frac_diff(x, d=float(d), threshold=threshold).dropna()
        if len(fd) < 30:
            continue
        adf = adf_test(fd, alpha)
        corr = float(np.corrcoef(x.loc[fd.index], fd)[0, 1]) if len(fd) > 2 else np.nan
        rows.append(
            {
                "d": float(d),
                "adf_stat": adf.statistic,
                "adf_pvalue": adf.pvalue,
                "stationary": adf.reject_null,
                "corr_with_original": corr,
                "n_obs": len(fd),
            }
        )
        if chosen is None and adf.reject_null:
            chosen = float(d)

    path = pd.DataFrame(rows)
    memory = float(path.loc[path["d"] == chosen, "corr_with_original"].iloc[0]) if chosen is not None and not path.empty else np.nan
    return {
        "d": chosen,
        "memory_retained": memory,
        "path": path,
        "advice": (
            f"d={chosen} achieves stationarity while retaining {memory:.0%} correlation "
            "with the original series"
            if chosen is not None
            else "no tested d achieved stationarity — widen d_values or get more data"
        ),
    }


def half_life(series: pd.Series) -> float:
    """Mean-reversion half-life from an AR(1) fit, in bars.

    Fits dY = lambda * Y_{t-1} + c and reports ln(2) / -lambda. This is the single most
    useful number for a mean-reversion strategy: it sets the holding period, the
    lookback for the z-score, and whether the trade is even viable after costs. A
    half-life of 400 bars on an hourly series means a two-week hold, which changes the
    cost arithmetic completely.

    Returns inf when the series is not mean-reverting (lambda >= 0).
    """
    y = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if len(y) < 20:
        return float("nan")
    lagged = y.shift(1).dropna()
    delta = (y - y.shift(1)).dropna()
    common = lagged.index.intersection(delta.index)
    x = np.column_stack([lagged.loc[common].to_numpy(), np.ones(len(common))])
    beta, *_ = np.linalg.lstsq(x, delta.loc[common].to_numpy(), rcond=None)
    lam = beta[0]
    if lam >= 0:
        return float("inf")
    return float(np.log(2) / -lam)
