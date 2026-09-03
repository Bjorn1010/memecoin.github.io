# Carte des méthodes quantitatives

Ce document est une **carte**, pas un cours : chaque module du code porte son propre
raisonnement en docstring. Ici, on répond à trois questions par méthode — *quelle
question elle résout*, *où elle est implémentée*, et *quel piège elle cache*.

Les pièges ne sont pas théoriques. Chacun de ceux marqués **⚠ mesuré** a été rencontré
en construisant ce système, avec le chiffre observé.

---

## 1. Économétrie des séries temporelles — `qt/econometrics/`

### Stationnarité et mémoire (`stationarity.py`)

| Méthode | Question | Piège |
|---|---|---|
| ADF | Y a-t-il une racine unitaire ? | Faible puissance près de la racine unitaire |
| KPSS | La série est-elle stationnaire ? | Hypothèse nulle **inverse** de l'ADF |
| Variance ratio (Lo-MacKinlay) | Tendance ou retour à la moyenne ? | La version homoscédastique rejette la marche aléatoire à cause du seul clustering de volatilité |
| `find_min_ffd` | Combien différencier au minimum ? | Prendre d=1 (les rendements) sur-différencie presque toujours |

ADF et KPSS sont lancés **ensemble** parce qu'ils répondent à des questions différentes.
Les deux qui rejettent simultanément (cas fréquent) signale une série fractionnairement
intégrée — c'est là que `frac_diff` sert.

**Mesuré sur BTC horaire 2021-2024** : `d = 0,4` atteint la stationnarité en conservant
**95 % de corrélation** avec la série d'origine. Prendre les rendements aurait jeté cette
mémoire pour rien.

### Cointégration (`cointegration.py`)

**⚠ mesuré — le piège le plus coûteux de tout le build.** Appliquer les valeurs critiques
ADF standard aux résidus d'une régression cointégrante estimée est faux : la régression a
été ajustée pour minimiser exactement la variance que le test examine. Résultat mesuré
sur 20 paires de marches aléatoires **indépendantes** :

- avec les valeurs critiques ADF : **14 cointégrations fallacieuses sur 20** (70 %)
- avec les valeurs critiques Engle-Granger/MacKinnon : retour au taux nominal

Sur le vrai panel de 10 actifs, la correction fait passer le compte de **25 paires
cointégrées à 8**.

Deux autres corrections appliquées ici :
- les **deux orientations** de la régression sont testées, et la p-value est corrigée de
  Bonferroni pour ça (prendre le minimum de deux tests sans correction double le taux de
  faux positifs) ;
- `screen_pairs` corrige de Bonferroni sur les N(N−1)/2 paires testées.

### Volatilité conditionnelle (`garch.py`)

EWMA (RiskMetrics) → GARCH(1,1) → GJR-GARCH. La question : quelle volatilité pour
dimensionner la position demain ?

**Mesuré sur BTC horaire** : GARCH bat EWMA sur QLIKE (1,964 vs 2,052) et sur BIC
(60 312 vs 63 189). GJR n'apporte quasiment rien (γ = 0,005) — l'effet de levier est réel
en actions, marginal en crypto, et le fit le dit.

**⚠** Persistance mesurée à 0,997 : quasi-IGARCH. La variance de long terme
ω/(1−persistance) devient alors hypersensible à la 3ᵉ décimale et **n'est pas un chiffre
sur lequel trader**. Le code le signale (`long_run_reliable: False`). Le chemin de
volatilité conditionnelle et la prévision court-terme restent parfaitement utilisables.

**⚠** QLIKE plutôt que MSE. Le MSE sur variance est dominé par les quelques plus grandes
observations et classera premier un modèle faux partout sauf dans le calme.

### Filtre de Kalman (`kalman.py`)

Question : estimer un ratio de couverture **qui bouge**, sans choisir entre lent (fenêtre
longue, obsolète) et bruyant (fenêtre courte).

**Mesuré sur BTC/ETH** : le bêta de Kalman est **19,6× plus lisse** que l'OLS glissant,
en suivant la même relation. L'OLS glissant saute chaque fois qu'une vieille observation
sort de la fenêtre — un artefact de la fenêtre, pas du marché.

### Ornstein-Uhlenbeck (`ornstein_uhlenbeck.py`)

θ (vitesse), μ (juste valeur), σ (bruit) → demi-vie = ln(2)/θ, qui fixe la durée de
détention et donc la viabilité après coûts. `optimal_thresholds` **dérive** les seuils
d'entrée/sortie au lieu de les deviner à ±2σ.

**⚠** Un optimum au bord de la grille de recherche n'est pas un optimum. Le code renvoie
`viable: False` et **supprime les chiffres de rendement attendu** dans ce cas — les
laisser affichés (« +104 % annualisé » à côté de « non tradable ») invite exactement
l'erreur que le module doit empêcher.

### Ruptures structurelles (`breaks.py`)

SADF (bulles/explosivité), CUSUM des carrés (rupture de variance), test de Chow (rupture
à une date connue).

**⚠** Chow exige une date de rupture **connue à l'avance**. Tester toutes les dates et
garder la plus significative est l'erreur de tests multiples ; utiliser SADF ou CUSUM
quand la date est inconnue.

---

## 2. Construction de portefeuille — `qt/portfolio/`

### Estimation de covariance (`covariance.py`)

Markowitz n'échoue pas par la théorie mais par l'**input** : l'optimiseur maximise
l'erreur, en surpondérant précisément là où l'estimation est la plus fausse.

| Estimateur | Quand |
|---|---|
| Échantillon | Beaucoup d'observations, peu d'actifs |
| EWMA | Les corrélations bougent (elles bougent) |
| Ledoit-Wolf | Défaut raisonnable ; l'intensité de shrinkage est auto-calibrée |
| Débruitage RMT | Beaucoup d'actifs : ne garde que les valeurs propres hors bande de Marchenko-Pastur |

**Mesuré sur le panel de 10 crypto (35 021 barres)** : shrinkage Ledoit-Wolf = 0,002 —
quasi nul, parce que 35 000 observations pour 10 actifs suffisent largement. L'estimateur
s'adapte correctement. Marchenko-Pastur ne trouve **qu'une seule valeur propre sur 10**
distinguable du bruit.

### Optimiseurs (`optimisers.py`)

Classés par confiance accordée aux inputs — donc par gravité de l'échec :
équipondéré → volatilité inverse → risk parity → variance minimale → diversification
maximale → moyenne-variance → HRP.

**Mesuré** : la variance minimale met **93,6 % du capital sur un seul actif**. C'est le
mode d'échec documenté, pas un bug.

HRP n'inverse jamais la matrice de covariance — c'est précisément pourquoi il survit à un
panel où tout est corrélé à 0,9.

### Décomposition du risque (`risk.py`)

**Le chiffre le plus parlant de tout le système.** Un portefeuille équipondéré de 10
crypto a un **nombre effectif de paris de 1,02**. Dix positions, un pari.

Autres mesures : VaR (historique / paramétrique / Cornish-Fisher), CVaR, contributions au
risque, stress tests historiques.

**Mesuré** : CVaR = 1,55× la VaR paramétrique — la queue est nettement plus épaisse que
la normale. Stress test mai 2021 : −45,5 % avec un drawdown de −61,7 %.

**⚠** Le nombre effectif de paris est défini dans la base propre. Quand plusieurs valeurs
propres sont quasi égales, cette base est arbitraire et la mesure devient indéfinie. Cela
n'arrive pas sur des panels réels ; cela arrive sur des données synthétiques.

### Black-Litterman (`black_litterman.py`)

Résout le problème qui rend moyenne-variance inutilisable : on n'a pas un vecteur de
rendements attendus, on a **quelques opinions**. Part des rendements d'équilibre implicites
(optimisation inverse depuis le portefeuille de marché) et ne met à jour que ce sur quoi
on a une vue.

