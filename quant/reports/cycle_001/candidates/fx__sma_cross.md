# sma_cross — fx
**Décision : PROMISING** — robustesse 60% (< 70%); Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 75% au Monte Carlo (> 10%)
> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.
## 1. Hypothèse de marché
Quand la moyenne 50 jours est au-dessus de la 200 jours, le rendement des jours suivants est supérieur à celui des jours où elle est en dessous, après coûts.

*Pourquoi cela pourrait marcher :* Sous-réaction des investisseurs à l'information, puis comportement grégaire (Moskowitz, Ooi, Pedersen 2012).
## 2. Stratégie retail
Famille **trend**. Signal : SMA(fast) − SMA(slow). Condition : aucune. Horizon : tant que le signe ne change pas. Cible mesurée : rendement net par jour exposé > 0. Risque : drawdown pendant les retournements ; whipsaws en marché sans tendance.
## 3. Formulation mathématique
`pos_t = sign(SMA_f(C)_t − SMA_s(C)_t)`

Exécution : décision sur la clôture de t, exécution à l'ouverture de t+1.
## 4. Implémentation quant
`qt/lab/strategies.py::sma_cross` — baseline `{'fast': 50, 'slow': 200}`, candidat retenu par le walk-forward `{'fast': 50, 'slow': 100}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
## 5. Données
| instrument | début | années | note d'audit | problèmes |
|---|---|---|---|---|
| EURUSD=X | 2003-12-01 | 22.84 | B | 67 barres OHLC incohérentes (réparées : high/low recalculés); 2 trous de plus de 5 jours (max 18) |
| GBPUSD=X | 2003-12-01 | 22.84 | A | 50 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 6) |
| USDJPY=X | 1996-10-30 | 29.92 | B | 162 barres OHLC incohérentes (réparées : high/low recalculés); 2 trous de plus de 5 jours (max 18) |
| AUDUSD=X | 2006-05-16 | 20.38 | B | 94 barres OHLC incohérentes (réparées : high/low recalculés); 1 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| USDCAD=X | 2003-09-17 | 23.04 | A | 43 barres OHLC incohérentes (réparées : high/low recalculés); 1 barres le week-end sur un marché fermé le week-end |
| USDCHF=X | 2003-09-17 | 23.04 | B | 63 barres OHLC incohérentes (réparées : high/low recalculés); 1 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| NZDUSD=X | 2003-12-01 | 22.84 | B | 304 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 6) |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | -0.06 | +0.13 |
| CAGR | -0.8% | 0.8% |
| volatilité | 8.2% | 8.3% |
| drawdown max | -27.9% | -28.3% |
| Sortino | -0.07 | +0.18 |
| Calmar | -0.03 | +0.03 |
| trades | 168 | 331 |
| taux de réussite | 36.9% | 40.2% |
| profit factor | 1.19 | 1.38 |
| espérance / trade | +9.2 bp | +14.7 bp |
| exposition | 96.7% | 98.3% |
| skew | -0.56 | -0.22 |
| kurtosis | 8.6 | 7.5 |
| CVaR 5 % | -1.2% | -1.2% |
| récupération max (jours) | 5568 | 1951 |
| années | 23.9 | 23.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.08 |
| CAGR | 0.3% |
| volatilité | 7.9% |
| drawdown max | -26.3% |
| Sortino | +0.10 |
| Calmar | +0.01 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.26 |
| kurtosis | 8.5 |
| CVaR 5 % | -1.2% |
| récupération max (jours) | 1965 |
| années | 19.6 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.08 ; années positives 52.6% ; stabilité des paramètres 52.6% ; baseline sans sélection sur les mêmes années +0.01 ; ratio OOS/IS -0.21.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2001 | 1998-2000 | fast=50,slow=100 | +0.50 | +0.58 |
| 2002 | 1998-2001 | fast=50,slow=100 | +0.52 | -0.65 |
| 2003 | 1998-2002 | fast=50,slow=100 | +0.30 | +0.42 |
| 2004 | 1999-2003 | fast=50,slow=300 | +0.38 | -0.26 |
| 2005 | 2000-2004 | fast=50,slow=300 | +0.30 | -0.26 |
| 2006 | 2001-2005 | fast=20,slow=300 | +0.33 | -0.69 |
| 2007 | 2002-2006 | fast=20,slow=200 | +0.01 | +0.51 |
| 2008 | 2003-2007 | fast=50,slow=100 | +0.27 | +0.90 |
| 2009 | 2004-2008 | fast=50,slow=100 | +0.43 | +0.79 |
| 2010 | 2005-2009 | fast=50,slow=100 | +0.53 | +0.32 |
| 2011 | 2006-2010 | fast=50,slow=100 | +0.52 | +0.08 |
| 2012 | 2007-2011 | fast=50,slow=100 | +0.53 | -1.50 |
| 2013 | 2008-2012 | fast=50,slow=100 | +0.28 | +0.35 |
| 2014 | 2009-2013 | fast=50,slow=100 | +0.06 | +1.43 |
| 2015 | 2010-2014 | fast=20,slow=100 | +0.37 | -0.02 |
| 2016 | 2011-2015 | fast=20,slow=200 | +0.42 | +0.25 |
| 2017 | 2012-2016 | fast=20,slow=200 | +0.46 | -1.58 |
| 2018 | 2013-2017 | fast=20,slow=200 | +0.34 | -0.42 |
| 2019 | 2014-2018 | fast=20,slow=200 | +0.20 | -1.66 |

## 9. Robustesse
Score 60.0% sur 20 perturbations ; ratio voisins/optimum +0.70.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.11 | oui |
| fast −5 % | paramètre | +0.12 | oui |
| slow +5 % | paramètre | +0.06 | non |
| slow −5 % | paramètre | +0.18 | oui |
| fast +10 % | paramètre | +0.09 | oui |
| fast −10 % | paramètre | +0.16 | oui |
| slow +10 % | paramètre | +0.02 | non |
| slow −10 % | paramètre | +0.17 | oui |
| fast +20 % | paramètre | -0.02 | non |
| fast −20 % | paramètre | +0.06 | non |
| slow +20 % | paramètre | +0.07 | oui |
| slow −20 % | paramètre | +0.09 | oui |
| coûts × 1.25 | coûts | +0.10 | oui |
| coûts × 1.5 | coûts | +0.07 | non |
| slippage + 2.0 bp | coûts | +0.12 | oui |
| entrée retardée d'1 barre | exécution | +0.10 | oui |
| sortie retardée d'1 barre | exécution | +0.12 | oui |
| signal bruité (5%) | signal | +0.04 | non |
| sans les 5% meilleurs trades | dépendance | -0.25 | non |
| sans les 10% meilleurs trades | dépendance | -0.40 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -31.2%, 5e centile -53.6% ; CAGR médian 0.7% [-2.0% ; 3.4%] ; P(perte) 34.4%. P(drawdown au-delà de) : 10% → 100.0%, 20% → 91.6%, 25% → 75.4%, 35% → 37.1%, 50% → 7.6%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 8 trades, 95e centile 12 ; P(perte) 10.1%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.10. Reality Check / SPA sur les 22 stratégies de la classe : p = 0.999 / 1.000 (meilleure : sma_cross).

## 12. Capacité
pas de volume consolidé (marché OTC) : capacité non mesurable avec ces données

## 13. Coûts
Modèle : 1.15 bp/côté (comm 0.35, demi-spread 0.5, slippage 0.3), portage 1.0% long / 1.0% short. Part des coûts dans le résultat brut : 3.4%. Sharpe avec coûts × 1,5 : +0.07.

## 14. Drawdown
Recherche : max -28.3%, moyen -9.3%, plus long passage sous l'eau 1951 jours. Walk-forward OOS : max -26.3%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.22 (43.8% des jours) ; bull Sharpe +0.21 (38.3% des jours) ; sideways Sharpe -0.68 (17.9% des jours)
- **volatility** : high_vol Sharpe +0.49 (24.4% des jours) ; low_vol Sharpe -0.09 (34.3% des jours) ; normal_vol Sharpe -0.23 (41.3% des jours)
- **crisis** : no_crisis Sharpe +0.08 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.08 (28.9% des jours) ; neutral Sharpe +0.46 (39.9% des jours) ; trending Sharpe -0.31 (31.2% des jours)

Dépendance détectée : volatility:high_vol. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 8 configurations déclarée avant exécution ; stabilité des paramètres 52.6% ; PBO 0.10 ; ratio OOS/IS -0.21.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 14 trades / an sur la classe ; exposition moyenne 98.3% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés sans tendance persistante, retournements en V (2020), coûts de portage élevés.

Observées sur l'OOS : direction = sideways (Sharpe -0.68), volatility = low_vol (Sharpe -0.09), volatility = normal_vol (Sharpe -0.23), character = trending (Sharpe -0.31).

## 20. Décision de recherche
**PROMISING**. - robustesse 60% (< 70%) - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 75% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.08, robustness 0.60, oos_stability 0.53, drawdown 0.00, cost_sensitivity 0.49, parameter_stability 0.53, capacity 0.50, regime_diversity 0.60, statistical_confidence 0.00, composite 0.37
