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

Le résultat le plus solide obtenu jusqu'ici, et l'axe testé actuellement.

Répartition des sorties de la référence (n=651, coût réel) :

| sortie | part | rendement moyen | hold médian | somme |
|---|---|---|---|---|
| `stop_loss` | 72.2% | **-28.29%** | **1 s** | -13299 pts |
| `trailing_stop` | 20.1% | +55.79% | 6 s | +7308 pts |
| `max_hold_time` | 6.8% | +40.52% | 600 s | +1783 pts |
| `mayhem_full_exit` | 0.9% | -3.99% | 7 s | -24 pts |

Un stop nominal à -12% qui se réalise à -28% en une seconde ne coupe pas une tendance : il se
déclenche avant qu'une tendance existe. Décomposition des 451 sorties `stop_loss` en ≤2s :
edge de prix médian -21.22%, slippage achat +0.19%, slippage vente -0.19%, frais 1.78%. **Ce
n'est ni du slippage ni des frais — le prix bouge vraiment.** Et la détection n'est pas en
retard : le lag médian entre `block_time` et notre détection est sous la seconde, et nos
achats sont bookés en 1 ms.

Reconstruit **indépendamment de notre simulation**, à partir des seuls événements on-chain de
Mayhem (3910 achats éligibles, pool ≥40 SOL), le prix après un achat de Mayhem vaut :

| horizon | médiane | p25 | p75 | >+100% |
|---|---|---|---|---|
| t+2s | -0.10% | -28.21% | +17.19% | 3.0% |
| t+5s | -4.20% | -41.57% | +15.82% | 6.2% |
| t+15s | -24.46% | -67.23% | +5.12% | 8.0% |
| t+60s | -72.03% | -95.22% | -0.07% | 7.2% |

Deux lectures simultanées : (1) l'écart interquartile à 2 secondes va de -28% à +17%, soit une
dispersion bien plus large que le seuil de -12% du stop — un seuil plus étroit que le bruit ne
discrimine rien, il encaisse la moitié basse ; (2) la fréquence des queues >+100% **croît avec
l'horizon** (3.0% → 8.0%), donc sortir en une seconde interdit structurellement d'atteindre
l'endroit où le rendement se trouve. Mais la médiane s'effondre avec le même horizon, donc
attendre n'est pas gratuit : il y a un arbitrage, et son optimum est ce qu'on mesure.

Attention au `t+300s` (médiane -28.73%, moyenne +3105%) : n=585 sur 3910, conditionné à ce que
Mayhem trade encore le mint 5 minutes plus tard. Biais de survie massif, ne pas s'en servir.

Roster en cours : `liquid-only` (stop immédiat, référence) / `grace-15s` / `grace-60s` /
`no-stop` (borne supérieure) / `post-migration` (sonde). Un seul axe varie.

## Artefacts démasqués (quatre) — à re-tester avant d'annoncer tout gain

1. Entrée bookée au prix d'une bonding curve **en cours de vidage** à la migration → faux +1300%.
2. Données de curve **réinjectées pour un mint déjà migré** → sortie 22x hors plage, et un
   `stop_loss` booké sur +176%.
3. Entrée **sans réserves connues** (slippage 0) appariée à une sortie calculée sur réserves →
   8 allers-retours de 3.5x à 13x en quelques secondes. **Les deux prix étaient dans la plage
   on-chain : le contrôle de plage seul ne suffit pas.**
4. Fills post-migration à **slippage nul dans un pool quasi vide** → +1464% en 81 secondes.

Contrôles à appliquer : prix d'entrée **et** de sortie contre la plage on-chain
(`mayhem_events`) ; multiple énorme sur durée courte ; slippage exactement 0 des deux côtés ;
slippage incohérent avec la profondeur du pool ; `stop_loss` à pct positif ou `take_profit` à
pct négatif. Un gain spectaculaire sur une durée courte est **suspect par défaut**.

Nuance : pour un mint migré, nos prix viennent de DexScreener alors que `mayhem_events`
contient des prix de bonding curve d'avant migration — la comparaison de plage sonnera « hors
plage » à tort. Juger alors sur l'amplitude réelle du mint et la durée.

## Distribution source

Trades de Mayhem : **médiane -47.6%, moyenne +26.7%** — une loterie portée par ~9.6% de trades
à +100% et plus. Il faut capturer la queue sans se faire saigner par les perdants fréquents ni
par les frais. Sa taille d'achat médiane est 0.0249 SOL (p90 = 0.164, p99 = 1.08).

## Statut

Aucune configuration n'est démontrée rentable à ce jour. Capitaux remis à 2 SOL au cycle du
31/08 12:10 : la référence était tombée à 0.139 SOL et ne pouvait plus ouvrir de position,
donc plus servir de contrôle. L'historique des trades reste en base — c'est lui qui porte
l'information, pas le solde. Si aucune ne tient après de nombreux
cycles, « ce wallet n'est pas copiable de façon rentable » est une conclusion valide et utile.
**Ne pas fabriquer un résultat positif.**
