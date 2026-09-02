"""Cointegration — the statistical basis of every pairs and relative-value trade.

Two non-stationary price series are cointegrated when some linear combination of them
*is* stationary. That combination is a spread with a mean it keeps returning to, and
trading it is the purest form of statistical arbitrage: you are not predicting either
price, only betting that a relationship holds.

Two tests, for two situations:

* **Engle-Granger** — regress one series on the other, test the residual for a unit
  root *with cointegration critical values*, not ordinary ADF ones. This distinction
  decides whether the test works at all: the regression is fitted to minimise the very
  residual variance the test examines, so plain ADF critical values reject far too
  often (measured here: 14 spurious cointegrations in 20 independent random-walk
  pairs). Simple, two assets only, and the result depends on which asset goes on the
  left, so both orientations are tested and the p-value is Bonferroni-corrected for it.
* **Johansen** — a system test that handles N assets at once and finds all independent
  cointegrating relationships, without an arbitrary choice of dependent variable. This
  is what you use for a basket.

A warning that matters more than the mathematics: **cointegration found by searching
over many pairs is mostly spurious**. Test 100 pairs at 5% significance and you expect
5 false positives with beautiful backtests. `screen_pairs` therefore reports the
multiple-testing-adjusted threshold alongside the raw p-values, and the economic
question ("why *should* these two be linked?") remains the real filter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from statsmodels.tsa.stattools import coint

from .stationarity import half_life


@dataclass
class CointegrationResult:
    asset_a: str
    asset_b: str
    hedge_ratio: float  # units of B per unit of A
    intercept: float
    pvalue: float
    statistic: float
    half_life_bars: float
    spread_std: float
    cointegrated: bool
    direction: str  # which regression orientation produced the result
    raw_pvalue: float = float("nan")  # before the two-orientation correction

    def _resolve(self, a, b=None, *, use_log: bool = True) -> tuple[pd.Series, pd.Series]:
        """Get (asset_a, asset_b) series, by name when possible.

        `engle_granger` tests both orientations and may return the pair reversed
        relative to how it was called, so passing the two series positionally in the
        original order silently builds the wrong spread — one that is still plausible
        and simply does not mean-revert. Pass a DataFrame (or dict) keyed by asset name
        and the correct series are selected by name; the positional form is kept for
        convenience and validated where it can be.
        """
        if b is None:
            frame = pd.DataFrame(a) if not isinstance(a, pd.DataFrame) else a
            missing = [c for c in (self.asset_a, self.asset_b) if c not in frame.columns]
            if missing:
                raise KeyError(
                    f"columns {missing} not found; this result is oriented as "
                    f"{self.asset_a} on {self.asset_b} ({self.direction})"
                )
            sa, sb = frame[self.asset_a], frame[self.asset_b]
        else:
            sa, sb = a, b
            for series, expected in ((sa, self.asset_a), (sb, self.asset_b)):
                name = getattr(series, "name", None)
                if name is not None and name != expected:
                    raise ValueError(
                        f"series named {name!r} passed where {expected!r} was expected — "
                        f"this result is oriented {self.asset_a} on {self.asset_b}. "
                        "Pass a DataFrame keyed by asset name to avoid the ambiguity."
                    )
        if use_log:
            sa, sb = np.log(sa.astype("float64")), np.log(sb.astype("float64"))
        return sa, sb

    def spread(self, a, b=None, *, use_log: bool = True) -> pd.Series:
        """The stationary combination: asset_a minus hedge_ratio times asset_b.

        `use_log=True` matches how `engle_granger` fits by default — the hedge ratio is
        in log space, and applying it to raw prices produces a series with no reason to
        be stationary.
        """
        sa, sb = self._resolve(a, b, use_log=use_log)
        return (sa - self.hedge_ratio * sb - self.intercept).rename(
            f"{self.asset_a}-{self.hedge_ratio:.3f}*{self.asset_b}"
        )

    def zscore(self, a, b=None, window: int | None = None, *, use_log: bool = True) -> pd.Series:
        """Spread in standard deviations.

        With `window`, uses a trailing estimate — the only form usable in a backtest,
        since the full-sample mean and standard deviation are not knowable in advance.
        """
        spread = self.spread(a, b, use_log=use_log)
        if window is None:
            return (spread - spread.mean()) / spread.std(ddof=0)
        mean = spread.rolling(window, min_periods=max(window // 4, 10)).mean()
        std = spread.rolling(window, min_periods=max(window // 4, 10)).std(ddof=0)
        return (spread - mean) / std.replace(0.0, np.nan)

    def to_dict(self) -> dict:
        return {
            "pair": f"{self.asset_a}/{self.asset_b}",
            "hedge_ratio": self.hedge_ratio,
            "pvalue": self.pvalue,
            "half_life_bars": self.half_life_bars,
            "cointegrated": self.cointegrated,
            "direction": self.direction,
        }


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Simple OLS of y on x with an intercept. Returns (slope, intercept, residuals)."""
    design = np.column_stack([x, np.ones(x.size)])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ beta
    return float(beta[0]), float(beta[1]), residuals


