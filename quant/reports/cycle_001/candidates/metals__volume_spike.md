# volume_spike — metals
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un volume relatif élevé avec une clôture dans le haut du range annonce une continuation.

*Pourquoi cela pourrait marcher :* Le volume confirme l'information.
## 2. Stratégie retail
Famille **volume**. Signal : volume / médiane 20 jours > k. Condition : clôture dans le quart haut (bas) du range. Horizon : 1 à 10 jours. Cible mesurée : espérance nette > 0. Risque : pics de volume de capitulation (retournement).
## 3. Formulation mathématique
`long h jours si V_t / médiane(V)_{20} > k et C_t dans le quart haut du range ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::volume_spike` — baseline `{'k': 2.0, 'hold': 5}`, candidat retenu par le walk-forward `{'k': 1.5, 'hold': 1}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.66 | +0.92 |
| CAGR | 2.5% | 2.5% |
| volatilité | 3.9% | 2.8% |
| drawdown max | -7.2% | -8.1% |
| Sortino | +0.64 | +0.85 |
| Calmar | +0.35 | +0.31 |
| trades | 593 | 1302 |
| taux de réussite | 51.4% | 50.6% |
| profit factor | 1.47 | 1.42 |
| espérance / trade | +6.6 bp | +3.0 bp |
| exposition | 51.2% | 30.1% |
| skew | -0.11 | +0.39 |
| kurtosis | 34.8 | 19.8 |
| CVaR 5 % | -0.6% | -0.4% |
| récupération max (jours) | 901 | 884 |
| années | 15.1 | 15.1 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.68 |
| CAGR | 2.6% |
| volatilité | 3.9% |
| drawdown max | -8.6% |
| Sortino | +0.74 |
| Calmar | +0.31 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.04 |
| kurtosis | 10.8 |
| CVaR 5 % | -0.6% |
| récupération max (jours) | 655 |
| années | 12.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.68 ; années positives 50.0% ; stabilité des paramètres 33.3% ; baseline sans sélection sur les mêmes années +0.42 ; ratio OOS/IS +0.47.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2008 | 2005-2007 | hold=5,k=1.5 | +2.00 | +1.47 |
| 2009 | 2005-2008 | hold=5,k=1.5 | +1.87 | -0.24 |
| 2010 | 2005-2009 | hold=5,k=1.5 | +1.53 | +0.68 |
| 2011 | 2006-2010 | hold=1,k=1.5 | +1.12 | +1.23 |
| 2012 | 2007-2011 | hold=1,k=1.5 | +1.29 | -0.15 |
| 2013 | 2008-2012 | hold=1,k=1.5 | +0.83 | -0.02 |
| 2014 | 2009-2013 | hold=1,k=1.5 | +0.55 | -1.90 |
| 2015 | 2010-2014 | hold=10,k=1.5 | +0.20 | +1.67 |
| 2016 | 2011-2015 | hold=10,k=1.5 | +0.29 | +1.97 |
| 2017 | 2012-2016 | hold=5,k=3.0 | +0.91 | -0.31 |
| 2018 | 2013-2017 | hold=5,k=2.0 | +0.62 | +1.69 |
| 2019 | 2014-2018 | hold=5,k=3.0 | +1.13 | -0.29 |

## 9. Robustesse
Score 82.4% sur 17 perturbations ; ratio voisins/optimum +0.94.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| k +5 % | paramètre | +0.86 | oui |
| k −5 % | paramètre | +0.87 | oui |
| hold +5 % | paramètre | +0.86 | oui |
| k +10 % | paramètre | +0.83 | oui |
| k −10 % | paramètre | +0.85 | oui |
| hold +10 % | paramètre | +0.86 | oui |
| k +20 % | paramètre | +0.66 | oui |
| k −20 % | paramètre | +0.75 | oui |
| hold +20 % | paramètre | +0.86 | oui |
| coûts × 1.25 | coûts | +0.86 | oui |
| coûts × 1.5 | coûts | +0.81 | oui |
| slippage + 2.0 bp | coûts | +0.71 | oui |
| entrée retardée d'1 barre | exécution | +0.10 | non |
| sortie retardée d'1 barre | exécution | +0.75 | oui |
| signal bruité (5%) | signal | +0.74 | oui |
| sans les 5% meilleurs trades | dépendance | -0.29 | non |
| sans les 10% meilleurs trades | dépendance | -0.79 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -4.5%, 5e centile -7.4% ; CAGR médian 2.5% [1.5% ; 3.7%] ; P(perte) 0.0%. P(drawdown au-delà de) : 10% → 0.5%, 20% → 0.0%, 25% → 0.0%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 9 trades, 95e centile 12 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.25. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.579 / 0.135 (meilleure : volume_spike).

## 12. Capacité
Edge net moyen +19.7 bp par trade. Moitié de l'edge perdue en impact vers 1,000,000 $, edge nul vers 5,000,000 $ (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 2.00 bp/côté (comm 0.5, demi-spread 1.0, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 18.6%. Sharpe avec coûts × 1,5 : +0.81.

## 14. Drawdown
Recherche : max -8.1%, moyen -1.7%, plus long passage sous l'eau 884 jours. Walk-forward OOS : max -8.6%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.12 (19.7% des jours) ; bull Sharpe +0.82 (61.4% des jours) ; sideways Sharpe +0.66 (18.9% des jours)
- **volatility** : high_vol Sharpe -0.34 (28.5% des jours) ; low_vol Sharpe +0.71 (27.8% des jours) ; normal_vol Sharpe +1.63 (43.6% des jours)
- **crisis** : no_crisis Sharpe +0.68 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.73 (38.4% des jours) ; neutral Sharpe +0.79 (36.8% des jours) ; trending Sharpe +0.46 (24.7% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 33.3% ; PBO 0.25 ; ratio OOS/IS +0.47.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 86 trades / an sur la classe ; exposition moyenne 30.1% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 1.81 | 0.9% | 4.3% | 0.4% | 94.4% | 46 |
| 10.0% | × 3.62 | 5.8% | 27.5% | 7.7% | 59.0% | 42 |
| 15.0% | × 5.43 | 12.7% | 47.1% | 10.1% | 30.1% | 38 |
| 20.0% | × 7.24 | 14.7% | 65.6% | 6.3% | 13.4% | 31 |
| 30.0% | × 10.86 | 14.1% | 78.4% | 5.0% | 2.5% | 21 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 1.81 | 19.6% | 5.7% | 0.1% | 74.6% | 172 |
| 10.0% | × 3.62 | 46.9% | 19.3% | 4.4% | 29.4% | 119 |
| 15.0% | × 5.43 | 47.7% | 38.2% | 8.1% | 6.0% | 76 |
| 20.0% | × 7.24 | 43.9% | 47.2% | 8.2% | 0.7% | 52 |
| 30.0% | × 10.86 | 35.2% | 59.8% | 4.9% | 0.1% | 31 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 1.81 | 42.0% | 0.0% | 35.3% | 22.7% | 130 |
| 10.0% | × 3.62 | 43.3% | 0.0% | 56.3% | 0.4% | 58 |
| 15.0% | × 5.43 | 37.5% | 0.0% | 62.5% | 0.0% | 31 |
| 20.0% | × 7.24 | 36.1% | 0.0% | 63.9% | 0.0% | 24 |
| 30.0% | × 10.86 | 33.4% | 0.0% | 66.6% | 0.0% | 14 |

## 19. Conditions d'échec
Attendues a priori : Volumes de fin de mois, de rebalancement d'indice, d'échéance.

Observées sur l'OOS : volatility = high_vol (Sharpe -0.34).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.68, robustness 0.82, oos_stability 0.50, drawdown 0.85, cost_sensitivity 0.88, parameter_stability 0.33, capacity 0.86, regime_diversity 0.90, statistical_confidence 0.00, composite 0.65
