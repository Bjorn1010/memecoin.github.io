# Mayhem bot — état des connaissances

Source de vérité pour les cycles autonomes. À relire au début de chaque cycle, et à mettre
à jour à la fin. La consigne de la Routine pointe ici plutôt que de dupliquer ces faits,
parce qu'une consigne figée devient fausse au bout de deux cycles et induit en erreur.

## Coûts réels (mesurés, pas supposés)

- **Priority fee : 0.000025 SOL par transaction.** Mesuré sur 40 transactions Mayhem lues
  on-chain (`src/tools/measureFees.ts`). Le modèle a longtemps facturé 0.003 — **120x trop**.
  Sur 364 jambes cela représentait 1.09 SOL de frais fictifs contre 0.009 réels, assez pour
  ruiner un capital de 2 SOL à lui seul. **Toute conclusion de rentabilité antérieure à cette
  mesure est invalide, y compris les conclusions négatives.**
- **Frais de plateforme : 1% par jambe, 2% par aller-retour.** Celui-ci est réel (pump.fun) et
  c'est désormais le coût qui contraint. Une variante n'est viable que si son edge de prix
  dépasse 2%.

## Ce qui marche

- **`maxHoldSeconds = 600` est indispensable.** Sans lui, une position sur un token mort ne
  sort jamais : pas de trade = pas de mouvement de prix = aucun seuil déclenché. La stratégie
  se bloque à 8/8, et les comparaisons deviennent une course à la saturation plutôt qu'un test
  de politique de sortie.

C'est tout, à ce jour. Rien d'autre n'a survécu à une seconde fenêtre.

## Ce qui est réfuté

- Trail large -45% : pire taux de gagnants (16%).
- Stop serré -6% : indiscernable de -12%.
- Grosses positions (0.75 SOL) : edge de prix -11.4%, ruinée en minutes. Baisser la charge
  fixe en pourcentage n'aide pas si l'edge est négatif.
- **Filtre de profondeur du pool : réfuté, et je l'avais annoncé à l'envers.** Sur 979
  allers-retours au coût réel, en rendement **pondéré par le capital engagé** (et non en
  moyenne non pondérée de pourcentages, qui donne le même poids à un aller-retour qu'à cent),
  il se dégrade de façon monotone quand on le durcit :
  40 SOL -5.98% (n=651) ; 150 SOL -9.23% (n=126) ; 250 SOL -12.33% (n=64) ;
  150 SOL + conviction -14.79% (n=15). La fréquence des queues >+100% s'effondre dans le même
  sens : 4.1% / 3.2% / 1.6% / 0.0%. Le filtre supprime les événements qui portent tout le
  rendement. Un cycle plus tôt j'avais écrit « plus le pool est profond, meilleurs sont le
  taux de gagnants et l'edge » sur une fenêtre unique : ça ne s'est pas reproduit. Profondeur
  tenue constante à 40 SOL désormais, comme contrôle.
- **Post-migration : prémisse morte.** 20 migrations détectées, pools à 1$-126$ (médiane ~6$)
  des heures après. Décodeur vérifié correct (octet 48 = complete, réserves nulles) : les
  courbes se terminent vraiment, mais les tokens sont vidés dans la foulée.
  **Ne jamais baisser `MIN_POST_MIGRATION_LIQUIDITY_USD` (25000)** : c'est la seule protection
  contre des fills sur des pools à 6$. La stratégie reste une sonde ; qu'elle ne trade jamais
  est le résultat attendu.

## Le stop-loss est plus étroit que le bruit dans lequel il baigne

Le résultat le plus solide obtenu jusqu'ici. **Le mécanisme est confirmé, le gain net ne l'est
pas** — la perte a changé de guichet plutôt que de disparaître.

Répartition des sorties de la référence historique (n=312, fenêtre 12:22-13:12) :

| sortie | part | rendement moyen | hold médian |
|---|---|---|---|
| `stop_loss` | 73.4% | **-28.72%** | **1 s** |
| `trailing_stop` | 22.4% | +40.78% | 4 s |
| `max_hold_time` | 3.5% | +72.05% | 600 s |

Un stop nominal à -12% qui se réalise à -28% en une seconde ne coupe pas une tendance : il se
déclenche avant qu'une tendance existe. Ce n'est ni du slippage (0.19% médian) ni des frais
(1.78%) — le prix bouge vraiment, et la détection n'est pas en retard (lag médian sous la
seconde, achats bookés en 1 ms).

