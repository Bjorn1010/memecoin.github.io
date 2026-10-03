# sma_cross — futures
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); PBO 0.64 (> 0.5); P(drawdown > 25 %) = 28% au Monte Carlo (> 10%)
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
`qt/lab/strategies.py::sma_cross` — baseline `{'fast': 50, 'slow': 200}`, candidat retenu par le walk-forward `{'fast': 100, 'slow': 300}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.20 | +0.23 |
| CAGR | 1.2% | 1.4% |
| volatilité | 6.9% | 7.0% |
| drawdown max | -20.7% | -17.0% |
| Sortino | +0.26 | +0.29 |
| Calmar | +0.06 | +0.08 |
| trades | 128 | 77 |
| taux de réussite | 35.2% | 36.4% |
| profit factor | 1.28 | 1.61 |
| espérance / trade | +15.4 bp | +36.5 bp |
| exposition | 95.9% | 93.8% |
| skew | -0.39 | -0.38 |
| kurtosis | 7.0 | 10.1 |
| CVaR 5 % | -1.0% | -1.1% |
| récupération max (jours) | 2927 | 1186 |
| années | 19.4 | 19.4 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.13 |
| CAGR | 0.7% |
| volatilité | 8.0% |
| drawdown max | -16.7% |
| Sortino | +0.17 |
| Calmar | +0.04 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.12 |
| kurtosis | 8.0 |
| CVaR 5 % | -1.2% |
| récupération max (jours) | 1560 |
| années | 15.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.13 ; années positives 66.7% ; stabilité des paramètres 40.0% ; baseline sans sélection sur les mêmes années +0.26 ; ratio OOS/IS +0.32.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2005 | 2002-2004 | fast=20,slow=300 | +0.10 | -1.53 |
| 2006 | 2002-2005 | fast=100,slow=300 | -0.08 | +0.07 |
| 2007 | 2002-2006 | fast=100,slow=300 | -0.05 | +0.13 |
| 2008 | 2003-2007 | fast=100,slow=300 | +0.01 | +0.80 |
| 2009 | 2004-2008 | fast=100,slow=300 | +0.26 | -0.84 |
| 2010 | 2005-2009 | fast=100,slow=300 | +0.08 | +0.35 |
| 2011 | 2006-2010 | fast=50,slow=100 | +0.27 | +0.68 |
| 2012 | 2007-2011 | fast=50,slow=100 | +0.32 | -1.26 |
| 2013 | 2008-2012 | fast=50,slow=100 | +0.22 | +0.10 |
| 2014 | 2009-2013 | fast=50,slow=200 | +0.34 | +0.97 |
| 2015 | 2010-2014 | fast=100,slow=300 | +0.62 | +0.06 |
| 2016 | 2011-2015 | fast=50,slow=200 | +0.69 | -0.07 |
| 2017 | 2012-2016 | fast=100,slow=200 | +0.78 | +1.72 |
| 2018 | 2013-2017 | fast=100,slow=200 | +1.00 | -0.12 |
| 2019 | 2014-2018 | fast=50,slow=200 | +0.48 | +0.57 |

## 9. Robustesse
Score 85.0% sur 20 perturbations ; ratio voisins/optimum +1.12.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.27 | oui |
| fast −5 % | paramètre | +0.22 | oui |
| slow +5 % | paramètre | +0.28 | oui |
| slow −5 % | paramètre | +0.17 | oui |
| fast +10 % | paramètre | +0.27 | oui |
| fast −10 % | paramètre | +0.21 | oui |
| slow +10 % | paramètre | +0.38 | oui |
| slow −10 % | paramètre | +0.18 | oui |
| fast +20 % | paramètre | +0.31 | oui |
| fast −20 % | paramètre | +0.25 | oui |
| slow +20 % | paramètre | +0.43 | oui |
| slow −20 % | paramètre | +0.10 | non |
| coûts × 1.25 | coûts | +0.23 | oui |
| coûts × 1.5 | coûts | +0.23 | oui |
| slippage + 2.0 bp | coûts | +0.23 | oui |
| entrée retardée d'1 barre | exécution | +0.21 | oui |
| sortie retardée d'1 barre | exécution | +0.22 | oui |
| signal bruité (5%) | signal | +0.25 | oui |
| sans les 5% meilleurs trades | dépendance | +0.01 | non |
| sans les 10% meilleurs trades | dépendance | -0.09 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -20.8%, 5e centile -35.4% ; CAGR médian 1.4% [-1.0% ; 3.9%] ; P(perte) 16.0%. P(drawdown au-delà de) : 10% → 99.4%, 20% → 53.5%, 25% → 28.1%, 35% → 5.8%, 50% → 0.1%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 6 trades, 95e centile 10 ; P(perte) 11.8%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.64. Reality Check / SPA sur les 23 stratégies de la classe : p = 0.210 / 0.276 (meilleure : rsi2_trend).

## 12. Capacité
Edge net moyen +364.7 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.00 bp/côté (comm 0.2, demi-spread 0.3, slippage 0.5), portage 0.0% long / 0.0% short. Part des coûts dans le résultat brut : 1.1%. Sharpe avec coûts × 1,5 : +0.23.

## 14. Drawdown
Recherche : max -17.0%, moyen -5.9%, plus long passage sous l'eau 1186 jours. Walk-forward OOS : max -16.7%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.40 (29.1% des jours) ; bull Sharpe +0.00 (50.8% des jours) ; sideways Sharpe +0.06 (20.1% des jours)
- **volatility** : high_vol Sharpe +0.19 (33.0% des jours) ; low_vol Sharpe +0.08 (32.1% des jours) ; normal_vol Sharpe +0.10 (34.9% des jours)
- **crisis** : no_crisis Sharpe +0.13 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.10 (27.2% des jours) ; neutral Sharpe +0.45 (39.4% des jours) ; trending Sharpe -0.18 (33.4% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 8 configurations déclarée avant exécution ; stabilité des paramètres 40.0% ; PBO 0.64 ; ratio OOS/IS +0.32.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 4 trades / an sur la classe ; exposition moyenne 93.8% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés sans tendance persistante, retournements en V (2020), coûts de portage élevés.

Observées sur l'OOS : character = trending (Sharpe -0.18).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - PBO 0.64 (> 0.5) - P(drawdown > 25 %) = 28% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.13, robustness 0.85, oos_stability 0.67, drawdown 0.29, cost_sensitivity 0.99, parameter_stability 0.40, capacity 0.50, regime_diversity 0.90, statistical_confidence 0.00, composite 0.53
