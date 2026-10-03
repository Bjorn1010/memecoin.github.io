# rsi2_trend — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Le retour à la moyenne après un RSI(2) extrême fonctionne mieux dans le sens de la tendance de fond (SMA 200).

*Pourquoi cela pourrait marcher :* Acheter les replis dans une tendance haussière : liquidité + momentum.
## 2. Stratégie retail
Famille **hybrid**. Signal : RSI(2) extrême. Condition : clôture du bon côté de la SMA(trend). Horizon : jusqu'à clôture > SMA5. Cible mesurée : espérance nette > celle de rsi2. Risque : moins de trades ; dépendance au régime haussier.
## 3. Formulation mathématique
`rsi2 restreint au côté de la tendance : long seulement si C_t > SMA_T, short seulement si C_t < SMA_T`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::rsi2_trend` — baseline `{'threshold': 10, 'trend': 200}`, candidat retenu par le walk-forward `{'threshold': 15, 'trend': 100}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.40 | +0.26 |
| CAGR | 1.1% | 0.7% |
| volatilité | 2.7% | 3.0% |
| drawdown max | -7.6% | -12.2% |
| Sortino | +0.31 | +0.21 |
| Calmar | +0.14 | +0.06 |
| trades | 953 | 1336 |
| taux de réussite | 63.7% | 62.8% |
| profit factor | 1.29 | 1.14 |
| espérance / trade | +2.2 bp | +1.1 bp |
| exposition | 36.6% | 46.1% |
| skew | -1.52 | -2.69 |
| kurtosis | 40.5 | 47.0 |
| CVaR 5 % | -0.4% | -0.5% |
| récupération max (jours) | 541 | 1439 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.47 |
| CAGR | 1.2% |
| volatilité | 2.5% |
| drawdown max | -5.1% |
| Sortino | +0.36 |
| Calmar | +0.23 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -1.22 |
| kurtosis | 35.1 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 610 |
| années | 15.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.47 ; années positives 80.0% ; stabilité des paramètres 26.7% ; baseline sans sélection sur les mêmes années +0.45 ; ratio OOS/IS +0.71.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2005 | 2002-2004 | threshold=10,trend=200 | +0.22 | +0.20 |
| 2006 | 2002-2005 | threshold=5,trend=200 | +0.23 | +0.79 |
| 2007 | 2002-2006 | threshold=10,trend=100 | +0.51 | +0.02 |
| 2008 | 2003-2007 | threshold=10,trend=100 | +0.44 | +2.72 |
| 2009 | 2004-2008 | threshold=15,trend=100 | +0.84 | +1.73 |
| 2010 | 2005-2009 | threshold=15,trend=100 | +1.29 | +0.55 |
| 2011 | 2006-2010 | threshold=15,trend=100 | +1.30 | +0.53 |
| 2012 | 2007-2011 | threshold=15,trend=100 | +1.03 | +0.43 |
| 2013 | 2008-2012 | threshold=10,trend=100 | +1.36 | +0.68 |
| 2014 | 2009-2013 | threshold=5,trend=100 | +1.09 | -0.11 |
| 2015 | 2010-2014 | threshold=5,trend=100 | +0.69 | -0.42 |
| 2016 | 2011-2015 | threshold=10,trend=200 | +0.74 | +0.78 |
| 2017 | 2012-2016 | threshold=10,trend=200 | +0.71 | +1.29 |
| 2018 | 2013-2017 | threshold=5,trend=200 | +1.03 | -0.91 |
| 2019 | 2014-2018 | threshold=5,trend=200 | +0.36 | +0.18 |

## 9. Robustesse
Score 75.0% sur 20 perturbations ; ratio voisins/optimum +0.96.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| threshold +5 % | paramètre | +0.24 | oui |
| threshold −5 % | paramètre | +0.32 | oui |
| trend +5 % | paramètre | +0.25 | oui |
| trend −5 % | paramètre | +0.24 | oui |
| threshold +10 % | paramètre | +0.24 | oui |
| threshold −10 % | paramètre | +0.32 | oui |
| trend +10 % | paramètre | +0.22 | oui |
| trend −10 % | paramètre | +0.26 | oui |
| threshold +20 % | paramètre | +0.20 | oui |
| threshold −20 % | paramètre | +0.37 | oui |
| trend +20 % | paramètre | +0.25 | oui |
| trend −20 % | paramètre | +0.20 | oui |
| coûts × 1.25 | coûts | +0.23 | oui |
| coûts × 1.5 | coûts | +0.21 | oui |
| slippage + 2.0 bp | coûts | +0.07 | non |
| entrée retardée d'1 barre | exécution | -0.11 | non |
| sortie retardée d'1 barre | exécution | +0.12 | non |
| signal bruité (5%) | signal | +0.30 | oui |
| sans les 5% meilleurs trades | dépendance | -0.17 | non |
| sans les 10% meilleurs trades | dépendance | -0.44 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -9.9%, 5e centile -18.1% ; CAGR médian 0.8% [-0.3% ; 1.8%] ; P(perte) 13.2%. P(drawdown au-delà de) : 10% → 49.2%, 20% → 2.4%, 25% → 0.2%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 10 ; P(perte) 8.2%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.44. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +10.7 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 26.6%. Sharpe avec coûts × 1,5 : +0.21.

## 14. Drawdown
Recherche : max -12.2%, moyen -3.1%, plus long passage sous l'eau 1439 jours. Walk-forward OOS : max -5.1%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe -0.01 (23.8% des jours) ; bull Sharpe +0.48 (63.8% des jours) ; sideways Sharpe +1.14 (12.4% des jours)
- **volatility** : high_vol Sharpe +0.37 (30.1% des jours) ; low_vol Sharpe +0.47 (28.9% des jours) ; normal_vol Sharpe +0.59 (41.0% des jours)
- **crisis** : no_crisis Sharpe +0.47 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.81 (30.6% des jours) ; neutral Sharpe +0.37 (36.8% des jours) ; trending Sharpe +0.27 (32.6% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 26.7% ; PBO 0.44 ; ratio OOS/IS +0.71.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 69 trades / an sur la classe ; exposition moyenne 46.1% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marché baissier prolongé, retournement de tendance.

Observées sur l'OOS : direction = bear (Sharpe -0.01).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.47, robustness 0.75, oos_stability 0.80, drawdown 0.64, cost_sensitivity 0.82, parameter_stability 0.27, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.57
