"""Retail scalping mechanics: whole shares, per-order fees, session boundaries.

The frictions tested here are the ones that decide the answer at €40 a trade and that a
percentage-based cost model makes invisible. A simulator that gets them wrong produces a
profitable curve from a strategy nobody could have placed a single order for.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.strategies.scalping import (
    BROKERS,
    Broker,
    ScalpSpec,
    feasibility,
    run_scalping,
    scalp_signal,
)


def make_bars(closes, *, price_scale=1.0, sessions=1, freq="5min") -> pd.DataFrame:
    closes = np.asarray(closes, dtype="float64") * price_scale
    index = pd.date_range("2026-06-01 13:30", periods=len(closes), freq=freq, tz="UTC")
    wiggle = np.abs(np.diff(closes, prepend=closes[0])) + closes * 0.0005
    per = max(len(closes) // sessions, 1)
    session_id = (np.arange(len(closes)) // per).astype("int64")
    return pd.DataFrame({
        "ts": (index.astype("int64") // 10**6),
        "open": closes, "high": closes + wiggle, "low": closes - wiggle,
        "close": closes, "volume": 1e6, "session_id": session_id,
    }, index=index)


@pytest.fixture
def noisy() -> pd.DataFrame:
    rng = np.random.default_rng(77)
    n = 1200
    close = 100 * np.exp(np.cumsum(rng.standard_normal(n) * 0.001))
    return make_bars(close, sessions=15)


# ------------------------------------------------------------------- broker
def test_whole_shares_make_a_small_order_impossible():
    """€40 does not buy one share of a $707 ETF. Not expensive — impossible.

    A simulator trading fractional notional assumes an account feature many brokers do
    not offer, and produces trades that could never have been placed.
    """
    broker = Broker(fractional_shares=False)
    assert broker.shares_for(40.0, 707.0) == 0.0
    assert broker.shares_for(40.0, 30.0) == 1.0
    assert broker.shares_for(100.0, 30.0) == 3.0

    fractional = Broker(fractional_shares=True)
    assert fractional.shares_for(40.0, 707.0) == pytest.approx(40 / 707)


def test_impossible_orders_are_counted_not_silently_skipped(noisy):
    """A run that placed no orders must say why, not report a flat zero."""
    expensive = make_bars(np.full(600, 1.0), price_scale=707.0, sessions=8)
    spec = ScalpSpec(position_eur=40.0, entry_threshold=0.0)
    result = run_scalping(expensive, spec, Broker(fractional_shares=False), symbol="QQQ")
    assert result.diagnostics["trades"] == 0
    assert "note" in result.diagnostics


def test_flat_fee_dominates_at_small_size():
    """A €1 order fee on €40 is 5% for the round trip; QQQ moves 0.08% in ten minutes."""
    broker = BROKERS["courtier européen 1 €"]
    assert broker.fee(40.0) == pytest.approx(1.0)
    round_trip_share = 2 * broker.fee(40.0) / 40.0
    assert round_trip_share == pytest.approx(0.05)

    free = BROKERS["US sans commission"]
    assert free.fee(40.0) == 0.0


def test_fill_price_crosses_the_spread_in_the_right_direction():
    broker = Broker(spread_cents=0.02)
    assert broker.fill_price(100.0, 1) == pytest.approx(100.01)   # buy at the ask
    assert broker.fill_price(100.0, -1) == pytest.approx(99.99)   # sell at the bid


def test_slippage_adds_beyond_the_half_spread():
    broker = Broker(spread_cents=0.02, slippage_cents=0.03)
    assert broker.fill_price(100.0, 1) == pytest.approx(100.04)


# --------------------------------------------------------------- feasibility
def test_feasibility_rejects_a_target_the_instrument_cannot_reach():
    """€20 on €40 is a 50% move. Checking that first makes simulating it unnecessary."""
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.standard_normal(2000) * 0.001))
    bars = make_bars(close, sessions=20)

    impossible = feasibility(ScalpSpec(position_eur=40.0, target_eur=20.0), bars)
    assert impossible["part_des_fenetres_atteignant_la_cible"] == "0.000%"
    assert "hors de portée" in impossible["verdict"]

    # A target near the instrument's own distribution is reachable.
    moves = bars["close"].pct_change(2).abs().dropna()
    reachable_target = 40.0 * float(moves.quantile(0.70))
    ok = feasibility(ScalpSpec(position_eur=40.0, target_eur=reachable_target), bars)
    assert ok["verdict"] == "atteignable"


def test_leverage_lowers_the_move_the_target_needs():
    plain = ScalpSpec(position_eur=40.0, target_eur=20.0, leverage=1.0)
    levered = ScalpSpec(position_eur=40.0, target_eur=20.0, leverage=50.0)
    assert plain.target_pct() == pytest.approx(0.5)
    assert levered.target_pct() == pytest.approx(0.01)


# --------------------------------------------------------------- simulation
def test_no_position_survives_the_session_boundary(noisy):
    """A scalper holding overnight is not scalping, and the gap is most of the variance."""
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.3, max_hold_bars=500,
                     target_eur=1e6, stop_eur=1e6, max_trades_per_session=99)
    result = run_scalping(noisy, spec, BROKERS["US sans commission"], symbol="X")
    assert not result.trades.empty

    session_of = noisy["session_id"]
    for _, trade in result.trades.iterrows():
        assert session_of.loc[trade["entree"]] == session_of.loc[trade["sortie"]]
    assert "clôture" in result.diagnostics["raisons_de_sortie"]


def test_entry_is_at_the_next_bar_open(noisy):
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.5)
    result = run_scalping(noisy, spec, Broker(spread_cents=0.0), symbol="X")
    if result.trades.empty:
        pytest.skip("no entries")
    first = result.trades.iloc[0]
    i = list(noisy.index).index(first["entree"])
    # The trade record rounds to 4 decimals; the computation does not.
    assert first["prix_entree"] == pytest.approx(noisy["open"].iloc[i], abs=1e-4)


def test_an_ambiguous_bar_is_read_as_the_stop(noisy):
    """Reading it as the target is how intraday backtests manufacture their edge."""
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.3,
                     target_eur=0.01, stop_eur=0.01, max_hold_bars=4)
    result = run_scalping(noisy, spec, BROKERS["US sans commission"], symbol="X")
    if result.trades.empty:
        pytest.skip("no trades")
    reasons = result.diagnostics["raisons_de_sortie"]
    # With target and stop equally close, a symmetric read would give roughly half
    # each; the pessimistic read must tilt to stops.
    assert reasons.get("stop", 0) >= reasons.get("cible", 0)


def test_trades_per_session_cap_binds(noisy):
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.1, max_trades_per_session=2,
                     max_hold_bars=1, cooldown_bars=0)
    result = run_scalping(noisy, spec, BROKERS["US sans commission"], symbol="X")
    if result.trades.empty:
        pytest.skip("no trades")
    per = result.trades.groupby(noisy["session_id"].loc[result.trades["entree"]].to_numpy()).size()
    assert per.max() <= 2


def test_fees_are_charged_on_both_sides(noisy):
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.5)
    free = run_scalping(noisy, spec, Broker(commission_per_order=0.0, spread_cents=0.0),
                        symbol="X")
    paid = run_scalping(noisy, spec, Broker(commission_per_order=1.0, spread_cents=0.0),
                        symbol="X")
    if free.trades.empty:
        pytest.skip("no trades")

    assert len(free.trades) == len(paid.trades)
    assert np.allclose(paid.trades["frais_eur"].to_numpy(), 2.0), (
        "a €1 flat fee must be charged on entry and on exit"
    )
    assert paid.trades["net_eur"].sum() < free.trades["net_eur"].sum()


def test_gross_is_unchanged_by_the_fee_structure(noisy):
    """Fees must not move the decisions, only the accounting."""
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.5)
    a = run_scalping(noisy, spec, Broker(commission_per_order=0.0, spread_cents=0.0), symbol="X")
    b = run_scalping(noisy, spec, Broker(commission_per_order=5.0, spread_cents=0.0), symbol="X")
    if a.trades.empty:
        pytest.skip("no trades")
    pd.testing.assert_series_equal(a.trades["brut_eur"], b.trades["brut_eur"])


def test_signal_is_causal(noisy):
    full = scalp_signal(noisy, ScalpSpec())
    cut = scalp_signal(noisy.iloc[:700], ScalpSpec())
    pd.testing.assert_series_equal(full.loc[cut.index], cut, check_freq=False)


def test_diagnostics_report_the_fee_share(noisy):
    """Above 100% the strategy is a fee generator whatever the signal does."""
    spec = ScalpSpec(position_eur=100.0, entry_threshold=0.4)
    result = run_scalping(noisy, spec, BROKERS["courtier européen 3 €"], symbol="X")
    if result.trades.empty:
        pytest.skip("no trades")
    assert "part_des_frais_sur_le_brut" in result.diagnostics
    assert result.diagnostics["frais_eur"] > 0
    assert result.diagnostics["net_par_heure_eur"] < 0, (
        "a €3 flat fee on €100 trades must lose money — if it does not, the fee is "
        "not being charged"
    )


def test_empty_result_keeps_its_columns(noisy):
    result = run_scalping(noisy, ScalpSpec(entry_threshold=99.0), symbol="X")
    assert result.trades.empty
    assert "net_eur" in result.trades.columns
