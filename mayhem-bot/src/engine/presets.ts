import type { StrategyConfig } from "../types.js";

/**
 * Roster du cycle courant : un seul axe testé, **la durée de la temporisation du stop**.
 *
 * Fenêtre 13:15-14:11, 766 allers-retours, contrôles anti-artefact passés (0 incohérence
 * raison/signe, 0 slippage nul des deux côtés, 0 gagnant >2x hors plage on-chain ; les gros
 * multiples se retrouvent à l'identique sur plusieurs variantes pour le même mint, ce qui les
 * recoupe) :
 *
 * | variante           |   n | rend. pondéré | médiane | >+100% |    PnL |
 * |--------------------|-----|---------------|---------|--------|--------|
 * | liquid-only        | 230 |       -11.55% | -20.75% |   2.6% | -2.281 |
 * | grace-60s          | 209 |        -7.34% | -15.19% |   4.8% | -1.912 |
 * | grace-60s-nofollow | 186 |        +0.18% |  -6.14% |   9.1% | +0.051 |
 * | no-stop            | 141 |       -12.10% |  -8.24% |   4.3% | -2.099 |
 *
 * `grace-60s-nofollow` est le meilleur résultat obtenu à ce jour et le premier rendement
 * pondéré non négatif. **Il faut le lire pour ce qu'il est : l'équilibre, pas la rentabilité.**
 * Il valait +13.30% à n=60 et +6.62% à n=78 avant de retomber à +0.18% à n=186 — la décroissance
 * attendue d'un résultat porté par quelques événements de queue. Aucune conclusion de rentabilité.
 *
 * Ce que la fenêtre a réfuté, et qui aurait fait un beau récit :
 * - **Le gain ne vient pas de « ne pas suivre Mayhem à la sortie ».** Test apparié sur les 30
 *   mints communs où `grace-60s` est effectivement sorti sur `mayhem_full_exit` : nofollow fait
 *   mieux sur 12/30, écart médian -1.4 pt. La moyenne (+20 pts) est portée par des valeurs
 *   extrêmes. C'est un pile ou face, pas un effet.
 * - **Le nombre de positions déjà ouvertes ne prédit pas la qualité d'une entrée.** Testé sur
 *   ~1500 allers-retours toutes variantes : médiane -22.6% à 0 position ouverte, -3.99% à 8,
 *   -32.8% à 9. Aucune monotonie exploitable. L'hypothèse d'un « régime de marché » lisible dans
 *   le taux d'occupation est morte.
 *
 * Ce qui reste debout, et qui motive ce cycle : **le trailing stop est la seule sortie rentable**,
 * partout et dans toutes les variantes (+64.91% chez nofollow, +43.36% chez grace-60s, +33.75%
 * chez liquid-only), et sa part varie de 18.7% à 41.4% selon la politique. Tout ce qui augmente
 * la proportion de sorties par trailing stop améliore le résultat.
 *
 * Or chez `grace-60s-nofollow`, ce qui tronque encore les positions, c'est le stop à 60s :
 *
 *     stop_loss       45.7%  **-70.12%**  hold  60s   somme -5960 pts
 *     trailing_stop   41.4%    +64.91%    hold  11s   somme +4998 pts
 *     max_hold_time   12.9%    +41.50%    hold 600s   somme  +996 pts
 *
 * Ce -70.12% n'est pas un hasard : il colle exactement à la décroissance mesurée on-chain, où la
 * médiane d'un achat de Mayhem vaut **-72.03% à t+60s** contre **-24.46% à t+15s**. Autrement dit
 * la temporisation à 60 secondes laisse bien les gagnants respirer (c'est son but, et ça marche :
 * le trailing passe de 18.7% à 41.4% des sorties), mais elle laisse aussi les perdants tomber
 * jusqu'au bout avant de couper. On encaisse la décroissance complète.
 *
 * D'où l'axe : **20 secondes**, choisi sur la courbe de décroissance et non par tâtonnement. Assez
 * pour être sorti de la bande de bruit des deux premières secondes (écart interquartile -28% /
 * +17%), qui était le problème d'origine ; assez tôt pour couper avant l'effondrement médian. Si
 * la temporisation n'a de valeur que pour franchir le bruit, 20s doit battre 60s. Si les gagnants
 * ont besoin de la minute entière pour se déclarer, 20s doit faire pire — et l'écart dira lequel
 * des deux effets domine.
 *
 * `no-stop` est retirée : sa question est tranchée (pire variante deux fenêtres de suite, -7.44%
 * puis -12.10%), supprimer entièrement le stop ne paie pas. `grace-60s` reste avec follow=true
 * pour continuer d'accumuler du n sur un contraste que le test apparié laisse indécis.
 *
 * Rappels durables :
 * - Filtre de profondeur du pool : **réfuté** (dégradation monotone du rendement pondéré et
 *   effondrement des queues quand on le durcit). Tenu constant à 40 SOL, comme contrôle.
 * - Priority fee **mesuré** à 0.000025 SOL. Le modèle a facturé 0.003 pendant longtemps, soit
 *   120x trop, ce qui a invalidé toutes les conclusions antérieures — y compris les négatives.
 *
 * Capitaux remis à 2 SOL : trois variantes sur quatre finissaient à solde 0.0000.
 *
 * Rien n'est démontré rentable. Voir FINDINGS.md.
 */
