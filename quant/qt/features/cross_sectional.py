"""Cross-sectional features — how an instrument ranks against its peers *right now*.

Time-series features answer "is BTC cheap versus its own past". Cross-sectional
features answer "is BTC cheap versus ETH, SOL and the rest today", which is a
different and largely uncorrelated question, and the basis of every long/short equity
factor ever run. In crypto it matters even more, because a single market factor
explains the majority of every altcoin's variance: without removing it, a "momentum"
model is really just a leveraged bet on beta.

Provided here:

* cross-sectional ranks (in [-1, 1]) of any time-series feature;
* rolling beta to the market and the residual (market-neutral) return;
* residual momentum — the part of the trend that is not just market direction;
* dispersion and average pairwise correlation, i.e. whether stock-picking is even
  possible in the current regime.

Everything is computed timestamp by timestamp on aligned panels, using only trailing
windows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import log_returns, safe_div


def align_panel(panel: dict[str, pd.DataFrame], column: str = "close") -> pd.DataFrame:
    """Stack one column from each instrument into a timestamp x symbol matrix.

    Uses an outer join then forward-fills *within each column only* — a stale price is
    an honest representation of an instrument that did not trade, whereas dropping the
    row would silently delete the timestamp for every other instrument too.
    """
    frames = {}
    for symbol, df in panel.items():
        if df is None or df.empty or column not in df.columns:
            continue
        s = df[column].astype("float64")
        s.index = df.index
        frames[symbol] = s
    if not frames:
        return pd.DataFrame()
    out = pd.DataFrame(frames).sort_index()
    return out.ffill()


def cross_sectional_rank(matrix: pd.DataFrame, *, min_names: int = 3) -> pd.DataFrame:
    """Rank each row across symbols, rescaled to [-1, 1]; NaN where too few names."""
    counts = matrix.notna().sum(axis=1)
    ranked = matrix.rank(axis=1, pct=True) * 2 - 1
    return ranked.where(counts >= min_names)


def market_factor(returns: pd.DataFrame, weights: pd.Series | None = None) -> pd.Series:
    """Equal-weight (or supplied-weight) market return — the first principal factor."""
    if weights is None:
        return returns.mean(axis=1, skipna=True)
    w = weights.reindex(returns.columns).fillna(0.0)
    total = w.sum()
    if total == 0:
        return returns.mean(axis=1, skipna=True)
    return (returns * w).sum(axis=1, skipna=True) / total


def rolling_beta(returns: pd.DataFrame, market: pd.Series, window: int = 168) -> pd.DataFrame:
    """Rolling beta of each instrument to the market factor."""
    mp = max(window // 4, 12)
    var = market.rolling(window, min_periods=mp).var(ddof=0)
    betas = {}
    for col in returns.columns:
        cov = returns[col].rolling(window, min_periods=mp).cov(market)
        betas[col] = safe_div(cov, var)
    return pd.DataFrame(betas, index=returns.index)


def build_panel_features(
    panel: dict[str, pd.DataFrame],
    *,
    beta_window: int = 168,
    momentum_windows: tuple[int, ...] = (24, 72, 168, 720),
) -> dict[str, pd.DataFrame]:
    """Compute cross-sectional features for every instrument in the panel.

    `panel` maps symbol -> bars frame (DatetimeIndex, at least a `close` column, and
    ideally `volume`). Returns symbol -> feature frame, prefixed `xs_`.
    """
    closes = align_panel(panel, "close")
    if closes.empty or closes.shape[1] < 2:
        return {s: pd.DataFrame(index=df.index) for s, df in panel.items()}

    rets = np.log(closes).diff()
    market = market_factor(rets)
    betas = rolling_beta(rets, market, beta_window)
    # `.mul(market, axis=0)`, never `betas * market`. Multiplying a DataFrame by a Series
    # aligns the Series' index against the frame's *columns*; here those are symbols
    # against timestamps, so the overlap is empty and every value becomes NaN. The result
    # still has the symbol columns (union alignment), so `residual[symbol]` keeps working
    # and returns an all-NaN series — no KeyError, no warning. That silently killed
    # `xs_resid_ret` and all four `xs_resmom_rank_*` columns, and with them the
    # xs_reversal alpha, which returned a flat zero for every bar.
    residual = rets.sub(betas.mul(market, axis=0))  # market-neutral return stream

    # Cross-sectional ranks of momentum, computed on both raw and residual returns.
    rank_frames: dict[str, pd.DataFrame] = {}
    for w in momentum_windows:
        mom = np.log(closes).diff(w)
        rank_frames[f"mom_rank_{w}"] = cross_sectional_rank(mom)
        res_mom = residual.rolling(w, min_periods=max(w // 4, 3)).sum()
        rank_frames[f"resmom_rank_{w}"] = cross_sectional_rank(res_mom)

    vol = rets.rolling(168, min_periods=48).std(ddof=0)
    rank_frames["vol_rank"] = cross_sectional_rank(vol)

    volumes = align_panel(panel, "quote_volume")
    if not volumes.empty:
        turnover = volumes.rolling(24, min_periods=6).sum()
        rank_frames["turnover_rank"] = cross_sectional_rank(turnover)
        rank_frames["turnover_shock_rank"] = cross_sectional_rank(
            safe_div_frame(turnover, turnover.rolling(168, min_periods=48).mean())
        )

    # Regime-level context, identical for every instrument but genuinely informative:
    # when dispersion collapses and correlation goes to 1, only direction matters and
    # relative-value strategies should stand down.
    dispersion = rets.std(axis=1, skipna=True)
    corr = _average_pairwise_correlation(rets, window=168)
    breadth = (rets > 0).sum(axis=1) / rets.notna().sum(axis=1).replace(0, np.nan)

    out: dict[str, pd.DataFrame] = {}
    for symbol, df in panel.items():
        if symbol not in closes.columns:
            out[symbol] = pd.DataFrame(index=df.index)
            continue
        cols = {
            "beta": betas[symbol],
            "resid_ret": residual[symbol],
            "market_ret": market,
            "dispersion": dispersion,
            "avg_corr": corr,
            "breadth": breadth,
        }
        for name, frame in rank_frames.items():
            if symbol in frame.columns:
                cols[name] = frame[symbol]
        feat = pd.DataFrame(cols).reindex(df.index)
        feat.columns = [f"xs_{c}" for c in feat.columns]
        out[symbol] = feat
    return out


def safe_div_frame(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    return (a / b.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)


def _average_pairwise_correlation(returns: pd.DataFrame, window: int = 168) -> pd.Series:
    """Mean off-diagonal correlation of the panel, rolling.

    Computed from the correlation of each name to the equal-weight market rather than
    every pair — O(n) instead of O(n^2), and the two agree closely for a panel driven
    by one dominant factor, which crypto is.
    """
    mp = max(window // 4, 12)
    market = returns.mean(axis=1, skipna=True)
    corrs = []
    for col in returns.columns:
        corrs.append(returns[col].rolling(window, min_periods=mp).corr(market))
    if not corrs:
        return pd.Series(np.nan, index=returns.index)
    return pd.concat(corrs, axis=1).mean(axis=1, skipna=True)
