import type { StrategyConfig } from "../types.js";

/**
 * Roster du cycle courant : un seul axe testé, la **temporisation du stop-loss**.
 *
 * Ce qui a mené ici, mesuré sur 979 allers-retours postérieurs à la correction du priority
 * fee (donc au coût réel) :
 *
 * - Le filtre de profondeur du pool est **réfuté**. Sur rendement pondéré par le capital
 *   engagé — et non sur une moyenne non pondérée de pourcentages, qui donne autant de poids
 *   à un aller-retour qu'à cent — il se dégrade de façon monotone quand on l'ouvre :
 *   40 SOL -5.98% (n=651), 150 SOL -9.23% (n=126), 250 SOL -12.33% (n=64),
 *   150 SOL + conviction -14.79% (n=15). Et la fréquence des queues >+100%, dont dépend
 *   toute la thèse, s'effondre dans le même sens : 4.1% / 3.2% / 1.6% / 0.0%. Le filtre
 *   supprime précisément les événements qui portent le rendement. Les trois variantes de
 *   profondeur sont retirées. (Une mesure antérieure concluait l'inverse sur une fenêtre
 *   unique ; elle ne s'est pas reproduite au cycle suivant. Le sens était une illusion de
 *   petit échantillon.)
 *
 * - Le vrai coupable est le stop-loss, et il l'est pour une raison structurelle, pas pour
 *   un mauvais réglage. Répartition des sorties de la référence :
 *     stop_loss        72.2%  rendement moyen -28.29%  hold médian    1s  somme -13299 pts
 *     trailing_stop    20.1%  rendement moyen +55.79%  hold médian    6s  somme  +7308 pts
 *     max_hold_time     6.8%  rendement moyen +40.52%  hold médian  600s  somme  +1783 pts
 *   Un stop nominal à -12% qui se réalise à -28% en une seconde ne coupe pas une tendance :
 *   il se déclenche avant qu'une tendance existe. Le slippage n'y est pour rien (0.19% médian)
 *   et les frais non plus (1.78%) — le prix bouge vraiment.
 *
 * - Reconstruit indépendamment de notre simulation, à partir des seuls événements on-chain
 *   de Mayhem (3910 achats éligibles), le prix après un achat de Mayhem vaut :
 *     t+2s   médiane  -0.10%   p25 -28.21%   p75 +17.19%   >+100% :  3.0%
 *     t+5s   médiane  -4.20%   p25 -41.57%   p75 +15.82%   >+100% :  6.2%
 *     t+15s  médiane -24.46%   p25 -67.23%   p75  +5.12%   >+100% :  8.0%
 *     t+60s  médiane -72.03%   p25 -95.22%   p75  -0.07%   >+100% :  7.2%
 *   Deux choses à la fois : la dispersion à 2 secondes (-28% / +17% entre quartiles) est
 *   bien plus large que le seuil de -12% du stop, et la fréquence des queues >+100% croît
 *   avec l'horizon. Un stop plus étroit que le bruit dans lequel il baigne ne discrimine
 *   rien ; il encaisse la moitié basse du bruit et interdit d'atteindre l'horizon où les
 *   queues apparaissent.
 *
 * D'où l'expérience : suspendre le stop pendant les N premières secondes, N étant le seul
 * paramètre qui varie. `no-stop` borne l'expérience par le haut — si elle bat les deux
 * autres, le stop n'a aucune valeur à aucun horizon ; si elle est la pire, la temporisation
 * a un optimum intermédiaire et il est entre 15 et 60 secondes. Le trailing stop et le
 * max-hold restent actifs partout, donc aucune variante ne peut se bloquer sur un token mort.
 *
 * Les capitaux sont remis à 2 SOL pour ce cycle : la référence était tombée à 0.139 SOL et
 * ne pouvait plus ouvrir la moindre position, ce qui la rendait incomparable aux autres.
 * L'historique des trades reste en base — c'est lui, pas le solde, qui porte l'information.
 *
 * Rien ici n'est démontré rentable. Voir FINDINGS.md.
 */
const BASE = {
  startingBalanceSol: 2,
  positionSizeSol: 0.15,
  takeProfitPct: null,
  stopLossPct: 0.12,
  trailingStopPct: 0.25,
  trailingArmPct: 0.5,
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
  maxConcurrentPositions: 8,
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
    name: "Référence (stop immédiat)",
    description:
      "Référence de comparaison, inchangée : stop-loss -12% armé dès l'entrée. C'est la configuration dont 72.2% des sorties partent en stop_loss au bout d'une seconde pour -28.29% en moyenne. Les trois variantes ci-dessous ne changent qu'UNE chose chacune : le moment où ce stop devient actif.",
    kind: "generic",
    enabled: true,
    ...BASE,
  },
  {
    id: "grace-15s",
    name: "Stop temporisé 15s",
    description:
      "Stop-loss suspendu pendant les 15 premières secondes. Choisi sur la dispersion mesurée : à t+2s l'écart interquartile va de -28.21% à +17.19%, à t+15s il s'est resserré vers le bas (médiane -24.46%, p75 +5.12%), c'est-à-dire qu'une baisse a cessé d'être du bruit et commence à être une tendance. Si le stop ne sert qu'à encaisser du bruit, cette variante doit battre la référence.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossGraceSeconds: 15,
  },
  {
    id: "grace-60s",
    name: "Stop temporisé 60s",
    description:
      "Même chose, mais 60 secondes. Pousse l'axe jusqu'à l'horizon où la médiane est déjà à -72.03% : si la temporisation aide, elle doit cesser d'aider quelque part avant ce point, et l'écart entre 15s et 60s dit où. Si au contraire 60s fait mieux que 15s, c'est que la fréquence des queues (7.2% à t+60s contre 3.0% à t+2s) compense la décroissance médiane.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossGraceSeconds: 60,
  },
  {
    id: "no-stop",
    name: "Sans stop-loss",
    description:
      "Borne supérieure de l'expérience : aucun stop-loss, sorties uniquement par trailing stop (-25% armé à +50%), max-hold 600s, ou sortie complète de Mayhem. Si elle bat les deux variantes temporisées, le stop n'a de valeur à aucun horizon et il faut le retirer. Si elle est la pire des quatre, la temporisation a un optimum intermédiaire — ce qui est l'information qu'on cherche.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossPct: null,
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
