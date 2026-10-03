# bollinger_reversion — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Une clôture hors des bandes de Bollinger revient vers la moyenne mobile plus souvent et plus fort que les coûts.

*Pourquoi cela pourrait marcher :* Surréaction à court terme.
## 2. Stratégie retail
Famille **mean_reversion**. Signal : clôture hors bande ± k écarts-types. Condition : aucune. Horizon : jusqu'au retour à la moyenne. Cible mesurée : espérance nette > 0. Risque : sortie de bande qui devient une tendance.
## 3. Formulation mathématique
`long si C_t < SMA_n − k·σ_n jusqu'à C_t ≥ SMA_n ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::bollinger_reversion` — baseline `{'n': 20, 'k': 2.0}`, candidat retenu par le walk-forward `{'n': 10, 'k': 2.0}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.10 | +0.37 |
| CAGR | 0.4% | 1.5% |
| volatilité | 5.6% | 4.2% |
| drawdown max | -13.3% | -13.4% |
| Sortino | +0.12 | +0.41 |
| Calmar | +0.03 | +0.11 |
| trades | 785 | 938 |
| taux de réussite | 65.0% | 66.6% |
| profit factor | 1.10 | 1.26 |
| espérance / trade | +1.6 bp | +3.1 bp |
| exposition | 85.9% | 70.6% |
| skew | -0.03 | -0.07 |
| kurtosis | 11.8 | 20.3 |
| CVaR 5 % | -0.9% | -0.6% |
| récupération max (jours) | 1638 | 850 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.09 |
| CAGR | 0.3% |
| volatilité | 4.7% |
| drawdown max | -12.1% |
| Sortino | +0.10 |
| Calmar | +0.03 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.04 |
| kurtosis | 19.5 |
| CVaR 5 % | -0.7% |
| récupération max (jours) | 1013 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.09 ; années positives 75.0% ; stabilité des paramètres 43.8% ; baseline sans sélection sur les mêmes années +0.17 ; ratio OOS/IS +0.35.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | k=2.5,n=10 | +0.60 | +0.13 |
| 2005 | 2001-2004 | k=2.5,n=20 | +0.39 | +0.47 |
| 2006 | 2001-2005 | k=2.5,n=20 | +0.40 | -0.11 |
| 2007 | 2002-2006 | k=2.5,n=10 | +0.47 | +0.08 |
| 2008 | 2003-2007 | k=2.5,n=40 | +0.73 | -0.21 |
| 2009 | 2004-2008 | k=2.0,n=10 | +0.57 | +0.66 |
| 2010 | 2005-2009 | k=2.0,n=10 | +0.71 | +0.03 |
| 2011 | 2006-2010 | k=2.0,n=10 | +0.50 | +0.64 |
| 2012 | 2007-2011 | k=2.0,n=10 | +0.45 | +0.63 |
| 2013 | 2008-2012 | k=1.5,n=10 | +0.42 | +0.53 |
| 2014 | 2009-2013 | k=2.0,n=10 | +0.72 | +0.29 |
| 2015 | 2010-2014 | k=2.5,n=40 | +0.69 | +0.68 |
| 2016 | 2011-2015 | k=2.0,n=40 | +0.89 | -0.75 |
| 2017 | 2012-2016 | k=2.0,n=10 | +0.88 | +1.26 |
| 2018 | 2013-2017 | k=2.0,n=10 | +1.00 | -1.22 |
| 2019 | 2014-2018 | k=1.5,n=40 | +0.51 | +0.34 |

## 9. Robustesse
Score 80.0% sur 20 perturbations ; ratio voisins/optimum +0.90.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| n +5 % | paramètre | +0.28 | oui |
| n −5 % | paramètre | +0.42 | oui |
| k +5 % | paramètre | +0.40 | oui |
| k −5 % | paramètre | +0.33 | oui |
| n +10 % | paramètre | +0.28 | oui |
| n −10 % | paramètre | +0.42 | oui |
| k +10 % | paramètre | +0.34 | oui |
| k −10 % | paramètre | +0.29 | oui |
| n +20 % | paramètre | +0.36 | oui |
| n −20 % | paramètre | +0.47 | oui |
| k +20 % | paramètre | +0.03 | non |
| k −20 % | paramètre | +0.28 | oui |
| coûts × 1.25 | coûts | +0.36 | oui |
| coûts × 1.5 | coûts | +0.35 | oui |
| slippage + 2.0 bp | coûts | +0.28 | oui |
| entrée retardée d'1 barre | exécution | +0.15 | non |
| sortie retardée d'1 barre | exécution | +0.21 | oui |
| signal bruité (5%) | signal | +0.35 | oui |
| sans les 5% meilleurs trades | dépendance | +0.04 | non |
| sans les 10% meilleurs trades | dépendance | -0.16 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -10.1%, 5e centile -17.9% ; CAGR médian 1.5% [0.2% ; 2.8%] ; P(perte) 2.9%. P(drawdown au-delà de) : 10% → 51.4%, 20% → 2.4%, 25% → 0.5%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 8 ; P(perte) 1.6%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.40. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +28.1 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 12.0%. Sharpe avec coûts × 1,5 : +0.35.

## 14. Drawdown
Recherche : max -13.4%, moyen -2.0%, plus long passage sous l'eau 850 jours. Walk-forward OOS : max -12.1%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.42 (19.6% des jours) ; bull Sharpe -0.28 (63.1% des jours) ; sideways Sharpe +0.81 (17.3% des jours)
- **volatility** : high_vol Sharpe +0.35 (30.9% des jours) ; low_vol Sharpe -0.30 (30.7% des jours) ; normal_vol Sharpe -0.02 (38.4% des jours)
- **crisis** : no_crisis Sharpe +0.09 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.13 (28.9% des jours) ; neutral Sharpe -0.07 (41.6% des jours) ; trending Sharpe +0.34 (29.5% des jours)

Dépendance détectée : volatility:high_vol. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 43.8% ; PBO 0.40 ; ratio OOS/IS +0.35.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 48 trades / an sur la classe ; exposition moyenne 70.6% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Breakouts de volatilité, tendances fortes.

Observées sur l'OOS : direction = bull (Sharpe -0.28), volatility = low_vol (Sharpe -0.30), volatility = normal_vol (Sharpe -0.02), character = neutral (Sharpe -0.07).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.09, robustness 0.80, oos_stability 0.75, drawdown 0.64, cost_sensitivity 0.94, parameter_stability 0.44, capacity 0.50, regime_diversity 0.60, statistical_confidence 0.00, composite 0.53
