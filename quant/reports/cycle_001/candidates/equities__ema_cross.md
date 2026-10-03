# ema_cross — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 27% au Monte Carlo (> 10%)
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
| Sharpe | -0.12 | +0.25 |
| CAGR | -1.1% | 1.5% |
| volatilité | 7.1% | 7.0% |
| drawdown max | -25.6% | -17.3% |
| Sortino | -0.16 | +0.30 |
| Calmar | -0.04 | +0.09 |
| trades | 1619 | 250 |
| taux de réussite | 30.5% | 33.2% |
| profit factor | 0.94 | 1.79 |
| espérance / trade | -0.7 bp | +20.2 bp |
| exposition | 99.4% | 97.2% |
| skew | -0.30 | -0.50 |
| kurtosis | 12.2 | 16.9 |
| CVaR 5 % | -1.1% | -1.1% |
| récupération max (jours) | 5194 | 1678 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.22 |
| CAGR | 1.3% |
| volatilité | 7.2% |
| drawdown max | -17.3% |
| Sortino | +0.26 |
| Calmar | +0.08 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.44 |
| kurtosis | 17.5 |
| CVaR 5 % | -1.1% |
| récupération max (jours) | 2210 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.22 ; années positives 58.8% ; stabilité des paramètres 70.6% ; baseline sans sélection sur les mêmes années -0.04 ; ratio OOS/IS +0.90.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | fast=8,slow=21 | -0.36 | +0.65 |
| 2004 | 2000-2003 | fast=8,slow=21 | -0.13 | +0.11 |
| 2005 | 2000-2004 | fast=30,slow=100 | -0.06 | -0.96 |
| 2006 | 2001-2005 | fast=8,slow=21 | +0.03 | -0.34 |
| 2007 | 2002-2006 | fast=50,slow=150 | +0.47 | +1.13 |
| 2008 | 2003-2007 | fast=50,slow=150 | +0.80 | +0.17 |
| 2009 | 2004-2008 | fast=50,slow=150 | +0.50 | +0.00 |
| 2010 | 2005-2009 | fast=50,slow=150 | +0.36 | +0.01 |
| 2011 | 2006-2010 | fast=50,slow=150 | +0.34 | -0.24 |
| 2012 | 2007-2011 | fast=50,slow=150 | +0.19 | -0.09 |
| 2013 | 2008-2012 | fast=12,slow=26 | +0.02 | +0.97 |
| 2014 | 2009-2013 | fast=50,slow=150 | +0.27 | +1.47 |
| 2015 | 2010-2014 | fast=50,slow=150 | +0.66 | -0.79 |
| 2016 | 2011-2015 | fast=50,slow=150 | +0.52 | -0.08 |
| 2017 | 2012-2016 | fast=50,slow=150 | +0.58 | +2.59 |
| 2018 | 2013-2017 | fast=50,slow=150 | +0.97 | -0.16 |
| 2019 | 2014-2018 | fast=50,slow=150 | +0.40 | +0.58 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +1.05.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.26 | oui |
| fast −5 % | paramètre | +0.25 | oui |
| slow +5 % | paramètre | +0.26 | oui |
| slow −5 % | paramètre | +0.26 | oui |
| fast +10 % | paramètre | +0.28 | oui |
| fast −10 % | paramètre | +0.26 | oui |
| slow +10 % | paramètre | +0.27 | oui |
| slow −10 % | paramètre | +0.27 | oui |
| fast +20 % | paramètre | +0.29 | oui |
| fast −20 % | paramètre | +0.28 | oui |
| slow +20 % | paramètre | +0.31 | oui |
| slow −20 % | paramètre | +0.22 | oui |
| coûts × 1.25 | coûts | +0.25 | oui |
| coûts × 1.5 | coûts | +0.24 | oui |
| slippage + 2.0 bp | coûts | +0.25 | oui |
| entrée retardée d'1 barre | exécution | +0.28 | oui |
| sortie retardée d'1 barre | exécution | +0.29 | oui |
| signal bruité (5%) | signal | +0.47 | oui |
| sans les 5% meilleurs trades | dépendance | -0.14 | non |
| sans les 10% meilleurs trades | dépendance | -0.27 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -20.4%, 5e centile -35.2% ; CAGR médian 1.5% [-0.7% ; 3.7%] ; P(perte) 12.1%. P(drawdown au-delà de) : 10% → 99.5%, 20% → 52.4%, 25% → 26.9%, 35% → 5.2%, 50% → 0.1%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 9 trades, 95e centile 14 ; P(perte) 1.4%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.00. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +360.9 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 0.9%. Sharpe avec coûts × 1,5 : +0.24.

## 14. Drawdown
Recherche : max -17.3%, moyen -7.4%, plus long passage sous l'eau 1678 jours. Walk-forward OOS : max -17.3%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.98 (25.4% des jours) ; bull Sharpe -0.00 (56.3% des jours) ; sideways Sharpe +0.15 (18.3% des jours)
- **volatility** : high_vol Sharpe -0.11 (29.7% des jours) ; low_vol Sharpe +0.34 (29.7% des jours) ; normal_vol Sharpe +0.70 (40.5% des jours)
- **crisis** : no_crisis Sharpe +0.22 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.68 (29.2% des jours) ; neutral Sharpe +0.20 (39.4% des jours) ; trending Sharpe -0.16 (31.4% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 70.6% ; PBO 0.00 ; ratio OOS/IS +0.90.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 12 trades / an sur la classe ; exposition moyenne 97.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Faible autocorrélation des rendements ; coûts qui mangent les signaux courts.

Observées sur l'OOS : direction = bull (Sharpe -0.00), volatility = high_vol (Sharpe -0.11), character = trending (Sharpe -0.16).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 27% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.22, robustness 0.90, oos_stability 0.59, drawdown 0.30, cost_sensitivity 0.96, parameter_stability 0.71, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.54
