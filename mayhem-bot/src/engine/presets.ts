import type { StrategyConfig } from "../types.js";

/**
 * Ce cycle teste une **prédiction**, pas une nouvelle idée. C'est plus fort qu'un énième balayage :
 * si l'effet est réel il doit se prolonger là où on ne l'a pas encore regardé.
 *
 * Fenêtre 17:11-18:07, expérience remarquablement propre : les cohortes `stop_loss` (819 sorties
 * à -22.99%) et `trailing_stop` (201 à +38.21%) sont **identiques au trade près** dans les quatre
 * variantes, puisque `maxHoldSeconds` ne peut rien changer avant que son horizon soit atteint.
 * Toute la différence tient donc à la seule cohorte `max_hold_time`, et le rendement pondéré
 * total est **monotone** :
 *
 *     hold-120s    -9.66%     cohorte max_hold n=50, +14.70%
 *     hold-300s    -9.85%     cohorte max_hold n=40, +15.44%
 *     liquid-only  -9.93%     cohorte max_hold n=37, +15.13%   (référence, 600s)
 *     hold-1800s  -10.48%     cohorte max_hold n=16, +12.20%
 *
 * Plus la sortie forcée est précoce, plus elle capture de positions (50 contre 16) à un rendement
 * moyen à peine plus bas, et meilleur est le total. Le sens colle exactement à la décroissance
 * mesurée on-chain : -24% à t+15s, -72% à t+60s, -95% à t+300s. Attendre coûte plus que ce que
 * la queue rapporte.
 *
 * **Mais ce n'est pas significatif**, et je ne le traite pas comme un résultat : le test apparié
 * restreint aux positions dont la sortie diffère effectivement de la référence donne
 * -2.44 pts [-6.22, +1.24] pour 120s, -2.72 pts [-6.37, +1.07] pour 300s — intervalles contenant
 * zéro, gains sur 53% des cas, soit un pile ou face. L'amplitude totale est de 0.82 point entre
 * les deux extrêmes. Un ordonnancement monotone sur une seule fenêtre est exactement ce qui m'a
 * fait annoncer à tort un effet de profondeur de pool, puis l'annoncer à l'envers.
 *
 * D'où le protocole : au lieu de rejouer les mêmes points, **prolonger vers 30s et 60s**. Si la
 * monotonie est réelle, elle doit continuer ; si elle s'inverse ou s'aplatit, c'était du bruit.
 * Une prédiction qui se vérifie sur des points nouveaux vaut bien mieux qu'une corrélation
 * réobservée sur les mêmes. `hold-120s` est conservée comme point de recouvrement entre les deux
 * fenêtres, `liquid-only` reste la référence à 600s.
 *
 * Garde-fou : le stop-loss immédiat et le trailing restent actifs partout, et les sorties par
 * trailing ont un hold médian de 5 secondes — une sortie forcée à 30s ne les tronque donc pas.
 *
 * Espace de sortie déjà exploré et clos : temporisation du stop **réfutée avec significativité**
 * (-5.83 pts [-9.35, -2.18]) ; réglages du trailing **sans effet** (trois IC contenant zéro,
 * variantes identiques à la référence sur 91-97% des mints) ; profondeur du pool réfutée ;
 * `sellOnMayhemFullExit` sans effet démontré ; suppression totale du stop pire que tout.
 *
 * Rappels durables :
 * - Priority fee **mesuré** à 0.000025 SOL. Le modèle a facturé 0.003 pendant longtemps, soit
 *   120x trop, ce qui a invalidé toutes les conclusions antérieures — y compris les négatives.
 * - Frais de plateforme (1% par jambe) : hypothèse du modèle **toujours non vérifiée**, une
 *   tentative de mesure a échoué (voir FINDINGS.md). La dernière hypothèse non vérifiée valait
 *   un facteur 120.
 * - Filtre de profondeur du pool : réfuté. Tenu constant à 40 SOL, comme contrôle.
 *
 * Rien n'est démontré rentable. Cumul depuis la correction des frais : 10810 allers-retours,
 * -115.94 SOL sur 1531 SOL engagés, soit -7.57%, médiane -20.45% par trade.
 */
