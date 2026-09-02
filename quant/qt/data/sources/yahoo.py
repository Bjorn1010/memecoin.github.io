"""Yahoo Finance daily bars — equities, ETFs, indices, FX and futures proxies.

This is the source that gets the system off crypto. It costs nothing, needs no key, and
reaches back decades: QQQ from March 1999, SPY from 1993, GLD from 2004. That depth is
the point. Ten crypto pairs since 2021 carry 1.02 effective bets and one regime; a
multi-asset book reaching back to 1999 has seen the dot-com bust, 2008, the 2013 taper
tantrum, 2020, and the 2022 rates shock — genuinely different worlds, which is the only
way to learn whether a strategy generalises or was fitted.

**Dividends and splits — the part that quietly ruins equity backtests.**

Yahoo returns two price streams. `close` is what actually printed. `adjclose` is that
series restated backwards for every split and dividend since. They are not
interchangeable, and picking the wrong one fails in opposite directions:

* Use raw `close` for returns and a dividend looks like a loss. TLT pays roughly 4% a
  year in monthly instalments; a long-TLT strategy measured on raw closes gives up 4
  points of annual return that the holder actually received. On a 20-year backtest that
  is not a rounding error, it inverts the conclusion.
* Use `adjclose` as the price you traded at and you have look-ahead. Today's adjusted
  series for 2005 depends on every dividend paid between 2005 and now — information
  nobody had in 2005. It is harmless for returns (the ratio is right) and wrong for
  anything level-dependent: position sizing in dollars, a price threshold, notional
  turnover, an impact model calibrated on price.

So this module stores **both**, plus the ratio between them. Downstream:

    returns   <- adj_close      (total return, dividend-correct)
    execution <- close          (the price that existed on the day)

`qt.bars.klines_to_bars` reads `close`, so a backtest is priced on real prints by
default; the total-return series is there under `adj_close` for the return calculation.
Getting this backwards is invisible — both produce a plausible equity curve.

**Survivorship.** Yahoo serves what exists today. A universe picked from today's index
membership and backtested to 1999 has quietly excluded every company that failed, which
is worth several points of annual return in a naive equity backtest. That is why the
default universe here is ETFs and not single names: an index ETF carries its own
survivorship internally and honestly, because the index rebalanced in real time. Single
tickers are supported, and `UNIVERSES` deliberately does not ship an S&P 500 constituent
list, because a point-in-time membership history is not available for free.
"""

from __future__ import annotations

import json

import pandas as pd

from .. import schemas
from ..http import get_text

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
VENUE = "yahoo"

# A diversified multi-asset book, in the shape a managed-futures desk actually runs:
# five asset classes whose correlations genuinely differ, rather than ten instruments
# that are all one bet on the same factor.
UNIVERSES: dict[str, tuple[str, ...]] = {
    # Liquid ETF proxies for the futures a CTA trades. Costs are higher than the
    # underlying futures and there is no embedded leverage, but the cross-asset
    # correlation structure is the real one.
    "multi_asset": (
        "QQQ",   # Nasdaq 100 — the tech beta
        "SPY",   # S&P 500
        "IWM",   # US small cap
        "EFA",   # developed markets ex-US
        "EEM",   # emerging markets
        "TLT",   # 20y+ Treasuries — the duration leg
        "IEF",   # 7-10y Treasuries
        "LQD",   # investment-grade credit
        "HYG",   # high yield — credit risk premium
        "GLD",   # gold
        "SLV",   # silver
        "USO",   # WTI crude
        "DBC",   # broad commodity basket
        "UUP",   # US dollar index
        "VNQ",   # US real estate
    ),
    # Equity sectors, for cross-sectional work where a market-neutral book is the point.
    "sectors": (
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
    ),
    # The headline indices on their own.
    "indices": ("QQQ", "SPY", "DIA", "IWM"),
}


