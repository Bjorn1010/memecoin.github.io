# atr_breakout — commodities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Une variation quotidienne supérieure à k ATR annonce une continuation.

*Pourquoi cela pourrait marcher :* Arrivée d'information majeure, digérée lentement.
## 2. Stratégie retail
Famille **volatility**. Signal : |ΔC| > k × ATR(14) de la veille. Condition : aucune. Horizon : 5 à 20 jours. Cible mesurée : espérance nette > 0. Risque : chocs qui se retournent.
## 3. Formulation mathématique
`si |C_t − C_{t−1}| > k·ATR14_{t−1} : position dans le sens du mouvement h jours`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::atr_breakout` — baseline `{'k': 1.0, 'hold': 10}`, candidat retenu par le walk-forward `{'k': 2.0, 'hold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.01 | +0.55 |
| CAGR | -0.1% | 0.9% |
| volatilité | 5.3% | 1.6% |
| drawdown max | -19.0% | -3.3% |
| Sortino | +0.01 | +0.41 |
| Calmar | -0.00 | +0.27 |
| trades | 1609 | 203 |
| taux de réussite | 41.3% | 55.2% |
| profit factor | 1.03 | 1.77 |
| espérance / trade | +0.4 bp | +6.8 bp |
| exposition | 98.8% | 20.9% |
| skew | +0.09 | +1.48 |
| kurtosis | 2.0 | 34.8 |
| CVaR 5 % | -0.8% | -0.2% |
| récupération max (jours) | 3342 | 1361 |
| années | 13.9 | 13.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.51 |
| CAGR | 1.4% |
| volatilité | 2.9% |
| drawdown max | -5.5% |
| Sortino | +0.53 |
| Calmar | +0.26 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +1.13 |
| kurtosis | 15.6 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 1131 |
| années | 10.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.51 ; années positives 50.0% ; stabilité des paramètres 40.0% ; baseline sans sélection sur les mêmes années +0.20 ; ratio OOS/IS +0.79.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2010 | 2007-2009 | hold=5,k=2.0 | +0.71 | -0.08 |
| 2011 | 2007-2010 | hold=5,k=2.0 | +0.42 | -0.59 |
| 2012 | 2007-2011 | hold=5,k=2.0 | +0.13 | +1.01 |
| 2013 | 2008-2012 | hold=20,k=2.0 | +0.28 | -0.83 |
| 2014 | 2009-2013 | hold=20,k=1.0 | -0.07 | +1.50 |
| 2015 | 2010-2014 | hold=10,k=2.0 | +0.43 | -0.23 |
| 2016 | 2011-2015 | hold=10,k=2.0 | +0.54 | -0.24 |
| 2017 | 2012-2016 | hold=10,k=2.0 | +0.71 | +0.99 |
| 2018 | 2013-2017 | hold=10,k=2.0 | +0.57 | +1.50 |
| 2019 | 2014-2018 | hold=5,k=2.0 | +1.00 | +0.68 |

## 9. Robustesse
Score 80.0% sur 20 perturbations ; ratio voisins/optimum +0.77.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| k +5 % | paramètre | +0.40 | oui |
| k −5 % | paramètre | +0.41 | oui |
| hold +5 % | paramètre | +0.51 | oui |
| hold −5 % | paramètre | +0.44 | oui |
| k +10 % | paramètre | +0.36 | oui |
| k −10 % | paramètre | +0.23 | non |
| hold +10 % | paramètre | +0.51 | oui |
| hold −10 % | paramètre | +0.44 | oui |
| k +20 % | paramètre | +0.41 | oui |
| k −20 % | paramètre | +0.20 | non |
| hold +20 % | paramètre | +0.51 | oui |
| hold −20 % | paramètre | +0.44 | oui |
| coûts × 1.25 | coûts | +0.53 | oui |
| coûts × 1.5 | coûts | +0.51 | oui |
| slippage + 2.0 bp | coûts | +0.51 | oui |
| entrée retardée d'1 barre | exécution | +0.45 | oui |
| sortie retardée d'1 barre | exécution | +0.55 | oui |
| signal bruité (5%) | signal | +0.55 | oui |
| sans les 5% meilleurs trades | dépendance | +0.13 | non |
| sans les 10% meilleurs trades | dépendance | -0.08 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -3.1%, 5e centile -5.5% ; CAGR médian 0.9% [0.3% ; 1.6%] ; P(perte) 1.0%. P(drawdown au-delà de) : 10% → 0.1%, 20% → 0.0%, 25% → 0.0%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 9 ; P(perte) 0.2%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.15. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.067 / 0.120 (meilleure : pairs).

## 12. Capacité
Edge net moyen +52.4 bp par trade. Moitié de l'edge perdue en impact vers 10,000,000 $, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 3.00 bp/côté (comm 0.5, demi-spread 1.5, slippage 1.0), portage 0.0% long / 2.0% short. Part des coûts dans le résultat brut : 9.1%. Sharpe avec coûts × 1,5 : +0.51.

## 14. Drawdown
Recherche : max -3.3%, moyen -1.1%, plus long passage sous l'eau 1361 jours. Walk-forward OOS : max -5.5%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.93 (30.7% des jours) ; bull Sharpe +0.83 (52.5% des jours) ; sideways Sharpe -1.00 (16.8% des jours)
- **volatility** : high_vol Sharpe +0.89 (35.4% des jours) ; low_vol Sharpe -0.21 (32.8% des jours) ; normal_vol Sharpe +0.31 (31.8% des jours)
- **crisis** : no_crisis Sharpe +0.51 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.69 (31.5% des jours) ; neutral Sharpe +0.83 (35.1% des jours) ; trending Sharpe -0.03 (30.0% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 40.0% ; PBO 0.15 ; ratio OOS/IS +0.79.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 15 trades / an sur la classe ; exposition moyenne 20.9% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 3.05 | 0.3% | 2.7% | 1.0% | 96.0% | 47 |
| 10.0% | × 6.10 | 6.8% | 26.1% | 1.1% | 66.0% | 34 |
| 15.0% | × 9.15 | 5.9% | 43.7% | 5.1% | 45.3% | 33 |
| 20.0% | × 12.20 | 7.1% | 60.6% | 4.5% | 27.8% | 27 |
| 30.0% | × 18.30 | 10.3% | 73.7% | 2.0% | 14.0% | 18 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 3.05 | 12.5% | 0.0% | 0.8% | 86.7% | 173 |
| 10.0% | × 6.10 | 38.0% | 21.1% | 6.3% | 34.6% | 110 |
| 15.0% | × 9.15 | 45.8% | 34.8% | 6.5% | 12.9% | 82 |
| 20.0% | × 12.20 | 44.0% | 46.4% | 5.3% | 4.3% | 66 |
| 30.0% | × 18.30 | 25.5% | 67.4% | 6.9% | 0.2% | 41 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 3.05 | 32.2% | 0.0% | 27.2% | 40.6% | 126 |
| 10.0% | × 6.10 | 41.8% | 0.0% | 54.7% | 3.5% | 68 |
| 15.0% | × 9.15 | 40.5% | 0.0% | 59.1% | 0.4% | 39 |
| 20.0% | × 12.20 | 33.8% | 0.0% | 66.1% | 0.1% | 29 |
| 30.0% | × 18.30 | 24.4% | 0.0% | 75.6% | 0.0% | 24 |

## 19. Conditions d'échec
Attendues a priori : Surréaction puis correction.

Observées sur l'OOS : direction = sideways (Sharpe -1.00), volatility = low_vol (Sharpe -0.21), character = trending (Sharpe -0.03).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.51, robustness 0.80, oos_stability 0.50, drawdown 0.89, cost_sensitivity 0.92, parameter_stability 0.40, capacity 1.00, regime_diversity 0.70, statistical_confidence 0.00, composite 0.64
