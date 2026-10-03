# tsmom — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 23% au Monte Carlo (> 10%)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Le signe du rendement des L derniers jours prédit le signe du rendement du jour suivant (momentum de série temporelle).

*Pourquoi cela pourrait marcher :* Prime documentée sur 58 marchés futures depuis 1985 (MOP 2012).
## 2. Stratégie retail
Famille **trend**. Signal : signe du rendement sur L jours. Condition : aucune. Horizon : quotidien. Cible mesurée : rendement net > 0. Risque : retournements brutaux de régime.
## 3. Formulation mathématique
`pos_t = sign(C_t / C_{t−L} − 1)`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::tsmom` — baseline `{'lookback': 252}`, candidat retenu par le walk-forward `{'lookback': 378}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.19 | +0.24 |
| CAGR | 1.1% | 1.4% |
| volatilité | 7.0% | 6.9% |
| drawdown max | -17.1% | -23.6% |
| Sortino | +0.23 | +0.29 |
| Calmar | +0.06 | +0.06 |
| trades | 548 | 406 |
| taux de réussite | 32.3% | 31.8% |
| profit factor | 1.26 | 1.48 |
| espérance / trade | +4.1 bp | +7.1 bp |
| exposition | 94.8% | 92.2% |
| skew | -0.52 | -0.41 |
| kurtosis | 9.3 | 11.0 |
| CVaR 5 % | -1.1% | -1.1% |
| récupération max (jours) | 1628 | 1519 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.03 |
| CAGR | -0.0% |
| volatilité | 7.6% |
| drawdown max | -26.6% |
| Sortino | +0.04 |
| Calmar | -0.00 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.26 |
| kurtosis | 9.9 |
| CVaR 5 % | -1.1% |
| récupération max (jours) | 2721 |
| années | 16.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.03 ; années positives 56.2% ; stabilité des paramètres 43.8% ; baseline sans sélection sur les mêmes années +0.23 ; ratio OOS/IS +0.16.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2004 | 2001-2003 | lookback=378 | +0.26 | +0.68 |
| 2005 | 2001-2004 | lookback=378 | +0.37 | -0.45 |
| 2006 | 2001-2005 | lookback=378 | +0.23 | +0.65 |
| 2007 | 2002-2006 | lookback=378 | +0.32 | +0.49 |
| 2008 | 2003-2007 | lookback=378 | +0.14 | +0.55 |
| 2009 | 2004-2008 | lookback=378 | +0.41 | -1.75 |
| 2010 | 2005-2009 | lookback=126 | +0.14 | -1.01 |
| 2011 | 2006-2010 | lookback=63 | +0.30 | -0.02 |
| 2012 | 2007-2011 | lookback=126 | +0.25 | +0.54 |
| 2013 | 2008-2012 | lookback=63 | +0.26 | +1.12 |
| 2014 | 2009-2013 | lookback=252 | +0.41 | +0.52 |
| 2015 | 2010-2014 | lookback=252 | +0.79 | -0.37 |
| 2016 | 2011-2015 | lookback=378 | +0.63 | -0.54 |
| 2017 | 2012-2016 | lookback=126 | +0.77 | +1.23 |
| 2018 | 2013-2017 | lookback=126 | +0.87 | +0.35 |
| 2019 | 2014-2018 | lookback=126 | +0.47 | -0.91 |

## 9. Robustesse
Score 71.4% sur 14 perturbations ; ratio voisins/optimum +0.70.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.21 | oui |
| lookback −5 % | paramètre | +0.16 | oui |
| lookback +10 % | paramètre | +0.29 | oui |
| lookback −10 % | paramètre | +0.06 | non |
| lookback +20 % | paramètre | +0.07 | non |
| lookback −20 % | paramètre | +0.17 | oui |
| coûts × 1.25 | coûts | +0.23 | oui |
| coûts × 1.5 | coûts | +0.23 | oui |
| slippage + 2.0 bp | coûts | +0.21 | oui |
| entrée retardée d'1 barre | exécution | +0.32 | oui |
| sortie retardée d'1 barre | exécution | +0.32 | oui |
| signal bruité (5%) | signal | +0.34 | oui |
| sans les 5% meilleurs trades | dépendance | -0.24 | non |
| sans les 10% meilleurs trades | dépendance | -0.30 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -19.5%, 5e centile -34.2% ; CAGR médian 1.4% [-0.8% ; 3.8%] ; P(perte) 14.6%. P(drawdown au-delà de) : 10% → 98.8%, 20% → 46.9%, 25% → 23.2%, 35% → 4.1%, 50% → 0.1%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 10 trades, 95e centile 14 ; P(perte) 11.8%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.45. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +53.3 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 6.0%. Sharpe avec coûts × 1,5 : +0.23.

## 14. Drawdown
Recherche : max -23.6%, moyen -7.4%, plus long passage sous l'eau 1519 jours. Walk-forward OOS : max -26.6%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.42 (24.3% des jours) ; bull Sharpe +0.24 (52.5% des jours) ; sideways Sharpe -0.73 (23.2% des jours)
- **volatility** : high_vol Sharpe +0.10 (31.5% des jours) ; low_vol Sharpe -0.36 (31.4% des jours) ; normal_vol Sharpe +0.23 (37.1% des jours)
- **crisis** : no_crisis Sharpe +0.03 (100.0% des jours)
- **character** : mean_reverting Sharpe +1.12 (31.4% des jours) ; neutral Sharpe -0.35 (40.0% des jours) ; trending Sharpe -0.57 (28.7% des jours)

Dépendance détectée : character:mean_reverting. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 5 configurations déclarée avant exécution ; stabilité des paramètres 43.8% ; PBO 0.45 ; ratio OOS/IS +0.16.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 21 trades / an sur la classe ; exposition moyenne 92.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Krachs de momentum (2009), marchés plats.

Observées sur l'OOS : direction = sideways (Sharpe -0.73), volatility = low_vol (Sharpe -0.36), character = neutral (Sharpe -0.35), character = trending (Sharpe -0.57).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 23% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.03, robustness 0.71, oos_stability 0.56, drawdown 0.32, cost_sensitivity 0.97, parameter_stability 0.44, capacity 0.50, regime_diversity 0.60, statistical_confidence 0.00, composite 0.46
