"""Tests for the equity/ETF path: dividend adjustment, lake round-trip, weight sizing.

Two of these guard bugs that produced a confident, wrong number rather than an error —
the pattern this codebase keeps hitting. `adj_close` was dropped on every lake write and
read, so the dividend-adjusted series silently became the raw one; and the portfolio
engine rescaled allocator weights by inverse volatility while a comment claimed it did
not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas
from qt.data.catalog import Catalog
from qt.data.sources import yahoo


def _eod(days, close, adj=None) -> pd.DataFrame:
    frame = pd.DataFrame({
        "ts": schemas.epoch_ms(days),
        "open": close, "high": np.asarray(close) * 1.01,
        "low": np.asarray(close) * 0.99, "close": close,
        "volume": 1e6,
    })
    if adj is not None:
        frame["adj_close"] = adj
    return schemas.normalise(frame, schemas.EOD, extra_columns=("adj_close",))


@pytest.fixture
def dividend_payer():
    """Ten years of a flat price paying 4% a year — the shape of TLT or LQD."""
    days = pd.date_range("2015-01-01", periods=252 * 10, freq="B", tz="UTC")
    close = np.full(len(days), 100.0)
    # Adjusted series compounds the reinvested dividend while the price stays flat.
    adj = 100.0 * (1.04 ** (np.arange(len(days)) / 252.0))
    return days, close, adj


def test_extra_columns_survive_a_lake_round_trip(tmp_path, dividend_payer):
    """normalise() dropped every non-canonical column, on write AND on read.

    The frame came back one column lighter with no error, so adj_close silently became
    close and every equity return lost its dividend.
    """
    days, close, adj = dividend_payer
    cat = Catalog(root=tmp_path)
    cat.write(schemas.EOD, "yahoo", "TESTX", _eod(days, close, adj))

    back = cat.read(schemas.EOD, "yahoo", "TESTX")
    assert "adj_close" in back.columns, "adj_close lost in the lake round-trip"
    assert back["adj_close"].iloc[-1] == pytest.approx(adj[-1], rel=1e-9)
    # The canonical columns must still come first and be unchanged.
    assert list(back.columns)[: len(schemas.EOD_COLUMNS)] == schemas.EOD_COLUMNS


def test_dividend_drag_recovers_the_known_yield(dividend_payer):
    days, close, adj = dividend_payer
    df = _eod(days, close, adj)
    assert yahoo.dividend_drag(df) == pytest.approx(0.04, abs=2e-3)


def test_no_dividend_means_no_drag():
    """Gold and oil pay nothing; a non-zero reading there is a bug in the adjustment."""
    days = pd.date_range("2015-01-01", periods=500, freq="B", tz="UTC")
    walk = 100 * np.exp(np.cumsum(np.random.default_rng(2).standard_normal(len(days)) * 0.01))
    df = _eod(days, walk, walk)
    assert yahoo.dividend_drag(df) == pytest.approx(0.0, abs=1e-9)


def test_total_return_index_beats_raw_price_by_the_yield(dividend_payer):
    days, close, adj = dividend_payer
    df = _eod(days, close, adj)
    tri = yahoo.total_return_index(df)
    assert tri.iloc[0] == pytest.approx(close[0])
    # Price flat, total return up ~48% over ten years at 4%.
    assert tri.iloc[-1] / tri.iloc[0] == pytest.approx(adj[-1] / adj[0], rel=1e-6)
    assert float(df["close"].iloc[-1] / df["close"].iloc[0]) == pytest.approx(1.0)


def test_signal_is_weight_stops_the_engine_rescaling_the_book(panel):
    """Without the flag the engine multiplies each weight by target_vol/instrument_vol.

    Every allocator then becomes a blend of itself and inverse-volatility, the methods
    look far more alike than they are, and gross exposure collapses — an equal-weight
    book summing to 1.0 ran at 3.4% realised volatility against a 10% target.
    """
    from qt.backtest import BacktestConfig
    from qt.backtest.engine import run_backtest

    symbols = list(panel)
    index = panel[symbols[0]].index
    weights = pd.DataFrame(1.0 / len(symbols), index=index, columns=symbols)

    cfg = dict(bars_per_year=252, target_annual_vol=0.10, allow_short=False,
               max_weight_per_symbol=1.0)
    scaled = run_backtest(panel, weights, BacktestConfig(**cfg, signal_is_weight=False))
    exact = run_backtest(panel, weights, BacktestConfig(**cfg, signal_is_weight=True))

    held = exact.weights.abs().sum(axis=1)
    assert held.max() == pytest.approx(1.0, abs=0.05), "weights must pass through untouched"

    rescaled = scaled.weights.abs().sum(axis=1)
    assert not np.isclose(rescaled.max(), held.max(), atol=0.05), (
        "the two paths produced the same book — the flag is not doing anything"
    )
