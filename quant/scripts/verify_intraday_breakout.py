"""Falsification test: do daily-bar breakout results survive the real intraday path?

The daily simulator cannot know whether a bar touched its long or its short stop
first, and resolves the ambiguity pessimistically. That still leaves a subtler gap:
on a daily bar, "the high reached the level" says nothing about how much of the day's
move happened before vs after the touch. Hourly bars resolve most of it.

For each UTC day this replays the same rule on Binance 1h klines:
    long stop  = day open + k × previous day's range
    short stop = day open − k × previous day's range
    the first hour that touches a level fills it (at the level, or at the hour's open
    on a gap); if one hour touches both, the losing side is assumed; exit at the
    day's close. Same costs as the research run.

and compares it with the daily-bar simulator on daily bars built from the same hours.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qt.data.sources.binance_vision import klines  # noqa: E402
from qt.lab.hypotheses import by_name  # noqa: E402
from qt.lab.markets import load_markets  # noqa: E402
from qt.lab.simulate import simulate  # noqa: E402


def hourly(symbol: str) -> pd.DataFrame:
    cache = ROOT / "data" / "lab" / f"binance_{symbol}_1h.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    k = klines(symbol, "1h", start="2017-08-17")
    k.index = pd.to_datetime(k["ts"], unit="ms", utc=True) - pd.Timedelta(hours=1)  # stamp at bar open
    k = k[["open", "high", "low", "close", "volume"]].astype("float64")
    cache.parent.mkdir(parents=True, exist_ok=True)
    k.to_parquet(cache)
    return k


def daily_from(h: pd.DataFrame) -> pd.DataFrame:
    d = h.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return d.dropna().assign(raw_close=lambda x: x["close"])


def intraday_replay(h: pd.DataFrame, d: pd.DataFrame, k: float, per_side_bps: float) -> pd.Series:
    rng_prev = (d["high"] - d["low"]).shift(1)
    out = {}
    for day, grp in h.groupby(h.index.floor("1D")):
        if day not in d.index or not np.isfinite(rng_prev.get(day, np.nan)) or len(grp) < 20:
            continue
        o = grp["open"].iloc[0]
        lv_l, lv_s = o + k * rng_prev[day], o - k * rng_prev[day]
        ret = 0.0
        for _, bar in grp.iterrows():
            hit_l, hit_s = bar["high"] >= lv_l, bar["low"] <= lv_s
            if not (hit_l or hit_s):
                continue
            close = grp["close"].iloc[-1]
            if hit_l and hit_s:
                pl = close / max(bar["open"], lv_l) - 1
                ps = 1 - close / min(bar["open"], lv_s)
                hit_l = pl <= ps
            if hit_l:
                ret = close / max(bar["open"], lv_l) - 1
            else:
                ret = 1 - close / min(bar["open"], lv_s)
            ret -= 2 * per_side_bps / 1e4
            break
        out[day] = ret
    return pd.Series(out)


def main() -> None:
    costs = load_markets()["crypto"].costs
    h = by_name("vol_breakout")
    for sym in ("BTCUSDT", "ETHUSDT"):
        hr = hourly(sym)
        d = daily_from(hr)
        for k in (0.3, 0.5, 0.7, 1.0):
            daily_r = simulate(d, h.func(d, k=k), costs, size=1.0, periods_per_year=365).returns
            intra_r = intraday_replay(hr, d, k, costs.per_side_bps)
            sh = lambda r: r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else float("nan")  # noqa: E731
            print(f"{sym} k={k}: Sharpe barres journalières {sh(daily_r):+.2f} | rejoué en horaire {sh(intra_r):+.2f}"
                  f" | jours tradés {int((intra_r != 0).sum())}", flush=True)


if __name__ == "__main__":
    main()
