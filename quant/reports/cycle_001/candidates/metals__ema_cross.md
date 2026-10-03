# ema_cross — metals
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 64% au Monte Carlo (> 10%)
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
| GLD | 2004-11-18 | 21.87 | A | — |
| SLV | 2006-04-28 | 20.43 | A | — |
| PPLT | 2010-01-08 | 16.73 | A | — |
| CPER | 2011-11-15 | 14.88 | C | 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain); 6 séquences de ≥ 5 clôtures identiques |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.04 | +0.23 |
| CAGR | -0.1% | 1.8% |
| volatilité | 9.6% | 10.3% |
| drawdown max | -29.7% | -25.6% |
| Sortino | +0.04 | +0.27 |
| Calmar | -0.00 | +0.07 |
| trades | 424 | 71 |
| taux de réussite | 32.8% | 26.8% |
| profit factor | 1.11 | 1.99 |
| espérance / trade | +3.7 bp | +68.5 bp |
| exposition | 99.2% | 96.1% |
| skew | -1.55 | -0.92 |
| kurtosis | 39.8 | 26.2 |
| CVaR 5 % | -1.4% | -1.5% |
| récupération max (jours) | 1276 | 1064 |
| années | 15.1 | 15.1 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.00 |
| CAGR | -0.4% |
| volatilité | 8.7% |
| drawdown max | -21.0% |
| Sortino | +0.00 |
| Calmar | -0.02 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.93 |
| kurtosis | 33.5 |
| CVaR 5 % | -1.3% |
| récupération max (jours) | 2103 |
| années | 12.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.00 ; années positives 50.0% ; stabilité des paramètres 50.0% ; baseline sans sélection sur les mêmes années -0.01 ; ratio OOS/IS -0.05.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2008 | 2005-2007 | fast=50,slow=150 | +1.00 | -0.20 |
| 2009 | 2005-2008 | fast=50,slow=150 | +0.65 | +0.75 |
| 2010 | 2005-2009 | fast=50,slow=150 | +0.64 | +1.53 |
| 2011 | 2006-2010 | fast=50,slow=150 | +0.57 | +0.01 |
| 2012 | 2007-2011 | fast=50,slow=150 | +0.36 | -2.13 |
| 2013 | 2008-2012 | fast=12,slow=26 | +0.33 | +0.56 |
| 2014 | 2009-2013 | fast=50,slow=150 | +0.36 | -0.05 |
| 2015 | 2010-2014 | fast=5,slow=20 | +0.32 | -0.35 |
| 2016 | 2011-2015 | fast=5,slow=20 | +0.27 | +0.63 |
| 2017 | 2012-2016 | fast=5,slow=20 | +0.29 | -0.52 |
| 2018 | 2013-2017 | fast=5,slow=20 | +0.17 | +0.03 |
| 2019 | 2014-2018 | fast=5,slow=20 | +0.03 | -0.49 |

## 9. Robustesse
Score 85.0% sur 20 perturbations ; ratio voisins/optimum +0.98.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.25 | oui |
| fast −5 % | paramètre | +0.21 | oui |
| slow +5 % | paramètre | +0.24 | oui |
| slow −5 % | paramètre | +0.18 | oui |
| fast +10 % | paramètre | +0.30 | oui |
| fast −10 % | paramètre | +0.20 | oui |
| slow +10 % | paramètre | +0.23 | oui |
| slow −10 % | paramètre | +0.15 | oui |
| fast +20 % | paramètre | +0.29 | oui |
| fast −20 % | paramètre | +0.15 | oui |
| slow +20 % | paramètre | +0.24 | oui |
| slow −20 % | paramètre | +0.07 | non |
| coûts × 1.25 | coûts | +0.22 | oui |
| coûts × 1.5 | coûts | +0.21 | oui |
| slippage + 2.0 bp | coûts | +0.23 | oui |
| entrée retardée d'1 barre | exécution | +0.23 | oui |
| sortie retardée d'1 barre | exécution | +0.22 | oui |
| signal bruité (5%) | signal | +0.32 | oui |
| sans les 5% meilleurs trades | dépendance | -0.15 | non |
| sans les 10% meilleurs trades | dépendance | -0.25 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -27.9%, 5e centile -47.6% ; CAGR médian 1.8% [-2.3% ; 6.2%] ; P(perte) 23.1%. P(drawdown au-delà de) : 10% → 100.0%, 20% → 87.0%, 25% → 64.0%, 35% → 26.1%, 50% → 3.5%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 12 ; P(perte) 14.9%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.40. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.579 / 0.135 (meilleure : volume_spike).

## 12. Capacité
Edge net moyen +222.7 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 2.00 bp/côté (comm 0.5, demi-spread 1.0, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 1.1%. Sharpe avec coûts × 1,5 : +0.21.

## 14. Drawdown
Recherche : max -25.6%, moyen -11.0%, plus long passage sous l'eau 1064 jours. Walk-forward OOS : max -21.0%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.11 (44.0% des jours) ; bull Sharpe +0.14 (38.8% des jours) ; sideways Sharpe -0.57 (17.2% des jours)
- **volatility** : high_vol Sharpe +0.14 (28.6% des jours) ; low_vol Sharpe +0.33 (33.8% des jours) ; normal_vol Sharpe -0.34 (37.6% des jours)
- **crisis** : no_crisis Sharpe +0.00 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.36 (30.0% des jours) ; neutral Sharpe +1.07 (38.2% des jours) ; trending Sharpe -0.87 (31.8% des jours)

Dépendance détectée : character:neutral. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 50.0% ; PBO 0.40 ; ratio OOS/IS -0.05.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 5 trades / an sur la classe ; exposition moyenne 96.1% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Faible autocorrélation des rendements ; coûts qui mangent les signaux courts.

Observées sur l'OOS : direction = sideways (Sharpe -0.57), volatility = normal_vol (Sharpe -0.34), character = mean_reverting (Sharpe -0.36), character = trending (Sharpe -0.87).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 64% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.00, robustness 0.85, oos_stability 0.50, drawdown 0.05, cost_sensitivity 0.94, parameter_stability 0.50, capacity 0.50, regime_diversity 0.60, statistical_confidence 0.00, composite 0.44
