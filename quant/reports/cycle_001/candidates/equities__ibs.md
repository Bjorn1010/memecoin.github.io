# ibs — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Une clôture dans le bas du range du jour (IBS faible) est suivie d'un rendement positif le lendemain.

*Pourquoi cela pourrait marcher :* Effet documenté sur les indices actions (pression de fin de séance).
## 2. Stratégie retail
Famille **mean_reversion**. Signal : IBS = (C − L)/(H − L). Condition : IBS < seuil (achat), > 1 − seuil (vente). Horizon : 1 à 3 jours. Cible mesurée : rendement net > 0. Risque : trades très fréquents : sensibles aux coûts.
## 3. Formulation mathématique
`IBS_t = (C_t − L_t)/(H_t − L_t) ; long si IBS < θ, short si IBS > 1 − θ ; détention h jours`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::ibs` — baseline `{'threshold': 0.2, 'hold': 1}`, candidat retenu par le walk-forward `{'threshold': 0.1, 'hold': 3}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.22 | +0.47 |
| CAGR | 0.9% | 2.2% |
| volatilité | 4.7% | 4.9% |
| drawdown max | -22.0% | -26.5% |
| Sortino | +0.30 | +0.64 |
| Calmar | +0.04 | +0.08 |
| trades | 17200 | 8892 |
| taux de réussite | 52.8% | 55.8% |
| profit factor | 1.05 | 1.13 |
| espérance / trade | +0.1 bp | +0.6 bp |
| exposition | 95.1% | 97.9% |
| skew | +0.27 | -0.03 |
| kurtosis | 9.1 | 9.7 |
| CVaR 5 % | -0.7% | -0.7% |
| récupération max (jours) | 2099 | 1722 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.37 |
| CAGR | 1.8% |
| volatilité | 5.3% |
| drawdown max | -25.7% |
| Sortino | +0.48 |
| Calmar | +0.07 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.36 |
| kurtosis | 9.7 |
| CVaR 5 % | -0.8% |
| récupération max (jours) | 2160 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.37 ; années positives 58.8% ; stabilité des paramètres 47.1% ; baseline sans sélection sur les mêmes années +0.27 ; ratio OOS/IS +0.51.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | hold=3,threshold=0.1 | +0.20 | +0.93 |
| 2004 | 2000-2003 | hold=3,threshold=0.3 | +0.46 | +0.21 |
| 2005 | 2000-2004 | hold=3,threshold=0.1 | +0.55 | +0.83 |
| 2006 | 2001-2005 | hold=3,threshold=0.1 | +0.81 | +1.81 |
| 2007 | 2002-2006 | hold=3,threshold=0.1 | +1.22 | +1.86 |
| 2008 | 2003-2007 | hold=3,threshold=0.1 | +1.35 | +3.49 |
| 2009 | 2004-2008 | hold=3,threshold=0.1 | +1.89 | +0.64 |
| 2010 | 2005-2009 | hold=3,threshold=0.1 | +1.78 | +1.70 |
| 2011 | 2006-2010 | hold=3,threshold=0.1 | +1.97 | +0.05 |
| 2012 | 2007-2011 | hold=1,threshold=0.1 | +1.55 | -0.01 |
| 2013 | 2008-2012 | hold=1,threshold=0.1 | +1.39 | -0.44 |
| 2014 | 2009-2013 | hold=3,threshold=0.2 | +0.58 | -0.77 |
| 2015 | 2010-2014 | hold=3,threshold=0.2 | +0.30 | +0.64 |
| 2016 | 2011-2015 | hold=3,threshold=0.2 | +0.20 | -0.28 |
| 2017 | 2012-2016 | hold=3,threshold=0.3 | +0.03 | -1.28 |
| 2018 | 2013-2017 | hold=3,threshold=0.3 | -0.15 | -1.51 |
| 2019 | 2014-2018 | hold=1,threshold=0.1 | -0.45 | -0.84 |

## 9. Robustesse
Score 85.0% sur 20 perturbations ; ratio voisins/optimum +0.87.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| threshold +5 % | paramètre | +0.45 | oui |
| threshold −5 % | paramètre | +0.44 | oui |
| hold +5 % | paramètre | +0.39 | oui |
| hold −5 % | paramètre | +0.41 | oui |
| threshold +10 % | paramètre | +0.44 | oui |
| threshold −10 % | paramètre | +0.41 | oui |
| hold +10 % | paramètre | +0.39 | oui |
| hold −10 % | paramètre | +0.41 | oui |
| threshold +20 % | paramètre | +0.38 | oui |
| threshold −20 % | paramètre | +0.44 | oui |
| hold +20 % | paramètre | +0.39 | oui |
| hold −20 % | paramètre | +0.41 | oui |
| coûts × 1.25 | coûts | +0.42 | oui |
| coûts × 1.5 | coûts | +0.36 | oui |
| slippage + 2.0 bp | coûts | +0.24 | oui |
| entrée retardée d'1 barre | exécution | +0.11 | non |
| sortie retardée d'1 barre | exécution | +0.34 | oui |
| signal bruité (5%) | signal | +0.47 | oui |
| sans les 5% meilleurs trades | dépendance | -0.66 | non |
| sans les 10% meilleurs trades | dépendance | -1.34 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -12.3%, 5e centile -21.0% ; CAGR médian 2.2% [0.6% ; 3.8%] ; P(perte) 1.4%. P(drawdown au-delà de) : 10% → 76.6%, 20% → 7.0%, 25% → 1.4%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 10 trades, 95e centile 14 ; P(perte) 0.1%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.18. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +14.7 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 25.8%. Sharpe avec coûts × 1,5 : +0.36.

## 14. Drawdown
Recherche : max -26.5%, moyen -6.4%, plus long passage sous l'eau 1722 jours. Walk-forward OOS : max -25.7%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe -0.55 (32.8% des jours) ; bull Sharpe +0.96 (54.9% des jours) ; sideways Sharpe +0.53 (12.3% des jours)
- **volatility** : high_vol Sharpe +0.56 (30.0% des jours) ; low_vol Sharpe +0.22 (30.9% des jours) ; normal_vol Sharpe +0.29 (39.1% des jours)
- **crisis** : no_crisis Sharpe +0.37 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.83 (31.5% des jours) ; neutral Sharpe -0.19 (38.1% des jours) ; trending Sharpe +0.74 (30.4% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 47.1% ; PBO 0.18 ; ratio OOS/IS +0.51.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 424 trades / an sur la classe ; exposition moyenne 97.9% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Coûts, marchés 24/7 sans clôture significative.

Observées sur l'OOS : direction = bear (Sharpe -0.55), character = neutral (Sharpe -0.19).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.37, robustness 0.85, oos_stability 0.59, drawdown 0.58, cost_sensitivity 0.77, parameter_stability 0.47, capacity 0.50, regime_diversity 0.80, statistical_confidence 0.00, composite 0.55
