# mr_equity_basket — multi
**Décision : PROMISING** — robustesse 62% (< 70%); Sharpe déflaté 0.00 sur 1300 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un panier à risque égal de règles de retour à la moyenne court terme (RSI(2) tendance, Bollinger, pullback, IBS) sur indices, ETF sectoriels et futures a un rendement net positif hors échantillon et plus stable que chaque règle seule.

*Pourquoi cela pourrait marcher :* Prime de fourniture de liquidité à court terme sur les actions (Nagel 2012) ; diversifier des edges faibles et peu corrélés augmente le Sharpe en racine du nombre de paris indépendants.
## 2. Stratégie retail
Famille **ensemble**. Signal : moyenne de 12 flux (4 règles × 3 classes), chacun ramené à 10 % de vol (échelle revue chaque mois). Condition : paramètres canoniques, aucune optimisation. Horizon : 1 à 10 jours par trade. Cible mesurée : rendement net du panier > 0, Sharpe déflaté ≥ 0,90. Risque : krachs où les excès s'étendent (2008, mars 2020) ; règles corrélées entre elles.
## 3. Formulation mathématique
`r_t = moyenne_i( s_i,t · r_i,t ), s_i,t = min(0,10 / σ̂_i(60 j), 3) révisé chaque mois ; i ∈ {rsi2_trend, bollinger, pullback, ibs} × {indices, actions, futures}`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::mr_equity_basket` — baseline `{'members': (('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures'))}`, candidat retenu par le walk-forward `{'members': (('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures'))}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.49 | +0.49 |
| CAGR | 3.1% | 3.1% |
| volatilité | 6.6% | 6.6% |
| drawdown max | -18.1% | -18.1% |
| Sortino | +0.61 | +0.61 |
| Calmar | +0.17 | +0.17 |
| trades | 58786 | 58786 |
| taux de réussite | 56.1% | 56.1% |
| profit factor | 1.13 | 1.13 |
| espérance / trade | +0.1 bp | +0.1 bp |
| exposition | 100.0% | 100.0% |
| skew | -0.22 | -0.22 |
| kurtosis | 31.0 | 31.0 |
| CVaR 5 % | -0.9% | -0.9% |
| récupération max (jours) | 710 | 710 |
| années | 27.0 | 27.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.48 |
| CAGR | 3.0% |
| volatilité | 6.7% |
| drawdown max | -18.1% |
| Sortino | +0.59 |
| Calmar | +0.17 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.21 |
| kurtosis | 32.8 |
| CVaR 5 % | -1.0% |
| récupération max (jours) | 580 |
| années | 23.1 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.48 ; années positives 73.9% ; stabilité des paramètres 100.0% ; baseline sans sélection sur les mêmes années +0.48 ; ratio OOS/IS +1.00.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.24 | +1.29 |
| 1998 | 1994-1997 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.57 | +1.34 |
| 1999 | 1994-1998 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.70 | +0.89 |
| 2000 | 1995-1999 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +1.01 | +1.04 |
| 2001 | 1996-2000 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +1.08 | -0.33 |
| 2002 | 1997-2001 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.87 | +0.61 |
| 2003 | 1998-2002 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.70 | +0.86 |
| 2004 | 1999-2003 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.59 | -0.44 |
| 2005 | 2000-2004 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.32 | -0.07 |
| 2006 | 2001-2005 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.12 | +0.96 |
| 2007 | 2002-2006 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.37 | +0.73 |
| 2008 | 2003-2007 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.42 | +2.19 |
| 2009 | 2004-2008 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.64 | +0.77 |
| 2010 | 2005-2009 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.88 | -0.07 |
| 2011 | 2006-2010 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.81 | +0.74 |
| 2012 | 2007-2011 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.77 | +0.28 |
| 2013 | 2008-2012 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.68 | +1.28 |
| 2014 | 2009-2013 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.55 | +0.01 |
| 2015 | 2010-2014 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.42 | +0.35 |
| 2016 | 2011-2015 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.51 | +0.83 |
| 2017 | 2012-2016 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.52 | +1.16 |
| 2018 | 2013-2017 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.66 | -1.00 |
| 2019 | 2014-2018 | members=(('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures')) | +0.03 | -0.04 |

