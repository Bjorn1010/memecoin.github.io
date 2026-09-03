"""Le bot fait du day trading en papier, et chaque trade est enregistré.

Ce script existe pour remplacer une affirmation par un relevé. La recherche de ce dépôt
conclut que le day trading de détail ne paie pas ; plutôt que de vous demander de me
croire, le bot le fait, sur des données réelles, et le résultat s'écrit tout seul dans un
fichier versionné que personne ne peut retoucher sans que ça se voie dans l'historique
git.

Le relevé est cumulatif : chaque exécution rejoue toutes les séances disponibles, et les
trades déjà connus ne sont pas comptés deux fois.

Aucun ordre réel n'est passé. Ce dépôt ne contient aucun adaptateur de courtier.

Lancer :  .venv/bin/python -u scripts/intraday_day.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from qt.data.catalog import Catalog
from qt.data.sources import yahoo
from qt.live.intraday_paper import NOMS, IntradaySpec, simulate, summarise

JOURNAL = Path(__file__).resolve().parents[1] / "journal" / "day_trading.csv"
RAPPORT = Path(__file__).resolve().parents[1] / "journal" / "RAPPORT_DAY_TRADING.md"
OBJECTIF_MENSUEL = 10_000.0


def load_journal() -> pd.DataFrame:
    if not JOURNAL.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(JOURNAL)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def merge(existing: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    """Ajoute les trades nouveaux, sans jamais dupliquer les anciens.

    L'identité d'un trade est (symbole, horodatage d'entrée) : le moteur est
    déterministe, donc rejouer les mêmes barres redonne exactement les mêmes trades, et
    la déduplication est exacte plutôt qu'approximative.
    """
    fresh = pd.DataFrame(rows)
    if existing.empty:
        return fresh.sort_values(["entrée", "symbole"]).reset_index(drop=True)
    if fresh.empty:
        return existing

    key = ["symbole", "entrée"]
    known = set(map(tuple, existing[key].astype(str).to_numpy()))
    mask = [tuple(r) not in known for r in fresh[key].astype(str).to_numpy()]
    added = fresh[mask]
    if added.empty:
        return existing
    return (pd.concat([existing, added], ignore_index=True)
            .sort_values(["entrée", "symbole"]).reset_index(drop=True))


def write_report(journal: pd.DataFrame, spec: IntradaySpec, stats: dict) -> None:
    lines = [
        "# Day trading en papier — relevé",
        "",
        "Généré par `scripts/intraday_day.py`. **Aucun ordre réel n'a jamais été passé** :",
        "ce dépôt ne contient aucun adaptateur de courtier.",
        "",
        "Ce relevé existe pour remplacer une affirmation par des chiffres. La recherche de",
        "ce dépôt conclut que le day trading de détail ne paie pas ; le bot le fait quand",
        "même, sur données réelles, et le résultat s'écrit ici tout seul.",
        "",
        "## Le relevé",
        "",
        "| | |",
        "|---|---|",
    ]
    if stats.get("trades", 0) == 0:
        lines.append("| trades | aucun trade terminé pour l'instant |")
    else:
        lines += [
            f"| trades terminés | {stats['trades']} |",
            f"| séances | {stats['séances']} |",
            f"| gain **brut** moyen | {stats['brut_moyen_bp']:+.3f} bp |",
            f"| coût moyen (fourchette) | {stats['coût_moyen_bp']:.3f} bp |",
            f"| gain **net** moyen | **{stats['net_moyen_bp']:+.3f} bp** |",
            f"| gain net **médian** | **{stats['net_médian_bp']:+.3f} bp** |",
            f"| trades gagnants | {stats['% gagnants'] * 100:.1f} % |",
            f"| résultat cumulé | **{stats['total_eur']:+.2f} €** |",
            f"| par heure de marché | {stats['eur_par_heure']:+.4f} € |",
            f"| t de Student | {stats['t']:.2f} |",
            f"| sorties au stop | {stats['stops']} |",
        ]
        lines += [
            "",
            "La ligne qui décide est **gain net moyen**. Le brut est ce que montrent les",
            "vendeurs de formations ; la fourchette est ce que le marché prélève entre les",
            "deux, à chaque aller-retour, sans exception.",
            "",
            "## Le test que personne ne montre : la moyenne tient-elle à quelques coups ?",
            "",
            "Une moyenne positive portée par une poignée de trades n'est pas un avantage,",
            "c'est une loterie gagnée. On retire les meilleurs trades et on regarde ce qui",
            "reste :",
            "",
            "| | gain net moyen |",
            "|---|---|",
            f"| tous les {stats['trades']} trades | {stats['net_moyen_bp']:+.3f} bp |",
            f"| sans les **5** meilleurs | {stats.get('sans_les_5_meilleurs_bp', float('nan')):+.3f} bp |",
            f"| sans les **10** meilleurs | {stats.get('sans_les_10_meilleurs_bp', float('nan')):+.3f} bp |",
            "",
            f"Et le trade **médian** rapporte {stats['net_médian_bp']:+.3f} bp : c'est ce que",
            "fait le trade typique, par opposition à la moyenne que quelques coups tirent",
            "vers le haut. Si la médiane est négative, la stratégie perd presque à chaque",
            "fois et se rattrape rarement — ce n'est pas la même chose qu'un avantage.",
            "",
            "## Face à l'objectif",
            "",
            f"Objectif annoncé : **{OBJECTIF_MENSUEL:,.0f} € par mois**.".replace(",", " "),
            "",
        ]
        per_month = stats["eur_par_heure"] * 6.5 * 21
        lines += [
            f"- rythme actuel : **{per_month:+.2f} € par mois** sur {spec.capital:.0f} € de capital",
            f"- il en faudrait : {OBJECTIF_MENSUEL:,.0f} €".replace(",", " "),
        ]
        if per_month > 0:
            lines.append(f"- facteur manquant : **x{OBJECTIF_MENSUEL / per_month:,.0f}**"
                         .replace(",", " "))
        else:
            lines.append("- le rythme actuel est **négatif** : aucun facteur ne comble "
                         "un écart en partant d'une perte.")

    if not journal.empty:
        lines += ["", "## Vingt derniers trades", "",
                  "| entrée | actif | sens | brut bp | coût bp | net bp | net € | sortie |",
                  "|---|---|---|---|---|---|---|---|"]
        for _, r in journal.tail(20).iloc[::-1].iterrows():
            lines.append(
                f"| {str(r['entrée'])[:16]} | {NOMS.get(r['symbole'], r['symbole'])} "
                f"| {r['sens']} | {float(r['brut_bp']):+.2f} | {float(r['coût_bp']):.2f} "
                f"| {float(r['net_bp']):+.2f} | {float(r['net_eur']):+.3f} "
                f"| {r['motif_sortie']} |")

    lines += ["", "---", "",
              f"Règles : fade d'extrême, fenêtre {spec.window} barres, seuil "
              f"{spec.threshold} écarts-types, détention max {spec.hold_bars} barres, "
              f"stop {spec.stop_sigma} écarts-types, {spec.position_eur:.0f} € par trade, "
              f"maximum {spec.max_trades_per_session} trades par séance. "
              f"Actifs : {', '.join(spec.symbols)}.",
              "",
              "Aucune position ne traverse la clôture. L'entrée se fait à l'ouverture de la",
              "barre **suivant** le signal : entrer à la clôture de la barre du signal",
              "serait un look-ahead d'une barre, et sur des barres de 5 minutes il vaut à",
              "lui seul plus que l'avantage recherché.",
              ""]

    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    spec = IntradaySpec()
    cat = Catalog()

    print(f"== rafraîchissement des barres 5 minutes ({', '.join(spec.symbols)})")
    try:
        counts = yahoo.ingest_intraday(cat, spec.symbols, interval="5m")
        print(counts.to_string(index=False))
    except Exception as exc:  # noqa: BLE001 - une panne de flux ne doit pas tout arrêter
        print(f"   échec du rafraîchissement : {type(exc).__name__}: {exc}")
        print("   on continue sur les barres déjà en cache")

    rows: list[dict] = []
    all_trades = []
    for symbol in spec.symbols:
        bars = cat.read_indexed("eod_5m", "yahoo", symbol)
        if bars.empty:
            print(f"   {symbol} : aucune barre")
            continue
        trades = simulate(bars, symbol, spec)
        all_trades.extend(trades)
        rows.extend(t.to_row() for t in trades)
        print(f"   {symbol} : {len(trades)} trades terminés sur {len(bars)} barres")

    journal = merge(load_journal(), rows)
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    journal.to_csv(JOURNAL, index=False)

    stats = summarise(all_trades, spec)
    print()
    if stats.get("trades", 0) == 0:
        print("aucun trade terminé")
    else:
        print(f"trades           : {stats['trades']} sur {stats['séances']} séances")
        print(f"gain brut moyen  : {stats['brut_moyen_bp']:+.3f} bp")
        print(f"coût moyen       : {stats['coût_moyen_bp']:.3f} bp")
        print(f"gain NET moyen   : {stats['net_moyen_bp']:+.3f} bp")
        print(f"trades gagnants  : {stats['% gagnants'] * 100:.1f} %")
        print(f"résultat cumulé  : {stats['total_eur']:+.2f} €")
        print(f"par heure        : {stats['eur_par_heure']:+.4f} €")
        print(f"t de Student     : {stats['t']:.2f}")

        per_month = stats["eur_par_heure"] * 6.5 * 21
        print(f"\nrythme mensuel   : {per_month:+.2f} € "
              f"(objectif {OBJECTIF_MENSUEL:,.0f} €)".replace(",", " "))

    write_report(journal, spec, stats)
    print(f"\njournal -> {JOURNAL}")
    print(f"rapport -> {RAPPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
