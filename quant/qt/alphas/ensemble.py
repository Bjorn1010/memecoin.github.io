"""Combining alphas without cheating.

The tempting way to combine signals is to compute each one's information coefficient
over the whole sample and weight accordingly. That is look-ahead: the weight used in
January encodes how the alpha performed in December of the following year. It reliably
produces a beautiful equity curve and no live edge whatsoever.

Everything here is computed on trailing windows only. The weight applied at time t is a
function of performance strictly before t, which is exactly what a live system could
have known. It makes the backtest look worse. That is the point.

Three combination schemes:

* **equal weight** — the honest baseline, and hard to beat. With noisy weight
  estimates, equal weighting frequently outperforms "optimised" weights out of sample.
* **IC-weighted** — trailing rank correlation between signal and subsequent return,
  shrunk toward equal weight so one lucky window cannot dominate.
* **risk parity** — inverse volatility of each alpha's own signal-return stream, so no
  single alpha contributes most of the portfolio's variance.

`orthogonalise` removes the overlap between correlated alphas, so that five variations
of momentum do not silently become a 5x leveraged momentum bet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def signal_returns(signals: pd.DataFrame, forward_ret: pd.Series) -> pd.DataFrame:
    """Per-bar return each alpha would have earned, before costs."""
    fwd = forward_ret.reindex(signals.index)
    return signals.mul(fwd, axis=0)


def information_coefficient(
    signals: pd.DataFrame, forward_ret: pd.Series, window: int = 720, method: str = "pearson"
) -> pd.DataFrame:
    """Trailing correlation between each signal and the return that followed.

    The IC is the cleanest single measure of whether a signal carries information.
    Values are small by nature: a persistent IC of 0.03-0.05 is a real, tradable edge;
    anything above 0.2 on liquid markets should be assumed to be a bug until proven
    otherwise.

    `method="pearson"` is the default and is vectorised. Signals here are already
    squashed into [-1, 1], so the outlier sensitivity that normally argues for rank
    correlation is largely handled. `method="spearman"` is available and correct, but
    costs O(n x window) with a sort inside — worth it for a final report, not inside a
    weighting loop.
    """
    fwd = forward_ret.reindex(signals.index)
    mp = max(window // 4, 30)
    out = {}
    for col in signals.columns:
        if method == "pearson":
            out[col] = signals[col].rolling(window, min_periods=mp).corr(fwd)
        else:
            out[col] = _rolling_spearman(pd.DataFrame({"x": signals[col], "y": fwd}), window, mp)
    return pd.DataFrame(out, index=signals.index)


def _rolling_spearman(df: pd.DataFrame, window: int, min_periods: int) -> pd.Series:
    x = df["x"].to_numpy(dtype="float64")
    y = df["y"].to_numpy(dtype="float64")
    n = len(df)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        xs = x[i - window + 1 : i + 1]
        ys = y[i - window + 1 : i + 1]
        mask = np.isfinite(xs) & np.isfinite(ys)
        if mask.sum() < min_periods:
            continue
        xr = pd.Series(xs[mask]).rank().to_numpy()
        yr = pd.Series(ys[mask]).rank().to_numpy()
        sx, sy = xr.std(), yr.std()
        if sx == 0 or sy == 0:
            continue
        out[i] = float(np.mean((xr - xr.mean()) * (yr - yr.mean())) / (sx * sy))
    return pd.Series(out, index=df.index)


def orthogonalise(signals: pd.DataFrame, window: int = 720) -> pd.DataFrame:
    """Sequentially remove each signal's projection onto the previous ones.

    Order matters and is taken as given (put the alpha you trust most first). Uses
    trailing windows, so the de-correlation applied at time t uses only past
    covariance.
    """
    cols = list(signals.columns)
    out = signals.copy()
    mp = max(window // 4, 30)
    for i, col in enumerate(cols[1:], start=1):
        residual = out[col].copy()
        for prior in cols[:i]:
            cov = residual.rolling(window, min_periods=mp).cov(out[prior])
            var = out[prior].rolling(window, min_periods=mp).var(ddof=0)
            beta = (cov / var.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            residual = residual - beta * out[prior]
        out[col] = residual
    return out


@dataclass
class EnsembleSpec:
    method: str = "ic_weighted"  # equal | ic_weighted | risk_parity
    window: int = 720  # trailing window for weights
    shrinkage: float = 0.5  # 0 = pure estimate, 1 = pure equal weight
    min_ic: float = 0.0  # alphas below this trailing IC get zero weight
    orthogonalise: bool = False
    clip: float = 1.0


def combine(
    signals: pd.DataFrame,
    forward_ret: pd.Series,
    spec: EnsembleSpec | None = None,
) -> tuple[pd.Series, pd.DataFrame]:
    """Combine alpha signals into one series. Returns (combined signal, weights).

    `forward_ret` is used only to *estimate weights from the past*; it is shifted so
    that the weight in force at time t depends on returns realised strictly before t.
    """
    spec = spec or EnsembleSpec()
    if signals.empty or signals.shape[1] == 0:
        return pd.Series(dtype="float64"), pd.DataFrame()

    sig = orthogonalise(signals, spec.window) if spec.orthogonalise else signals.copy()
    sig = sig.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    n = sig.shape[1]
    equal = pd.DataFrame(1.0 / n, index=sig.index, columns=sig.columns)

    if spec.method == "equal":
        weights = equal
    elif spec.method == "ic_weighted":
        ic = information_coefficient(sig, forward_ret, spec.window)
        # Shift by one bar: the IC computed *through* t already contains t's outcome.
        ic = ic.shift(1)
        pos_ic = ic.clip(lower=spec.min_ic).fillna(0.0)
        total = pos_ic.sum(axis=1).replace(0.0, np.nan)
        raw = pos_ic.div(total, axis=0)
        weights = raw.fillna(1.0 / n) * (1 - spec.shrinkage) + equal * spec.shrinkage
    elif spec.method == "risk_parity":
        rets = signal_returns(sig, forward_ret).shift(1)
        vol = rets.rolling(spec.window, min_periods=max(spec.window // 4, 30)).std(ddof=0)
        inv = (1.0 / vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        total = inv.sum(axis=1).replace(0.0, np.nan)
        raw = inv.div(total, axis=0)
        weights = raw.fillna(1.0 / n) * (1 - spec.shrinkage) + equal * spec.shrinkage
    else:
        raise ValueError(f"unknown ensemble method {spec.method!r}")

    combined = (sig * weights).sum(axis=1).clip(-spec.clip, spec.clip)
    return combined.rename("signal"), weights


def alpha_report(signals: pd.DataFrame, forward_ret: pd.Series, periods_per_year: float = 365 * 24) -> pd.DataFrame:
    """Full-sample diagnostics per alpha. In-sample by construction — orientation only.

    Read this to spot alphas that are broken (all-zero, degenerate, perfectly
    correlated with another), not to select which to trade. Selection uses the
    trailing-window machinery above and the validation module.
    """
    fwd = forward_ret.reindex(signals.index)
    rets = signal_returns(signals, fwd)
    rows = []
    for col in signals.columns:
        s = signals[col]
        r = rets[col].dropna()
        sd = r.std(ddof=1)
        rows.append(
            {
                "alpha": col,
                "ic": float(s.corr(fwd, method="spearman")) if s.notna().any() else np.nan,
                "sharpe_gross": float(r.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else np.nan,
                "hit_rate": float(((s > 0) == (fwd > 0)).mean()),
                "coverage": float((s.abs() > 0.05).mean()),  # how often it has an opinion
                "autocorr": float(s.autocorr(1)) if s.notna().sum() > 2 else np.nan,
                "mean_abs": float(s.abs().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("ic", ascending=False, key=abs).reset_index(drop=True)
