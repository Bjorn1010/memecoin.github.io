import type { StrategyConfig } from "../types.js";

/**
 * Roster du cycle courant : un seul axe testé, **suivre ou non Mayhem à la sortie**.
 *
 * Le cycle précédent a testé la temporisation du stop-loss (`stopLossGraceSeconds`) et le
 * mécanisme est confirmé, mais pas le résultat. Sur la fenêtre 12:22-13:12, 829 allers-retours :
 *
 * | variante      |   n | rend. pondéré | médiane | >+100% | part `stop_loss` |
 * |---------------|-----|---------------|---------|--------|------------------|
 * | liquid-only   | 312 |        -7.09% | -21.88% |   3.8% |            73.4% |
 * | grace-15s     | 203 |        -6.06% | -14.75% |   5.4% |            34.5% |
 * | grace-60s     | 154 |        -6.00% |  -6.22% |   5.8% |            14.3% |
 * | no-stop       | 149 |        -7.44% |  -6.55% |   4.7% |             0.0% |
 *
 * Tout ce que la temporisation devait produire, elle le produit : la médiane passe de -21.88%
 * à -6.22%, la fréquence des queues monte de 3.8% à 5.8%, et la part des sorties en `stop_loss`
 * s'effondre de 73.4% à 14.3% au profit du trailing stop (22.4% -> 46.8%), qui est la sortie
 * rentable (+35.92% en moyenne). Le stop tirait bien à l'intérieur du bruit.
 *
 * Et pourtant le rendement pondéré ne bouge quasiment pas (-7.09% -> -6.00%). Parce qu'une
 * fuite jusque-là invisible a pris le relais : `mayhem_full_exit` passe de 0.6% des sorties
 * (n=2) à 30.5% (n=47), **à -66.45% en moyenne**. Le stop-loss fermait la position à une
 * seconde ; en le retirant, ces positions vivent assez longtemps pour être fermées par la
 * sortie de Mayhem — plus tard et beaucoup plus bas. La perte n'a pas été supprimée, elle a
 * changé de guichet. Décomposition de `grace-60s` :
 *
 *     trailing_stop      46.8%  +35.92%   hold  8s   somme +2586 pts
 *     mayhem_full_exit   30.5%  -66.45%   hold  7s   somme -3123 pts
 *     stop_loss          14.3%  -60.84%   hold 60s   somme -1339 pts
 *     max_hold_time       8.4%  +70.98%   hold 600s  somme  +923 pts
 *
 * Ce -66.45% dit quelque chose de précis : **quand Mayhem sort complètement, le token a déjà
 * chuté des deux tiers.** Sa sortie n'est pas un signal avancé, c'est un signal retardé, et la
 * copier revient à vendre après la baisse plutôt qu'avant. `sellOnMayhemFullExit` a été écrit
 * comme une protection ; mesuré, c'est le premier poste de perte de la meilleure variante.
 * D'où l'axe de ce cycle. `grace-60s` devient la référence de travail, `grace-15s` cède sa
 * place : elle est au mieux à égalité (rendement pondéré -6.06% contre -6.00%) et nettement
 * derrière sur la médiane (-14.75% contre -6.22%).
 *
 * Contrôles anti-artefact passés sur les 829 allers-retours : 0 incohérence raison/signe,
 * 0 slippage nul des deux côtés, 0 gagnant >2x hors de la plage on-chain. Les 6 multiples
 * >3x en moins de 60s plafonnent à 3.2x, portent du slippage réel des deux côtés, et se
 * retrouvent à l'identique sur plusieurs variantes pour le même mint — ce sont de vraies
 * pompes, pas des artefacts.
 *
 * Rappels durables :
 * - Le filtre de profondeur du pool est **réfuté** (dégradation monotone du rendement pondéré
 *   et effondrement des queues quand on le durcit). Tenu constant à 40 SOL, comme contrôle.
 * - Priority fee **mesuré** à 0.000025 SOL, pas supposé. Le modèle a facturé 0.003 pendant
 *   longtemps, soit 120x trop, ce qui a invalidé toutes les conclusions antérieures.
 *
 * Capitaux remis à 2 SOL : les quatre variantes ont fini la fenêtre à solde 0.0000 et ne
 * pouvaient plus ouvrir de position. L'historique des trades reste en base — c'est lui qui
 * porte l'information, pas le solde.
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
    name: "Grace 60s, sans suivre la sortie de Mayhem",
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
    name: "Grace 60s (référence de travail)",
    description:
      "Meilleure variante de la fenetre precedente et nouvelle reference de comparaison : stop-loss suspendu 60 secondes, sortie sur la sortie complete de Mayhem conservee. Mediane -6.22% contre -21.88% pour liquid-only, queues >+100% a 5.8% contre 3.8%, part des sorties en stop_loss ramenee de 73.4% a 14.3%. C'est la variante dont grace-60s-nofollow ne change qu'UNE chose.",
    kind: "generic",
    enabled: true,
    ...BASE,
    stopLossGraceSeconds: 60,
  },
  {
    id: "no-stop",
    name: "Sans stop-loss",
    description:
      "Borne de l'axe stop : aucun stop-loss du tout, sorties par trailing stop, max-hold 600s ou sortie complete de Mayhem. Reponse de la fenetre precedente : c'est la PIRE en rendement pondere (-7.44%), alors qu'elle a la meilleure mediane apres grace-60s. Autrement dit supprimer entierement le stop ne paie pas — l'optimum est une temporisation, pas une suppression. Conservee pour verifier que ce resultat se reproduit, puisqu'un signal d'une seule fenetre n'est pas un signal.",
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
