"""Le rapport quotidien, en français simple.

Le reste du système parle en Sharpe, en z-scores et en points de base. C'est le bon
langage pour construire, et le mauvais pour décider. Ce module produit la seule sortie
qu'on lit tous les jours : ce que le bot a fait, ce qu'il détient, combien il a gagné ou
perdu, et s'il y a quelque chose à surveiller.

Trois règles d'écriture, parce qu'un rapport qu'on ne relit pas ne sert à rien :

* **Des euros et des pourcentages, pas des ratios.** « +142 € » se comprend ;
  « Sharpe 0,97 » demande un cours.
* **Ce qui a changé d'abord.** Une position stable ne demande aucune décision ; celle qui
  bouge, oui.
* **Les mauvaises nouvelles au même endroit que les bonnes.** Un rapport qui range les
  pertes ailleurs finit par ne plus être lu du tout.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Ce que chaque symbole est, en clair. Un ticker n'informe personne.
NOMS = {
    "QQQ": "Nasdaq 100", "SPY": "S&P 500", "IWM": "petites capis US",
    "EFA": "actions internationales", "EEM": "pays émergents",
    "TLT": "obligations d'État 20 ans", "IEF": "obligations d'État 10 ans",
    "LQD": "obligations d'entreprises", "HYG": "obligations à haut rendement",
    "GLD": "or", "SLV": "argent", "USO": "pétrole",
    "DBC": "matières premières", "UUP": "dollar américain", "VNQ": "immobilier US",
}

FAMILLES = {
    "Actions": ("QQQ", "SPY", "IWM", "EFA", "EEM"),
    "Obligations": ("TLT", "IEF", "LQD", "HYG"),
    "Matières premières": ("GLD", "SLV", "USO", "DBC"),
    "Devises et immobilier": ("UUP", "VNQ"),
}


def nom(symbole: str) -> str:
    return NOMS.get(symbole, symbole)


def famille(symbole: str) -> str:
    for nom_famille, membres in FAMILLES.items():
        if symbole in membres:
            return nom_famille
    return "Autre"


def _euros(fraction: float, capital: float) -> float:
    return fraction * capital


def positions(weights: dict[str, float], capital: float) -> pd.DataFrame:
    """Ce que le bot détient, en euros, par famille d'actifs."""
    lignes = []
    for symbole, poids in sorted(weights.items(), key=lambda kv: -abs(kv[1])):
        if abs(poids) < 1e-6:
            continue
        lignes.append({
            "famille": famille(symbole),
            "actif": nom(symbole),
            "code": symbole,
            "sens": "acheté" if poids > 0 else "vendu à découvert",
            "montant": round(_euros(abs(poids), capital), 2),
            "part": f"{abs(poids) * 100:.1f}%",
        })
    return pd.DataFrame(lignes)


def changements(avant: dict[str, float], apres: dict[str, float], capital: float,
                seuil: float = 0.005) -> pd.DataFrame:
    """Ce qui a bougé depuis hier — la seule partie qui demande une décision.

    Le seuil existe parce qu'un livre qui bouge de 0,1 % n'a rien décidé : il a dérivé.
    Lister ces lignes noie les vrais changements dans du bruit.
    """
    lignes = []
    for symbole in sorted(set(avant) | set(apres)):
        ancien, nouveau = avant.get(symbole, 0.0), apres.get(symbole, 0.0)
        delta = nouveau - ancien
        if abs(delta) < seuil:
            continue
        if ancien == 0 and nouveau != 0:
            action = "nouvelle position"
        elif nouveau == 0 and ancien != 0:
            action = "position fermée"
        elif abs(nouveau) > abs(ancien):
            action = "renforcé"
        else:
            action = "allégé"
        lignes.append({
            "actif": nom(symbole),
            "code": symbole,
            "action": action,
            "montant": round(_euros(abs(delta), capital), 2),
            "de": f"{ancien * 100:+.1f}%",
            "à": f"{nouveau * 100:+.1f}%",
        })
    return pd.DataFrame(lignes)


