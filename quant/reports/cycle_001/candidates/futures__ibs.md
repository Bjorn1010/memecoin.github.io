# ibs — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 17% au Monte Carlo (> 10%)
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
`qt/lab/strategies.py::ibs` — baseline `{'threshold': 0.2, 'hold': 1}`, candidat retenu par le walk-forward `{'threshold': 0.3, 'hold': 3}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| ES=F | 2000-09-18 | 26.04 | C | 73 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 10 barres OHLC incohérentes (réparées : high/low recalculés) |
| NQ=F | 2000-09-18 | 26.04 | C | 191 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 23 barres OHLC incohérentes (réparées : high/low recalculés) |
| YM=F | 2002-04-05 | 24.49 | C | 57 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 26 barres OHLC incohérentes (réparées : high/low recalculés) |
| RTY=F | 2017-07-10 | 9.23 | C | 40 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables) |
| ZN=F | 2000-09-21 | 26.03 | A | 20 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 12) |
| ZB=F | 2000-09-21 | 26.03 | A | 10 barres OHLC incohérentes (réparées : high/low recalculés) |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.28 | +0.41 |
| CAGR | 1.2% | 2.6% |
| volatilité | 4.7% | 6.8% |
| drawdown max | -12.2% | -19.2% |
| Sortino | +0.38 | +0.61 |
| Calmar | +0.10 | +0.14 |
| trades | 8299 | 8147 |
| taux de réussite | 53.4% | 61.3% |
| profit factor | 1.06 | 1.09 |
| espérance / trade | +0.3 bp | +0.7 bp |
| exposition | 81.9% | 99.4% |
| skew | +0.13 | +0.14 |
| kurtosis | 8.4 | 6.0 |
| CVaR 5 % | -0.7% | -0.9% |
| récupération max (jours) | 1567 | 2210 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.28 |
| CAGR | 1.5% |
| volatilité | 5.9% |
| drawdown max | -20.1% |
| Sortino | +0.39 |
| Calmar | +0.07 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.36 |
| kurtosis | 9.1 |
| CVaR 5 % | -0.8% |
| récupération max (jours) | 2210 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.28 ; années positives 50.0% ; stabilité des paramètres 37.5% ; baseline sans sélection sur les mêmes années +0.28 ; ratio OOS/IS +0.33.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | hold=3,threshold=0.3 | +1.03 | +0.87 |
| 2005 | 2001-2004 | hold=3,threshold=0.3 | +0.99 | +0.05 |
| 2006 | 2001-2005 | hold=3,threshold=0.3 | +0.80 | -0.71 |
| 2007 | 2002-2006 | hold=3,threshold=0.1 | +0.56 | -0.53 |
| 2008 | 2003-2007 | hold=3,threshold=0.3 | +0.35 | +3.01 |
| 2009 | 2004-2008 | hold=3,threshold=0.2 | +0.92 | -0.76 |
| 2010 | 2005-2009 | hold=3,threshold=0.3 | +0.69 | +1.91 |
| 2011 | 2006-2010 | hold=3,threshold=0.3 | +1.08 | -0.39 |
| 2012 | 2007-2011 | hold=1,threshold=0.1 | +1.10 | -0.09 |
| 2013 | 2008-2012 | hold=1,threshold=0.1 | +0.89 | +0.67 |
| 2014 | 2009-2013 | hold=3,threshold=0.2 | +0.48 | -1.69 |
| 2015 | 2010-2014 | hold=1,threshold=0.1 | +0.35 | -1.01 |
| 2016 | 2011-2015 | hold=1,threshold=0.3 | -0.16 | +1.26 |
| 2017 | 2012-2016 | hold=1,threshold=0.3 | +0.12 | +0.56 |
| 2018 | 2013-2017 | hold=1,threshold=0.3 | +0.38 | -0.75 |
| 2019 | 2014-2018 | hold=1,threshold=0.3 | -0.03 | +0.74 |

## 9. Robustesse
Score 75.0% sur 20 perturbations ; ratio voisins/optimum +0.99.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| threshold +5 % | paramètre | +0.34 | oui |
| threshold −5 % | paramètre | +0.40 | oui |
| hold +5 % | paramètre | +0.48 | oui |
| hold −5 % | paramètre | +0.41 | oui |
| threshold +10 % | paramètre | +0.34 | oui |
| threshold −10 % | paramètre | +0.34 | oui |
| hold +10 % | paramètre | +0.48 | oui |
| hold −10 % | paramètre | +0.41 | oui |
| threshold +20 % | paramètre | +0.35 | oui |
| threshold −20 % | paramètre | +0.29 | oui |
| hold +20 % | paramètre | +0.48 | oui |
| hold −20 % | paramètre | +0.41 | oui |
| coûts × 1.25 | coûts | +0.35 | oui |
| coûts × 1.5 | coûts | +0.29 | oui |
| slippage + 2.0 bp | coûts | -0.08 | non |
| entrée retardée d'1 barre | exécution | -0.23 | non |
| sortie retardée d'1 barre | exécution | -0.09 | non |
| signal bruité (5%) | signal | +0.40 | oui |
| sans les 5% meilleurs trades | dépendance | -0.73 | non |
| sans les 10% meilleurs trades | dépendance | -1.44 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -18.1%, 5e centile -31.6% ; CAGR médian 2.6% [0.1% ; 5.2%] ; P(perte) 4.8%. P(drawdown au-delà de) : 10% → 99.2%, 20% → 37.9%, 25% → 17.4%, 35% → 2.1%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 9 trades, 95e centile 12 ; P(perte) 1.9%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.13. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +8.2 bp par trade. Moitié de l'edge perdue en impact vers 10,000,000 $, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 38.0%. Sharpe avec coûts × 1,5 : +0.29.

## 14. Drawdown
Recherche : max -19.2%, moyen -6.3%, plus long passage sous l'eau 2210 jours. Walk-forward OOS : max -20.1%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.06 (31.2% des jours) ; bull Sharpe +0.35 (50.9% des jours) ; sideways Sharpe +0.43 (17.8% des jours)
- **volatility** : high_vol Sharpe +0.38 (29.6% des jours) ; low_vol Sharpe +0.15 (30.5% des jours) ; normal_vol Sharpe +0.28 (39.9% des jours)
- **crisis** : no_crisis Sharpe +0.28 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.17 (30.4% des jours) ; neutral Sharpe +0.19 (40.3% des jours) ; trending Sharpe +0.48 (29.3% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 37.5% ; PBO 0.13 ; ratio OOS/IS +0.33.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 421 trades / an sur la classe ; exposition moyenne 99.4% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Coûts, marchés 24/7 sans clôture significative.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 17% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.28, robustness 0.75, oos_stability 0.50, drawdown 0.37, cost_sensitivity 0.70, parameter_stability 0.38, capacity 1.00, regime_diversity 1.00, statistical_confidence 0.00, composite 0.55
