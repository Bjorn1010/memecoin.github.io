"""A money-per-hour target, the return it implies, and what paper trading actually earns.

The arithmetic here is trivial and that is the point: it is trivial and it is almost
never done, so a target gets accepted, pursued, and only revealed as impossible after the
capital is at risk. These tests pin the two failure modes that matter — an implausible
target being quietly waved through, and a short paper record being annualised into a
number a hopeful reader will quote.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas
from qt.live.objective import (
    HOURS_PER_YEAR,
    Objective,
    achieved,
    capital_table,
    levers,
    return_table,
)
from qt.live.state import Store


def test_target_translates_to_the_right_annual_figure():
    obj = Objective(target_per_hour=100.0, capital=100_000.0, hours_basis="crypto_24_7")
    assert obj.hours_per_year == 8760
    assert obj.target_per_year == pytest.approx(876_000.0)
    assert obj.required_return == pytest.approx(8.76)


def test_hours_basis_changes_the_target_by_more_than_five_times():
    """Counting a per-hour target against hours the market is shut inflates it silently."""
    always = Objective(100.0, 100_000.0, "crypto_24_7").target_per_year
    market = Objective(100.0, 100_000.0, "us_market_hours").target_per_year
    assert always / market > 5.0


def test_unknown_basis_raises_rather_than_defaulting():
    with pytest.raises(ValueError, match="unknown hours_basis"):
        Objective(100.0, 1000.0, "whenever").hours_per_year


@pytest.mark.parametrize("capital,expected", [
    (25_000_000, "atteignable"),   # 3.5%/yr — what the bot actually measured
    (10_000_000, "atteignable"),   # 8.8%
    (5_000_000, "ambitieux"),      # 17.5%
    (2_000_000, "hors de portée"), # 43.8%
    (100_000, "impossible"),       # 876%
    (1_000, "impossible"),         # 87,600%
])
def test_verdict_tracks_recorded_history(capital, expected):
    """A required return above the best fund ever recorded must be named impossible.

    Accepting it quietly is how a system ends up meeting a target only by taking risk
    that ends in ruin.
    """
    verdict, _ = Objective(100.0, float(capital), "crypto_24_7").verdict()
    assert verdict == expected


def test_required_capital_inverts_the_arithmetic():
    obj = Objective(100.0, 100_000.0, "crypto_24_7")
    assert obj.required_capital(0.035) == pytest.approx(876_000 / 0.035)
    # At the return the bot measured, the target needs about 25 million.
    assert 24e6 < obj.required_capital(0.035) < 26e6


def test_zero_capital_is_infinite_not_a_crash():
    assert Objective(100.0, 0.0).required_return == float("inf")


def test_capital_table_covers_the_reference_returns():
    table = capital_table(Objective(100.0, 100_000.0))
    assert len(table) == 4
    caps = table["capital_requis"].to_numpy()
    # Higher return, less capital needed — strictly.
    assert (np.diff(caps) < 0).all()


def test_return_table_is_monotone_in_capital():
    table = return_table(Objective(100.0, 100_000.0))
    pct = [float(s.replace(",", "").rstrip("%")) for s in table["rendement_requis"]]
    assert (np.diff(pct) < 0).all()


def test_levers_price_risk_honestly():
    """Every lever except capital buys return by buying drawdown; the table must say so."""
    table = levers(Objective(100.0, 100_000.0))
    gains = table["gain_par_heure"].to_numpy()
    assert (np.diff(gains) > 0).all(), "more risk must show more gain"

    dd = [float(s.replace("−", "").rstrip("%")) for s in table["drawdown_mauvaise_année"]]
    assert (np.diff(dd) > 0).all(), "more risk must show more drawdown"
    # Even at 3x risk on 100k, the gain is nowhere near 100/hour.
    assert gains.max() < 2.0


# ------------------------------------------------------------------ achieved
@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "runs.sqlite")


def _record(store: Store, run_id: str, points: list[tuple[pd.Timestamp, float]]) -> None:
    for stamp, equity in points:
        ms = int(schemas.epoch_ms(pd.DatetimeIndex([stamp])).iloc[0])
        store.record_equity(run_id, ms, equity, equity, 1.0, 0.0, False)


def test_achieved_needs_a_record_before_it_reports_anything(store):
    got = achieved(store, "empty")
    assert got.cycles == 0
    assert got.per_hour == 0.0
    assert "pas encore" in got.note


def test_achieved_measures_wall_clock_hours(store):
    """Per-hour means elapsed time. Switching to trading hours multiplies it by five."""
    start = pd.Timestamp("2026-01-01", tz="UTC")
    _record(store, "r", [(start, 100_000.0), (start + pd.Timedelta(days=100), 110_000.0)])

    got = achieved(store, "r")
    assert got.hours == pytest.approx(2400.0)
    assert got.pnl == pytest.approx(10_000.0)
    assert got.per_hour == pytest.approx(10_000.0 / 2400.0)


def test_a_short_record_is_flagged_not_annualised_silently(store):
    """Two weeks annualises to nonsense, and that nonsense is what gets quoted."""
    start = pd.Timestamp("2026-01-01", tz="UTC")
    _record(store, "r", [(start, 100_000.0), (start + pd.Timedelta(days=14), 101_000.0)])

    got = achieved(store, "r")
    assert got.note, "a fortnight of record must carry the caveat"
    assert "jours de trace" in got.note


def test_a_long_record_is_annualised_without_the_caveat(store):
    start = pd.Timestamp("2024-01-01", tz="UTC")
    _record(store, "r", [(start, 100_000.0), (start + pd.Timedelta(days=730), 121_000.0)])

    got = achieved(store, "r")
    assert got.note == ""
    # 21% over two years compounds to about 10% a year.
    assert got.annualised_return == pytest.approx(0.10, abs=0.005)


def test_losses_report_as_negative_per_hour(store):
    start = pd.Timestamp("2026-01-01", tz="UTC")
    _record(store, "r", [(start, 100_000.0), (start + pd.Timedelta(days=50), 92_000.0)])

    got = achieved(store, "r")
    assert got.per_hour < 0
    assert got.pnl == pytest.approx(-8_000.0)


def test_identical_timestamps_report_rather_than_dividing_by_zero(store):
    stamp = pd.Timestamp("2026-01-01", tz="UTC")
    ms = int(schemas.epoch_ms(pd.DatetimeIndex([stamp])).iloc[0])
    store.record_equity("r", ms, 100_000.0, 100_000.0, 1.0, 0.0, False)
    store.record_equity("r", ms, 100_000.0, 100_000.0, 1.0, 0.0, False)

    got = achieved(store, "r")
    assert np.isfinite(got.per_hour)
    assert got.per_hour == 0.0


def test_hours_per_year_constants_are_right():
    assert HOURS_PER_YEAR["crypto_24_7"] == 8760
    assert HOURS_PER_YEAR["us_market_hours"] == pytest.approx(1638.0)
    assert HOURS_PER_YEAR["working_day"] == 2000
