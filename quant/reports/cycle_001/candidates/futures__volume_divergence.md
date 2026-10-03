# volume_divergence — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
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
| ES=F | 2000-09-18 | 26.04 | C | 73 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 10 barres OHLC incohérentes (réparées : high/low recalculés) |
| NQ=F | 2000-09-18 | 26.04 | C | 191 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 23 barres OHLC incohérentes (réparées : high/low recalculés) |
| YM=F | 2002-04-05 | 24.49 | C | 57 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 26 barres OHLC incohérentes (réparées : high/low recalculés) |
| RTY=F | 2017-07-10 | 9.23 | C | 40 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables) |
| ZN=F | 2000-09-21 | 26.03 | A | 20 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 12) |
| ZB=F | 2000-09-21 | 26.03 | A | 10 barres OHLC incohérentes (réparées : high/low recalculés) |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | -0.08 | +0.10 |
| CAGR | -0.4% | 0.3% |
| volatilité | 3.9% | 3.8% |
| drawdown max | -15.8% | -17.5% |
| Sortino | -0.10 | +0.12 |
| Calmar | -0.02 | +0.02 |
| trades | 1144 | 1915 |
| taux de réussite | 54.1% | 55.4% |
| profit factor | 0.98 | 1.05 |
| espérance / trade | -0.2 bp | +0.5 bp |
| exposition | 74.0% | 72.1% |
| skew | +0.40 | +0.50 |
| kurtosis | 11.3 | 9.7 |
| CVaR 5 % | -0.6% | -0.6% |
| récupération max (jours) | 1555 | 1354 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.01 |
| CAGR | -0.1% |
| volatilité | 4.2% |
| drawdown max | -19.8% |
| Sortino | +0.01 |
| Calmar | -0.00 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.07 |
| kurtosis | 16.0 |
| CVaR 5 % | -0.6% |
| récupération max (jours) | 972 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.01 ; années positives 62.5% ; stabilité des paramètres 43.8% ; baseline sans sélection sur les mêmes années -0.02 ; ratio OOS/IS +0.12.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | hold=3,lookback=10 | +0.23 | +0.18 |
| 2005 | 2001-2004 | hold=3,lookback=20 | +0.24 | -0.46 |
| 2006 | 2001-2005 | hold=3,lookback=10 | +0.14 | +1.62 |
| 2007 | 2002-2006 | hold=3,lookback=20 | +0.46 | +0.35 |
| 2008 | 2003-2007 | hold=5,lookback=20 | +0.64 | -0.40 |
| 2009 | 2004-2008 | hold=3,lookback=10 | +0.68 | +0.29 |
| 2010 | 2005-2009 | hold=3,lookback=10 | +0.70 | +0.23 |
| 2011 | 2006-2010 | hold=3,lookback=10 | +0.76 | +0.87 |
| 2012 | 2007-2011 | hold=3,lookback=10 | +0.62 | +0.55 |
| 2013 | 2008-2012 | hold=3,lookback=10 | +0.60 | +0.13 |
| 2014 | 2009-2013 | hold=5,lookback=10 | +0.45 | +0.49 |
| 2015 | 2010-2014 | hold=5,lookback=10 | +0.57 | +0.41 |
| 2016 | 2011-2015 | hold=10,lookback=10 | +0.67 | -0.58 |
| 2017 | 2012-2016 | hold=5,lookback=10 | +0.22 | -1.00 |
| 2018 | 2013-2017 | hold=10,lookback=10 | -0.10 | -0.83 |
| 2019 | 2014-2018 | hold=10,lookback=10 | -0.12 | -1.07 |

## 9. Robustesse
Score 70.0% sur 20 perturbations ; ratio voisins/optimum +1.12.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.10 | oui |
| lookback −5 % | paramètre | +0.19 | oui |
| hold +5 % | paramètre | +0.06 | oui |
| hold −5 % | paramètre | +0.12 | oui |
| lookback +10 % | paramètre | +0.10 | oui |
| lookback −10 % | paramètre | +0.19 | oui |
| hold +10 % | paramètre | +0.06 | oui |
| hold −10 % | paramètre | +0.12 | oui |
| lookback +20 % | paramètre | +0.09 | oui |
| lookback −20 % | paramètre | +0.13 | oui |
| hold +20 % | paramètre | +0.06 | oui |
| hold −20 % | paramètre | +0.12 | oui |
| coûts × 1.25 | coûts | +0.07 | oui |
| coûts × 1.5 | coûts | +0.05 | non |
| slippage + 2.0 bp | coûts | -0.11 | non |
| entrée retardée d'1 barre | exécution | -0.11 | non |
| sortie retardée d'1 barre | exécution | +0.03 | non |
| signal bruité (5%) | signal | +0.05 | oui |
| sans les 5% meilleurs trades | dépendance | -0.53 | non |
| sans les 10% meilleurs trades | dépendance | -0.92 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -14.3%, 5e centile -26.8% ; CAGR médian 0.3% [-1.0% ; 1.6%] ; P(perte) 34.7%. P(drawdown au-delà de) : 10% → 82.3%, 20% → 18.9%, 25% → 7.2%, 35% → 0.1%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 9 trades, 95e centile 12 ; P(perte) 28.5%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.23. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +6.2 bp par trade. Moitié de l'edge perdue en impact vers 10,000,000 $, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 44.8%. Sharpe avec coûts × 1,5 : +0.05.

## 14. Drawdown
Recherche : max -17.5%, moyen -3.8%, plus long passage sous l'eau 1354 jours. Walk-forward OOS : max -19.8%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.17 (32.0% des jours) ; bull Sharpe -0.23 (46.1% des jours) ; sideways Sharpe +0.18 (21.9% des jours)
- **volatility** : high_vol Sharpe +0.56 (29.1% des jours) ; low_vol Sharpe +0.29 (32.0% des jours) ; normal_vol Sharpe -0.63 (38.9% des jours)
- **crisis** : no_crisis Sharpe +0.01 (100.0% des jours)
- **character** : mean_reverting Sharpe -0.54 (29.4% des jours) ; neutral Sharpe +0.03 (41.0% des jours) ; trending Sharpe +0.56 (29.6% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 43.8% ; PBO 0.23 ; ratio OOS/IS +0.12.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 99 trades / an sur la classe ; exposition moyenne 72.1% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Tendances régulières à volume décroissant.

Observées sur l'OOS : direction = bull (Sharpe -0.23), volatility = normal_vol (Sharpe -0.63), character = mean_reverting (Sharpe -0.54).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.01, robustness 0.70, oos_stability 0.62, drawdown 0.46, cost_sensitivity 0.48, parameter_stability 0.44, capacity 1.00, regime_diversity 0.70, statistical_confidence 0.00, composite 0.49
