import type { StrategyConfig } from "../types.js";

/**
 * **La temporisation du stop est réfutée, avec significativité.** C'est le premier résultat
 * franchement concluant obtenu ici, et il annule ce que ce fichier affirmait il y a cinq cycles.
 *
 * Il a fallu pour cela supprimer la contention d'emplacements (60 positions, 20 SOL) : les
 * variantes prennent désormais **99.0% des mêmes entrées** (302 mints communs sur 305), ce qui
 * rend enfin valide la comparaison appariée mint par mint — celle qui élimine la variance de
 * régime de marché, dominante et jusqu'ici confondue avec l'effet des politiques.
 *
 * Écart apparié contre la référence (stop immédiat), fenêtre 15:10-16:09 :
 *
 * | variante           |   n | écart moyen | gagne sur | IC 90%           |
 * |--------------------|-----|-------------|-----------|------------------|
 * | grace-60s          | 299 |   -2.07 pts |       19% | [-5.16 , +1.51]  |
 * | grace-60s-nofollow | 297 |   -4.90 pts |       27% | [-9.66 , -0.26]  |
 * | grace-20s-nofollow | 298 |   -5.83 pts |       20% | [-9.35 , -2.18]  |
 *
 * Les deux dernières ont un intervalle qui **exclut zéro** : elles sont significativement pires
 * que le stop immédiat. L'écart médian est nul et elles ne gagnent que sur 19-27% des mints —
 * autrement dit, la plupart du temps la temporisation ne change rien, et quand elle change
 * quelque chose elle perd plus qu'elle ne gagne.
 *
 * Le diagnostic de départ restait juste : le stop à -12% est bien plus étroit que la dispersion
 * à deux secondes (écart interquartile -28% / +17%), il coupe donc dans le bruit. **Mais le
 * remède coûte plus cher que le mal.** Couper vite à -28% bat couper tard à -70%, et la mesure
 * on-chain le disait déjà sans que j'en tire la conséquence : médiane -24.46% à t+15s,
 * -72.03% à t+60s. Laisser respirer les perdants coûte davantage que ce que rapporte laisser
 * respirer les gagnants. Retour au stop immédiat partout.
 *
 * **L'évaluateur hors-ligne classe ces mêmes politiques à l'envers** — il donnait grace-20s
 * meilleure que la référence (+2.96% contre +1.60%) là où le test apparié la donne pire de
 * 5.83 points avec IC excluant zéro. La raison est structurelle et connue : son chemin de prix
 * n'est échantillonné qu'aux transactions de Mayhem, il ne voit pas les creux intra-seconde qui
 * déclenchent 79% des sorties de la référence à un hold médian d'UNE seconde. Son biais
 * d'optimisme n'est donc **pas uniforme** : il favorise précisément les politiques qui évitent
 * les stops rapides. **Ne pas s'en servir pour classer des politiques différant par le timing du
 * stop.** Il reste valide pour des effets lents — largeur du trailing, seuil d'armement, durée
 * max — qui sont l'axe testé ici.
 *
 * Ce cycle teste donc le trailing stop, la seule sortie rentable dans toutes les fenêtres
 * (+33% à +65% de moyenne selon la variante), sur ses deux paramètres, à stop immédiat partout
 * pour que la comparaison appariée reste propre :
 * - `trail-arm-20` abaisse le seuil d'armement de +50% à +20% : aujourd'hui une position qui
 *   monte de 40% puis retombe n'a aucune protection de trailing et finit au stop-loss.
 * - `trail-tight-15` et `trail-wide-40` encadrent la largeur actuelle de -25%.
 *
 * Rappels durables :
 * - Filtre de profondeur du pool : **réfuté**. Tenu constant à 40 SOL, comme contrôle.
 * - Priority fee **mesuré** à 0.000025 SOL. Le modèle a facturé 0.003 pendant longtemps, soit
 *   120x trop, ce qui a invalidé toutes les conclusions antérieures — y compris les négatives.
 * - `sellOnMayhemFullExit`, suppression totale du stop, taux d'occupation : testés, aucun effet
 *   démontré. Voir FINDINGS.md.
 *
 * Rien n'est démontré rentable. La référence elle-même est à -8.77% [IC90 -10.75, -6.68].
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
    id: "trail-arm-20",
    name: "Trailing arme a +20%",
    description:
      "Abaisse le seuil d'armement du trailing stop de +50% a +20%. Aujourd'hui une position qui monte de 40% puis retombe n'est jamais protegee par le trailing et finit au stop-loss : le trailing ne s'arme qu'au-dela de +50% de gain au pic. Or le trailing est la seule sortie rentable de toutes les fenetres. Elargir la population de positions qu'il protege est l'hypothese la plus directe qui reste. Risque symetrique : armer trop tot coupe une vraie pompe sur son premier repli ordinaire, ce que le seuil a +50% avait justement ete introduit pour eviter.",
    kind: "generic",
    enabled: true,
    ...BASE,
    trailingArmPct: 0.2,
  },
  {
    id: "trail-tight-15",
    name: "Trailing serre -15%",
    description:
      "Resserre le trailing de -25% a -15%, a seuil d'armement inchange. Encadre la largeur actuelle par le bas : une fois une position declaree gagnante, rend-on plus en verrouillant tot qu'en laissant courir ?",
    kind: "generic",
    enabled: true,
    ...BASE,
    trailingStopPct: 0.15,
  },
  {
    id: "trail-wide-40",
    name: "Trailing large -40%",
    description:
      "Elargit le trailing de -25% a -40%, a seuil d'armement inchange. Encadre la largeur actuelle par le haut. Un trail a -45% avait ete teste et rejete tres tot, mais sous le regime du priority fee errone (120x trop cher) qui a invalide toutes les conclusions de cette periode : l'hypothese merite d'etre reposee proprement.",
    kind: "generic",
    enabled: true,
    ...BASE,
    trailingStopPct: 0.4,
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
