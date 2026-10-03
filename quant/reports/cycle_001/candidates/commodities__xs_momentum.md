# xs_momentum — commodities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 84% au Monte Carlo (> 10%)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Dans une classe d'actifs, les instruments qui ont le plus monté sur L jours surperforment ceux qui ont le moins monté le mois suivant.

*Pourquoi cela pourrait marcher :* Momentum relatif (Jegadeesh-Titman, Asness-Moskowitz-Pedersen).
## 2. Stratégie retail
Famille **momentum**. Signal : rang du rendement sur L jours (en sautant les `skip` derniers). Condition : ≥ 3 instruments. Horizon : 21 jours. Cible mesurée : rendement net du long-short > 0. Risque : krachs de momentum, petite taille d'univers.
## 3. Formulation mathématique
`chaque 21 j : rang de C_{t−s}/C_{t−s−L} ; long tiers haut, short tiers bas, inverse-vol, 50 % par jambe`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::xs_momentum` — baseline `{'lookback': 126, 'skip': 0}`, candidat retenu par le walk-forward `{'lookback': 252, 'skip': 0}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| USO | 2006-04-10 | 20.48 | A | — |
| UNG | 2007-04-18 | 19.46 | A | — |
| DBA | 2007-01-05 | 19.74 | A | — |
| DBC | 2006-02-06 | 20.65 | A | — |
| DBB | 2007-01-05 | 19.74 | A | — |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.19 | +0.04 |
| CAGR | 1.4% | -0.1% |
| volatilité | 10.3% | 10.1% |
| drawdown max | -32.4% | -38.3% |
| Sortino | +0.27 | +0.05 |
| Calmar | +0.04 | -0.00 |
| trades | 71 | 58 |
| taux de réussite | 46.5% | 48.3% |
| profit factor | 1.20 | 1.36 |
| espérance / trade | +64.0 bp | +90.7 bp |
| exposition | 99.1% | 99.1% |
| skew | +0.09 | -0.54 |
| kurtosis | 3.7 | 5.0 |
| CVaR 5 % | -1.4% | -1.5% |
| récupération max (jours) | 1936 | 1937 |
| années | 13.9 | 13.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.04 |
| CAGR | -0.2% |
| volatilité | 10.5% |
| drawdown max | -33.1% |
| Sortino | +0.05 |
| Calmar | -0.01 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.04 |
| kurtosis | 1.5 |
| CVaR 5 % | -1.5% |
| récupération max (jours) | 1936 |
| années | 9.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.04 ; années positives 66.7% ; stabilité des paramètres 55.6% ; baseline sans sélection sur les mêmes années +0.05 ; ratio OOS/IS +0.10.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2011 | 2008-2010 | lookback=252,skip=21 | +0.71 | +1.49 |
| 2012 | 2008-2011 | lookback=252,skip=21 | +0.87 | +0.39 |
| 2013 | 2008-2012 | lookback=252,skip=21 | +0.78 | -2.08 |
| 2014 | 2009-2013 | lookback=252,skip=0 | +0.37 | +0.71 |
| 2015 | 2010-2014 | lookback=252,skip=0 | +0.29 | +0.51 |
| 2016 | 2011-2015 | lookback=252,skip=0 | +0.18 | -0.65 |
| 2017 | 2012-2016 | lookback=252,skip=0 | -0.16 | +1.36 |
| 2018 | 2013-2017 | lookback=252,skip=0 | +0.08 | -1.54 |
| 2019 | 2014-2018 | lookback=126,skip=0 | +0.22 | +0.14 |

## 9. Robustesse
Score 76.5% sur 17 perturbations ; ratio voisins/optimum +1.65.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.16 | oui |
| lookback −5 % | paramètre | +0.22 | oui |
| skip +5 % | paramètre | +0.06 | oui |
| lookback +10 % | paramètre | +0.07 | oui |
| lookback −10 % | paramètre | +0.34 | oui |
| skip +10 % | paramètre | +0.06 | oui |
| lookback +20 % | paramètre | +0.07 | oui |
| lookback −20 % | paramètre | -0.05 | non |
| skip +20 % | paramètre | +0.06 | oui |
| coûts × 1.25 | coûts | +0.03 | oui |
| coûts × 1.5 | coûts | +0.01 | non |
| slippage + 2.0 bp | coûts | +0.03 | oui |
| entrée retardée d'1 barre | exécution | +0.07 | oui |
| sortie retardée d'1 barre | exécution | +0.04 | oui |
| signal bruité (5%) | signal | +0.04 | oui |
| sans les 5% meilleurs trades | dépendance | -0.32 | non |
| sans les 10% meilleurs trades | dépendance | -0.43 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -35.9%, 5e centile -58.9% ; CAGR médian -0.3% [-4.9% ; 4.3%] ; P(perte) 53.7%. P(drawdown au-delà de) : 10% → 100.0%, 20% → 95.3%, 25% → 83.5%, 35% → 52.0%, 50% → 16.2%.

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.35. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.067 / 0.120 (meilleure : pairs).

## 12. Capacité
stratégie de portefeuille : capacité non estimée dans ce cycle

## 13. Coûts
Modèle : 3.00 bp/côté (comm 0.5, demi-spread 1.5, slippage 1.0), portage 0.0% long / 2.0% short. Part des coûts dans le résultat brut : 2.8%. Sharpe avec coûts × 1,5 : +0.01.

## 14. Drawdown
Recherche : max -38.3%, moyen -13.2%, plus long passage sous l'eau 1937 jours. Walk-forward OOS : max -33.1%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe -0.01 (40.3% des jours) ; bull Sharpe -0.11 (39.0% des jours) ; sideways Sharpe +0.41 (20.7% des jours)
- **volatility** : high_vol Sharpe -0.38 (24.4% des jours) ; low_vol Sharpe +0.51 (42.0% des jours) ; normal_vol Sharpe -0.24 (33.6% des jours)
- **crisis** : crisis Sharpe -0.16 (6.1% des jours) ; no_crisis Sharpe +0.05 (93.9% des jours)
- **character** : mean_reverting Sharpe +0.48 (29.0% des jours) ; neutral Sharpe -0.19 (40.3% des jours) ; trending Sharpe -0.06 (30.7% des jours)

Dépendance détectée : direction:sideways, volatility:low_vol, crisis:no_crisis, character:mean_reverting. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 55.6% ; PBO 0.35 ; ratio OOS/IS +0.10.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 4 trades / an sur la classe ; exposition moyenne 99.1% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Univers trop petit ; retournements de leadership.

Observées sur l'OOS : direction = bear (Sharpe -0.01), direction = bull (Sharpe -0.11), volatility = high_vol (Sharpe -0.38), volatility = normal_vol (Sharpe -0.24), character = neutral (Sharpe -0.19), character = trending (Sharpe -0.06).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 84% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.04, robustness 0.76, oos_stability 0.67, drawdown 0.00, cost_sensitivity 0.30, parameter_stability 0.56, capacity 0.50, regime_diversity 0.36, statistical_confidence 0.00, composite 0.35
