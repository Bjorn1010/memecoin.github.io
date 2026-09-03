"""Le simulateur de croissance par versements : ce qui doit tenir pour que le plan compte.

Un plan d'épargne calculé sur un taux composé lisse cache les creux que la stratégie a
réellement traversés. Ces tests vérifient que le bootstrap par blocs les restitue, que le
résultat est une distribution et non un chiffre unique, et que l'arithmétique de base
(plus on verse, plus vite on arrive) ne se dérègle jamais silencieusement.
"""

from __future__ import annotations

import numpy as np
import pytest

from qt.live.growth import ContributionPlan, contribution_ladder, simulate


def flat_returns(rate: float = 0.0002, n: int = 3000) -> np.ndarray:
    """Rendements constants : la trajectoire est alors un intérêt composé exact,
    ce qui donne un cas où le résultat du simulateur peut être vérifié analytiquement."""
    return np.full(n, rate)


def noisy_returns(mean: float = 0.066 / 252, vol: float = 0.068 / np.sqrt(252),
                  n: int = 252 * 15, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, vol, n)


# --------------------------------------------------------------------- exactitude
def test_a_flat_return_matches_compound_interest_exactly():
    """Sur des rendements constants, la simulation doit retrouver la formule fermée.

    C'est le seul cas où « combien de temps pour atteindre X » a une réponse exacte, et
    c'est donc le test qui garantit que le mécanisme de versement est correctement
    composé plutôt qu'additionné en linéaire par erreur.
    """
    rate = 0.0003
    returns = flat_returns(rate, n=252 * 40)
    plan = ContributionPlan(start_capital=1000.0, monthly_contribution=0.0,
                            target_capital=1000.0 * (1 + rate) ** 252,
                            daily_returns=returns, max_years=5.0)
    result = simulate(plan, n_paths=50, seed=1)
    assert result["années_médiane"] == pytest.approx(1.0, abs=0.02)


def test_contributions_compound_not_just_accumulate():
    """Sans intérêt (rendement nul), N mois de versement M doivent donner exactement
    capital initial + N*M — le test qui isole le mécanisme de versement de celui de
    la croissance, en désactivant la seconde."""
    returns = flat_returns(0.0, n=252 * 10)
    plan = ContributionPlan(start_capital=100.0, monthly_contribution=50.0,
                            target_capital=100.0 + 50.0 * 12, daily_returns=returns,
                            max_years=3.0)
    result = simulate(plan, n_paths=20, seed=2)
    assert result["années_médiane"] == pytest.approx(1.0, abs=0.05)


# ---------------------------------------------------------------------- monotonie
def test_a_larger_contribution_never_takes_longer():
    """L'arithmétique la plus basique : verser plus ne peut jamais ralentir."""
    returns = noisy_returns()
    table = contribution_ladder(500.0, 200_000.0, returns, (100, 500, 2000),
                                n_paths=800, seed=5, max_years=40.0)
    years = table["années_médiane"].to_numpy()
    finite = np.where(np.isfinite(years), years, np.inf)
    assert (np.diff(finite) <= 0).all()


def test_a_higher_target_never_arrives_sooner():
    returns = noisy_returns()
    plan_near = ContributionPlan(500.0, 300.0, 50_000.0, returns, max_years=40.0)
    plan_far = ContributionPlan(500.0, 300.0, 500_000.0, returns, max_years=40.0)
    near = simulate(plan_near, n_paths=800, seed=7)
    far = simulate(plan_far, n_paths=800, seed=7)
    assert far["années_médiane"] >= near["années_médiane"]


def test_more_starting_capital_never_takes_longer():
    returns = noisy_returns()
    plan_small = ContributionPlan(500.0, 300.0, 100_000.0, returns, max_years=40.0)
    plan_big = ContributionPlan(50_000.0, 300.0, 100_000.0, returns, max_years=40.0)
    small = simulate(plan_small, n_paths=800, seed=9)
    big = simulate(plan_big, n_paths=800, seed=9)
    assert big["années_médiane"] <= small["années_médiane"]


# --------------------------------------------------------------------- distribution
def test_the_result_is_a_spread_not_a_single_number():
    """Le point du bootstrap : deux tirages du même plan ne donnent pas la même
    trajectoire, donc p10 et p90 doivent être distincts sur un historique volatil."""
    returns = noisy_returns()
    plan = ContributionPlan(500.0, 500.0, 300_000.0, returns, max_years=40.0)
    result = simulate(plan, n_paths=2000, seed=11)
    assert result["années_p90"] > result["années_p10"]
    assert result["années_p10"] <= result["années_médiane"] <= result["années_p90"]


def test_block_bootstrap_preserves_the_historical_worst_drawdown_order_of_magnitude():
    """Un livre dont la pire perte réelle est -18% ne doit pas produire des trajectoires
    lisses de +2% de creux max : ce serait la signature d'un rééchantillonnage qui a
    détruit l'autocorrélation des épisodes de marché."""
    returns = noisy_returns(mean=0.066 / 252, vol=0.15 / np.sqrt(252))  # plus volatil
    plan = ContributionPlan(500.0, 200.0, 1_000_000.0, returns, max_years=40.0)
    result = simulate(plan, n_paths=1500, seed=13)
    assert result["pire_perte_médiane_en_chemin"] < -0.02


def test_an_unreachable_target_reports_zero_not_a_crash():
    """Un objectif hors de portée dans le délai simulé doit se voir dans le taux
    d'atteinte, jamais planter ni renvoyer une année inventée."""
    returns = flat_returns(0.00001, n=2000)              # croissance quasi nulle
    plan = ContributionPlan(500.0, 10.0, 50_000_000.0, returns, max_years=5.0)
    result = simulate(plan, n_paths=200, seed=17)
    assert result["atteint_dans_le_délai"] == pytest.approx(0.0)
    assert np.isnan(result["années_médiane"])


def test_starting_already_past_the_target_reaches_immediately():
    returns = noisy_returns()
    plan = ContributionPlan(1_000_000.0, 0.0, 500_000.0, returns, max_years=10.0)
    result = simulate(plan, n_paths=50, seed=19)
    assert result["atteint_dans_le_délai"] == pytest.approx(1.0)
    assert result["années_médiane"] < 0.01


# -------------------------------------------------------------------------- ladder
def test_the_ladder_returns_one_row_per_contribution_level():
    returns = noisy_returns()
    table = contribution_ladder(500.0, 100_000.0, returns, (100, 500, 1000),
                                n_paths=300, seed=23, max_years=30.0)
    assert list(table["versement_mensuel"]) == [100, 500, 1000]
    assert len(table) == 3


def test_a_too_short_history_is_rejected_rather_than_silently_wrapping():
    """Un historique plus court que la taille de bloc ne peut pas fournir de blocs
    valides : mieux vaut une erreur explicite qu'un bootstrap qui rééchantillonne du
    vide."""
    plan = ContributionPlan(500.0, 100.0, 10_000.0, np.array([0.001, 0.002]),
                            block_days=21)
    with pytest.raises(ValueError, match="historique trop court"):
        simulate(plan, n_paths=10)
