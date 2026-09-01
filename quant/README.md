# qt — stack de recherche quantitative et paper trading

Système de trading quantitatif complet, construit **uniquement sur des données publiques
gratuites** (aucune clé API), **100 % paper trading** (aucun code d'exécution réelle
n'existe dans ce dépôt), et entièrement algorithmique — pas de LLM dans la boucle de
décision.

```bash
cd quant
python3 -m venv .venv && .venv/bin/pip install -e .

.venv/bin/qt ingest --symbols BTCUSDT,ETHUSDT --interval 1h --start 2021-01-01
.venv/bin/qt research BTCUSDT          # ensemble de règles vs buy-and-hold, coûts réels
.venv/bin/qt walkforward BTCUSDT       # ML réentraîné en marche avant
.venv/bin/qt replay BTCUSDT --bars 500 # rejoue l'historique dans la boucle live
.venv/bin/qt serve                     # API + dashboard sur :8000
```

---

## Ce que ce système essaie de faire, et ce qu'il ne fait pas

Il n'y a pas d'algorithme secret rentable, et aucune IA ne « sait tout » sur les
marchés. Ce qui distingue une recherche quantitative sérieuse d'un backtest qui
s'effondre en réel, c'est un très petit nombre de propriétés, toutes ennuyeuses :

1. **Aucune fuite temporelle.** Aucune feature ne peut voir le futur, jamais.
2. **Des coûts honnêtes.** Frais, spread, impact de marché et funding, tous facturés.
3. **Une validation qui punit la sélection.** Un Sharpe choisi parmi 200 essais n'est
   pas un Sharpe.
4. **Un moteur de risque que rien ne peut contourner.**

Tout le dépôt est organisé autour de ces quatre points. Les résultats qu'il produit
sont souvent décevants — c'est le comportement correct. Un système qui ne peut pas
vous dire « cette stratégie ne marche pas » ne peut pas non plus vous dire l'inverse.

---

## Données — tout est gratuit et sans clé

Sources vérifiées comme accessibles et normalisées vers un schéma unique (`qt/data/`) :

| Source | Contenu | Pourquoi elle est là |
|---|---|---|
| **data.binance.vision** | klines 1s→1d depuis 2017, aggTrades tick, bookTicker (L1), funding | L'archive publique la plus riche en crypto. Ses klines incluent `taker_buy_volume`, donc le **flux d'ordres signé est gratuit** — c'est là que se trouve l'essentiel du signal de microstructure, et la plupart des sources « gratuites » jettent cette colonne. |
| **Hyperliquid** | perps, candles, funding, open interest | Accessible partout, sert de flux live et de contre-vérification indépendante |
| **Coinbase** | WebSocket trades (avec côté agresseur), candles REST | Le flux live du paper trading |
| **Kraken** | OHLC et spread récents | Contrôle de cohérence des prix entre venues |
| **Deribit** | DVOL (l'indice de vol implicite crypto) | Prime de risque de variance, un régime-detector propre |
| **Stooq** | EOD actions, indices, VIX, DXY, or, crédit | Contexte cross-asset — une des rares sources d'information *orthogonale* |

Le lac de données est en Parquet immuable + DuckDB pour la recherche :

```bash
qt lake
qt catalog-sql "SELECT count(*) FROM lake('klines_1h','binance','BTCUSDT')"
```

---

## Architecture

```
qt/
├── data/         lac Parquet + DuckDB, 6 adaptateurs de venues, schémas canoniques
├── bars/         barres tick/volume/dollar/imbalance/run + filtre d'événements CUSUM
├── features/     ~255 features, toutes causales (prouvé par test)
├── labels/       triple-barrière, meta-labeling, poids d'échantillons
├── alphas/       15 alphas, chacun avec sa justification économique + ensemble
├── models/       LightGBM/sklearn, calibration, MDA, registre versionné
├── validation/   CV purgée + embargo, CPCV, Sharpe dégonflé, PBO, bootstrap
├── backtest/     moteur événementiel, modèle de coûts, métriques, walk-forward
├── risk/         vol targeting, Kelly fractionnel, limites dures, coupe-circuits
├── live/         boucle de paper trading, broker simulé, feeds, état SQLite
└── api/          API de monitoring en lecture seule (+ dashboard React)
```

### Barres — pourquoi pas des bougies 1 minute

L'information n'arrive pas à intervalles réguliers. Une minute un dimanche à 3h du
matin et une minute pendant une publication macro ont la même durée et n'ont rien à
voir. Échantillonner sur le temps sur-échantillonne donc le calme et sous-échantillonne
exactement les moments qui portent le signal. Les barres **dollar** (une barre par
tranche de notionnel échangé) produisent des rendements bien plus proches de la
normalité i.i.d. — l'hypothèse que tous les tests statistiques en aval font en silence.

### Features — 255, toutes causales

Prix/momentum, volatilité (5 estimateurs : close-to-close, Parkinson, Garman-Klass,
Rogers-Satchell, Yang-Zhang — leurs **désaccords** sont eux-mêmes des features),
microstructure (order flow imbalance, lambda de Kyle, Amihud, Roll, Corwin-Schultz,
VPIN), indicateurs techniques classiques, structure statistique (Hurst, variance ratio,
entropie, différenciation fractionnaire), régimes, calendrier, cross-sectional
(bêta-neutre) et contexte externe.

La propriété qui compte est vérifiée mécaniquement :

```python
qt.features.assert_causal(bars)   # recalcule sur un historique tronqué,
                                  # exige des valeurs identiques bit à bit
```

Toute utilisation d'une fenêtre centrée, d'un `shift` négatif ou d'un `fit` sur
l'échantillon complet change les valeurs passées et fait échouer ce test. Il tourne sur
**tout le registre** dans la suite de tests.

### Labels — triple barrière

Étiqueter par « le rendement sur N barres est-il positif ? » est presque inutile : ça
ignore le chemin (un trade qui perd 8 % avant de finir à +1 % est compté comme gagnant,
alors qu'aucune position réelle n'aurait survécu) et ça ignore la volatilité (une cible
de +1 % n'a pas le même sens à 20 % et à 120 % de vol annualisée).

La triple barrière pose une prise de profit, un stop et une limite de temps, tous
dimensionnés par la volatilité **courante**. Le label est la première barrière touchée —
exactement ce qu'une position réelle avec un stop réel aurait vécu.

Le **meta-labeling** sépare le côté (quelle direction) de la taille (faut-il y aller) :
un modèle primaire donne la direction, un second modèle prédit uniquement si cet appel
va payer. C'est un problème d'apprentissage bien plus facile, et c'est ce qui permet de
rentabiliser un signal médiocre mais réel en le dimensionnant correctement.

### Poids d'échantillons — le piège des labels qui se chevauchent

Un label à 10h couvrant 24h partage 23 heures avec celui de 11h. Les traiter comme
indépendants gonfle la taille d'échantillon effective d'un ordre de grandeur — c'est
précisément pourquoi tant de modèles semblent significatifs in-sample et s'évaporent
ensuite. Trois corrections sont appliquées : unicité (1/concurrence), attribution par le
rendement réalisé, et décroissance temporelle.

### Validation — la partie que la plupart des backtests sautent

- **CV purgée avec embargo** : on retire de l'entraînement tout label dont la durée de
  vie chevauche la période de test, plus un tampon derrière.
- **CPCV** : produit plusieurs trajectoires de backtest au lieu d'une, donc une
  *distribution* à laquelle comparer le résultat.
- **Sharpe dégonflé (DSR)** : si vous testez 100 stratégies aléatoires, la meilleure
  affichera un Sharpe d'environ 2,5 sans aucun edge. Le DSR relève la barre au niveau
  de ce que la chance produirait sur N essais. `n_trials` compte **toutes** les
  configurations évaluées, y compris celles jetées parce qu'elles étaient mauvaises.
- **PBO** : à quelle fréquence le gagnant in-sample finit sous la médiane out-of-sample.
- **Bootstrap par blocs** : la distribution de drawdown que le même edge aurait pu
  produire — bien plus honnête que le seul drawdown qui s'est trouvé se produire.

### Coûts — là où meurent la plupart des edges

Une stratégie horaire qui retourne son book une fois par jour paie ~36 %/an rien qu'en
frais taker. Le modèle facture séparément commission, spread, impact
(`impact = coeff × σ × √participation`, la loi en racine carrée standard) et funding.

Deux corrections issues de la construction de ce système, documentées dans le code :

- L'estimateur de spread **Corwin-Schultz est fortement biaisé à la hausse sur des
  barres intraday** : ~16 bps de médiane sur du BTC horaire, contre un spread réel
  inférieur à 1 bp. Assez pour déclarer morte une stratégie rentable. Il n'est donc pas
  le défaut ; les vraies cotations (archive bookTicker, gratuite) le sont.
- L'impact doit être **proportionnel à la volatilité de la barre**. Un coefficient
  constant se trompe dans les deux régimes.

`capacity_curve()` répond à la question que tout backtest devrait poser et ne pose
presque jamais : à partir de quelle taille l'edge disparaît-il ?

### Backtester — la règle structurelle

**Un signal calculé sur la clôture de la barre t est exécuté à l'ouverture de t+1.**
Pas à la clôture de t, ce qui est la triche silencieuse la plus répandue. La règle est
imposée par la structure de la boucle, pas par un `shift` qu'on peut oublier.

Trois tests la verrouillent :

| test | ce qu'il prouve |
|---|---|
| `test_perfect_knowledge_of_the_current_bar_earns_nothing` | connaître la barre qui vient de clôturer ne rapporte rien |
| `test_perfect_foresight_does_earn` | un vrai oracle à une barre gagne énormément (contrôle : le moteur trade bien) |
| `test_shifting_a_signal_later_destroys_its_edge` | retarder le signal détruit son edge |

### Risque — la seule couche qui a le droit de dire non

Chaque poids cible passe par `RiskEngine.apply` avant de devenir une position, et le
moteur ne peut que **réduire** l'exposition. Vol targeting, Kelly fractionnel (jamais
plein : plein Kelly sur-parie dès qu'il y a une erreur d'estimation, et il y en a
toujours), plafonds par instrument, levier brut, nombre de positions, dé-risquage
progressif à l'approche de la limite de drawdown.

Deux coupe-circuits, avec des sémantiques volontairement différentes :

- **Perte journalière** → flat + arrêt, **reprise automatique** à la session suivante
  (une mauvaise journée n'est pas la preuve d'un système cassé).
- **Drawdown maximum** → flat + arrêt, **redémarrage manuel obligatoire** (si le modèle
  est cassé, un redémarrage automatique se contente de continuer à perdre).

### Boucle de paper trading

```
barre clôturée → historique → features → signal → vol targeting → moteur de risque
→ broker simulé → mark-to-market → persistance SQLite
```

Le broker partage le **même modèle de coûts que le backtester**, donc une session paper
et un backtest de la même période sont directement comparables — s'ils divergent, l'un
des deux a un bug, et c'est l'information la plus utile que la boucle produit.

La boucle est défensive : une exception du feed, un signal NaN ou une stratégie qui
lève ne tuent jamais le processus et ne laissent jamais une position non gérée. Tout ce
qu'elle ne comprend pas se traduit par **aucun risque nouveau**, jamais par une
supposition.

`qt replay` rejoue de l'historique dans cette boucle exacte — même constructeur de
barres, mêmes features, même broker. C'est le test d'intégration de toute la pile live.

---

## Résultats de référence (BTCUSDT 1h, 2021-2024, 35 026 barres)

Reproductibles avec `python scripts/research_btc.py` :

| | ensemble de règles | ML walk-forward | buy & hold |
|---|---|---|---|
| CAGR | −4,8 % | −2,9 % | +29,2 % |
| Vol annualisée | 2,9 % | 5,6 % | 61,0 % |
| Sharpe | −1,68 | −0,50 | 0,72 |
| Max drawdown | −18,1 % | −17,1 % | −77,2 % |
| Turnover annuel | 97× | 59× | 0 |
| **Coûts / rendement brut** | **4,7×** | **3,5×** | 0 |
| Sharpe dégonflé | 0,000 | 0,002 | — |

**Verdict : « indiscernable de la chance de sélection » dans les deux cas.**

C'est le résultat honnête, et c'est le point. Les deux stratégies ont un edge brut
quasi nul en horaire, et les coûts consomment plusieurs fois ce qui reste. Le système a
fait exactement son travail : il a refusé de valider quelque chose qui ne marche pas.

Le turnover est le coupable principal (97×/an). La direction de recherche évidente est
la fréquence plus basse — passer en 4h ou en journalier divise le turnover d'un ordre
de grandeur pour un edge brut comparable :

```bash
qt research BTCUSDT --resample 1D --n-trials 25
```

**Attention en explorant** : chaque configuration testée doit être comptée dans
`--n-trials`. C'est ce qui empêche la recherche de devenir du data-mining déguisé.

---

## Commandes

| commande | rôle |
|---|---|
| `qt ingest` | télécharge l'historique gratuit dans le lac |
| `qt lake` / `qt catalog-sql` | inspecte et interroge le lac |
| `qt features` / `qt alphas` | liste les groupes de features et les alphas avec leurs justifications |
| `qt research SYM` | ensemble de règles vs buy-and-hold + Sharpe dégonflé + bootstrap |
| `qt walkforward SYM` | simulation réentraînée en marche avant |
| `qt train SYM` | entraîne et versionne un modèle (`--importance` pour la MDA) |
| `qt models` | registre des modèles |
| `qt paper` | boucle de paper trading en direct |
| `qt replay SYM` | rejoue l'historique dans la boucle live |
| `qt serve` | API de monitoring + dashboard |
| `qt status` | résumé d'une session depuis la base d'état |

## Tests

```bash
.venv/bin/python -m pytest tests/ -q     # 34 tests, ~25 s
```

`tests/test_no_lookahead.py` contient les tests qui comptent : causalité de tout le
registre de features, convention d'exécution du moteur, purge de la CV, et alignement
features/labels.

## Dashboard

```bash
npm --prefix web install && npm --prefix web run build
qt serve      # http://localhost:8000
```

Équité, drawdown, journal des décisions (ce que la stratégie a demandé, ce que le risque
a autorisé, et pourquoi c'est passé au-dessus), fills avec décomposition des coûts,
positions, et la bibliothèque d'alphas avec ses justifications. **En lecture seule** :
un dashboard qui pourrait modifier des positions est un accident en attente.

---

## Limites — à lire avant de faire confiance à un chiffre

- **Paper uniquement.** Aucun adaptateur d'exécution, aucune gestion de clés, aucun code
  de signature d'ordre. C'est une contrainte voulue, pas une fonctionnalité manquante.
- Le backtester suppose que vos ordres ne déplacent pas le marché pour les autres, qu'il
  n'y a pas de panne, et que tout ordre est rempli. Ces hypothèses cassent à la taille —
  `capacity_curve` est l'outil pour savoir où.
- Les fills utilisent l'ouverture de la barre suivante. Sur des barres horaires c'est
  conservateur ; en haute fréquence il faudrait des données tick, que l'archive fournit
  (`agg_trades`) mais que le moteur ne consomme pas encore.
- Le funding est appliqué depuis la série réalisée quand elle est fournie ; sinon il
  vaut zéro, ce qui **flatte** les positions longues sur perps.
- Les résultats ci-dessus sont un point de départ, pas une stratégie. Ils disent
  « ceci ne marche pas », ce qui est utile et n'est pas la même chose que « voici ce qui
  marche ».
