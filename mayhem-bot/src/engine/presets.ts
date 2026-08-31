import type { StrategyConfig } from "../types.js";

/**
 * Ce cycle ne change pas un seuil : il change le **protocole de mesure**, parce que la mesure
 * elle-même s'est révélée incapable de départager quoi que ce soit.
 *
 * Rendement pondéré de la MÊME configuration, inchangée, sur trois fenêtres consécutives :
 *
 * | variante           | 12:22-13:12 | 13:15-14:11 | 14:13-15:09 |
 * |--------------------|-------------|-------------|-------------|
 * | liquid-only        |      -7.09% |     -11.55% |      -7.88% |
 * | grace-60s          |      -6.00% |      -7.34% |     -18.58% |
 * | grace-60s-nofollow |          -- |      +0.18% |     -19.70% |
 *
 * `liquid-only` n'a pas bougé d'un paramètre et oscille sur 4.5 points. `grace-60s-nofollow`,
 * annoncée meilleure variante jamais obtenue à +0.18%, revient à -19.70% la fenêtre suivante.
 * **La variance entre fenêtres est du même ordre que les écarts entre variantes** : tout ce que
 * j'ai comparé jusqu'ici était à la limite du bruit.
 *
 * Intervalles de confiance à 90% (bootstrap 4000 tirages, fenêtres poolées) :
 *
 *     liquid-only          n=856   -8.49%   [-11.54% , -5.20%]   largeur  6.3 pts
 *     grace-60s            n=468   -9.09%   [-15.31% , -2.83%]   largeur 12.5 pts
 *     grace-60s-nofollow   n=297   -5.46%   [-15.37% , +5.48%]   largeur 20.9 pts
 *     grace-20s-nofollow   n=178   -8.65%   [-19.32% , +2.60%]   largeur 21.9 pts
 *     grace-15s            n=202   -6.06%   [-13.55% , +1.51%]   largeur 15.1 pts
 *     no-stop              n=286   -9.63%   [-17.14% , -1.51%]   largeur 15.6 pts
 *
 * **Tous les intervalles se recoupent.** Aucune variante n'est distinguable d'une autre, ni de
 * la référence. Les estimations ponctuelles tiennent toutes entre -5% et -10%. Sur une
 * distribution en loterie, quelques centaines d'allers-retours ne suffisent pas : la queue porte
 * le résultat et sa fréquence d'apparition est elle-même très bruitée.
 *
 * La cause est identifiée et corrigeable. Les variantes **ne prennent pas les mêmes entrées** :
 * dès qu'une politique de sortie garde ses positions plus longtemps, ses 8 emplacements se
 * saturent et elle rate des entrées que les autres prennent. La comparaison mélange alors deux
 * effets — la politique de sortie et le hasard de l'occupation — et le second domine. C'est
 * précisément ce qui avait fait attribuer à tort le résultat de `grace-60s-nofollow` au fait de
 * ne pas suivre Mayhem, alors que le test apparié ne montrait aucun effet (12/30, médiane -1.4 pt).
 *
 * **Correctif : supprimer la contention.** `maxConcurrentPositions` passe de 8 à 60 et le capital
 * de 2 à 20 SOL, si bien qu'aucune variante ne peut plus être limitée ni par un emplacement ni
 * par le solde (60 x 0.15 = 9 SOL de déploiement maximum contre 20 disponibles). Toutes voient
 * alors **exactement le même flux d'entrées**, et leurs différences ne viennent plus que de la
 * politique de sortie. La comparaison appariée mint par mint devient la mesure principale : elle
 * élimine d'un coup la variance de régime de marché, qui est la source de bruit dominante, et
 * c'est le seul test qui ait produit ici une réponse stable.
 *
 * Effet secondaire bienvenu : plus de faillite en cours de fenêtre, donc plus de remise à zéro
 * du capital qui tronquait les séries.
 *
 * Le rendement pondéré reste sans dimension, donc comparable aux fenêtres précédentes malgré le
 * changement d'échelle du capital.
 *
 * Rappels durables :
 * - **Le trailing stop est la seule sortie rentable**, dans toutes les variantes et toutes les
 *   fenêtres (+38% à +65% de moyenne). Sa part varie de 18.7% à 41.4% selon la politique.
 * - Filtre de profondeur du pool : **réfuté**. Tenu constant à 40 SOL, comme contrôle.
 * - Priority fee **mesuré** à 0.000025 SOL. Le modèle a facturé 0.003 pendant longtemps, soit
 *   120x trop, ce qui a invalidé toutes les conclusions antérieures — y compris les négatives.
 * - Taux d'occupation, `sellOnMayhemFullExit`, suppression totale du stop : hypothèses testées,
 *   aucune n'a survécu. Voir FINDINGS.md.
 *
 * Rien n'est démontré rentable, et à ce stade rien n'est même démontré différent.
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
