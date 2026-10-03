# sma_cross — indices
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 26% au Monte Carlo (> 10%)
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
| SPY | 1993-01-29 | 33.67 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| QQQ | 1999-03-10 | 27.56 | A | 1 trous de plus de 5 jours (max 7) |
| DIA | 1998-01-20 | 28.7 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| IWM | 2000-05-26 | 26.35 | A | 1 trous de plus de 5 jours (max 7) |
| EWG | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7); 1 séquences de ≥ 5 clôtures identiques |
| EWU | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7); 3 séquences de ≥ 5 clôtures identiques |
| EWJ | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7) |
| FEZ | 2002-10-21 | 23.95 | A | — |

## 6. Backtest (période de recherche, après coûts)
| métrique | baseline | candidat |
|---|---|---|
| Sharpe | +0.32 | +0.43 |
| CAGR | 2.2% | 3.2% |
| volatilité | 7.9% | 8.3% |
| drawdown max | -23.4% | -29.5% |
| Sortino | +0.39 | +0.52 |
| Calmar | +0.10 | +0.11 |
| trades | 215 | 118 |
| taux de réussite | 42.8% | 47.5% |
| profit factor | 3.69 | 8.01 |
| espérance / trade | +88.5 bp | +255.6 bp |
| exposition | 97.1% | 95.6% |
| skew | -0.61 | -0.55 |
| kurtosis | 9.2 | 13.4 |
| CVaR 5 % | -1.2% | -1.3% |
| récupération max (jours) | 2723 | 2723 |
| années | 26.9 | 26.9 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.16 |
| CAGR | 1.0% |
| volatilité | 8.3% |
| drawdown max | -33.9% |
| Sortino | +0.20 |
| Calmar | +0.03 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.64 |
| kurtosis | 16.3 |
| CVaR 5 % | -1.2% |
| récupération max (jours) | 2723 |
| années | 23.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.16 ; années positives 60.9% ; stabilité des paramètres 30.4% ; baseline sans sélection sur les mêmes années +0.23 ; ratio OOS/IS +0.37.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 1997 | 1994-1996 | fast=50,slow=300 | +1.56 | +1.24 |
| 1998 | 1994-1997 | fast=50,slow=300 | +1.48 | +0.62 |
| 1999 | 1994-1998 | fast=50,slow=300 | +1.31 | +1.04 |
| 2000 | 1995-1999 | fast=100,slow=300 | +1.66 | -0.96 |
| 2001 | 1996-2000 | fast=100,slow=300 | +0.74 | +0.04 |
| 2002 | 1997-2001 | fast=100,slow=300 | +0.56 | +0.12 |
| 2003 | 1998-2002 | fast=50,slow=300 | +0.39 | +0.33 |
| 2004 | 1999-2003 | fast=50,slow=300 | +0.33 | +0.68 |
| 2005 | 2000-2004 | fast=20,slow=300 | +0.30 | +0.22 |
| 2006 | 2001-2005 | fast=20,slow=300 | +0.45 | +1.12 |
| 2007 | 2002-2006 | fast=20,slow=300 | +0.59 | +0.45 |
| 2008 | 2003-2007 | fast=50,slow=300 | +0.61 | +0.27 |
| 2009 | 2004-2008 | fast=100,slow=300 | +0.54 | -0.68 |
| 2010 | 2005-2009 | fast=50,slow=200 | +0.37 | -0.21 |
| 2011 | 2006-2010 | fast=50,slow=200 | +0.36 | -0.63 |
| 2012 | 2007-2011 | fast=50,slow=200 | +0.13 | -1.38 |
| 2013 | 2008-2012 | fast=20,slow=100 | +0.05 | +1.65 |
| 2014 | 2009-2013 | fast=50,slow=100 | +0.21 | -0.03 |
| 2015 | 2010-2014 | fast=50,slow=100 | +0.15 | -0.47 |
| 2016 | 2011-2015 | fast=50,slow=100 | +0.07 | -1.33 |
| 2017 | 2012-2016 | fast=100,slow=300 | +0.29 | +2.75 |
| 2018 | 2013-2017 | fast=100,slow=300 | +0.80 | -0.15 |
| 2019 | 2014-2018 | fast=100,slow=300 | +0.27 | +0.23 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +1.06.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.45 | oui |
| fast −5 % | paramètre | +0.41 | oui |
| slow +5 % | paramètre | +0.45 | oui |
| slow −5 % | paramètre | +0.42 | oui |
| fast +10 % | paramètre | +0.47 | oui |
| fast −10 % | paramètre | +0.42 | oui |
| slow +10 % | paramètre | +0.47 | oui |
| slow −10 % | paramètre | +0.45 | oui |
| fast +20 % | paramètre | +0.54 | oui |
| fast −20 % | paramètre | +0.45 | oui |
| slow +20 % | paramètre | +0.46 | oui |
| slow −20 % | paramètre | +0.37 | oui |
| coûts × 1.25 | coûts | +0.38 | oui |
| coûts × 1.5 | coûts | +0.34 | oui |
| slippage + 2.0 bp | coûts | +0.42 | oui |
| entrée retardée d'1 barre | exécution | +0.44 | oui |
| sortie retardée d'1 barre | exécution | +0.45 | oui |
| signal bruité (5%) | signal | +0.48 | oui |
| sans les 5% meilleurs trades | dépendance | -0.14 | non |
| sans les 10% meilleurs trades | dépendance | -0.16 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -20.6%, 5e centile -33.4% ; CAGR médian 3.2% [1.0% ; 5.6%] ; P(perte) 1.0%. P(drawdown au-delà de) : 10% → 100.0%, 20% → 54.3%, 25% → 25.7%, 35% → 3.4%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 5 trades, 95e centile 8 ; P(perte) 5.8%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.31. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.133 / 0.154 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +1049.6 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.0, demi-spread 1.0, slippage 0.5), portage 3.0% long / 1.0% short. Part des coûts dans le résultat brut : 0.1%. Sharpe avec coûts × 1,5 : +0.34.

## 14. Drawdown
Recherche : max -29.5%, moyen -10.6%, plus long passage sous l'eau 2723 jours. Walk-forward OOS : max -33.9%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe -0.28 (30.8% des jours) ; bull Sharpe +0.14 (51.7% des jours) ; sideways Sharpe +0.91 (17.5% des jours)
- **volatility** : high_vol Sharpe +0.41 (28.7% des jours) ; low_vol Sharpe -0.21 (29.5% des jours) ; normal_vol Sharpe +0.10 (41.8% des jours)
- **crisis** : no_crisis Sharpe +0.16 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.77 (30.6% des jours) ; neutral Sharpe +0.26 (41.0% des jours) ; trending Sharpe -0.56 (28.4% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 8 configurations déclarée avant exécution ; stabilité des paramètres 30.4% ; PBO 0.31 ; ratio OOS/IS +0.37.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 4 trades / an sur la classe ; exposition moyenne 95.6% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés sans tendance persistante, retournements en V (2020), coûts de portage élevés.

Observées sur l'OOS : direction = bear (Sharpe -0.28), volatility = low_vol (Sharpe -0.21), character = trending (Sharpe -0.56).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 26% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.16, robustness 0.90, oos_stability 0.61, drawdown 0.33, cost_sensitivity 0.81, parameter_stability 0.30, capacity 0.50, regime_diversity 0.70, statistical_confidence 0.00, composite 0.48
