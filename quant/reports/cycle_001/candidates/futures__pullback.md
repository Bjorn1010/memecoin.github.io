# pullback — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.69 (> 0.5)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Dans une tendance de fond, une clôture au plus bas de N jours est suivie d'un rebond (pullback statistique).

*Pourquoi cela pourrait marcher :* Acheter la faiblesse temporaire dans une tendance.
## 2. Stratégie retail
Famille **mean_reversion**. Signal : clôture = plus bas sur N jours. Condition : clôture au-dessus de la SMA(trend). Horizon : jusqu'au plus haut N jours ou 10 jours. Cible mesurée : espérance nette > 0. Risque : replis qui deviennent des retournements.
## 3. Formulation mathématique
`long si C_t = min(C_{t−N+1..t}) et C_t > SMA_T, sortie à max(C_{t−N+1..t}) ou 10 jours ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::pullback` — baseline `{'lookback': 5, 'trend': 200, 'max_hold': 10}`, candidat retenu par le walk-forward `{'lookback': 3, 'trend': 200, 'max_hold': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.27 | +0.32 |
| CAGR | 1.2% | 1.5% |
| volatilité | 4.8% | 5.0% |
| drawdown max | -11.3% | -12.0% |
| Sortino | +0.30 | +0.37 |
| Calmar | +0.10 | +0.12 |
| trades | 1775 | 3315 |
| taux de réussite | 66.2% | 65.6% |
| profit factor | 1.13 | 1.12 |
| espérance / trade | +1.3 bp | +0.9 bp |
| exposition | 76.8% | 80.6% |
| skew | -0.71 | -0.68 |
| kurtosis | 12.6 | 11.0 |
| CVaR 5 % | -0.8% | -0.8% |
| récupération max (jours) | 1365 | 1893 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.43 |
| CAGR | 2.0% |
| volatilité | 4.9% |
| drawdown max | -12.5% |
| Sortino | +0.51 |
| Calmar | +0.16 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.42 |
| kurtosis | 10.1 |
| CVaR 5 % | -0.7% |
| récupération max (jours) | 1560 |
| années | 15.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.43 ; années positives 60.0% ; stabilité des paramètres 33.3% ; baseline sans sélection sur les mêmes années +0.31 ; ratio OOS/IS +0.76.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2005 | 2002-2004 | lookback=3,max_hold=10,trend=200 | +0.93 | -0.48 |
| 2006 | 2002-2005 | lookback=3,max_hold=10,trend=200 | +0.57 | +1.02 |
| 2007 | 2002-2006 | lookback=3,max_hold=10,trend=200 | +0.67 | -0.20 |
| 2008 | 2003-2007 | lookback=3,max_hold=10,trend=200 | +0.24 | +2.59 |
| 2009 | 2004-2008 | lookback=3,max_hold=10,trend=200 | +0.66 | +0.74 |
| 2010 | 2005-2009 | lookback=3,max_hold=10,trend=100 | +0.80 | +0.78 |
| 2011 | 2006-2010 | lookback=3,max_hold=10,trend=100 | +0.99 | -0.68 |
| 2012 | 2007-2011 | lookback=5,max_hold=10,trend=100 | +0.61 | -0.75 |
| 2013 | 2008-2012 | lookback=3,max_hold=10,trend=100 | +0.55 | +1.17 |
| 2014 | 2009-2013 | lookback=10,max_hold=10,trend=100 | +0.53 | -0.05 |
| 2015 | 2010-2014 | lookback=10,max_hold=10,trend=200 | +0.33 | +0.39 |
| 2016 | 2011-2015 | lookback=10,max_hold=10,trend=200 | +0.54 | +0.94 |
| 2017 | 2012-2016 | lookback=10,max_hold=10,trend=200 | +0.70 | +1.94 |
| 2018 | 2013-2017 | lookback=10,max_hold=10,trend=200 | +1.11 | +0.46 |
| 2019 | 2014-2018 | lookback=10,max_hold=10,trend=200 | +0.71 | -0.29 |

## 9. Robustesse
Score 84.6% sur 26 perturbations ; ratio voisins/optimum +0.93.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.29 | oui |
| lookback −5 % | paramètre | +0.26 | oui |
| trend +5 % | paramètre | +0.31 | oui |
| trend −5 % | paramètre | +0.29 | oui |
| max_hold +5 % | paramètre | +0.32 | oui |
| max_hold −5 % | paramètre | +0.31 | oui |
| lookback +10 % | paramètre | +0.29 | oui |
| lookback −10 % | paramètre | +0.26 | oui |
| trend +10 % | paramètre | +0.33 | oui |
| trend −10 % | paramètre | +0.28 | oui |
| max_hold +10 % | paramètre | +0.32 | oui |
| max_hold −10 % | paramètre | +0.31 | oui |
| lookback +20 % | paramètre | +0.29 | oui |
| lookback −20 % | paramètre | +0.26 | oui |
| trend +20 % | paramètre | +0.33 | oui |
| trend −20 % | paramètre | +0.22 | oui |
| max_hold +20 % | paramètre | +0.33 | oui |
| max_hold −20 % | paramètre | +0.33 | oui |
| coûts × 1.25 | coûts | +0.29 | oui |
| coûts × 1.5 | coûts | +0.25 | oui |
| slippage + 2.0 bp | coûts | +0.04 | non |
| entrée retardée d'1 barre | exécution | -0.07 | non |
| sortie retardée d'1 barre | exécution | +0.20 | oui |
| signal bruité (5%) | signal | +0.33 | oui |
| sans les 5% meilleurs trades | dépendance | -0.27 | non |
| sans les 10% meilleurs trades | dépendance | -0.66 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -13.1%, 5e centile -22.4% ; CAGR médian 1.5% [-0.2% ; 3.1%] ; P(perte) 7.4%. P(drawdown au-delà de) : 10% → 80.4%, 20% → 9.5%, 25% → 2.5%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 10 ; P(perte) 3.8%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.69. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +8.9 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 31.2%. Sharpe avec coûts × 1,5 : +0.25.

## 14. Drawdown
Recherche : max -12.0%, moyen -4.2%, plus long passage sous l'eau 1893 jours. Walk-forward OOS : max -12.5%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.73 (35.5% des jours) ; bull Sharpe +0.37 (47.1% des jours) ; sideways Sharpe +0.11 (17.4% des jours)
- **volatility** : high_vol Sharpe +0.73 (29.6% des jours) ; low_vol Sharpe +0.84 (31.4% des jours) ; normal_vol Sharpe -0.11 (39.0% des jours)
- **crisis** : no_crisis Sharpe +0.43 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.25 (29.9% des jours) ; neutral Sharpe +0.66 (39.1% des jours) ; trending Sharpe +0.34 (31.0% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 33.3% ; PBO 0.69 ; ratio OOS/IS +0.76.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 171 trades / an sur la classe ; exposition moyenne 80.6% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Retournements de tendance, krachs.

Observées sur l'OOS : volatility = normal_vol (Sharpe -0.11).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.69 (> 0.5)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.43, robustness 0.85, oos_stability 0.60, drawdown 0.55, cost_sensitivity 0.78, parameter_stability 0.33, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.55
