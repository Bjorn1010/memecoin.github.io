"""Instrument universe definitions.

Universe choice is a research decision, not a detail. Two rules are baked in here:

* **Liquidity floor.** Only instruments deep enough that a retail-sized order is
  noise. Anything thinner produces backtests that cannot be traded.
* **Survivorship awareness.** These lists include assets that have gone through
  drawdowns of 80%+ and periods of near-zero volume. They are kept deliberately:
  removing yesterday's losers from a universe is the single most common way to
  manufacture a fake backtest.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str  # canonical symbol used across the lake
    venue: str
    kind: str  # "spot" | "perp" | "eod"
    quote: str = "USDT"
    # Perp funding is charged every 8h on Binance; None for non-perps.
    funding_interval_hours: int | None = None


# Binance spot majors — deepest free history available anywhere (2017+).
CRYPTO_SPOT = [
    Instrument("BTCUSDT", "binance", "spot"),
    Instrument("ETHUSDT", "binance", "spot"),
    Instrument("BNBUSDT", "binance", "spot"),
    Instrument("SOLUSDT", "binance", "spot"),
    Instrument("XRPUSDT", "binance", "spot"),
    Instrument("ADAUSDT", "binance", "spot"),
    Instrument("AVAXUSDT", "binance", "spot"),
    Instrument("LINKUSDT", "binance", "spot"),
    Instrument("DOGEUSDT", "binance", "spot"),
    Instrument("LTCUSDT", "binance", "spot"),
]

# USD-M perpetuals: same names, plus funding and the ability to be short without borrow.
CRYPTO_PERP = [
    Instrument(i.symbol, "binance-um", "perp", funding_interval_hours=8) for i in CRYPTO_SPOT
]

# Cross-asset context, daily frequency (see sources/stooq.py for symbology).
MACRO_EOD = [
    Instrument("idx_spx", "stooq", "eod", quote="USD"),
    Instrument("idx_vix", "stooq", "eod", quote="USD"),
    Instrument("idx_ndx", "stooq", "eod", quote="USD"),
    Instrument("tlt.us", "stooq", "eod", quote="USD"),
    Instrument("gld.us", "stooq", "eod", quote="USD"),
    Instrument("hyg.us", "stooq", "eod", quote="USD"),
    Instrument("dxy", "stooq", "eod", quote="USD"),
]

UNIVERSES = {
    "crypto_spot": CRYPTO_SPOT,
    "crypto_perp": CRYPTO_PERP,
    "macro": MACRO_EOD,
}


def get(name: str) -> list[Instrument]:
    if name not in UNIVERSES:
        raise KeyError(f"unknown universe {name!r}; known: {sorted(UNIVERSES)}")
    return list(UNIVERSES[name])


def symbols(name: str) -> list[str]:
    return [i.symbol for i in get(name)]
