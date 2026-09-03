"""Un moteur de day trading en papier, reproductible d'un bout à l'autre.

Ce module existe pour une raison précise : la recherche de ce dépôt dit que le day
trading de détail ne paie pas, et une affirmation de ma part ne vaut pas un relevé. Ici
le bot fait du day trading pour de vrai — signal, entrée, stop, sortie avant la clôture,
fourchette payée — sur des données réelles, sans argent. Le relevé s'accumule et tranche
tout seul, ligne par ligne.

## Ce qui a déjà été mesuré, et que ce module met à l'épreuve du temps réel

* prédiction de direction horaire : 49,96 % hors échantillon, il en faudrait 53,3 %
* stratégie intraday à seuils : meilleure configuration hors échantillon Sharpe −0,14,
  Sharpe déflaté 0,000015, coûts = 204 % du brut
* cinq stratégies de retour à la moyenne : toutes négatives après fourchette
* fade d'extrême, la seule à avoir un avantage brut (+1,93 bp) : −4,12 bp hors
  échantillon une fois la fourchette payée

Le signal retenu ici est ce fade d'extrême, précisément parce que c'est le meilleur
candidat mesuré. Ce n'est pas une stratégie à laquelle je crois : c'est l'hypothèse à
réfuter, mise en papier pour être réfutée par des données que personne n'a choisies.

## Le choix de conception qui rend le relevé fiable

Le conteneur est éphémère et le script tourne à des heures irrégulières. Un moteur qui
tiendrait une position « en mémoire » entre deux exécutions perdrait son état à chaque
recyclage, et le relevé serait faux sans que rien ne le signale.

Donc rien n'est tenu en mémoire. **Toute la séance est recalculée depuis les barres à
chaque exécution.** Le même jeu de barres donne toujours exactement les mêmes trades,
quelle que soit l'heure d'exécution, et relancer trois fois ne crée pas trois relevés
différents. Le journal ne stocke que des trades terminés.

## Ce qui est payé

La fourchette, aux deux jambes, au tarif de l'actif. Pas de commission : les ETF
américains n'en portent pas chez les grands courtiers. C'est le poste qui décide du
résultat, donc il est explicite et par actif plutôt que moyenné.

## Ce qui n'est jamais fait

Aucun ordre réel. Ce module ne connaît aucun courtier et n'a aucun moyen d'en joindre un.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Demi-fourchette par actif, en points de base, pour un ordre au marché de détail.
# Estimations, pas mesures : les barres Yahoo ne portent pas de cotations. Volontairement
# pessimistes sur les lignes peu liquides.
HALF_SPREAD_BPS = {
    "SPY": 0.25, "QQQ": 0.35, "IWM": 0.80, "EFA": 1.00, "EEM": 1.50,
    "TLT": 0.80, "IEF": 0.80, "LQD": 1.00, "HYG": 1.00, "GLD": 0.60,
    "SLV": 1.50, "USO": 2.50, "DBC": 4.00, "UUP": 3.00, "VNQ": 1.50,
}

NOMS = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "GLD": "or", "IWM": "petites capis US",
        "EEM": "pays émergents", "SLV": "argent", "TLT": "obligations 20 ans"}


@dataclass
class IntradaySpec:
    """Les règles. Un seul jeu pour tous les actifs, jamais ajusté actif par actif.

    Ajuster les seuils par actif sur soixante séances trouve un signal à tous les coups.
    Quinze actifs sous les mêmes règles sont quinze tests du même pari ; quinze actifs
    sous quinze réglages sont quinze exercices de mémorisation.
    """

    # Les deux ETF les plus serrés du livre. Le day trading paie la fourchette deux fois
    # par trade, donc élargir l'univers aux lignes larges ajoute du coût et pas de la
    # diversification : DBC à 8 bp d'aller-retour ne peut structurellement pas être
    # tradé à la journée, quel que soit le signal.
    symbols: tuple[str, ...] = ("SPY", "QQQ")
    window: int = 24               # barres pour la moyenne et l'écart-type
    threshold: float = 1.5         # écarts-types avant de prendre le contre
    hold_bars: int = 6             # 30 minutes sur des barres de 5 minutes
    stop_sigma: float = 2.0        # coupe à 2 écarts-types contre soi
    capital: float = 500.0
    position_eur: float = 100.0    # engagé par trade
    max_trades_per_session: int = 6

    def to_meta(self) -> dict:
        return {"symbols": list(self.symbols), "window": self.window,
                "threshold": self.threshold, "hold_bars": self.hold_bars,
                "stop_sigma": self.stop_sigma, "position_eur": self.position_eur,
                "max_trades_per_session": self.max_trades_per_session}


@dataclass
class Trade:
    symbol: str
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int                      # +1 long, -1 short
    entry_price: float
    exit_price: float
    gross_bp: float
    cost_bp: float
    net_bp: float
    net_eur: float
    exit_reason: str               # durée | stop | clôture

    def to_row(self) -> dict:
        return {
            "symbole": self.symbol,
            "entrée": self.entry_ts.isoformat(),
            "sortie": self.exit_ts.isoformat(),
            "sens": "achat" if self.side > 0 else "vente",
            "prix_entrée": round(self.entry_price, 4),
            "prix_sortie": round(self.exit_price, 4),
            "brut_bp": round(self.gross_bp, 4),
            "coût_bp": round(self.cost_bp, 4),
            "net_bp": round(self.net_bp, 4),
            "net_eur": round(self.net_eur, 4),
            "motif_sortie": self.exit_reason,
        }


def zscore(close: pd.Series, window: int) -> pd.Series:
    mean = close.rolling(window, min_periods=window // 2).mean()
    sd = close.rolling(window, min_periods=window // 2).std(ddof=0)
    return (close - mean) / sd.replace(0.0, np.nan)


def simulate(bars: pd.DataFrame, symbol: str, spec: IntradaySpec) -> list[Trade]:
    """Rejoue toutes les séances disponibles et rend les trades terminés.

    Déterministe : les mêmes barres donnent toujours les mêmes trades. C'est ce qui rend
    l'exécution idempotente et le relevé impossible à fausser en relançant le script.

    L'entrée se fait à l'OUVERTURE de la barre suivant le signal. Le signal se lit sur la
    clôture de la barre t ; un ordre passé après cette clôture ne peut pas s'exécuter à ce
    prix-là. Entrer à la clôture de t serait un look-ahead d'une barre — sur des barres de
    5 minutes, il représente à lui seul plus que l'avantage recherché.
    """
    if bars.empty or len(bars) < spec.window + spec.hold_bars + 2:
        return []

    close = bars["close"].astype("float64")
    open_ = bars["open"].astype("float64")
    high = bars["high"].astype("float64")
    low = bars["low"].astype("float64")
    session = (bars["session_id"] if "session_id" in bars.columns
               else bars.index.normalize().astype("int64"))

    z = zscore(close, spec.window)
    sd_price = close.rolling(spec.window, min_periods=spec.window // 2).std(ddof=0)
    half_spread = HALF_SPREAD_BPS.get(symbol, 2.0) / 1e4

    z_a, open_a, high_a, low_a, close_a = (z.to_numpy(), open_.to_numpy(), high.to_numpy(),
                                           low.to_numpy(), close.to_numpy())
    sd_a, sess_a = sd_price.to_numpy(), np.asarray(session)
    index = bars.index

    trades: list[Trade] = []
    i = 0
    n = len(bars)
    per_session: dict = {}

    while i < n - 1:
        if not np.isfinite(z_a[i]) or not np.isfinite(sd_a[i]) or sd_a[i] <= 0:
            i += 1
            continue

        side = -1 if z_a[i] > spec.threshold else 1 if z_a[i] < -spec.threshold else 0
        if side == 0:
            i += 1
            continue

        entry_bar = i + 1
        current = sess_a[entry_bar]
        if current != sess_a[i]:
            # Le signal est né sur la dernière barre de la séance : l'entrée tomberait
            # le lendemain, ce qui n'est plus du day trading mais un pari overnight.
            i += 1
            continue
        if per_session.get(current, 0) >= spec.max_trades_per_session:
            i += 1
            continue

        entry_price = float(open_a[entry_bar])
        stop_distance = spec.stop_sigma * float(sd_a[i])
        stop_price = entry_price - side * stop_distance

        exit_bar, exit_price, reason = None, None, ""
        for j in range(entry_bar, min(entry_bar + spec.hold_bars + 1, n)):
            if sess_a[j] != current:
                exit_bar, exit_price, reason = j - 1, float(close_a[j - 1]), "clôture"
                break
            # Le stop est vérifié sur les extrêmes de la barre, pas sur sa clôture : une
            # barre qui touche le stop puis revient a bel et bien sorti la position.
            if side > 0 and low_a[j] <= stop_price:
                exit_bar, exit_price, reason = j, stop_price, "stop"
                break
            if side < 0 and high_a[j] >= stop_price:
                exit_bar, exit_price, reason = j, stop_price, "stop"
                break
            if j == entry_bar + spec.hold_bars:
                exit_bar, exit_price, reason = j, float(close_a[j]), "durée"
                break

        if exit_bar is None:
            # La série s'arrête avant la sortie : la position est encore ouverte, donc
            # elle n'est pas un trade terminé et n'entre pas au relevé. L'enregistrer en
            # la valorisant au dernier prix connu gonflerait le relevé des positions qui
            # vont bien et masquerait celles qui vont mal.
            break

        gross_bp = side * (exit_price / entry_price - 1.0) * 1e4
        cost_bp = 2 * half_spread * 1e4
        net_bp = gross_bp - cost_bp
        trades.append(Trade(
            symbol=symbol, entry_ts=index[entry_bar], exit_ts=index[exit_bar], side=side,
            entry_price=entry_price, exit_price=exit_price, gross_bp=gross_bp,
            cost_bp=cost_bp, net_bp=net_bp,
            net_eur=net_bp / 1e4 * spec.position_eur, exit_reason=reason,
        ))
        per_session[current] = per_session.get(current, 0) + 1
        i = exit_bar + 1

    return trades


def summarise(trades: list[Trade], spec: IntradaySpec) -> dict:
    """Ce que le relevé dit, avec le seul chiffre qui décide : le net après fourchette."""
    if not trades:
        return {"trades": 0, "note": "aucun trade terminé"}

    net_bp = np.array([t.net_bp for t in trades])
    gross_bp = np.array([t.gross_bp for t in trades])
    net_eur = np.array([t.net_eur for t in trades])
    sessions = len({t.entry_ts.date() for t in trades})
    hours = sessions * 6.5

    sd = float(net_bp.std(ddof=1)) if len(net_bp) > 1 else np.nan
    t_stat = (float(net_bp.mean() / sd * np.sqrt(len(net_bp)))
              if np.isfinite(sd) and sd > 0 else np.nan)

    # Le diagnostic qui décide, et celui qu'on ne montre jamais.
    #
    # Une moyenne positive portée par une poignée de trades n'est pas un avantage, c'est
    # une loterie gagnée. Mesuré sur ce moteur : moyenne +2,291 bp, mais médiane
    # **−0,861 bp** — le trade typique perd. En retirant les dix meilleurs sur 656, la
    # moyenne tombe à +0,397 bp. Dix trades sur six cent cinquante-six portent 83 % du
    # résultat, et rien ne dit qu'ils se reproduiront.
    #
    # Un avantage réel survit à l'ablation de ses meilleurs coups. Celui-ci non, donc le
    # chiffre est publié à côté de la moyenne plutôt que laissé à qui pense à le calculer.
    ranked = np.sort(net_bp)[::-1]
    without = {f"sans_les_{k}_meilleurs_bp": (float(ranked[k:].mean())
                                              if len(ranked) > k + 10 else np.nan)
               for k in (5, 10)}

    return {
        "trades": len(trades),
        "séances": sessions,
        "brut_moyen_bp": float(gross_bp.mean()),
        "coût_moyen_bp": float(np.mean([t.cost_bp for t in trades])),
        "net_moyen_bp": float(net_bp.mean()),
        "net_médian_bp": float(np.median(net_bp)),
        "% gagnants": float((net_bp > 0).mean()),
        "total_eur": float(net_eur.sum()),
        "eur_par_heure": float(net_eur.sum() / hours) if hours else np.nan,
        "t": t_stat,
        "stops": sum(1 for t in trades if t.exit_reason == "stop"),
        **without,
    }
