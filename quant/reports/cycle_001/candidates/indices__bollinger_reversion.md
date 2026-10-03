# bollinger_reversion — indices
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
| Sharpe | +0.13 | +0.50 |
| CAGR | 0.6% | 3.1% |
| volatilité | 6.1% | 6.6% |
| drawdown max | -20.2% | -14.8% |
| Sortino | +0.16 | +0.65 |
| Calmar | +0.03 | +0.21 |
| trades | 1533 | 3769 |
| taux de réussite | 64.8% | 64.4% |
| profit factor | 1.20 | 1.36 |
| espérance / trade | +2.2 bp | +2.8 bp |
| exposition | 87.6% | 92.6% |
| skew | +0.39 | +0.07 |
| kurtosis | 15.5 | 10.4 |
| CVaR 5 % | -0.9% | -1.0% |
| récupération max (jours) | 5451 | 688 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.36 |
| CAGR | 2.0% |
| volatilité | 5.9% |
| drawdown max | -13.3% |
| Sortino | +0.45 |
| Calmar | +0.15 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.02 |
| kurtosis | 14.7 |
| CVaR 5 % | -0.9% |
| récupération max (jours) | 790 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.36 ; années positives 78.3% ; stabilité des paramètres 60.9% ; baseline sans sélection sur les mêmes années +0.16 ; ratio OOS/IS +0.68.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | k=1.5,n=10 | +0.80 | +0.41 |
| 1998 | 1994-1997 | k=1.5,n=10 | +0.72 | +0.95 |
| 1999 | 1994-1998 | k=1.5,n=10 | +0.75 | +0.19 |
| 2000 | 1995-1999 | k=1.5,n=10 | +0.54 | +0.97 |
| 2001 | 1996-2000 | k=1.5,n=10 | +0.76 | +0.38 |
| 2002 | 1997-2001 | k=1.5,n=10 | +0.60 | +0.39 |
| 2003 | 1998-2002 | k=2.0,n=10 | +0.65 | +0.55 |
| 2004 | 1999-2003 | k=2.0,n=10 | +0.54 | -0.75 |
| 2005 | 2000-2004 | k=1.5,n=10 | +0.33 | +0.37 |
| 2006 | 2001-2005 | k=1.5,n=10 | +0.20 | +1.95 |
| 2007 | 2002-2006 | k=1.5,n=10 | +0.51 | +0.83 |
| 2008 | 2003-2007 | k=1.5,n=10 | +0.61 | +0.39 |
| 2009 | 2004-2008 | k=1.5,n=10 | +0.55 | +0.27 |
| 2010 | 2005-2009 | k=1.5,n=10 | +0.71 | -0.64 |
| 2011 | 2006-2010 | k=1.5,n=10 | +0.50 | +0.80 |
| 2012 | 2007-2011 | k=1.5,n=10 | +0.36 | +0.74 |
| 2013 | 2008-2012 | k=2.5,n=10 | +0.39 | +0.74 |
| 2014 | 2009-2013 | k=2.0,n=10 | +0.50 | +0.20 |
| 2015 | 2010-2014 | k=2.0,n=40 | +0.43 | +0.67 |
| 2016 | 2011-2015 | k=2.0,n=10 | +0.67 | +1.21 |
| 2017 | 2012-2016 | k=2.0,n=10 | +0.95 | -0.57 |
| 2018 | 2013-2017 | k=2.0,n=10 | +0.66 | -0.81 |
| 2019 | 2014-2018 | k=1.5,n=20 | +0.40 | -0.34 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +0.89.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| n +5 % | paramètre | +0.37 | oui |
| n −5 % | paramètre | +0.45 | oui |
| k +5 % | paramètre | +0.43 | oui |
| k −5 % | paramètre | +0.47 | oui |
| n +10 % | paramètre | +0.37 | oui |
| n −10 % | paramètre | +0.45 | oui |
| k +10 % | paramètre | +0.44 | oui |
| k −10 % | paramètre | +0.45 | oui |
| n +20 % | paramètre | +0.25 | oui |
| n −20 % | paramètre | +0.49 | oui |
| k +20 % | paramètre | +0.43 | oui |
| k −20 % | paramètre | +0.44 | oui |
| coûts × 1.25 | coûts | +0.45 | oui |
| coûts × 1.5 | coûts | +0.41 | oui |
| slippage + 2.0 bp | coûts | +0.41 | oui |
| entrée retardée d'1 barre | exécution | +0.32 | oui |
| sortie retardée d'1 barre | exécution | +0.44 | oui |
| signal bruité (5%) | signal | +0.44 | oui |
| sans les 5% meilleurs trades | dépendance | -0.20 | non |
| sans les 10% meilleurs trades | dépendance | -0.46 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -16.7%, 5e centile -26.9% ; CAGR médian 3.1% [1.2% ; 4.9%] ; P(perte) 0.4%. P(drawdown au-delà de) : 10% → 98.5%, 20% → 25.7%, 25% → 8.5%, 35% → 0.5%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 11 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.08. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +32.9 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 9.7%. Sharpe avec coûts × 1,5 : +0.41.

## 14. Drawdown
Recherche : max -14.8%, moyen -2.8%, plus long passage sous l'eau 688 jours. Walk-forward OOS : max -13.3%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.38 (19.7% des jours) ; bull Sharpe -0.06 (61.6% des jours) ; sideways Sharpe +1.45 (18.7% des jours)
- **volatility** : high_vol Sharpe +0.39 (29.8% des jours) ; low_vol Sharpe +0.50 (30.6% des jours) ; normal_vol Sharpe +0.27 (39.6% des jours)
- **crisis** : no_crisis Sharpe +0.36 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.40 (30.1% des jours) ; neutral Sharpe +0.35 (41.2% des jours) ; trending Sharpe +0.35 (28.7% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 60.9% ; PBO 0.08 ; ratio OOS/IS +0.68.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 140 trades / an sur la classe ; exposition moyenne 92.6% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Breakouts de volatilité, tendances fortes.

Observées sur l'OOS : direction = bull (Sharpe -0.06).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.36, robustness 0.90, oos_stability 0.78, drawdown 0.46, cost_sensitivity 0.83, parameter_stability 0.61, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.59
