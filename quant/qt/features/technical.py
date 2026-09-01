"""Classical technical indicators, treated as features rather than as rules.

A word on why these are here at all. As standalone trading rules ("buy when RSI < 30")
they are close to worthless: they are the most data-mined objects in finance and any
standalone edge was arbitraged away decades ago. As *inputs to a model* they are
useful, because each is a compact, well-behaved non-linear summary of the price path
that a tree can split on cheaply — and their conditional value (RSI oversold **while**
flow is positive **and** vol is contracting) is not the same thing as their
unconditional value.

So: computed, normalised, handed to the model, and never used as a rule on their own.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import register, safe_div, zscore


def _wilder(series: pd.Series, window: int) -> pd.Series:
    """Wilder's smoothing — the EMA variant the original indicators were defined with."""
    return series.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()


def _true_range(bars: pd.DataFrame) -> pd.Series:
    h, l, c = bars["high"], bars["low"], bars["close"]
    prev = c.shift(1)
    return pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)


@register("osc", description="Oscillators: RSI, Stochastic, Williams %R, CCI, MFI", warmup=336, tags=("technical",))
def oscillators(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    v = bars["volume"].astype("float64")
    out: dict[str, pd.Series] = {}

    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    for w in (14, 24, 72):
        rs = safe_div(_wilder(gain, w), _wilder(loss, w))
        rsi = 100 - 100 / (1 + rs)
        # Centre on zero and scale to [-1, 1]: models split cleaner on symmetric inputs.
        out[f"rsi_{w}"] = (rsi - 50) / 50

    for w in (14, 48):
        ll = l.rolling(w, min_periods=max(w // 2, 3)).min()
        hh = h.rolling(w, min_periods=max(w // 2, 3)).max()
        k = safe_div(c - ll, hh - ll)
        out[f"stoch_k_{w}"] = k * 2 - 1
        out[f"stoch_d_{w}"] = (k.rolling(3, min_periods=2).mean()) * 2 - 1
        out[f"williams_r_{w}"] = safe_div(hh - c, hh - ll) * -2 + 1

    tp = (h + l + c) / 3
    for w in (20, 72):
        ma = tp.rolling(w, min_periods=max(w // 2, 3)).mean()
        md = (tp - ma).abs().rolling(w, min_periods=max(w // 2, 3)).mean()
        out[f"cci_{w}"] = safe_div(tp - ma, 0.015 * md) / 100

    # Money Flow Index: RSI computed on dollar volume signed by the typical price.
    raw_flow = tp * v
    pos_flow = raw_flow.where(tp.diff() > 0, 0.0)
    neg_flow = raw_flow.where(tp.diff() < 0, 0.0)
    for w in (14, 48):
        ratio = safe_div(
            pos_flow.rolling(w, min_periods=max(w // 2, 3)).sum(),
            neg_flow.rolling(w, min_periods=max(w // 2, 3)).sum(),
        )
        out[f"mfi_{w}"] = ((100 - 100 / (1 + ratio)) - 50) / 50
    return pd.DataFrame(out, index=bars.index)


@register("trend", description="MACD, ADX/DMI, Aroon, Vortex, Supertrend state", warmup=336, tags=("technical",))
def trend(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    out: dict[str, pd.Series] = {}

    for fast, slow, sig in ((12, 26, 9), (24, 72, 18)):
        macd = c.ewm(span=fast, min_periods=fast, adjust=False).mean() - c.ewm(
            span=slow, min_periods=slow, adjust=False
        ).mean()
        signal = macd.ewm(span=sig, min_periods=sig, adjust=False).mean()
        out[f"macd_{fast}_{slow}"] = safe_div(macd, c)
        out[f"macd_hist_{fast}_{slow}"] = safe_div(macd - signal, c)

    tr = _true_range(bars)
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    for w in (14, 48):
        atr = _wilder(tr, w)
        plus_di = 100 * safe_div(_wilder(plus_dm, w), atr)
        minus_di = 100 * safe_div(_wilder(minus_dm, w), atr)
        dx = 100 * safe_div((plus_di - minus_di).abs(), plus_di + minus_di)
        out[f"adx_{w}"] = _wilder(dx, w) / 100  # 0 = no trend, ~1 = extreme trend
        out[f"di_diff_{w}"] = (plus_di - minus_di) / 100

    for w in (25, 72):
        # Aroon: how recently the window's extreme was set. Pure timing, no magnitude.
        idx_max = h.rolling(w, min_periods=max(w // 2, 3)).apply(np.argmax, raw=True)
        idx_min = l.rolling(w, min_periods=max(w // 2, 3)).apply(np.argmin, raw=True)
        out[f"aroon_up_{w}"] = idx_max / (w - 1)
        out[f"aroon_down_{w}"] = idx_min / (w - 1)
        out[f"aroon_osc_{w}"] = (idx_max - idx_min) / (w - 1)

    # Vortex: competing up/down movement, good at flagging trend *changes*.
    vm_plus = (h - l.shift(1)).abs()
    vm_minus = (l - h.shift(1)).abs()
    for w in (14, 48):
        tr_sum = tr.rolling(w, min_periods=max(w // 2, 3)).sum()
        out[f"vortex_{w}"] = safe_div(vm_plus.rolling(w, min_periods=max(w // 2, 3)).sum(), tr_sum) - safe_div(
            vm_minus.rolling(w, min_periods=max(w // 2, 3)).sum(), tr_sum
        )

    # Supertrend as a state variable (distance to the band, and which side we are on).
    for w, mult in ((10, 3.0), (48, 4.0)):
        atr = _wilder(tr, w)
        mid = (h + l) / 2
        upper = mid + mult * atr
        lower = mid - mult * atr
        out[f"supertrend_dist_{w}"] = safe_div(c - lower, c)
        out[f"supertrend_side_{w}"] = np.sign(safe_div(c - mid, c))

    # Ichimoku conversion/base lines, expressed as distances (never as crossovers).
    for a, b in ((9, 26), (24, 72)):
        conv = (h.rolling(a, min_periods=a // 2).max() + l.rolling(a, min_periods=a // 2).min()) / 2
        base = (h.rolling(b, min_periods=b // 2).max() + l.rolling(b, min_periods=b // 2).min()) / 2
        out[f"ichimoku_conv_{a}"] = safe_div(c, conv) - 1
        out[f"ichimoku_base_{b}"] = safe_div(c, base) - 1
        out[f"ichimoku_span_{a}_{b}"] = safe_div(conv - base, c)
    return pd.DataFrame(out, index=bars.index)


@register("band", description="Bollinger, Keltner and Donchian channel state", warmup=336, tags=("technical",))
def bands(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    out: dict[str, pd.Series] = {}

    for w, k in ((20, 2.0), (72, 2.5)):
        mp = max(w // 2, 3)
        ma = c.rolling(w, min_periods=mp).mean()
        sd = c.rolling(w, min_periods=mp).std(ddof=0)
        upper, lower = ma + k * sd, ma - k * sd
        out[f"bb_pctb_{w}"] = safe_div(c - lower, upper - lower)
        out[f"bb_width_{w}"] = safe_div(upper - lower, ma)
        # Bandwidth percentile is the "squeeze" detector: compressed vol precedes
        # expansion far more reliably than direction is predictable.
        out[f"bb_squeeze_{w}"] = out[f"bb_width_{w}"].rolling(336, min_periods=72).rank(pct=True)

    tr = _true_range(bars)
    for w, k in ((20, 2.0), (72, 2.5)):
        mp = max(w // 2, 3)
        ma = c.ewm(span=w, min_periods=mp, adjust=False).mean()
        atr = _wilder(tr, w)
        out[f"keltner_pos_{w}"] = safe_div(c - ma, k * atr)

    for w in (20, 55, 168):
        mp = max(w // 2, 3)
        hh = h.rolling(w, min_periods=mp).max()
        ll = l.rolling(w, min_periods=mp).min()
        out[f"donchian_pos_{w}"] = safe_div(c - ll, hh - ll) * 2 - 1
        # Breakout state: strictly using the channel as of the PREVIOUS bar, else the
        # current bar's own high defines the level it is supposed to break.
        out[f"donchian_break_{w}"] = (c > hh.shift(1)).astype("float64") - (c < ll.shift(1)).astype("float64")
    return pd.DataFrame(out, index=bars.index)


@register("volflow", description="Volume-based indicators: OBV, CMF, force index", warmup=336, tags=("technical",))
def volume_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    h = bars["high"].astype("float64")
    l = bars["low"].astype("float64")
    v = bars["volume"].astype("float64")
    out: dict[str, pd.Series] = {}

    obv = (np.sign(c.diff()).fillna(0.0) * v).cumsum()
    # A raw cumulative sum is non-stationary and unusable as a feature; its slope
    # relative to recent volume is not.
    for w in (24, 72):
        out[f"obv_slope_{w}"] = safe_div(obv.diff(w), v.rolling(w, min_periods=max(w // 4, 3)).sum())

    mfm = safe_div((c - l) - (h - c), h - l)
    mfv = mfm * v
    for w in (20, 72):
        mp = max(w // 2, 3)
        out[f"cmf_{w}"] = safe_div(mfv.rolling(w, min_periods=mp).sum(), v.rolling(w, min_periods=mp).sum())

    force = c.diff() * v
    for w in (13, 48):
        out[f"force_{w}"] = zscore(force.ewm(span=w, min_periods=w // 2, adjust=False).mean(), 168)

    # Volume-weighted momentum: return of the period weighted by where volume traded.
    if "vwap" in bars.columns:
        vwap = bars["vwap"].astype("float64")
        for w in (24, 72):
            out[f"vwap_dev_{w}"] = zscore(safe_div(c, vwap) - 1, w)
    return pd.DataFrame(out, index=bars.index)
