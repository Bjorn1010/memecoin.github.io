"""Was this result skill, or was it the 200th thing I tried?

A Sharpe ratio computed on a strategy you selected *because* it had a high Sharpe is
not an estimate of anything. If you test 100 random strategies on the same data, the
best one will show a Sharpe around 2.5 by construction, with zero edge. Reporting that
number as if it came from a single pre-registered test is the central sin of
quantitative research, and it is why most published backtests do not survive contact
with a live account.

This module implements the corrections:

* **PSR** — probability that the true Sharpe exceeds a benchmark, correcting for
  sample length, skew and kurtosis (a Sharpe of 1.5 on 60 fat-tailed observations is
  not the same claim as 1.5 on 6000 well-behaved ones).
* **DSR** — the same, but with the benchmark raised to what the best of N trials would
  be expected to produce by luck alone. This is the number to quote.
* **MinTRL** — how long a track record must be before a Sharpe is credible.
* **PBO** — probability of backtest overfitting, via combinatorially symmetric CV:
  how often the configuration that wins in-sample lands below median out-of-sample.
  Above ~0.5 the selection procedure is worse than useless.
* **Monte Carlo bootstrap** of the trade sequence: the distribution of outcomes the
  same edge could plausibly have produced, which is the honest way to state a drawdown
  expectation.

`n_trials` is not optional bookkeeping. Every configuration you evaluated counts —
including the ones you discarded because they looked bad.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

EULER_MASCHERONI = 0.5772156649015329


def sharpe_ratio(returns: pd.Series, periods_per_year: float = 365 * 24) -> float:
    """Annualised Sharpe of a per-bar return series (excess of zero)."""
    r = pd.Series(returns).dropna()
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float(r.mean() / sd * np.sqrt(periods_per_year))


def probabilistic_sharpe_ratio(
    returns: pd.Series, benchmark_sr: float = 0.0, periods_per_year: float = 365 * 24
) -> float:
    """P(true Sharpe > benchmark), adjusted for sample size, skew and kurtosis."""
    r = pd.Series(returns).dropna()
    n = len(r)
    if n < 3:
        return float("nan")
    sr = sharpe_ratio(r, periods_per_year)
    if not np.isfinite(sr):
        return float("nan")
    # Work in per-period units: the moment corrections are defined there.
    sr_p = sr / np.sqrt(periods_per_year)
    bench_p = benchmark_sr / np.sqrt(periods_per_year)
    skew = float(stats.skew(r, bias=False))
    kurt = float(stats.kurtosis(r, fisher=False, bias=False))
    denom = np.sqrt(max(1 - skew * sr_p + (kurt - 1) / 4.0 * sr_p**2, 1e-12))
    z = (sr_p - bench_p) * np.sqrt(n - 1) / denom
    return float(stats.norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Sharpe the best of `n_trials` independent no-edge strategies would show by luck.

    Uses the expected maximum of N draws from a normal with the observed cross-trial
    variance of Sharpe ratios (López de Prado & Bailey).
    """
    if n_trials <= 1 or sr_variance <= 0:
        return 0.0
    n = float(n_trials)
    z1 = stats.norm.ppf(1 - 1.0 / n)
    z2 = stats.norm.ppf(1 - 1.0 / (n * np.e))
    return float(np.sqrt(sr_variance) * ((1 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2))


def deflated_sharpe_ratio(
    returns: pd.Series,
    n_trials: int,
    sr_variance: float | None = None,
    trial_sharpes: pd.Series | None = None,
    periods_per_year: float = 365 * 24,
) -> dict:
    """Deflated Sharpe: PSR against the luck-adjusted benchmark.

    Supply either `sr_variance` (variance of Sharpes across all trials you ran) or
    `trial_sharpes` (the Sharpes themselves, from which it is computed). Reading the
    result: DSR > 0.95 is a genuine claim; DSR < 0.5 means the strategy is
    indistinguishable from the best of your random attempts.
    """
    if trial_sharpes is not None and len(trial_sharpes) > 1:
        sr_variance = float(pd.Series(trial_sharpes).var(ddof=1))
        n_trials = max(n_trials, len(trial_sharpes))

    # Without a dispersion estimate there is no deflation to perform. Defaulting
    # sr_variance to zero makes expected_max_sharpe return zero, so the "deflated"
    # figure silently equals the plain PSR against zero — and the verdict then announced
    # "significant after deflation" for a number that had never been deflated. That is
    # the most dangerous output this module can produce, because it is the one a reader
    # trusts most. Report the gap instead of papering over it.
    undeflated = sr_variance is None
    sr_variance = 0.0 if undeflated else float(sr_variance)

    benchmark = expected_max_sharpe(n_trials, sr_variance)
    dsr = probabilistic_sharpe_ratio(returns, benchmark, periods_per_year)
    result = {
        "sharpe": sharpe_ratio(returns, periods_per_year),
        "n_trials": int(n_trials),
        "sr_variance": sr_variance,
        "benchmark_sharpe": benchmark,
        "psr_vs_zero": probabilistic_sharpe_ratio(returns, 0.0, periods_per_year),
        "deflated_sharpe": dsr,
        "verdict": _verdict(dsr),
    }
    if undeflated and n_trials > 1:
        result["deflated_sharpe"] = float("nan")
        result["verdict"] = (
            f"NOT DEFLATED — pass sr_variance or trial_sharpes for {n_trials} trials; "
            "psr_vs_zero below ignores selection entirely"
        )
    return result


def _verdict(dsr: float) -> str:
    if not np.isfinite(dsr):
        return "insufficient data"
    if dsr >= 0.95:
        return "significant after deflation"
    if dsr >= 0.75:
        return "suggestive, not significant"
    return "indistinguishable from selection luck"


def min_track_record_length(
    returns: pd.Series,
    benchmark_sr: float = 0.0,
    confidence: float = 0.95,
    periods_per_year: float = 365 * 24,
) -> float:
    """Observations needed before the Sharpe is credible at `confidence`."""
    r = pd.Series(returns).dropna()
    if len(r) < 3:
        return float("nan")
    sr_p = sharpe_ratio(r, periods_per_year) / np.sqrt(periods_per_year)
    bench_p = benchmark_sr / np.sqrt(periods_per_year)
    if sr_p <= bench_p:
        return float("inf")
    skew = float(stats.skew(r, bias=False))
    kurt = float(stats.kurtosis(r, fisher=False, bias=False))
    num = 1 - skew * sr_p + (kurt - 1) / 4.0 * sr_p**2
    return float(1 + num * (stats.norm.ppf(confidence) / (sr_p - bench_p)) ** 2)


def probability_of_backtest_overfitting(
    performance: pd.DataFrame,
    n_splits: int = 10,
    metric: str = "sharpe",
    periods_per_year: float = 365 * 24,
) -> dict:
    """PBO via combinatorially symmetric cross-validation (Bailey et al.).

    `performance` is a matrix of per-bar returns, one column per configuration you
    evaluated. The sample is cut into `n_splits` blocks; for every way of assigning
    half the blocks to in-sample, the in-sample winner is found and its out-of-sample
    rank recorded. PBO is the share of cases where the winner lands in the bottom half
    out of sample.

    One trap worth knowing: do NOT demean the columns before passing them in. A column
    forced to sum to zero must underperform in exactly the blocks it did not win, so
    PBO goes to 1.0 by construction and says nothing about the selection procedure.
    Pass the raw return streams.
    """
    if performance.shape[1] < 2:
        return {"pbo": float("nan"), "n_configs": int(performance.shape[1]), "n_cases": 0}

    blocks = np.array_split(np.arange(len(performance)), n_splits)
    half = n_splits // 2
    logits: list[float] = []
    below_median = 0
    cases = 0

    for combo in combinations(range(n_splits), half):
        is_idx = np.concatenate([blocks[b] for b in combo])
        oos_idx = np.concatenate([blocks[b] for b in range(n_splits) if b not in combo])
        is_perf = performance.iloc[is_idx]
        oos_perf = performance.iloc[oos_idx]

        if metric == "sharpe":
            is_score = is_perf.apply(lambda c: sharpe_ratio(c, periods_per_year))
            oos_score = oos_perf.apply(lambda c: sharpe_ratio(c, periods_per_year))
        else:
            is_score = is_perf.mean()
            oos_score = oos_perf.mean()

        is_score = is_score.replace([np.inf, -np.inf], np.nan).dropna()
        if is_score.empty:
            continue
        winner = is_score.idxmax()
        ranks = oos_score.rank(pct=True)
        if winner not in ranks or not np.isfinite(ranks[winner]):
            continue
        w = float(ranks[winner])
        cases += 1
        if w < 0.5:
            below_median += 1
        w_clipped = min(max(w, 1e-6), 1 - 1e-6)
        logits.append(np.log(w_clipped / (1 - w_clipped)))

    pbo = below_median / cases if cases else float("nan")
    return {
        "pbo": float(pbo),
        "n_configs": int(performance.shape[1]),
        "n_cases": int(cases),
        "mean_logit": float(np.mean(logits)) if logits else float("nan"),
        "verdict": "overfit selection" if (np.isfinite(pbo) and pbo > 0.5) else "selection holds up",
    }


@dataclass
class BootstrapResult:
    sharpe: pd.Series
    max_drawdown: pd.Series
    total_return: pd.Series

    def summary(self, quantiles=(0.05, 0.25, 0.5, 0.75, 0.95)) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "sharpe": self.sharpe.quantile(quantiles),
                "max_drawdown": self.max_drawdown.quantile(quantiles),
                "total_return": self.total_return.quantile(quantiles),
            }
        )