def engle_granger(
    a: pd.Series, b: pd.Series, *, name_a: str = "A", name_b: str = "B", alpha: float = 0.05,
    use_log: bool = True,
) -> CointegrationResult:
    """Two-step Engle-Granger test, run in both directions with a correction.

    The orientation matters: regressing A on B and B on A can give different answers,
    and reporting only the one that happened to work is a quiet form of p-hacking. Both
    are computed and the stronger is returned, with the direction recorded.

    **And the p-value is doubled for it.** Taking the minimum of two tests and quoting
    it raw is the same multiple-testing error `screen_pairs` corrects for across pairs;
    doing it inside a single test would be inconsistent, and it roughly doubles the
    false-positive rate — enough to flag two independent random walks as cointegrated.
    The Bonferroni correction over the two orientations is exact here (two tests), and
    `raw_pvalue` keeps the uncorrected number for reference.
    """
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 60:
        return CointegrationResult(
            name_a, name_b, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, False, "n/a", np.nan
        )

    x_a = np.log(df["a"].to_numpy()) if use_log else df["a"].to_numpy()
    x_b = np.log(df["b"].to_numpy()) if use_log else df["b"].to_numpy()

    best = None
    for direction, (lhs, rhs, la, lb) in {
        "a_on_b": (x_a, x_b, name_a, name_b),
        "b_on_a": (x_b, x_a, name_b, name_a),
    }.items():
        slope, intercept, resid = _ols(lhs, rhs)
        resid_series = pd.Series(resid, index=df.index)

        # Engle-Granger p-value with MacKinnon critical values — NOT a plain ADF test
        # on the residuals. This distinction is not a technicality: the cointegrating
        # regression is fitted to minimise exactly the residual variance the test then
        # examines, so the residuals look far more stationary than they are, and the
        # standard ADF critical values reject constantly. Measured on independent
        # random walks, the plain-ADF version produced spurious cointegration in 14
        # cases out of 20; `coint` brings that back to the nominal rate.
        stat, raw_p, _ = coint(lhs, rhs, trend="c", autolag="aic")

        hl = half_life(resid_series)
        # Two orientations tested => Bonferroni over 2.
        corrected = min(raw_p * 2.0, 1.0) if np.isfinite(raw_p) else np.nan
        candidate = CointegrationResult(
            asset_a=la,
            asset_b=lb,
            hedge_ratio=slope,
            intercept=intercept,
            pvalue=corrected,
            statistic=float(stat),
            half_life_bars=hl,
            spread_std=float(resid_series.std(ddof=0)),
            cointegrated=bool(np.isfinite(corrected) and corrected < alpha),
            direction=direction,
            raw_pvalue=float(raw_p),
        )
        if best is None or (np.isfinite(candidate.pvalue) and candidate.pvalue < best.pvalue):
            best = candidate
    return best


