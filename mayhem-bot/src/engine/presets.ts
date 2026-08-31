import type { StrategyConfig } from "../types.js";

/**
 * L'espace des politiques de SORTIE est très largement exploré, et rien n'y bat la référence.
 * Deux fenêtres appariées propres (99% d'entrées communes, contention d'emplacements supprimée) :
 *
 * Fenêtre 15:10-16:09 — **la temporisation du stop est réfutée**, deux variantes sur trois avec
 * un IC excluant zéro : grace-20s-nofollow -5.83 pts [-9.35, -2.18], grace-60s-nofollow
 * -4.90 pts [-9.66, -0.26]. Couper vite à -28% bat couper tard à -70%.
 *
 * Fenêtre 16:12-17:08 — **les paramètres du trailing ne font aucune différence mesurable** :
 * trail-arm-20 +0.48 pts [-0.09, +1.07], trail-tight-15 -4.20 pts [-14.07, +1.77],
 * trail-wide-40 -1.71 pts [-3.74, +0.34]. Les trois intervalles contiennent zéro, et les écarts
 * médians sont nuls : les variantes se comportent identiquement à la référence sur 91-97% des
 * mints. Axe mort.
 *
 * S'ajoutent, plus tôt : profondeur du pool réfutée, `sellOnMayhemFullExit` sans effet
 * démontré, suppression totale du stop pire que tout. Reste UN paramètre de sortie jamais testé
 * proprement, et ce n'est pas le moindre — `maxHoldSeconds`. Les sorties `max_hold_time`
 * rendent **+40.11% en moyenne**, la deuxième meilleure sortie après le trailing, mais ne
 * représentent que 4.4% des fermetures. Personne n'a vérifié si 600 secondes est le bon
 * horizon, ni ce qui se passe si on force davantage de positions à sortir par cette porte.
 *
 * L'argument va dans les deux sens, ce qui en fait un vrai test : la décroissance médiane
 * mesurée on-chain (-24% à t+15s, -72% à t+60s, -95% à t+300s) plaide pour couper tôt ; la
 * fréquence des queues >+100%, qui croît avec l'horizon, plaide pour laisser courir. Les
 * variantes encadrent donc la valeur actuelle des deux côtés.
 *
 * L'évaluateur hors-ligne est **valide sur cet axe** (effet lent, pas de timing de stop) —
 * contrairement à l'axe précédent où il classait les politiques à l'envers.
 *
 * Rappels durables :
 * - Priority fee **mesuré** à 0.000025 SOL. Le modèle a facturé 0.003 pendant longtemps, soit
 *   120x trop, ce qui a invalidé toutes les conclusions antérieures — y compris les négatives.
 * - Frais de plateforme (1% par jambe) : **tentative de mesure non concluante**. Reconstruire
 *   le SOL entré dans la courbe depuis les réserves stockées et les tokens échangés donne un
 *   frais implicite négatif (médiane -15%) dans les deux sens de lecture (réserves pré- ou
 *   post-trade), donc la reconstruction ne reproduit pas les montants. `price_sol` vaut
 *   exactement S/T des réserves stockées, elles sont donc cohérentes entre elles ; l'écart
 *   vient d'ailleurs (réserves virtuelles contre montants réels, très probablement). À
 *   reprendre, sans en tirer de conclusion pour l'instant.
 * - « Premier achat de Mayhem sur un mint » comme filtre d'entrée : **inutilisable**, 67 cas
 *   éligibles contre 5215 renforts, soit 1.3%. Trop rare pour porter une stratégie.
 * - Filtre de profondeur du pool : réfuté. Tenu constant à 40 SOL, comme contrôle.
 *
 * Rien n'est démontré rentable. La référence est à -4.20% [IC90 -7.92, -0.15] sur la dernière
 * fenêtre. Si `maxHoldSeconds` ne donne rien non plus, « ce wallet n'est pas copiable de façon
 * rentable par réglage de politique » deviendra une conclusion solide et honnête.
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
    id: "hold-120s",
    name: "Sortie forcee a 120s",
    description:
      "Ramene maxHoldSeconds de 600 a 120 secondes. La decroissance mediane mesuree on-chain (-24% a t+15s, -72% a t+60s, -95% a t+300s) dit qu'attendre coute cher : couper plus tot doit reduire la perte des positions qui n'ont ni touche le stop ni arme le trailing.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 120,
  },
  {
    id: "hold-300s",
    name: "Sortie forcee a 300s",
    description:
      "Point intermediaire entre 120s et la valeur actuelle de 600s. Sert a dire si l'effet, s'il existe, est monotone ou s'il a un optimum — un seul point de chaque cote ne le dirait pas.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 300,
  },
  {
    id: "hold-1800s",
    name: "Sortie forcee a 1800s",
    description:
      "Elargit a 30 minutes. L'argument oppose : la frequence des queues >+100% croit avec l'horizon (3.0% a t+2s, 8.0% a t+15s), et les sorties max_hold_time rendent deja +40.11% en moyenne, la deuxieme meilleure sortie. Si laisser courir paie, c'est ici que ca doit se voir. Garde-fou intact : le stop-loss immediat et le trailing restent actifs, donc une position qui s'effondre sort bien avant.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 1800,
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
