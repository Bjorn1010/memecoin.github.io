# squeeze_breakout — futures
**Décision : PROMISING** — robustesse 44% (< 70%); optimum en pic : les paramètres voisins font moins de la moitié du Sharpe; Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Lorsque la volatilité augmente après une période de compression, la probabilité d'un mouvement directionnel durable augmente.

*Pourquoi cela pourrait marcher :* Les régimes de volatilité alternent ; l'expansion suit la compression.
## 2. Stratégie retail
Famille **volatility**. Signal : clôture hors bande de Bollinger. Condition : largeur des bandes dans le quantile bas de 6 mois. Horizon : 5 à 20 jours. Cible mesurée : espérance nette > 0. Risque : faux départs.
## 3. Formulation mathématique
`si largeur(Bollinger)_{t−1} ≤ quantile_q(126 j) et C_t hors bande : position h jours`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::squeeze_breakout` — baseline `{'n': 20, 'quantile': 0.1, 'window': 126, 'hold': 10}`, candidat retenu par le walk-forward `{'n': 20, 'quantile': 0.2, 'window': 126, 'hold': 10}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.03 | +0.07 |
| CAGR | 0.0% | 0.2% |
| volatilité | 2.5% | 3.1% |
| drawdown max | -7.0% | -7.7% |
| Sortino | +0.02 | +0.07 |
| Calmar | +0.00 | +0.02 |
| trades | 342 | 468 |
| taux de réussite | 52.3% | 51.9% |
| profit factor | 1.01 | 1.04 |
| espérance / trade | +0.1 bp | +0.6 bp |
| exposition | 41.4% | 53.3% |
| skew | +0.60 | +0.64 |
| kurtosis | 23.0 | 23.8 |
| CVaR 5 % | -0.4% | -0.5% |
| récupération max (jours) | 1766 | 2189 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.07 |
| CAGR | 0.2% |
| volatilité | 2.9% |
| drawdown max | -7.7% |
| Sortino | +0.07 |
| Calmar | +0.02 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +1.19 |
| kurtosis | 32.2 |
| CVaR 5 % | -0.5% |
| récupération max (jours) | 1094 |
| années | 15.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.07 ; années positives 66.7% ; stabilité des paramètres 60.0% ; baseline sans sélection sur les mêmes années +0.00 ; ratio OOS/IS +0.63.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2005 | 2002-2004 | hold=5,n=20,quantile=0.1,window=126 | +0.31 | -0.53 |
| 2006 | 2002-2005 | hold=5,n=20,quantile=0.1,window=126 | +0.05 | +1.37 |
| 2007 | 2002-2006 | hold=5,n=20,quantile=0.1,window=126 | +0.28 | +0.55 |
| 2008 | 2003-2007 | hold=10,n=20,quantile=0.1,window=126 | +0.19 | +0.07 |
| 2009 | 2004-2008 | hold=10,n=20,quantile=0.1,window=126 | +0.44 | -0.70 |
| 2010 | 2005-2009 | hold=10,n=20,quantile=0.1,window=126 | +0.12 | +0.01 |
| 2011 | 2006-2010 | hold=10,n=20,quantile=0.2,window=126 | +0.28 | +0.49 |
| 2012 | 2007-2011 | hold=10,n=20,quantile=0.2,window=126 | +0.39 | +0.37 |
| 2013 | 2008-2012 | hold=10,n=20,quantile=0.2,window=126 | +0.32 | -0.35 |
| 2014 | 2009-2013 | hold=10,n=20,quantile=0.2,window=126 | +0.26 | +0.71 |
| 2015 | 2010-2014 | hold=10,n=20,quantile=0.2,window=126 | +0.44 | +0.18 |
| 2016 | 2011-2015 | hold=10,n=20,quantile=0.2,window=126 | +0.27 | -1.18 |
| 2017 | 2012-2016 | hold=10,n=20,quantile=0.2,window=126 | -0.03 | +0.20 |
| 2018 | 2013-2017 | hold=10,n=20,quantile=0.2,window=126 | -0.08 | +1.03 |
| 2019 | 2014-2018 | hold=10,n=20,quantile=0.2,window=126 | +0.10 | -0.11 |

