"""Shared fixtures. Everything is synthetic so the suite runs offline and fast."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data.schemas import epoch_ms


def make_bars(n: int = 2000, seed: int = 7, start: str = "2023-01-01", freq: str = "1h") -> pd.DataFrame:
    """A synthetic OHLCV series with realistic-ish structure.

    Deliberately includes volatility clustering and a signed-flow column, so the
    microstructure and regime features are exercised rather than silently NaN.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=n, freq=freq, tz="UTC")

    # GARCH-ish volatility so the vol and regime features have something to detect.
    vol = np.zeros(n)
    vol[0] = 0.004
    shocks = rng.standard_normal(n)
    for i in range(1, n):
        vol[i] = np.sqrt(1e-7 + 0.9 * vol[i - 1] ** 2 + 0.05 * (vol[i - 1] * shocks[i - 1]) ** 2)
    ret = vol * shocks
    close = 30_000 * np.exp(np.cumsum(ret))

    spread = np.abs(rng.standard_normal(n)) * vol * close * 0.5
    high = close + spread
    low = close - spread
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = np.abs(rng.lognormal(3.0, 0.6, n))
    buy_share = np.clip(0.5 + 3 * ret / np.maximum(vol, 1e-9) * 0.02, 0.05, 0.95)

    df = pd.DataFrame(
        {
            # Via epoch_ms, not `index.astype("int64") // 10**6`: pd.date_range
            # returns a microsecond-resolution index on pandas 3, so that expression
            # yields seconds and every downstream ts is wrong by 1000x.
            "ts": epoch_ms(index).to_numpy(),
            "start_ts": epoch_ms(index).to_numpy() - 3_600_000,
            "open": open_,
            "high": np.maximum.reduce([high, open_, close]),
            "low": np.minimum.reduce([low, open_, close]),
            "close": close,
            "vwap": close,
            "volume": volume,
            "quote_volume": volume * close,
            "trades": np.maximum((volume * 30).astype(int), 1).astype("float64"),
            "buy_volume": volume * buy_share,
        },
        index=index,
    )
    df["sell_volume"] = df["volume"] - df["buy_volume"]
    df.index.name = "dt"
    return df


def make_trades(n: int = 5000, seed: int = 3) -> pd.DataFrame:
    """Synthetic tick data in the canonical trades schema."""
    rng = np.random.default_rng(seed)
    ts = np.sort(rng.integers(1_700_000_000_000, 1_700_086_400_000, n))
    price = 30_000 * np.exp(np.cumsum(rng.standard_normal(n) * 0.0002))
    qty = np.abs(rng.lognormal(-2, 1.0, n))
    is_buyer_maker = rng.random(n) < 0.5
    return pd.DataFrame({"ts": ts, "price": price, "qty": qty, "is_buyer_maker": is_buyer_maker})


@pytest.fixture
def bars() -> pd.DataFrame:
    return make_bars()


@pytest.fixture
def small_bars() -> pd.DataFrame:
    return make_bars(n=900, seed=11)


@pytest.fixture
def trades() -> pd.DataFrame:
    return make_trades()


@pytest.fixture
def tmp_catalog(tmp_path):
    from qt.data import Catalog

    return Catalog(tmp_path / "lake")
