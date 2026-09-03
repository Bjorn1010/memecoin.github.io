"""The autonomous scalping loop: it must not raise, and it must not trade real money.

The second property is the one worth a test rather than a comment. This package ships no
broker adapter, and the cycle refuses outright if a non-paper execution is handed to it —
so a real adapter cannot be connected by configuration, only by an edit someone has to
make deliberately.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas
from qt.data.catalog import Catalog
from qt.live.scalp_bot import (
    MARKETS,
    PaperBroker,
    ScalpBotSpec,
    SkillGate,
    decide,
    run_cycle,
)
from qt.live.state import Store


def make_bars(n: int = 1500, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2026-06-01 13:30", periods=n, freq="5min", tz="UTC")
    close = 400 * np.exp(np.cumsum(rng.standard_normal(n) * 0.001))
    wiggle = np.abs(rng.standard_normal(n)) * close * 0.0008
    frame = pd.DataFrame({
        "ts": schemas.epoch_ms(index),
        "open": close, "high": close + wiggle, "low": close - wiggle,
        "close": close, "volume": 1e6,
        "session_id": pd.to_datetime(index).normalize().astype("int64"),
    })
    return schemas.to_datetime_index(
        schemas.normalise(frame, schemas.EOD, extra_columns=("session_id",)))


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    cat = Catalog(root=tmp_path / "lake")
    for symbol in ("QQQ", "GLD"):
        cat.write("eod_5m", "yahoo", symbol, make_bars(seed=hash(symbol) % 100))
    return cat, Store(tmp_path / "runs.sqlite")


# ----------------------------------------------------------------- safety
class FakeLiveBroker:
    """Stands in for a real adapter. Nothing in the package returns one of these."""

    @property
    def is_paper(self) -> bool:
        return False

    def submit(self, *args, **kwargs):
        raise AssertionError("a real order was attempted")


def test_a_non_paper_execution_is_refused(seeded):
    """Connecting real money must be an edit someone makes, never a config flip."""
    cat, store = seeded
    report = run_cycle(ScalpBotSpec(), catalog=cat, broker=FakeLiveBroker(),
                       store=store, refresh=False)
    assert report.status == "refusé"
    assert "argent réel" in report.reason
    assert not report.fills


def test_the_paper_broker_places_nothing():
    broker = PaperBroker()
    fill = broker.submit("QQQ", 1, 100.0, 700.0, "test")
    assert broker.is_paper
    assert fill["papier"] is True
    assert len(broker.fills) == 1


# ------------------------------------------------------------------ cycle
def test_a_cycle_never_raises(seeded, monkeypatch):
    """A loop that stops is not autonomous."""
    cat, store = seeded

    def explode(*args, **kwargs):
        raise RuntimeError("panne simulée de l'analyse")

    monkeypatch.setattr("qt.live.scalp_bot.decide", explode)
    report = run_cycle(ScalpBotSpec(), catalog=cat, store=store, refresh=False)
    assert report.status == "erreur"
    assert "panne simulée" in report.reason


def test_a_cycle_decides_on_every_market(seeded):
    cat, store = seeded
    spec = ScalpBotSpec(symbols=("QQQ", "GLD"))
    report = run_cycle(spec, catalog=cat, store=store, refresh=False)

    assert report.status == "ok"
    assert len(report.decisions) == 2
    assert {d.symbol for d in report.decisions} == {"QQQ", "GLD"}
    for d in report.decisions:
        assert d.action in ("ACHETER", "VENDRE", "ATTENDRE", "BLOQUÉ")
        assert d.reason, "every decision must carry its reason"


def test_a_missing_market_is_reported_not_skipped(tmp_path):
    cat = Catalog(root=tmp_path / "empty")
    report = run_cycle(ScalpBotSpec(symbols=("QQQ",)), catalog=cat, refresh=False)
    assert len(report.decisions) == 1
    assert report.decisions[0].action == "ATTENDRE"
    assert "aucune donnée" in report.decisions[0].reason


def test_decisions_are_recorded(seeded):
    cat, store = seeded
    run_cycle(ScalpBotSpec(), catalog=cat, store=store, run_id="t", refresh=False)
    decisions = store.decisions("t", limit=50)
    assert not decisions.empty
    assert decisions["risk_reason"].str.len().min() > 0


# ------------------------------------------------------------------- gate
def test_the_gate_blocks_by_default_on_a_signal_with_no_skill(seeded):
    """Synthetic random walks have no predictable direction, so the gate must fire."""
    cat, _ = seeded
    bars = cat.read_indexed("eod_5m", "yahoo", "QQQ")
    decision = decide(bars, "QQQ", ScalpBotSpec())
    assert decision.action in ("BLOQUÉ", "ATTENDRE")
    if decision.action == "BLOQUÉ":
        assert "distinguer" in decision.reason or "taux de base" in decision.reason


def test_no_order_is_placed_when_the_gate_blocks(seeded):
    cat, store = seeded
    broker = PaperBroker()
    run_cycle(ScalpBotSpec(), catalog=cat, broker=broker, store=store, refresh=False)
    blocked = [d for d in run_cycle(ScalpBotSpec(), catalog=cat, broker=broker,
                                    store=store, refresh=False).decisions
               if d.action == "BLOQUÉ"]
    for d in blocked:
        assert not any(f["symbole"] == d.symbol for f in broker.fills[-len(blocked):])


def test_required_probability_reflects_the_cost(seeded):
    """A higher round-trip cost must raise the bar the probability has to clear."""
    cat, _ = seeded
    bars = cat.read_indexed("eod_5m", "yahoo", "QQQ")
    cheap = decide(bars, "QQQ", ScalpBotSpec(round_trip_cost=0.0001))
    dear = decide(bars, "QQQ", ScalpBotSpec(round_trip_cost=0.0020))
    assert dear.required > cheap.required


def test_markets_are_named_in_plain_language():
    assert MARKETS["QQQ"] == "Nasdaq 100"
    assert MARKETS["GLD"] == "or"


def test_report_serialises(seeded):
    cat, store = seeded
    report = run_cycle(ScalpBotSpec(), catalog=cat, store=store, refresh=False)
    payload = report.to_dict()
    assert set(payload) >= {"horodatage", "statut", "décisions", "ordres"}
    assert all("action" in d and "raison" in d for d in payload["décisions"])
