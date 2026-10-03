# pullback — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
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
| XLK | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| XLF | 1998-12-22 | 27.78 | B | 1 trous de plus de 5 jours (max 7); 3 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| XLE | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| XLV | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| XLI | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| XLY | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| XLP | 1998-12-22 | 27.78 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| XLU | 1998-12-22 | 27.78 | B | 1 trous de plus de 5 jours (max 7); 1 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| XLB | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.46 | +0.57 |
| CAGR | 2.1% | 2.7% |
| volatilité | 4.7% | 4.8% |
| drawdown max | -8.8% | -11.4% |
| Sortino | +0.51 | +0.66 |
| Calmar | +0.24 | +0.23 |
| trades | 3541 | 6715 |
| taux de réussite | 65.5% | 63.6% |
| profit factor | 1.25 | 1.22 |
| espérance / trade | +1.3 bp | +0.9 bp |
| exposition | 86.7% | 88.5% |
| skew | -1.05 | -0.78 |
| kurtosis | 19.2 | 15.4 |
| CVaR 5 % | -0.7% | -0.8% |
| récupération max (jours) | 679 | 615 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.47 |
| CAGR | 2.2% |
| volatilité | 4.9% |
| drawdown max | -8.7% |
| Sortino | +0.52 |
| Calmar | +0.25 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.99 |
| kurtosis | 15.1 |
| CVaR 5 % | -0.8% |
| récupération max (jours) | 642 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.47 ; années positives 76.5% ; stabilité des paramètres 41.2% ; baseline sans sélection sur les mêmes années +0.51 ; ratio OOS/IS +0.71.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | lookback=3,max_hold=10,trend=200 | +0.65 | +2.01 |
| 2004 | 2000-2003 | lookback=3,max_hold=10,trend=200 | +1.05 | +0.02 |
| 2005 | 2000-2004 | lookback=3,max_hold=10,trend=200 | +0.81 | +0.40 |
| 2006 | 2001-2005 | lookback=3,max_hold=10,trend=200 | +0.66 | +1.56 |
| 2007 | 2002-2006 | lookback=3,max_hold=10,trend=200 | +1.02 | +0.40 |
| 2008 | 2003-2007 | lookback=10,max_hold=10,trend=200 | +0.85 | +0.66 |
| 2009 | 2004-2008 | lookback=3,max_hold=10,trend=200 | +0.93 | +0.66 |
| 2010 | 2005-2009 | lookback=3,max_hold=10,trend=200 | +1.05 | +0.08 |
| 2011 | 2006-2010 | lookback=3,max_hold=10,trend=100 | +1.02 | -0.13 |
| 2012 | 2007-2011 | lookback=5,max_hold=10,trend=100 | +0.64 | +0.66 |
| 2013 | 2008-2012 | lookback=5,max_hold=10,trend=100 | +0.67 | +1.33 |
| 2014 | 2009-2013 | lookback=5,max_hold=10,trend=100 | +0.61 | +0.02 |
| 2015 | 2010-2014 | lookback=5,max_hold=10,trend=200 | +0.55 | -0.17 |
| 2016 | 2011-2015 | lookback=10,max_hold=10,trend=200 | +0.73 | +0.83 |
| 2017 | 2012-2016 | lookback=10,max_hold=10,trend=200 | +0.82 | +1.79 |
| 2018 | 2013-2017 | lookback=10,max_hold=10,trend=200 | +1.00 | -0.04 |
| 2019 | 2014-2018 | lookback=10,max_hold=10,trend=200 | +0.64 | -0.32 |

## 9. Robustesse
Score 92.3% sur 26 perturbations ; ratio voisins/optimum +0.96.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.53 | oui |
| lookback −5 % | paramètre | +0.29 | oui |
| trend +5 % | paramètre | +0.58 | oui |
| trend −5 % | paramètre | +0.56 | oui |
| max_hold +5 % | paramètre | +0.57 | oui |
| max_hold −5 % | paramètre | +0.55 | oui |
| lookback +10 % | paramètre | +0.53 | oui |
| lookback −10 % | paramètre | +0.29 | oui |
| trend +10 % | paramètre | +0.56 | oui |
| trend −10 % | paramètre | +0.54 | oui |
| max_hold +10 % | paramètre | +0.57 | oui |
| max_hold −10 % | paramètre | +0.55 | oui |
| lookback +20 % | paramètre | +0.53 | oui |
| lookback −20 % | paramètre | +0.29 | oui |
| trend +20 % | paramètre | +0.58 | oui |
| trend −20 % | paramètre | +0.49 | oui |
| max_hold +20 % | paramètre | +0.57 | oui |
| max_hold −20 % | paramètre | +0.56 | oui |
| coûts × 1.25 | coûts | +0.53 | oui |
| coûts × 1.5 | coûts | +0.49 | oui |
| slippage + 2.0 bp | coûts | +0.38 | oui |
| entrée retardée d'1 barre | exécution | +0.40 | oui |
| sortie retardée d'1 barre | exécution | +0.55 | oui |
| signal bruité (5%) | signal | +0.54 | oui |
| sans les 5% meilleurs trades | dépendance | -0.11 | non |
| sans les 10% meilleurs trades | dépendance | -0.56 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -11.4%, 5e centile -19.1% ; CAGR médian 2.6% [1.1% ; 4.2%] ; P(perte) 0.1%. P(drawdown au-delà de) : 10% → 67.6%, 20% → 3.4%, 25% → 0.6%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 11 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.23. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +17.1 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 19.8%. Sharpe avec coûts × 1,5 : +0.49.

## 14. Drawdown
Recherche : max -11.4%, moyen -2.5%, plus long passage sous l'eau 615 jours. Walk-forward OOS : max -8.7%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.94 (20.6% des jours) ; bull Sharpe +0.30 (62.5% des jours) ; sideways Sharpe +0.56 (16.9% des jours)
- **volatility** : high_vol Sharpe +0.38 (31.5% des jours) ; low_vol Sharpe +0.70 (30.6% des jours) ; normal_vol Sharpe +0.46 (37.9% des jours)
- **crisis** : no_crisis Sharpe +0.47 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.18 (27.9% des jours) ; neutral Sharpe +0.53 (41.4% des jours) ; trending Sharpe +0.69 (30.7% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 41.2% ; PBO 0.23 ; ratio OOS/IS +0.71.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 320 trades / an sur la classe ; exposition moyenne 88.5% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Retournements de tendance, krachs.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.47, robustness 0.92, oos_stability 0.76, drawdown 0.62, cost_sensitivity 0.87, parameter_stability 0.41, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.62
