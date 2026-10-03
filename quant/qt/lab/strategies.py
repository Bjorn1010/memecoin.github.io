"""Retail strategies, implemented in their simplest textbook form.

Every function takes daily bars (and its parameters) and returns a `StrategyOutput`
stamped at the bar whose close produced it. Nothing here knows about position sizing,
accounts, prop firms or brokers — that separation is tested.

Causality rule: every indicator uses data up to and including bar t, and the simulator
executes at t+1. A rolling max that should exclude today is written with `.shift(1)`
explicitly, because "close above the 20-day high" is a contradiction if today's high
is part of the 20 days (the close can never exceed a high that includes itself).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .simulate import StrategyOutput, wilder_atr

# ------------------------------------------------------------------ indicators


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).where(dn > 0, 100.0)


def adx(bars: pd.DataFrame, n: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    h, l = bars["high"], bars["low"]
    up = h.diff()
    dn = -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=bars.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=bars.index)
    atr = wilder_atr(bars, n)
    pdi = 100 * plus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / atr
    mdi = 100 * minus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean(), pdi, mdi


def hold_events(setup: pd.Series, bars_to_hold: int) -> pd.Series:
    """Turn a one-bar setup (+1/-1/0) into a target held for `bars_to_hold` bars.

    A fresh setup in the same direction extends the hold; an opposite one replaces it.
    """
    if bars_to_hold <= 1:
        return setup.astype("float64").fillna(0.0)
    s = setup.replace(0, np.nan)
    return s.ffill(limit=bars_to_hold - 1).fillna(0.0)


def _state_machine(long_entry, long_exit, short_entry, short_exit) -> pd.Series:
    """Position from entry/exit conditions — for rules whose exit differs from the
    reverse of their entry (Donchian 20/10, Bollinger exit at the mid-band)."""
    le, lx = long_entry.to_numpy(), long_exit.to_numpy()
    se, sx = short_entry.to_numpy(), short_exit.to_numpy()
    out = np.zeros(len(le))
    pos = 0
    for i in range(len(le)):
        if pos == 1 and lx[i]:
            pos = 0
        elif pos == -1 and sx[i]:
            pos = 0
        if pos == 0:
            if le[i] and not se[i]:
                pos = 1
            elif se[i] and not le[i]:
                pos = -1
        out[i] = pos
    return pd.Series(out, index=long_entry.index)


# ------------------------------------------------------------------ trend


def sma_cross(b, fast=50, slow=200):
    f, s = sma(b["close"], fast), sma(b["close"], slow)
    return StrategyOutput(target=np.sign(f - s).fillna(0.0))


def ema_cross(b, fast=12, slow=26):
    f, s = ema(b["close"], fast), ema(b["close"], slow)
    return StrategyOutput(target=np.sign(f - s).fillna(0.0))


def donchian(b, entry=20, exit=10, stop_atr=2.0):
    c = b["close"]
    hi_e, lo_e = b["high"].rolling(entry).max().shift(1), b["low"].rolling(entry).min().shift(1)
    hi_x, lo_x = b["high"].rolling(exit).max().shift(1), b["low"].rolling(exit).min().shift(1)
    t = _state_machine(c > hi_e, c < lo_x, c < lo_e, c > hi_x)
    return StrategyOutput(target=t, stop_atr=stop_atr)


def tsmom(b, lookback=252):
    return StrategyOutput(target=np.sign(b["close"].pct_change(lookback)).fillna(0.0))


def adx_trend(b, period=14, threshold=25):
    a, pdi, mdi = adx(b, period)
    t = np.where(a > threshold, np.sign(pdi - mdi), 0.0)
    return StrategyOutput(target=pd.Series(t, index=b.index).fillna(0.0))


# ------------------------------------------------------------------ mean reversion


def rsi2(b, length=2, threshold=10):
    r = rsi(b["close"], length)
    ma5 = sma(b["close"], 5)
    c = b["close"]
    t = _state_machine(r < threshold, c > ma5, r > 100 - threshold, c < ma5)
    return StrategyOutput(target=t)


def rsi2_trend(b, threshold=10, trend=200):
    r = rsi(b["close"], 2)
    ma5, mat = sma(b["close"], 5), sma(b["close"], trend)
    c = b["close"]
    up, down = c > mat, c < mat
    t = _state_machine((r < threshold) & up, (c > ma5) | down, (r > 100 - threshold) & down, (c < ma5) | up)
    return StrategyOutput(target=t)


def bollinger_reversion(b, n=20, k=2.0):
    c = b["close"]
    mid = sma(c, n)
    sd = c.rolling(n, min_periods=n).std()
    t = _state_machine(c < mid - k * sd, c >= mid, c > mid + k * sd, c <= mid)
    return StrategyOutput(target=t)


def pullback(b, lookback=5, trend=200, max_hold=10):
    c = b["close"]
    mat = sma(c, trend)
    low_n = c.rolling(lookback).min()
    high_n = c.rolling(lookback).max()
    t = _state_machine((c <= low_n) & (c > mat), c >= high_n, (c >= high_n) & (c < mat), c <= low_n)
    return StrategyOutput(target=t, max_hold=max_hold)


def ibs(b, threshold=0.2, hold=1):
    rng = (b["high"] - b["low"]).replace(0.0, np.nan)
    v = (b["close"] - b["low"]) / rng
    setup = pd.Series(np.where(v < threshold, 1.0, np.where(v > 1 - threshold, -1.0, 0.0)), index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


# ------------------------------------------------------------------ breakout


def vol_breakout(b, k=0.5, use_atr=False):
    rng = wilder_atr(b, 5) if use_atr else (b["high"] - b["low"])
    off = k * rng
    return StrategyOutput(long_entry_offset=off, short_entry_offset=off, exit_same_bar_close=True)


def nr7(b, n=7, hold=3):
    rng = b["high"] - b["low"]
    narrow = rng <= rng.rolling(n).min()
    return StrategyOutput(long_entry_level=b["high"].where(narrow), short_entry_level=b["low"].where(narrow),
                          max_hold=hold, stop_atr=1.0)


def prev_hl_breakout(b, buffer_atr=0.0, hold=1):
    a = wilder_atr(b, 14)
    out = StrategyOutput(long_entry_level=b["high"] + buffer_atr * a, short_entry_level=b["low"] - buffer_atr * a)
    if hold <= 1:
        out.exit_same_bar_close = True
    else:
        out.max_hold = hold
    return out


# ------------------------------------------------------------------ momentum


def roc_accel(b, n=20, m=5):
    roc = b["close"].pct_change(n)
    acc = roc - roc.shift(m)
    t = np.where((roc > 0) & (acc > 0), 1.0, np.where((roc < 0) & (acc < 0), -1.0, 0.0))
    return StrategyOutput(target=pd.Series(t, index=b.index))


def mtf_momentum(b, long=120, short=5, hold=10):
    c = b["close"]
    lr, sr = c.pct_change(long), c.pct_change(short)
    setup = pd.Series(np.where((lr > 0) & (sr < 0), 1.0, np.where((lr < 0) & (sr > 0), -1.0, 0.0)), index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


def xs_momentum_weights(closes: pd.DataFrame, vols: pd.DataFrame, lookback=126, skip=0,
                        rebalance=21) -> pd.DataFrame:
    """Cross-sectional momentum inside one asset class: long the top third, short the
    bottom third, each leg inverse-volatility weighted, rebalanced every `rebalance`."""
    mom = closes.shift(skip) / closes.shift(skip + lookback) - 1.0
    w = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    rebal = np.arange(len(closes)) % rebalance == 0
    for i in np.flatnonzero(rebal):
        m = mom.iloc[i].dropna()
        v = vols.iloc[i].reindex(m.index)
        m = m[v.notna() & (v > 0)]
        if len(m) < 3:
            continue
        k = max(len(m) // 3, 1)
        ranked = m.sort_values()
        inv = 1.0 / vols.iloc[i]
        longs, shorts = ranked.index[-k:], ranked.index[:k]
        w.iloc[i, w.columns.get_indexer(longs)] = (inv[longs] / inv[longs].sum()).to_numpy() * 0.5
        w.iloc[i, w.columns.get_indexer(shorts)] = -(inv[shorts] / inv[shorts].sum()).to_numpy() * 0.5
    keep = pd.Series(rebal, index=closes.index)
    return w.where(keep).ffill().fillna(0.0)


# ------------------------------------------------------------------ volatility


def squeeze_breakout(b, n=20, quantile=0.1, window=126, hold=10):
    c = b["close"]
    mid = sma(c, n)
    sd = c.rolling(n, min_periods=n).std()
    width = 4 * sd / mid
    # Compressed = yesterday's width in the bottom quantile of the trailing window.
    thresh = width.rolling(window, min_periods=window // 2).quantile(quantile)
    compressed = (width <= thresh).shift(1, fill_value=False)
    setup = pd.Series(np.where(compressed & (c > mid + 2 * sd), 1.0,
                               np.where(compressed & (c < mid - 2 * sd), -1.0, 0.0)), index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


def atr_breakout(b, k=1.0, hold=10):
    a = wilder_atr(b, 14).shift(1)
    d = b["close"].diff()
    setup = pd.Series(np.where(d > k * a, 1.0, np.where(d < -k * a, -1.0, 0.0)), index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


# ------------------------------------------------------------------ price action


def market_structure(b, swing=5):
    """Higher highs and higher lows. A swing high at t-k is only *known* at t, once k
    later bars have failed to exceed it — using it earlier is look-ahead."""
    h, l = b["high"].to_numpy(), b["low"].to_numpy()
    n = len(h)
    out = np.zeros(n)
    highs: list[float] = []
    lows: list[float] = []
    for t in range(2 * swing, n):
        p = t - swing
        win_h = h[p - swing:t + 1]
        win_l = l[p - swing:t + 1]
        if h[p] == win_h.max():
            highs.append(h[p])
        if l[p] == win_l.min():
            lows.append(l[p])
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                out[t] = 1.0
            elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                out[t] = -1.0
    return StrategyOutput(target=pd.Series(out, index=b.index))


def liquidity_sweep(b, lookback=20, hold=5):
    """"Turtle soup": price runs the N-day low (stops below it get taken) and closes
    back above it — the breakout failed, fade it."""
    prior_low = b["low"].rolling(lookback).min().shift(1)
    prior_high = b["high"].rolling(lookback).max().shift(1)
    long_ = (b["low"] < prior_low) & (b["close"] > prior_low)
    short = (b["high"] > prior_high) & (b["close"] < prior_high)
    setup = pd.Series(np.where(long_ & ~short, 1.0, np.where(short & ~long_, -1.0, 0.0)), index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


def rejection(b, wick=0.5, lookback=20, hold=5):
    rng = (b["high"] - b["low"]).replace(0.0, np.nan)
    lower = (b[["open", "close"]].min(axis=1) - b["low"]) / rng
    upper = (b["high"] - b[["open", "close"]].max(axis=1)) / rng
    at_low = b["low"] <= b["low"].rolling(lookback).min()
    at_high = b["high"] >= b["high"].rolling(lookback).max()
    setup = pd.Series(np.where((lower >= wick) & at_low, 1.0, np.where((upper >= wick) & at_high, -1.0, 0.0)),
                      index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


# ------------------------------------------------------------------ volume


def volume_spike(b, k=2.0, hold=5):
    v = b["volume"].replace(0.0, np.nan)
    rel = v / v.rolling(20, min_periods=10).median().shift(1)
    rng = (b["high"] - b["low"]).replace(0.0, np.nan)
    pos = (b["close"] - b["low"]) / rng
    setup = pd.Series(np.where((rel > k) & (pos > 0.75), 1.0, np.where((rel > k) & (pos < 0.25), -1.0, 0.0)),
                      index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


def volume_divergence(b, lookback=20, hold=5):
    v = b["volume"].replace(0.0, np.nan)
    weak = v < v.rolling(20, min_periods=10).median().shift(1)
    c = b["close"]
    new_high = c >= c.rolling(lookback).max()
    new_low = c <= c.rolling(lookback).min()
    setup = pd.Series(np.where(new_high & weak, -1.0, np.where(new_low & weak, 1.0, 0.0)), index=b.index)
    return StrategyOutput(target=hold_events(setup, hold))


# ------------------------------------------------------------------ statistical


def pair_weights(a: pd.DataFrame, b: pd.DataFrame, window=120, entry=2.0, exit=0.0) -> pd.DataFrame:
    """Two-leg spread on log prices with a rolling (causal) hedge ratio.

    The hedge ratio is estimated on the trailing window only. A full-sample cointegrating
    regression knows the future relationship between the legs — the most common leak in
    published pairs backtests.
    """
    la, lb = np.log(a["close"]), np.log(b["close"])
    df = pd.concat([la.rename("a"), lb.rename("b")], axis=1).dropna()
    cov = df["a"].rolling(window).cov(df["b"])
    var = df["b"].rolling(window).var()
    beta = (cov / var).clip(0.0, 3.0)
    spread = df["a"] - beta * df["b"]
    z = (spread - spread.rolling(window).mean()) / spread.rolling(window).std()
    t = _state_machine(z < -entry, z >= -exit, z > entry, z <= exit)
    gross = 1.0 + beta.abs()
    wa = (t / gross).fillna(0.0)
    wb = (-t * beta / gross).fillna(0.0)
    return pd.DataFrame({"A": wa, "B": wb})
