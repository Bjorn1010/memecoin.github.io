# mtf_momentum — equities
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
| Sharpe | +0.45 | +0.67 |
| CAGR | 2.7% | 4.8% |
| volatilité | 6.4% | 7.4% |
| drawdown max | -10.9% | -11.8% |
| Sortino | +0.56 | +0.81 |
| Calmar | +0.25 | +0.41 |
| trades | 1364 | 806 |
| taux de réussite | 56.6% | 60.2% |
| profit factor | 1.34 | 1.92 |
| espérance / trade | +4.3 bp | +12.5 bp |
| exposition | 97.7% | 95.3% |
| skew | -0.61 | -0.69 |
| kurtosis | 5.7 | 7.6 |
| CVaR 5 % | -1.0% | -1.2% |
| récupération max (jours) | 1148 | 631 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.63 |
| CAGR | 4.5% |
| volatilité | 7.4% |
| drawdown max | -12.9% |
| Sortino | +0.75 |
| Calmar | +0.35 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.80 |
| kurtosis | 8.0 |
| CVaR 5 % | -1.2% |
| récupération max (jours) | 516 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.63 ; années positives 76.5% ; stabilité des paramètres 47.1% ; baseline sans sélection sur les mêmes années +0.58 ; ratio OOS/IS +0.78.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | hold=10,long=60,short=5 | +0.31 | +1.27 |
| 2004 | 2000-2003 | hold=10,long=60,short=5 | +0.55 | +1.10 |
| 2005 | 2000-2004 | hold=10,long=60,short=5 | +0.66 | -1.82 |
| 2006 | 2001-2005 | hold=10,long=250,short=3 | +0.54 | +1.27 |
| 2007 | 2002-2006 | hold=10,long=250,short=3 | +0.88 | +0.93 |
| 2008 | 2003-2007 | hold=10,long=250,short=10 | +0.96 | +0.03 |
| 2009 | 2004-2008 | hold=10,long=250,short=10 | +0.92 | -0.59 |
| 2010 | 2005-2009 | hold=10,long=250,short=3 | +0.72 | +0.82 |
| 2011 | 2006-2010 | hold=10,long=250,short=3 | +0.79 | +0.18 |
| 2012 | 2007-2011 | hold=10,long=250,short=3 | +0.58 | +1.32 |
| 2013 | 2008-2012 | hold=10,long=250,short=3 | +0.56 | +2.59 |
| 2014 | 2009-2013 | hold=10,long=250,short=3 | +0.91 | +1.10 |
| 2015 | 2010-2014 | hold=10,long=250,short=3 | +1.06 | +0.58 |
| 2016 | 2011-2015 | hold=10,long=250,short=10 | +1.06 | -0.09 |
| 2017 | 2012-2016 | hold=10,long=250,short=10 | +1.19 | +2.25 |
| 2018 | 2013-2017 | hold=10,long=250,short=5 | +1.35 | -0.33 |
| 2019 | 2014-2018 | hold=10,long=120,short=10 | +0.70 | +0.06 |

## 9. Robustesse
Score 92.3% sur 26 perturbations ; ratio voisins/optimum +0.93.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| long +5 % | paramètre | +0.59 | oui |
| long −5 % | paramètre | +0.63 | oui |
| short +5 % | paramètre | +0.63 | oui |
| short −5 % | paramètre | +0.52 | oui |
| hold +5 % | paramètre | +0.65 | oui |
| hold −5 % | paramètre | +0.67 | oui |
| long +10 % | paramètre | +0.60 | oui |
| long −10 % | paramètre | +0.62 | oui |
| short +10 % | paramètre | +0.63 | oui |
| short −10 % | paramètre | +0.52 | oui |
| hold +10 % | paramètre | +0.65 | oui |
| hold −10 % | paramètre | +0.67 | oui |
| long +20 % | paramètre | +0.57 | oui |
| long −20 % | paramètre | +0.65 | oui |
| short +20 % | paramètre | +0.63 | oui |
| short −20 % | paramètre | +0.52 | oui |
| hold +20 % | paramètre | +0.66 | oui |
| hold −20 % | paramètre | +0.66 | oui |
| coûts × 1.25 | coûts | +0.67 | oui |
| coûts × 1.5 | coûts | +0.66 | oui |
| slippage + 2.0 bp | coûts | +0.66 | oui |
| entrée retardée d'1 barre | exécution | +0.61 | oui |
| sortie retardée d'1 barre | exécution | +0.64 | oui |
| signal bruité (5%) | signal | +0.59 | oui |
| sans les 5% meilleurs trades | dépendance | +0.30 | non |
| sans les 10% meilleurs trades | dépendance | +0.09 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -15.6%, 5e centile -24.5% ; CAGR médian 4.8% [2.4% ; 7.3%] ; P(perte) 0.1%. P(drawdown au-delà de) : 10% → 98.0%, 20% → 18.4%, 25% → 3.9%, 35% → 0.2%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 9 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.12. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +131.0 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 1.6%. Sharpe avec coûts × 1,5 : +0.66.

## 14. Drawdown
Recherche : max -11.8%, moyen -3.6%, plus long passage sous l'eau 631 jours. Walk-forward OOS : max -12.9%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.82 (16.7% des jours) ; bull Sharpe +0.48 (67.0% des jours) ; sideways Sharpe +1.01 (16.3% des jours)
- **volatility** : high_vol Sharpe +1.04 (33.0% des jours) ; low_vol Sharpe +0.39 (29.0% des jours) ; normal_vol Sharpe +0.28 (38.0% des jours)
- **crisis** : no_crisis Sharpe +0.63 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.31 (30.4% des jours) ; neutral Sharpe +1.10 (38.8% des jours) ; trending Sharpe +0.32 (30.8% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 47.1% ; PBO 0.12 ; ratio OOS/IS +0.78.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 38 trades / an sur la classe ; exposition moyenne 95.3% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.67 | 0.0% | 4.1% | 2.0% | 93.9% | n/a |
| 10.0% | × 1.35 | 3.8% | 14.1% | 13.9% | 68.2% | 50 |
| 15.0% | × 2.02 | 9.7% | 44.4% | 18.5% | 27.4% | 41 |
| 20.0% | × 2.70 | 11.1% | 69.4% | 11.8% | 7.7% | 29 |
| 30.0% | × 4.04 | 10.2% | 83.1% | 6.1% | 0.6% | 19 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.67 | 11.9% | 0.0% | 0.8% | 87.3% | 192 |
| 10.0% | × 1.35 | 45.0% | 20.0% | 6.7% | 28.3% | 138 |
| 15.0% | × 2.02 | 54.2% | 26.4% | 12.3% | 7.1% | 88 |
| 20.0% | × 2.70 | 52.0% | 31.7% | 14.3% | 2.0% | 64 |
| 30.0% | × 4.04 | 36.4% | 55.9% | 7.7% | 0.0% | 27 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.67 | 33.0% | 0.0% | 45.7% | 21.3% | 150 |
| 10.0% | × 1.35 | 36.2% | 0.0% | 63.7% | 0.1% | 63 |
| 15.0% | × 2.02 | 32.3% | 0.0% | 67.7% | 0.0% | 32 |
| 20.0% | × 2.70 | 29.9% | 0.0% | 70.1% | 0.0% | 22 |
| 30.0% | × 4.04 | 27.9% | 0.0% | 72.1% | 0.0% | 10 |

## 19. Conditions d'échec
Attendues a priori : Retournements de tendance longue.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.63, robustness 0.92, oos_stability 0.76, drawdown 0.51, cost_sensitivity 0.98, parameter_stability 0.47, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.64
