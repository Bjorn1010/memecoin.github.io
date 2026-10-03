"""Research hypotheses: every retail strategy written as a falsifiable claim.

An entry is only kept if its claim can be tested statistically: it names a signal, a
condition, a horizon, a measurable target and the risk taken. The parameter grid is
declared here, before any data is seen, and capped by the protocol (≤ 9 configurations).
The baseline is the canonical textbook setting — never the best of the grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable

from . import strategies as S


@dataclass(frozen=True)
class Hypothesis:
    name: str
    family: str
    func: Callable | None
    kind: str  # "trade" | "xs" | "pair" | "deferred"
    claim: str  # the falsifiable statement
    signal: str
    condition: str
    horizon: str
    target: str
    risk: str
    rationale: str  # why it might work (economic / behavioural)
    falsification: str  # the conditions under which it should stop working
    baseline: dict = field(default_factory=dict)
    grid: tuple[dict, ...] = ()
    requires_volume: bool = False
    deferred_reason: str = ""

    def configs(self) -> list[dict]:
        """Baseline first, then the declared grid (deduplicated)."""
        out = [dict(self.baseline)]
        for g in self.grid:
            cfg = {**self.baseline, **g}
            if cfg not in out:
                out.append(cfg)
        return out


def _grid(**axes) -> tuple[dict, ...]:
    keys = list(axes)
    return tuple(dict(zip(keys, vals)) for vals in product(*axes.values()))


H = Hypothesis

HYPOTHESES: list[Hypothesis] = [
    # ------------------------------------------------------------------ trend
    H("sma_cross", "trend", S.sma_cross, "trade",
      "Quand la moyenne 50 jours est au-dessus de la 200 jours, le rendement des jours suivants est supérieur à celui des jours où elle est en dessous, après coûts.",
      "SMA(fast) − SMA(slow)", "aucune", "tant que le signe ne change pas", "rendement net par jour exposé > 0",
      "drawdown pendant les retournements ; whipsaws en marché sans tendance",
      "Sous-réaction des investisseurs à l'information, puis comportement grégaire (Moskowitz, Ooi, Pedersen 2012).",
      "Marchés sans tendance persistante, retournements en V (2020), coûts de portage élevés.",
      {"fast": 50, "slow": 200},
      tuple(g for g in _grid(fast=[20, 50, 100], slow=[100, 200, 300]) if g["fast"] < g["slow"])),
    H("ema_cross", "trend", S.ema_cross, "trade",
      "Le croisement EMA rapide/lente prédit le signe du rendement futur au-delà des coûts.",
      "EMA(fast) − EMA(slow)", "aucune", "jusqu'au croisement inverse", "rendement net > 0",
      "whipsaws, turnover élevé sur les petites périodes",
      "Même mécanisme que le croisement SMA, réaction plus rapide.",
      "Faible autocorrélation des rendements ; coûts qui mangent les signaux courts.",
      {"fast": 12, "slow": 26},
      tuple({"fast": f, "slow": s} for f, s in [(5, 20), (8, 21), (20, 50), (30, 100), (50, 150)])),
    H("donchian", "trend", S.donchian, "trade",
      "Une clôture au-delà du plus haut (bas) des N derniers jours est suivie d'une continuation qui dépasse le coût d'un stop à 2 ATR.",
      "clôture > plus haut N jours (hors aujourd'hui)", "aucune", "jusqu'à la cassure inverse sur M jours ou le stop", "espérance nette par trade > 0",
      "faux breakouts, stop 2 ATR", "Règles des Tortues : les grandes tendances paient les nombreuses petites pertes.",
      "Marchés en range, breakouts sans suivi, gaps contre la position.",
      {"entry": 20, "exit": 10, "stop_atr": 2.0},
      tuple({"entry": e, "exit": x} for e, x in [(20, 20), (55, 20), (55, 55), (100, 50), (10, 5)])),
    H("tsmom", "trend", S.tsmom, "trade",
      "Le signe du rendement des L derniers jours prédit le signe du rendement du jour suivant (momentum de série temporelle).",
      "signe du rendement sur L jours", "aucune", "quotidien", "rendement net > 0",
      "retournements brutaux de régime", "Prime documentée sur 58 marchés futures depuis 1985 (MOP 2012).",
      "Krachs de momentum (2009), marchés plats.",
      {"lookback": 252}, tuple({"lookback": l} for l in [21, 63, 126, 378])),
    H("adx_trend", "trend", S.adx_trend, "trade",
      "Quand l'ADX dépasse le seuil, la direction des DI prédit le rendement futur.",
      "+DI vs −DI", "ADX > seuil", "tant que la condition tient", "rendement net > 0",
      "entrée tardive : l'ADX confirme quand la tendance est déjà avancée",
      "Filtrer les périodes sans tendance devrait améliorer le rapport signal/bruit.",
      "L'ADX est retardé ; si les tendances sont courtes, il entre au sommet.",
      {"period": 14, "threshold": 25}, _grid(period=[14, 20], threshold=[20, 25, 30])),
    # ------------------------------------------------------------------ mean reversion
    H("rsi2", "mean_reversion", S.rsi2, "trade",
      "Un RSI(2) extrême est suivi d'un retour vers la moyenne 5 jours qui dépasse les coûts.",
      "RSI(n) < seuil (achat) / > 100 − seuil (vente)", "aucune", "jusqu'à clôture > SMA5", "espérance nette par trade > 0",
      "pas de stop : un excès qui continue coûte cher", "Liquidité fournie aux vendeurs forcés à court terme (Connors).",
      "Marchés en forte tendance ; crises où les excès s'étendent ; coûts élevés.",
      {"length": 2, "threshold": 10}, _grid(length=[2, 3, 4], threshold=[5, 10, 15])),
    H("rsi2_trend", "hybrid", S.rsi2_trend, "trade",
      "Le retour à la moyenne après un RSI(2) extrême fonctionne mieux dans le sens de la tendance de fond (SMA 200).",
      "RSI(2) extrême", "clôture du bon côté de la SMA(trend)", "jusqu'à clôture > SMA5", "espérance nette > celle de rsi2",
      "moins de trades ; dépendance au régime haussier",
      "Acheter les replis dans une tendance haussière : liquidité + momentum.",
      "Marché baissier prolongé, retournement de tendance.",
      {"threshold": 10, "trend": 200}, _grid(threshold=[5, 10, 15], trend=[100, 200])),
    H("bollinger_reversion", "mean_reversion", S.bollinger_reversion, "trade",
      "Une clôture hors des bandes de Bollinger revient vers la moyenne mobile plus souvent et plus fort que les coûts.",
      "clôture hors bande ± k écarts-types", "aucune", "jusqu'au retour à la moyenne", "espérance nette > 0",
      "sortie de bande qui devient une tendance", "Surréaction à court terme.",
      "Breakouts de volatilité, tendances fortes.",
      {"n": 20, "k": 2.0}, _grid(n=[10, 20, 40], k=[1.5, 2.0, 2.5])),
    H("pullback", "mean_reversion", S.pullback, "trade",
      "Dans une tendance de fond, une clôture au plus bas de N jours est suivie d'un rebond (pullback statistique).",
      "clôture = plus bas sur N jours", "clôture au-dessus de la SMA(trend)", "jusqu'au plus haut N jours ou 10 jours", "espérance nette > 0",
      "replis qui deviennent des retournements", "Acheter la faiblesse temporaire dans une tendance.",
      "Retournements de tendance, krachs.",
      {"lookback": 5, "trend": 200, "max_hold": 10}, _grid(lookback=[3, 5, 10], trend=[100, 200])),
    H("ibs", "mean_reversion", S.ibs, "trade",
      "Une clôture dans le bas du range du jour (IBS faible) est suivie d'un rendement positif le lendemain.",
      "IBS = (C − L)/(H − L)", "IBS < seuil (achat), > 1 − seuil (vente)", "1 à 3 jours", "rendement net > 0",
      "trades très fréquents : sensibles aux coûts", "Effet documenté sur les indices actions (pression de fin de séance).",
      "Coûts, marchés 24/7 sans clôture significative.",
      {"threshold": 0.2, "hold": 1}, _grid(threshold=[0.1, 0.2, 0.3], hold=[1, 3])),
    # ------------------------------------------------------------------ breakout
    H("vol_breakout", "breakout", S.vol_breakout, "trade",
      "Un mouvement intrajournalier supérieur à k × le range de la veille depuis l'ouverture se prolonge jusqu'à la clôture.",
      "ordre stop à ouverture ± k × range", "aucune", "intrajournalier (sortie à la clôture)", "espérance nette > 0",
      "faux départs ; coût aller-retour chaque jour", "Breakout de volatilité de Larry Williams.",
      "Marchés à retour à la moyenne intrajournalier, spreads larges.",
      {"k": 0.5, "use_atr": False}, _grid(k=[0.3, 0.5, 0.7, 1.0], use_atr=[False, True])),
    H("nr7", "breakout", S.nr7, "trade",
      "Après le range le plus étroit des N derniers jours, la cassure du haut/bas de ce jour annonce un mouvement directionnel.",
      "cassure du haut/bas du jour NR", "range du jour = plus petit des N", "1 à 5 jours, stop 1 ATR", "espérance nette > 0",
      "faux breakouts", "Compression puis expansion de volatilité (Crabel).",
      "Volatilité qui reste comprimée ; breakouts sans suivi.",
      {"n": 7, "hold": 3}, _grid(n=[4, 7], hold=[1, 3, 5])),
    H("prev_hl_breakout", "breakout", S.prev_hl_breakout, "trade",
      "La cassure du plus haut (bas) de la veille se prolonge dans la séance.",
      "ordre stop au plus haut/bas de la veille ± tampon", "aucune", "1 à 3 jours", "espérance nette > 0",
      "faux breakouts quotidiens", "Breakout de niveau visible (stops et ordres en attente).",
      "Chasse aux stops puis retour.",
      {"buffer_atr": 0.0, "hold": 1}, _grid(buffer_atr=[0.0, 0.1, 0.25], hold=[1, 3])),
    # ------------------------------------------------------------------ momentum
    H("roc_accel", "momentum", S.roc_accel, "trade",
      "Un momentum positif qui accélère prédit un rendement positif.",
      "ROC(n) et sa variation sur m jours", "même signe", "quotidien", "rendement net > 0",
      "entrée au sommet de l'accélération", "Momentum + accélération.",
      "Accélérations finales des bulles.",
      {"n": 20, "m": 5}, _grid(n=[10, 20, 60], m=[5, 10])),
    H("mtf_momentum", "multi_timeframe", S.mtf_momentum, "trade",
      "Un repli court dans une tendance longue est suivi d'une reprise de la tendance (tendance HTF + entrée LTF).",
      "ROC(short) contre ROC(long)", "tendance longue établie", "10 jours", "espérance nette > 0",
      "repli qui devient retournement", "Combiner momentum lent et retour à la moyenne rapide.",
      "Retournements de tendance longue.",
      {"long": 120, "short": 5, "hold": 10}, _grid(long=[60, 120, 250], short=[3, 5, 10])),
    H("xs_momentum", "momentum", None, "xs",
      "Dans une classe d'actifs, les instruments qui ont le plus monté sur L jours surperforment ceux qui ont le moins monté le mois suivant.",
      "rang du rendement sur L jours (en sautant les `skip` derniers)", "≥ 3 instruments", "21 jours", "rendement net du long-short > 0",
      "krachs de momentum, petite taille d'univers", "Momentum relatif (Jegadeesh-Titman, Asness-Moskowitz-Pedersen).",
      "Univers trop petit ; retournements de leadership.",
      {"lookback": 126, "skip": 0}, _grid(lookback=[63, 126, 252], skip=[0, 21])),
    # ------------------------------------------------------------------ volatility
    H("squeeze_breakout", "volatility", S.squeeze_breakout, "trade",
      "Lorsque la volatilité augmente après une période de compression, la probabilité d'un mouvement directionnel durable augmente.",
      "clôture hors bande de Bollinger", "largeur des bandes dans le quantile bas de 6 mois", "5 à 20 jours", "espérance nette > 0",
      "faux départs", "Les régimes de volatilité alternent ; l'expansion suit la compression.",
      "Expansion sans direction (aller-retour).",
      {"n": 20, "quantile": 0.1, "window": 126, "hold": 10}, _grid(quantile=[0.1, 0.2], hold=[5, 10, 20])),
    H("atr_breakout", "volatility", S.atr_breakout, "trade",
      "Une variation quotidienne supérieure à k ATR annonce une continuation.",
      "|ΔC| > k × ATR(14) de la veille", "aucune", "5 à 20 jours", "espérance nette > 0",
      "chocs qui se retournent", "Arrivée d'information majeure, digérée lentement.",
      "Surréaction puis correction.",
      {"k": 1.0, "hold": 10}, _grid(k=[1.0, 1.5, 2.0], hold=[5, 10, 20])),
    # ------------------------------------------------------------------ price action
    H("market_structure", "price_action", S.market_structure, "trade",
      "Une suite de sommets et de creux ascendants (structure haussière) prédit la continuation.",
      "deux derniers sommets/creux de swing confirmés", "HH+HL ou LH+LL", "jusqu'au changement de structure", "rendement net > 0",
      "confirmation tardive (k barres)", "Définition « price action » de la tendance.",
      "Ranges, structures ambiguës.",
      {"swing": 5}, _grid(swing=[3, 10])),
    H("liquidity_sweep", "price_action", S.liquidity_sweep, "trade",
      "Un passage sous le plus bas de N jours suivi d'une clôture au-dessus (balayage de liquidité) est suivi d'une hausse.",
      "plus bas < plus bas N jours ET clôture > ce niveau", "aucune", "3 à 10 jours", "espérance nette > 0",
      "le balayage qui devient une vraie cassure", "Turtle soup : les stops sous un niveau visible sont déclenchés puis le prix revient.",
      "Vraies cassures, tendances fortes.",
      {"lookback": 20, "hold": 5}, _grid(lookback=[10, 20, 55], hold=[3, 5, 10])),
    H("rejection", "price_action", S.rejection, "trade",
      "Une longue mèche de rejet au plus bas de 20 jours est suivie d'une hausse.",
      "mèche ≥ w × range", "au plus bas/haut de 20 jours", "3 à 10 jours", "espérance nette > 0",
      "pattern fréquent et bruité", "Rejet d'un niveau par les acheteurs (pin bar).",
      "Marchés en tendance où les mèches n'arrêtent rien.",
      {"wick": 0.5, "lookback": 20, "hold": 5}, _grid(wick=[0.5, 0.66], hold=[3, 5, 10])),
    # ------------------------------------------------------------------ volume
    H("volume_spike", "volume", S.volume_spike, "trade",
      "Un volume relatif élevé avec une clôture dans le haut du range annonce une continuation.",
      "volume / médiane 20 jours > k", "clôture dans le quart haut (bas) du range", "1 à 10 jours", "espérance nette > 0",
      "pics de volume de capitulation (retournement)", "Le volume confirme l'information.",
      "Volumes de fin de mois, de rebalancement d'indice, d'échéance.",
      {"k": 2.0, "hold": 5}, _grid(k=[1.5, 2.0, 3.0], hold=[1, 5, 10]), requires_volume=True),
    H("volume_divergence", "volume", S.volume_divergence, "trade",
      "Un nouveau plus haut sur volume faible est suivi d'une baisse (divergence prix/volume).",
      "clôture au plus haut N jours", "volume < médiane 20 jours", "3 à 10 jours", "espérance nette > 0",
      "volume faible en tendance saine", "Absence de participation = mouvement fragile.",
      "Tendances régulières à volume décroissant.",
      {"lookback": 20, "hold": 5}, _grid(lookback=[10, 20], hold=[3, 5, 10]), requires_volume=True),
    # ------------------------------------------------------------------ statistical
    H("pairs", "statistical", None, "pair",
      "L'écart entre deux actifs économiquement liés revient vers sa moyenne glissante après un écart de plus de e écarts-types.",
      "z-score du spread log (couverture glissante)", "paires déclarées a priori, pas screenées", "jusqu'au retour à la moyenne", "rendement net > 0",
      "rupture de la relation (le spread diverge pour toujours)", "Arbitrage statistique entre substituts.",
      "Changements structurels (or/argent, politique monétaire).",
      {"window": 120, "entry": 2.0}, _grid(window=[60, 120, 250], entry=[1.5, 2.0, 2.5])),
    # ------------------------------------------------------------------ deferred
    H("opening_range_breakout", "breakout", None, "deferred",
      "La cassure du range des 30 premières minutes se prolonge dans la séance.", "", "", "", "", "", "", "",
      deferred_reason="exige de l'intraday sur plusieurs années ; Yahoo ne fournit que 60 jours en 5 minutes. "
                      "Recherche intraday antérieure de ce dépôt (journal/RAPPORT_DAY_TRADING.md) : non rentable après coûts."),
    H("session_breakout", "breakout", None, "deferred",
      "La cassure du range de la session asiatique se prolonge en session de Londres (FX).", "", "", "", "", "", "", "",
      deferred_reason="exige des données FX intraday horodatées par session (Dukascopy) non encore intégrées."),
    H("factor_model", "statistical", None, "deferred",
      "Des facteurs (value, qualité, taille) expliquent les rendements croisés futurs.", "", "", "", "", "", "", "",
      deferred_reason="exige des fondamentaux point-in-time ; les sources gratuites ne les fournissent pas sans biais de survie et de révision."),
]


def by_name(name: str) -> Hypothesis:
    for h in HYPOTHESES:
        if h.name == name:
            return h
    raise KeyError(name)


def active() -> list[Hypothesis]:
    return [h for h in HYPOTHESES if h.kind != "deferred"]
