# donchian — commodities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.58 (> 0.5)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Une clôture au-delà du plus haut (bas) des N derniers jours est suivie d'une continuation qui dépasse le coût d'un stop à 2 ATR.

*Pourquoi cela pourrait marcher :* Règles des Tortues : les grandes tendances paient les nombreuses petites pertes.
## 2. Stratégie retail
Famille **trend**. Signal : clôture > plus haut N jours (hors aujourd'hui). Condition : aucune. Horizon : jusqu'à la cassure inverse sur M jours ou le stop. Cible mesurée : espérance nette par trade > 0. Risque : faux breakouts, stop 2 ATR.
## 3. Formulation mathématique
`entrée long si C_t > max(H_{t−N..t−1}), sortie si C_t < min(L_{t−M..t−1}) ; symétrique ; stop 2·ATR14`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::donchian` — baseline `{'entry': 20, 'exit': 10, 'stop_atr': 2.0}`, candidat retenu par le walk-forward `{'entry': 55, 'exit': 20, 'stop_atr': 2.0}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| USO | 2006-04-10 | 20.48 | A | — |
| UNG | 2007-04-18 | 19.46 | A | — |
| DBA | 2007-01-05 | 19.74 | A | — |
| DBC | 2006-02-06 | 20.65 | A | — |
| DBB | 2007-01-05 | 19.74 | A | — |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.41 | +0.57 |
| CAGR | 2.1% | 3.0% |
| volatilité | 5.5% | 5.5% |
| drawdown max | -15.8% | -11.0% |
| Sortino | +0.58 | +0.75 |
| Calmar | +0.13 | +0.27 |
| trades | 535 | 238 |
| taux de réussite | 34.4% | 32.8% |
| profit factor | 1.31 | 1.77 |
| espérance / trade | +5.8 bp | +16.9 bp |
| exposition | 97.2% | 91.0% |
| skew | +0.13 | +0.16 |
| kurtosis | 3.7 | 7.1 |
| CVaR 5 % | -0.8% | -0.8% |
| récupération max (jours) | 1533 | 1452 |
| années | 13.9 | 13.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.27 |
| CAGR | 1.3% |
| volatilité | 5.1% |
| drawdown max | -11.0% |
| Sortino | +0.34 |
| Calmar | +0.11 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.16 |
| kurtosis | 8.0 |
| CVaR 5 % | -0.8% |
| récupération max (jours) | 1128 |
| années | 10.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.27 ; années positives 50.0% ; stabilité des paramètres 40.0% ; baseline sans sélection sur les mêmes années +0.14 ; ratio OOS/IS +0.08.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2010 | 2007-2009 | entry=55,exit=20,stop_atr=2.0 | +1.41 | -0.21 |
| 2011 | 2007-2010 | entry=55,exit=20,stop_atr=2.0 | +1.10 | -1.01 |
| 2012 | 2007-2011 | entry=55,exit=20,stop_atr=2.0 | +0.80 | +0.25 |
| 2013 | 2008-2012 | entry=55,exit=20,stop_atr=2.0 | +0.64 | -0.79 |
| 2014 | 2009-2013 | entry=100,exit=50,stop_atr=2.0 | +0.20 | +2.74 |
| 2015 | 2010-2014 | entry=100,exit=50,stop_atr=2.0 | +0.84 | +0.80 |
| 2016 | 2011-2015 | entry=100,exit=50,stop_atr=2.0 | +0.77 | -0.50 |
| 2017 | 2012-2016 | entry=55,exit=55,stop_atr=2.0 | +0.78 | +0.49 |
| 2018 | 2013-2017 | entry=55,exit=55,stop_atr=2.0 | +0.94 | +0.53 |
| 2019 | 2014-2018 | entry=55,exit=55,stop_atr=2.0 | +1.07 | -1.58 |

## 9. Robustesse
Score 92.3% sur 26 perturbations ; ratio voisins/optimum +1.02.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| entry +5 % | paramètre | +0.55 | oui |
| entry −5 % | paramètre | +0.58 | oui |
| exit +5 % | paramètre | +0.55 | oui |
| exit −5 % | paramètre | +0.63 | oui |
| stop_atr +5 % | paramètre | +0.59 | oui |
| stop_atr −5 % | paramètre | +0.58 | oui |
| entry +10 % | paramètre | +0.52 | oui |
| entry −10 % | paramètre | +0.60 | oui |
| exit +10 % | paramètre | +0.59 | oui |
| exit −10 % | paramètre | +0.63 | oui |
| stop_atr +10 % | paramètre | +0.57 | oui |
| stop_atr −10 % | paramètre | +0.56 | oui |
| entry +20 % | paramètre | +0.54 | oui |
| entry −20 % | paramètre | +0.60 | oui |
| exit +20 % | paramètre | +0.57 | oui |
| exit −20 % | paramètre | +0.66 | oui |
| stop_atr +20 % | paramètre | +0.53 | oui |
| stop_atr −20 % | paramètre | +0.58 | oui |
| coûts × 1.25 | coûts | +0.55 | oui |
| coûts × 1.5 | coûts | +0.53 | oui |
| slippage + 2.0 bp | coûts | +0.55 | oui |
| entrée retardée d'1 barre | exécution | +0.55 | oui |
| sortie retardée d'1 barre | exécution | +0.57 | oui |
| signal bruité (5%) | signal | +0.49 | oui |
| sans les 5% meilleurs trades | dépendance | -0.12 | non |
| sans les 10% meilleurs trades | dépendance | -0.27 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -11.5%, 5e centile -19.5% ; CAGR médian 2.9% [0.6% ; 5.7%] ; P(perte) 2.5%. P(drawdown au-delà de) : 10% → 71.6%, 20% → 4.4%, 25% → 0.5%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 9 trades, 95e centile 14 ; P(perte) 2.6%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.58. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.067 / 0.120 (meilleure : pairs).

## 12. Capacité
Edge net moyen +130.4 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 3.00 bp/côté (comm 0.5, demi-spread 1.5, slippage 1.0), portage 0.0% long / 2.0% short. Part des coûts dans le résultat brut : 4.1%. Sharpe avec coûts × 1,5 : +0.53.

## 14. Drawdown
Recherche : max -11.0%, moyen -5.0%, plus long passage sous l'eau 1452 jours. Walk-forward OOS : max -11.0%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.42 (51.9% des jours) ; bull Sharpe +0.48 (29.3% des jours) ; sideways Sharpe -0.47 (18.8% des jours)
- **volatility** : high_vol Sharpe +0.70 (24.8% des jours) ; low_vol Sharpe +0.05 (37.7% des jours) ; normal_vol Sharpe -0.05 (37.6% des jours)
- **crisis** : no_crisis Sharpe +0.27 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.15 (27.7% des jours) ; neutral Sharpe -0.03 (39.3% des jours) ; trending Sharpe +0.80 (32.9% des jours)

Dépendance détectée : character:trending. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 40.0% ; PBO 0.58 ; ratio OOS/IS +0.08.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 17 trades / an sur la classe ; exposition moyenne 91.0% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés en range, breakouts sans suivi, gaps contre la position.

Observées sur l'OOS : direction = sideways (Sharpe -0.47), volatility = normal_vol (Sharpe -0.05), character = mean_reverting (Sharpe -0.15), character = neutral (Sharpe -0.03).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.58 (> 0.5)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.27, robustness 0.92, oos_stability 0.50, drawdown 0.61, cost_sensitivity 0.93, parameter_stability 0.40, capacity 0.50, regime_diversity 0.60, statistical_confidence 0.00, composite 0.53
