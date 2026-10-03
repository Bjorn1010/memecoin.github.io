# rsi2_trend — indices
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.77 (> 0.5)
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
`qt/lab/strategies.py::rsi2_trend` — baseline `{'threshold': 10, 'trend': 200}`, candidat retenu par le walk-forward `{'threshold': 15, 'trend': 200}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.58 | +0.61 |
| CAGR | 1.7% | 2.1% |
| volatilité | 3.0% | 3.6% |
| drawdown max | -7.8% | -11.5% |
| Sortino | +0.46 | +0.54 |
| Calmar | +0.22 | +0.19 |
| trades | 1778 | 2552 |
| taux de réussite | 62.0% | 62.4% |
| profit factor | 1.60 | 1.52 |
| espérance / trade | +2.9 bp | +2.6 bp |
| exposition | 37.5% | 48.2% |
| skew | -1.26 | -1.38 |
| kurtosis | 58.3 | 43.4 |
| CVaR 5 % | -0.4% | -0.5% |
| récupération max (jours) | 483 | 963 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.32 |
| CAGR | 0.9% |
| volatilité | 3.0% |
| drawdown max | -11.5% |
| Sortino | +0.25 |
| Calmar | +0.08 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -3.06 |
| kurtosis | 86.4 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 940 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.32 ; années positives 69.6% ; stabilité des paramètres 30.4% ; baseline sans sélection sur les mêmes années +0.53 ; ratio OOS/IS +0.54.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | threshold=15,trend=100 | +1.86 | +2.25 |
| 1998 | 1994-1997 | threshold=15,trend=100 | +1.91 | +0.99 |
| 1999 | 1994-1998 | threshold=15,trend=100 | +1.75 | +0.94 |
| 2000 | 1995-1999 | threshold=15,trend=200 | +1.89 | -0.04 |
| 2001 | 1996-2000 | threshold=10,trend=200 | +1.33 | +0.96 |
| 2002 | 1997-2001 | threshold=10,trend=200 | +1.31 | -0.30 |
| 2003 | 1998-2002 | threshold=5,trend=200 | +0.77 | +1.14 |
| 2004 | 1999-2003 | threshold=5,trend=200 | +0.68 | +0.72 |
| 2005 | 2000-2004 | threshold=5,trend=200 | +0.66 | +0.26 |
| 2006 | 2001-2005 | threshold=5,trend=200 | +0.69 | +0.18 |
| 2007 | 2002-2006 | threshold=10,trend=100 | +0.47 | -0.27 |
| 2008 | 2003-2007 | threshold=5,trend=200 | +0.51 | +0.85 |
| 2009 | 2004-2008 | threshold=15,trend=200 | +0.49 | +1.44 |
| 2010 | 2005-2009 | threshold=15,trend=100 | +0.86 | -0.69 |
| 2011 | 2006-2010 | threshold=15,trend=100 | +0.81 | +0.61 |
| 2012 | 2007-2011 | threshold=10,trend=100 | +0.77 | +0.94 |
| 2013 | 2008-2012 | threshold=10,trend=100 | +1.05 | +1.17 |
| 2014 | 2009-2013 | threshold=10,trend=100 | +0.93 | -1.41 |
| 2015 | 2010-2014 | threshold=15,trend=200 | +0.46 | +0.02 |
| 2016 | 2011-2015 | threshold=15,trend=200 | +0.66 | +0.62 |
| 2017 | 2012-2016 | threshold=15,trend=200 | +0.63 | +2.45 |
| 2018 | 2013-2017 | threshold=15,trend=200 | +0.97 | -0.96 |
| 2019 | 2014-2018 | threshold=15,trend=200 | +0.12 | -0.32 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +1.00.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| threshold +5 % | paramètre | +0.60 | oui |
| threshold −5 % | paramètre | +0.65 | oui |
| trend +5 % | paramètre | +0.60 | oui |
| trend −5 % | paramètre | +0.60 | oui |
| threshold +10 % | paramètre | +0.60 | oui |
| threshold −10 % | paramètre | +0.65 | oui |
| trend +10 % | paramètre | +0.61 | oui |
| trend −10 % | paramètre | +0.59 | oui |
| threshold +20 % | paramètre | +0.54 | oui |
| threshold −20 % | paramètre | +0.59 | oui |
| trend +20 % | paramètre | +0.59 | oui |
| trend −20 % | paramètre | +0.62 | oui |
| coûts × 1.25 | coûts | +0.57 | oui |
| coûts × 1.5 | coûts | +0.53 | oui |
| slippage + 2.0 bp | coûts | +0.51 | oui |
| entrée retardée d'1 barre | exécution | +0.58 | oui |
| sortie retardée d'1 barre | exécution | +0.72 | oui |
| signal bruité (5%) | signal | +0.60 | oui |
| sans les 5% meilleurs trades | dépendance | -0.01 | non |
| sans les 10% meilleurs trades | dépendance | -0.26 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -9.2%, 5e centile -15.3% ; CAGR médian 2.1% [1.1% ; 3.2%] ; P(perte) 0.1%. P(drawdown au-delà de) : 10% → 38.8%, 20% → 0.9%, 25% → 0.1%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 10 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.77. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +27.0 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 9.8%. Sharpe avec coûts × 1,5 : +0.53.

## 14. Drawdown
Recherche : max -11.5%, moyen -2.0%, plus long passage sous l'eau 963 jours. Walk-forward OOS : max -11.5%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.21 (21.8% des jours) ; bull Sharpe +0.30 (60.0% des jours) ; sideways Sharpe +0.50 (18.2% des jours)
- **volatility** : high_vol Sharpe +0.18 (29.5% des jours) ; low_vol Sharpe +0.46 (28.7% des jours) ; normal_vol Sharpe +0.42 (41.8% des jours)
- **crisis** : no_crisis Sharpe +0.32 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.42 (32.4% des jours) ; neutral Sharpe +0.01 (39.9% des jours) ; trending Sharpe +0.68 (27.7% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 30.4% ; PBO 0.77 ; ratio OOS/IS +0.54.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 95 trades / an sur la classe ; exposition moyenne 48.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marché baissier prolongé, retournement de tendance.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.77 (> 0.5)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.32, robustness 0.90, oos_stability 0.70, drawdown 0.69, cost_sensitivity 0.87, parameter_stability 0.30, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.59
