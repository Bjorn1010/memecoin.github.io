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

## LA TEMPORISATION DU STOP EST RÉFUTÉE (résultat significatif)

Premier résultat franchement concluant de tout le projet, et il annule ma conclusion du matin.

Il a fallu supprimer la contention d'emplacements (60 positions, 20 SOL) pour l'obtenir : les
variantes prennent désormais **99.0% des mêmes entrées** (302 mints communs sur 305), ce qui rend
enfin valide la **comparaison appariée mint par mint** — la seule mesure qui élimine la variance
de régime de marché, dominante et jusque-là confondue avec l'effet des politiques.

Écart apparié contre la référence (stop immédiat), fenêtre 15:10-16:09 :

| variante | n | écart moyen | médiane | gagne sur | IC 90% |
|---|---|---|---|---|---|
| grace-60s | 299 | -2.07 pts | +0.00 | 19% | [-5.16, +1.51] |
| grace-60s-nofollow | 297 | -4.90 pts | +0.00 | 27% | [-9.66, **-0.26**] |
| grace-20s-nofollow | 298 | -5.83 pts | +0.00 | 20% | [-9.35, **-2.18**] |

Les deux dernières ont un **intervalle qui exclut zéro** : significativement pires que le stop
immédiat. Écart médian nul, gain sur seulement 19-27% des mints — la plupart du temps la
temporisation ne change rien, et quand elle change quelque chose elle perd plus qu'elle ne gagne.

**Le diagnostic restait juste, le remède coûte plus cher que le mal.** Le stop à -12% est bien
plus étroit que la dispersion à 2 secondes (interquartile -28% / +17%), il coupe donc dans le
bruit. Mais couper vite à -28% bat couper tard à -70%. La mesure on-chain le disait déjà sans que
j'en tire la conséquence : médiane **-24.46% à t+15s, -72.03% à t+60s**. Laisser respirer les
perdants coûte plus que ce que rapporte laisser respirer les gagnants.

### L'évaluateur hors-ligne classe ces politiques À L'ENVERS

Il donnait `grace 20s` meilleure que la référence (+2.96% contre +1.60%) là où le test apparié la
donne **pire de 5.83 points avec IC excluant zéro**. La cause est structurelle : son chemin de
prix n'est échantillonné qu'aux transactions de Mayhem, il ne voit pas les creux intra-seconde
qui déclenchent 79% des sorties de la référence à un hold médian d'UNE seconde. **Son biais
d'optimisme n'est donc pas uniforme** : il favorise exactement les politiques qui évitent les
stops rapides.

**Ne jamais utiliser le replay pour classer des politiques différant par le timing du stop.**
Il reste valide pour les effets lents — largeur du trailing, seuil d'armement, durée max.

## `sellOnMayhemFullExit` : effet non démontré

Quand Mayhem sort complètement, le token a déjà chuté : `mayhem_full_exit` se réalise à -49%
à -66% de rendement moyen selon la fenêtre, et représente 40-52% des sorties des variantes
temporisées. Sa sortie est donc un signal **retardé**.

**Mais désactiver le suivi n'a pas d'effet démontrable.** Test apparié sur les 30 mints communs
où `grace-60s` est effectivement sorti sur `mayhem_full_exit` : nofollow fait mieux sur 12/30,
écart médian -1.4 pt (la moyenne +20 pts est portée par des valeurs extrêmes). C'est un pile ou
face. `grace-60s-nofollow` est bien la meilleure variante, mais **pas pour la raison qu'on lui
prête** — et c'est exactement le piège dans lequel la profondeur des pools m'a fait tomber.

## Hypothèses testées et mortes

- **Le taux d'occupation ne prédit pas la qualité d'une entrée.** Sur ~1500 allers-retours,
  médiane -22.6% à 0 position ouverte, -3.99% à 8, -32.8% à 9. Aucune monotonie. L'idée d'un
  « régime de marché » lisible dans le nombre de positions ouvertes est morte.
- **Supprimer entièrement le stop ne paie pas.** `no-stop` est la pire variante deux fenêtres de
  suite (-7.44% puis -12.10% en rendement pondéré) malgré une bonne médiane. L'optimum est une
  temporisation, pas une suppression.

## Ce qui reste debout : le trailing stop est la seule sortie rentable

Vrai dans toutes les variantes et toutes les fenêtres : +64.91% chez `grace-60s-nofollow`,
+43.36% chez `grace-60s`, +33.75% chez `liquid-only`. Sa part varie de 18.7% à 41.4% selon la
politique de sortie. **Tout ce qui augmente la proportion de sorties par trailing stop améliore
le résultat** — c'est le fil conducteur le plus fiable dont on dispose.