Propriété de sécurité vérifiée par test : **sans vue, le résultat est exactement le
portefeuille de marché**.

### Modèles factoriels (`factors.py`)

PCA, Fama-MacBeth, résidualisation.

**⚠** Fama-MacBeth est en deux passes pour une raison : regrouper tous les actifs et
toutes les périodes dans une seule régression traite les observations comme
indépendantes, alors qu'à chaque date elles partagent le choc de marché. Les
t-statistiques sortent plusieurs fois trop grandes. Erreurs standard de Newey-West
incluses.

---

## 3. Dérivés et volatilité — `qt/derivatives/`

### Black-Scholes (`black_scholes.py`)
Prix, grecques complètes, volatilité implicite par Brent (pas Newton : Newton échoue
exactement là où ça compte, loin de la monnaie, quand véga → 0).

**⚠** Un prix violant les bornes d'arbitrage renvoie `NaN`, jamais un chiffre inventé.
C'est constant avec des cotations périmées.

### Surface de volatilité (`vol_surface.py`)
SVI (sans arbitrage par construction, contrairement à un ajustement polynomial), structure
par terme, prime de risque de variance.

**⚠ mesuré** : le prix du swap de variance par réplication est **sensible à la troncature
des ailes**. Test d'identité intégré : sur un smile plat, le résultat doit égaler
exactement la volatilité plate — il le fait.

**⚠ mesuré** : Corwin-Schultz surestime le spread intraday d'un facteur ~20 (16 bps
estimés sur BTC horaire contre <1 bp réel). Assez pour déclarer morte une stratégie
rentable. Retiré des défauts du backtester.

### Volatilité stochastique et sauts (`stochastic_vol.py`)
Black-Scholes suppose une volatilité constante — donc suppose que le smile n'existe pas.

- **Heston** : ρ produit le skew, la vol-de-vol produit la courbure. Explique la *forme*
  à maturité longue.
- **Merton** : les sauts produisent le smile court terme qu'une diffusion pure ne peut
  pas atteindre.

Tests de correctitude : Heston → Black-Scholes **exactement** quand la vol-de-vol → 0 ;
ρ négatif → skew baissier, ρ positif → skew haussier ; calibration aller-retour à
RMSE 0,000000.

**Mesuré** : avec Merton, l'aile K=70 se soulève de **+42 points de vol à 7 jours** contre
**+2 à 90 jours**. C'est exactement le phénomène qu'une diffusion ne reproduit pas.

---

## 4. Exécution — `qt/execution/`

### Almgren-Chriss (`almgren_chriss.py`)
Arbitrage entre payer l'impact et porter le risque. Deux limites à retenir comme
vérification : aversion nulle → **TWAP** ; aversion infinie → liquidation immédiate.

**⚠ mesuré** : deux bugs numériques réels ici.
1. `sinh(κT)` **déborde** vers l'infini quand l'aversion est élevée, donnant inf/inf = NaN
   et un calendrier vide, silencieusement. Réécrit sous forme stable.
2. Mélanger les secondes et les pas rend l'échelle de λ dénuée de sens : κT était
   multiplié par 60, poussant tout calendrier vers la liquidation immédiate quelle que
   soit l'aversion. Tout est maintenant **par pas**.

Aussi : TWAP, VWAP, POV, et l'attribution de l'*implementation shortfall* (délai vs
exécution vs opportunité — battre le VWAP ne veut rien dire si le prix s'est enfui avant
de commencer).

