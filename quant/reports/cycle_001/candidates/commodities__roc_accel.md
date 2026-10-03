# roc_accel — commodities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un momentum positif qui accélère prédit un rendement positif.

*Pourquoi cela pourrait marcher :* Momentum + accélération.
## 2. Stratégie retail
Famille **momentum**. Signal : ROC(n) et sa variation sur m jours. Condition : même signe. Horizon : quotidien. Cible mesurée : rendement net > 0. Risque : entrée au sommet de l'accélération.
## 3. Formulation mathématique
`long si ROC_n > 0 et ROC_n − ROC_n(t−m) > 0 ; short symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::roc_accel` — baseline `{'n': 20, 'm': 5}`, candidat retenu par le walk-forward `{'n': 60, 'm': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.19 | +0.35 |
| CAGR | 0.8% | 1.6% |
| volatilité | 4.7% | 4.9% |
| drawdown max | -11.7% | -10.2% |
| Sortino | +0.29 | +0.51 |
| Calmar | +0.07 | +0.16 |
| trades | 2445 | 1605 |
| taux de réussite | 43.0% | 44.2% |
| profit factor | 1.08 | 1.17 |
| espérance / trade | +0.8 bp | +1.7 bp |
| exposition | 95.2% | 93.8% |
| skew | +0.21 | +0.18 |
| kurtosis | 2.6 | 3.3 |
| CVaR 5 % | -0.7% | -0.7% |
| récupération max (jours) | 1907 | 804 |
| années | 13.9 | 13.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.24 |
| CAGR | 1.1% |
| volatilité | 4.9% |
| drawdown max | -10.6% |
| Sortino | +0.35 |
| Calmar | +0.10 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.17 |
| kurtosis | 3.2 |
| CVaR 5 % | -0.7% |
| récupération max (jours) | 1150 |
| années | 10.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.24 ; années positives 50.0% ; stabilité des paramètres 60.0% ; baseline sans sélection sur les mêmes années +0.00 ; ratio OOS/IS +0.27.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2010 | 2007-2009 | m=10,n=20 | +0.87 | -0.42 |
| 2011 | 2007-2010 | m=5,n=20 | +0.77 | -0.15 |
| 2012 | 2007-2011 | m=5,n=20 | +0.57 | +0.35 |
| 2013 | 2008-2012 | m=5,n=20 | +0.57 | -1.43 |
| 2014 | 2009-2013 | m=10,n=60 | -0.06 | +1.77 |
| 2015 | 2010-2014 | m=10,n=60 | +0.34 | +1.20 |
| 2016 | 2011-2015 | m=10,n=60 | +0.80 | +1.04 |
| 2017 | 2012-2016 | m=10,n=60 | +1.01 | -0.41 |
| 2018 | 2013-2017 | m=10,n=60 | +0.71 | +0.56 |
| 2019 | 2014-2018 | m=10,n=60 | +0.90 | -0.78 |

## 9. Robustesse
Score 85.0% sur 20 perturbations ; ratio voisins/optimum +1.08.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| n +5 % | paramètre | +0.31 | oui |
| n −5 % | paramètre | +0.34 | oui |
| m +5 % | paramètre | +0.40 | oui |
| m −5 % | paramètre | +0.38 | oui |
| n +10 % | paramètre | +0.20 | oui |
| n −10 % | paramètre | +0.31 | oui |
| m +10 % | paramètre | +0.40 | oui |
| m −10 % | paramètre | +0.38 | oui |
| n +20 % | paramètre | +0.15 | non |
| n −20 % | paramètre | +0.40 | oui |
| m +20 % | paramètre | +0.41 | oui |
| m −20 % | paramètre | +0.45 | oui |
| coûts × 1.25 | coûts | +0.30 | oui |
| coûts × 1.5 | coûts | +0.24 | oui |
| slippage + 2.0 bp | coûts | +0.25 | oui |
| entrée retardée d'1 barre | exécution | +0.26 | oui |
| sortie retardée d'1 barre | exécution | +0.44 | oui |
| signal bruité (5%) | signal | +0.39 | oui |
| sans les 5% meilleurs trades | dépendance | -0.80 | non |
| sans les 10% meilleurs trades | dépendance | -1.22 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -11.8%, 5e centile -20.4% ; CAGR médian 1.6% [-0.4% ; 3.7%] ; P(perte) 9.4%. P(drawdown au-delà de) : 10% → 69.8%, 20% → 5.8%, 25% → 1.0%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 11 trades, 95e centile 15 ; P(perte) 7.3%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.38. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.067 / 0.120 (meilleure : pairs).

## 12. Capacité
Edge net moyen +15.0 bp par trade. Moitié de l'edge perdue en impact vers 500,000 $, edge nul vers 5,000,000 $ (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 3.00 bp/côté (comm 0.5, demi-spread 1.5, slippage 1.0), portage 0.0% long / 2.0% short. Part des coûts dans le résultat brut : 27.6%. Sharpe avec coûts × 1,5 : +0.24.

## 14. Drawdown
Recherche : max -10.2%, moyen -3.4%, plus long passage sous l'eau 804 jours. Walk-forward OOS : max -10.6%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.21 (35.5% des jours) ; bull Sharpe +0.34 (53.0% des jours) ; sideways Sharpe -0.05 (11.6% des jours)
- **volatility** : high_vol Sharpe +0.42 (31.2% des jours) ; low_vol Sharpe +0.53 (30.4% des jours) ; normal_vol Sharpe -0.10 (38.3% des jours)
- **crisis** : no_crisis Sharpe +0.24 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.98 (32.3% des jours) ; neutral Sharpe -0.20 (37.2% des jours) ; trending Sharpe +0.06 (30.5% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 60.0% ; PBO 0.38 ; ratio OOS/IS +0.27.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 116 trades / an sur la classe ; exposition moyenne 93.8% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Accélérations finales des bulles.

Observées sur l'OOS : direction = sideways (Sharpe -0.05), volatility = normal_vol (Sharpe -0.10), character = neutral (Sharpe -0.20).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.24, robustness 0.85, oos_stability 0.50, drawdown 0.59, cost_sensitivity 0.68, parameter_stability 0.60, capacity 0.81, regime_diversity 0.70, statistical_confidence 0.00, composite 0.55
