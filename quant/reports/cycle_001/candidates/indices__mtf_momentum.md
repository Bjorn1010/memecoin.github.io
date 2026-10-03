# mtf_momentum — indices
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.58 (> 0.5)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un repli court dans une tendance longue est suivi d'une reprise de la tendance (tendance HTF + entrée LTF).

*Pourquoi cela pourrait marcher :* Combiner momentum lent et retour à la moyenne rapide.
## 2. Stratégie retail
Famille **multi_timeframe**. Signal : ROC(short) contre ROC(long). Condition : tendance longue établie. Horizon : 10 jours. Cible mesurée : espérance nette > 0. Risque : repli qui devient retournement.
## 3. Formulation mathématique
`long h jours si ROC_L > 0 et ROC_S < 0 (repli dans la tendance) ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::mtf_momentum` — baseline `{'long': 120, 'short': 5, 'hold': 10}`, candidat retenu par le walk-forward `{'long': 250, 'short': 10, 'hold': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| SPY | 1993-01-29 | 33.67 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| QQQ | 1999-03-10 | 27.56 | A | 1 trous de plus de 5 jours (max 7) |
| DIA | 1998-01-20 | 28.7 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| IWM | 2000-05-26 | 26.35 | A | 1 trous de plus de 5 jours (max 7) |
| EWG | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7); 1 séquences de ≥ 5 clôtures identiques |
| EWU | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7); 3 séquences de ≥ 5 clôtures identiques |
| EWJ | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7) |
| FEZ | 2002-10-21 | 23.95 | A | — |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.54 | +0.63 |
| CAGR | 3.9% | 4.3% |
| volatilité | 7.6% | 7.1% |
| drawdown max | -20.1% | -14.0% |
| Sortino | +0.68 | +0.75 |
| Calmar | +0.19 | +0.31 |
| trades | 1214 | 1212 |
| taux de réussite | 58.6% | 69.6% |
| profit factor | 1.80 | 2.01 |
| espérance / trade | +12.0 bp | +11.9 bp |
| exposition | 96.3% | 91.2% |
| skew | -0.41 | -0.44 |
| kurtosis | 6.4 | 8.6 |
| CVaR 5 % | -1.2% | -1.1% |
| récupération max (jours) | 1830 | 1102 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.41 |
| CAGR | 2.7% |
| volatilité | 7.0% |
| drawdown max | -18.6% |
| Sortino | +0.52 |
| Calmar | +0.14 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.41 |
| kurtosis | 7.6 |
| CVaR 5 % | -1.1% |
| récupération max (jours) | 2183 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.41 ; années positives 60.9% ; stabilité des paramètres 39.1% ; baseline sans sélection sur les mêmes années +0.46 ; ratio OOS/IS +0.50.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | hold=10,long=60,short=10 | +1.21 | +1.13 |
| 1998 | 1994-1997 | hold=10,long=250,short=5 | +1.20 | +0.79 |
| 1999 | 1994-1998 | hold=10,long=250,short=5 | +1.13 | +1.44 |
| 2000 | 1995-1999 | hold=10,long=250,short=5 | +1.77 | -1.39 |
| 2001 | 1996-2000 | hold=10,long=250,short=10 | +0.82 | +0.76 |
| 2002 | 1997-2001 | hold=10,long=250,short=10 | +0.77 | +1.43 |
| 2003 | 1998-2002 | hold=10,long=250,short=10 | +0.71 | +0.48 |
| 2004 | 1999-2003 | hold=10,long=120,short=10 | +0.83 | +0.65 |
| 2005 | 2000-2004 | hold=10,long=120,short=10 | +0.67 | -0.78 |
| 2006 | 2001-2005 | hold=10,long=250,short=10 | +0.79 | +1.34 |
| 2007 | 2002-2006 | hold=10,long=250,short=10 | +0.92 | +1.15 |
| 2008 | 2003-2007 | hold=10,long=250,short=10 | +0.89 | +1.46 |
| 2009 | 2004-2008 | hold=10,long=250,short=10 | +1.08 | -0.56 |
| 2010 | 2005-2009 | hold=10,long=250,short=10 | +0.85 | +0.07 |
| 2011 | 2006-2010 | hold=10,long=120,short=5 | +0.81 | -0.26 |
| 2012 | 2007-2011 | hold=10,long=120,short=5 | +0.52 | -0.98 |
| 2013 | 2008-2012 | hold=10,long=60,short=5 | +0.40 | +1.52 |
| 2014 | 2009-2013 | hold=10,long=60,short=5 | +0.44 | -0.51 |
| 2015 | 2010-2014 | hold=10,long=250,short=10 | +0.35 | -0.06 |
| 2016 | 2011-2015 | hold=10,long=60,short=10 | +0.43 | -0.56 |
| 2017 | 2012-2016 | hold=10,long=120,short=10 | +0.54 | +2.69 |
| 2018 | 2013-2017 | hold=10,long=120,short=10 | +1.22 | +0.48 |
| 2019 | 2014-2018 | hold=10,long=120,short=10 | +0.77 | -0.73 |

## 9. Robustesse
Score 92.3% sur 26 perturbations ; ratio voisins/optimum +0.98.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| long +5 % | paramètre | +0.56 | oui |
| long −5 % | paramètre | +0.58 | oui |
| short +5 % | paramètre | +0.54 | oui |
| short −5 % | paramètre | +0.63 | oui |
| hold +5 % | paramètre | +0.64 | oui |
| hold −5 % | paramètre | +0.63 | oui |
| long +10 % | paramètre | +0.59 | oui |
| long −10 % | paramètre | +0.59 | oui |
| short +10 % | paramètre | +0.54 | oui |
| short −10 % | paramètre | +0.63 | oui |
| hold +10 % | paramètre | +0.64 | oui |
| hold −10 % | paramètre | +0.63 | oui |
| long +20 % | paramètre | +0.55 | oui |
| long −20 % | paramètre | +0.60 | oui |
| short +20 % | paramètre | +0.45 | oui |
| short −20 % | paramètre | +0.66 | oui |
| hold +20 % | paramètre | +0.65 | oui |
| hold −20 % | paramètre | +0.62 | oui |
| coûts × 1.25 | coûts | +0.58 | oui |
| coûts × 1.5 | coûts | +0.54 | oui |
| slippage + 2.0 bp | coûts | +0.60 | oui |
| entrée retardée d'1 barre | exécution | +0.55 | oui |
| sortie retardée d'1 barre | exécution | +0.61 | oui |
| signal bruité (5%) | signal | +0.63 | oui |
| sans les 5% meilleurs trades | dépendance | +0.17 | non |
| sans les 10% meilleurs trades | dépendance | +0.01 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -16.3%, 5e centile -25.8% ; CAGR médian 4.3% [2.2% ; 6.4%] ; P(perte) 0.1%. P(drawdown au-delà de) : 10% → 98.2%, 20% → 22.7%, 25% → 6.3%, 35% → 0.4%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 8 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.58. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +101.0 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 2.3%. Sharpe avec coûts × 1,5 : +0.54.

## 14. Drawdown
Recherche : max -14.0%, moyen -4.1%, plus long passage sous l'eau 1102 jours. Walk-forward OOS : max -18.6%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.16 (22.5% des jours) ; bull Sharpe +0.38 (61.1% des jours) ; sideways Sharpe +0.91 (16.5% des jours)
- **volatility** : high_vol Sharpe +0.87 (31.7% des jours) ; low_vol Sharpe +0.29 (28.4% des jours) ; normal_vol Sharpe +0.01 (39.9% des jours)
- **crisis** : no_crisis Sharpe +0.41 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.69 (31.8% des jours) ; neutral Sharpe -0.10 (40.1% des jours) ; trending Sharpe +0.85 (28.1% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 39.1% ; PBO 0.58 ; ratio OOS/IS +0.50.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 45 trades / an sur la classe ; exposition moyenne 91.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Retournements de tendance longue.

Observées sur l'OOS : character = neutral (Sharpe -0.10).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.58 (> 0.5)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.41, robustness 0.92, oos_stability 0.61, drawdown 0.48, cost_sensitivity 0.86, parameter_stability 0.39, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.56
