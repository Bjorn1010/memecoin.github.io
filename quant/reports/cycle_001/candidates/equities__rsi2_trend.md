# rsi2_trend — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.55 (> 0.5)
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
`qt/lab/strategies.py::rsi2_trend` — baseline `{'threshold': 10, 'trend': 200}`, candidat retenu par le walk-forward `{'threshold': 5, 'trend': 200}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.56 | +0.46 |
| CAGR | 1.4% | 0.8% |
| volatilité | 2.6% | 1.8% |
| drawdown max | -5.3% | -3.6% |
| Sortino | +0.49 | +0.30 |
| Calmar | +0.27 | +0.23 |
| trades | 1914 | 925 |
| taux de réussite | 65.5% | 65.1% |
| profit factor | 1.40 | 1.45 |
| espérance / trade | +1.6 bp | +1.8 bp |
| exposition | 51.6% | 31.3% |
| skew | -1.47 | -2.38 |
| kurtosis | 43.8 | 76.8 |
| CVaR 5 % | -0.4% | -0.3% |
| récupération max (jours) | 593 | 1024 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.48 |
| CAGR | 1.1% |
| volatilité | 2.4% |
| drawdown max | -7.4% |
| Sortino | +0.39 |
| Calmar | +0.15 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -2.42 |
| kurtosis | 48.7 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 724 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.48 ; années positives 76.5% ; stabilité des paramètres 35.3% ; baseline sans sélection sur les mêmes années +0.61 ; ratio OOS/IS +0.69.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | threshold=5,trend=200 | +0.64 | +1.55 |
| 2004 | 2000-2003 | threshold=5,trend=200 | +0.93 | +1.39 |
| 2005 | 2000-2004 | threshold=5,trend=200 | +1.04 | +1.41 |
| 2006 | 2001-2005 | threshold=5,trend=200 | +1.16 | +1.07 |
| 2007 | 2002-2006 | threshold=5,trend=200 | +1.21 | -0.05 |
| 2008 | 2003-2007 | threshold=5,trend=200 | +0.91 | -0.66 |
| 2009 | 2004-2008 | threshold=5,trend=100 | +0.92 | +0.75 |
| 2010 | 2005-2009 | threshold=15,trend=100 | +1.08 | +0.17 |
| 2011 | 2006-2010 | threshold=15,trend=100 | +1.13 | +0.74 |
| 2012 | 2007-2011 | threshold=10,trend=100 | +0.85 | +1.15 |
| 2013 | 2008-2012 | threshold=15,trend=100 | +1.21 | +1.58 |
| 2014 | 2009-2013 | threshold=10,trend=100 | +1.18 | +0.28 |
| 2015 | 2010-2014 | threshold=10,trend=200 | +1.00 | -0.12 |
| 2016 | 2011-2015 | threshold=10,trend=100 | +0.95 | +1.01 |
| 2017 | 2012-2016 | threshold=10,trend=200 | +0.93 | +1.50 |
| 2018 | 2013-2017 | threshold=10,trend=100 | +0.93 | -1.24 |
| 2019 | 2014-2018 | threshold=15,trend=200 | +0.26 | +0.66 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +1.07.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| threshold +5 % | paramètre | +0.49 | oui |
| threshold −5 % | paramètre | +0.46 | oui |
| trend +5 % | paramètre | +0.50 | oui |
| trend −5 % | paramètre | +0.46 | oui |
| threshold +10 % | paramètre | +0.49 | oui |
| threshold −10 % | paramètre | +0.46 | oui |
| trend +10 % | paramètre | +0.49 | oui |
| trend −10 % | paramètre | +0.49 | oui |
| threshold +20 % | paramètre | +0.49 | oui |
| threshold −20 % | paramètre | +0.46 | oui |
| trend +20 % | paramètre | +0.51 | oui |
| trend −20 % | paramètre | +0.48 | oui |
| coûts × 1.25 | coûts | +0.44 | oui |
| coûts × 1.5 | coûts | +0.43 | oui |
| slippage + 2.0 bp | coûts | +0.39 | oui |
| entrée retardée d'1 barre | exécution | +0.50 | oui |
| sortie retardée d'1 barre | exécution | +0.53 | oui |
| signal bruité (5%) | signal | +0.41 | oui |
| sans les 5% meilleurs trades | dépendance | +0.17 | non |
| sans les 10% meilleurs trades | dépendance | -0.03 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -4.3%, 5e centile -7.2% ; CAGR médian 0.8% [0.3% ; 1.3%] ; P(perte) 0.4%. P(drawdown au-delà de) : 10% → 0.6%, 20% → 0.0%, 25% → 0.0%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 8 ; P(perte) 0.1%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.55. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +30.3 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 10.4%. Sharpe avec coûts × 1,5 : +0.43.

## 14. Drawdown
Recherche : max -3.6%, moyen -0.9%, plus long passage sous l'eau 1024 jours. Walk-forward OOS : max -7.4%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +1.06 (20.0% des jours) ; bull Sharpe +0.38 (66.1% des jours) ; sideways Sharpe +0.40 (13.9% des jours)
- **volatility** : high_vol Sharpe +0.59 (29.8% des jours) ; low_vol Sharpe +0.33 (30.1% des jours) ; normal_vol Sharpe +0.49 (40.1% des jours)
- **crisis** : no_crisis Sharpe +0.48 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.44 (32.1% des jours) ; neutral Sharpe +0.62 (40.0% des jours) ; trending Sharpe +0.33 (27.9% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 35.3% ; PBO 0.55 ; ratio OOS/IS +0.69.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 44 trades / an sur la classe ; exposition moyenne 31.3% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 2.82 | 0.0% | 4.6% | 1.8% | 93.6% | n/a |
| 10.0% | × 5.64 | 0.5% | 24.8% | 0.9% | 73.8% | 52 |
| 15.0% | × 8.46 | 4.0% | 37.9% | 4.1% | 54.0% | 47 |
| 20.0% | × 11.28 | 8.0% | 50.9% | 3.1% | 38.0% | 38 |
| 30.0% | × 16.92 | 8.6% | 72.1% | 4.8% | 14.5% | 34 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 2.82 | 2.1% | 4.9% | 1.0% | 92.0% | 221 |
| 10.0% | × 5.64 | 28.1% | 36.6% | 1.9% | 33.4% | 172 |
| 15.0% | × 8.46 | 41.9% | 45.1% | 2.3% | 10.7% | 132 |
| 20.0% | × 11.28 | 39.9% | 55.8% | 0.8% | 3.5% | 92 |
| 30.0% | × 16.92 | 39.4% | 57.4% | 2.8% | 0.4% | 56 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 2.82 | 21.0% | 0.0% | 41.6% | 37.4% | 190 |
| 10.0% | × 5.64 | 38.6% | 0.0% | 58.7% | 2.7% | 112 |
| 15.0% | × 8.46 | 37.0% | 0.0% | 62.9% | 0.1% | 64 |
| 20.0% | × 11.28 | 34.1% | 0.0% | 65.9% | 0.0% | 44 |
| 30.0% | × 16.92 | 30.4% | 0.0% | 69.6% | 0.0% | 28 |

## 19. Conditions d'échec
Attendues a priori : Marché baissier prolongé, retournement de tendance.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.55 (> 0.5)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.48, robustness 0.90, oos_stability 0.76, drawdown 0.86, cost_sensitivity 0.94, parameter_stability 0.35, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.64