def johansen(
    prices: pd.DataFrame, *, det_order: int = 0, k_ar_diff: int = 1, alpha: float = 0.05,
    use_log: bool = True,
) -> dict:
    """Johansen trace test for N assets simultaneously.

    Unlike Engle-Granger it needs no choice of dependent variable and finds *all*
    independent cointegrating vectors, so it is the right tool for a basket (say
    BTC/ETH/SOL) rather than a pair.

    The first eigenvector is the most strongly mean-reverting combination and is what a
    basket spread should be built from.
    """
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    df = prices.replace([np.inf, -np.inf], np.nan).dropna()
    if use_log:
        df = np.log(df[(df > 0).all(axis=1)])
    if len(df) < 100 or df.shape[1] < 2:
        return {"n_relationships": 0, "error": "need >=100 rows and >=2 assets"}

    res = coint_johansen(df.to_numpy(), det_order, k_ar_diff)
    # Column index into the critical-value table: 0 -> 90%, 1 -> 95%, 2 -> 99%.
    col = {0.10: 0, 0.05: 1, 0.01: 2}.get(alpha, 1)

    n_rel = 0
    rows = []
    for i in range(len(res.lr1)):
        trace_stat = float(res.lr1[i])
        crit = float(res.cvt[i, col])
        significant = trace_stat > crit
        rows.append(
            {
                "rank_null": f"r <= {i}",
                "trace_stat": trace_stat,
                "critical_value": crit,
                "reject": significant,
            }
        )
        if significant:
            n_rel = i + 1
        else:
            break

    # Eigenvectors are columns of evec, ordered by eigenvalue descending.
    vectors = pd.DataFrame(res.evec, index=df.columns)
    first = vectors.iloc[:, 0]
    first = first / first.abs().max()  # scale for readability

    spread = (df * first).sum(axis=1)
    return {
        "n_relationships": n_rel,
        "cointegrated": n_rel > 0,
        "trace_table": pd.DataFrame(rows),
        "eigenvectors": vectors,
        "weights": first,
        "spread": spread,
        "half_life_bars": half_life(spread),
        "eigenvalues": list(map(float, res.eig)),
    }


def screen_pairs(
    prices: pd.DataFrame,
    *,
    alpha: float = 0.05,
    min_half_life: float = 2.0,
    max_half_life: float = 500.0,
    use_log: bool = True,
) -> pd.DataFrame:
    """Test every pair in a price panel, with an explicit multiple-testing correction.

    Screening N assets means N(N-1)/2 tests. At 5% significance on 10 assets that is 45
    tests and ~2 expected false positives — each of which will produce a lovely
    backtest. The Bonferroni-adjusted threshold is reported alongside the raw p-value,
    and `passes_corrected` is the column to filter on.

    A half-life filter is applied too: a spread that reverts in 1 bar is noise the
    costs will eat, and one that takes 500 bars is a directional bet in disguise.
    """
    cols = list(prices.columns)
    n_tests = len(cols) * (len(cols) - 1) // 2
    corrected_alpha = alpha / max(n_tests, 1)

    rows = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            res = engle_granger(prices[a], prices[b], name_a=a, name_b=b, alpha=alpha, use_log=use_log)
            tradeable_hl = min_half_life <= res.half_life_bars <= max_half_life
            rows.append(
                {
                    "asset_a": res.asset_a,
                    "asset_b": res.asset_b,
                    "hedge_ratio": res.hedge_ratio,
                    "pvalue": res.pvalue,
                    "half_life_bars": res.half_life_bars,
                    "passes_raw": bool(np.isfinite(res.pvalue) and res.pvalue < alpha),
                    "passes_corrected": bool(np.isfinite(res.pvalue) and res.pvalue < corrected_alpha),
                    "half_life_ok": bool(tradeable_hl),
                    "tradeable": bool(
                        np.isfinite(res.pvalue) and res.pvalue < corrected_alpha and tradeable_hl
                    ),
                    "direction": res.direction,
                }
            )

    out = pd.DataFrame(rows).sort_values("pvalue").reset_index(drop=True)
    out.attrs["n_tests"] = n_tests
    out.attrs["alpha"] = alpha
    out.attrs["corrected_alpha"] = corrected_alpha
    return out
