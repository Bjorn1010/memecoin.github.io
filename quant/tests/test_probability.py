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
    shrink_to_evidence,
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


# ------------------------------------------------------------- shrinkage
"""Isotonic regression will say 0.998 from sixteen observations, and the market then
rises 25% of the time. That was measured on the Nasdaq, and it is the defect these
tests pin down: a probability must not claim more than its evidence supports.
"""


def calibration_set(n: int = 1000, seed: int = 3):
    """A calibration sample whose scores span the range, with a 50% base rate."""
    rng = np.random.default_rng(seed)
    scores = rng.uniform(0.0, 1.0, n)
    outcomes = rng.integers(0, 2, n)
    return scores, outcomes


def test_a_confident_probability_from_a_thin_bucket_is_pulled_back():
    """The measured failure: an extreme probability standing on almost no observations."""
    # Ninety-nine per cent of the calibration set sits low; the top of the range holds
    # a handful of observations — exactly the shape that produced 0.998 on QQQ.
    rng = np.random.default_rng(5)
    scores = np.concatenate([rng.uniform(0.0, 0.5, 990), rng.uniform(0.95, 1.0, 10)])
    outcomes = np.concatenate([rng.integers(0, 2, 990), np.ones(10, dtype=int)])

    out = shrink_to_evidence(np.array([1.0]), np.array([0.97]), scores, outcomes,
                             prior_strength=50.0)
    assert out[0] < 0.65, "ten observations cannot support a claim of certainty"
    assert out[0] > 0.5, "but the evidence still points up, so it must not be erased"


def test_a_thick_bucket_keeps_its_probability():
    """Shrinkage must fade as evidence accumulates, or the model can never say anything."""
    scores, outcomes = calibration_set(4000)
    thin = shrink_to_evidence(np.array([0.8]), np.array([0.5]),
                              scores[:120], outcomes[:120], prior_strength=50.0)
    thick = shrink_to_evidence(np.array([0.8]), np.array([0.5]), scores, outcomes,
                               prior_strength=50.0)
    assert thick[0] > thin[0]
    assert thick[0] == pytest.approx(0.8, abs=0.05)


def test_shrinkage_is_monotone_in_the_prior():
    """A firmer prior must pull harder — nothing else about the knob is meaningful."""
    scores, outcomes = calibration_set()
    probe, probe_score = np.array([0.9]), np.array([0.5])
    pulled = [float(shrink_to_evidence(probe, probe_score, scores, outcomes,
                                       prior_strength=s)[0])
              for s in (0.0, 25.0, 100.0, 400.0)]
    assert pulled == sorted(pulled, reverse=True)
    assert pulled[0] == pytest.approx(0.9), "prior 0 must leave the probability alone"


def test_evidence_is_counted_where_the_score_lives_not_where_the_probability_lands():
    """The scale bug: isotonic maps scores onto probabilities, so the two do not align.

    Here every calibration score sits in 0.45-0.55 while the calibrated output is 0.95.
    Counting evidence in probability space finds an empty bucket and shrinks all the way
    to the base rate; counting it in score space finds the thousand observations that
    actually stand behind the number. The second is correct, and the first returns a
    plausible figure computed from the wrong place.
    """
    rng = np.random.default_rng(9)
    scores = rng.uniform(0.45, 0.55, 1000)
    outcomes = rng.integers(0, 2, 1000)

    out = float(shrink_to_evidence(np.array([0.95]), np.array([0.50]), scores, outcomes,
                                   prior_strength=50.0)[0])
    base = float(outcomes.mean())
    assert out > base + 0.2, "a thousand observations must not be shrunk to the base rate"


def test_a_score_in_a_region_never_seen_falls_back_to_the_base_rate():
    """No evidence means no claim — and it must not mean a NaN."""
    rng = np.random.default_rng(13)
    scores = rng.uniform(0.40, 0.60, 500)
    outcomes = (rng.uniform(size=500) < 0.6).astype(int)

    out = shrink_to_evidence(np.array([0.99]), np.array([0.59999]), scores, outcomes,
                             prior_strength=0.0)
    assert np.isfinite(out).all()


def test_no_divide_by_zero_warning_on_an_empty_bucket():
    """0/0 would give NaN, and every downstream comparison reads NaN as 'do not trade'
    — the right action for entirely the wrong reason, with no error to show for it."""
    scores = np.full(200, 0.55)
    outcomes = (np.arange(200) % 2).astype(int)
    with np.errstate(all="raise"):
        out = shrink_to_evidence(np.array([0.05, 0.55, 0.95]), np.array([0.05, 0.55, 0.95]),
                                 scores, outcomes, prior_strength=0.0)
    assert np.isfinite(out).all()


def test_an_empty_calibration_set_changes_nothing():
    probe = np.array([0.2, 0.8])
    out = shrink_to_evidence(probe, probe, np.array([]), np.array([]))
    assert out == pytest.approx(probe)


def test_shrinkage_reduces_calibration_error_by_the_predicted_amount():
    """The end-to-end claim, checked against the algebra rather than a round number.

    Shrinking by w = n/(n+s) moves every forecast a factor w toward the base rate, and
    the calibration error is a squared distance — so it must fall by w², not by "a lot".
    Here 2000 uniform scores spread over ten bins give n = 200 per bin against a prior
    of 50, so w = 0.8 and the error should land near 64% of what it was.

    Asserting a loose threshold instead would pass just as happily if the shrinkage were
    applied twice, or to the wrong bucket.
    """
    rng = np.random.default_rng(19)
    n = 2000
    scores = rng.uniform(0.0, 1.0, n)
    outcomes = rng.integers(0, 2, n)          # the score predicts nothing at all
    overconfident = scores                     # ...but the forecast claims it does

    before = brier_decomposition(overconfident, outcomes)["reliability"]
    after = brier_decomposition(
        shrink_to_evidence(overconfident, scores, scores, outcomes, prior_strength=50.0),
        outcomes)["reliability"]

    w = (n / 10) / (n / 10 + 50.0)
    assert after == pytest.approx(before * w**2, rel=0.15)


def test_shrinkage_is_strongest_exactly_where_the_evidence_is_thinnest():
    """On real data the extreme probabilities came from buckets of 4, 10 and 16.

    The whole point is that the pull is local: a claim standing on a handful of
    observations must be pulled hard, while a claim standing on a thousand is left
    nearly alone. A global shrink toward the base rate would pass a "calibration
    improved" test and would be the wrong fix.
    """
    rng = np.random.default_rng(23)
    # A crowded middle and a nearly empty top — the shape a boosted model produces.
    scores = np.concatenate([rng.uniform(0.30, 0.70, 1900), rng.uniform(0.90, 1.00, 12)])
    outcomes = np.concatenate([rng.integers(0, 2, 1900), np.ones(12, dtype=int)])

    crowded = float(shrink_to_evidence(np.array([0.75]), np.array([0.50]),
                                       scores, outcomes, prior_strength=50.0)[0])
    thin = float(shrink_to_evidence(np.array([0.75]), np.array([0.95]),
                                    scores, outcomes, prior_strength=50.0)[0])
    base = float(outcomes.mean())

    assert abs(crowded - 0.75) < abs(thin - 0.75), "the thin bucket must be pulled harder"
    assert abs(thin - base) < abs(crowded - base)


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
