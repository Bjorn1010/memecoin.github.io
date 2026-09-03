"""Ce qu'un petit compte peut réellement acheter — et ce que ça coûte.

Un backtest raisonne en poids : 7,9 % sur le S&P 500. Un courtier vend des actions
entières. Sur 100 000 € la différence est un arrondi ; sur 500 € elle détruit la
stratégie, et elle la détruit en silence, parce qu'un moteur qui travaille en poids
n'a aucune raison de lever une erreur.

Mesuré sur le livre réel de ce dépôt, avec 500 € :

    positions demandées        15
    positions achetables        3   (UUP, HYG, DBC)
    capital réellement investi  196 € sur les 729 € voulus

Les douze positions manquantes ne sont pas les moins importantes : ce sont les plus
chères à l'action, ce qui n'a aucun rapport avec leur rôle dans le portefeuille. Le
S&P 500 à 765 $ l'action disparaît, l'or à 403 $ disparaît, le dollar à 28 $ reste. Le
livre qui survit est le livre des actions bon marché — un critère de sélection qui
n'apparaît nulle part dans la stratégie et que personne n'a choisi.

C'est la raison d'être de ce module : rendre la contrainte visible et chiffrable, au
lieu de la laisser agir dans le dos du backtest.

## Les deux mondes

* **Actions fractionnées.** Trading 212, Interactive Brokers, Trade Republic et d'autres
  les proposent aujourd'hui. Le livre est alors reproductible presque exactement, à la
  poussière près.
* **Actions entières.** Le courtier classique. En dessous de quelques dizaines de
  milliers d'euros, le livre reproduit n'est plus celui qui a été mesuré.

`implement` répond à la question dans les deux cas et rend l'écart, plutôt que de
choisir à la place de l'utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Implementation:
    """Le livre réellement achetable, et de combien il s'écarte de celui voulu."""

    capital: float
    fractional: bool
    shares: dict[str, float] = field(default_factory=dict)
    target_weights: dict[str, float] = field(default_factory=dict)
    actual_weights: dict[str, float] = field(default_factory=dict)
    invested: float = 0.0
    wanted: float = 0.0
    cash_left: float = 0.0
    commission_paid: float = 0.0

    @property
    def positions_wanted(self) -> int:
        return sum(1 for w in self.target_weights.values() if abs(w) > 1e-6)

    @property
    def positions_held(self) -> int:
        return sum(1 for s in self.shares.values() if abs(s) > 0)

    @property
    def weight_error(self) -> float:
        """Somme des écarts absolus de poids. Zéro = le livre voulu, exactement.

        C'est la mesure qui compte, et pas le nombre de positions manquantes : perdre une
        ligne à 1,6 % n'est pas perdre une ligne à 15 %.
        """
        keys = set(self.target_weights) | set(self.actual_weights)
        return float(sum(abs(self.actual_weights.get(k, 0.0) - self.target_weights.get(k, 0.0))
                         for k in keys))

    def to_frame(self) -> pd.DataFrame:
        keys = sorted(set(self.target_weights) | set(self.actual_weights),
                      key=lambda k: -abs(self.target_weights.get(k, 0.0)))
        return pd.DataFrame([{
            "symbole": k,
            "poids_voulu": self.target_weights.get(k, 0.0),
            "poids_obtenu": self.actual_weights.get(k, 0.0),
            "actions": self.shares.get(k, 0.0),
            "écart": self.actual_weights.get(k, 0.0) - self.target_weights.get(k, 0.0),
        } for k in keys])


def implement(
    weights: pd.Series | dict[str, float],
    prices: pd.Series | dict[str, float],
    capital: float,
    *,
    fractional: bool = False,
    commission_per_order: float = 0.0,
    fx_rate: float = 1.0,
) -> Implementation:
    """Traduire des poids en actions réellement achetables.

    `fx_rate` convertit le prix (souvent en dollars) vers la devise du capital. Il vaut
    1,0 par défaut et il est explicite plutôt que caché : un ETF américain acheté avec
    des euros coûte le prix en dollars divisé par le taux, et ignorer ce facteur fausse
    le nombre d'actions dans le sens qui flatte — vers plus d'actions achetables.

    Les positions courtes sont refusées ici : un petit compte ne vend pas à découvert,
    et faire semblant que si produirait un livre reproductible sur le papier et
    impossible chez le courtier. Elles sont laissées à zéro et comptées dans l'écart.
    """
    w = dict(weights.items()) if isinstance(weights, pd.Series) else dict(weights)
    p = dict(prices.items()) if isinstance(prices, pd.Series) else dict(prices)

    shares: dict[str, float] = {}
    actual: dict[str, float] = {}
    invested = 0.0
    wanted = 0.0
    orders = 0

    for symbol, weight in w.items():
        weight = float(weight)
        wanted += abs(weight) * capital
        price = float(p.get(symbol, np.nan)) / fx_rate if fx_rate else np.nan
        if not np.isfinite(price) or price <= 0 or weight <= 0:
            # A short, a missing price, or a zero target: nothing is bought, and the
            # gap shows up in weight_error rather than being quietly dropped.
            shares[symbol] = 0.0
            actual[symbol] = 0.0
            continue

        budget = capital * weight
        qty = budget / price if fractional else float(int(budget // price))
        cost = qty * price
        if qty > 0:
            orders += 1
        shares[symbol] = qty
        invested += cost

    commission = orders * commission_per_order
    for symbol, qty in shares.items():
        price = float(p.get(symbol, np.nan)) / fx_rate if fx_rate else np.nan
        actual[symbol] = (qty * price / capital) if np.isfinite(price) and capital > 0 else 0.0

    return Implementation(
        capital=capital, fractional=fractional, shares=shares,
        target_weights={k: float(v) for k, v in w.items()}, actual_weights=actual,
        invested=invested, wanted=wanted,
        cash_left=capital - invested - commission, commission_paid=commission,
    )


def capital_ladder(
    weights: pd.Series | dict[str, float],
    prices: pd.Series | dict[str, float],
    capitals=(500, 1_000, 2_500, 5_000, 10_000, 25_000, 100_000),
    *,
    fx_rate: float = 1.0,
) -> pd.DataFrame:
    """À partir de quel capital le livre devient-il reproductible ?

    La seule façon honnête de répondre à « est-ce que ça marche avec 500 € » : montrer
    la courbe, pas un seuil inventé.
    """
    rows = []
    for capital in capitals:
        whole = implement(weights, prices, float(capital), fractional=False, fx_rate=fx_rate)
        frac = implement(weights, prices, float(capital), fractional=True, fx_rate=fx_rate)
        rows.append({
            "capital": capital,
            "positions voulues": whole.positions_wanted,
            "positions obtenues": whole.positions_held,
            "investi / voulu": (whole.invested / whole.wanted) if whole.wanted else np.nan,
            "erreur de poids (entières)": whole.weight_error,
            "erreur de poids (fractionnées)": frac.weight_error,
        })
    return pd.DataFrame(rows)
