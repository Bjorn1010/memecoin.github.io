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

C'est la raison d'être des 75 tests : ils ne vérifient pas que le code s'exécute, ils
vérifient qu'il donne la **bonne réponse** dans les cas où elle est connue analytiquement.