## 9. Robustesse
Score 43.8% sur 32 perturbations ; ratio voisins/optimum +0.37 — **optimum en pic**.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| n +5 % | paramètre | -0.04 | non |
| n −5 % | paramètre | +0.03 | non |
| quantile +5 % | paramètre | +0.10 | oui |
| quantile −5 % | paramètre | +0.04 | oui |
| window +5 % | paramètre | +0.07 | oui |
| window −5 % | paramètre | +0.05 | oui |
| hold +5 % | paramètre | +0.01 | non |
| hold −5 % | paramètre | +0.02 | non |
| n +10 % | paramètre | -0.08 | non |
| n −10 % | paramètre | -0.04 | non |
| quantile +10 % | paramètre | +0.11 | oui |
| quantile −10 % | paramètre | +0.07 | oui |
| window +10 % | paramètre | +0.04 | oui |
| window −10 % | paramètre | -0.00 | non |
| hold +10 % | paramètre | +0.01 | non |
| hold −10 % | paramètre | +0.02 | non |
| n +20 % | paramètre | -0.13 | non |
| n −20 % | paramètre | -0.25 | non |
| quantile +20 % | paramètre | +0.04 | oui |
| quantile −20 % | paramètre | +0.08 | oui |
| window +20 % | paramètre | +0.00 | non |
| window −20 % | paramètre | +0.10 | oui |
| hold +20 % | paramètre | -0.06 | non |
| hold −20 % | paramètre | +0.09 | oui |
| coûts × 1.25 | coûts | +0.06 | oui |
| coûts × 1.5 | coûts | +0.05 | oui |
| slippage + 2.0 bp | coûts | +0.00 | non |
| entrée retardée d'1 barre | exécution | -0.15 | non |
| sortie retardée d'1 barre | exécution | +0.03 | non |
| signal bruité (5%) | signal | +0.06 | oui |
| sans les 5% meilleurs trades | dépendance | -0.27 | non |
| sans les 10% meilleurs trades | dépendance | -0.47 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -11.0%, 5e centile -21.0% ; CAGR médian 0.1% [-0.8% ; 1.1%] ; P(perte) 41.1%. P(drawdown au-delà de) : 10% → 59.9%, 20% → 6.2%, 25% → 1.5%, 35% → 0.1%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 11 ; P(perte) 42.5%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.03. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen -4.5 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 41.4%. Sharpe avec coûts × 1,5 : +0.05.

## 14. Drawdown
Recherche : max -7.7%, moyen -3.6%, plus long passage sous l'eau 2189 jours. Walk-forward OOS : max -7.7%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +1.18 (30.4% des jours) ; bull Sharpe -0.38 (45.4% des jours) ; sideways Sharpe -0.43 (24.2% des jours)
- **volatility** : high_vol Sharpe -0.05 (31.3% des jours) ; low_vol Sharpe +0.48 (30.2% des jours) ; normal_vol Sharpe +0.04 (38.5% des jours)
- **crisis** : no_crisis Sharpe +0.07 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.11 (32.3% des jours) ; neutral Sharpe +0.13 (39.3% des jours) ; trending Sharpe -0.06 (27.5% des jours)

Dépendance détectée : direction:bear. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 6 configurations déclarée avant exécution ; stabilité des paramètres 60.0% ; PBO 0.03 ; ratio OOS/IS +0.63.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 24 trades / an sur la classe ; exposition moyenne 53.3% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Expansion sans direction (aller-retour).

Observées sur l'OOS : direction = bull (Sharpe -0.38), direction = sideways (Sharpe -0.43), volatility = high_vol (Sharpe -0.05), character = trending (Sharpe -0.06).

## 20. Décision de recherche
**PROMISING**. - robustesse 44% (< 70%) - optimum en pic : les paramètres voisins font moins de la moitié du Sharpe - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.07, robustness 0.44, oos_stability 0.67, drawdown 0.58, cost_sensitivity 0.75, parameter_stability 0.60, capacity 0.50, regime_diversity 0.60, statistical_confidence 0.00, composite 0.47
