# rejection — metals
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Une longue mèche de rejet au plus bas de 20 jours est suivie d'une hausse.

*Pourquoi cela pourrait marcher :* Rejet d'un niveau par les acheteurs (pin bar).
## 2. Stratégie retail
Famille **price_action**. Signal : mèche ≥ w × range. Condition : au plus bas/haut de 20 jours. Horizon : 3 à 10 jours. Cible mesurée : espérance nette > 0. Risque : pattern fréquent et bruité.
## 3. Formulation mathématique
`long h jours si mèche basse ≥ w·R_t au plus bas 20 j ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::rejection` — baseline `{'wick': 0.5, 'lookback': 20, 'hold': 5}`, candidat retenu par le walk-forward `{'wick': 0.5, 'lookback': 20, 'hold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.40 | +0.40 |
| CAGR | 1.3% | 1.3% |
| volatilité | 3.4% | 3.4% |
| drawdown max | -10.8% | -10.8% |
| Sortino | +0.38 | +0.38 |
| Calmar | +0.12 | +0.12 |
| trades | 383 | 383 |
| taux de réussite | 53.3% | 53.3% |
| profit factor | 1.30 | 1.30 |
| espérance / trade | +5.5 bp | +5.5 bp |
| exposition | 41.5% | 41.5% |
| skew | +1.13 | +1.13 |
| kurtosis | 25.9 | 25.9 |
| CVaR 5 % | -0.5% | -0.5% |
| récupération max (jours) | 2178 | 2178 |
| années | 15.1 | 15.1 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.39 |
| CAGR | 1.2% |
| volatilité | 3.1% |
| drawdown max | -9.8% |
| Sortino | +0.38 |
| Calmar | +0.12 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.97 |
| kurtosis | 24.3 |
| CVaR 5 % | -0.5% |
| récupération max (jours) | 1706 |
| années | 12.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.39 ; années positives 58.3% ; stabilité des paramètres 33.3% ; baseline sans sélection sur les mêmes années +0.30 ; ratio OOS/IS +0.41.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2008 | 2005-2007 | hold=5,lookback=20,wick=0.5 | +0.66 | +0.65 |
| 2009 | 2005-2008 | hold=5,lookback=20,wick=0.5 | +0.66 | +1.52 |
| 2010 | 2005-2009 | hold=5,lookback=20,wick=0.5 | +0.80 | +0.81 |
| 2011 | 2006-2010 | hold=5,lookback=20,wick=0.5 | +0.84 | +0.01 |
| 2012 | 2007-2011 | hold=3,lookback=20,wick=0.5 | +0.95 | -1.54 |
| 2013 | 2008-2012 | hold=3,lookback=20,wick=0.5 | +0.68 | -0.71 |
| 2014 | 2009-2013 | hold=3,lookback=20,wick=0.5 | +0.37 | -0.33 |
| 2015 | 2010-2014 | hold=10,lookback=20,wick=0.66 | +0.14 | -0.57 |
| 2016 | 2011-2015 | hold=10,lookback=20,wick=0.66 | +0.16 | +1.65 |
| 2017 | 2012-2016 | hold=10,lookback=20,wick=0.5 | +0.12 | +1.27 |
| 2018 | 2013-2017 | hold=10,lookback=20,wick=0.5 | +0.69 | -0.16 |
| 2019 | 2014-2018 | hold=10,lookback=20,wick=0.5 | +0.66 | +0.14 |

## 9. Robustesse
Score 88.5% sur 26 perturbations ; ratio voisins/optimum +0.92.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| wick +5 % | paramètre | +0.33 | oui |
| wick −5 % | paramètre | +0.40 | oui |
| lookback +5 % | paramètre | +0.46 | oui |
| lookback −5 % | paramètre | +0.31 | oui |
| hold +5 % | paramètre | +0.30 | oui |
| hold −5 % | paramètre | +0.45 | oui |
| wick +10 % | paramètre | +0.29 | oui |
| wick −10 % | paramètre | +0.50 | oui |
| lookback +10 % | paramètre | +0.48 | oui |
| lookback −10 % | paramètre | +0.30 | oui |
| hold +10 % | paramètre | +0.30 | oui |
| hold −10 % | paramètre | +0.45 | oui |
| wick +20 % | paramètre | +0.09 | non |
| wick −20 % | paramètre | +0.43 | oui |
| lookback +20 % | paramètre | +0.48 | oui |
| lookback −20 % | paramètre | +0.29 | oui |
| hold +20 % | paramètre | +0.30 | oui |
| hold −20 % | paramètre | +0.45 | oui |
| coûts × 1.25 | coûts | +0.38 | oui |
| coûts × 1.5 | coûts | +0.36 | oui |
| slippage + 2.0 bp | coûts | +0.34 | oui |
| entrée retardée d'1 barre | exécution | +0.24 | oui |
| sortie retardée d'1 barre | exécution | +0.34 | oui |
| signal bruité (5%) | signal | +0.33 | oui |
| sans les 5% meilleurs trades | dépendance | -0.22 | non |
| sans les 10% meilleurs trades | dépendance | -0.45 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -8.8%, 5e centile -15.6% ; CAGR médian 1.3% [-0.0% ; 2.9%] ; P(perte) 5.7%. P(drawdown au-delà de) : 10% → 35.0%, 20% → 0.7%, 25% → 0.1%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 10 ; P(perte) 6.9%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.14. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.579 / 0.135 (meilleure : volume_spike).

## 12. Capacité
Edge net moyen +32.3 bp par trade. Moitié de l'edge perdue en impact vers 5,000,000 $, edge nul vers 10,000,000 $ (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 2.00 bp/côté (comm 0.5, demi-spread 1.0, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 11.6%. Sharpe avec coûts × 1,5 : +0.36.

## 14. Drawdown
Recherche : max -10.8%, moyen -4.3%, plus long passage sous l'eau 2178 jours. Walk-forward OOS : max -9.8%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.52 (26.4% des jours) ; bull Sharpe +0.23 (53.2% des jours) ; sideways Sharpe +0.68 (20.4% des jours)
- **volatility** : high_vol Sharpe +1.08 (27.1% des jours) ; low_vol Sharpe +0.17 (31.0% des jours) ; normal_vol Sharpe -0.10 (41.8% des jours)
- **crisis** : no_crisis Sharpe +0.39 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.33 (32.8% des jours) ; neutral Sharpe +0.11 (41.1% des jours) ; trending Sharpe +0.99 (26.1% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 33.3% ; PBO 0.14 ; ratio OOS/IS +0.41.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 25 trades / an sur la classe ; exposition moyenne 41.5% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)

**template_1step_trailing_intraday/one_step_25k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 1.45 | 0.3% | 1.9% | 2.7% | 95.1% | 49 |
| 10.0% | × 2.91 | 5.3% | 23.9% | 7.8% | 63.0% | 38 |
| 15.0% | × 4.36 | 8.0% | 42.3% | 11.4% | 38.3% | 34 |
| 20.0% | × 5.81 | 9.6% | 62.5% | 8.7% | 19.2% | 30 |
| 30.0% | × 8.72 | 14.3% | 74.8% | 6.1% | 4.8% | 23 |

**template_2step_static/challenge_100k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 1.45 | 9.8% | 0.0% | 1.5% | 88.7% | 166 |
| 10.0% | × 2.91 | 31.5% | 17.7% | 14.1% | 36.7% | 127 |
| 15.0% | × 4.36 | 37.3% | 39.1% | 14.9% | 8.7% | 92 |
| 20.0% | × 5.81 | 36.8% | 48.4% | 13.1% | 1.7% | 69 |
| 30.0% | × 8.72 | 32.6% | 60.9% | 6.5% | 0.0% | 36 |

**template_futures_trailing_eod/eval_50k** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :

| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |
|---|---|---|---|---|---|---|
| 5.0% | × 1.45 | 23.7% | 0.0% | 53.2% | 23.1% | 131 |
| 10.0% | × 2.91 | 31.9% | 0.0% | 67.7% | 0.4% | 72 |
| 15.0% | × 4.36 | 30.7% | 0.0% | 69.3% | 0.0% | 38 |
| 20.0% | × 5.81 | 31.0% | 0.0% | 69.0% | 0.0% | 27 |
| 30.0% | × 8.72 | 32.1% | 0.0% | 67.9% | 0.0% | 16 |

## 19. Conditions d'échec
Attendues a priori : Marchés en tendance où les mèches n'arrêtent rien.

Observées sur l'OOS : volatility = normal_vol (Sharpe -0.10).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.39, robustness 0.88, oos_stability 0.58, drawdown 0.69, cost_sensitivity 0.91, parameter_stability 0.33, capacity 0.96, regime_diversity 0.90, statistical_confidence 0.00, composite 0.63
