"""The committed paper-trading record, and whether a small account can buy the book.

Two failures are guarded here, and neither raises anything on its own.

A paper trial whose state lives only in a gitignored SQLite file silently restarts from
its seed value the first time the machine is recycled: flat curve, zero drawdown, and a
record that looks like a calm month rather than a lost one.

And a book of fifteen weights is not a book of fifteen positions. On EUR 500 only three
of these ETFs can be bought as whole shares, so the trial would be measuring a strategy
the account cannot hold — correctly, and about the wrong thing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.live.journal import Journal, performance
from qt.live.orchestrator import CycleResult, DailySpec, mark_to_market
from qt.live.retail import capital_ladder, implement
from qt.live.state import Store


def result_at(day: str, equity: float, weights: dict, status: str = "ok") -> CycleResult:
    return CycleResult(
        ts=pd.Timestamp(day, tz="UTC"), status=status, reason="",
        weights=weights, raw_weights=weights, equity=equity,
        drawdown=0.0, risk_scale=1.0, gross=float(sum(abs(v) for v in weights.values())),
        data_age_days=0.5,
    )


@pytest.fixture
def journal(tmp_path) -> Journal:
    return Journal(path=tmp_path / "journal" / "paper.csv")


# ------------------------------------------------------------------- journal
def test_an_absent_journal_is_empty_not_an_error(journal):
    assert journal.frame().empty
    assert journal.last() is None


def test_a_cycle_survives_a_round_trip(journal):
    journal.append(result_at("2026-01-05", 500.0, {"SPY": 0.4, "GLD": 0.2}))
    row = journal.last()
    assert row["date"] == "2026-01-05"
    assert row["equity"] == pytest.approx(500.0)
    assert '"SPY": 0.4' in row["weights"]


def test_rerunning_a_day_replaces_it_rather_than_duplicating(journal):
    """A cycle is re-run often — a failed refresh, a retry. Two rows on one date would
    make every return computed afterwards count that day twice."""
    journal.append(result_at("2026-01-05", 500.0, {"SPY": 0.4}))
    journal.append(result_at("2026-01-05", 502.0, {"SPY": 0.5}))
    df = journal.frame()
    assert len(df) == 1
    assert float(df["equity"].iloc[0]) == pytest.approx(502.0)


def test_the_record_stays_ordered_by_time(journal):
    for day, equity in (("2026-01-07", 503.0), ("2026-01-05", 500.0), ("2026-01-06", 501.0)):
        journal.append(result_at(day, equity, {"SPY": 0.4}))
    assert journal.frame()["date"].tolist() == ["2026-01-05", "2026-01-06", "2026-01-07"]


def test_a_failed_cycle_is_recorded_too(journal):
    """A journal containing only the good days is not a record of what happened, and the
    failures are the rows that explain a gap in the curve."""
    journal.append(result_at("2026-01-05", 500.0, {}, status="stale"))
    assert journal.last()["status"] == "stale"


# ------------------------------------------------------------------- restore
def test_restore_rebuilds_enough_state_to_revalue_the_book(tmp_path):
    """The failure this whole module exists for.

    Without a restore, a fresh container starts from `starting_equity` with no holdings:
    `mark_to_market` finds an empty curve, returns the seed value, and the drawdown reads
    zero however the market moved. The trial silently resets and looks calm.
    """
    journal = Journal(path=tmp_path / "paper.csv")
    journal.append(result_at("2026-01-05", 512.0, {"SPY": 0.6}))

    fresh = Store(tmp_path / "runs.sqlite")
    assert journal.restore(fresh) == 1

    prices = pd.DataFrame(
        {"SPY": [100.0, 110.0, 121.0]},
        index=pd.date_range("2026-01-06", periods=3, freq="D", tz="UTC"))
    equity, drawdown, held = mark_to_market(fresh, "daily", prices, DailySpec())

    assert held == {"SPY": pytest.approx(0.6)}
    # The decision was made from data through 2026-01-05's close, so the order fills on
    # the next bar: entry at 100, revalued at 121, a 21% move on a 0.6 weight. Crediting
    # the book from the decision bar's own close would be a one-bar look-ahead worth a
    # full point of CAGR (see the note in `mark_to_market`).
    assert equity == pytest.approx(512.0 * (1 + 0.6 * 0.21))
    assert drawdown == pytest.approx(0.0)


def test_restoring_an_empty_journal_reports_zero(tmp_path):
    assert Journal(path=tmp_path / "nothing.csv").restore(Store(tmp_path / "r.sqlite")) == 0


# --------------------------------------------------------------- performance
def test_performance_withholds_a_sharpe_it_cannot_support(journal):
    """Annualising two weeks of returns produces a number with no information in it,
    and it is always the number people quote."""
    for i in range(10):
        journal.append(result_at(f"2026-01-{i + 5:02d}", 500.0 + i, {"SPY": 0.4}))
    perf = performance(journal)
    assert "sharpe" not in perf
    assert "il en faut 60" in perf["note"]


def test_performance_reports_once_the_sample_can_carry_it(journal):
    rng = np.random.default_rng(3)
    equity = 500.0
    for i, day in enumerate(pd.date_range("2026-01-01", periods=80, freq="B")):
        equity *= 1 + rng.normal(0.0004, 0.005)
        journal.append(result_at(day.strftime("%Y-%m-%d"), equity, {"SPY": 0.4}))
    perf = performance(journal)
    assert perf["jours"] == 80
    assert np.isfinite(perf["sharpe"])
    assert perf["pire_perte"] <= 0.0


# ------------------------------------------------------------------- retail
BOOK = {"UUP": 0.22, "SPY": 0.08, "GLD": 0.04}
PRICES = {"UUP": 28.17, "SPY": 765.16, "GLD": 402.78}


def test_whole_shares_drop_the_expensive_lines_on_a_small_account():
    """Measured on the real book: 3 of 15 positions survive on EUR 500.

    The lines that disappear are the expensive ones per share, which has nothing to do
    with their role in the portfolio — a selection criterion nobody chose.
    """
    small = implement(BOOK, PRICES, 500.0, fractional=False)
    assert small.shares["UUP"] >= 1
    assert small.shares["SPY"] == 0, "one SPY share costs more than its whole allocation"
    assert small.weight_error > 0.1


def test_fractional_shares_reproduce_the_book_exactly():
    frac = implement(BOOK, PRICES, 500.0, fractional=True)
    assert frac.positions_held == frac.positions_wanted
    assert frac.weight_error == pytest.approx(0.0, abs=1e-9)


def test_the_currency_rate_is_applied_and_not_assumed_to_be_one():
    """A dollar-priced ETF bought with euros costs price/rate. Ignoring the rate
    overstates how many shares fit — always in the flattering direction."""
    at_par = implement(BOOK, PRICES, 20_000.0, fractional=False, fx_rate=1.0)
    strong_euro = implement(BOOK, PRICES, 20_000.0, fractional=False, fx_rate=1.5)
    assert strong_euro.shares["SPY"] > at_par.shares["SPY"]


def test_a_short_is_not_silently_bought():
    """A small account does not sell short; pretending otherwise produces a book that
    reconciles on paper and cannot be placed with a broker."""
    out = implement({"SPY": -0.3}, PRICES, 10_000.0, fractional=True)
    assert out.shares["SPY"] == 0.0
    assert out.weight_error == pytest.approx(0.3)


def test_a_missing_price_costs_the_position_rather_than_raising():
    out = implement({"SPY": 0.5, "ZZZZ": 0.5}, {"SPY": 100.0}, 10_000.0, fractional=True)
    assert out.shares["ZZZZ"] == 0.0
    assert np.isfinite(out.weight_error)


def test_the_ladder_shows_replication_improving_with_capital():
    ladder = capital_ladder(BOOK, PRICES, capitals=(500, 5_000, 100_000))
    errors = ladder["erreur de poids (entières)"].to_numpy()
    assert (np.diff(errors) < 0).all(), "more capital must track the book more closely"
    assert (ladder["erreur de poids (fractionnées)"] < 1e-9).all()


def test_commission_is_charged_per_order_placed():
    free = implement(BOOK, PRICES, 10_000.0, fractional=False, commission_per_order=0.0)
    paid = implement(BOOK, PRICES, 10_000.0, fractional=False, commission_per_order=5.0)
    assert paid.commission_paid == pytest.approx(5.0 * paid.positions_held)
    assert paid.cash_left < free.cash_left
