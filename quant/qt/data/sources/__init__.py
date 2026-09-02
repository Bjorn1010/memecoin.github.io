"""Venue adapters. Every one is free and keyless."""

from . import (  # noqa: F401
    binance_vision,
    bitstamp,
    coinbase,
    deribit,
    hyperliquid,
    kraken,
    stooq,
    tradingview,
)

ALL = {
    "binance_vision": binance_vision,
    "bitstamp": bitstamp,
    "coinbase": coinbase,
    "deribit": deribit,
    "hyperliquid": hyperliquid,
    "kraken": kraken,
    "stooq": stooq,
    "tradingview": tradingview,
}
