# rsi2 — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un RSI(2) extrême est suivi d'un retour vers la moyenne 5 jours qui dépasse les coûts.

*Pourquoi cela pourrait marcher :* Liquidité fournie aux vendeurs forcés à court terme (Connors).
## 2. Stratégie retail
Famille **mean_reversion**. Signal : RSI(n) < seuil (achat) / > 100 − seuil (vente). Condition : aucune. Horizon : jusqu'à clôture > SMA5. Cible mesurée : espérance nette par trade > 0. Risque : pas de stop : un excès qui continue coûte cher.
## 3. Formulation mathématique
`long si RSI_n(C)_t < θ jusqu'à C_t > SMA5_t ; short si RSI_n > 100 − θ jusqu'à C_t < SMA5_t`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::rsi2` — baseline `{'length': 2, 'threshold': 10}`, candidat retenu par le walk-forward `{'length': 4, 'threshold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.19 | +0.44 |
| CAGR | 0.8% | 0.5% |
| volatilité | 5.1% | 1.3% |
| drawdown max | -17.3% | -4.2% |
| Sortino | +0.23 | +0.22 |
| Calmar | +0.05 | +0.13 |
| trades | 2473 | 132 |
| taux de réussite | 62.4% | 66.7% |
| profit factor | 1.08 | 2.20 |
| espérance / trade | +0.7 bp | +8.1 bp |
| exposition | 83.2% | 8.3% |
| skew | -0.22 | +6.36 |
| kurtosis | 15.5 | 172.7 |
| CVaR 5 % | -0.8% | -0.1% |
| récupération max (jours) | 1365 | 959 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.24 |
| CAGR | 0.8% |
| volatilité | 3.8% |
| drawdown max | -9.9% |
| Sortino | +0.24 |
| Calmar | +0.09 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.06 |
| kurtosis | 26.6 |
| CVaR 5 % | -0.6% |
| récupération max (jours) | 806 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.24 ; années positives 75.0% ; stabilité des paramètres 37.5% ; baseline sans sélection sur les mêmes années +0.14 ; ratio OOS/IS +0.48.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | length=3,threshold=15 | +0.66 | -0.32 |
| 2005 | 2001-2004 | length=4,threshold=5 | +0.43 | +0.59 |
| 2006 | 2001-2005 | length=3,threshold=15 | +0.48 | +0.53 |
| 2007 | 2002-2006 | length=4,threshold=10 | +0.64 | -0.45 |
| 2008 | 2003-2007 | length=2,threshold=5 | +0.39 | +0.36 |
| 2009 | 2004-2008 | length=2,threshold=15 | +0.81 | +0.79 |
| 2010 | 2005-2009 | length=2,threshold=15 | +0.97 | +0.01 |
| 2011 | 2006-2010 | length=2,threshold=15 | +0.84 | +0.05 |
| 2012 | 2007-2011 | length=2,threshold=15 | +0.62 | +0.93 |
| 2013 | 2008-2012 | length=2,threshold=15 | +0.75 | +0.21 |
| 2014 | 2009-2013 | length=4,threshold=15 | +0.43 | -0.37 |
| 2015 | 2010-2014 | length=4,threshold=5 | +0.37 | +1.46 |
| 2016 | 2011-2015 | length=4,threshold=5 | +0.63 | +0.81 |
| 2017 | 2012-2016 | length=4,threshold=5 | +0.96 | -2.02 |
| 2018 | 2013-2017 | length=4,threshold=5 | +0.49 | +0.71 |
| 2019 | 2014-2018 | length=4,threshold=5 | +0.42 | +1.44 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +0.78.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| length +5 % | paramètre | +0.33 | oui |
| length −5 % | paramètre | +0.27 | oui |
| threshold +5 % | paramètre | +0.36 | oui |
| threshold −5 % | paramètre | +0.45 | oui |
| length +10 % | paramètre | +0.33 | oui |
| length −10 % | paramètre | +0.27 | oui |
| threshold +10 % | paramètre | +0.36 | oui |
| threshold −10 % | paramètre | +0.45 | oui |
| length +20 % | paramètre | +0.33 | oui |
| length −20 % | paramètre | +0.27 | oui |
| threshold +20 % | paramètre | +0.36 | oui |
| threshold −20 % | paramètre | +0.45 | oui |
| coûts × 1.25 | coûts | +0.44 | oui |
| coûts × 1.5 | coûts | +0.43 | oui |
| slippage + 2.0 bp | coûts | +0.40 | oui |
| entrée retardée d'1 barre | exécution | +0.04 | non |
| sortie retardée d'1 barre | exécution | +0.33 | oui |
| signal bruité (5%) | signal | +0.42 | oui |
| sans les 5% meilleurs trades | dépendance | +0.27 | oui |
| sans les 10% meilleurs trades | dépendance | +0.14 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -2.2%, 5e centile -3.8% ; CAGR médian 0.5% [0.2% ; 0.9%] ; P(perte) 0.5%. P(drawdown au-delà de) : 10% → 0.0%, 20% → 0.0%, 25% → 0.0%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 4 trades, 95e centile 6 ; P(perte) 0.1%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.39. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +75.4 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 4.6%. Sharpe avec coûts × 1,5 : +0.43.

## 14. Drawdown
Recherche : max -4.2%, moyen -0.6%, plus long passage sous l'eau 959 jours. Walk-forward OOS : max -9.9%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.19 (18.7% des jours) ; bull Sharpe +0.19 (67.5% des jours) ; sideways Sharpe +0.52 (13.7% des jours)
- **volatility** : high_vol Sharpe +0.20 (31.4% des jours) ; low_vol Sharpe +0.62 (42.7% des jours) ; normal_vol Sharpe -0.20 (25.9% des jours)
- **crisis** : no_crisis Sharpe +0.24 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.59 (22.9% des jours) ; neutral Sharpe +0.10 (33.5% des jours) ; trending Sharpe +0.45 (23.4% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 37.5% ; PBO 0.39 ; ratio OOS/IS +0.48.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 7 trades / an sur la classe ; exposition moyenne 8.3% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés en forte tendance ; crises où les excès s'étendent ; coûts élevés.

Observées sur l'OOS : volatility = normal_vol (Sharpe -0.20).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.24, robustness 0.90, oos_stability 0.75, drawdown 0.92, cost_sensitivity 0.98, parameter_stability 0.38, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.62