Chez la meilleure variante, ce qui tronque encore les positions est le stop à 60s :

    stop_loss       45.7%   -70.12%   hold  60s   somme -5960 pts
    trailing_stop   41.4%   +64.91%   hold  11s   somme +4998 pts
    max_hold_time   12.9%   +41.50%   hold 600s   somme  +996 pts

Ce -70.12% colle exactement à la décroissance mesurée on-chain (médiane -72.03% à t+60s contre
-24.46% à t+15s) : la temporisation à 60s laisse les gagnants respirer, mais laisse aussi les
perdants tomber jusqu'au bout. D'où l'axe en cours, 20 secondes.

Roster : `liquid-only` (témoin) / `grace-60s-nofollow` (référence de travail) / `grace-60s`
(suit Mayhem) / `grace-20s-nofollow` (le test) / `post-migration` (sonde).

## LE PROBLÈME DE MESURE — à lire avant toute comparaison de variantes

Rendement pondéré de configurations **inchangées** sur trois fenêtres consécutives :

| variante | 12:22-13:12 | 13:15-14:11 | 14:13-15:09 |
|---|---|---|---|
| liquid-only | -7.09% | -11.55% | -7.88% |
| grace-60s | -6.00% | -7.34% | -18.58% |
| grace-60s-nofollow | -- | **+0.18%** | **-19.70%** |

`liquid-only` n'a pas bougé d'un paramètre et oscille sur 4.5 points. `grace-60s-nofollow`,
annoncée « meilleur résultat à ce jour » à +0.18%, revient à -19.70% la fenêtre suivante.

Intervalles de confiance à 90% (bootstrap 4000 tirages, fenêtres poolées) :

| variante | n | estimation | IC 90% | largeur |
|---|---|---|---|---|
| liquid-only | 856 | -8.49% | [-11.54%, -5.20%] | 6.3 pts |
| grace-60s | 468 | -9.09% | [-15.31%, -2.83%] | 12.5 pts |
| grace-60s-nofollow | 297 | -5.46% | [-15.37%, +5.48%] | 20.9 pts |
| grace-20s-nofollow | 178 | -8.65% | [-19.32%, +2.60%] | 21.9 pts |
| grace-15s | 202 | -6.06% | [-13.55%, +1.51%] | 15.1 pts |
| no-stop | 286 | -9.63% | [-17.14%, -1.51%] | 15.6 pts |

**Tous les intervalles se recoupent.** Aucune variante n'est distinguable d'une autre ni de la
référence ; les estimations tiennent toutes entre -5% et -10%. Sur une distribution en loterie,
quelques centaines d'allers-retours ne suffisent pas — la queue porte le résultat et sa
fréquence d'apparition est elle-même très bruitée.

**Conséquence : ne jamais annoncer une variante gagnante sur une seule fenêtre.** Exiger que
l'écart survive à une deuxième fenêtre ET dépasse la largeur de l'intervalle de confiance.

## Le correctif : supprimer la contention d'emplacements

La cause du bruit est identifiée. Les variantes **ne prenaient pas les mêmes entrées** : dès
qu'une politique de sortie garde ses positions plus longtemps, ses 8 emplacements saturent et
elle rate des entrées que les autres prennent. La comparaison mélangeait la politique de sortie
et le hasard de l'occupation, et le second dominait. C'est ce qui avait fait attribuer à tort le
résultat de `grace-60s-nofollow` au fait de ne pas suivre Mayhem.

Depuis le cycle 15:10 : `maxConcurrentPositions` = 60 et capital = 20 SOL, donc plus aucune
contention possible (60 x 0.15 = 9 SOL de déploiement maximum contre 20 disponibles). Toutes les
variantes voient **exactement le même flux d'entrées**.

**La comparaison appariée mint par mint devient la mesure principale** : elle élimine la variance
de régime de marché, qui est la source de bruit dominante, et c'est le seul test qui ait produit
ici une réponse stable. Le rendement pondéré reste sans dimension, donc comparable aux fenêtres
antérieures malgré le changement d'échelle du capital.

## L'évaluateur hors-ligne (`src/tools/replay.ts`)

Construit au cycle 15:20 pour attaquer le vrai goulot : une fenêtre live produit ~200
allers-retours en 50 minutes, avec un IC90 de 6 à 22 points — trop large pour trancher quoi que
ce soit. Le replay rejoue les événements déjà en base : **4346 entrées éligibles en 2.3
secondes**, autant de fois qu'on veut. `npx tsx src/tools/replay.ts`.

Il réutilise `simulateBuy`/`simulateSell` et `PLATFORM_FEE_PCT` du moteur réel — réimplémenter
la comptabilité reviendrait à comparer deux modèles différents.