## 9. Robustesse
Score 62.5% sur 8 perturbations ; ratio voisins/optimum n/a.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| coûts × 1.25 | coûts | +0.42 | oui |
| coûts × 1.5 | coûts | +0.34 | oui |
| slippage + 2.0 bp | coûts | +0.18 | non |
| entrée retardée d'1 barre | exécution | +0.37 | oui |
| sortie retardée d'1 barre | exécution | +0.52 | oui |
| signal bruité (5%) | signal | +0.49 | oui |
| sans les 5% meilleurs trades | dépendance | +0.03 | non |
| sans les 10% meilleurs trades | dépendance | -0.23 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -15.4%, 5e centile -24.5% ; CAGR médian 3.1% [1.3% ; 4.7%] ; P(perte) 0.2%. P(drawdown au-delà de) : 10% → 96.2%, 20% → 17.9%, 25% → 4.2%, 35% → 0.3%, 50% → 0.0%.

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1300 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.72) — indistinguishable from selection luck. PBO de la grille : n/a. Reality Check / SPA sur les 2 stratégies de la classe : p = 0.010 / 0.010 (meilleure : mr_equity_basket).

## 12. Capacité
stratégie de portefeuille : capacité non estimée dans ce cycle

## 13. Coûts
Modèle : 0.00 bp/côté (comm 0.0, demi-spread 0.0, slippage 0.0), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 30.7%. Sharpe avec coûts × 1,5 : +0.34.

## 14. Drawdown
Recherche : max -18.1%, moyen -3.3%, plus long passage sous l'eau 710 jours. Walk-forward OOS : max -18.1%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.56 (19.0% des jours) ; bull Sharpe +0.17 (67.9% des jours) ; sideways Sharpe +1.36 (13.1% des jours)
- **volatility** : high_vol Sharpe +0.88 (30.2% des jours) ; low_vol Sharpe +0.29 (31.0% des jours) ; normal_vol Sharpe +0.16 (38.8% des jours)
- **crisis** : no_crisis Sharpe +0.48 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.09 (30.7% des jours) ; neutral Sharpe +0.85 (39.7% des jours) ; trending Sharpe +0.38 (29.6% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1300 essais enregistrés dans la base ; grille de 1 configurations déclarée avant exécution ; stabilité des paramètres 100.0% ; PBO n/a ; ratio OOS/IS +1.00.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 2176 trades / an sur la classe ; exposition moyenne 100.0% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.76 | 0.0% | 0.7% | 1.1% | 98.2% | n/a |
| 10.0% | × 1.53 | 1.2% | 11.6% | 8.9% | 78.3% | 55 |
| 15.0% | × 2.29 | 8.1% | 24.7% | 16.1% | 51.1% | 45 |
| 20.0% | × 3.05 | 17.6% | 34.1% | 20.5% | 27.8% | 37 |
| 30.0% | × 4.58 | 25.4% | 48.0% | 19.8% | 6.8% | 26 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.76 | 4.0% | 0.9% | 1.1% | 94.0% | 197 |
| 10.0% | × 1.53 | 37.9% | 10.1% | 7.0% | 45.0% | 156 |
| 15.0% | × 2.29 | 51.5% | 21.5% | 12.0% | 15.0% | 118 |
| 20.0% | × 3.05 | 53.6% | 31.8% | 11.6% | 3.0% | 81 |
| 30.0% | × 4.58 | 48.4% | 37.8% | 13.8% | 0.0% | 43 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.76 | 24.7% | 0.0% | 37.4% | 37.9% | 169 |
| 10.0% | × 1.53 | 40.7% | 0.0% | 58.3% | 1.0% | 85 |
| 15.0% | × 2.29 | 38.1% | 0.0% | 61.9% | 0.0% | 43 |
| 20.0% | × 3.05 | 37.7% | 0.0% | 62.3% | 0.0% | 30 |
| 30.0% | × 4.58 | 37.1% | 0.0% | 62.9% | 0.0% | 18 |

## 19. Conditions d'échec
Attendues a priori : Corrélation des règles proche de 1 (un seul pari) ; régimes de forte tendance baissière.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - robustesse 62% (< 70%) - Sharpe déflaté 0.00 sur 1300 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.48, robustness 0.62, oos_stability 0.74, drawdown 0.51, cost_sensitivity 0.70, parameter_stability 1.00, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.62
