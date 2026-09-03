"""Calibrated probabilities, and the gate that decides whether to act on one.

Two failures are guarded here, and both produce a confident number rather than an error.

A classifier's raw score is not a probability: gradient boosting says 0.85 for outcomes
that happen 0.65 of the time, and position size follows confidence, so the error is
always in the expensive direction.

And a probability can be perfectly calibrated and completely useless. A model that
outputs the base rate for every observation scores flawlessly on every calibration
metric and cannot produce a single position. Resolution is the term that separates the
two, and it is the one that is almost never reported.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.live.scalp_bot import ScalpBotSpec, SkillGate
from qt.models.probability import (
    brier_decomposition,
    brier_score,
    edge_from_probability,
    probability_report,
    reliability_curve,
    required_probability,
)


# ------------------------------------------------------------------- scoring
def test_brier_of_a_perfect_forecast_is_zero():
    outcomes = np.array([1, 0, 1, 1, 0])
    assert brier_score(outcomes.astype("float64"), outcomes) == 0.0


def test_brier_of_a_coin_flip_is_a_quarter():
    rng = np.random.default_rng(2)
    outcomes = rng.integers(0, 2, 5000)
    assert brier_score(np.full(5000, 0.5), outcomes) == pytest.approx(0.25)


def test_decomposition_adds_back_to_the_brier_score():
    """Brier = reliability − resolution + uncertainty. If it does not, the terms are wrong."""
    rng = np.random.default_rng(7)
    p = rng.uniform(0.1, 0.9, 4000)
    outcomes = (rng.uniform(size=4000) < p).astype(int)

    d = brier_decomposition(p, outcomes, n_bins=10)
    rebuilt = d["reliability"] - d["resolution"] + d["uncertainty"]
    assert rebuilt == pytest.approx(d["brier"], abs=0.01)


def test_a_constant_forecast_has_zero_resolution():
    """The trap: perfectly calibrated, perfectly useless, and it looks excellent.

    A model that always predicts the base rate has no calibration error at all. Only
    resolution reveals that it has said nothing.
    """
    rng = np.random.default_rng(11)
    outcomes = (rng.uniform(size=4000) < 0.47).astype(int)
    base = float(outcomes.mean())

    d = brier_decomposition(np.full(4000, base), outcomes)
    assert d["resolution"] == pytest.approx(0.0, abs=1e-6)
    assert d["reliability"] == pytest.approx(0.0, abs=1e-3)


def test_resolution_is_positive_when_the_forecast_discriminates():
    rng = np.random.default_rng(13)
    n = 4000
    informative = rng.uniform(size=n)
    p = np.where(informative > 0.5, 0.8, 0.2)
    outcomes = (rng.uniform(size=n) < p).astype(int)

    d = brier_decomposition(p, outcomes)
    assert d["resolution"] > 0.05
    assert d["brier"] < d["uncertainty"], "a discriminating forecast must beat the base rate"


# --------------------------------------------------------------- reliability
def test_reliability_curve_exposes_overconfidence():
    """The failure that matters: 0.90 predicted, 0.50 realised."""
    rng = np.random.default_rng(17)
    n = 3000
    p = rng.choice([0.1, 0.5, 0.9], size=n)
    # The outcome ignores the forecast entirely: every bucket resolves at 50%.
    outcomes = rng.integers(0, 2, n)

    curve = reliability_curve(p, outcomes, n_bins=10)
    high = curve[curve["probabilité_prédite"] > 0.8]
    assert not high.empty
    assert float(high["écart"].iloc[0]) > 0.3, "overconfidence must show as a positive gap"

    low = curve[curve["probabilité_prédite"] < 0.2]
    assert float(low["écart"].iloc[0]) < -0.3


# ------------------------------------------------------------------- report
@pytest.fixture
def useless_probabilities():
    """A forecast that varies but predicts nothing — the realistic failure."""
    rng = np.random.default_rng(23)
    n = 2000
    p = pd.Series(np.clip(rng.normal(0.47, 0.12, n), 0.01, 0.99))
    outcomes = pd.Series(rng.integers(0, 2, n))
    return p, outcomes


def test_report_names_a_model_that_loses_to_the_base_rate(useless_probabilities):
    p, outcomes = useless_probabilities
    report = probability_report(p, outcomes)
    assert report.diagnostics["gain_sur_le_taux_de_base"] < 0
    assert "taux de base" in report.diagnostics["verdict"]


def test_report_flags_a_probability_that_never_moves():
    n = 2000
    rng = np.random.default_rng(29)
    p = pd.Series(np.full(n, 0.47) + rng.normal(0, 0.002, n))
    outcomes = pd.Series((rng.uniform(size=n) < 0.47).astype(int))

    report = probability_report(p, outcomes)
    assert report.diagnostics["amplitude_5e_95e"] < 0.05
    assert "sans contenu" in report.diagnostics["verdict"]


def test_report_recognises_a_forecast_with_real_skill():
    rng = np.random.default_rng(31)
    n = 4000
    signal = rng.uniform(size=n)
    p = pd.Series(np.clip(0.5 + 0.35 * (signal - 0.5) * 2, 0.05, 0.95))
    outcomes = pd.Series((rng.uniform(size=n) < p).astype(int))

    report = probability_report(p, outcomes)
    assert report.diagnostics["gain_sur_le_taux_de_base"] > 0
    assert report.diagnostics["resolution"] > 0.01
    assert not report.reliability.empty


# ----------------------------------------------------------------- decision
def test_required_probability_rises_with_cost():
    """At 1:1 odds and no cost the break-even is a coin flip; cost pushes it up."""
    assert required_probability(1.0, 0.0) == pytest.approx(0.5)
    assert required_probability(1.0, 0.4) == pytest.approx(0.7)
    # Better odds lower the bar.
    assert required_probability(2.0, 0.0) == pytest.approx(1 / 3)


def test_edge_is_zero_exactly_at_the_required_probability():
    for payoff, cost in ((1.0, 0.0), (1.5, 0.2), (2.0, 0.35)):
        p = required_probability(payoff, cost)
        assert edge_from_probability(p, payoff, cost) == pytest.approx(0.0, abs=1e-12)


def test_edge_is_negative_below_the_threshold():
    p = required_probability(1.0, 0.4)
    assert edge_from_probability(p - 0.05, 1.0, 0.4) < 0
    assert edge_from_probability(p + 0.05, 1.0, 0.4) > 0


# --------------------------------------------------------------------- gate
def test_gate_blocks_a_probability_with_no_resolution():
    """The measured case: resolution 0.0003 on QQQ against an uncertainty of 0.249."""
    gate = SkillGate(ScalpBotSpec())
    allowed, reason = gate.evaluate({
        "resolution": 0.0003, "amplitude_5e_95e": 0.35,
        "gain_sur_le_taux_de_base": 0.01,
    })
    assert not allowed
    assert "distinguer" in reason


def test_gate_blocks_a_flat_probability():
    gate = SkillGate(ScalpBotSpec())
    allowed, reason = gate.evaluate({
        "resolution": 0.02, "amplitude_5e_95e": 0.01,
        "gain_sur_le_taux_de_base": 0.01,
    })
    assert not allowed
    assert "plate" in reason


def test_gate_blocks_a_model_worse_than_the_base_rate():
    gate = SkillGate(ScalpBotSpec())
    allowed, reason = gate.evaluate({
        "resolution": 0.02, "amplitude_5e_95e": 0.35,
        "gain_sur_le_taux_de_base": -0.02,
    })
    assert not allowed
    assert "taux de base" in reason


def test_gate_allows_a_probability_that_passes_all_three():
    gate = SkillGate(ScalpBotSpec())
    allowed, reason = gate.evaluate({
        "resolution": 0.03, "amplitude_5e_95e": 0.30,
        "gain_sur_le_taux_de_base": 0.015,
    })
    assert allowed
    assert "resolution" in reason


def test_gate_can_be_disabled_but_says_so():
    """Turning it off must be visible in the record, not silent."""
    gate = SkillGate(ScalpBotSpec(require_skill=False))
    allowed, reason = gate.evaluate({"resolution": 0.0, "amplitude_5e_95e": 0.0,
                                     "gain_sur_le_taux_de_base": -1.0})
    assert allowed
    assert "désactivé" in reason
