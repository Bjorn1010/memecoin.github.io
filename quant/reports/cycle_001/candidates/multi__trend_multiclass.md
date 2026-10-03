# trend_multiclass — multi
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 13% au Monte Carlo (> 10%)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un portefeuille de suivi de tendance (momentum 12 mois, croisement 50/200, Donchian 20/10) réparti à risque égal sur les 7 classes d'actifs a un rendement net positif hors échantillon.

*Pourquoi cela pourrait marcher :* Prime de tendance documentée sur un siècle et sur de nombreux marchés (Hurst, Ooi, Pedersen 2017) ; la diversification entre classes est la source principale de son Sharpe.
## 2. Stratégie retail
Famille **ensemble**. Signal : moyenne de 21 flux (3 règles × 7 classes), chacun ramené à 10 % de vol (échelle revue chaque mois). Condition : paramètres canoniques, aucune optimisation. Horizon : semaines à mois. Cible mesurée : rendement net > 0, Sharpe déflaté ≥ 0,90. Risque : retournements brutaux simultanés ; coût de portage.
## 3. Formulation mathématique
`r_t = moyenne_i( s_i,t · r_i,t ) ; i ∈ {tsmom 252, SMA 50/200, Donchian 20/10} × 7 classes ; même échelle mensuelle`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::trend_multiclass` — baseline `{'members': (('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities'))}`, candidat retenu par le walk-forward `{'members': (('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities'))}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.43 | +0.43 |
| CAGR | 2.5% | 2.5% |
| volatilité | 6.1% | 6.1% |
| drawdown max | -18.1% | -18.1% |
| Sortino | +0.52 | +0.52 |
| Calmar | +0.14 | +0.14 |
| trades | 10373 | 10373 |
| taux de réussite | 34.1% | 34.1% |
| profit factor | 1.89 | 1.89 |
| espérance / trade | +0.8 bp | +0.8 bp |
| exposition | 100.0% | 100.0% |
| skew | -0.88 | -0.88 |
| kurtosis | 14.8 | 14.8 |
| CVaR 5 % | -0.9% | -0.9% |
| récupération max (jours) | 1195 | 1195 |
| années | 27.8 | 27.8 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.41 |
| CAGR | 2.2% |
| volatilité | 5.6% |
| drawdown max | -11.3% |
| Sortino | +0.52 |
| Calmar | +0.19 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.60 |
| kurtosis | 8.0 |
| CVaR 5 % | -0.9% |
| récupération max (jours) | 1195 |
| années | 23.8 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.41 ; années positives 78.3% ; stabilité des paramètres 100.0% ; baseline sans sélection sur les mêmes années +0.41 ; ratio OOS/IS +0.77.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.81 | +1.79 |
| 1998 | 1994-1997 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +1.00 | +0.22 |
| 1999 | 1994-1998 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.88 | +0.31 |
| 2000 | 1995-1999 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +1.45 | -0.86 |
| 2001 | 1996-2000 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.54 | +0.52 |
| 2002 | 1997-2001 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.47 | +0.60 |
| 2003 | 1998-2002 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.20 | +0.35 |
| 2004 | 1999-2003 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.23 | +0.20 |
| 2005 | 2000-2004 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.21 | -0.80 |
| 2006 | 2001-2005 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.25 | +1.11 |
| 2007 | 2002-2006 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.32 | +0.55 |
| 2008 | 2003-2007 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.30 | +0.43 |
| 2009 | 2004-2008 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.32 | -0.13 |
| 2010 | 2005-2009 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.26 | +0.71 |
| 2011 | 2006-2010 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.51 | +0.05 |
| 2012 | 2007-2011 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.34 | -1.05 |
| 2013 | 2008-2012 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.12 | +2.18 |
| 2014 | 2009-2013 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.41 | +0.28 |
| 2015 | 2010-2014 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.50 | +0.13 |
| 2016 | 2011-2015 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.38 | +0.17 |
| 2017 | 2012-2016 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.40 | +2.05 |
| 2018 | 2013-2017 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.93 | +0.25 |
| 2019 | 2014-2018 | members=(('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities')) | +0.55 | -0.32 |

## 9. Robustesse
Score 75.0% sur 8 perturbations ; ratio voisins/optimum n/a.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| coûts × 1.25 | coûts | +0.38 | oui |
| coûts × 1.5 | coûts | +0.32 | oui |
| slippage + 2.0 bp | coûts | +0.38 | oui |
| entrée retardée d'1 barre | exécution | +0.42 | oui |
| sortie retardée d'1 barre | exécution | +0.46 | oui |
| signal bruité (5%) | signal | +0.44 | oui |
| sans les 5% meilleurs trades | dépendance | -0.13 | non |
| sans les 10% meilleurs trades | dépendance | -0.23 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -17.4%, 5e centile -28.7% ; CAGR médian 2.4% [0.7% ; 4.4%] ; P(perte) 1.7%. P(drawdown au-delà de) : 10% → 99.1%, 20% → 32.6%, 25% → 12.9%, 35% → 1.2%, 50% → 0.1%.

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : n/a. Reality Check / SPA sur les 2 stratégies de la classe : p = 0.010 / 0.010 (meilleure : mr_equity_basket).

## 12. Capacité
stratégie de portefeuille : capacité non estimée dans ce cycle

## 13. Coûts
Modèle : 0.00 bp/côté (comm 0.0, demi-spread 0.0, slippage 0.0), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 2.4%. Sharpe avec coûts × 1,5 : +0.32.

## 14. Drawdown
Recherche : max -18.1%, moyen -5.0%, plus long passage sous l'eau 1195 jours. Walk-forward OOS : max -11.3%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +1.18 (25.5% des jours) ; bull Sharpe +0.25 (51.6% des jours) ; sideways Sharpe +0.19 (23.0% des jours)
- **volatility** : high_vol Sharpe -0.15 (26.8% des jours) ; low_vol Sharpe +0.30 (33.4% des jours) ; normal_vol Sharpe +1.02 (39.8% des jours)
- **crisis** : no_crisis Sharpe +0.41 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.74 (31.9% des jours) ; neutral Sharpe +0.45 (38.4% des jours) ; trending Sharpe +0.08 (29.7% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 1 configurations déclarée avant exécution ; stabilité des paramètres 100.0% ; PBO n/a ; ratio OOS/IS +0.77.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 374 trades / an sur la classe ; exposition moyenne 100.0% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés sans tendance pendant des années (2011-2013) ; corrélations qui montent vers 1 en crise.

Observées sur l'OOS : volatility = high_vol (Sharpe -0.15).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 13% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.41, robustness 0.75, oos_stability 0.78, drawdown 0.43, cost_sensitivity 0.75, parameter_stability 1.00, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.61
