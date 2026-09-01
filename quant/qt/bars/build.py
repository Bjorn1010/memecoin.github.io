"""Bar construction from tick data.

Why not just use 1-minute candles? Because calendar time is not the clock the market
runs on. Information arrives in bursts: a minute at 03:00 UTC on a Sunday and a
minute during a CPI print are the same length and nothing alike. Sampling on a fixed
time grid therefore over-samples quiet periods and under-samples the moments that
carry the signal, and it leaves returns strongly non-normal and heteroskedastic.

Sampling on *activity* instead — a bar every N ticks, N units of volume, or N dollars
traded — fixes most of that: dollar bars in particular have returns much closer to
IID normal, which is the assumption every downstream statistical test quietly makes.

All builders here are strictly causal: a bar closes on the tick that crosses the
threshold, and it is stamped with that tick's timestamp. No bar can contain
information from after its own stamp.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from ..data import schemas

BAR_COLUMNS = [
    "ts",  # close timestamp (ms) — the instant the bar's information is complete
    "start_ts",
    "open",
    "high",
    "low",
    "close",
    "vwap",
    "volume",
    "quote_volume",
    "trades",
    "buy_volume",  # base volume where the aggressor was a buyer
    "sell_volume",
]

BarKind = Literal["tick", "volume", "dollar", "time"]


def _empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in BAR_COLUMNS})


def _aggregate(
    ts: np.ndarray,
    price: np.ndarray,
    qty: np.ndarray,
    buy: np.ndarray,
    edges: np.ndarray,
) -> pd.DataFrame:
    """Aggregate ticks into bars given the index at which each bar ends (exclusive)."""
    if edges.size == 0:
        return _empty()

    starts = np.concatenate([[0], edges[:-1]])
    notional = price * qty
    cum_notional = np.concatenate([[0.0], np.cumsum(notional)])
    cum_qty = np.concatenate([[0.0], np.cumsum(qty)])
    cum_buy = np.concatenate([[0.0], np.cumsum(np.where(buy, qty, 0.0))])

    highs = np.empty(edges.size)
    lows = np.empty(edges.size)
    for i, (a, b) in enumerate(zip(starts, edges)):
        seg = price[a:b]
        highs[i] = seg.max()
        lows[i] = seg.min()

    vol = cum_qty[edges] - cum_qty[starts]
    quote = cum_notional[edges] - cum_notional[starts]
    buy_vol = cum_buy[edges] - cum_buy[starts]

    out = pd.DataFrame(
        {
            "ts": ts[edges - 1],
            "start_ts": ts[starts],
            "open": price[starts],
            "high": highs,
            "low": lows,
            "close": price[edges - 1],
            "vwap": np.divide(quote, vol, out=np.full(edges.size, np.nan), where=vol > 0),
            "volume": vol,
            "quote_volume": quote,
            "trades": (edges - starts).astype("float64"),
            "buy_volume": buy_vol,
            "sell_volume": vol - buy_vol,
        }
    )
    out["ts"] = out["ts"].astype("int64")
    out["start_ts"] = out["start_ts"].astype("int64")
    return out


def _threshold_edges(values: np.ndarray, threshold: float) -> np.ndarray:
    """Indices (exclusive ends) where the running sum of `values` crosses `threshold`.

    Implemented as a scan rather than vectorised arithmetic on the cumulative sum,
    because the counter must reset at every bar close — otherwise a single huge tick
    would silently swallow several bars' worth of threshold.
    """
    edges: list[int] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if running >= threshold:
            edges.append(i + 1)
            running = 0.0
    return np.asarray(edges, dtype="int64")


def build_bars(
    trades: pd.DataFrame,
    kind: BarKind = "dollar",
    threshold: float | None = None,
    target_bars_per_day: float | None = None,
) -> pd.DataFrame:
    """Turn a canonical trades frame into bars.

    `trades` needs columns ts, price, qty, is_buyer_maker (Binance convention:
    is_buyer_maker=True means the aggressor was a seller).

    Either give an explicit `threshold`, or give `target_bars_per_day` and let the
    threshold be calibrated from the sample so the bar count is comparable across
    instruments of wildly different notional — which is what makes cross-sectional
    features meaningful.
    """
    if trades is None or trades.empty:
        return _empty()

    df = trades.sort_values("ts", kind="mergesort")
    ts = df["ts"].to_numpy(dtype="int64")
    price = df["price"].to_numpy(dtype="float64")
    qty = df["qty"].to_numpy(dtype="float64")
    buy = ~df["is_buyer_maker"].to_numpy(dtype="bool")  # aggressor was the buyer

    if kind == "time":
        if threshold is None:
            raise ValueError("time bars need `threshold` in milliseconds")
        bucket = (ts // int(threshold)).astype("int64")
        change = np.flatnonzero(np.diff(bucket)) + 1
        edges = np.concatenate([change, [ts.size]])
        return _aggregate(ts, price, qty, buy, edges)

    if kind == "tick":
        driver = np.ones_like(qty)
    elif kind == "volume":
        driver = qty
    elif kind == "dollar":
        driver = price * qty
    else:
        raise ValueError(f"unknown bar kind {kind!r}")

    if threshold is None:
        threshold = calibrate_threshold(ts, driver, target_bars_per_day or 96.0)

    edges = _threshold_edges(driver, float(threshold))
    if edges.size == 0 or edges[-1] != ts.size:
        # Drop the trailing partial bar: it is not yet a complete observation and
        # including it is a subtle look-ahead (its close is not a real close).
        pass
    return _aggregate(ts, price, qty, buy, edges)


def calibrate_threshold(ts: np.ndarray, driver: np.ndarray, target_bars_per_day: float) -> float:
    """Pick a threshold that yields roughly `target_bars_per_day` bars over the sample."""
    if ts.size == 0:
        return 1.0
    span_days = max((ts[-1] - ts[0]) / 86_400_000.0, 1e-9)
    total = float(driver.sum())
    n_bars = max(target_bars_per_day * span_days, 1.0)
    return max(total / n_bars, 1e-12)


def bars_from_klines(klines: pd.DataFrame, rule: str = "4h") -> pd.DataFrame:
    """Downsample canonical klines to a coarser time grid.

    Kept for the cases where only OHLCV exists (macro EOD, venues without tick
    archives). Note `taker_buy_base` survives the resample, so signed flow is
    preserved when the source provides it.
    """
    if klines is None or klines.empty:
        return _empty()
    df = klines.copy()
    df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
    # label/closed on the right so each bar is stamped at its close, never its open.
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "quote_volume": "sum",
        "trades": "sum",
    }
    # Signed flow must survive the resample, otherwise every microstructure feature
    # silently goes NaN on downsampled bars. Accept either the archive's column name
    # or the bar frame's, so this works on klines and on already-built bars alike.
    flow_col = None
    for candidate in ("taker_buy_base", "buy_volume"):
        if candidate in df.columns and df[candidate].notna().any():
            agg[candidate] = "sum"
            flow_col = candidate
            break
    res = df.resample(rule, label="right", closed="right").agg(agg).dropna(subset=["close"])
    ts_ms = schemas.epoch_ms(res.index).to_numpy()
    out = pd.DataFrame(
        {
            "ts": ts_ms,
            "start_ts": ts_ms - _rule_ms(rule),
            "open": res["open"].to_numpy(),
            "high": res["high"].to_numpy(),
            "low": res["low"].to_numpy(),
            "close": res["close"].to_numpy(),
            "vwap": np.divide(
                res["quote_volume"].to_numpy(),
                res["volume"].to_numpy(),
                out=res["close"].to_numpy().astype("float64").copy(),
                where=res["volume"].to_numpy() > 0,
            ),
            "volume": res["volume"].to_numpy(),
            "quote_volume": res["quote_volume"].to_numpy(),
            "trades": res["trades"].to_numpy(),
        }
    )
    if flow_col is not None and flow_col in res.columns:
        out["buy_volume"] = res[flow_col].to_numpy()
        out["sell_volume"] = out["volume"] - out["buy_volume"]
    else:
        out["buy_volume"] = np.nan
        out["sell_volume"] = np.nan
    return out.reset_index(drop=True)


def klines_to_bars(klines: pd.DataFrame) -> pd.DataFrame:
    """Reinterpret canonical klines as bars without changing their frequency."""
    if klines is None or klines.empty:
        return _empty()
    df = klines
    volume = df["volume"].to_numpy(dtype="float64")
    quote = df["quote_volume"].to_numpy(dtype="float64")
    buy = df["taker_buy_base"].to_numpy(dtype="float64")
    out = pd.DataFrame(
        {
            "ts": df["ts"].to_numpy(dtype="int64"),
            "start_ts": df["ts"].to_numpy(dtype="int64"),
            "open": df["open"].to_numpy(dtype="float64"),
            "high": df["high"].to_numpy(dtype="float64"),
            "low": df["low"].to_numpy(dtype="float64"),
            "close": df["close"].to_numpy(dtype="float64"),
            "vwap": np.divide(
                quote, volume, out=df["close"].to_numpy(dtype="float64").copy(), where=volume > 0
            ),
            "volume": volume,
            "quote_volume": quote,
            "trades": df["trades"].to_numpy(dtype="float64"),
            "buy_volume": buy,
            "sell_volume": volume - buy,
        }
    )
    gap = out["ts"].diff().median()
    out["start_ts"] = out["ts"] - (int(gap) if pd.notna(gap) else 0)
    return out


def _rule_ms(rule: str) -> int:
    return int(pd.Timedelta(rule).value // 10**6)
