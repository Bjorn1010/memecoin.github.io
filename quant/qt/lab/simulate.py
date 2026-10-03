"""Trade-level simulator for retail-style strategies on daily bars.

`qt.backtest.engine` works in portfolio weights, which is right for allocators and
wrong for the strategies a retail trader runs: those are trades — an entry, a stop, a
target, a time limit, a stop order placed above yesterday's high. This simulator models
exactly that, with the conventions chosen to err against the strategy:

* A decision made on bar t's close is executed at bar t+1's open. Never at t's close.
* A stop-entry order placed for bar t+1 fills at its level, or at the open if the
  market gapped through it (a gap gives you a worse price, never a better one).
* A protective stop fills at its level, or at the open on a gap; its slippage is
  multiplied (a stop is a market order fired into a moving market).
* If a bar touches both the stop and the target, the stop is assumed hit first. Daily
  bars do not say which came first, and assuming the favourable order is a classic way
  to manufacture a profitable backtest from a losing strategy.
* After a stop, target or time exit the strategy may not re-enter on the same signal;
  the signal has to change first. Otherwise a stopped trend trade re-enters the next
  morning and the stop is decorative.
* Costs per side (commission + half-spread + slippage) on every fill, and carry (swap,
  CFD financing, funding, borrow) on every bar a position is open.

Positions are expressed as a fraction of equity fixed at entry, so the per-bar return
series composes into an equity curve and instruments of different volatility can be
put on equal footing before they are averaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .markets import CostProfile


@dataclass
class StrategyOutput:
    """What a strategy asks for. Every series is stamped at the bar that produced it."""

    target: pd.Series | None = None  # desired side after next open: -1, 0, +1
    # Stop-entry orders for the NEXT bar, as a distance from that bar's open (so an
    # order like "open + 0.5 x yesterday's range" is expressible without peeking at the
    # open) or as an absolute level.
    long_entry_offset: pd.Series | None = None
    short_entry_offset: pd.Series | None = None
    long_entry_level: pd.Series | None = None
    short_entry_level: pd.Series | None = None
    stop_atr: float | None = None
    target_atr: float | None = None
    max_hold: int | None = None  # bars; time exit at that bar's close
    exit_same_bar_close: bool = False  # day trade: out at the close of the entry bar


@dataclass
class SimResult:
    returns: pd.Series  # per-bar net return on equity
    worst_intrabar: pd.Series  # per-bar return at the bar's most adverse price
    position: pd.Series  # signed size held at each close
    trades: pd.DataFrame
    gross_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))


def wilder_atr(bars: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = bars["close"].shift(1)
    tr = pd.concat([bars["high"] - bars["low"], (bars["high"] - prev).abs(), (bars["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def vol_target_size(bars: pd.DataFrame, *, target_vol: float, lookback: int, periods_per_year: int,
                    max_leverage: float) -> pd.Series:
    """Causal position size so each instrument runs at `target_vol` annualised."""
    r = np.log(bars["close"]).diff()
    vol = r.rolling(lookback, min_periods=max(lookback // 2, 10)).std() * np.sqrt(periods_per_year)
    return (target_vol / vol).clip(upper=max_leverage).replace([np.inf, -np.inf], np.nan)


def _arr(s: pd.Series | None, index: pd.Index, fill=np.nan) -> np.ndarray | None:
    if s is None:
        return None
    return s.reindex(index).astype("float64").fillna(fill).to_numpy()


def simulate(
    bars: pd.DataFrame,
    out: StrategyOutput,
    costs: CostProfile,
    *,
    size: pd.Series | float = 1.0,
    periods_per_year: int = 252,
    entry_delay: int = 0,
    exit_delay: int = 0,
    atr_period: int = 14,
) -> SimResult:
    index = bars.index
    n = len(index)
    o = bars["open"].to_numpy(dtype="float64")
    h = bars["high"].to_numpy(dtype="float64")
    lo = bars["low"].to_numpy(dtype="float64")
    c = bars["close"].to_numpy(dtype="float64")
    atr = wilder_atr(bars, atr_period).to_numpy()
    sz = (np.full(n, float(size)) if np.isscalar(size) else _arr(size, index, np.nan))

    tgt = _arr(out.target, index, 0.0) if out.target is not None else np.zeros(n)
    l_off = _arr(out.long_entry_offset, index)
    s_off = _arr(out.short_entry_offset, index)
    l_lvl = _arr(out.long_entry_level, index)
    s_lvl = _arr(out.short_entry_level, index)
    has_stop_entries = any(x is not None for x in (l_off, s_off, l_lvl, s_lvl))

    side_bps = costs.per_side_bps / 1e4
    stop_bps = (costs.commission_bps + costs.half_spread_bps
                + costs.slippage_bps * costs.stop_slippage_multiplier) / 1e4
    carry_long = costs.holding_long_annual / periods_per_year
    carry_short = costs.holding_short_annual / periods_per_year

    rets = np.zeros(n)
    gross = np.zeros(n)
    worst = np.zeros(n)
    pos_hist = np.zeros(n)
    trades: list[dict] = []

    side = 0  # +1 / -1 / 0
    mag = 0.0  # |size| fixed at entry
    mark = 0.0  # last price the open position was marked at
    entry_px = 0.0
    entry_i = -1
    stop_px = np.nan
    take_px = np.nan
    blocked = 0  # side that may not be re-entered until the signal changes
    trade_cost = 0.0

    def close_trade(i: int, px: float, reason: str, cost_rate: float) -> float:
        nonlocal side, mag, trade_cost, blocked
        pnl = side * mag * (px / mark - 1.0)
        cost = mag * cost_rate
        gross_ret = side * mag * (px / entry_px - 1.0)
        trades.append({
            "entry_ts": index[entry_i], "exit_ts": index[i], "side": side, "size": mag,
            "entry_px": entry_px, "exit_px": px, "bars": i - entry_i,
            "gross": gross_ret, "cost": trade_cost + cost, "net": gross_ret - trade_cost - cost,
            "reason": reason,
        })
        if reason in ("stop", "target", "time", "day"):
            blocked = side
        side, mag, trade_cost = 0, 0.0, 0.0
        return pnl - cost

    def open_trade(i: int, px: float, new_side: int, size_val: float, cost_rate: float) -> float:
        nonlocal side, mag, mark, entry_px, entry_i, stop_px, take_px, trade_cost
        side, mag, mark, entry_px, entry_i = new_side, size_val, px, px, i
        a = atr[i - 1] if i >= 1 else np.nan
        stop_px = px - new_side * out.stop_atr * a if out.stop_atr and np.isfinite(a) else np.nan
        take_px = px + new_side * out.target_atr * a if out.target_atr and np.isfinite(a) else np.nan
        trade_cost = size_val * cost_rate
        return -size_val * cost_rate

    for i in range(1, n):
        r = 0.0
        g = 0.0
        # 1. Overnight gap on the position carried from yesterday.
        if side:
            move = side * mag * (o[i] / mark - 1.0)
            r += move
            g += move
            mark = o[i]
            # 2. Gap through the protective stop or the target: out at the open.
            if np.isfinite(stop_px) and side * (o[i] - stop_px) <= 0:
                r += close_trade(i, o[i], "stop", stop_bps)
            elif np.isfinite(take_px) and side * (o[i] - take_px) >= 0:
                r += close_trade(i, o[i], "target", side_bps)

        # 3. Market orders decided at earlier closes.
        j_in = i - 1 - entry_delay
        j_out = i - 1 - exit_delay
        want_in = int(np.sign(tgt[j_in])) if j_in >= 0 else 0
        want_out = int(np.sign(tgt[j_out])) if j_out >= 0 else 0
        if blocked and want_in != blocked:
            blocked = 0
        if side and out.target is not None and want_out != side:
            r += close_trade(i, o[i], "signal", side_bps)
        # A strategy with a protective stop may not enter before the stop can be
        # computed: a trade opened during the ATR warm-up would never get one.
        stop_ready = not out.stop_atr or np.isfinite(atr[i - 1])
        if not side and want_in and want_in != blocked and j_in >= 0 and stop_ready:
            s_val = sz[j_in]
            if np.isfinite(s_val) and s_val > 0:
                r += open_trade(i, o[i], want_in, float(s_val), side_bps)

        # 4. Stop-entry orders for this bar, placed at yesterday's close.
        if not side and has_stop_entries and j_in >= 0:
            lv_long = (o[i] + l_off[j_in]) if l_off is not None else (l_lvl[j_in] if l_lvl is not None else np.nan)
            lv_short = (o[i] - s_off[j_in]) if s_off is not None else (s_lvl[j_in] if s_lvl is not None else np.nan)
            hit_long = np.isfinite(lv_long) and h[i] >= lv_long
            hit_short = np.isfinite(lv_short) and lo[i] <= lv_short
            s_val = sz[j_in]
            if hit_long and hit_short:
                # Both stop orders touched in one bar. Which filled first is unknowable
                # from daily data — and skipping the day is NOT neutral: only at the
                # close do you learn both were hit, so skipping deletes exactly the
                # whipsaw days, after the fact. That look-ahead turned a daily breakout
                # on S&P futures into a Sharpe of 2.4. Assume the side that ends the
                # bar worse was the one filled.
                pnl_long = c[i] - max(o[i], lv_long)
                pnl_short = min(o[i], lv_short) - c[i]
                hit_long, hit_short = pnl_long <= pnl_short, pnl_long > pnl_short
            if (hit_long or hit_short) and np.isfinite(s_val) and s_val > 0 and stop_ready:
                new_side = 1 if hit_long else -1
                lv = lv_long if hit_long else lv_short
                px = max(o[i], lv) if hit_long else min(o[i], lv)
                if new_side != blocked:
                    r += open_trade(i, px, new_side, float(s_val), side_bps)

        # 5. Intrabar stop / target, stop first when both are touched.
        if side:
            adverse = lo[i] if side > 0 else h[i]
            worst[i] = r + side * mag * (adverse / mark - 1.0)
            stop_hit = np.isfinite(stop_px) and side * (adverse - stop_px) <= 0
            fav = h[i] if side > 0 else lo[i]
            take_hit = np.isfinite(take_px) and side * (fav - take_px) >= 0
            if stop_hit:
                # close_trade books the move from `mark` to the stop into r.
                g += side * mag * (stop_px / mark - 1.0)
                r += close_trade(i, stop_px, "stop", stop_bps)
            elif take_hit:
                px = take_px
                g += side * mag * (px / mark - 1.0)
                r += close_trade(i, px, "target", side_bps)

        # 6. Time exits at this bar's close.
        if side and (
            (out.exit_same_bar_close and entry_i == i)
            or (out.max_hold and i - entry_i >= out.max_hold)
        ):
            g += side * mag * (c[i] / mark - 1.0)
            r += close_trade(i, c[i], "day" if out.exit_same_bar_close else "time", side_bps)

        # 7. Mark the survivor at the close and charge carry.
        if side:
            move = side * mag * (c[i] / mark - 1.0)
            r += move
            g += move
            mark = c[i]
            r -= mag * (carry_long if side > 0 else carry_short)
        worst[i] = min(worst[i], r)
        rets[i] = r
        gross[i] = g
        pos_hist[i] = side * mag

    trades_df = pd.DataFrame(trades)
    return SimResult(
        returns=pd.Series(rets, index=index),
        worst_intrabar=pd.Series(worst, index=index),
        position=pd.Series(pos_hist, index=index),
        trades=trades_df,
        gross_returns=pd.Series(gross, index=index),
    )


def simulate_weights(
    bars: dict[str, pd.DataFrame],
    weights: pd.DataFrame,
    costs: CostProfile,
    *,
    periods_per_year: int = 252,
    entry_delay: int = 0,
) -> SimResult:
    """Portfolio strategies (cross-sectional momentum, pairs): weights decided at close
    t, traded at open t+1. Overnight gap earns yesterday's book, the session earns the
    new one."""
    symbols = [s for s in weights.columns if s in bars]
    idx = weights.index
    for s in symbols:
        idx = idx.union(bars[s].index)
    idx = idx.sort_values()
    o = pd.DataFrame({s: bars[s]["open"] for s in symbols}).reindex(idx)
    c = pd.DataFrame({s: bars[s]["close"] for s in symbols}).reindex(idx)
    # An instrument with no bar today cannot be traded today: carry its weight forward.
    w = weights[symbols].reindex(idx).ffill().fillna(0.0).shift(1 + entry_delay).fillna(0.0)
    tradable = c.notna() & o.notna()
    w = w.where(tradable).ffill().fillna(0.0)
    held = w.shift(1).fillna(0.0)
    prev_c = c.ffill().shift(1)
    gap = (o / prev_c - 1.0).where(tradable).fillna(0.0)
    session = (c / o - 1.0).where(tradable).fillna(0.0)
    gross = (held * gap).sum(axis=1) + (w * session).sum(axis=1)
    turnover = (w - held).abs().sum(axis=1)
    carry = (w.clip(lower=0).sum(axis=1) * costs.holding_long_annual
             + (-w.clip(upper=0)).sum(axis=1) * costs.holding_short_annual) / periods_per_year
    net = gross - turnover * costs.per_side_bps / 1e4 - carry

    # Each rebalance is recorded as one "trade" of the book, so trade statistics and the
    # Monte Carlo have something to resample.
    pos = np.flatnonzero((turnover > 1e-9).to_numpy())
    bounds = list(pos) + [len(idx)]
    trades = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg_net = net.iloc[a:b]
        trades.append({"entry_ts": idx[a], "exit_ts": idx[b - 1], "side": 0,
                       "size": float(w.iloc[a].abs().sum()), "bars": b - a,
                       "gross": float(gross.iloc[a:b].sum()),
                       "cost": float(turnover.iloc[a] * costs.per_side_bps / 1e4),
                       "net": float((1 + seg_net).prod() - 1), "reason": "rebalance"})
    return SimResult(returns=net, worst_intrabar=net.copy(), position=w.abs().sum(axis=1),
                     trades=pd.DataFrame(trades), gross_returns=gross)
