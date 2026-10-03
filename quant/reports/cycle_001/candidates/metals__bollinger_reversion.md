# bollinger_reversion — metals
**Décision : PROMISING** — robustesse 55% (< 70%); optimum en pic : les paramètres voisins font moins de la moitié du Sharpe; Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Une clôture hors des bandes de Bollinger revient vers la moyenne mobile plus souvent et plus fort que les coûts.

*Pourquoi cela pourrait marcher :* Surréaction à court terme.
## 2. Stratégie retail
Famille **mean_reversion**. Signal : clôture hors bande ± k écarts-types. Condition : aucune. Horizon : jusqu'au retour à la moyenne. Cible mesurée : espérance nette > 0. Risque : sortie de bande qui devient une tendance.
## 3. Formulation mathématique
`long si C_t < SMA_n − k·σ_n jusqu'à C_t ≥ SMA_n ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::bollinger_reversion` — baseline `{'n': 20, 'k': 2.0}`, candidat retenu par le walk-forward `{'n': 10, 'k': 2.5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | -0.09 | +0.17 |
| CAGR | -0.9% | 0.2% |
| volatilité | 6.9% | 1.3% |
| drawdown max | -24.9% | -5.2% |
| Sortino | -0.11 | +0.10 |
| Calmar | -0.03 | +0.04 |
| trades | 397 | 64 |
| taux de réussite | 62.2% | 54.7% |
| profit factor | 0.90 | 1.27 |
| espérance / trade | -2.8 bp | +4.6 bp |
| exposition | 80.6% | 14.6% |
| skew | +1.36 | +2.60 |
| kurtosis | 50.7 | 106.7 |
| CVaR 5 % | -1.0% | -0.2% |
| récupération max (jours) | 3629 | 1839 |
| années | 15.1 | 15.1 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.14 |
| CAGR | 0.4% |
| volatilité | 2.8% |
| drawdown max | -9.7% |
| Sortino | +0.12 |
| Calmar | +0.04 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.70 |
| kurtosis | 24.1 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 702 |
| années | 12.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.14 ; années positives 66.7% ; stabilité des paramètres 58.3% ; baseline sans sélection sur les mêmes années -0.08 ; ratio OOS/IS +0.61.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2008 | 2005-2007 | k=2.5,n=10 | +1.02 | +0.70 |
| 2009 | 2005-2008 | k=2.5,n=10 | +0.95 | +0.09 |
| 2010 | 2005-2009 | k=2.5,n=10 | +0.83 | +0.78 |
| 2011 | 2006-2010 | k=2.5,n=10 | +0.70 | +1.13 |
| 2012 | 2007-2011 | k=2.5,n=10 | +0.83 | -0.36 |
| 2013 | 2008-2012 | k=2.5,n=10 | +0.34 | +0.11 |
| 2014 | 2009-2013 | k=2.5,n=10 | +0.25 | -1.29 |
| 2015 | 2010-2014 | k=2.5,n=20 | +0.04 | +1.32 |
| 2016 | 2011-2015 | k=2.5,n=40 | +0.20 | -0.31 |
| 2017 | 2012-2016 | k=2.5,n=40 | +0.17 | +1.97 |
| 2018 | 2013-2017 | k=2.5,n=20 | +0.32 | +0.10 |
| 2019 | 2014-2018 | k=2.5,n=40 | +0.43 | -0.54 |

## 9. Robustesse
Score 55.0% sur 20 perturbations ; ratio voisins/optimum +0.26 — **optimum en pic**.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| n +5 % | paramètre | +0.13 | oui |
| n −5 % | paramètre | -0.12 | non |
| k +5 % | paramètre | +0.25 | oui |
| k −5 % | paramètre | -0.02 | non |
| n +10 % | paramètre | +0.13 | oui |
| n −10 % | paramètre | -0.12 | non |
| k +10 % | paramètre | +0.12 | oui |
| k −10 % | paramètre | -0.07 | non |
| n +20 % | paramètre | +0.11 | oui |
| n −20 % | paramètre | n/a | non |
| k +20 % | paramètre | n/a | non |
| k −20 % | paramètre | -0.16 | non |
| coûts × 1.25 | coûts | +0.16 | oui |
| coûts × 1.5 | coûts | +0.16 | oui |
| slippage + 2.0 bp | coûts | +0.15 | oui |
| entrée retardée d'1 barre | exécution | +0.36 | oui |
| sortie retardée d'1 barre | exécution | +0.26 | oui |
| signal bruité (5%) | signal | +0.17 | oui |
| sans les 5% meilleurs trades | dépendance | -0.08 | non |
| sans les 10% meilleurs trades | dépendance | -0.16 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -3.8%, 5e centile -7.4% ; CAGR médian 0.2% [-0.3% ; 0.7%] ; P(perte) 24.9%. P(drawdown au-delà de) : 10% → 0.8%, 20% → 0.0%, 25% → 0.0%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 4 trades, 95e centile 7 ; P(perte) 30.1%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.25. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.579 / 0.135 (meilleure : volume_spike).

## 12. Capacité
Edge net moyen +8.5 bp par trade. Moitié de l'edge perdue en impact vers 250,000 $, edge nul vers 500,000 $ (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 2.00 bp/côté (comm 0.5, demi-spread 1.0, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 11.4%. Sharpe avec coûts × 1,5 : +0.16.

## 14. Drawdown
Recherche : max -5.2%, moyen -2.0%, plus long passage sous l'eau 1839 jours. Walk-forward OOS : max -9.7%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.53 (31.0% des jours) ; bull Sharpe -0.53 (44.5% des jours) ; sideways Sharpe +0.59 (24.5% des jours)
- **volatility** : high_vol Sharpe +0.51 (28.0% des jours) ; low_vol Sharpe +0.62 (20.3% des jours) ; normal_vol Sharpe -0.39 (51.7% des jours)
- **crisis** : no_crisis Sharpe +0.14 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.63 (19.2% des jours) ; neutral Sharpe +0.35 (25.7% des jours) ; trending Sharpe +0.80 (16.8% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 58.3% ; PBO 0.25 ; ratio OOS/IS +0.61.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 4 trades / an sur la classe ; exposition moyenne 14.6% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Breakouts de volatilité, tendances fortes.

Observées sur l'OOS : direction = bull (Sharpe -0.53), volatility = normal_vol (Sharpe -0.39), character = mean_reverting (Sharpe -0.63).

## 20. Décision de recherche
**PROMISING**. - robustesse 55% (< 70%) - optimum en pic : les paramètres voisins font moins de la moitié du Sharpe - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.14, robustness 0.55, oos_stability 0.67, drawdown 0.85, cost_sensitivity 0.92, parameter_stability 0.58, capacity 0.77, regime_diversity 0.70, statistical_confidence 0.00, composite 0.58