def resultat(store, run_id: str = "daily", capital_initial: float = 100_000.0) -> dict:
    """Combien le bot a gagné ou perdu, sur la période et depuis le début."""
    courbe = store.equity_curve(run_id)
    if courbe.empty:
        return {"statut": "aucun cycle enregistré", "cycles": 0}

    equity = float(courbe["equity"].iloc[-1])
    depart = float(courbe["equity"].iloc[0])
    pic = float(courbe["equity"].max())

    debut = pd.Timestamp(int(courbe["ts"].iloc[0]), unit="ms", tz="UTC")
    fin = pd.Timestamp(int(courbe["ts"].iloc[-1]), unit="ms", tz="UTC")
    jours = max((fin - debut).total_seconds() / 86400.0, 0.0)

    veille = float(courbe["equity"].iloc[-2]) if len(courbe) > 1 else depart

    return {
        "cycles": int(len(courbe)),
        "jours": round(jours, 1),
        "capital": round(equity, 2),
        "gain_total": round(equity - depart, 2),
        "gain_total_pct": round((equity / depart - 1) * 100, 2) if depart else 0.0,
        "gain_dernier_cycle": round(equity - veille, 2),
        "sous_le_pic": round((equity / pic - 1) * 100, 2) if pic else 0.0,
        "debut": debut.date().isoformat(),
        "fin": fin.date().isoformat(),
    }


def alertes(cycle_status: str, cycle_reason: str, res: dict, gross: float,
            data_age_days: float) -> list[str]:
    """Ce qu'il faut surveiller. Vide quand tout va bien, et c'est le cas normal."""
    out: list[str] = []

    if cycle_status == "stale":
        out.append("⛔ Les données ne se mettent plus à jour — le bot ne prend aucun "
                   "risque nouveau tant que ce n'est pas réglé.")
    elif cycle_status == "halted":
        out.append(f"⛔ Le bot est en pause : {cycle_reason}")
    elif cycle_status == "error":
        out.append(f"⛔ Le cycle a échoué : {cycle_reason}")

    if np.isfinite(data_age_days) and data_age_days > 2:
        out.append(f"⚠ Les prix datent de {data_age_days:.0f} jours.")

    if res.get("sous_le_pic", 0.0) <= -10:
        out.append(f"⚠ Le capital est {abs(res['sous_le_pic']):.0f}% sous son plus haut. "
                   "Le bot réduit automatiquement ses positions dans ce cas.")

    if res.get("cycles", 0) < 20:
        out.append(f"ℹ Seulement {res.get('cycles', 0)} cycles enregistrés. "
                   "Il en faut plusieurs mois avant que les chiffres veuillent dire "
                   "quelque chose.")

    if gross > 1.4:
        out.append(f"ℹ Le bot est investi à {gross * 100:.0f}% du capital, "
                   "proche de sa limite de 150%.")

    return out


def resume(cycle, store, run_id: str = "daily",
           capital_initial: float = 100_000.0) -> dict:
    """Tout le rapport, prêt à afficher."""
    res = resultat(store, run_id, capital_initial)
    capital = res.get("capital", capital_initial)

    # Ce qui était détenu au cycle précédent, pour dire ce qui a changé.
    avant: dict[str, float] = {}
    try:
        decisions = store.decisions(run_id, limit=400)
        if not decisions.empty:
            horodatages = sorted(decisions["ts"].unique())
            if len(horodatages) > 1:
                veille = decisions[decisions["ts"] == horodatages[-2]]
                avant = {r["symbol"]: float(r["allowed_weight"] or 0.0)
                         for _, r in veille.iterrows()}
    except Exception:  # noqa: BLE001 — un historique illisible ne doit pas bloquer le rapport
        avant = {}

    return {
        "resultat": res,
        "positions": positions(cycle.weights, capital),
        "changements": changements(avant, cycle.weights, capital),
        "alertes": alertes(cycle.status, cycle.reason, res, cycle.gross,
                           cycle.data_age_days),
        "investi_pct": round(cycle.gross * 100, 1),
        "liquidites_pct": round(max(0.0, 100 - cycle.gross * 100), 1),
    }
