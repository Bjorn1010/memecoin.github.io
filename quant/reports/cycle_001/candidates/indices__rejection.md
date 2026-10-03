# rejection — indices
**Décision : PROMISING** — robustesse 65% (< 70%); Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
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
`qt/lab/strategies.py::rejection` — baseline `{'wick': 0.5, 'lookback': 20, 'hold': 5}`, candidat retenu par le walk-forward `{'wick': 0.66, 'lookback': 20, 'hold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.06 | +0.15 |
| CAGR | 0.1% | 0.3% |
| volatilité | 3.6% | 2.2% |
| drawdown max | -22.2% | -7.7% |
| Sortino | +0.06 | +0.11 |
| Calmar | +0.01 | +0.04 |
| trades | 1618 | 696 |
| taux de réussite | 49.7% | 51.7% |
| profit factor | 1.08 | 1.20 |
| espérance / trade | +0.7 bp | +1.7 bp |
| exposition | 59.2% | 33.0% |
| skew | +0.54 | -1.55 |
| kurtosis | 49.7 | 110.7 |
| CVaR 5 % | -0.5% | -0.3% |
| récupération max (jours) | 5351 | 2895 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.06 |
| CAGR | 0.1% |
| volatilité | 2.6% |
| drawdown max | -13.1% |
| Sortino | +0.05 |
| Calmar | +0.01 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -1.37 |
| kurtosis | 65.0 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 4592 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.06 ; années positives 60.9% ; stabilité des paramètres 30.4% ; baseline sans sélection sur les mêmes années +0.17 ; ratio OOS/IS +0.37.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | hold=5,lookback=20,wick=0.66 | +0.33 | +0.49 |
| 1998 | 1994-1997 | hold=5,lookback=20,wick=0.66 | +0.35 | +0.12 |
| 1999 | 1994-1998 | hold=5,lookback=20,wick=0.66 | +0.31 | +0.57 |
| 2000 | 1995-1999 | hold=5,lookback=20,wick=0.66 | +0.17 | +0.03 |
| 2001 | 1996-2000 | hold=10,lookback=20,wick=0.66 | +0.30 | -1.66 |
| 2002 | 1997-2001 | hold=5,lookback=20,wick=0.5 | -0.13 | -1.49 |
| 2003 | 1998-2002 | hold=10,lookback=20,wick=0.66 | -0.25 | +0.22 |
| 2004 | 1999-2003 | hold=10,lookback=20,wick=0.66 | -0.11 | +0.22 |
| 2005 | 2000-2004 | hold=10,lookback=20,wick=0.66 | -0.17 | +1.88 |
| 2006 | 2001-2005 | hold=3,lookback=20,wick=0.66 | +0.06 | -0.33 |
| 2007 | 2002-2006 | hold=10,lookback=20,wick=0.66 | +0.52 | +1.34 |
| 2008 | 2003-2007 | hold=5,lookback=20,wick=0.66 | +0.90 | -0.61 |
| 2009 | 2004-2008 | hold=10,lookback=20,wick=0.66 | +0.50 | -0.22 |
| 2010 | 2005-2009 | hold=5,lookback=20,wick=0.66 | +0.58 | +0.78 |
| 2011 | 2006-2010 | hold=5,lookback=20,wick=0.66 | +0.53 | -0.38 |
| 2012 | 2007-2011 | hold=5,lookback=20,wick=0.5 | +0.36 | +0.20 |
| 2013 | 2008-2012 | hold=5,lookback=20,wick=0.5 | +0.24 | +0.36 |
| 2014 | 2009-2013 | hold=5,lookback=20,wick=0.5 | +0.42 | +0.87 |
| 2015 | 2010-2014 | hold=3,lookback=20,wick=0.5 | +0.38 | +1.54 |
| 2016 | 2011-2015 | hold=5,lookback=20,wick=0.5 | +0.54 | +0.65 |
| 2017 | 2012-2016 | hold=3,lookback=20,wick=0.5 | +1.13 | -1.01 |
| 2018 | 2013-2017 | hold=3,lookback=20,wick=0.5 | +0.83 | -0.03 |
| 2019 | 2014-2018 | hold=3,lookback=20,wick=0.66 | +1.03 | -0.27 |

## 9. Robustesse
Score 65.4% sur 26 perturbations ; ratio voisins/optimum +0.81.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| wick +5 % | paramètre | +0.20 | oui |
| wick −5 % | paramètre | -0.08 | non |
| lookback +5 % | paramètre | +0.11 | oui |
| lookback −5 % | paramètre | +0.16 | oui |
| hold +5 % | paramètre | +0.05 | non |
| hold −5 % | paramètre | +0.19 | oui |
| wick +10 % | paramètre | +0.26 | oui |
| wick −10 % | paramètre | +0.06 | non |
| lookback +10 % | paramètre | +0.11 | oui |
| lookback −10 % | paramètre | +0.13 | oui |
| hold +10 % | paramètre | +0.05 | non |
| hold −10 % | paramètre | +0.19 | oui |
| wick +20 % | paramètre | +0.24 | oui |
| wick −20 % | paramètre | +0.07 | non |
| lookback +20 % | paramètre | +0.10 | oui |
| lookback −20 % | paramètre | +0.13 | oui |
| hold +20 % | paramètre | +0.05 | non |
| hold −20 % | paramètre | +0.19 | oui |
| coûts × 1.25 | coûts | +0.13 | oui |
| coûts × 1.5 | coûts | +0.11 | oui |
| slippage + 2.0 bp | coûts | +0.10 | oui |
| entrée retardée d'1 barre | exécution | -0.02 | non |
| sortie retardée d'1 barre | exécution | +0.11 | oui |
| signal bruité (5%) | signal | +0.12 | oui |
| sans les 5% meilleurs trades | dépendance | -0.22 | non |
| sans les 10% meilleurs trades | dépendance | -0.37 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -8.6%, 5e centile -16.2% ; CAGR médian 0.3% [-0.3% ; 1.0%] ; P(perte) 19.9%. P(drawdown au-delà de) : 10% → 33.8%, 20% → 1.1%, 25% → 0.1%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 11 ; P(perte) 11.2%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.19. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +14.2 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 14.9%. Sharpe avec coûts × 1,5 : +0.11.

## 14. Drawdown
Recherche : max -7.7%, moyen -2.3%, plus long passage sous l'eau 2895 jours. Walk-forward OOS : max -13.1%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.13 (29.2% des jours) ; bull Sharpe -0.15 (54.1% des jours) ; sideways Sharpe +0.31 (16.7% des jours)
- **volatility** : high_vol Sharpe +0.21 (27.9% des jours) ; low_vol Sharpe -0.24 (30.4% des jours) ; normal_vol Sharpe +0.02 (41.7% des jours)
- **crisis** : no_crisis Sharpe +0.06 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.01 (33.9% des jours) ; neutral Sharpe +0.13 (36.6% des jours) ; trending Sharpe +0.06 (29.5% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 30.4% ; PBO 0.19 ; ratio OOS/IS +0.37.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 26 trades / an sur la classe ; exposition moyenne 33.0% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés en tendance où les mèches n'arrêtent rien.

Observées sur l'OOS : direction = bull (Sharpe -0.15), volatility = low_vol (Sharpe -0.24), character = mean_reverting (Sharpe -0.01).

## 20. Décision de recherche
**PROMISING**. - robustesse 65% (< 70%) - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.06, robustness 0.65, oos_stability 0.61, drawdown 0.68, cost_sensitivity 0.73, parameter_stability 0.30, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.47
