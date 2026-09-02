"""Tests for the macro/funding context loader.

The bug this guards against does not raise: an alpha whose inputs are missing returns a
flat zero, the report still lists it, and the strategy quietly runs on fewer signals than
it claims. So the assertions here are about *coverage* — a feature column that exists but
is constant is treated as a failure, not a pass.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas
from qt.data.catalog import Catalog
from qt.features import context as ctxmod
from qt.features import build_features, context_report, load_context


@pytest.fixture
def lake(tmp_path, bars):
    """A catalog holding one macro series, one DVOL series and one funding series."""
    cat = Catalog(root=tmp_path)
    idx = bars.index
    days = pd.date_range(idx.min().floor("D"), idx.max().ceil("D"), freq="1D", tz="UTC")
    rng = np.random.default_rng(3)

    for venue, symbol, level in (
        (ctxmod.MACRO_VENUE, "spx", 4000.0),
        (ctxmod.MACRO_VENUE, "vix", 18.0),
        (ctxmod.MACRO_VENUE, "dxy", 103.0),
        (ctxmod.DVOL_VENUE, "DVOLBTC", 55.0),
    ):
        walk = level * np.exp(np.cumsum(rng.standard_normal(len(days)) * 0.01))
        cat.write(schemas.EOD, venue, symbol, schemas.normalise(pd.DataFrame({
            "ts": schemas.epoch_ms(days), "open": walk, "high": walk * 1.01,
            "low": walk * 0.99, "close": walk, "volume": 1.0,
        }), schemas.EOD))

    # Funding prints every 8 hours, as Binance actually pays them.
    fund_idx = pd.date_range(idx.min(), idx.max(), freq="8h", tz="UTC")
    rate = rng.standard_normal(len(fund_idx)) * 1e-4 + 5e-5
    cat.write(schemas.FUNDING, ctxmod.PERP_VENUE, "BTCUSDT", schemas.normalise(
        pd.DataFrame({"ts": schemas.epoch_ms(fund_idx), "rate": rate}), schemas.FUNDING))
    return cat


def test_load_context_finds_what_was_written(lake):
    ctx = load_context(lake, ["BTCUSDT"])
    assert {"spx", "vix", "dxy", "dvol"} <= set(ctx["macro"])
    assert "BTCUSDT" in ctx["funding"]


def test_missing_series_are_omitted_not_returned_empty(lake):
    """An empty frame would become an all-NaN column and reach the model as noise."""
    ctx = load_context(lake, ["BTCUSDT", "NOTLISTEDUSDT"])
    assert "NOTLISTEDUSDT" not in ctx["funding"]
    assert all(not df.empty for df in ctx["macro"].values())


def test_funding_is_read_from_the_perp_venue_not_spot(lake):
    """The spot and perp tickers are the same string; only the venue separates them.

    Reading funding from the "binance" venue returns nothing and raises nothing — the
    exact shape of the bug this module exists to fix.
    """
    assert ctxmod.load_funding(lake, ["BTCUSDT"], venue="binance") == {}
    assert ctxmod.load_funding(lake, ["BTCUSDT"]) != {}


@pytest.mark.parametrize("symbol,asset", [
    ("BTCUSDT", "BTC"), ("BTCUSD", "BTC"), ("ETHUSDC", "ETH"), ("BTC", "BTC"), ("USDT", "USDT"),
])
def test_asset_of(symbol, asset):
    assert ctxmod._asset_of(symbol) == asset


def test_context_activates_otherwise_flat_features(lake, bars):
    """Without context the funding/macro columns are absent; with it they vary."""
    plain = build_features(bars, symbol="BTCUSDT").X
    assert not any(c.startswith("funding_") for c in plain.columns)

    ctx = load_context(lake, ["BTCUSDT"])
    rich = build_features(bars, symbol="BTCUSDT",
                          macro=ctx["macro"], funding=ctx["funding"]["BTCUSDT"]).X

    for col in ("funding_rate", "funding_z", "spx_ret_20d", "vix_z", "vrp"):
        assert col in rich.columns, f"{col} missing — the alpha reading it would be flat"
        series = rich[col].dropna()
        assert len(series) > 0, f"{col} is entirely NaN"
        assert series.std() > 0, f"{col} is constant — present but inert"


def test_macro_join_is_backward_only(lake, bars):
    """A daily close must never be visible on a bar that precedes its publication."""
    ctx = load_context(lake, ["BTCUSDT"])
    spx = ctx["macro"]["spx"]
    joined = ctxmod.pd.DataFrame(index=bars.index)
    from qt.features.external import asof_join

    joined = asof_join(bars, spx, "spx", columns=("close",))["spx_close"]
    spx_idx = pd.to_datetime(spx["ts"], unit="ms", utc=True)
    spx_close = pd.Series(spx["close"].to_numpy(), index=spx_idx)

    for ts in bars.index[::97]:
        value = joined.loc[ts]
        if pd.isna(value):
            continue
        # The joined value must equal the last close published at or before this bar.
        eligible = spx_close[spx_close.index <= ts]
        assert not eligible.empty
        assert value == pytest.approx(eligible.iloc[-1])


def test_context_report_flags_absent_series(lake):
    rep = context_report(lake, ["BTCUSDT", "ETHUSDT"])
    assert (rep["rows"] == 0).any(), "series absent from the lake must be reported, not hidden"
    eth = rep[(rep["kind"] == "funding") & (rep["series"] == "ETHUSDT")]
    assert len(eth) == 1 and int(eth["rows"].iloc[0]) == 0

    btc = rep[(rep["kind"] == "funding") & (rep["series"] == "BTCUSDT")]
    assert int(btc["rows"].iloc[0]) > 0
    assert pd.notna(btc["end"].iloc[0])


def test_non_positive_macro_series_do_not_become_nan(bars):
    """A yield spread goes negative; log() of it is NaN, and NaN is not an error.

    The 10y-2y slope was below zero on 551 days of the 2022-23 inversion and WTI printed
    -$37 in April 2020. Taking log returns of either wipes the series out silently.
    """
    from qt.features.external import macro_features

    days = pd.date_range(bars.index.min().floor("D"), bars.index.max().ceil("D"),
                         freq="1D", tz="UTC")
    rng = np.random.default_rng(11)
    # A spread that inverts, exactly like T10Y2Y.
    spread = np.linspace(1.2, -0.9, len(days)) + rng.standard_normal(len(days)) * 0.02
    curve = schemas.normalise(pd.DataFrame({
        "ts": schemas.epoch_ms(days), "open": spread, "high": spread,
        "low": spread, "close": spread, "volume": 0.0,
    }), schemas.EOD)

    out = macro_features(bars, {"curve": curve})
    assert (spread < 0).any(), "fixture must actually invert or it tests nothing"

    # Named a change, not a return — the units are points, not log-returns.
    assert "curve_chg_20d" in out.columns
    assert "curve_ret_20d" not in out.columns

    values = out["curve_chg_20d"].dropna()
    assert len(values) > 0
    assert np.isfinite(values).all(), "log() of a negative level leaked through"


def test_positive_macro_series_still_use_log_returns(bars):
    from qt.features.external import macro_features

    days = pd.date_range(bars.index.min().floor("D"), bars.index.max().ceil("D"),
                         freq="1D", tz="UTC")
    level = 4000 * np.exp(np.cumsum(np.random.default_rng(5).standard_normal(len(days)) * 0.01))
    spx = schemas.normalise(pd.DataFrame({
        "ts": schemas.epoch_ms(days), "open": level, "high": level,
        "low": level, "close": level, "volume": 0.0,
    }), schemas.EOD)

    out = macro_features(bars, {"spx": spx})
    assert "spx_ret_20d" in out.columns, "the alpha library looks this name up by hand"
    assert np.isfinite(out["spx_ret_20d"].dropna()).all()


def test_residual_returns_are_not_silently_nan(panel):
    """`frame * series` aligns the series index against the frame's COLUMNS.

    Symbols against timestamps overlap in nothing, so every value becomes NaN — and
    because pandas takes the union, `residual[symbol]` still resolves and returns an
    all-NaN series. No KeyError, no warning. This killed xs_resid_ret and all four
    xs_resmom_rank_* columns, and the xs_reversal alpha that reads them returned a flat
    zero for every bar.
    """
    from qt.features.cross_sectional import build_panel_features

    xs = build_panel_features(panel)
    first = next(iter(panel))
    frame = xs[first]

    for col in ("xs_resid_ret", "xs_resmom_rank_24", "xs_resmom_rank_720"):
        assert col in frame.columns, f"{col} missing"
        series = frame[col]
        assert series.notna().sum() > len(series) * 0.5, f"{col} is mostly NaN"
        assert series.std() > 0, f"{col} is constant"

    # The frame's columns must all be feature names. Timestamp columns are the
    # fingerprint of the broadcasting bug.
    assert all(isinstance(c, str) for c in frame.columns)


def test_every_alpha_produces_a_live_signal_given_full_context(crypto_panel, lake):
    """No alpha may be silently inert once its inputs exist.

    An alpha returning zeros still appears in the report with a name and a rationale,
    so this is the only place the difference is visible.
    """
    from qt import alphas as A
    from qt.features import build_panel, load_context

    symbols = list(crypto_panel)
    ctx = load_context(lake, symbols)
    mats = build_panel(crypto_panel, **ctx)

    first = symbols[0]
    sig = A.compute_all(crypto_panel[first], mats[first].X, warn_missing=False)
    inert = [c for c in sig.columns if float((sig[c].fillna(0) != 0).mean()) == 0.0]
    assert not inert, f"alphas present in the report but producing nothing: {inert}"
