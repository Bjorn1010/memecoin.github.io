"""Day trading: discrete entries and exits, with stops and a hard cap on frequency.

Everything else in this codebase produces a continuous weight — a view that drifts from
0.03 to 0.05 and is rebalanced on a schedule. Day trading is a different object. It opens
a position, sets a level at which it is wrong, sets a level at which it is done, and
closes. Modelling it as a drifting weight hides exactly the thing that matters: how often
you cross the spread.

## The arithmetic that governs this file

A round trip on Binance spot at retail rates is 5bps taker each way plus roughly a
basis point of half-spread each way — **12bps, every time**. That number does not fall
when you trade more often, so the annual cost of a frequency is fixed before any signal
is written:

    1 trade every 2 days     182 a year       21.9% of capital, annually
    1 a day                  365              43.8%
    3 a day                1 095             131.4%
    10 a day               3 650             438.0%

Against that, hourly BTC has a 68bps standard deviation and a 25bps median absolute
move. The cost is 0.18 of an hourly sigma — about half the typical hourly move. That is
demanding but not absurd, and it is why crypto is one of the few venues where retail
intraday is not dead on arrival; on equities the spread is a far larger share of the
intraday range.

The binding consequence: **frequency is a risk limit, not a preference.** `max_trades_
per_day` defaults to 3 and exists so a signal that fires constantly cannot quietly turn
into a 400%-a-year cost. A strategy is free to want more trades; it does not get them.

## Why stops, and why a time stop especially

A day trade without an exit rule is a position trade that has not admitted it yet. Three
exits, and the third is the one people omit:

* **Stop loss**, in volatility units rather than percent — a 1% stop is a scratch on
  DOGE and a catastrophe on a stablecoin pair. Sized as a multiple of recent realised
  volatility, it means the same thing on every instrument.
* **Take profit**, likewise in volatility units, set wider than the stop. A rule with a
  tighter target than stop needs a hit rate above 50% just to break even, and short-horizon
  signals do not have one.
* **Time stop.** If the move has not happened within `max_hold_bars`, the reason for the
  trade has expired whether or not the price has moved. Without it, a losing intraday
  trade silently becomes an overnight position, and the risk profile the backtest measured
  is not the one being run.

## What this does not do

It does not predict. The signals here are the documented short-horizon effects — reversal
after an outsized move, order-flow imbalance, volatility breakout — combined and then
filtered hard. Whether the combination survives 12bps a round trip is a measurement, and
`scripts/research_intraday.py` performs it rather than assuming it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class IntradaySpec:
    """A day-trading rule set. Every default is a risk limit rather than a tuned value."""

    # --- entry
    entry_threshold: float = 1.0      # signal units required to open
    vol_window: int = 48              # bars for the volatility estimate (2 days hourly)
    reversal_window: int = 6          # lookback for the short-term reversal leg
    breakout_window: int = 24         # lookback for the volatility-breakout leg
    flow_window: int = 12             # lookback for order-flow imbalance

    # --- exits, all in units of recent volatility so they mean the same on every symbol
    stop_atr: float = 1.5
    target_atr: float = 3.0           # wider than the stop: a 1:1 rule needs >50% hit rate
    max_hold_bars: int = 12           # a day trade does not become an overnight position

    # --- frequency, which is a cost limit and therefore a risk limit
    max_trades_per_day: int = 3
    cooldown_bars: int = 2            # bars to wait after an exit before re-entering

    # --- sizing
    risk_per_trade: float = 0.01      # fraction of equity risked between entry and stop
    max_weight: float = 0.5
    allow_short: bool = True

    bars_per_day: int = 24            # 24 for hourly crypto; 7 for hourly US equities

    def to_meta(self) -> dict:
        return {
            "entry_threshold": self.entry_threshold, "stop_atr": self.stop_atr,
            "target_atr": self.target_atr, "max_hold_bars": self.max_hold_bars,
            "max_trades_per_day": self.max_trades_per_day,
            "cooldown_bars": self.cooldown_bars, "risk_per_trade": self.risk_per_trade,
            "max_weight": self.max_weight, "allow_short": self.allow_short,
        }


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=max(window // 3, 3)).mean()
    std = series.rolling(window, min_periods=max(window // 3, 3)).std(ddof=0)
    return (series - mean) / std.replace(0.0, np.nan)


def entry_signal(bars: pd.DataFrame, spec: IntradaySpec | None = None) -> pd.DataFrame:
    """Three short-horizon legs, each causal, returned separately and combined.

    Kept separate so the combination can be inspected: a combined signal that works only
    because one leg dominates is a one-leg strategy carrying two decorations, and the
    only way to see that is to look at them apart.
    """
    spec = spec or IntradaySpec()
    close = bars["close"].astype("float64")
    returns = np.log(close).diff()

    out = pd.DataFrame(index=bars.index)

    # 1. Short-term reversal. The best-documented intraday effect in crypto: an outsized
    #    move over a few hours is partly liquidity absorption and partly information, and
    #    the liquidity part comes back. Sign inverted — this is a fade.
    move = np.log(close).diff(spec.reversal_window)
    out["reversal"] = -_zscore(move, spec.vol_window * 2)

    # 2. Volatility breakout, the opposite bet, on a longer window. Held together with
    #    reversal deliberately: they disagree by construction, and which one is right
    #    depends on whether the move carried information. The combination is a filter —
    #    a trade is taken only when the two do not cancel.
    high = bars["high"].astype("float64").rolling(spec.breakout_window).max()
    low = bars["low"].astype("float64").rolling(spec.breakout_window).min()
    span = (high - low).replace(0.0, np.nan)
    out["breakout"] = ((close - (high + low) / 2) / (span / 2)).clip(-2, 2)

    # 3. Order-flow imbalance. Binance publishes the taker-buy split, which is the only
    #    genuinely microstructural input available for free: it says who was the
    #    aggressor, not merely where the price ended.
    if "buy_volume" in bars.columns and "volume" in bars.columns:
        volume = bars["volume"].astype("float64").replace(0.0, np.nan)
        imbalance = (2.0 * bars["buy_volume"].astype("float64") / volume) - 1.0
        out["flow"] = _zscore(imbalance.rolling(spec.flow_window, min_periods=4).mean(),
                              spec.vol_window * 2)
    else:
        out["flow"] = np.nan

    legs = [c for c in ("reversal", "breakout", "flow") if out[c].notna().any()]
    out["combined"] = out[legs].mean(axis=1)
    # Realised volatility per bar, used for both position sizing and the stop distance.
    out["vol"] = returns.rolling(spec.vol_window, min_periods=spec.vol_window // 2).std(ddof=0)
    return out


@dataclass
class Trade:
    """One completed round trip, with the reason it ended."""

    symbol: str
    direction: int          # +1 long, -1 short
    entry_ts: pd.Timestamp
    entry_price: float
    exit_ts: pd.Timestamp
    exit_price: float
    bars_held: int
    exit_reason: str        # stop | target | time | end_of_sample
    weight: float
    gross_return: float
    net_return: float


@dataclass
class IntradayResult:
    trades: pd.DataFrame
    weights: pd.Series
    signal: pd.DataFrame
    spec: IntradaySpec
    diagnostics: dict = field(default_factory=dict)


def run_intraday(
    bars: pd.DataFrame,
    spec: IntradaySpec | None = None,
    *,
    symbol: str = "",
    round_trip_bps: float = 12.0,
) -> IntradayResult:
    """Walk the bars, opening and closing one position at a time.

    A single position at a time, on purpose. Stacking entries turns a rule with a known
    stop distance into a book with an unknown one, and the risk-per-trade budget stops
    meaning anything.

    Execution is at the *next* bar's open, never at the close that produced the signal —
    the same one-bar lag the rest of the system uses, and the same one whose absence was
    worth a full point of annual return when it was found in the daily path.
    """
    spec = spec or IntradaySpec()
    signal = entry_signal(bars, spec)

    opens = bars["open"].astype("float64").to_numpy()
    highs = bars["high"].astype("float64").to_numpy()
    lows = bars["low"].astype("float64").to_numpy()
    closes = bars["close"].astype("float64").to_numpy()
    index = bars.index

    combined = signal["combined"].to_numpy()
    vol = signal["vol"].to_numpy()

    weights = np.zeros(len(bars))
    trades: list[Trade] = []

    position = 0            # 0 flat, +1 long, -1 short
    entry_i = -1
    entry_price = stop_price = target_price = weight = 0.0
    cooldown_until = 0
    day_of: np.ndarray = np.asarray([d.date() for d in index])
    trades_today: dict = {}

    cost_per_side = round_trip_bps / 2.0 / 1e4

    for i in range(1, len(bars) - 1):
        # ---------------------------------------------------------- manage a position
        if position != 0:
            hit_stop = (lows[i] <= stop_price) if position > 0 else (highs[i] >= stop_price)
            hit_target = (highs[i] >= target_price) if position > 0 else (lows[i] <= target_price)
            timed_out = (i - entry_i) >= spec.max_hold_bars

            reason, exit_price = "", 0.0
            if hit_stop:
                # When a bar touches both, assume the stop: the pessimistic reading is
                # the only honest one without tick data, and the optimistic reading is
                # how intraday backtests manufacture their edge.
                reason, exit_price = "stop", stop_price
            elif hit_target:
                reason, exit_price = "target", target_price
            elif timed_out:
                reason, exit_price = "time", closes[i]

            if reason:
                gross = position * (exit_price / entry_price - 1.0)
                net = gross - 2 * cost_per_side
                trades.append(Trade(
                    symbol=symbol, direction=position, entry_ts=index[entry_i],
                    entry_price=entry_price, exit_ts=index[i], exit_price=exit_price,
                    bars_held=i - entry_i, exit_reason=reason, weight=weight,
                    gross_return=gross * weight, net_return=net * weight,
                ))
                position = 0
                cooldown_until = i + spec.cooldown_bars
                weights[i] = 0.0
                continue

            weights[i] = position * weight
            continue

        # ------------------------------------------------------------- consider entry
        if i < cooldown_until or not np.isfinite(combined[i]) or not np.isfinite(vol[i]):
            continue
        if vol[i] <= 0:
            continue

        today = day_of[i]
        if trades_today.get(today, 0) >= spec.max_trades_per_day:
            continue  # frequency is a cost limit, and it binds

        strength = combined[i]
        if abs(strength) < spec.entry_threshold:
            continue
        direction = 1 if strength > 0 else -1
        if direction < 0 and not spec.allow_short:
            continue

        # Enter at the next bar's open. Never at this bar's close.
        entry_i = i + 1
        entry_price = opens[entry_i]
        if not np.isfinite(entry_price) or entry_price <= 0:
            continue

        stop_distance = spec.stop_atr * vol[i]
        target_distance = spec.target_atr * vol[i]
        stop_price = entry_price * (1 - direction * stop_distance)
        target_price = entry_price * (1 + direction * target_distance)

        # Size so that the move from entry to stop costs `risk_per_trade` of equity.
        weight = min(spec.risk_per_trade / max(stop_distance, 1e-9), spec.max_weight)

        position = direction
        trades_today[today] = trades_today.get(today, 0) + 1
        weights[entry_i] = position * weight

    # An empty result keeps the full column set. A bare `pd.DataFrame([])` has no
    # columns at all, so a caller reading `result.trades["exit_reason"]` gets a KeyError
    # on the one path they are least likely to have tested — the day the strategy takes
    # no trades. Shape-compatibility on the empty case is the same rule
    # `schemas.normalise` applies to a dataset from a poorer venue.
    columns = list(Trade.__dataclass_fields__)
    frame = (pd.DataFrame([t.__dict__ for t in trades]) if trades
             else pd.DataFrame(columns=columns))
    weight_series = pd.Series(weights, index=index, name="weight")

    diagnostics = _diagnose(frame, weight_series, spec, len(bars))
    return IntradayResult(frame, weight_series, signal, spec, diagnostics)


def _diagnose(trades: pd.DataFrame, weights: pd.Series, spec: IntradaySpec,
              n_bars: int) -> dict:
    """The numbers that say whether this is a strategy or a fee generator."""
    days = max(n_bars / spec.bars_per_day, 1e-9)
    if trades.empty:
        return {"trades": 0, "note": "aucune entrée déclenchée — seuil trop haut, ou pas de signal"}

    net = trades["net_return"]
    gross = trades["gross_return"]
    wins = net > 0
    cost_total = float((gross - net).sum())

    return {
        "trades": int(len(trades)),
        "trades_per_day": round(len(trades) / days, 3),
        "hit_rate": round(float(wins.mean()), 4),
        "avg_bars_held": round(float(trades["bars_held"].mean()), 2),
        "gross_total": round(float(gross.sum()), 4),
        "net_total": round(float(net.sum()), 4),
        "cost_total": round(cost_total, 4),
        # The number that decides everything: if costs exceed the gross edge, no amount
        # of signal work helps — the frequency has to come down.
        "cost_share_of_gross": (round(cost_total / abs(float(gross.sum())), 4)
                                if gross.sum() != 0 else None),
        "avg_win": round(float(net[wins].mean()), 5) if wins.any() else 0.0,
        "avg_loss": round(float(net[~wins].mean()), 5) if (~wins).any() else 0.0,
        "exit_reasons": trades["exit_reason"].value_counts().to_dict(),
        "time_in_market": round(float((weights != 0).mean()), 4),
        "pct_long": round(float((trades["direction"] > 0).mean()), 4),
    }


def equity_curve(result: IntradayResult, starting_equity: float = 100_000.0) -> pd.Series:
    """Compound the net trade returns into a curve stamped at each exit."""
    if result.trades.empty:
        return pd.Series([starting_equity], index=[result.weights.index[0]], name="equity")
    curve = starting_equity * (1.0 + result.trades["net_return"]).cumprod()
    curve.index = pd.DatetimeIndex(result.trades["exit_ts"])
    curve.name = "equity"
    return pd.concat([pd.Series([starting_equity], index=[result.weights.index[0]]), curve])


def performance(result: IntradayResult, starting_equity: float = 100_000.0) -> dict:
    """Annualised numbers from the trade record, and the drawdown that paid for them."""
    if result.trades.empty:
        return {"trades": 0, "note": "aucun trade"}

    curve = equity_curve(result, starting_equity)
    span = (curve.index[-1] - curve.index[0]).total_seconds() / (365.25 * 24 * 3600)
    total = float(curve.iloc[-1] / curve.iloc[0] - 1.0)
    cagr = (1 + total) ** (1 / span) - 1 if span > 0 and total > -1 else float("nan")

    net = result.trades["net_return"]
    # Per-trade Sharpe scaled by the realised trade frequency, which is the right
    # annualisation for a strategy whose "period" is a trade rather than a bar.
    trades_per_year = len(net) / span if span > 0 else 0.0
    sharpe = (float(net.mean() / net.std(ddof=1)) * np.sqrt(trades_per_year)
              if net.std(ddof=1) > 0 else float("nan"))

    peak = curve.cummax()
    drawdown = float((curve / peak - 1.0).min())

    return {
        "trades": int(len(net)),
        "total_return": round(total, 4),
        "cagr": round(cagr, 4) if np.isfinite(cagr) else None,
        "sharpe": round(sharpe, 3) if np.isfinite(sharpe) else None,
        "max_drawdown": round(drawdown, 4),
        "years": round(span, 2),
        **result.diagnostics,
    }
