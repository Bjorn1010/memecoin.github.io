# liquidity_sweep — equities
**Décision : PROMISING** — robustesse 65% (< 70%); Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un passage sous le plus bas de N jours suivi d'une clôture au-dessus (balayage de liquidité) est suivi d'une hausse.

*Pourquoi cela pourrait marcher :* Turtle soup : les stops sous un niveau visible sont déclenchés puis le prix revient.
## 2. Stratégie retail
Famille **price_action**. Signal : plus bas < plus bas N jours ET clôture > ce niveau. Condition : aucune. Horizon : 3 à 10 jours. Cible mesurée : espérance nette > 0. Risque : le balayage qui devient une vraie cassure.
## 3. Formulation mathématique
`long h jours si L_t < min(L_{t−N..t−1}) et C_t > ce minimum ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::liquidity_sweep` — baseline `{'lookback': 20, 'hold': 5}`, candidat retenu par le walk-forward `{'lookback': 10, 'hold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.10 | +0.19 |
| CAGR | 0.3% | 0.8% |
| volatilité | 4.2% | 4.7% |
| drawdown max | -10.1% | -13.8% |
| Sortino | +0.13 | +0.25 |
| Calmar | +0.03 | +0.06 |
| trades | 2863 | 4034 |
| taux de réussite | 54.3% | 55.4% |
| profit factor | 1.06 | 1.08 |
| espérance / trade | +0.4 bp | +0.6 bp |
| exposition | 94.6% | 98.7% |
| skew | -0.15 | -0.37 |
| kurtosis | 17.5 | 14.2 |
| CVaR 5 % | -0.6% | -0.7% |
| récupération max (jours) | 2346 | 2549 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.10 |
| CAGR | 0.4% |
| volatilité | 4.6% |
| drawdown max | -14.2% |
| Sortino | +0.13 |
| Calmar | +0.03 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.40 |
| kurtosis | 18.7 |
| CVaR 5 % | -0.7% |
| récupération max (jours) | 2549 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.10 ; années positives 70.6% ; stabilité des paramètres 41.2% ; baseline sans sélection sur les mêmes années +0.04 ; ratio OOS/IS +0.38.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | hold=3,lookback=20 | +0.51 | +0.03 |
| 2004 | 2000-2003 | hold=3,lookback=10 | +0.46 | -0.21 |
| 2005 | 2000-2004 | hold=3,lookback=10 | +0.32 | +0.47 |
| 2006 | 2001-2005 | hold=3,lookback=10 | +0.02 | +0.49 |
| 2007 | 2002-2006 | hold=5,lookback=10 | +0.32 | +0.59 |
| 2008 | 2003-2007 | hold=5,lookback=10 | +0.71 | +0.05 |
| 2009 | 2004-2008 | hold=5,lookback=10 | +0.48 | +1.15 |
| 2010 | 2005-2009 | hold=5,lookback=10 | +0.68 | -0.78 |
| 2011 | 2006-2010 | hold=5,lookback=10 | +0.38 | +0.23 |
| 2012 | 2007-2011 | hold=5,lookback=10 | +0.22 | +0.25 |
| 2013 | 2008-2012 | hold=5,lookback=10 | +0.15 | -0.68 |
| 2014 | 2009-2013 | hold=10,lookback=20 | +0.10 | -0.58 |
| 2015 | 2010-2014 | hold=5,lookback=20 | -0.15 | +1.60 |
| 2016 | 2011-2015 | hold=3,lookback=10 | +0.15 | +0.16 |
| 2017 | 2012-2016 | hold=3,lookback=10 | +0.21 | -1.99 |
| 2018 | 2013-2017 | hold=10,lookback=10 | -0.05 | +0.54 |
| 2019 | 2014-2018 | hold=5,lookback=55 | +0.38 | +0.53 |

## 9. Robustesse
Score 65.0% sur 20 perturbations ; ratio voisins/optimum +0.74.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.23 | oui |
| lookback −5 % | paramètre | +0.19 | oui |
| hold +5 % | paramètre | +0.09 | non |
| hold −5 % | paramètre | +0.14 | oui |
| lookback +10 % | paramètre | +0.23 | oui |
| lookback −10 % | paramètre | +0.19 | oui |
| hold +10 % | paramètre | +0.09 | non |
| hold −10 % | paramètre | +0.14 | oui |
| lookback +20 % | paramètre | +0.22 | oui |
| lookback −20 % | paramètre | +0.11 | oui |
| hold +20 % | paramètre | +0.09 | non |
| hold −20 % | paramètre | +0.14 | oui |
| coûts × 1.25 | coûts | +0.15 | oui |
| coûts × 1.5 | coûts | +0.12 | oui |
| slippage + 2.0 bp | coûts | +0.07 | non |
| entrée retardée d'1 barre | exécution | -0.03 | non |
| sortie retardée d'1 barre | exécution | +0.09 | oui |
| signal bruité (5%) | signal | +0.14 | oui |
| sans les 5% meilleurs trades | dépendance | -0.54 | non |
| sans les 10% meilleurs trades | dépendance | -1.00 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -15.9%, 5e centile -27.8% ; CAGR médian 0.8% [-0.7% ; 2.3%] ; P(perte) 19.7%. P(drawdown au-delà de) : 10% → 92.5%, 20% → 25.9%, 25% → 10.0%, 35% → 0.9%, 50% → 0.1%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 10 trades, 95e centile 13 ; P(perte) 7.4%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.27. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +12.9 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 27.1%. Sharpe avec coûts × 1,5 : +0.12.

## 14. Drawdown
Recherche : max -13.8%, moyen -4.4%, plus long passage sous l'eau 2549 jours. Walk-forward OOS : max -14.2%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.68 (32.4% des jours) ; bull Sharpe -0.53 (43.6% des jours) ; sideways Sharpe +0.24 (24.0% des jours)
- **volatility** : high_vol Sharpe +0.15 (29.9% des jours) ; low_vol Sharpe +0.03 (31.7% des jours) ; normal_vol Sharpe +0.11 (38.4% des jours)
- **crisis** : no_crisis Sharpe +0.10 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.27 (31.0% des jours) ; neutral Sharpe +0.32 (40.1% des jours) ; trending Sharpe +0.21 (29.0% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 41.2% ; PBO 0.27 ; ratio OOS/IS +0.38.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 192 trades / an sur la classe ; exposition moyenne 98.7% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Vraies cassures, tendances fortes.

Observées sur l'OOS : direction = bull (Sharpe -0.53), character = mean_reverting (Sharpe -0.27).

## 20. Décision de recherche
**PROMISING**. - robustesse 65% (< 70%) - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.10, robustness 0.65, oos_stability 0.71, drawdown 0.44, cost_sensitivity 0.64, parameter_stability 0.41, capacity 0.50, regime_diversity 0.80, statistical_confidence 0.00, composite 0.47
