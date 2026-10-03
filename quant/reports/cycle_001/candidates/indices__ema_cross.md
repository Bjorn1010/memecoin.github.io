# ema_cross — indices
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 44% au Monte Carlo (> 10%)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Le croisement EMA rapide/lente prédit le signe du rendement futur au-delà des coûts.

*Pourquoi cela pourrait marcher :* Même mécanisme que le croisement SMA, réaction plus rapide.
## 2. Stratégie retail
Famille **trend**. Signal : EMA(fast) − EMA(slow). Condition : aucune. Horizon : jusqu'au croisement inverse. Cible mesurée : rendement net > 0. Risque : whipsaws, turnover élevé sur les petites périodes.
## 3. Formulation mathématique
`pos_t = sign(EMA_f(C)_t − EMA_s(C)_t)`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::ema_cross` — baseline `{'fast': 12, 'slow': 26}`, candidat retenu par le walk-forward `{'fast': 50, 'slow': 150}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | -0.12 | +0.31 |
| CAGR | -1.3% | 2.2% |
| volatilité | 8.5% | 8.3% |
| drawdown max | -44.2% | -27.2% |
| Sortino | -0.15 | +0.38 |
| Calmar | -0.03 | +0.08 |
| trades | 1523 | 246 |
| taux de réussite | 30.7% | 35.0% |
| profit factor | 1.07 | 3.86 |
| espérance / trade | +1.1 bp | +84.5 bp |
| exposition | 99.5% | 97.8% |
| skew | -0.51 | -0.59 |
| kurtosis | 13.0 | 13.2 |
| CVaR 5 % | -1.3% | -1.3% |
| récupération max (jours) | 2836 | 2723 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.12 |
| CAGR | 0.6% |
| volatilité | 8.3% |
| drawdown max | -37.3% |
| Sortino | +0.14 |
| Calmar | +0.02 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.60 |
| kurtosis | 14.4 |
| CVaR 5 % | -1.3% |
| récupération max (jours) | 2723 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.12 ; années positives 52.2% ; stabilité des paramètres 69.6% ; baseline sans sélection sur les mêmes années -0.17 ; ratio OOS/IS +0.23.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | fast=50,slow=150 | +1.21 | +1.30 |
| 1998 | 1994-1997 | fast=50,slow=150 | +1.23 | -0.29 |
| 1999 | 1994-1998 | fast=50,slow=150 | +0.93 | +1.66 |
| 2000 | 1995-1999 | fast=50,slow=150 | +1.43 | -0.93 |
| 2001 | 1996-2000 | fast=50,slow=150 | +0.60 | +0.20 |
| 2002 | 1997-2001 | fast=50,slow=150 | +0.32 | +0.34 |
| 2003 | 1998-2002 | fast=50,slow=150 | +0.07 | +0.98 |
| 2004 | 1999-2003 | fast=50,slow=150 | +0.34 | +0.52 |
| 2005 | 2000-2004 | fast=50,slow=150 | +0.24 | -0.14 |
| 2006 | 2001-2005 | fast=50,slow=150 | +0.37 | +1.00 |
| 2007 | 2002-2006 | fast=50,slow=150 | +0.52 | +0.61 |
| 2008 | 2003-2007 | fast=50,slow=150 | +0.62 | +0.34 |
| 2009 | 2004-2008 | fast=50,slow=150 | +0.39 | +0.10 |
| 2010 | 2005-2009 | fast=50,slow=150 | +0.32 | -0.68 |
| 2011 | 2006-2010 | fast=50,slow=150 | +0.28 | -0.62 |
| 2012 | 2007-2011 | fast=50,slow=150 | +0.07 | -0.97 |
| 2013 | 2008-2012 | fast=8,slow=21 | +0.23 | -0.00 |
| 2014 | 2009-2013 | fast=20,slow=50 | +0.00 | -1.34 |
| 2015 | 2010-2014 | fast=30,slow=100 | -0.13 | -0.78 |
| 2016 | 2011-2015 | fast=30,slow=100 | -0.16 | -0.67 |
| 2017 | 2012-2016 | fast=30,slow=100 | -0.09 | +2.57 |
| 2018 | 2013-2017 | fast=30,slow=100 | +0.43 | +0.56 |
| 2019 | 2014-2018 | fast=30,slow=100 | +0.13 | -1.56 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +0.98.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.31 | oui |
| fast −5 % | paramètre | +0.31 | oui |
| slow +5 % | paramètre | +0.31 | oui |
| slow −5 % | paramètre | +0.31 | oui |
| fast +10 % | paramètre | +0.30 | oui |
| fast −10 % | paramètre | +0.29 | oui |
| slow +10 % | paramètre | +0.27 | oui |
| slow −10 % | paramètre | +0.30 | oui |
| fast +20 % | paramètre | +0.31 | oui |
| fast −20 % | paramètre | +0.27 | oui |
| slow +20 % | paramètre | +0.23 | oui |
| slow −20 % | paramètre | +0.34 | oui |
| coûts × 1.25 | coûts | +0.27 | oui |
| coûts × 1.5 | coûts | +0.23 | oui |
| slippage + 2.0 bp | coûts | +0.31 | oui |
| entrée retardée d'1 barre | exécution | +0.31 | oui |
| sortie retardée d'1 barre | exécution | +0.32 | oui |
| signal bruité (5%) | signal | +0.42 | oui |
| sans les 5% meilleurs trades | dépendance | -0.17 | non |
| sans les 10% meilleurs trades | dépendance | -0.20 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -23.9%, 5e centile -39.3% ; CAGR médian 2.2% [-0.1% ; 4.7%] ; P(perte) 5.7%. P(drawdown au-delà de) : 10% → 100.0%, 20% → 74.8%, 25% → 43.5%, 35% → 11.2%, 50% → 0.5%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 10 ; P(perte) 6.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.00. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +455.5 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 0.3%. Sharpe avec coûts × 1,5 : +0.23.

## 14. Drawdown
Recherche : max -27.2%, moyen -12.0%, plus long passage sous l'eau 2723 jours. Walk-forward OOS : max -37.3%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.09 (35.5% des jours) ; bull Sharpe -0.07 (44.3% des jours) ; sideways Sharpe +0.64 (20.2% des jours)
- **volatility** : high_vol Sharpe -0.14 (28.3% des jours) ; low_vol Sharpe +0.37 (31.9% des jours) ; normal_vol Sharpe +0.34 (39.8% des jours)
- **crisis** : no_crisis Sharpe +0.12 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.09 (30.4% des jours) ; neutral Sharpe +0.40 (39.9% des jours) ; trending Sharpe -0.23 (29.6% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 69.6% ; PBO 0.00 ; ratio OOS/IS +0.23.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 9 trades / an sur la classe ; exposition moyenne 97.8% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Faible autocorrélation des rendements ; coûts qui mangent les signaux courts.

Observées sur l'OOS : direction = bull (Sharpe -0.07), volatility = high_vol (Sharpe -0.14), character = trending (Sharpe -0.23).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 44% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.12, robustness 0.90, oos_stability 0.52, drawdown 0.21, cost_sensitivity 0.74, parameter_stability 0.70, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.49