def bootstrap_returns(
    returns: pd.Series,
    n_samples: int = 1000,
    block_size: int = 24,
    periods_per_year: float = 365 * 24,
    seed: int = 0,
) -> BootstrapResult:
    """Stationary block bootstrap of the return series.

    Resampling in blocks preserves the volatility clustering and autocorrelation that
    an IID bootstrap would destroy — which matters enormously for drawdown, since
    drawdown is entirely a property of the *ordering* of returns. The 5th percentile
    of the max-drawdown distribution is a far more honest risk statement than the
    single drawdown that happened to occur in the backtest.
    """
    r = pd.Series(returns).dropna().to_numpy()
    n = r.size
    if n < block_size * 2:
        empty = pd.Series(dtype="float64")
        return BootstrapResult(empty, empty, empty)

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    sharpes, drawdowns, totals = [], [], []
    for _ in range(n_samples):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        path = np.concatenate([r[s : s + block_size] for s in starts])[:n]
        sd = path.std(ddof=1)
        sharpes.append(path.mean() / sd * np.sqrt(periods_per_year) if sd > 0 else np.nan)
        equity = np.cumprod(1 + path)
        peak = np.maximum.accumulate(equity)
        drawdowns.append(float((equity / peak - 1).min()))
        totals.append(float(equity[-1] - 1))
    return BootstrapResult(pd.Series(sharpes), pd.Series(drawdowns), pd.Series(totals))
