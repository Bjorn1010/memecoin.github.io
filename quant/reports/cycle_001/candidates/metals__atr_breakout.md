# atr_breakout — metals
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
`qt/lab/strategies.py::atr_breakout` — baseline `{'k': 1.0, 'hold': 10}`, candidat retenu par le walk-forward `{'k': 1.5, 'hold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| GLD | 2004-11-18 | 21.87 | A | — |
| SLV | 2006-04-28 | 20.43 | A | — |
| PPLT | 2010-01-08 | 16.73 | A | — |
| CPER | 2011-11-15 | 14.88 | C | 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain); 6 séquences de ≥ 5 clôtures identiques |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.14 | +0.38 |
| CAGR | 0.8% | 1.8% |
| volatilité | 7.7% | 5.1% |
| drawdown max | -21.1% | -8.7% |
| Sortino | +0.18 | +0.34 |
| Calmar | +0.04 | +0.21 |
| trades | 1250 | 785 |
| taux de réussite | 40.7% | 49.4% |
| profit factor | 1.08 | 1.31 |
| espérance / trade | +1.7 bp | +4.4 bp |
| exposition | 97.6% | 56.7% |
| skew | -0.88 | -3.67 |
| kurtosis | 28.9 | 167.6 |
| CVaR 5 % | -1.1% | -0.7% |
| récupération max (jours) | 1768 | 1258 |
| années | 15.1 | 15.1 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.18 |
| CAGR | 0.8% |
| volatilité | 5.2% |
| drawdown max | -9.5% |
| Sortino | +0.17 |
| Calmar | +0.09 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -4.26 |
| kurtosis | 181.6 |
| CVaR 5 % | -0.7% |
| récupération max (jours) | 1968 |
| années | 12.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.18 ; années positives 50.0% ; stabilité des paramètres 75.0% ; baseline sans sélection sur les mêmes années +0.03 ; ratio OOS/IS +0.53.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2008 | 2005-2007 | hold=5,k=1.5 | +1.01 | +1.18 |
| 2009 | 2005-2008 | hold=5,k=1.5 | +1.05 | +1.85 |
| 2010 | 2005-2009 | hold=5,k=1.5 | +1.11 | -0.01 |
| 2011 | 2006-2010 | hold=5,k=1.5 | +0.87 | +0.95 |
| 2012 | 2007-2011 | hold=5,k=1.5 | +0.85 | -0.29 |
| 2013 | 2008-2012 | hold=5,k=1.5 | +0.67 | -0.82 |
| 2014 | 2009-2013 | hold=5,k=1.5 | +0.22 | -0.14 |
| 2015 | 2010-2014 | hold=10,k=1.0 | -0.05 | +0.30 |
| 2016 | 2011-2015 | hold=10,k=1.0 | +0.08 | +0.31 |
| 2017 | 2012-2016 | hold=5,k=1.5 | +0.02 | -0.32 |
| 2018 | 2013-2017 | hold=5,k=1.5 | +0.02 | -0.43 |
| 2019 | 2014-2018 | hold=5,k=2.0 | +0.09 | +0.56 |

## 9. Robustesse
Score 80.0% sur 20 perturbations ; ratio voisins/optimum +0.74.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| k +5 % | paramètre | +0.43 | oui |
| k −5 % | paramètre | +0.25 | oui |
| hold +5 % | paramètre | +0.33 | oui |
| hold −5 % | paramètre | +0.28 | oui |
| k +10 % | paramètre | +0.40 | oui |
| k −10 % | paramètre | +0.21 | oui |
| hold +10 % | paramètre | +0.33 | oui |
| hold −10 % | paramètre | +0.28 | oui |
| k +20 % | paramètre | +0.24 | oui |
| k −20 % | paramètre | +0.09 | non |
| hold +20 % | paramètre | +0.33 | oui |
| hold −20 % | paramètre | +0.28 | oui |
| coûts × 1.25 | coûts | +0.36 | oui |
| coûts × 1.5 | coûts | +0.34 | oui |
| slippage + 2.0 bp | coûts | +0.31 | oui |
| entrée retardée d'1 barre | exécution | +0.05 | non |
| sortie retardée d'1 barre | exécution | +0.30 | oui |
| signal bruité (5%) | signal | +0.35 | oui |
| sans les 5% meilleurs trades | dépendance | -0.28 | non |
| sans les 10% meilleurs trades | dépendance | -0.58 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -10.5%, 5e centile -17.9% ; CAGR médian 1.8% [0.2% ; 3.6%] ; P(perte) 4.0%. P(drawdown au-delà de) : 10% → 56.0%, 20% → 2.1%, 25% → 0.2%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 13 ; P(perte) 1.4%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.25. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.579 / 0.135 (meilleure : volume_spike).

## 12. Capacité
Edge net moyen +19.8 bp par trade. Moitié de l'edge perdue en impact vers 1,000,000 $, edge nul vers 5,000,000 $ (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 2.00 bp/côté (comm 0.5, demi-spread 1.0, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 13.3%. Sharpe avec coûts × 1,5 : +0.34.

## 14. Drawdown
Recherche : max -8.7%, moyen -3.0%, plus long passage sous l'eau 1258 jours. Walk-forward OOS : max -9.5%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +1.30 (29.0% des jours) ; bull Sharpe -0.33 (40.8% des jours) ; sideways Sharpe -0.10 (30.1% des jours)
- **volatility** : high_vol Sharpe +0.13 (30.7% des jours) ; low_vol Sharpe +0.61 (29.0% des jours) ; normal_vol Sharpe +0.03 (40.3% des jours)
- **crisis** : no_crisis Sharpe +0.18 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.39 (29.3% des jours) ; neutral Sharpe +0.69 (41.1% des jours) ; trending Sharpe -0.47 (29.6% des jours)

Dépendance détectée : direction:bear. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 75.0% ; PBO 0.25 ; ratio OOS/IS +0.53.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 52 trades / an sur la classe ; exposition moyenne 56.7% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Surréaction puis correction.

Observées sur l'OOS : direction = bull (Sharpe -0.33), direction = sideways (Sharpe -0.10), character = trending (Sharpe -0.47).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.18, robustness 0.80, oos_stability 0.50, drawdown 0.64, cost_sensitivity 0.89, parameter_stability 0.75, capacity 0.86, regime_diversity 0.70, statistical_confidence 0.00, composite 0.59
