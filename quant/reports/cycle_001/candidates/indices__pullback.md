# pullback — indices
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
`qt/lab/strategies.py::pullback` — baseline `{'lookback': 5, 'trend': 200, 'max_hold': 10}`, candidat retenu par le walk-forward `{'lookback': 10, 'trend': 200, 'max_hold': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.45 | +0.58 |
| CAGR | 2.3% | 2.5% |
| volatilité | 5.4% | 4.4% |
| drawdown max | -12.4% | -10.1% |
| Sortino | +0.49 | +0.57 |
| Calmar | +0.18 | +0.25 |
| trades | 3361 | 1541 |
| taux de réussite | 65.1% | 62.0% |
| profit factor | 1.36 | 1.62 |
| espérance / trade | +2.3 bp | +5.1 bp |
| exposition | 75.1% | 62.9% |
| skew | -0.74 | -0.75 |
| kurtosis | 19.1 | 23.2 |
| CVaR 5 % | -0.8% | -0.7% |
| récupération max (jours) | 1030 | 1392 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.25 |
| CAGR | 1.1% |
| volatilité | 4.9% |
| drawdown max | -12.7% |
| Sortino | +0.27 |
| Calmar | +0.09 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.82 |
| kurtosis | 16.7 |
| CVaR 5 % | -0.8% |
| récupération max (jours) | 2121 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.25 ; années positives 60.9% ; stabilité des paramètres 26.1% ; baseline sans sélection sur les mêmes années +0.38 ; ratio OOS/IS +0.45.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | lookback=10,max_hold=10,trend=100 | +1.76 | +1.00 |
| 1998 | 1994-1997 | lookback=10,max_hold=10,trend=100 | +1.60 | +0.95 |
| 1999 | 1994-1998 | lookback=10,max_hold=10,trend=100 | +1.50 | +1.94 |
| 2000 | 1995-1999 | lookback=5,max_hold=10,trend=100 | +1.70 | -0.22 |
| 2001 | 1996-2000 | lookback=10,max_hold=10,trend=100 | +1.06 | -0.29 |
| 2002 | 1997-2001 | lookback=5,max_hold=10,trend=100 | +0.95 | +0.06 |
| 2003 | 1998-2002 | lookback=5,max_hold=10,trend=100 | +0.52 | +0.37 |
| 2004 | 1999-2003 | lookback=10,max_hold=10,trend=200 | +0.66 | -0.66 |
| 2005 | 2000-2004 | lookback=3,max_hold=10,trend=200 | +0.33 | -0.49 |
| 2006 | 2001-2005 | lookback=3,max_hold=10,trend=200 | +0.29 | +0.94 |
| 2007 | 2002-2006 | lookback=10,max_hold=10,trend=200 | +0.46 | +0.92 |
| 2008 | 2003-2007 | lookback=10,max_hold=10,trend=200 | +0.71 | +1.27 |
| 2009 | 2004-2008 | lookback=5,max_hold=10,trend=200 | +0.68 | -0.08 |
| 2010 | 2005-2009 | lookback=10,max_hold=10,trend=100 | +0.99 | -1.10 |
| 2011 | 2006-2010 | lookback=3,max_hold=10,trend=100 | +0.82 | -0.33 |
| 2012 | 2007-2011 | lookback=5,max_hold=10,trend=100 | +0.53 | +0.09 |
| 2013 | 2008-2012 | lookback=3,max_hold=10,trend=100 | +0.51 | +0.97 |
| 2014 | 2009-2013 | lookback=5,max_hold=10,trend=100 | +0.28 | -0.82 |
| 2015 | 2010-2014 | lookback=5,max_hold=10,trend=200 | +0.09 | +0.10 |
| 2016 | 2011-2015 | lookback=5,max_hold=10,trend=200 | +0.27 | +0.56 |
| 2017 | 2012-2016 | lookback=10,max_hold=10,trend=200 | +0.45 | +3.40 |
| 2018 | 2013-2017 | lookback=10,max_hold=10,trend=200 | +1.04 | +0.32 |
| 2019 | 2014-2018 | lookback=10,max_hold=10,trend=200 | +0.73 | -0.90 |

## 9. Robustesse
Score 92.3% sur 26 perturbations ; ratio voisins/optimum +0.97.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.56 | oui |
| lookback −5 % | paramètre | +0.53 | oui |
| trend +5 % | paramètre | +0.56 | oui |
| trend −5 % | paramètre | +0.58 | oui |
| max_hold +5 % | paramètre | +0.57 | oui |
| max_hold −5 % | paramètre | +0.56 | oui |
| lookback +10 % | paramètre | +0.56 | oui |
| lookback −10 % | paramètre | +0.53 | oui |
| trend +10 % | paramètre | +0.57 | oui |
| trend −10 % | paramètre | +0.57 | oui |
| max_hold +10 % | paramètre | +0.57 | oui |
| max_hold −10 % | paramètre | +0.56 | oui |
| lookback +20 % | paramètre | +0.56 | oui |
| lookback −20 % | paramètre | +0.52 | oui |
| trend +20 % | paramètre | +0.59 | oui |
| trend −20 % | paramètre | +0.58 | oui |
| max_hold +20 % | paramètre | +0.52 | oui |
| max_hold −20 % | paramètre | +0.62 | oui |
| coûts × 1.25 | coûts | +0.55 | oui |
| coûts × 1.5 | coûts | +0.51 | oui |
| slippage + 2.0 bp | coûts | +0.53 | oui |
| entrée retardée d'1 barre | exécution | +0.50 | oui |
| sortie retardée d'1 barre | exécution | +0.56 | oui |
| signal bruité (5%) | signal | +0.60 | oui |
| sans les 5% meilleurs trades | dépendance | +0.08 | non |
| sans les 10% meilleurs trades | dépendance | -0.13 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -10.2%, 5e centile -16.5% ; CAGR médian 2.5% [1.2% ; 3.6%] ; P(perte) 0.0%. P(drawdown au-delà de) : 10% → 52.4%, 20% → 1.0%, 25% → 0.1%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 10 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.04. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +52.5 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 5.3%. Sharpe avec coûts × 1,5 : +0.51.

## 14. Drawdown
Recherche : max -10.1%, moyen -2.6%, plus long passage sous l'eau 1392 jours. Walk-forward OOS : max -12.7%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.17 (23.8% des jours) ; bull Sharpe -0.00 (62.6% des jours) ; sideways Sharpe +1.25 (13.6% des jours)
- **volatility** : high_vol Sharpe +0.60 (30.6% des jours) ; low_vol Sharpe +0.59 (29.0% des jours) ; normal_vol Sharpe -0.29 (40.3% des jours)
- **crisis** : no_crisis Sharpe +0.25 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.35 (32.0% des jours) ; neutral Sharpe -0.11 (39.7% des jours) ; trending Sharpe +0.59 (28.3% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 26.1% ; PBO 0.04 ; ratio OOS/IS +0.45.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 57 trades / an sur la classe ; exposition moyenne 62.9% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Retournements de tendance, krachs.

Observées sur l'OOS : direction = bull (Sharpe -0.00), volatility = normal_vol (Sharpe -0.29), character = neutral (Sharpe -0.11).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.25, robustness 0.92, oos_stability 0.61, drawdown 0.67, cost_sensitivity 0.89, parameter_stability 0.26, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.53
