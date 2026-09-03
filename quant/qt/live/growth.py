"""Combien de temps, en épargnant en plus de la stratégie, pour atteindre un revenu cible.

Deux choses distinguent ce module d'un calcul d'intérêts composés fait sur un coin de
table.

**Les rendements viennent de l'historique réel du livre, pas d'une moyenne lissée.**
Un calcul à 6,6 % par an constant cache les −18 % de pire perte que ce livre a
effectivement traversés. Le bootstrap par blocs rééchantillonne des tranches de trois
semaines de l'historique réel : la moyenne à long terme converge vers 6,6 %, mais chaque
trajectoire simulée contient ses propres creux, dans le bon ordre de grandeur et la bonne
autocorrélation — un mois de tendance ne se rééchantillonne pas jour par jour, ce qui
détruirait la persistance des tendances qui fait vivre une partie du signal.

**Le résultat est une distribution, pas un chiffre.** « Combien de temps pour atteindre
X ? » n'a pas de réponse unique quand le chemin est risqué : la même stratégie, au même
rythme de versement, met 12 ans dans un tirage favorable et 22 dans un tirage
défavorable. Donner un seul chiffre serait aussi trompeur que le calcul lisse qu'il
remplace.

Ce module ne teste aucune nouvelle stratégie. Il prend celle qui a déjà survécu à une
déflation honnête (`chemin_rentabilite.py`, `research_trend.py`) et répond à la question
qui reste : combien de temps, et à quel effort d'épargne.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21          # ~252 / 12


@dataclass
class ContributionPlan:
    """Le point de départ, l'effort d'épargne, et la cible."""

    start_capital: float
    monthly_contribution: float
    target_capital: float
    daily_returns: np.ndarray            # historique réel du livre, source du bootstrap
    block_days: int = TRADING_DAYS_PER_MONTH
    max_years: float = 50.0


def _block_bootstrap_returns(daily_returns: np.ndarray, n_paths: int, n_days: int,
                             block_days: int, rng: np.random.Generator) -> np.ndarray:
    """`n_paths` trajectoires de `n_days` rendements, assemblées par blocs de `block_days`.

    Rééchantillonner jour par jour effacerait l'autocorrélation d'une tendance : un mois
    haussier et un mois baissier seraient recombinés en bruit blanc, ce qui sous-estime
    à la fois les creux et les séries gagnantes que la stratégie exploite. Un bloc de
    trois semaines préserve la forme d'un épisode de marché tout en variant lequel est
    tiré.
    """
    n = len(daily_returns)
    if n <= block_days:
        raise ValueError(f"historique trop court ({n} jours) pour des blocs de {block_days}")

    n_blocks = -(-n_days // block_days)          # division entière arrondie au-dessus
    starts = rng.integers(0, n - block_days, size=(n_paths, n_blocks))
    offsets = np.arange(block_days)
    idx = starts[:, :, None] + offsets[None, None, :]
    return daily_returns[idx].reshape(n_paths, -1)[:, :n_days]


def simulate(plan: ContributionPlan, *, n_paths: int = 4000, seed: int = 0) -> dict:
    """Simule `n_paths` trajectoires et rend la distribution du temps pour atteindre la cible.

    Le versement mensuel s'ajoute APRÈS la croissance du mois, comme un virement fait en
    fin de mois plutôt qu'investi rétroactivement au premier jour — l'hypothèse la moins
    généreuse des deux, et la plus proche de comment un versement arrive réellement.
    """
    rng = np.random.default_rng(seed)
    max_days = int(plan.max_years * TRADING_DAYS_PER_YEAR)

    returns = _block_bootstrap_returns(plan.daily_returns, n_paths, max_days,
                                       plan.block_days, rng)
    growth = 1.0 + returns
    cumgrowth = np.cumprod(growth, axis=1)

    contrib_mask = np.zeros(max_days)
    contrib_mask[TRADING_DAYS_PER_MONTH - 1::TRADING_DAYS_PER_MONTH] = plan.monthly_contribution

    # wealth[t] = cumgrowth[t] * (capital_initial + somme des versements passés,
    # chacun ramené à sa valeur "en unités de cumgrowth au jour 0" avant d'être remis à
    # l'échelle du jour t). C'est la version vectorisée d'une boucle qui, à chaque mois,
    # ferait `capital = capital * croissance_du_mois + versement`.
    adjusted_contrib = contrib_mask[None, :] / cumgrowth
    cumsum_adjusted = np.cumsum(adjusted_contrib, axis=1)
    wealth = cumgrowth * (plan.start_capital + cumsum_adjusted)

    reached = wealth >= plan.target_capital
    any_reached = reached.any(axis=1)
    first_day = np.where(any_reached, reached.argmax(axis=1), -1)
    years = np.where(any_reached, (first_day + 1) / TRADING_DAYS_PER_YEAR, np.nan)

    # La pire perte subie par CHAQUE trajectoire jusqu'à ce qu'elle atteigne la cible (ou
    # sur toute la période simulée si elle ne l'atteint jamais) — pas la pire perte du
    # livre entier, qui dirait moins sur ce qu'un épargnant particulier traverse.
    running_peak = np.maximum.accumulate(wealth, axis=1)
    drawdown = wealth / running_peak - 1.0
    worst_drawdown = np.empty(n_paths)
    for p in range(n_paths):
        cutoff = first_day[p] + 1 if any_reached[p] else max_days
        worst_drawdown[p] = float(drawdown[p, :cutoff].min())

    reached_pct = float(any_reached.mean())
    valid_years = years[np.isfinite(years)]

    return {
        "atteint_dans_le_délai": reached_pct,
        "années_médiane": float(np.median(valid_years)) if len(valid_years) else np.nan,
        "années_p10": float(np.percentile(valid_years, 10)) if len(valid_years) else np.nan,
        "années_p90": float(np.percentile(valid_years, 90)) if len(valid_years) else np.nan,
        "pire_perte_médiane_en_chemin": float(np.median(worst_drawdown)),
        "pire_perte_p10_en_chemin": float(np.percentile(worst_drawdown, 10)),
        "n_paths": n_paths,
    }


def contribution_ladder(start_capital: float, target_capital: float,
                        daily_returns: np.ndarray, monthly_contributions,
                        *, n_paths: int = 4000, seed: int = 0,
                        max_years: float = 50.0) -> pd.DataFrame:
    """Le même calcul pour plusieurs niveaux de versement mensuel, en une table."""
    rows = []
    for contribution in monthly_contributions:
        plan = ContributionPlan(start_capital, float(contribution), target_capital,
                                daily_returns, max_years=max_years)
        stats = simulate(plan, n_paths=n_paths, seed=seed)
        rows.append({"versement_mensuel": contribution, **stats})
    return pd.DataFrame(rows)
