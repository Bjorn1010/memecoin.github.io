"""Statistical structure of the return series, plus calendar effects.

These features answer a question the price-level features cannot: *what kind of
process is this right now?* A market with Hurst > 0.5 and a variance ratio above 1 is
trending and should be traded with momentum; the same instrument two weeks later can
be strongly mean-reverting. Feeding the model a direct measurement of that structure
is far more efficient than hoping it infers the regime from raw prices.

`fracdiff` deserves a note. Prices are non-stationary, so models trained on them
break out of sample; the usual fix is to difference them into returns, which makes
them stationary but throws away *all* memory of the level — and the level (where we
are in the range, how far from the peak) is genuinely informative. Fractional
differentiation with d ≈ 0.3-0.6 keeps most of the memory while passing a
stationarity test. It is the best of both, and it is cheap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import log_returns, register, safe_div, zscore


# --------------------------------------------------------------------------
# fractional differentiation
# --------------------------------------------------------------------------
def frac_diff_weights(d: float, threshold: float = 1e-4, max_size: int = 2000) -> np.ndarray:
    """Binomial weights for fractional differencing, truncated where they vanish."""
    w = [1.0]
    for k in range(1, max_size):
        w_k = -w[-1] * (d - k + 1) / k
        if abs(w_k) < threshold:
            break
        w.append(w_k)
    return np.array(w[::-1])


def frac_diff(series: pd.Series, d: float = 0.4, threshold: float = 1e-4) -> pd.Series:
    """Fixed-width-window fractional differentiation (López de Prado, ch. 5).

    Causal: value at t uses only t-k..t. The first `len(w)-1` values are NaN because
    the window is not yet full — never back-filled, since that would inject the future.
    """
    w = frac_diff_weights(d, threshold)
    width = len(w)
    values = series.astype("float64").to_numpy()
    if values.size < width:
        return pd.Series(np.nan, index=series.index)
    out = np.full(values.size, np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(values, width)
    dotted = windows @ w
    out[width - 1 :] = dotted
    return pd.Series(out, index=series.index)


# --------------------------------------------------------------------------
# rolling statistical estimators
# --------------------------------------------------------------------------
def _hurst_rs(x: np.ndarray) -> float:
    """Hurst exponent by rescaled range over dyadic sub-samples.

    > 0.5 trending / persistent, ~0.5 random walk, < 0.5 mean-reverting.
    """
    n = x.size
    if n < 32 or not np.all(np.isfinite(x)):
        return np.nan
    scales = [s for s in (8, 16, 32, 64, 128) if s <= n // 2]
    if len(scales) < 2:
        return np.nan
    rs_values = []
    for s in scales:
        chunks = n // s
        rs_chunk = []
        for i in range(chunks):
            seg = x[i * s : (i + 1) * s]
            dev = np.cumsum(seg - seg.mean())
            r = dev.max() - dev.min()
            sd = seg.std(ddof=0)
            if sd > 0 and r > 0:
                rs_chunk.append(r / sd)
        if rs_chunk:
            rs_values.append((s, float(np.mean(rs_chunk))))
    if len(rs_values) < 2:
        return np.nan
    logs = np.log(np.array([v[0] for v in rs_values], dtype="float64"))
    logrs = np.log(np.array([v[1] for v in rs_values], dtype="float64"))
    slope = np.polyfit(logs, logrs, 1)[0]
    return float(slope)


def _variance_ratio(x: np.ndarray, q: int = 4) -> float:
    """Lo-MacKinlay variance ratio: var of q-period returns / (q * var of 1-period).

    > 1 means returns are positively autocorrelated (trending); < 1 mean-reverting.
    """
    n = x.size
    if n < q * 4 or not np.all(np.isfinite(x)):
        return np.nan
    v1 = np.var(x, ddof=1)
    if v1 <= 0:
        return np.nan
    agg = np.add.reduceat(x, np.arange(0, n - n % q, q))
    vq = np.var(agg, ddof=1)
    return float(vq / (q * v1))


def _shannon_entropy(x: np.ndarray, bins: int = 8) -> float:
    """Entropy of the discretised return distribution, normalised to [0, 1].

    Low entropy = the market is repeating itself = more predictable structure.
    """
    finite = x[np.isfinite(x)]
    if finite.size < 16:
        return np.nan
    hist, _ = np.histogram(finite, bins=bins)
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log(p)).sum() / np.log(bins))


def strided_rolling_apply(
    series: pd.Series, window: int, func, *, stride: int = 6, min_periods: int | None = None
) -> pd.Series:
    """Evaluate an expensive rolling statistic every `stride` bars, then hold the value.

    These estimators (Hurst, variance ratio, entropy) describe slow-moving structural
    properties measured over a 168+ bar window; recomputing them every single bar costs
    an order of magnitude more time to move the estimate by a rounding error. Holding
    the last computed value forward is still strictly causal — bar i+3 sees the number
    computed at bar i, which used only data up to i.
    """
    values = series.to_numpy(dtype="float64")
    n = values.size
    mp = min_periods or max(window // 2, 8)
    out = np.full(n, np.nan)
    for i in range(window - 1, n, stride):
        seg = values[i - window + 1 : i + 1]
        if np.isfinite(seg).sum() < mp:
            continue
        out[i] = func(seg[np.isfinite(seg)])
    return pd.Series(out, index=series.index).ffill(limit=stride - 1)


@register("stat", description="Hurst, variance ratio, autocorrelation, entropy", warmup=720, tags=("statistical",))
def structure(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    r = log_returns(c)
    out: dict[str, pd.Series] = {}

    # These are expensive; coarse windows, and evaluated on a stride (see above).
    for w in (168, 336):
        mp = max(w // 2, 64)
        out[f"hurst_{w}"] = strided_rolling_apply(r, w, _hurst_rs, min_periods=mp)
        out[f"vratio2_{w}"] = strided_rolling_apply(r, w, lambda x: _variance_ratio(x, 2), min_periods=mp)
        out[f"vratio8_{w}"] = strided_rolling_apply(r, w, lambda x: _variance_ratio(x, 8), min_periods=mp)
        out[f"entropy_{w}"] = strided_rolling_apply(r, w, _shannon_entropy, min_periods=mp)

    # Rolling autocorrelation, expressed as a rolling correlation against the lagged
    # series — mathematically identical to the per-window autocorr and vectorised,
    # where the apply-per-window form costs minutes on a multi-year sample.
    for lag in (1, 2, 6, 24):
        out[f"acf_{lag}_168"] = r.rolling(168, min_periods=48).corr(r.shift(lag))
    # Autocorrelation of |returns| is the volatility-clustering signature; it is far
    # more persistent than the autocorrelation of returns themselves.
    abs_r = r.abs()
    out["acf_abs_1_168"] = abs_r.rolling(168, min_periods=48).corr(abs_r.shift(1))
    return pd.DataFrame(out, index=bars.index)


@register("fd", description="Fractionally differentiated price (stationary with memory)", warmup=720, tags=("statistical", "core"))
def fractional(bars: pd.DataFrame) -> pd.DataFrame:
    log_close = np.log(bars["close"].astype("float64"))
    out = {}
    for d in (0.2, 0.4, 0.6):
        fd = frac_diff(log_close, d=d)
        out[f"d{int(d * 10)}"] = fd
        out[f"d{int(d * 10)}_z"] = zscore(fd, 336)
    return pd.DataFrame(out, index=bars.index)


@register("cal", description="Calendar and session effects", warmup=0, tags=("calendar",))
def calendar(bars: pd.DataFrame) -> pd.DataFrame:
    """Hour-of-day and day-of-week structure.

    Crypto trades 24/7 but its participants do not: liquidity and volatility follow
    the Asia/Europe/US session handovers, and the weekend is a distinct, thinner
    regime. Encoded as sine/cosine pairs so the model sees 23:00 and 00:00 as
    adjacent rather than as opposite extremes.
    """
    idx = bars.index
    if not isinstance(idx, pd.DatetimeIndex):
        return pd.DataFrame(index=idx)
    hour = idx.hour.to_numpy(dtype="float64")
    dow = idx.dayofweek.to_numpy(dtype="float64")
    out = {
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "dow_sin": np.sin(2 * np.pi * dow / 7),
        "dow_cos": np.cos(2 * np.pi * dow / 7),
        "is_weekend": (dow >= 5).astype("float64"),
        # Session flags in UTC: Asia 00-08, Europe 07-16, US 13-21.
        "asia": ((hour >= 0) & (hour < 8)).astype("float64"),
        "europe": ((hour >= 7) & (hour < 16)).astype("float64"),
        "us": ((hour >= 13) & (hour < 21)).astype("float64"),
        # The 8-hourly perp funding stamps (00/08/16 UTC) reliably distort flow.
        "funding_hour": np.isin(hour, [0, 8, 16]).astype("float64"),
    }
    return pd.DataFrame(out, index=idx)