const BASE = {
  startingBalanceSol: 20,
  positionSizeSol: 0.15,
  takeProfitPct: null,
  stopLossPct: 0.12,
  trailingStopPct: 0.25,
  trailingArmPct: 0.5,
  // Mesuré à -66.45% de rendement moyen sur 47 sorties : quand Mayhem sort complètement, le
  // token a déjà chuté des deux tiers. Conservé à `true` par défaut pour que la référence reste
  // la référence, mais c'est l'axe testé ce cycle — voir grace-60s-nofollow.
  sellOnMayhemFullExit: true,
  // MESURÉ, pas supposé : 40 transactions Mayhem lues on-chain paient toutes exactement
  // 0.000025 SOL de frais. Le modèle facturait 0.003, soit 120x trop. Sur les 364 jambes de
  // liquid-only cela représentait 1.09 SOL de frais fictifs contre 0.009 réels — assez pour
  // ruiner un capital de 2 SOL à lui seul, et donc pour invalider toute conclusion de
  // rentabilité tirée avant cette mesure. Outil de mesure : src/tools/measureFees.ts.
  priorityFeeSol: 0.000025,
  // Tenu constant à 40 SOL sur toutes les variantes : l'axe profondeur est réfuté (voir
  // en-tête), donc il devient un contrôle, plus une variable.
  minPoolLiquiditySol: 40,
  minMayhemBuySol: null,
  waitForMigration: false,
  stopLossGraceSeconds: null,
  maxConcurrentPositions: 60,
  // Sans lui, une position sur un token mort ne sort jamais : pas de trade = pas de mouvement
  // de prix = aucun seuil déclenché. La stratégie se bloque à 8/8 et la comparaison devient
  // une course à la saturation plutôt qu'un test de politique de sortie. La sortie forcée
  // price son fill via simulateSell contre les dernières réserves connues, donc elle encaisse
  // l'impact de l'AMM et non la marque périmée.
  maxHoldSeconds: 600,
} as const;

export const defaultStrategies: StrategyConfig[] = [
  {
    id: "liquid-only",
    name: "Référence historique (stop immédiat)",
    description:
      "Temoin inchange depuis le debut, garde pour la continuite des comparaisons : stop-loss -12% arme des l'entree. 73.4% de ses sorties partent en stop_loss au bout d'une seconde pour -28.72% en moyenne. C'est la configuration que les variantes cherchent a battre, et elle reste la pire sur la mediane (-21.88%).",
    kind: "generic",
    enabled: true,
    ...BASE,
  },
  {
    id: "hold-30s",
    name: "Sortie forcee a 30s",
    description:
      "Prolonge la monotonie observee vers l'horizon le plus court testable. Si l'effet est reel, cette variante doit battre hold-60s, qui doit battre hold-120s, qui doit battre la reference a 600s. Si l'ordre s'inverse ou s'aplatit ici, la monotonie de la fenetre precedente etait du bruit. Les sorties par trailing ont un hold median de 5 secondes, donc 30s ne les tronque pas.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 30,
  },
  {
    id: "hold-60s",
    name: "Sortie forcee a 60s",
    description:
      "Point intermediaire entre 30s et 120s. Deux points nouveaux plutot qu'un seul : une monotonie sur quatre horizons consecutifs (30, 60, 120, 600) est bien plus difficile a produire par hasard qu'un ecart entre deux points.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 60,
  },
  {
    id: "hold-120s",
    name: "Sortie forcee a 120s",
    description:
      "Conservee de la fenetre precedente comme point de RECOUVREMENT entre les deux experiences : c'est elle qui dira si le resultat se reproduit sur une fenetre independante, ou s'il etait propre au regime de marche de 17h. Elle etait la meilleure des quatre a -9.66% de rendement pondere.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 120,
  },
  {
    id: "post-migration",
    name: "Après migration (sonde)",
    description:
      "Conservée uniquement comme sonde, elle ne coûte rien. Sur 20 migrations détectées, les pools résultants valaient 1$ à 126$ (médiane ~6$) plusieurs heures après : il n'y a rien de tradable. Ne prendra une position que si un pool dépasse enfin 25000$ de profondeur, ce qui n'est jamais arrivé. Qu'elle ne trade jamais est le résultat attendu.",
    kind: "generic",
    enabled: true,
    ...BASE,
    minPoolLiquiditySol: null,
    waitForMigration: true,
  },
];