### Market making (`market_making.py`)
Avellaneda-Stoikov : prix de réservation (penche contre l'inventaire) et spread optimal.
Présent comme **analyse**, pas comme stratégie live — un vrai market making exige des
mises à jour sub-milliseconde. Utile pour comprendre l'autre côté de chaque spread payé.

---

## 5. Arbitrage statistique — `qt/strategies/statarb.py`

Assemble toute la chaîne : screen cointégration corrigé → couverture Kalman → OU →
seuils dérivés des coûts → moniteur de rupture.

**Résultat mesuré sur le panel de 10 actifs, 1 461 barres journalières :**

- 45 paires testées, seuil Bonferroni α = 0,00111
- **8 paires cointégrées**
- **0 paire tradable** après analyse des coûts

Motifs de rejet : demi-vies de 41 à 89 jours (c'est un pari directionnel, pas du retour à
la moyenne), et aucun seuil d'entrée ne franchit le coût aller-retour de 12 bps.

Vérification en forçant quand même la paire la plus cointégrée (BNB/BTC, p ≈ 0, entrée à
2σ) : **Sharpe brut −0,03, Sharpe net −0,13**. La cointégration était réelle ; la
rentabilité, non. Le screen avait raison.

---


---

## 6. Dimensionnement des mises — `qt/sizing/`

### Les progressions (`progressions.py`)

Ces systèmes se discutent d'habitude au lieu de se calculer. C'est une erreur dans les
deux sens : la martingale n'est ni l'argent gratuit que vantent ses partisans, ni
l'impossibilité mathématique que dénoncent ses détracteurs. C'est une **transformation
calculable** d'une distribution de rendements, et la chose honnête est de l'implémenter
et de la mesurer.

| Progression | Après une PERTE | Après un GAIN | Caractère |
|---|---|---|---|
| Martingale | double | reset | beaucoup de petits gains, ruine rare |
| Anti-martingale (Paroli) | reset | double | beaucoup de petites pertes, gros gain rare |
| D'Alembert | +1 unité | −1 unité | martingale linéaire, même forme |
| Fibonacci | avance d'un rang | recule de deux | plus douce encore, même forme |
| **Fraction fixe** | **% constant du capital** | **% constant** | **aucun état de ruine** |
| Ratio fixe | croît avec le profit cumulé | idem | compromis de Jones |

**Ce que dit vraiment la mathématique, mesuré par Monte Carlo (1000 paris, 2000 chemins) :**

Pièce équilibrée, aucun edge :

| | Martingale | Fraction fixe |
|---|---|---|
| Taux de ruine | **79 %** | **0 %** |
| Médiane finale | **0** | 94 181 |
| Moyenne finale | 107 628 | 99 704 |
| % de comptes profitables | 20,8 % | 44,6 % |

La moyenne dépasse le capital de départ pendant que la médiane est à zéro. **C'est
exactement le mécanisme qui trompe** : agrégée sur beaucoup de comptes, la moyenne
paraît saine grâce à quelques survivants énormes ; le compte typique est liquidé.

Avec un edge **authentique** de 55 % :

| Progression | Taux de ruine |
|---|---|
| Plate | 0 % |
| Fraction fixe | 0 % |
| D'Alembert | 15,9 % |
| **Martingale** | **46,5 %** |

**La martingale tue encore 46 % des comptes avec un vrai edge gagnant.** L'edge ne
sauve pas — il déplace seulement la date. Et avec un edge négatif de 48 % (réaliste
après coûts), la martingale ruine 88,9 % des comptes et D'Alembert 96,2 %.

**Le tableau du capital requis** (`martingale_capital_table`) est de l'arithmétique, pas
une opinion : survivre à n pertes consécutives exige 2ⁿ−1 unités, avec une probabilité
de 2⁻ⁿ. Le capital croît géométriquement, la probabilité décroît au même rythme, et leur
produit — le coût espéré — ne diminue pas. Onze pertes d'affilée exigent 2 047 unités et
surviennent environ tous les 2 048 séquences, soit tous les **102 jours** à 20 trades
par jour.

### Ruine, Kelly et optimal f (`ruin.py`)

**⚠ mesuré** : à **plein Kelly** (10 % par pari sur un edge de 55 %), la probabilité de
subir un drawdown de 20 % est de **1,0 — la certitude**. À 2,5× Kelly, une stratégie
avec un edge réel finit à **3,5 % du capital initial** : le sur-pari transforme un edge
gagnant en ruine, parce qu'au-delà du pic de Kelly la croissance composée devient
négative.

Kelly fractionnel au quart conserve **44 % de la croissance** pour un quart de la mise.
C'est pourquoi c'est le choix standard.

**Sans edge, la ruine est certaine quelle que soit la taille des mises.** La taille
change le délai, pas l'issue. Aucune règle de dimensionnement ne crée d'edge — elle met
à l'échelle des résultats, elle n'en fabrique pas.

---

## 7. Changement de régime markovien — `qt/econometrics/regime_switching.py`

Les régimes par quantiles glissants (`features/regime.py`) sont rapides et causaux mais
ne donnent ni probabilité d'état, ni durée attendue, ni détection de transition avant
confirmation par le prix. Le modèle de Markov estime tout cela.

**Mesuré sur BTC horaire, 2 états :** calme à **27,3 % de vol annualisée** (persistance
12,8 barres) et turbulent à **103,6 %** (persistance 6,2 barres).

**3 états :** calme 15,8 %, normal 41,5 %, **crise 130,7 % avec moyenne négative**.

**⚠ deux pièges décisifs :**
1. **Probabilités filtrées, jamais lissées.** `smoothed_marginal_probabilities` est ce
   que statsmodels trace par défaut et utilise **tout l'échantillon à chaque point**.
   Un backtest piloté par là sera extraordinaire et sans valeur. Ce module n'expose que
   les probabilités filtrées.
2. **Réajuster sur fenêtres glissantes.** Un modèle ajusté une fois sur tout
   l'échantillon connaît l'histoire complète quand il étiquette 2021.

**⚠** Les états sortent dans un ordre arbitraire et peuvent permuter entre deux
réajustements. Les labels sont donc attribués **par propriété** (volatilité) et non par
indice, sinon conditionner sur « l'état 0 » signifie autre chose chaque semaine.

---

## 8. Backtest de portefeuille multi-actifs — `qt/backtest/portfolio_backtest.py`

Jusqu'ici les optimiseurs produisaient des poids que rien ne consommait. Toute la
différence entre optimiseurs se joue dans le **turnover**, et elle n'apparaît qu'une
fois les coûts payés.

**Mesuré sur 10 crypto, 2021-2024, rééquilibrage hebdomadaire, coûts réels :**

| Méthode | Sharpe | Turnover/an | Coûts/brut | Trades | Paris effectifs |
|---|---|---|---|---|---|
| max_diversification | **0,98** | 5,6× | 1,5 % | 190 | 1,38 |
| equal_weight | 0,78 | 5,3× | **0,7 %** | **88** | 1,07 |
| hrp | 0,62 | 6,0× | 1,4 % | 146 | 1,30 |
| inverse_vol | 0,57 | 5,0× | 1,2 % | 101 | 1,17 |
| risk_parity | 0,51 | 5,6× | 1,3 % | 103 | 1,16 |
| **min_variance** | **0,44** | 5,3× | **3,9 %** | **213** | 2,07 |

Deux résultats :

1. **L'équipondéré bat risk parity, inverse-vol, min-variance et HRP.** C'est le
   résultat de DeMiguel, Garlappi & Uppal, confirmé sur ces données.
2. **La variance minimale est la pire tout en payant 6× plus de coûts** (213 trades
   contre 88). Elle gagne sur le papier et perd une fois tradée — exactement le mode
   d'échec par churn documenté dans le module.

**⚠** La covariance est estimée sur fenêtre glissante uniquement. L'ajuster sur tout
l'échantillon — ce que fait presque toute comparaison publiée d'optimiseurs — rend la
variance minimale spectaculaire pour une raison évidente.

---

## 9. Profondeur d'historique — `qt/data/history.py`, `bitstamp.py`, `tradingview.py`

**TradingView ne publie aucune API de données historiques gratuite, et ne le peut pas** :
il licencie la majorité de ses données auprès des bourses sous des accords interdisant
la redistribution. Vérifié : recherche de symboles 403, endpoints de données 404, et le
seul endpoint ouvert (`scanner`) renvoie des instantanés de screener sans historique.

Ce qui est légitime et implémenté : import des CSV que vous exportez depuis vos propres
graphiques, et lecture du screener en tant qu'instantané assumé.

Ce qui est **plus profond** que TradingView, et gratuit :

| Source | Profondeur mesurée |
|---|---|
| **Bitstamp** | **BTC quotidien depuis le 19/08/2011 — 15,0 ans, 5 495 barres** |
| Binance Vision | depuis août 2017, le premier mois d'existence de BTCUSDT |
| Coinbase | 2015+ |
| Stooq | décennies d'actions et d'indices |

`find_first_month` sonde l'archive **par bissection** pour trouver la vraie date de
listing de chaque symbole : ~7 requêtes au lieu de ~100. Dates trouvées : BTCUSDT
2017-08, DOGEUSDT 2019-07, SOLUSDT 2020-08, AVAXUSDT 2020-09.

**⚠** Le défaut « télécharger depuis 2021 » est un choix méthodologique silencieux et
mauvais : un modèle validé sur 2021-2024 n'a vu **qu'une seule transition de régime**.
`coverage_report` affiche une colonne `years` et les cycles couverts, à lire avant de
faire confiance à un Sharpe.

---

## 10. Résilience du flux — `qt/live/health.py`

Ce qui met fin aux sessions de paper trading n'est pas un mauvais signal, c'est un
WebSocket tombé à 3h du matin et un processus qui reste neuf heures avec une position
en croyant au dernier prix vu.

- Reconnexion à backoff exponentiel **avec jitter** — sans jitter, tous les clients se
  reconnectent au même instant après un redémarrage de la venue et se font tous refuser.
- **Détection de silence** : une connexion ouverte mais muette est plus dangereuse
  qu'une connexion fermée, parce que rien ne lève d'exception.
- **Contrôle croisé entre venues** : un prix qui diverge de plus de la tolérance d'une
  venue indépendante est presque toujours un mauvais print, pas un arbitrage.

Principe : **un système en mauvaise santé ne prend aucun risque nouveau.** Mais il ne
liquide pas non plus — solder sur des prix périmés est une autre façon de perdre.


## Le fil conducteur

Chaque piège listé ci-dessus produit un résultat **plus flatteur** que la vérité. Aucun ne
lève d'exception ; tous produisent des chiffres confiants et faux :

| Erreur | Effet mesuré |
|---|---|
| Valeurs critiques ADF sur résidus cointégrants | 70 % de faux positifs |
| Minimum de deux orientations sans correction | Taux de faux positifs doublé |
| Corwin-Schultz sur barres intraday | Spread surestimé ×20 |
| `astype("int64") // 10**6` sur index non-nanoseconde | Timestamps ÷1000, Sharpe de 581 |
| Optimum au bord de grille présenté comme résultat | « +104 % annualisé » sur une paire non tradable |
| Secondes mélangées aux pas dans Almgren-Chriss | λ sans effet, liquidation toujours immédiate |
| Pondération IC sur échantillon complet | Poids de janvier connaissant décembre suivant |
| Valeurs critiques ADF au lieu d'Engle-Granger | 14 faux positifs sur 20 |
| Probabilités de régime lissées au lieu de filtrées | Le modèle voit tout l'échantillon à chaque point |
| Covariance ajustée sur tout l'échantillon | Min-variance devient spectaculaire |
| `pd.Timestamp(x, tz="UTC")` sur un objet déjà tz-aware | Exception seulement quand l'argument optionnel est omis |
| Martingale jugée sur la moyenne | Moyenne à 107 628, médiane à 0 |
| `DataFrame * Series` au lieu de `.mul(series, axis=0)` | Alignement sur les **colonnes** : symboles contre timestamps, recouvrement vide. Les 5 colonnes de rendement résiduel deviennent NaN, `residual[symbole]` répond quand même (union), l'alpha `xs_reversal` renvoie zéro à chaque barre |
| `macro=`/`funding=` jamais renseignés par un appelant | 5 alphas sur 15 calculés sur du vide. Aucune erreur, le rapport en liste toujours 15 |
| Source qui traite une réponse illisible comme « pas de données » | Stooq a ajouté une vérification anti-bot JavaScript ; l'ingestion a renvoyé 0 ligne avec un code de sortie 0 |
| `np.log()` sur une série qui peut être négative | Pente 10a-2a négative sur 551 jours d'inversion, WTI à −37 $ : NaN silencieux sur toute la série |
| Unités datetime différentes de part et d'autre d'un `merge_asof` | `MergeError` — le seul de la table qui lève. Il n'apparaissait que sur les barres ré-échantillonnées |
| `normalise()` supprimait les colonnes hors schéma | `adj_close` perdu à l'écriture **et** à la lecture. La série ajustée redevenait la série brute : tous les dividendes effacés, sans erreur |
| Backtest actions sur le close brut | Les dividendes ne sont jamais encaissés. HYG perd 6,33 %/an, LQD 4,35 %, TLT 3,50 %. **Le classement des allocateurs s'inverse** |
| Commentaire décrivant un comportement jamais implémenté | « disable that scaling » — la mise à l'échelle n'était pas désactivée. Chaque allocateur devenait un hybride avec inverse-vol ; exposition brute à 1,0 mais vol réalisée à 3,4 % pour une cible de 10 % |

| Boucle autonome sans valorisation du livre | L'équité reste au montant de départ **pour toujours**. La courbe est plate, le drawdown à zéro, le disjoncteur ne peut jamais se déclencher. Le système tourne, enregistre, rapporte — et annonce « aucune perte » quoi que fasse le marché |
| `sr_variance` par défaut à zéro dans le Sharpe déflaté | Le benchmark vaut 0, la déflation ne déflate rien, et le verdict annonce quand même « significatif après déflation » |
| Plafonds appliqués **avant** la mise à l'échelle par volatilité | Le multiplicateur repousse la position au-delà de son propre plafond. Premier cycle live : 25,63 % sur un ETF pour une limite de 25 % |
| Scalaire de levier recalculé chaque barre | Pompe à rotation : 7,1× → 26,7× par an, 9,5 % du brut parti en exécution, pour un contrôle du risque identique |
| `warnings.filterwarnings("ignore", RuntimeWarning)` global | Masque toutes les divisions par zéro et valeurs invalides de numpy sur l'ensemble du système. C'est exactement ainsi que le `log()` d'un spread négatif est passé inaperçu |

## Day trading : l'arithmétique décide avant le signal

Un aller-retour sur Binance spot au tarif retail coûte **12 bps** — 5 bps taker de chaque
côté plus environ un point de demi-spread. Ce chiffre ne baisse pas quand on trade plus
souvent, donc le coût annuel d'une fréquence est fixé avant d'écrire le moindre signal :

| Fréquence | Trades/an | Coût annuel |
|---|---|---|
| 1 tous les 2 jours | 182 | 21,9 % |
| 1 par jour | 365 | **43,8 %** |
| 3 par jour | 1 095 | **131,4 %** |
| 10 par jour | 3 650 | 438,0 % |

Face à ça, le BTC horaire a un écart-type de 68 bps et un mouvement absolu médian de
25 bps. Le coût vaut **0,18 écart-type horaire**, soit la moitié du mouvement typique.
Exigeant mais pas absurde — c'est pourquoi le crypto est un des rares marchés où
l'intraday retail n'est pas mort d'avance ; en actions le spread représente une part bien
plus grande de l'amplitude intraday.

Conséquence : **la fréquence est une limite de risque, pas une préférence.**

### Ce que la stratégie a mesuré

Trois jambes courtes (reversal, breakout, order flow), 24 configurations classées sur
2021-2022 uniquement, la meilleure portée telle quelle sur 2023-2024.

| Jambe | IC de rang (BTC / ETH / SOL) |
|---|---|
| reversal | +0,024 / +0,012 / +0,017 |
| breakout | **−0,041 / −0,019 / −0,016** |
| flow | −0,029 / +0,001 / −0,007 |

Le breakout est **anti-prédictif sur les trois** et tirait la combinaison vers le bas.
Plus subtil : le reversal a un IC positif mais un edge conditionnel **négatif dans la
queue**, là où la stratégie entre effectivement. Les petites dislocations reviennent ;
les grandes portent de l'information et continuent. La stratégie entrait précisément là
où l'effet qu'elle exploite s'inverse.

**Aucune des 24 configurations n'a un Sharpe positif, même en échantillon.** La meilleure
fait −0,744 là où elle a été choisie, −0,141 hors échantillon, DSR **0,000015**.

### Le test qui tranche

| Coûts appliqués | Sharpe hors échantillon | Brut | Trades |
|---|---|---|---|
| taker/taker (12 bps, réel) | −0,141 | +0,98 % | 34 |
| maker/maker (4 bps, ordres limite) | +0,043 | +0,98 % | 34 |
| **gratuit (0 bps, impossible)** | **−1,876** | **−36,1 %** | 515 |

Même avec une exécution parfaite et gratuite, la stratégie perd. **Le problème n'est pas
les coûts, c'est qu'il n'y a pas de signal.** Et la ligne à 0 bps enseigne autre chose :
sans pénalité de coût, la recherche sélectionne la configuration la plus sur-ajustée —
515 trades au lieu de 34 — qui s'effondre ensuite hors échantillon.

| Erreur qu'un moteur intraday cassé commet | Ce qu'elle rapporte gratuitement |
|---|---|
| Exécuter à la clôture qui a produit le signal | Un mouvement entier par trade |
| Résoudre une barre ambiguë en sa faveur | Transforme chaque stop en cible |
| Laisser courir au-delà du stop temporel | Un day trade devient une position, et le profil de risque mesuré n'est pas celui exécuté |

Les trois sont testés dans `tests/test_intraday.py`, parce que chacun vaut plus que
n'importe quel signal.

## Un signal passé à la place d'un autre

`combine_trend_and_allocator(trend, allocation, blend)` calcule
`(1−b)·alloc + b·|alloc|·trend`. Le terme `trend` doit être le **signal** borné dans
[−1, 1]. Tous les appelants lui passaient les **poids**.

Les deux sont des DataFrames de même forme et même index, donc l'échange ne lève rien et
produit un livre plausible. Mais l'amplitude typique diffère d'un facteur 17 :

| | Amplitude médiane |
|---|---|
| `trend_score` (le signal) | 0,53 |
| `trend_weights` (les poids) | 0,031 |

Le terme de timing sortait donc **17 fois trop petit**. Le livre « rp+trend 70 % » était
en réalité `0,3 × risk parity` plus une erreur d'arrondi, puis remis à l'échelle par la
cible de volatilité — un allocateur statique portant une étiquette de tendance.

Symptôme visible : un poids de +0,11 sur TLT alors que son signal de tendance valait
−0,53.

**Classement avant et après correction :**

| Configuration | Sharpe buggé | Sharpe réel | Rotation | Coûts |
|---|---|---|---|---|
| rp+trend 30 % | 0,897 | **0,972** | 5,4× | 1,2 % |
| rp+trend 50 % | 0,964 | 0,904 | 10,8× | 3,1 % |
| risk parity seul | 0,793 | 0,792 | 3,5× | 0,8 % |
| **rp+trend 70 %** | **1,100** | **0,784** | **17,3×** | **5,8 %** |

Plus de tendance est **pire**, et la colonne rotation dit pourquoi : le signal churne, et
au-delà d'un tiers du livre le churn coûte plus que le timing ne rapporte. Le réglage par
défaut du bot était 0,7 ; il est passé à 0,3.

`combine_trend_and_allocator` refuse désormais une entrée dont l'amplitude médiane est
sous 0,05, avec un message qui nomme la confusion.

## Une construction qui ne peut pas vendre à découvert

`(1−b)·w + b·|w|·s` ne change de signe que si `s < −(1−b)/b`. Or `s` sort d'un tanh et
est borné à −1.

| Mélange | Bascule short à |
|---|---|
| 30 % | s < −2,33 → **impossible** |
| 50 % | s < −1,00 → limite exacte |
| 70 % | s < −0,43 |

**En dessous de 50 % de tendance, le livre ne peut jamais être short** : le timing module
la taille, jamais la direction. Ce n'est pas un défaut — le meilleur mélange mesuré est
30 %, où le livre est du risk parity modulé entre 0,7× et 1,3× — mais c'est invisible
depuis les poids seuls. `sign_flip_threshold()` le calcule et la commande `qt signal`
l'affiche.

## Le chemin live contre le backtest

Deux implémentations de la même idée dérivent toujours, et la dérive se découvre en
production des mois plus tard. `scripts/replay_live.py` rejoue l'orchestrateur cycle par
cycle sur l'historique — 716 cycles, 2012-2026 — en ne lui montrant que le passé à chaque
pas, puis compare à un backtest de la même fenêtre.

Il a immédiatement trouvé un biais :

| | CAGR | Drawdown max |
|---|---|---|
| Replay live, avant correction | **4,38 %** | −10,8 % |
| Backtest | 3,38 % | −8,1 % |
| Replay live, après correction | 3,67 % | −10,6 % |

Le cycle se créditait du rendement **depuis la clôture sur laquelle il avait décidé**.
Un ordre passé après cette clôture s'exécute à la séance suivante. Un point entier de
CAGR d'avantage temporel qu'aucun ordre n'aurait pu capturer — et le backtest utilisait
déjà `execution_lag_bars=1` depuis toujours, donc c'est bien le chemin live qui était
faux.

L'écart résiduel de 0,30 point est la différence de modèle de coûts : le chemin live
facture un spread forfaitaire sur la rotation, le moteur modélise spread et impact par
exécution. Le seuil du script est fixé à 1 point pour détecter tout retour du biais.

| Erreur | Effet mesuré |
|---|---|
| Valorisation depuis la barre de décision | +1,01 pt de CAGR de pure avance temporelle. Invisible sans rejouer le chemin live contre le backtest |

## Les quatre styles quant : ce qui marche et ce qui ne marche pas

Livre de 15 ETF, 2007-2026, chaque configuration ramenée à 10 % de volatilité et
facturée aux mêmes coûts.

| Style | Sharpe |
|---|---|
| **trend seul** | **0,52** |
| defensive seul | −0,01 |
| carry seul | −0,15 |
| value seul | −0,53 |
| les quatre, neutre au marché | 0,15 |
| les quatre, directionnel | −0,09 — **DSR 0,0004** |

**Seule la tendance a du contenu ici.** Combiner les quatre à poids égaux détruit environ
0,6 de Sharpe, et le Sharpe déflaté de la combinaison est 0,0004 : rejeté catégoriquement.

La cause est la **donnée**, pas la théorie :

- Le **carry** réel est la pente de la courbe de futures ou un différentiel de taux.
  Estimé ici par un rendement de dividende glissant, il est rétrospectif et quasi
  immobile : il dégénère en « toujours surpondérer HYG et LQD », un biais statique
  déguisé en signal.
- La **value** réelle a une ancre fondamentale : rendement bénéficiaire, taux réel,
  valeur comptable. Un ETF n'en a pas, donc j'utilise un retour à la moyenne sur 5 ans —
  sans fondement théorique solide entre classes d'actifs, et sans contenu empirique ici.
- Le **defensive** sur 15 instruments hétérogènes se réduit à « détenir des obligations ».

Les trois exigent soit un univers de nombreux instruments comparables **au sein** d'une
classe d'actifs, soit des données fondamentales. Ni l'un ni l'autre n'est gratuit. C'est
la contrainte structurelle de tout ce projet, énoncée plutôt que contournée.

Le module reste implémenté et testé — ce sont des méthodes correctes — mais la
configuration par défaut ne fait tourner que la tendance, parce que livrer les quatre par
défaut reviendrait à livrer une configuration mesurée perdante.

| Erreur trouvée en chemin | Effet mesuré |
|---|---|
| Normaliser les poids par l'exposition brute | Le livre est **toujours** investi à 1,5, quelle que soit la force du signal. Détruit la propriété la plus précieuse d'un signal — être petit quand il n'a pas d'avis. Coût : **0,6 de Sharpe** (trend passe de −0,22 à 0,52 une fois corrigé) |
| Un style sans données renvoyant zéro | Zéro est un « aucun avis » confiant : il dilue d'un quart les styles qui ont des données, et le rapport en liste toujours quatre |

## Le rééquilibrage : le plus gros levier de coût

Même signal, même livre, seule la fréquence change.

| Fréquence | Rotation annuelle | Part des coûts | Sharpe |
|---|---|---|---|
| Quotidienne | 26,7× | **9,97 %** | 0,658 |
| Hebdomadaire | 15,5× | 5,55 % | 0,699 |
| Mensuelle | 9,2× | **2,89 %** | 0,700 |

Le signal évolue sur des horizons de 32 à 256 jours. Rééquilibrer quotidiennement, c'est
payer pour ré-exprimer la même opinion. Ralentir divise les coûts par 3,5 et améliore le
Sharpe — ce n'est pas un compromis, c'est une correction.

## Actions et ETF : ce que le dividende change vraiment

Même livre, même période (2010-2026), même moteur. Seule différence : les dividendes
sont crédités ou non.

| Allocateur | Sharpe rendement total | Sharpe prix seul | Apport du dividende (CAGR) |
|---|---|---|---|
| risk_parity | **1,06** | 0,56 | +1,64 pt |
| inverse_vol | 1,00 | 0,56 | +2,03 pt |
| max_diversification | 0,96 | **0,57** | +1,76 pt |
| hrp | 0,92 | 0,32 | +1,98 pt |
| min_variance | 0,88 | 0,32 | +2,13 pt |
| equal_weight | 0,78 | 0,55 | +1,59 pt |

Le dividende ne décale pas les niveaux, il **change le gagnant**. Sur le prix seul on
choisirait `max_diversification` ; sur le rendement réel c'est `risk_parity`. Et `hrp`
passe de dernier ex æquo à quatrième.

## Pourquoi l'équipondération gagne en crypto et perd en multi-actifs

| Livre | Paris effectifs | Facteurs > borne MP | Corrélation moyenne | Meilleur allocateur |
|---|---|---|---|---|
| 10 cryptos | 1,02 / 10 | 1 / 10 | 0,612 | equal_weight (0,78) |
| 15 ETF multi-actifs | 1,35 / 15 | 4 / 15 | 0,227 | risk_parity (1,06), equal_weight **dernier** |

C'est le résultat de DeMiguel lu correctement. L'équipondération bat les optimiseurs
quand il n'y a **aucune structure à exploiter** : dix cryptos sont un seul pari portant
dix tickers, donc estimer une matrice de covariance ne fait qu'ajouter du bruit. Dès
qu'il existe quatre facteurs de risque réellement distincts, l'optimisation retrouve son
utilité et l'équipondération devient le pire choix — elle concentre le risque sur les
actions sans le savoir.

C'est aussi la justification du module portefeuille entier : sur le crypto seul, il
n'avait rien à faire.

C'est la raison d'être des 75 tests : ils ne vérifient pas que le code s'exécute, ils
vérifient qu'il donne la **bonne réponse** dans les cas où elle est connue analytiquement.

## Quand le bot annonce 70 %, est-ce que ça arrive ?

C'est la question qui décide si une probabilité vaut quoi que ce soit, et la première
réponse mesurée était mauvaise.

La régression isotonique a le droit de sortir 0,0 et 1,0, et elle le fait à partir d'une
poignée d'observations. Sur le Nasdaq, les compartiments produisant les probabilités
extrêmes contenaient **4, 10 et 16 observations** : le modèle annonçait **99,8 %** et le
marché montait **25 %** du temps. Ce n'est pas une propriété des marchés, c'est un
calibrateur qui prend le bruit au premier degré. Et comme la taille des positions suit la
confiance, l'erreur allait toujours dans le sens coûteux.

`shrink_to_evidence` ramène chaque probabilité vers le taux de base à hauteur de ce que
les données autorisent — moyenne a posteriori Beta-Binomiale, `p̂ = (k + s·b) / (n + s)`,
où `n` est le nombre d'observations de calibration dans le voisinage du score et `s` le
poids accordé au taux de base. Avec seize observations et `s = 50`, un compartiment sorti
à 100 % annonce environ 0,60 : c'est ce que seize observations autorisent à dire.

Mesuré sur QQQ, GLD et SPY, mêmes plis, seul le rétrécissement change
(`scripts/research_calibration.py`) :

| | Avant | Après |
|---|---|---|
| Pire écart annoncé / réalisé | **0,748** | **0,297** |
| Erreur de calibration moyenne | 0,01975 | **0,00414** |
| Amplitude de la probabilité | 0,319 | 0,104 |

Le compartiment qui annonçait 0,998 pour un réalisé de 0,250 a disparu ; il ne reste plus
aucune annonce au-dessus de 0,63.

**L'amplitude est le garde-fou de cette correction, et elle est publiée à côté du gain.**
Rétrécir améliore *mécaniquement* la calibration : à la limite, annoncer toujours 50 % est
parfaitement calibré et totalement inutile, puisqu'aucune position n'en sort. Une table qui
ne montrerait que l'erreur de calibration ferait passer la destruction du signal pour un
progrès. `resolution` et l'amplitude sont donc reportées dans le même tableau.

| Erreur trouvée en chemin | Effet mesuré |
|---|---|
| Compter les preuves dans l'espace des **probabilités** au lieu de celui des **scores** | L'isotonique fait passer de l'un à l'autre : les scores d'un modèle boosté se tassent dans 0,4–0,6 pendant que la sortie calibrée couvre 0–1. Le comptage tombait donc systématiquement dans le mauvais compartiment — en général un compartiment vide à côté d'un compartiment plein — et renvoyait un nombre plausible calculé au mauvais endroit |
| `n + s` au dénominateur avec `s = 0` et un compartiment vide | 0/0 → NaN. Toute comparaison en aval lit NaN comme faux, donc le bot lisait « ne pas trader » — la bonne action pour une raison entièrement fausse, sans la moindre erreur levée |

### Ce que ça ne corrige pas

Une probabilité honnête n'est pas une probabilité rentable. Après correction, sur données
horaires réelles :

| | Nasdaq 100 | Or |
|---|---|---|
| Amplitude (seuil 0,05) | 0,130 ✅ | 0,113 ✅ |
| Resolution (seuil 0,005) | **0,00024** ❌ | **0,00023** ❌ |
| Gain de Brier (seuil > 0) | **−0,00412** ❌ | **−0,00923** ❌ |

Le garde-fou bloque toujours, et il bloque sur la **resolution** — vingt fois sous le
seuil. Autrement dit : le bot annonce maintenant des chiffres auxquels on peut se fier, et
ces chiffres disent qu'il ne sait pas prédire la direction de la prochaine heure. C'est
un progrès réel et c'est un résultat négatif ; les deux sont vrais en même temps.

## Conditionner au régime de marché : mesuré, puis écarté

Le module de régimes markoviens existait depuis longtemps sans nourrir une seule
décision — exactement la situation où l'on suppose qu'un composant aide parce qu'il est
sophistiqué. Deux tests, tous deux négatifs.

**Sur le livre qui marche.** Le Sharpe du livre trend + risk parity par régime, sur
2010-2026, régimes estimés de façon causale sur le SPY et décalés d'une barre :

| Régimes | Régime le plus calme | Le plus agité | Écart |
|---|---|---|---|
| 2 états | 1,23 (76 % du temps) | 0,44 (24 %) | 0,78 |
| 3 états | 0,78 / 1,29 | 0,67 (9 %) | 0,62 |

L'écart existe, donc couper le mauvais régime devrait payer. En apparence, ça paie :
Sharpe 0,974 → **1,039**, drawdown −18,2 % → −13,0 %.

**C'est faux, et la façon dont c'est faux est instructive.** Le régime coupé a été choisi
en regardant le Sharpe de chaque régime sur tout l'échantillon, puis mesuré sur ce même
échantillon. En choisissant le régime sur 2010-2019 et en mesurant sur 2019-2026 :

| | Sharpe hors échantillon |
|---|---|
| Sans filtre | 0,881 |
| Filtre 2 états | **0,074** (−0,807) |
| Filtre 3 états | **0,559** (−0,321) |

Le filtre ne perd pas un peu, il détruit la stratégie. Et le régime désigné comme « le
pire » n'est même pas stable : la première moitié désigne le régime 0, l'échantillon
complet désigne le régime 2. Il n'y avait pas de mauvais régime à couper — seulement
trois tirages d'une statistique bruitée et la liberté de choisir le meilleur.

**Sur la prédiction horaire.** L'hypothèse restante était que la direction est prévisible
*à l'intérieur* d'un régime et que le mélange noie le signal. Sur QQQ, GLD et SPY, en
régime calme et en régime agité :

| Actif | Régime | Précision | Taux de base | Excès |
|---|---|---|---|---|
| QQQ | calme | 0,483 | 0,526 | −0,043 |
| QQQ | agité | 0,514 | 0,557 | −0,043 |
| GLD | calme | 0,499 | 0,549 | −0,050 |
| SPY | calme | 0,509 | 0,542 | −0,033 |

**0 résultat significatif sur 6**, pour 0,3 attendu par pur hasard. Tous les excès sont
négatifs. Le signal n'était pas noyé : il n'y en a pas.

Un modèle de régime ne crée pas de signal, il ne peut que redistribuer celui qui existe.
Le module reste implémenté et testé — ce sont des méthodes correctes — mais il ne pilote
aucune décision, parce que le brancher a été mesuré comme destructeur.

| Erreur trouvée en chemin | Effet mesuré |
|---|---|
| Choisir le régime à couper sur l'échantillon de mesure | +0,065 de Sharpe apparent, **−0,81 réel**. Trois régimes, c'est trois essais ; le meilleur de trois essais sur une statistique bruitée bat la référence à peu près une fois sur deux, sans qu'aucune affirmation fausse ne soit écrite |

## Le chemin vers la rentabilité, en chiffres

`scripts/chemin_rentabilite.py` fait l'arithmétique jusqu'au bout à partir de la seule
stratégie qui survit à une déflation honnête.

| | Mesuré |
|---|---|
| Rendement annuel | 6,63 % |
| Volatilité | 6,83 % |
| Sharpe | 0,971 |
| Pire perte | −18,2 % |
| Période | 16,5 ans, coûts inclus |

Sur 500 € : **33 € par an**, soit 2,76 € par mois, soit **0,0202 € par heure** de marché
ouvert. L'objectif de 20 €/heure demande **6 552 % par an** — il manque un facteur 989.

Les deux seuls leviers, chiffrés :

* **Capital.** Au rendement mesuré, 20 €/heure exige **494 357 €**. À 66 % par an — le
  record absolu, fonds fermé depuis 1993 — il en faudrait encore 49 636 €.
* **Risque.** Le levier nécessaire est x989, soit une volatilité de 6 749 %. Dès x10 la
  pire perte historique du livre dépasse −100 %, et il n'y a pas de seconde chance
  après. La probabilité de perdre la moitié du capital en un an, simulée au taux de
  réussite mesuré (52,6 % de jours positifs) : 1,4 % en risquant 2 % par jour, **56 %**
  à 5 %, **99 %** à 10 %.

Le multiplicateur caché a été cherché dans cinq directions — scalping, prédiction
horaire, day trading crypto, primes de style, régimes. Les cinq sont mesurées négatives
et documentées ci-dessus. Ce qui reste est un chemin réel mais lent : une stratégie
modeste et vérifiée, appliquée à du capital qui grandit.

## Étape 1 : le papier-trading, et ce qu'il a révélé sur 500 €

L'essai de trois mois demande deux choses que le code n'avait pas.

**Un état qui survit au conteneur.** L'orchestrateur enregistrait tout dans un SQLite
sous le lac de données — ignoré par git, et détruit avec la machine. Au premier
recyclage, l'essai serait reparti de sa valeur de départ : courbe plate, drawdown nul,
et un relevé ressemblant à un mois calme plutôt qu'à un mois perdu. `qt/live/journal.py`
tient une seconde copie en CSV versionné, une ligne par cycle, rejouée dans une base de
travail au début de chaque exécution. Le journal est le relevé ; la base est une copie
de travail, jamais l'inverse.

**Une vérification que le livre est achetable.** C'est le vrai résultat de cette étape.
Un backtest raisonne en poids ; un courtier vend des actions entières. Sur 100 000 € la
différence est un arrondi. Sur 500 €, mesuré sur le livre réel :

| Capital | Positions obtenues | Investi / voulu | Erreur de poids (entières) | (fractionnées) |
|---|---|---|---|---|
| **500 €** | **3 / 15** | **28 %** | **1,045** | 0,000 |
| 1 000 € | 7 / 15 | 54 % | 0,668 | 0,000 |
| 2 500 € | 10 / 15 | 73 % | 0,394 | 0,000 |
| 5 000 € | 12 / 15 | 83 % | 0,244 | 0,000 |
| 10 000 € | 14 / 15 | 92 % | 0,112 | 0,000 |
| 25 000 € | 15 / 15 | 95 % | 0,079 | 0,000 |

L'erreur de poids est la somme des écarts entre le livre voulu et le livre obtenu. À
1,045 sur 500 €, ce n'est plus la même stratégie — c'est un autre portefeuille portant le
même nom.

Et les lignes qui disparaissent ne sont pas les moins utiles : ce sont les **plus chères
à l'action**. Le S&P 500 à 765 $ disparaît, l'or à 403 $ disparaît, le dollar à 28 $
reste. Le livre survivant est celui des actions bon marché — un critère de sélection qui
n'apparaît nulle part dans la stratégie et que personne n'a choisi. Un moteur qui
travaille en poids n'a aucune raison de lever une erreur là-dessus.

**Conséquence** : avec 500 €, il faut un courtier proposant les actions fractionnées, et
la reproduction devient alors exacte (erreur 0,000). Chez un courtier classique il
faudrait environ 25 000 €.

| Erreur trouvée en chemin | Effet mesuré |
|---|---|
| Supposer qu'un livre de quinze poids est un livre de quinze positions | Sur 500 €, trois positions sur quinze et 28 % du capital investi. L'essai aurait mesuré correctement une stratégie que le compte ne peut pas tenir |
| Ignorer le taux de change sur des ETF cotés en dollars | Surestime le nombre d'actions achetables, toujours dans le sens flatteur. Le taux est maintenant un paramètre explicite |
| Annualiser un Sharpe sur deux semaines de papier | Un nombre sans information, et toujours celui qu'on cite. `performance` le retient jusqu'à 60 jours de rendements |

### Comment l'essai tourne tout seul

`scripts/daily_paper.sh` fait une journée complète sur une machine neuve : il crée
l'environnement s'il manque, rafraîchit les cours, exécute le cycle, puis commite et
pousse le journal. Une routine planifiée le déclenche à 23 h UTC du lundi au vendredi —
après la clôture américaine dans les deux fuseaux, heure d'été comme heure d'hiver.

Le lac de données est ignoré par git et disparaît avec le conteneur, mais ce n'est pas un
problème : `yahoo.daily()` demande la fenêtre maximale à chaque appel, donc l'historique
se reconstruit seul. La seule chose à conserver entre deux exécutions est le journal, et
c'est précisément pour ça qu'il est versionné.

Le script est idempotent — relancer le même jour remplace la ligne du jour — et il
commite même les cycles en échec, parce que ce sont eux qui expliquent un trou dans la
courbe.

## Le day trading, testé pour de bon

Un trou dans le travail précédent, et il était important. `research_prediction.py`
demandait « un modèle peut-il prédire la direction ? » — non, 49,96 %. Mais **aucun day
trader ne fait ça**. Le day trading classique ne prédit pas la direction : il parie que
ce qui vient de trop bouger revient. Hypothèse structurellement différente, jamais testée
ici jusqu'à maintenant.

### Cinq stratégies, quinze actifs, un seul jeu de paramètres

Barres de 5 minutes, aucune position à travers la clôture, entrée retardée d'une barre.

| Stratégie | Brut | Net (3 bp d'aller-retour) | Actifs positifs |
|---|---|---|---|
| **fade d'extrême (z)** | **+1,927 bp** | −1,073 bp | 4 / 15 |
| fade du gap | +0,995 bp | −2,005 bp | 4 / 14 |
| retour au VWAP | +0,134 bp | −2,866 bp | 0 / 15 |
| cassure d'ouverture | −0,107 bp | −3,107 bp | 0 / 15 |
| retournement de série | −0,322 bp | −3,322 bp | 0 / 15 |

Le résultat qui compte n'est pas « tout est négatif ». C'est que **l'avantage brut
existe** : le prix revient bien après un écart, +8,6 bp sur EEM, +7,5 sur SLV, +7,1 sur
QQQ. Ce qui n'existe pas, c'est ce qu'il en reste après la fourchette.

### Le fade d'extrême, poussé jusqu'au bout

Seul candidat sérieux, donc traité comme tel : coûts par actif (0,5 bp d'aller-retour sur
SPY, 8 bp sur DBC), trois ans d'horaire, paramètres choisis sur la première moitié et
mesurés sur la seconde.

| | Hors échantillon |
|---|---|
| Gain net moyen | **−4,12 bp** |
| Actifs positifs | 3 / 7 |
| t du livre équipondéré | **−0,87** |

Et la sensibilité aux coûts, parce que le verdict en dépend entièrement :

| Multiplicateur de fourchette | Gain net |
|---|---|
| x0,5 | −3,29 bp |
| x1,0 | −4,12 bp |
| x2,0 | −5,78 bp |

Même en divisant mes estimations de fourchette par deux, c'est négatif. Le verdict ne
repose donc pas sur mon estimation du coût.

### Le moteur en papier, et le piège qu'il a failli tendre

`qt/live/intraday_paper.py` fait tourner ce fade sur SPY et QQQ — les deux fourchettes
les plus serrées — avec stop, plafond de trades par séance, et sortie avant la clôture.
Sur 60 séances et 656 trades : **+2,291 bp net, t = 2,06, +15,03 €**.

C'est positif. C'est aussi le moment exact où il faut se méfier le plus, parce que c'est
le résultat que tout le monde espère.

| | Gain net moyen |
|---|---|
| Les 656 trades | +2,291 bp |
| Sans les **5** meilleurs | +1,180 bp |
| Sans les **10** meilleurs | +0,397 bp |
| **Trade médian** | **−0,861 bp** |

Dix trades sur six cent cinquante-six portent 83 % du résultat, et **le trade typique
perd**. Aucune des deux moitiés de l'échantillon n'est significative prise seule (t=1,77
et t=1,06). Une moyenne positive portée par une poignée de coups n'est pas un avantage,
c'est une loterie gagnée — et `summarise` publie désormais la médiane et l'ablation à
côté de la moyenne, plutôt que de les laisser à qui pense à les calculer.

| Erreur trouvée en chemin | Effet mesuré |
|---|---|
| N'avoir testé que la prédiction de direction | Concluait « pas de signal » alors que le retour à la moyenne a un avantage brut réel (+1,93 bp). La conclusion finale ne change pas ; le raisonnement qui y menait était faux |
| Un coût moyen de 3 bp pour tout le livre | Condamne SPY (0,5 bp réel) à tort et absout DBC (8 bp) à tort. C'est le paramètre qui décide, il ne peut pas être une constante |
| Publier la moyenne sans la médiane | +2,29 bp de moyenne contre −0,86 bp de médiane. La moyenne seule décrit comme gagnante une stratégie qui perd presque à chaque fois |

### Ce que ça donne face à l'objectif

Le relevé tourne tous les jours et s'écrit dans `journal/RAPPORT_DAY_TRADING.md`. Au
rythme mesuré : **+5,26 € par mois** sur 500 € de capital. L'objectif de 10 000 €/mois
demande un facteur **1 901**.

Et l'arithmétique du capital, qui ne dépend d'aucune stratégie :

| Rendement annuel | Référence | Capital requis pour 10 000 €/mois |
|---|---|---|
| 6,6 % | ce bot, mesuré | 1 818 182 € |
| 10 % | S&P 500 long terme | 1 200 000 € |
| 19,8 % | Buffett, 1965-2023 | 606 061 € |
| 66 % | Medallion, record absolu, fonds fermé | **181 818 €** |

Avec 500 € il faudrait **24 000 % par an**.

### Une heure plutôt que trente minutes — corrigé sur une remarque d'utilisateur

Le réglage de détention venait d'une grille automatique. Un utilisateur qui tient ses
positions Nasdaq une heure au maximum a signalé que ce n'était pas la bonne durée.
Vérifié sur QQQ, 60 séances, sans plafond de trades :

| Détention | Net moyen | t |
|---|---|---|
| 15 min | +1,25 bp | 0,98 |
| 30 min | +3,09 bp | 1,65 |
| **1 heure** | **+5,82 bp** | **2,34** |
| 2 heures | +3,50 bp | 1,04 |

Il avait raison, et l'explication est cohérente avec ce que la stratégie prétend faire :
le retour à la moyenne après un écart met plus de trente minutes à se produire, et
au-delà de deux heures c'est la dérive de la séance qui domine le retour.

**Deux réserves, écrites parce qu'elles vont dans le sens défavorable.**

Le changement n'améliore pas tout. Sur le livre effectivement livré — SPY et QQQ, six
trades par séance — passer à une heure fait *baisser* le t de 2,06 à 1,66 et le cumul de
15,03 € à 12,98 €. Le réglage est conservé parce que le raisonnement tient sur l'actif
visé, pas parce qu'il gagne partout.

Et il ne rend rien significatif. Seize configurations ont été balayées pour trouver ce
t de 2,34 ; le t médian du meilleur de seize tirages de **pur bruit** vaut 2,03. Corrigé
pour la recherche, **p = 0,28**.

L'ablation reste la même : sur 291 trades, retirer les dix meilleurs fait tomber le gain
de +5,82 bp à +0,78 bp, et le trade médian rapporte −0,11 bp.

| Erreur trouvée en chemin | Effet mesuré |
|---|---|
| Lire un t de 2,34 comme significatif après avoir balayé seize configurations | Le meilleur de seize tirages de bruit donne un t médian de 2,03. Le p honnête est 0,28, pas 0,02 |

## Le plan d'épargne : la bonne reformulation de "vivre du trading"

Chercher une stratégie qui transforme 500 € en un revenu de plusieurs milliers d'euros
par mois est chercher un rendement de plusieurs milliers de pour cent par an — mesuré
impossible, à plusieurs reprises, dans les sections précédentes. Investir de plus en
plus au fil du temps, jusqu'à ce que le revenu suive, est une question différente : ce
n'est plus une question de stratégie, c'est une question d'épargne et de temps.
`qt/live/growth.py` et `scripts/plan_croissance.py` chiffrent cette question sans
changer de stratégie — c'est toujours risk parity + 30 % de tendance, la seule mesurée
positive après une déflation honnête.

### Pourquoi une simulation, et pas une formule d'intérêts composés

Un calcul à 6,6 % constant efface les −18,2 % de pire perte que ce livre a réellement
traversés. Chaque trajectoire simulée est rééchantillonnée **par blocs de trois
semaines** depuis l'historique réel du livre plutôt que jour par jour : un
rééchantillonnage journalier détruirait l'autocorrélation d'une tendance et sous-
estimerait à la fois les creux et les séries gagnantes. Le résultat est une
**distribution**, pas un chiffre — la même stratégie, au même rythme de versement, met
33 ans dans un tirage favorable et 43 dans un tirage défavorable, et donner un seul
chiffre serait aussi trompeur que le calcul lisse qu'il remplace.

### Ce que ça donne, pour 6 000 €/mois

| | |
|---|---|
| Capital requis au rendement mesuré (6,63 %) | **1 086 499 €** |
| Au rendement du S&P 500 (10 %) | 720 000 € |
| Au rendement de Buffett (19,8 %, 1965-2023) | 363 636 € |
| Au record absolu (Medallion, 66 %, fonds fermé) | 109 091 € |

500 € seuls, réinvestis sans un euro ajouté, au rendement mesuré : **120 ans**. Ce n'est
pas un défaut de la stratégie, c'est l'arithmétique de partir petit — et c'est
exactement pourquoi verser est obligatoire, pas optionnel.

Avec des versements mensuels en plus de la stratégie, simulé sur 3 000 trajectoires,
plafonné à 45 ans :

| Versement/mois | Atteint dans le délai | Médiane | p10 – p90 | Pire perte en chemin (médiane) |
|---|---|---|---|---|
| 100 € | 0 % | > 45 ans | — | −19 % |
| 250 € | 24 % | 42,9 ans | 39,2 – 44,6 | −19 % |
| **500 €** | **88 %** | **38,3 ans** | 33,3 – 43,1 | −18 % |
| 1 000 € | 100 % | 29,6 ans | 25,4 – 34,5 | −18 % |
| 2 000 € | 100 % | 20,9 ans | 18,1 – 24,6 | −17 % |
| 3 000 € | 100 % | 16,6 ans | 14,5 – 19,4 | −16 % |

La colonne « pire perte en chemin, p10 » (jusqu'à −26 % aux versements faibles) dit ce
qu'il faut être prêt à tenir sans arrêter les versements ni vendre au pire moment —
arrêter là referait repartir le compteur à zéro.

Ce plan ne dépend d'aucune stratégie non mesurée dans ce dépôt. Il dépend de deux
choses vérifiables : que la stratégie continue de se comporter comme sur 2010-2026 —
ce que l'essai papier en cours vérifie en ce moment sur des données réelles — et que
les versements soient tenus. La seconde est entièrement sous le contrôle de
l'utilisateur ; la première ne l'est pas, et personne ne peut la garantir.
