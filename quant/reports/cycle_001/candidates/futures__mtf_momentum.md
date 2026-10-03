# mtf_momentum — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
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
`qt/lab/strategies.py::mtf_momentum` — baseline `{'long': 120, 'short': 5, 'hold': 10}`, candidat retenu par le walk-forward `{'long': 250, 'short': 3, 'hold': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| ES=F | 2000-09-18 | 26.04 | C | 73 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 10 barres OHLC incohérentes (réparées : high/low recalculés) |
| NQ=F | 2000-09-18 | 26.04 | C | 191 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 23 barres OHLC incohérentes (réparées : high/low recalculés) |
| YM=F | 2002-04-05 | 24.49 | C | 57 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 26 barres OHLC incohérentes (réparées : high/low recalculés) |
| RTY=F | 2017-07-10 | 9.23 | C | 40 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables) |
| ZN=F | 2000-09-21 | 26.03 | A | 20 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 12) |
| ZB=F | 2000-09-21 | 26.03 | A | 10 barres OHLC incohérentes (réparées : high/low recalculés) |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.46 | +0.53 |
| CAGR | 2.9% | 3.6% |
| volatilité | 6.7% | 7.1% |
| drawdown max | -17.7% | -12.0% |
| Sortino | +0.61 | +0.65 |
| Calmar | +0.16 | +0.30 |
| trades | 668 | 451 |
| taux de réussite | 59.7% | 58.8% |
| profit factor | 1.38 | 1.60 |
| espérance / trade | +8.8 bp | +14.9 bp |
| exposition | 97.1% | 94.8% |
| skew | -0.34 | -0.56 |
| kurtosis | 5.4 | 8.4 |
| CVaR 5 % | -1.0% | -1.1% |
| récupération max (jours) | 1804 | 793 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.44 |
| CAGR | 2.9% |
| volatilité | 7.2% |
| drawdown max | -15.2% |
| Sortino | +0.55 |
| Calmar | +0.19 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.53 |
| kurtosis | 9.4 |
| CVaR 5 % | -1.1% |
| récupération max (jours) | 1167 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.44 ; années positives 75.0% ; stabilité des paramètres 56.2% ; baseline sans sélection sur les mêmes années +0.49 ; ratio OOS/IS +0.64.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | hold=10,long=60,short=5 | +0.93 | +0.32 |
| 2005 | 2001-2004 | hold=10,long=60,short=5 | +0.79 | -2.44 |
| 2006 | 2001-2005 | hold=10,long=60,short=5 | +0.22 | +1.35 |
| 2007 | 2002-2006 | hold=10,long=250,short=5 | +0.49 | +0.35 |
| 2008 | 2003-2007 | hold=10,long=250,short=3 | +0.35 | +0.97 |
| 2009 | 2004-2008 | hold=10,long=250,short=3 | +0.61 | -0.45 |
| 2010 | 2005-2009 | hold=10,long=250,short=3 | +0.52 | +0.22 |
| 2011 | 2006-2010 | hold=10,long=250,short=3 | +0.48 | +0.54 |
| 2012 | 2007-2011 | hold=10,long=250,short=3 | +0.43 | +0.45 |
| 2013 | 2008-2012 | hold=10,long=250,short=3 | +0.43 | +3.05 |
| 2014 | 2009-2013 | hold=10,long=250,short=3 | +0.72 | +0.27 |
| 2015 | 2010-2014 | hold=10,long=250,short=3 | +0.81 | +0.73 |
| 2016 | 2011-2015 | hold=10,long=250,short=3 | +0.94 | -0.88 |
| 2017 | 2012-2016 | hold=10,long=120,short=10 | +1.04 | +2.52 |
| 2018 | 2013-2017 | hold=10,long=120,short=10 | +1.66 | -0.00 |
| 2019 | 2014-2018 | hold=10,long=120,short=10 | +0.96 | +0.34 |

## 9. Robustesse
Score 92.3% sur 26 perturbations ; ratio voisins/optimum +0.90.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| long +5 % | paramètre | +0.45 | oui |
| long −5 % | paramètre | +0.45 | oui |
| short +5 % | paramètre | +0.51 | oui |
| short −5 % | paramètre | +0.38 | oui |
| hold +5 % | paramètre | +0.53 | oui |
| hold −5 % | paramètre | +0.50 | oui |
| long +10 % | paramètre | +0.46 | oui |
| long −10 % | paramètre | +0.39 | oui |
| short +10 % | paramètre | +0.51 | oui |
| short −10 % | paramètre | +0.38 | oui |
| hold +10 % | paramètre | +0.53 | oui |
| hold −10 % | paramètre | +0.50 | oui |
| long +20 % | paramètre | +0.44 | oui |
| long −20 % | paramètre | +0.30 | oui |
| short +20 % | paramètre | +0.51 | oui |
| short −20 % | paramètre | +0.38 | oui |
| hold +20 % | paramètre | +0.53 | oui |
| hold −20 % | paramètre | +0.49 | oui |
| coûts × 1.25 | coûts | +0.52 | oui |
| coûts × 1.5 | coûts | +0.52 | oui |
| slippage + 2.0 bp | coûts | +0.50 | oui |
| entrée retardée d'1 barre | exécution | +0.45 | oui |
| sortie retardée d'1 barre | exécution | +0.50 | oui |
| signal bruité (5%) | signal | +0.45 | oui |
| sans les 5% meilleurs trades | dépendance | +0.10 | non |
| sans les 10% meilleurs trades | dépendance | -0.08 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -15.8%, 5e centile -25.8% ; CAGR médian 3.6% [1.1% ; 6.2%] ; P(perte) 0.9%. P(drawdown au-delà de) : 10% → 96.7%, 20% → 21.6%, 25% → 6.7%, 35% → 0.8%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 9 ; P(perte) 0.2%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.37. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +76.5 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 2.7%. Sharpe avec coûts × 1,5 : +0.52.

## 14. Drawdown
Recherche : max -12.0%, moyen -3.5%, plus long passage sous l'eau 793 jours. Walk-forward OOS : max -15.2%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.39 (16.1% des jours) ; bull Sharpe +0.15 (63.7% des jours) ; sideways Sharpe +1.29 (20.3% des jours)
- **volatility** : high_vol Sharpe +0.98 (30.3% des jours) ; low_vol Sharpe +0.21 (32.0% des jours) ; normal_vol Sharpe -0.02 (37.6% des jours)
- **crisis** : no_crisis Sharpe +0.44 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.59 (29.3% des jours) ; neutral Sharpe +0.67 (37.7% des jours) ; trending Sharpe +0.04 (32.9% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 56.2% ; PBO 0.37 ; ratio OOS/IS +0.64.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 23 trades / an sur la classe ; exposition moyenne 94.8% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Retournements de tendance longue.

Observées sur l'OOS : volatility = normal_vol (Sharpe -0.02).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.44, robustness 0.92, oos_stability 0.75, drawdown 0.48, cost_sensitivity 0.99, parameter_stability 0.56, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.62