const BASE = {
  startingBalanceSol: 2,
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
    name: "Référence historique (stop immédiat)",
    description:
      "Temoin inchange depuis le debut, garde pour la continuite des comparaisons : stop-loss -12% arme des l'entree. 73.4% de ses sorties partent en stop_loss au bout d'une seconde pour -28.72% en moyenne. C'est la configuration que les variantes cherchent a battre, et elle reste la pire sur la mediane (-21.88%).",
    kind: "generic",
    enabled: true,
    ...BASE,
  },
  {
    id: "grace-60s-nofollow",
    name: "Grace 60s sans suivre Mayhem (référence de travail)",
    description:
      "LE test du cycle. Identique a grace-60s sauf sellOnMayhemFullExit: false. Sur la fenetre precedente cette sortie representait 30.5% des fermetures de grace-60s pour -66.45% en moyenne, soit -3123 points, le premier poste de perte de la meilleure variante. Si la sortie de Mayhem est un signal retarde, la desactiver doit ameliorer le rendement pondere ; si elle protege vraiment d'une chute encore pire, cette variante doit faire pire et on saura que -66% etait le moindre mal. Les positions concernees sortiront alors par trailing stop, stop-loss apres 60s, ou max-hold a 600s.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossGraceSeconds: 60,
    sellOnMayhemFullExit: false,
  },
  {
    id: "grace-60s",
    name: "Grace 60s (suit Mayhem)",
    description:
      "Meilleure variante de la fenetre precedente et nouvelle reference de comparaison : stop-loss suspendu 60 secondes, sortie sur la sortie complete de Mayhem conservee. Mediane -6.22% contre -21.88% pour liquid-only, queues >+100% a 5.8% contre 3.8%, part des sorties en stop_loss ramenee de 73.4% a 14.3%. C'est la variante dont grace-60s-nofollow ne change qu'UNE chose.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossGraceSeconds: 60,
  },
  {
    id: "grace-20s-nofollow",
    name: "Grace 20s, sans suivre Mayhem",
    description:
      "LE test du cycle. Identique a grace-60s-nofollow sauf la temporisation, ramenee de 60 a 20 secondes. Choisi sur la courbe de decroissance mesuree on-chain : la mediane d'un achat de Mayhem vaut -24.46% a t+15s contre -72.03% a t+60s, et le stop de grace-60s-nofollow se realise justement a -70.12%. Vingt secondes suffisent a franchir la bande de bruit des deux premieres secondes (ecart interquartile -28% / +17%) tout en coupant avant l'effondrement median. Si la temporisation ne sert qu'a franchir le bruit, cette variante doit gagner ; si les gagnants ont besoin de la minute entiere pour se declarer, elle doit perdre.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossGraceSeconds: 20,
    sellOnMayhemFullExit: false,
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
