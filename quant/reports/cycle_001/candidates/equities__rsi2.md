# rsi2 — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.62 (> 0.5)
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
`qt/lab/strategies.py::rsi2` — baseline `{'length': 2, 'threshold': 10}`, candidat retenu par le walk-forward `{'length': 2, 'threshold': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.46 | +0.46 |
| CAGR | 2.1% | 2.1% |
| volatilité | 4.8% | 4.8% |
| drawdown max | -14.4% | -14.4% |
| Sortino | +0.57 | +0.57 |
| Calmar | +0.15 | +0.15 |
| trades | 4954 | 4954 |
| taux de réussite | 64.3% | 64.3% |
| profit factor | 1.21 | 1.21 |
| espérance / trade | +1.0 bp | +1.0 bp |
| exposition | 93.6% | 93.6% |
| skew | -0.19 | -0.19 |
| kurtosis | 25.2 | 25.2 |
| CVaR 5 % | -0.7% | -0.7% |
| récupération max (jours) | 873 | 873 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.35 |
| CAGR | 1.5% |
| volatilité | 4.5% |
| drawdown max | -9.2% |
| Sortino | +0.41 |
| Calmar | +0.16 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.06 |
| kurtosis | 34.0 |
| CVaR 5 % | -0.6% |
| récupération max (jours) | 924 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.35 ; années positives 64.7% ; stabilité des paramètres 23.5% ; baseline sans sélection sur les mêmes années +0.35 ; ratio OOS/IS +0.57.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | length=2,threshold=10 | +0.94 | +0.31 |
| 2004 | 2000-2003 | length=3,threshold=15 | +0.83 | +0.06 |
| 2005 | 2000-2004 | length=3,threshold=15 | +0.70 | +0.96 |
| 2006 | 2001-2005 | length=3,threshold=15 | +0.53 | +2.30 |
| 2007 | 2002-2006 | length=4,threshold=15 | +0.79 | +0.50 |
| 2008 | 2003-2007 | length=3,threshold=10 | +1.03 | +0.77 |
| 2009 | 2004-2008 | length=3,threshold=10 | +1.03 | -0.93 |
| 2010 | 2005-2009 | length=2,threshold=15 | +1.00 | -0.04 |
| 2011 | 2006-2010 | length=2,threshold=15 | +0.87 | +0.60 |
| 2012 | 2007-2011 | length=2,threshold=15 | +0.64 | +1.57 |
| 2013 | 2008-2012 | length=2,threshold=15 | +0.82 | -0.53 |
| 2014 | 2009-2013 | length=2,threshold=10 | +0.40 | -0.21 |
| 2015 | 2010-2014 | length=2,threshold=10 | +0.43 | +0.70 |
| 2016 | 2011-2015 | length=2,threshold=10 | +0.52 | +0.60 |
| 2017 | 2012-2016 | length=4,threshold=10 | +0.73 | -1.50 |
| 2018 | 2013-2017 | length=4,threshold=10 | +0.42 | -0.33 |
| 2019 | 2014-2018 | length=4,threshold=5 | +0.27 | +1.96 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +0.90.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| length +5 % | paramètre | +0.37 | oui |
| length −5 % | paramètre | +0.33 | oui |
| threshold +5 % | paramètre | +0.49 | oui |
| threshold −5 % | paramètre | +0.46 | oui |
| length +10 % | paramètre | +0.37 | oui |
| length −10 % | paramètre | +0.33 | oui |
| threshold +10 % | paramètre | +0.49 | oui |
| threshold −10 % | paramètre | +0.46 | oui |
| length +20 % | paramètre | +0.37 | oui |
| length −20 % | paramètre | +0.33 | oui |
| threshold +20 % | paramètre | +0.47 | oui |
| threshold −20 % | paramètre | +0.49 | oui |
| coûts × 1.25 | coûts | +0.43 | oui |
| coûts × 1.5 | coûts | +0.39 | oui |
| slippage + 2.0 bp | coûts | +0.32 | oui |
| entrée retardée d'1 barre | exécution | +0.23 | oui |
| sortie retardée d'1 barre | exécution | +0.37 | oui |
| signal bruité (5%) | signal | +0.39 | oui |
| sans les 5% meilleurs trades | dépendance | -0.10 | non |
| sans les 10% meilleurs trades | dépendance | -0.48 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -12.0%, 5e centile -19.7% ; CAGR médian 2.1% [0.7% ; 3.6%] ; P(perte) 0.7%. P(drawdown au-delà de) : 10% → 75.4%, 20% → 4.3%, 25% → 0.9%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 11 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.62. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +25.3 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 17.7%. Sharpe avec coûts × 1,5 : +0.39.

## 14. Drawdown
Recherche : max -14.4%, moyen -2.7%, plus long passage sous l'eau 873 jours. Walk-forward OOS : max -9.2%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.78 (26.2% des jours) ; bull Sharpe -0.04 (58.7% des jours) ; sideways Sharpe +1.01 (15.1% des jours)
- **volatility** : high_vol Sharpe +0.28 (31.0% des jours) ; low_vol Sharpe +0.42 (30.0% des jours) ; normal_vol Sharpe +0.46 (39.0% des jours)
- **crisis** : no_crisis Sharpe +0.35 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.56 (31.8% des jours) ; neutral Sharpe +0.15 (39.1% des jours) ; trending Sharpe +0.42 (29.1% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 23.5% ; PBO 0.62 ; ratio OOS/IS +0.57.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 236 trades / an sur la classe ; exposition moyenne 93.6% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés en forte tendance ; crises où les excès s'étendent ; coûts élevés.

Observées sur l'OOS : direction = bull (Sharpe -0.04).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.62 (> 0.5)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.35, robustness 0.90, oos_stability 0.65, drawdown 0.61, cost_sensitivity 0.85, parameter_stability 0.24, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.55