def daily(symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Fetch the full daily history for one symbol.

    Requests the widest possible window by epoch rather than `range=max`: the range
    parameter is honoured inconsistently and silently returns a short window for some
    tickers (AAPL came back with 168 bars instead of forty years). Asking by explicit
    period is the form that behaves.
    """
    text = get_text(
        CHART.format(symbol=symbol),
        params={"period1": 0, "period2": 4_102_444_800, "interval": "1d"},
        min_gap=0.4,
    )
    if not text:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    try:
        result = json.loads(text)["chart"]["result"][0]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    if not stamps or "close" not in quote:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    # Yahoo timestamps mark the session open in exchange-local time; normalising to the
    # UTC date keeps a daily bar on one calendar day rather than drifting with DST.
    index = pd.to_datetime(pd.Series(stamps), unit="s", utc=True).dt.normalize()

    adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
    frame = pd.DataFrame({
        "ts": schemas.epoch_ms(index),
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("close"),
        "volume": quote.get("volume"),
    })
    # The adjusted series rides alongside rather than replacing the raw one; see the
    # module docstring for why substituting it is a look-ahead bug.
    frame["adj_close"] = adj if adj is not None else frame["close"]

    # Yahoo emits nulls for halted sessions. Dropping is right — forward-filling would
    # invent a print and flatten a real gap, which is exactly the day a strategy cares
    # about.
    frame = frame.dropna(subset=["close", "ts"]).reset_index(drop=True)
    if frame.empty:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    out = schemas.normalise(frame, schemas.EOD, extra_columns=("adj_close",))
    if start is not None:
        out = out[out["ts"] >= int(schemas.to_utc(start).value // 10**6)]
    if end is not None:
        out = out[out["ts"] <= int(schemas.to_utc(end).value // 10**6)]
    return out.reset_index(drop=True)


def ingest(catalog, symbols=None, *, universe: str = "multi_asset",
           start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Download a universe and write it to the lake as EOD bars."""
    tickers = tuple(symbols) if symbols else UNIVERSES[universe]
    rows = []
    for symbol in tickers:
        df = daily(symbol, start=start, end=end)
        if not df.empty:
            catalog.write(schemas.EOD, VENUE, symbol, df)
        idx = pd.to_datetime(df["ts"], unit="ms", utc=True) if not df.empty else pd.Series(dtype="datetime64[ns, UTC]")
        rows.append({
            "symbol": symbol,
            "rows": len(df),
            "start": idx.min() if len(idx) else pd.NaT,
            "end": idx.max() if len(idx) else pd.NaT,
            "years": round(len(df) / 252.0, 1) if len(df) else 0.0,
        })
    return pd.DataFrame(rows)


def total_return_index(df: pd.DataFrame) -> pd.Series:
    """The dividend-adjusted return series, as a price index starting at the raw close.

    Returns come from `adj_close` because that is the only stream that includes the
    dividend; the level is rebased onto the first raw close so the series is quoted in
    the same units a reader expects. Use this for performance measurement, never as the
    price an order filled at.
    """
    if df.empty:
        return pd.Series(dtype="float64")
    adj = df["adj_close"].astype("float64") if "adj_close" in df.columns else df["close"].astype("float64")
    rets = adj.pct_change().fillna(0.0)
    return float(df["close"].iloc[0]) * (1.0 + rets).cumprod()


def dividend_drag(df: pd.DataFrame) -> float:
    """Annualised return the raw close misses versus the adjusted one.

    Worth printing before trusting any equity backtest. For TLT it is roughly four
    points a year — enough on its own to turn a profitable carry strategy into a losing
    one when measured on raw closes.
    """
    if df.empty or "adj_close" not in df.columns or len(df) < 2:
        return 0.0
    years = (df["ts"].iloc[-1] - df["ts"].iloc[0]) / (365.25 * 24 * 3600 * 1000)
    if years <= 0:
        return 0.0
    raw = float(df["close"].iloc[-1]) / float(df["close"].iloc[0])
    adj = float(df["adj_close"].iloc[-1]) / float(df["adj_close"].iloc[0])
    return (adj ** (1 / years)) - (raw ** (1 / years))