Reconstruit **indépendamment de notre simulation**, sur les seuls événements on-chain de Mayhem
(3910 achats éligibles, pool ≥40 SOL) :

| horizon | médiane | p25 | p75 | >+100% |
|---|---|---|---|---|
| t+2s | -0.10% | -28.21% | +17.19% | 3.0% |
| t+5s | -4.20% | -41.57% | +15.82% | 6.2% |
| t+15s | -24.46% | -67.23% | +5.12% | 8.0% |
| t+60s | -72.03% | -95.22% | -0.07% | 7.2% |

L'écart interquartile à 2 secondes va de -28% à +17% : le seuil de -12% est deux fois plus
étroit que le bruit dans lequel il baigne, donc il ne discrimine rien et encaisse la moitié
basse. Et la fréquence des queues croît avec l'horizon pendant que la médiane s'effondre — il y
a un arbitrage, pas un réglage évident.

Attention au `t+300s` (médiane -28.73%, moyenne +3105%) : n=585 sur 3910, conditionné à ce que
Mayhem trade encore le mint 5 minutes plus tard. **Biais de survie massif, ne pas s'en servir.**

### Ce que la temporisation a donné (829 allers-retours, fenêtre 12:22-13:12)

| variante | n | rend. pondéré | médiane | >+100% | part `stop_loss` |
|---|---|---|---|---|---|
| liquid-only | 312 | -7.09% | -21.88% | 3.8% | 73.4% |
| grace-15s | 203 | -6.06% | -14.75% | 5.4% | 34.5% |
| grace-60s | 154 | **-6.00%** | **-6.22%** | **5.8%** | 14.3% |
| no-stop | 149 | -7.44% | -6.55% | 4.7% | 0.0% |

Tout ce que la temporisation devait produire, elle le produit : médiane -21.88% → -6.22%,
queues 3.8% → 5.8%, part du `stop_loss` 73.4% → 14.3% au profit du trailing stop (22.4% →
46.8%), qui est la sortie rentable. **Et pourtant le rendement pondéré ne bouge presque pas.**

Deux enseignements à garder :
- **Supprimer entièrement le stop ne paie pas.** `no-stop` est la pire en rendement pondéré
  (-7.44%) malgré une bonne médiane. L'optimum est une temporisation, pas une suppression.
- **60s > 15s**, mais l'écart est sur la médiane, pas sur le rendement pondéré (-6.00% contre
  -6.06%, égalité). Ne pas surinterpréter.

## `sellOnMayhemFullExit` : la sortie de Mayhem est un signal retardé

La fuite qu'a révélée la temporisation, et l'axe testé actuellement. `mayhem_full_exit` passe
de 0.6% des sorties (n=2) chez liquid-only à 30.5% (n=47) chez grace-60s, **à -66.45% de
rendement moyen**, soit -3123 points : le premier poste de perte de la meilleure variante.

Le stop-loss fermait la position à une seconde ; en le temporisant, ces positions vivent assez
longtemps pour être fermées par la sortie de Mayhem — plus tard et beaucoup plus bas. Ce
-66.45% dit quelque chose de précis : **quand Mayhem sort complètement, le token a déjà chuté
des deux tiers.** Sa sortie n'est pas un signal avancé mais retardé, et la copier revient à
vendre après la baisse. `sellOnMayhemFullExit` a été écrit comme une protection ; mesuré, c'est
la principale perte.

Roster en cours : `liquid-only` (témoin historique) / `grace-60s` (référence de travail) /
`grace-60s-nofollow` (le test) / `no-stop` (borne de l'axe stop) / `post-migration` (sonde).

## Distribution source

Trades de Mayhem : **médiane -47.6%, moyenne +26.7%** — une loterie portée par ~9.6% de trades
à +100% et plus. Il faut capturer la queue sans se faire saigner par les perdants fréquents ni
par les frais. Sa taille d'achat médiane est 0.0249 SOL (p90 = 0.164, p99 = 1.08).

## Statut

Aucune configuration n'est démontrée rentable à ce jour. Capitaux remis à 2 SOL aux cycles du
31/08 12:10 puis 13:15 (les quatre variantes finissaient la fenêtre à solde 0.0000) : la référence était tombée à 0.139 SOL et ne pouvait plus ouvrir de position,
donc plus servir de contrôle. L'historique des trades reste en base — c'est lui qui porte
l'information, pas le solde. Si aucune ne tient après de nombreux
cycles, « ce wallet n'est pas copiable de façon rentable » est une conclusion valide et utile.
**Ne pas fabriquer un résultat positif.**
