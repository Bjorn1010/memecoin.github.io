"""Une journée de papier-trading, enregistrée pour de bon.

C'est l'étape 1 du chemin : faire tourner la stratégie mesurée sur des données réelles,
jour après jour, et vérifier que l'écart avec le backtest reste sous 0,5 point de CAGR.
Tant que cet écart n'est pas mesuré sur du vrai temps qui passe, le 6,63 % annuel reste
un chiffre de backtest — et un backtest est une hypothèse, pas un relevé.

Ce que fait le script, dans l'ordre :

1. restaure le journal versionné dans une base de travail — sans quoi une machine neuve
   repart de sa valeur de départ, courbe plate et drawdown nul ;
2. rafraîchit les cours (Yahoo, gratuit) ;
3. fait tourner un cycle de décision complet ;
4. ajoute une ligne au journal et réécrit le rapport lisible ;
5. affiche ce qui a été décidé et pourquoi.

Aucun ordre réel n'est passé. Ce dépôt ne contient aucun adaptateur de courtier.

Lancer :  .venv/bin/python -u scripts/paper_day.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from qt.config import CONFIG
from qt.data.catalog import Catalog
from qt.live.journal import Journal, performance
from qt.live.orchestrator import DailySpec, run_cycle
from qt.live.rapport import NOMS
from qt.live.retail import capital_ladder, implement
from qt.live.state import Store

RAPPORT = Path(__file__).resolve().parents[1] / "journal" / "RAPPORT.md"
# The account this trial is actually for. The strategy was measured in weights, which is
# scale-free; whether those weights can be *bought* with this much money is not, and it
# is checked on every cycle rather than assumed — see `qt.live.retail`.
CAPITAL = 500.0
FX_RATE = 1.08          # EUR/USD: the ETFs are priced in dollars, the account is in euros
# Measured in scripts/research_trend.py over 2010-2026 on this exact configuration.
# The paper trial exists to check the live path lands near it, so it is a constant here
# rather than something recomputed — a moving benchmark cannot be missed.
BACKTEST_CAGR = 0.0663
TOLERANCE = 0.005          # the 0.5 point of CAGR that defines success for step 1


def last_prices(symbols) -> dict[str, float]:
    cat = Catalog()
    out = {}
    for symbol in symbols:
        bars = cat.read_indexed("eod", "yahoo", symbol)
        if not bars.empty:
            out[symbol] = float(bars["close"].iloc[-1])
    return out


def buyability(weights: dict[str, float]) -> tuple[object, object, object]:
    """Le livre voulu est-il achetable avec ce capital ? Vérifié, pas supposé.

    Sans ça, l'essai mesurerait un livre de quinze lignes pendant que le compte ne peut
    en tenir que trois — et le relevé serait juste, et il ne dirait rien sur ce que
    l'utilisateur peut faire.
    """
    prices = last_prices(weights)
    whole = implement(weights, prices, CAPITAL, fractional=False, fx_rate=FX_RATE)
    frac = implement(weights, prices, CAPITAL, fractional=True, fx_rate=FX_RATE)
    ladder = capital_ladder(weights, prices, fx_rate=FX_RATE)
    return whole, frac, ladder


def write_report(journal: Journal, result, spec: DailySpec) -> None:
    perf = performance(journal)
    df = journal.frame()

    lines = [
        "# Papier-trading — relevé",
        "",
        "Généré par `scripts/paper_day.py`. Aucun ordre réel n'a jamais été passé :",
        "ce dépôt ne contient aucun adaptateur de courtier.",
        "",
        f"**Dernier cycle** : {pd.Timestamp(result.ts).strftime('%Y-%m-%d %H:%M UTC')} "
        f"— statut `{result.status}`",
        "",
        "## Où en est l'essai",
        "",
        "| | |",
        "|---|---|",
        f"| jours enregistrés | {perf.get('jours', 0)} |",
    ]
    if perf.get("jours", 0) >= 2:
        lines += [
            f"| du | {perf['du']} |",
            f"| au | {perf['au']} |",
            f"| équité | {perf['équité']:,.2f} |".replace(",", " "),
            f"| rendement total | {perf['rendement_total'] * 100:+.2f} % |",
            f"| pire perte | {perf['pire_perte'] * 100:.2f} % |",
            f"| jours non-`ok` | {perf['jours_halted']} |",
        ]
    if "sharpe" in perf:
        gap = perf["rendement_annualisé"] - BACKTEST_CAGR
        verdict = "✅ dans la tolérance" if abs(gap) <= TOLERANCE else "❌ hors tolérance"
        lines += [
            f"| rendement annualisé | {perf['rendement_annualisé'] * 100:.2f} % |",
            f"| volatilité | {perf['volatilité_annualisée'] * 100:.2f} % |",
            f"| Sharpe | {perf['sharpe']:.2f} |",
            "",
            "## Étape 1 : le live colle-t-il au backtest ?",
            "",
            f"- backtest 2010-2026 : **{BACKTEST_CAGR * 100:.2f} %** par an",
            f"- papier, annualisé : **{perf['rendement_annualisé'] * 100:.2f} %**",
            f"- écart : **{gap * 100:+.2f} point** (tolérance ±{TOLERANCE * 100:.1f}) — {verdict}",
        ]
    else:
        lines += [
            "",
            "## Étape 1 : le live colle-t-il au backtest ?",
            "",
            f"Pas encore mesurable. {perf.get('note', '')}",
            "",
            "Annualiser deux semaines de rendements produit un nombre sans information,",
            "et c'est toujours celui qu'on cite. Il est retenu jusqu'à 60 jours.",
        ]

    if result.weights:
        whole, frac, ladder = buyability(result.weights)
        lines += [
            "", f"## Ce livre est-il achetable avec {CAPITAL:.0f} € ?", "",
            "| | actions entières | actions fractionnées |",
            "|---|---|---|",
            f"| positions obtenues | **{whole.positions_held} / {whole.positions_wanted}** "
            f"| {frac.positions_held} / {frac.positions_wanted} |",
            f"| capital investi | {whole.invested:.0f} € sur {whole.wanted:.0f} € voulus "
            f"| {frac.invested:.0f} € |",
            f"| erreur de poids | **{whole.weight_error:.3f}** | {frac.weight_error:.3f} |",
            "",
            "L'erreur de poids est la somme des écarts entre le livre voulu et le livre",
            "obtenu. Zéro = la stratégie mesurée, exactement. Au-dessus de ~0,2 ce n'est",
            "plus la même stratégie, quel que soit le nom qu'on lui donne.",
            "",
            "Les lignes qui disparaissent en actions entières ne sont pas les moins utiles :",
            "ce sont les plus chères à l'action, ce qui n'a aucun rapport avec leur rôle",
            "dans le portefeuille. Un critère de sélection que personne n'a choisi.",
            "",
            "### À partir de quel capital le livre est-il reproductible ?",
            "",
            "| capital | positions obtenues | investi / voulu | erreur (entières) "
            "| erreur (fractionnées) |",
            "|---|---|---|---|---|",
            *(f"| {int(r['capital']):,} € ".replace(",", " ")
              + f"| {int(r['positions obtenues'])} / {int(r['positions voulues'])} "
                f"| {r['investi / voulu'] * 100:.0f} % "
                f"| {r['erreur de poids (entières)']:.3f} "
                f"| {r['erreur de poids (fractionnées)']:.3f} |"
              for _, r in ladder.iterrows()),
            "",
            f"**Conséquence pratique** : avec {CAPITAL:.0f} €, il faut un courtier qui",
            "propose les **actions fractionnées** (Trading 212, Interactive Brokers,",
            "Trade Republic et d'autres). Chez un courtier classique il faudrait environ",
            "25 000 € pour tenir les quinze lignes.",
        ]

        lines += ["", "## Livre actuel", "", "| marché | poids |", "|---|---|"]
        for symbol, weight in sorted(result.weights.items(),
                                     key=lambda kv: -abs(kv[1]))[:20]:
            if abs(weight) > 1e-4:
                lines.append(f"| {NOMS.get(symbol, symbol)} ({symbol}) | {weight:+.2%} |")

    if not df.empty:
        lines += ["", "## Dix derniers cycles", "",
                  "| date | statut | équité | perte | brut |", "|---|---|---|---|---|"]
        for _, row in df.tail(10).iloc[::-1].iterrows():
            lines.append(f"| {row['date']} | {row['status']} | {float(row['equity']):,.2f} "
                         f"| {float(row['drawdown']) * 100:.2f} % "
                         f"| {float(row['gross']):.2f} |".replace(",", " "))

    lines += ["", "---", "",
              f"Configuration : `{json.dumps(spec.to_meta()['trend'], sort_keys=True)}`, "
              f"mélange tendance {spec.trend_blend:.0%}, cible de volatilité "
              f"{spec.target_vol:.0%}, capital de départ {spec.starting_equity:,.0f}."
              .replace(",", " "),
              ""]

    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    spec = DailySpec(starting_equity=CAPITAL)
    journal = Journal()

    store = Store(CONFIG.runs_dir / "daily.sqlite")
    restored = journal.restore(store)
    print(f"journal : {restored} cycles restaurés depuis {journal.path}"
          if restored else "journal : vide — premier cycle de l'essai")

    result = run_cycle(spec, store=store, do_refresh=True)

    print(f"\nstatut     : {result.status}")
    if result.reason:
        print(f"raison     : {result.reason}")
    print(f"équité     : {result.equity:,.2f}".replace(",", " "))
    print(f"perte      : {result.drawdown * 100:.2f} %")
    print(f"exposition : {result.gross:.2f}")
    if result.weights:
        held = {k: v for k, v in result.weights.items() if abs(v) > 1e-4}
        print(f"\nlivre ({len(held)} positions) :")
        for symbol, weight in sorted(held.items(), key=lambda kv: -abs(kv[1])):
            print(f"  {NOMS.get(symbol, symbol):24s} {symbol:5s} {weight:+7.2%}")

        whole, frac, _ = buyability(result.weights)
        print(f"\nachetable avec {CAPITAL:.0f} € ?")
        print(f"  actions entières     : {whole.positions_held}/{whole.positions_wanted} "
              f"positions, erreur de poids {whole.weight_error:.3f}")
        print(f"  actions fractionnées : {frac.positions_held}/{frac.positions_wanted} "
              f"positions, erreur de poids {frac.weight_error:.3f}")
        if whole.weight_error > 0.2:
            print("  -> chez un courtier sans actions fractionnées, ce n'est pas la")
            print("     stratégie mesurée qui serait tradée. Il en faut un qui les propose.")

    # An errored cycle is recorded too. A journal that only contains the good days is
    # not a record of what happened, and the failures are the rows that explain a gap.
    journal.append(result)
    write_report(journal, result, spec)
    print(f"\njournal   -> {journal.path}")
    print(f"rapport   -> {RAPPORT}")

    perf = performance(journal)
    if "sharpe" in perf:
        gap = perf["rendement_annualisé"] - BACKTEST_CAGR
        print(f"\nétape 1 : écart live/backtest {gap * 100:+.2f} pt "
              f"(tolérance ±{TOLERANCE * 100:.1f})")
    else:
        print(f"\nétape 1 : {perf.get('note', 'pas encore mesurable')}")

    return 0 if result.status in ("ok", "halted", "warming_up") else 1


if __name__ == "__main__":
    sys.exit(main())