**Trois bugs trouvés dans l'outil lui-même avant de croire un seul de ses chiffres.** À
connaître, ils se reproduiront :

1. **Biais de survie → +46.29% fabriqué.** Les positions n'atteignant aucun seuil avant la fin
   du chemin étaient jetées. Or un token mort cesse d'être tradé par Mayhem, donc n'a plus
   d'observations, donc ne peut plus déclencher de sortie : les jeter revient à jeter les pires
   perdants. « Sans stop » abandonnait ainsi 47% de ses positions. Elles sont désormais closes
   de force à la dernière observation, et le taux de clôtures forcées est affiché.
2. **Générateur aléatoire cassé.** Un LCG naïf en flottant JS (`seed * 1103515245`) dépasse 2^53
   au premier tour et perd ses bits faibles. Symptôme : **l'IC n'encadrait pas son estimation
   ponctuelle** — c'est toujours un bug de générateur, jamais un résultat. Remplacé par
   mulberry32 (`Math.imul`, arithmétique 32 bits exacte).
3. **`full_exit` est un KIND d'événement**, pas un `sell` à solde nul. Le solde résiduel n'est
   jamais exactement zéro (minimum observé 0.648 token de poussière) ; c'est `txParser` qui
   applique `DUST_UI_AMOUNT` à l'écriture. Symptôme : deux politiques ne différant que par
   `sellOnMayhemFullExit` rendaient des résultats **rigoureusement identiques**.

### BIAIS D'OPTIMISME — ne jamais lire un chiffre positif du replay comme « rentable »

Le replay rend **+0.5% à +3.0%** là où les mêmes politiques rendent **-5% à -10% en live**.
L'écart est structurel et va toujours dans ce sens : en live 66-73% des sorties partent en
`stop_loss` à un hold médian d'UNE seconde, sur des creux intra-seconde que le chemin
échantillonné (uniquement les transactions de Mayhem, médiane ~103 observations après l'entrée)
ne voit pas. **C'est un comparateur de politiques sur effets lents, pas un prédicteur de PnL.**
Toute conclusion doit être confirmée en fenêtre live.

### Ce qu'il dit aujourd'hui

| politique | n | rend. pondéré | IC 90% | médiane | >+100% | forcées |
|---|---|---|---|---|---|---|
| référence (stop immédiat) | 4346 | +1.60% | [-0.2, +3.5] | -18.74% | 5.6% | 12.8% |
| grace 20s | 4346 | +2.96% | [+0.2, +5.7] | -16.10% | 9.3% | 19.0% |
| grace 60s | 4346 | +1.33% | [-1.5, +4.2] | -11.30% | 9.5% | 22.9% |
| grace 60s nofollow | 4346 | +1.93% | [-1.1, +4.8] | -5.51% | 10.1% | 30.3% |
| sans stop | 4346 | +0.54% | [-2.4, +3.4] | -6.23% | 9.9% | 27.6% |
| trail armé à +20% | 4346 | +1.88% | [+0.1, +3.8] | -17.67% | 5.4% | 12.4% |
| trail serré -15% | 4346 | +1.76% | [+0.1, +3.5] | -18.61% | 5.4% | 11.9% |

**Tous les intervalles se recoupent largement** — même verdict que le live, sur 20x plus de
données : aucune politique de sortie n'est distinguable des autres. La temporisation améliore
nettement la médiane (-18.74% → -5.51%) et double la fréquence des queues (5.6% → 10.1%) sans
que le rendement pondéré suive, ce qui est cohérent avec tout ce qui précède.

## Distribution source

Trades de Mayhem : **médiane -47.6%, moyenne +26.7%** — une loterie portée par ~9.6% de trades
à +100% et plus. Il faut capturer la queue sans se faire saigner par les perdants fréquents ni
par les frais. Sa taille d'achat médiane est 0.0249 SOL (p90 = 0.164, p99 = 1.08).

## Statut

Aucune configuration n'est démontrée rentable à ce jour, **ni même démontrée différente d'une
autre** : voir la section sur le problème de mesure. Capitaux remis à 2 SOL aux cycles du
31/08 12:10 puis 13:15 (les quatre variantes finissaient la fenêtre à solde 0.0000) : la référence était tombée à 0.139 SOL et ne pouvait plus ouvrir de position,
donc plus servir de contrôle. L'historique des trades reste en base — c'est lui qui porte
l'information, pas le solde. Si aucune ne tient après de nombreux
cycles, « ce wallet n'est pas copiable de façon rentable » est une conclusion valide et utile.
**Ne pas fabriquer un résultat positif.**
