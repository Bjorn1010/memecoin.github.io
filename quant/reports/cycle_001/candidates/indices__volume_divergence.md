# volume_divergence — indices
**Décision : PROMISING** — robustesse 55% (< 70%); Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 12% au Monte Carlo (> 10%)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un nouveau plus haut sur volume faible est suivi d'une baisse (divergence prix/volume).

*Pourquoi cela pourrait marcher :* Absence de participation = mouvement fragile.
## 2. Stratégie retail
Famille **volume**. Signal : clôture au plus haut N jours. Condition : volume < médiane 20 jours. Horizon : 3 à 10 jours. Cible mesurée : espérance nette > 0. Risque : volume faible en tendance saine.
## 3. Formulation mathématique
`short h jours si C_t = max N jours et V_t < médiane 20 j ; long symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::volume_divergence` — baseline `{'lookback': 20, 'hold': 5}`, candidat retenu par le walk-forward `{'lookback': 10, 'hold': 3}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | -0.17 | +0.18 |
| CAGR | -0.8% | 0.6% |
| volatilité | 4.1% | 4.0% |
| drawdown max | -25.5% | -11.6% |
| Sortino | -0.21 | +0.23 |
| Calmar | -0.03 | +0.06 |
| trades | 2148 | 3778 |
| taux de réussite | 51.7% | 53.7% |
| profit factor | 0.96 | 1.11 |
| espérance / trade | -0.4 bp | +0.8 bp |
| exposition | 79.2% | 80.2% |
| skew | +0.50 | +0.35 |
| kurtosis | 16.4 | 9.9 |
| CVaR 5 % | -0.6% | -0.6% |
| récupération max (jours) | 6294 | 1788 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.25 |
| CAGR | 1.0% |
| volatilité | 4.3% |
| drawdown max | -12.5% |
| Sortino | +0.37 |
| Calmar | +0.08 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +1.63 |
| kurtosis | 21.3 |
| CVaR 5 % | -0.6% |
| récupération max (jours) | 1514 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.25 ; années positives 56.5% ; stabilité des paramètres 52.2% ; baseline sans sélection sur les mêmes années -0.06 ; ratio OOS/IS +0.65.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | hold=3,lookback=10 | -0.05 | -0.37 |
| 1998 | 1994-1997 | hold=3,lookback=10 | -0.10 | +0.46 |
| 1999 | 1994-1998 | hold=3,lookback=10 | -0.03 | +1.14 |
| 2000 | 1995-1999 | hold=3,lookback=10 | +0.00 | +0.52 |
| 2001 | 1996-2000 | hold=5,lookback=10 | +0.01 | -0.10 |
| 2002 | 1997-2001 | hold=3,lookback=10 | +0.30 | +0.03 |
| 2003 | 1998-2002 | hold=3,lookback=10 | +0.40 | -0.59 |
| 2004 | 1999-2003 | hold=5,lookback=10 | +0.31 | -0.80 |
| 2005 | 2000-2004 | hold=5,lookback=10 | -0.01 | +0.01 |
| 2006 | 2001-2005 | hold=5,lookback=10 | -0.08 | +1.72 |
| 2007 | 2002-2006 | hold=5,lookback=10 | +0.29 | +1.60 |
| 2008 | 2003-2007 | hold=5,lookback=10 | +0.68 | +0.46 |
| 2009 | 2004-2008 | hold=3,lookback=10 | +0.78 | -0.16 |
| 2010 | 2005-2009 | hold=3,lookback=10 | +0.82 | -1.12 |
| 2011 | 2006-2010 | hold=3,lookback=10 | +0.62 | +1.06 |
| 2012 | 2007-2011 | hold=3,lookback=10 | +0.49 | +1.06 |
| 2013 | 2008-2012 | hold=3,lookback=10 | +0.36 | -1.24 |
| 2014 | 2009-2013 | hold=3,lookback=10 | -0.09 | -0.65 |
| 2015 | 2010-2014 | hold=3,lookback=20 | -0.16 | +0.11 |
| 2016 | 2011-2015 | hold=10,lookback=10 | +0.13 | +1.10 |
| 2017 | 2012-2016 | hold=5,lookback=10 | +0.19 | -0.87 |
| 2018 | 2013-2017 | hold=10,lookback=10 | +0.01 | +1.46 |
| 2019 | 2014-2018 | hold=10,lookback=10 | +0.71 | -1.18 |

## 9. Robustesse
Score 55.0% sur 20 perturbations ; ratio voisins/optimum +0.56.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.10 | oui |
| lookback −5 % | paramètre | +0.13 | oui |
| hold +5 % | paramètre | +0.20 | oui |
| hold −5 % | paramètre | -0.00 | non |
| lookback +10 % | paramètre | +0.10 | oui |
| lookback −10 % | paramètre | +0.13 | oui |
| hold +10 % | paramètre | +0.20 | oui |
| hold −10 % | paramètre | -0.00 | non |
| lookback +20 % | paramètre | +0.07 | non |
| lookback −20 % | paramètre | +0.11 | oui |
| hold +20 % | paramètre | +0.20 | oui |
| hold −20 % | paramètre | -0.00 | non |
| coûts × 1.25 | coûts | +0.13 | oui |
| coûts × 1.5 | coûts | +0.08 | non |
| slippage + 2.0 bp | coûts | +0.04 | non |
| entrée retardée d'1 barre | exécution | +0.04 | non |
| sortie retardée d'1 barre | exécution | +0.20 | oui |
| signal bruité (5%) | signal | +0.13 | oui |
| sans les 5% meilleurs trades | dépendance | -0.69 | non |
| sans les 10% meilleurs trades | dépendance | -1.07 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -16.2%, 5e centile -29.4% ; CAGR médian 0.6% [-0.6% ; 1.9%] ; P(perte) 20.2%. P(drawdown au-delà de) : 10% → 93.3%, 20% → 28.1%, 25% → 12.0%, 35% → 1.1%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 10 trades, 95e centile 13 ; P(perte) 8.4%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.04. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +11.0 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 27.8%. Sharpe avec coûts × 1,5 : +0.08.

## 14. Drawdown
Recherche : max -11.6%, moyen -4.2%, plus long passage sous l'eau 1788 jours. Walk-forward OOS : max -12.5%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.52 (40.5% des jours) ; bull Sharpe +0.38 (41.3% des jours) ; sideways Sharpe -0.73 (18.2% des jours)
- **volatility** : high_vol Sharpe +0.70 (27.2% des jours) ; low_vol Sharpe -0.14 (32.0% des jours) ; normal_vol Sharpe +0.12 (40.7% des jours)
- **crisis** : no_crisis Sharpe +0.25 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.27 (30.0% des jours) ; neutral Sharpe +0.51 (38.8% des jours) ; trending Sharpe +0.35 (31.2% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 52.2% ; PBO 0.04 ; ratio OOS/IS +0.65.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 140 trades / an sur la classe ; exposition moyenne 80.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Tendances régulières à volume décroissant.

Observées sur l'OOS : direction = sideways (Sharpe -0.73), volatility = low_vol (Sharpe -0.14), character = mean_reverting (Sharpe -0.27).

## 20. Décision de recherche
**PROMISING**. - robustesse 55% (< 70%) - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 12% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.25, robustness 0.55, oos_stability 0.57, drawdown 0.41, cost_sensitivity 0.46, parameter_stability 0.52, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.44
