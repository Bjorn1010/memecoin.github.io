# volume_spike — futures
**Décision : PROMISING** — robustesse 25% (< 70%); optimum en pic : les paramètres voisins font moins de la moitié du Sharpe; Sharpe déflaté 0.00 sur 1133 essais (< 0.9)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Un volume relatif élevé avec une clôture dans le haut du range annonce une continuation.

*Pourquoi cela pourrait marcher :* Le volume confirme l'information.
## 2. Stratégie retail
Famille **volume**. Signal : volume / médiane 20 jours > k. Condition : clôture dans le quart haut (bas) du range. Horizon : 1 à 10 jours. Cible mesurée : espérance nette > 0. Risque : pics de volume de capitulation (retournement).
## 3. Formulation mathématique
`long h jours si V_t / médiane(V)_{20} > k et C_t dans le quart haut du range ; symétrique`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::volume_spike` — baseline `{'k': 2.0, 'hold': 5}`, candidat retenu par le walk-forward `{'k': 2.0, 'hold': 5}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.08 | +0.08 |
| CAGR | 0.2% | 0.2% |
| volatilité | 2.5% | 2.5% |
| drawdown max | -8.4% | -8.4% |
| Sortino | +0.06 | +0.06 |
| Calmar | +0.02 | +0.02 |
| trades | 800 | 800 |
| taux de réussite | 44.6% | 44.6% |
| profit factor | 1.05 | 1.05 |
| espérance / trade | +0.5 bp | +0.5 bp |
| exposition | 33.3% | 33.3% |
| skew | +0.32 | +0.32 |
| kurtosis | 32.1 | 32.1 |
| CVaR 5 % | -0.4% | -0.4% |
| récupération max (jours) | 2111 | 2111 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.05 |
| CAGR | 0.1% |
| volatilité | 2.3% |
| drawdown max | -10.2% |
| Sortino | +0.04 |
| Calmar | +0.01 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | +0.75 |
| kurtosis | 45.6 |
| CVaR 5 % | -0.4% |
| récupération max (jours) | 2111 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.05 ; années positives 50.0% ; stabilité des paramètres 62.5% ; baseline sans sélection sur les mêmes années +0.13 ; ratio OOS/IS -0.79.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | hold=5,k=2.0 | -0.09 | +0.90 |
| 2005 | 2001-2004 | hold=5,k=2.0 | +0.11 | +0.62 |
| 2006 | 2001-2005 | hold=5,k=2.0 | +0.20 | +0.03 |
| 2007 | 2002-2006 | hold=5,k=2.0 | +0.30 | +1.01 |
| 2008 | 2003-2007 | hold=1,k=3.0 | +0.63 | -1.28 |
| 2009 | 2004-2008 | hold=1,k=3.0 | +0.53 | +1.51 |
| 2010 | 2005-2009 | hold=5,k=2.0 | +0.62 | -0.23 |
| 2011 | 2006-2010 | hold=5,k=2.0 | +0.43 | +0.08 |
| 2012 | 2007-2011 | hold=1,k=3.0 | +0.57 | -1.68 |
| 2013 | 2008-2012 | hold=5,k=2.0 | -0.03 | -1.23 |
| 2014 | 2009-2013 | hold=1,k=3.0 | -0.09 | -1.66 |
| 2015 | 2010-2014 | hold=5,k=2.0 | -0.47 | +0.10 |
| 2016 | 2011-2015 | hold=1,k=3.0 | -0.18 | -0.57 |
| 2017 | 2012-2016 | hold=5,k=2.0 | -0.19 | -0.43 |
| 2018 | 2013-2017 | hold=5,k=2.0 | -0.08 | -0.03 |
| 2019 | 2014-2018 | hold=10,k=2.0 | +0.10 | +0.95 |

## 9. Robustesse
Score 25.0% sur 20 perturbations ; ratio voisins/optimum -0.39 — **optimum en pic**.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| k +5 % | paramètre | +0.10 | oui |
| k −5 % | paramètre | -0.07 | non |
| hold +5 % | paramètre | -0.08 | non |
| hold −5 % | paramètre | +0.03 | non |
| k +10 % | paramètre | +0.01 | non |
| k −10 % | paramètre | +0.02 | non |
| hold +10 % | paramètre | -0.08 | non |
| hold −10 % | paramètre | +0.03 | non |
| k +20 % | paramètre | -0.24 | non |
| k −20 % | paramètre | -0.18 | non |
| hold +20 % | paramètre | -0.08 | non |
| hold −20 % | paramètre | +0.03 | non |
| coûts × 1.25 | coûts | +0.06 | oui |
| coûts × 1.5 | coûts | +0.04 | non |
| slippage + 2.0 bp | coûts | -0.09 | non |
| entrée retardée d'1 barre | exécution | +0.05 | oui |
| sortie retardée d'1 barre | exécution | +0.13 | oui |
| signal bruité (5%) | signal | +0.05 | oui |
| sans les 5% meilleurs trades | dépendance | -0.44 | non |
| sans les 10% meilleurs trades | dépendance | -0.72 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -9.5%, 5e centile -18.7% ; CAGR médian 0.2% [-0.7% ; 1.0%] ; P(perte) 36.6%. P(drawdown au-delà de) : 10% → 44.5%, 20% → 3.2%, 25% → 0.2%, 35% → 0.0%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 10 trades, 95e centile 14 ; P(perte) 35.2%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.07. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen -0.0 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 50.6%. Sharpe avec coûts × 1,5 : +0.04.

## 14. Drawdown
Recherche : max -8.4%, moyen -3.0%, plus long passage sous l'eau 2111 jours. Walk-forward OOS : max -10.2%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.65 (33.3% des jours) ; bull Sharpe -0.56 (45.8% des jours) ; sideways Sharpe +0.31 (21.0% des jours)
- **volatility** : high_vol Sharpe -0.34 (30.8% des jours) ; low_vol Sharpe +0.13 (28.4% des jours) ; normal_vol Sharpe +0.39 (40.8% des jours)
- **crisis** : no_crisis Sharpe +0.05 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.18 (32.7% des jours) ; neutral Sharpe +0.33 (37.2% des jours) ; trending Sharpe -0.42 (30.1% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 9 configurations déclarée avant exécution ; stabilité des paramètres 62.5% ; PBO 0.07 ; ratio OOS/IS -0.79.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 41 trades / an sur la classe ; exposition moyenne 33.3% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Volumes de fin de mois, de rebalancement d'indice, d'échéance.

Observées sur l'OOS : direction = bull (Sharpe -0.56), volatility = high_vol (Sharpe -0.34), character = trending (Sharpe -0.42).

## 20. Décision de recherche
**PROMISING**. - robustesse 25% (< 70%) - optimum en pic : les paramètres voisins font moins de la moitié du Sharpe - Sharpe déflaté 0.00 sur 1133 essais (< 0.9)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.05, robustness 0.25, oos_stability 0.50, drawdown 0.63, cost_sensitivity 0.47, parameter_stability 0.62, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.41
