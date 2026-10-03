# bollinger_reversion — equities
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
`qt/lab/strategies.py::bollinger_reversion` — baseline `{'n': 20, 'k': 2.0}`, candidat retenu par le walk-forward `{'n': 10, 'k': 1.5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.31 | +0.47 |
| CAGR | 1.5% | 2.5% |
| volatilité | 5.4% | 5.6% |
| drawdown max | -11.5% | -13.7% |
| Sortino | +0.39 | +0.62 |
| Calmar | +0.13 | +0.18 |
| trades | 1620 | 3992 |
| taux de réussite | 67.3% | 66.2% |
| profit factor | 1.28 | 1.24 |
| espérance / trade | +2.2 bp | +1.4 bp |
| exposition | 96.3% | 98.7% |
| skew | +0.24 | -0.12 |
| kurtosis | 23.1 | 15.0 |
| CVaR 5 % | -0.8% | -0.8% |
| récupération max (jours) | 1233 | 584 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.50 |
| CAGR | 2.3% |
| volatilité | 4.9% |
| drawdown max | -7.8% |
| Sortino | +0.60 |
| Calmar | +0.30 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.13 |
| kurtosis | 23.3 |
| CVaR 5 % | -0.7% |
| récupération max (jours) | 585 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.50 ; années positives 76.5% ; stabilité des paramètres 52.9% ; baseline sans sélection sur les mêmes années +0.26 ; ratio OOS/IS +0.74.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | k=1.5,n=10 | +0.67 | +0.11 |
| 2004 | 2000-2003 | k=2.0,n=10 | +0.60 | +0.24 |
| 2005 | 2000-2004 | k=2.0,n=10 | +0.52 | +0.30 |
| 2006 | 2001-2005 | k=1.5,n=10 | +0.26 | +2.10 |
| 2007 | 2002-2006 | k=1.5,n=10 | +0.53 | +0.70 |
| 2008 | 2003-2007 | k=1.5,n=10 | +0.65 | +0.72 |
| 2009 | 2004-2008 | k=1.5,n=10 | +0.76 | +0.32 |
| 2010 | 2005-2009 | k=1.5,n=10 | +0.80 | -0.36 |
| 2011 | 2006-2010 | k=1.5,n=10 | +0.62 | +0.83 |
| 2012 | 2007-2011 | k=1.5,n=10 | +0.48 | +1.39 |
| 2013 | 2008-2012 | k=1.5,n=10 | +0.57 | -0.29 |
| 2014 | 2009-2013 | k=2.0,n=10 | +0.60 | +0.82 |
| 2015 | 2010-2014 | k=2.5,n=40 | +0.59 | +0.75 |
| 2016 | 2011-2015 | k=2.5,n=10 | +0.88 | +0.97 |
| 2017 | 2012-2016 | k=2.0,n=10 | +0.99 | -0.50 |
| 2018 | 2013-2017 | k=2.5,n=10 | +0.97 | +0.56 |
| 2019 | 2014-2018 | k=2.5,n=10 | +0.82 | -0.31 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +0.92.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| n +5 % | paramètre | +0.40 | oui |
| n −5 % | paramètre | +0.47 | oui |
| k +5 % | paramètre | +0.47 | oui |
| k −5 % | paramètre | +0.43 | oui |
| n +10 % | paramètre | +0.40 | oui |
| n −10 % | paramètre | +0.47 | oui |
| k +10 % | paramètre | +0.43 | oui |
| k −10 % | paramètre | +0.42 | oui |
| n +20 % | paramètre | +0.34 | oui |
| n −20 % | paramètre | +0.44 | oui |
| k +20 % | paramètre | +0.46 | oui |
| k −20 % | paramètre | +0.41 | oui |
| coûts × 1.25 | coûts | +0.44 | oui |
| coûts × 1.5 | coûts | +0.41 | oui |
| slippage + 2.0 bp | coûts | +0.37 | oui |
| entrée retardée d'1 barre | exécution | +0.44 | oui |
| sortie retardée d'1 barre | exécution | +0.46 | oui |
| signal bruité (5%) | signal | +0.42 | oui |
| sans les 5% meilleurs trades | dépendance | +0.01 | non |
| sans les 10% meilleurs trades | dépendance | -0.32 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -13.0%, 5e centile -21.2% ; CAGR médian 2.6% [0.8% ; 4.2%] ; P(perte) 0.9%. P(drawdown au-delà de) : 10% → 84.2%, 20% → 7.4%, 25% → 1.2%, 35% → 0.1%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 10 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.43. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +29.9 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 12.8%. Sharpe avec coûts × 1,5 : +0.41.

## 14. Drawdown
Recherche : max -13.7%, moyen -2.3%, plus long passage sous l'eau 584 jours. Walk-forward OOS : max -7.8%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +1.33 (16.8% des jours) ; bull Sharpe +0.17 (64.1% des jours) ; sideways Sharpe +0.77 (19.1% des jours)
- **volatility** : high_vol Sharpe +0.68 (29.8% des jours) ; low_vol Sharpe +0.67 (30.8% des jours) ; normal_vol Sharpe +0.22 (39.4% des jours)
- **crisis** : no_crisis Sharpe +0.50 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.16 (32.3% des jours) ; neutral Sharpe +0.40 (39.4% des jours) ; trending Sharpe +0.98 (28.2% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 52.9% ; PBO 0.43 ; ratio OOS/IS +0.74.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 190 trades / an sur la classe ; exposition moyenne 98.7% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.89 | 0.0% | 5.6% | 3.1% | 91.3% | n/a |
| 10.0% | × 1.78 | 1.3% | 18.9% | 8.8% | 71.0% | 45 |
| 15.0% | × 2.67 | 7.6% | 34.0% | 24.4% | 34.0% | 43 |
| 20.0% | × 3.56 | 10.7% | 55.5% | 22.5% | 11.3% | 35 |
| 30.0% | × 5.34 | 9.8% | 76.8% | 13.1% | 0.3% | 18 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.89 | 3.6% | 4.6% | 1.5% | 90.3% | 215 |
| 10.0% | × 1.78 | 30.7% | 23.8% | 9.7% | 35.8% | 142 |
| 15.0% | × 2.67 | 42.7% | 32.2% | 14.6% | 10.5% | 98 |
| 20.0% | × 3.56 | 44.2% | 39.7% | 14.9% | 1.2% | 68 |
| 30.0% | × 5.34 | 36.8% | 48.0% | 15.2% | 0.0% | 35 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 0.89 | 19.4% | 0.0% | 53.4% | 27.2% | 154 |
| 10.0% | × 1.78 | 29.4% | 0.0% | 70.4% | 0.2% | 72 |
| 15.0% | × 2.67 | 26.6% | 0.0% | 73.4% | 0.0% | 36 |
| 20.0% | × 3.56 | 24.9% | 0.0% | 75.1% | 0.0% | 22 |
| 30.0% | × 5.34 | 22.3% | 0.0% | 77.7% | 0.0% | 11 |

## 19. Conditions d'échec
Attendues a priori : Breakouts de volatilité, tendances fortes.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.50, robustness 0.90, oos_stability 0.76, drawdown 0.58, cost_sensitivity 0.88, parameter_stability 0.53, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.63
