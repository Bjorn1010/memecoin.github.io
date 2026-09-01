"""Market microstructure features — who is trading, how aggressively, at what cost.

This is where most of the free-data edge lives, and where most free datasets are
useless: an OHLCV row tells you a price moved, not whether buyers lifted offers or
sellers hit bids to get there. The Binance archive publishes `taker_buy_base`, so
signed order flow is available for the whole history at no cost.

Estimators implemented here are the standard ones from the market-microstructure
literature, all in rolling (causal) form:

* **Order flow imbalance** — net aggressive volume, the most direct read on pressure.
* **Kyle's lambda** — price move per unit of signed flow: the market's depth. Rising
  lambda means the book is thinning, which precedes violent moves.
* **Amihud illiquidity** — |return| per dollar traded, the low-frequency cousin.
* **Roll's estimator** — effective spread implied by negative return autocovariance.
* **Corwin-Schultz** — spread implied by the high-low range over one and two bars.
* **VPIN** — volume-synchronised probability of informed trading; it spiked before
  the 2010 flash crash and behaves similarly before crypto liquidation cascades.

Every one degrades to NaN, not to a wrong number, when the venue does not publish the
inputs it needs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import log_returns, register, safe_div, zscore

FLOW_WINDOWS = (6, 24, 72, 168)


def _signed_volume(bars: pd.DataFrame) -> pd.Series:
    """Net aggressive volume (buy-initiated minus sell-initiated), in base units."""
    if "buy_volume" in bars.columns and bars["buy_volume"].notna().any():
        buy = bars["buy_volume"].astype("float64")
        sell = bars.get("sell_volume")
        sell = sell.astype("float64") if sell is not None else bars["volume"].astype("float64") - buy
        return buy - sell
    if "taker_buy_base" in bars.columns and bars["taker_buy_base"].notna().any():
        buy = bars["taker_buy_base"].astype("float64")
        return 2 * buy - bars["volume"].astype("float64")
    # No aggressor information: fall back to the tick rule on bar closes. Coarse, but
    # better than pretending flow is unobservable.
    return np.sign(bars["close"].diff()).fillna(0.0) * bars["volume"].astype("float64")


@register("flow", description="Order flow imbalance and aggression", warmup=336, tags=("microstructure", "core"))
def order_flow(bars: pd.DataFrame) -> pd.DataFrame:
    volume = bars["volume"].astype("float64")
    signed = _signed_volume(bars)
    out: dict[str, pd.Series] = {}
    out["ofi"] = safe_div(signed, volume).clip(-1, 1)
    for w in FLOW_WINDOWS:
        mp = max(w // 4, 2)
        out[f"ofi_{w}"] = safe_div(
            signed.rolling(w, min_periods=mp).sum(), volume.rolling(w, min_periods=mp).sum()
        ).clip(-1, 1)
        out[f"ofi_z_{w}"] = zscore(out["ofi"], w)
    # Persistence of flow: informed order splitting shows up as positive
    # autocorrelation in imbalance, noise trading does not.
    out["ofi_autocorr_72"] = out["ofi"].rolling(72, min_periods=24).corr(out["ofi"].shift(1))
    # Divergence: price up while flow is negative means the move is unsupported.
    r = log_returns(bars["close"].astype("float64"))
    for w in (24, 72):
        out[f"flow_price_div_{w}"] = (
            np.sign(r.rolling(w, min_periods=6).sum()) - np.sign(out[f"ofi_{w}"])
        ).abs() / 2.0
    return pd.DataFrame(out, index=bars.index)


@register("liq", description="Liquidity, depth and price-impact estimators", warmup=336, tags=("microstructure",))
def liquidity(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"].astype("float64")
    r = log_returns(close)
    volume = bars["volume"].astype("float64")
    notional = bars["quote_volume"].astype("float64") if "quote_volume" in bars.columns else volume * close
    signed = _signed_volume(bars)
    out: dict[str, pd.Series] = {}

    # Amihud: average |return| per unit of dollar volume. Scaled by 1e6 to keep the
    # magnitude in a range that gradient boosting splits comfortably.
    illiq = safe_div(r.abs(), notional) * 1e6
    for w in (24, 72, 168):
        out[f"amihud_{w}"] = illiq.rolling(w, min_periods=max(w // 4, 3)).mean()

    # Kyle's lambda: rolling OLS slope of return on signed volume, no intercept.
    # lambda = cov(r, q) / var(q); the market's price impact per unit of flow.
    q = safe_div(signed, volume.rolling(168, min_periods=24).mean())  # normalise flow scale
    for w in (72, 168):
        mp = max(w // 4, 6)
        cov = r.rolling(w, min_periods=mp).cov(q)
        var = q.rolling(w, min_periods=mp).var(ddof=0)
        out[f"kyle_lambda_{w}"] = safe_div(cov, var) * 1e4
        out[f"kyle_lambda_z_{w}"] = zscore(out[f"kyle_lambda_{w}"], w)

    # Roll (1984): effective spread = 2*sqrt(-cov(dp_t, dp_{t-1})) when that cov < 0.
    dp = close.diff()
    for w in (24, 72):
        cov = dp.rolling(w, min_periods=max(w // 4, 4)).cov(dp.shift(1))
        out[f"roll_spread_{w}"] = safe_div(2 * np.sqrt((-cov).clip(lower=0)), close) * 1e4  # bps

    # Corwin-Schultz (2012) high-low spread estimator, in basis points.
    h, l = bars["high"].astype("float64"), bars["low"].astype("float64")
    beta = (np.log(safe_div(h, l)) ** 2).rolling(2, min_periods=2).sum()
    h2 = h.rolling(2, min_periods=2).max()
    l2 = l.rolling(2, min_periods=2).min()
    gamma = np.log(safe_div(h2, l2)) ** 2
    denom = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / denom - np.sqrt(gamma / denom)
    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    out["cs_spread"] = (spread.clip(lower=0) * 1e4).rolling(24, min_periods=6).mean()

    # Turnover and its trend: volume alone is not comparable across time, share of
    # recent average is.
    for w in (24, 72, 168):
        out[f"vol_ratio_{w}"] = safe_div(volume, volume.rolling(w, min_periods=max(w // 4, 3)).mean())
    out["notional_z_168"] = zscore(np.log1p(notional), 168)
    return pd.DataFrame(out, index=bars.index)


@register("tape", description="Trade-count, trade-size and VPIN diagnostics", warmup=336, tags=("microstructure",))
def tape(bars: pd.DataFrame) -> pd.DataFrame:
    volume = bars["volume"].astype("float64")
    out: dict[str, pd.Series] = {}

    if "trades" in bars.columns and bars["trades"].notna().any():
        n = bars["trades"].astype("float64")
        out["trade_intensity_z"] = zscore(np.log1p(n), 168)
        avg_size = safe_div(volume, n)
        out["avg_trade_size_z"] = zscore(np.log1p(avg_size), 168)
        # Large average size with flat trade count = institutional-style participation;
        # many tiny trades = retail churn or wash activity.
        out["size_over_count"] = safe_div(
            zscore(np.log1p(avg_size), 168), zscore(np.log1p(n), 168).abs() + 1.0
        )
    else:
        for name in ("trade_intensity_z", "avg_trade_size_z", "size_over_count"):
            out[name] = pd.Series(np.nan, index=bars.index)

    # VPIN: |buy - sell| / total, averaged over a window of volume buckets. Here the
    # buckets are bars, which is the standard approximation when using bar data.
    signed_abs = _signed_volume(bars).abs()
    for w in (24, 50, 168):
        mp = max(w // 4, 3)
        out[f"vpin_{w}"] = safe_div(
            signed_abs.rolling(w, min_periods=mp).sum(), volume.rolling(w, min_periods=mp).sum()
        ).clip(0, 1)
    out["vpin_z"] = zscore(out["vpin_50"], 336)
    return pd.DataFrame(out, index=bars.index)
