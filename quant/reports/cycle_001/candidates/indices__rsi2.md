# rsi2 — indices
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
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
`qt/lab/strategies.py::rsi2` — baseline `{'length': 2, 'threshold': 10}`, candidat retenu par le walk-forward `{'length': 3, 'threshold': 15}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.32 | +0.40 |
| CAGR | 1.6% | 1.8% |
| volatilité | 5.5% | 4.7% |
| drawdown max | -14.8% | -12.3% |
| Sortino | +0.39 | +0.45 |
| Calmar | +0.11 | +0.15 |
| trades | 4594 | 3290 |
| taux de réussite | 60.6% | 60.6% |
| profit factor | 1.21 | 1.30 |
| espérance / trade | +1.3 bp | +1.8 bp |
| exposition | 81.7% | 68.2% |
| skew | -0.08 | -0.00 |
| kurtosis | 17.1 | 25.9 |
| CVaR 5 % | -0.8% | -0.7% |
| récupération max (jours) | 1691 | 808 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.29 |
| CAGR | 1.1% |
| volatilité | 3.9% |
| drawdown max | -11.3% |
| Sortino | +0.28 |
| Calmar | +0.09 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.00 |
| kurtosis | 40.5 |
| CVaR 5 % | -0.6% |
| récupération max (jours) | 1387 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.29 ; années positives 65.2% ; stabilité des paramètres 26.1% ; baseline sans sélection sur les mêmes années +0.33 ; ratio OOS/IS +0.22.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | length=2,threshold=15 | +0.43 | +1.90 |
| 1998 | 1994-1997 | length=2,threshold=15 | +0.70 | +1.45 |
| 1999 | 1994-1998 | length=2,threshold=15 | +0.83 | +0.12 |
| 2000 | 1995-1999 | length=2,threshold=15 | +0.84 | +0.51 |
| 2001 | 1996-2000 | length=3,threshold=15 | +1.07 | +0.22 |
| 2002 | 1997-2001 | length=3,threshold=15 | +1.06 | +0.68 |
| 2003 | 1998-2002 | length=3,threshold=15 | +0.89 | +0.40 |
| 2004 | 1999-2003 | length=3,threshold=15 | +0.71 | -1.02 |
| 2005 | 2000-2004 | length=3,threshold=15 | +0.41 | +0.31 |
| 2006 | 2001-2005 | length=3,threshold=15 | +0.13 | +0.73 |
| 2007 | 2002-2006 | length=4,threshold=5 | +0.31 | -0.55 |
| 2008 | 2003-2007 | length=2,threshold=5 | +0.39 | +1.06 |
| 2009 | 2004-2008 | length=3,threshold=10 | +0.67 | -1.21 |
| 2010 | 2005-2009 | length=4,threshold=5 | +0.68 | -0.93 |
| 2011 | 2006-2010 | length=3,threshold=10 | +0.69 | +0.21 |
| 2012 | 2007-2011 | length=4,threshold=5 | +0.60 | +0.04 |
| 2013 | 2008-2012 | length=4,threshold=5 | +0.65 | -0.28 |
| 2014 | 2009-2013 | length=2,threshold=10 | +0.27 | -0.78 |
| 2015 | 2010-2014 | length=4,threshold=5 | +0.35 | +0.55 |
| 2016 | 2011-2015 | length=4,threshold=5 | +0.49 | +0.10 |
| 2017 | 2012-2016 | length=4,threshold=10 | +0.52 | -0.67 |
| 2018 | 2013-2017 | length=4,threshold=10 | +0.38 | -0.21 |
| 2019 | 2014-2018 | length=3,threshold=5 | +0.22 | +0.30 |

## 9. Robustesse
Score 75.0% sur 20 perturbations ; ratio voisins/optimum +0.75.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| length +5 % | paramètre | +0.17 | non |
| length −5 % | paramètre | +0.30 | oui |
| threshold +5 % | paramètre | +0.36 | oui |
| threshold −5 % | paramètre | +0.38 | oui |
| length +10 % | paramètre | +0.17 | non |
| length −10 % | paramètre | +0.30 | oui |
| threshold +10 % | paramètre | +0.36 | oui |
| threshold −10 % | paramètre | +0.38 | oui |
| length +20 % | paramètre | +0.17 | non |
| length −20 % | paramètre | +0.30 | oui |
| threshold +20 % | paramètre | +0.37 | oui |
| threshold −20 % | paramètre | +0.31 | oui |
| coûts × 1.25 | coûts | +0.37 | oui |
| coûts × 1.5 | coûts | +0.33 | oui |
| slippage + 2.0 bp | coûts | +0.30 | oui |
| entrée retardée d'1 barre | exécution | +0.27 | oui |
| sortie retardée d'1 barre | exécution | +0.40 | oui |
| signal bruité (5%) | signal | +0.37 | oui |
| sans les 5% meilleurs trades | dépendance | -0.24 | non |
| sans les 10% meilleurs trades | dépendance | -0.51 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -13.6%, 5e centile -22.1% ; CAGR médian 1.8% [0.4% ; 3.1%] ; P(perte) 1.4%. P(drawdown au-delà de) : 10% → 86.6%, 20% → 9.3%, 25% → 2.2%, 35% → 0.1%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 11 ; P(perte) 0.1%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.22. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +26.8 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 14.6%. Sharpe avec coûts × 1,5 : +0.33.

## 14. Drawdown
Recherche : max -12.3%, moyen -2.6%, plus long passage sous l'eau 808 jours. Walk-forward OOS : max -11.3%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.23 (23.4% des jours) ; bull Sharpe +0.30 (61.2% des jours) ; sideways Sharpe +0.34 (15.4% des jours)
- **volatility** : high_vol Sharpe +0.46 (29.4% des jours) ; low_vol Sharpe +0.59 (31.1% des jours) ; normal_vol Sharpe -0.06 (39.5% des jours)
- **crisis** : no_crisis Sharpe +0.29 (100.0% des jours)
- **character** : mean_reverting Sharpe +1.05 (29.6% des jours) ; neutral Sharpe -0.34 (40.3% des jours) ; trending Sharpe +0.32 (30.0% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 26.1% ; PBO 0.22 ; ratio OOS/IS +0.22.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 122 trades / an sur la classe ; exposition moyenne 68.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés en forte tendance ; crises où les excès s'étendent ; coûts élevés.

Observées sur l'OOS : volatility = normal_vol (Sharpe -0.06), character = neutral (Sharpe -0.34).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.29, robustness 0.75, oos_stability 0.65, drawdown 0.56, cost_sensitivity 0.81, parameter_stability 0.26, capacity 0.50, regime_diversity 0.80, statistical_confidence 0.00, composite 0.51
