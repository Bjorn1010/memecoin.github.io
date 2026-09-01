"""Volatility features.

Volatility is the most predictable quantity in finance — far more predictable than
return — and it is what turns a raw signal into a position size. Several estimators
are computed rather than one, because they disagree in informative ways:

* close-to-close ignores the path and underestimates when the range is wide;
* Parkinson uses the high-low range, ~5x more efficient, but ignores gaps;
* Garman-Klass adds the open-close body;
* Rogers-Satchell is drift-robust — the one to trust in a strong trend;
* Yang-Zhang combines overnight gaps with intraday movement, the best all-round.

The *spread between them* is itself a feature: Parkinson far above close-to-close
means violent intrabar movement that mean-reverts by the close, a jump/liquidation
signature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import log_returns, register, safe_div, zscore

VOL_WINDOWS = (24, 72, 168, 336)
_ANN = np.sqrt(365 * 24)  # 1h bars -> annualised; rescale elsewhere if bars differ


@register("vol", description="Realised volatility estimators", warmup=336, tags=("volatility", "core"))
def realised(bars: pd.DataFrame) -> pd.DataFrame:
    o = bars["open"].astype("float64")
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    c = bars["close"].astype("float64")
    r = log_returns(c)
    out: dict[str, pd.Series] = {}

    log_hl = np.log(safe_div(h, l))
    log_co = np.log(safe_div(c, o))
    log_ho = np.log(safe_div(h, o))
    log_lo = np.log(safe_div(l, o))
    prev_c = c.shift(1)
    log_oc_prev = np.log(safe_div(o, prev_c))

    for w in VOL_WINDOWS:
        mp = max(w // 4, 3)
        cc = r.rolling(w, min_periods=mp).std(ddof=0)
        out[f"cc_{w}"] = cc
        park = np.sqrt((log_hl**2).rolling(w, min_periods=mp).mean() / (4 * np.log(2)))
        out[f"parkinson_{w}"] = park
        gk = np.sqrt(
            (0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2).rolling(w, min_periods=mp).mean().clip(lower=0)
        )
        out[f"garman_klass_{w}"] = gk
        rs = np.sqrt(
            (log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)).rolling(w, min_periods=mp).mean().clip(lower=0)
        )
        out[f"rogers_satchell_{w}"] = rs
        # Yang-Zhang: overnight + open-to-close + drift-independent Rogers-Satchell.
        k = 0.34 / (1.34 + (w + 1) / (w - 1)) if w > 1 else 0.34
        v_open = (log_oc_prev - log_oc_prev.rolling(w, min_periods=mp).mean()).pow(2).rolling(
            w, min_periods=mp
        ).mean()
        v_close = (log_co - log_co.rolling(w, min_periods=mp).mean()).pow(2).rolling(w, min_periods=mp).mean()
        yz = np.sqrt((v_open + k * v_close + (1 - k) * rs**2).clip(lower=0))
        out[f"yang_zhang_{w}"] = yz
        # Estimator disagreement: intrabar violence relative to close-to-close.
        out[f"park_over_cc_{w}"] = safe_div(park, cc)

    base = out[f"cc_{VOL_WINDOWS[1]}"]
    out["annualised"] = base * _ANN
    # Vol of vol, and where current vol sits in its own history (the regime dial).
    out["of_vol"] = base.rolling(168, min_periods=48).std(ddof=0)
    out["z_168"] = zscore(base, 168)
    out["z_720"] = zscore(base, 720)
    # Term structure of realised vol: short over long. > 1 means vol is expanding.
    out["ratio_short_long"] = safe_div(out[f"cc_{VOL_WINDOWS[0]}"], out[f"cc_{VOL_WINDOWS[-1]}"])
    return pd.DataFrame(out, index=bars.index)


@register("atr", description="Average true range and range expansion", warmup=336, tags=("volatility",))
def atr(bars: pd.DataFrame) -> pd.DataFrame:
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    c = bars["close"].astype("float64")
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    out = {}
    for w in (14, 24, 72, 168):
        a = tr.ewm(alpha=1 / w, min_periods=w // 2, adjust=False).mean()
        out[f"{w}"] = safe_div(a, c)  # normalised: comparable across instruments
    out["tr_over_atr"] = safe_div(tr, tr.ewm(alpha=1 / 24, min_periods=6, adjust=False).mean())
    out["ratio"] = safe_div(out["24"], out["168"])
    return pd.DataFrame(out, index=bars.index)


@register("jump", description="Jump and tail-risk diagnostics", warmup=336, tags=("volatility",))
def jumps(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    r = log_returns(c)
    out = {}
    for w in (72, 168, 336):
        mp = max(w // 4, 3)
        # Bipower variation is robust to jumps; realised variance is not. Their gap
        # isolates the jump component of variance (Barndorff-Nielsen & Shephard).
        rv = (r**2).rolling(w, min_periods=mp).sum()
        bv = (r.abs() * r.abs().shift(1)).rolling(w, min_periods=mp).sum() * (np.pi / 2)
        out[f"jump_share_{w}"] = safe_div(rv - bv, rv).clip(-1, 1)
        out[f"skew_{w}"] = r.rolling(w, min_periods=mp).skew()
        out[f"kurt_{w}"] = r.rolling(w, min_periods=mp).kurt()
        # Downside semi-deviation: the half of vol that actually hurts a long.
        neg = r.where(r < 0, 0.0)
        out[f"semidev_{w}"] = neg.pow(2).rolling(w, min_periods=mp).mean().pow(0.5)
        out[f"vol_skew_{w}"] = safe_div(
            out[f"semidev_{w}"], r.where(r > 0, 0.0).pow(2).rolling(w, min_periods=mp).mean().pow(0.5)
        )
    vol = r.ewm(span=168, min_periods=24).std()
    out["ret_over_vol"] = safe_div(r, vol)
    out["abs_ret_z"] = zscore(r.abs(), 168)
    return pd.DataFrame(out, index=bars.index)
