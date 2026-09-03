"""Le chemin réel vers 6 000 €/mois : pas une stratégie plus agressive, un plan d'épargne.

Ce script répond à une reformulation, et c'est la bonne. Chercher une stratégie qui
transforme 500 € en 6 000 €/mois immédiatement, c'est chercher un rendement de
plusieurs milliers de pour cent par an — mesuré impossible dans ce dépôt, à plusieurs
reprises (`chemin_rentabilite.py`). Investir de plus en plus, à mesure que le capital
grandit, jusqu'à ce que le revenu suive, est une question complètement différente : ce
n'est plus une question de stratégie, c'est une question d'épargne et de temps.

La stratégie ne change pas. C'est celle qui a déjà survécu à une déflation honnête :
risk parity + 30 % de tendance, quinze ETF, Sharpe 0,97, 6,6 % par an, mesuré sur 2010-
2026 avec les coûts. Ce script ne cherche pas mieux — il applique l'épargne à ce qui
marche déjà, et chiffre combien de temps ça prend.

Le calcul n'est pas un taux d'intérêt composé lisse. Chaque trajectoire simulée est
rééchantillonnée par blocs depuis l'historique réel du livre (`qt/live/growth.py`), donc
elle traverse ses propres creux — pas la moyenne qui les efface.

Lancer :  .venv/bin/python -u scripts/plan_croissance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chemin_rentabilite import measured_book, stats_of  # noqa: E402
from qt.data.catalog import Catalog  # noqa: E402
from qt.live.growth import ContributionPlan, contribution_ladder, simulate  # noqa: E402

pd.set_option("display.width", 240)

START_CAPITAL = 500.0
TARGET_PER_MONTH = 6_000.0
MONTHLY_CONTRIBUTIONS = (100, 250, 500, 1_000, 2_000, 3_000)
N_PATHS = 3_000
MAX_YEARS = 45.0          # au-delà, verser plus est la seule réponse utile de toute façon


def fr(value: float, decimals: int = 0) -> str:
    """Séparateur de milliers français, pour ne pas laisser {:,} écrire 6552 en 6,552."""
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def main() -> None:
    cat = Catalog()

    print("=" * 88)
    print("LE POINT DE DÉPART : LA STRATÉGIE QUI MARCHE, TELLE QU'ELLE EST\n")
    result = measured_book(cat)
    s = stats_of(result)
    daily_returns = result.equity.pct_change().dropna().to_numpy()

    print(f"  risk parity + 30 % de tendance, 15 ETF, {s['years']:.1f} ans, coûts inclus")
    print(f"  rendement annuel : {s['cagr'] * 100:.2f} %   ·   volatilité : {s['vol'] * 100:.2f} %"
          f"   ·   Sharpe : {s['sharpe']:.2f}   ·   pire perte : {s['max_dd'] * 100:.1f} %")
    print("\n  Aucune stratégie plus agressive n'est proposée ici : chacune de celles")
    print("  testées ailleurs dans ce dépôt (scalping, day trading, régimes) est mesurée")
    print("  perdante ou non significative après coûts. Celle-ci est la seule qui reste,")
    print("  et le plan est construit dessus, pas sur un espoir de mieux.")

    target_capital = TARGET_PER_MONTH * 12 / s["cagr"]
    print("\n" + "=" * 88)
    print(f"LA CIBLE : LE CAPITAL QUI PRODUIT {fr(TARGET_PER_MONTH)} € PAR MOIS\n")
    print(f"  {fr(TARGET_PER_MONTH)} €/mois = {fr(TARGET_PER_MONTH * 12)} €/an")
    print(f"  au rendement mesuré de {s['cagr'] * 100:.2f} % : il faut {fr(target_capital)} € de capital")
    print("\n  Pour situer ce chiffre, au rendement d'autres références :")
    for label, r in (("S&P 500, long terme", 0.10), ("Buffett, 1965-2023", 0.198),
                     ("Medallion, record absolu, fonds fermé", 0.66)):
        print(f"    {label:42s} {r * 100:5.1f} % -> {fr(TARGET_PER_MONTH * 12 / r):>14s} €")

    # -------------------------------------------------------------- sans versement
    print("\n" + "=" * 88)
    print("POURQUOI L'ÉPARGNE EST OBLIGATOIRE : LE CAPITAL SEUL, SANS RIEN AJOUTER\n")
    # Question fermée arithmétiquement, pas simulée : le bootstrap ne change pas la
    # réponse à une croissance composée déterministe sur cet horizon, et une simulation
    # à 200 ans coûterait plusieurs gigaoctets de mémoire pour rien.
    years_solo = np.log(target_capital / START_CAPITAL) / np.log(1 + s["cagr"])
    print(f"  {fr(START_CAPITAL)} € seuls, réinvestis au rendement mesuré de "
          f"{s['cagr'] * 100:.2f} % par an, sans un euro ajouté :")
    print(f"  {years_solo:.0f} ans pour atteindre {fr(target_capital)} €.")
    print("\n  Ce n'est pas un défaut de la stratégie, c'est l'arithmétique de partir")
    print("  petit : les intérêts composés ont besoin de plusieurs générations sur un")
    print("  capital de 500 €. C'est exactement pourquoi verser régulièrement est")
    print("  obligatoire, pas optionnel.")

    # ----------------------------------------------------------------- avec versement
    print("\n" + "=" * 88)
    print("LE PLAN : VERSER CHAQUE MOIS, EN PLUS DE LA CROISSANCE DE LA STRATÉGIE\n")
    print(f"  Chaque ligne simule {N_PATHS:,} trajectoires rééchantillonnées depuis l'historique"
         .replace(",", " "))
    print("  réel du livre — pas une moyenne lisse. « médiane » est le résultat typique ;")
    print("  « p10 / p90 » bornent 80 % des trajectoires, le mauvais et le bon tirage.\n")

    table = contribution_ladder(START_CAPITAL, target_capital, daily_returns,
                                MONTHLY_CONTRIBUTIONS, n_paths=N_PATHS, max_years=MAX_YEARS)
    show = table.copy()
    show["versement_mensuel"] = show["versement_mensuel"].map(lambda v: f"{fr(v)} €")
    show["atteint_dans_le_délai"] = (show["atteint_dans_le_délai"] * 100).map(lambda v: f"{v:.0f} %")
    for col in ("années_médiane", "années_p10", "années_p90"):
        show[col] = table[col].map(lambda v: f"{v:.1f}" if np.isfinite(v) else f"> {MAX_YEARS:.0f}")
    for col in ("pire_perte_médiane_en_chemin", "pire_perte_p10_en_chemin"):
        show[col] = (table[col] * 100).map(lambda v: f"{v:.0f} %")
    print(show.to_string(index=False))

    print("\n  « pire_perte_p10_en_chemin » : dans un tirage sur dix, la perte la plus")
    print("  profonde traversée avant d'atteindre la cible est au moins celle-ci. C'est")
    print("  ce qu'il faut être prêt à tenir sans arrêter les versements ni vendre au")
    print("  pire moment — arrêter là referait repartir le compteur à zéro.")

    # ------------------------------------------------------------- effort require
    reachable = table[table["atteint_dans_le_délai"] >= 0.5]
    print("\n" + "=" * 88)
    print("CE QUE ÇA VEUT DIRE, DIRECTEMENT\n")
    if reachable.empty:
        print(f"  Même à {fr(MONTHLY_CONTRIBUTIONS[-1])} €/mois, moins de la moitié des")
        print(f"  trajectoires atteignent la cible en {MAX_YEARS:.0f} ans. Il faut soit verser plus,")
        print("  soit revoir l'objectif à la baisse, soit les deux.")
    else:
        best = reachable.iloc[0]
        print(f"  À partir de {fr(best['versement_mensuel'])} €/mois versés en plus de la")
        print(f"  stratégie, la moitié des trajectoires atteignent {fr(TARGET_PER_MONTH)} €/mois")
        print(f"  de revenu en {best['années_médiane']:.0f} ans — entre {best['années_p10']:.0f} et "
              f"{best['années_p90']:.0f} ans selon que le marché a été favorable ou non.")

    print(f"\n  Ce plan ne dépend d'aucune stratégie non mesurée ici. Il dépend de deux")
    print(f"  choses vérifiables : que la stratégie continue de se comporter comme sur")
    print(f"  2010-2026 — ce que l'essai papier en cours (`journal/RAPPORT.md`) vérifie")
    print(f"  en ce moment sur des données réelles — et que les versements soient tenus.")
    print(f"  Le second est entièrement sous votre contrôle ; le premier ne l'est pas,")
    print(f"  et personne ne peut le garantir, ici ou ailleurs.")


if __name__ == "__main__":
    main()
