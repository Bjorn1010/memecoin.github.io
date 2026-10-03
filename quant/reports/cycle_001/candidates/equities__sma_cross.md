# sma_cross — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 10% au Monte Carlo (> 10%)
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
`qt/lab/strategies.py::sma_cross` — baseline `{'fast': 50, 'slow': 200}`, candidat retenu par le walk-forward `{'fast': 100, 'slow': 200}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.27 | +0.43 |
| CAGR | 1.6% | 2.9% |
| volatilité | 6.8% | 7.1% |
| drawdown max | -16.1% | -14.5% |
| Sortino | +0.32 | +0.53 |
| Calmar | +0.10 | +0.20 |
| trades | 253 | 204 |
| taux de réussite | 36.4% | 43.6% |
| profit factor | 1.69 | 2.30 |
| espérance / trade | +18.2 bp | +35.3 bp |
| exposition | 96.2% | 96.2% |
| skew | -0.49 | -0.54 |
| kurtosis | 11.9 | 8.4 |
| CVaR 5 % | -1.1% | -1.1% |
| récupération max (jours) | 1210 | 1229 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.39 |
| CAGR | 2.6% |
| volatilité | 7.4% |
| drawdown max | -20.4% |
| Sortino | +0.48 |
| Calmar | +0.13 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.44 |
| kurtosis | 12.3 |
| CVaR 5 % | -1.2% |
| récupération max (jours) | 1601 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.39 ; années positives 70.6% ; stabilité des paramètres 29.4% ; baseline sans sélection sur les mêmes années +0.37 ; ratio OOS/IS +1.05.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | fast=50,slow=200 | -0.22 | +1.00 |
| 2004 | 2000-2003 | fast=100,slow=200 | +0.08 | +0.37 |
| 2005 | 2000-2004 | fast=100,slow=300 | +0.15 | +0.66 |
| 2006 | 2001-2005 | fast=100,slow=300 | +0.25 | +0.71 |
| 2007 | 2002-2006 | fast=20,slow=300 | +0.55 | +1.12 |
| 2008 | 2003-2007 | fast=20,slow=300 | +0.80 | +0.31 |
| 2009 | 2004-2008 | fast=50,slow=300 | +0.64 | -0.43 |
| 2010 | 2005-2009 | fast=100,slow=200 | +0.44 | -0.10 |
| 2011 | 2006-2010 | fast=20,slow=300 | +0.40 | -0.01 |
| 2012 | 2007-2011 | fast=100,slow=200 | +0.31 | +0.12 |
| 2013 | 2008-2012 | fast=50,slow=100 | +0.15 | +1.68 |
| 2014 | 2009-2013 | fast=50,slow=100 | +0.47 | +1.10 |
| 2015 | 2010-2014 | fast=20,slow=300 | +0.85 | -0.60 |
| 2016 | 2011-2015 | fast=100,slow=200 | +0.74 | +0.89 |
| 2017 | 2012-2016 | fast=100,slow=200 | +0.95 | +1.76 |
| 2018 | 2013-2017 | fast=100,slow=300 | +1.32 | -0.89 |
| 2019 | 2014-2018 | fast=50,slow=300 | +0.52 | +1.17 |

## 9. Robustesse
Score 90.0% sur 20 perturbations ; ratio voisins/optimum +0.95.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| fast +5 % | paramètre | +0.42 | oui |
| fast −5 % | paramètre | +0.44 | oui |
| slow +5 % | paramètre | +0.46 | oui |
| slow −5 % | paramètre | +0.38 | oui |
| fast +10 % | paramètre | +0.40 | oui |
| fast −10 % | paramètre | +0.37 | oui |
| slow +10 % | paramètre | +0.43 | oui |
| slow −10 % | paramètre | +0.30 | oui |
| fast +20 % | paramètre | +0.41 | oui |
| fast −20 % | paramètre | +0.34 | oui |
| slow +20 % | paramètre | +0.42 | oui |
| slow −20 % | paramètre | +0.32 | oui |
| coûts × 1.25 | coûts | +0.43 | oui |
| coûts × 1.5 | coûts | +0.42 | oui |
| slippage + 2.0 bp | coûts | +0.43 | oui |
| entrée retardée d'1 barre | exécution | +0.40 | oui |
| sortie retardée d'1 barre | exécution | +0.40 | oui |
| signal bruité (5%) | signal | +0.49 | oui |
| sans les 5% meilleurs trades | dépendance | +0.03 | non |
| sans les 10% meilleurs trades | dépendance | -0.12 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -16.9%, 5e centile -28.3% ; CAGR médian 2.8% [0.6% ; 5.0%] ; P(perte) 1.2%. P(drawdown au-delà de) : 10% → 98.2%, 20% → 27.4%, 25% → 10.2%, 35% → 0.8%, 50% → 0.0%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 7 trades, 95e centile 11 ; P(perte) 0.0%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.19. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +535.0 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 0.5%. Sharpe avec coûts × 1,5 : +0.42.

## 14. Drawdown
Recherche : max -14.5%, moyen -4.9%, plus long passage sous l'eau 1229 jours. Walk-forward OOS : max -20.4%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.77 (17.9% des jours) ; bull Sharpe +0.17 (59.5% des jours) ; sideways Sharpe +0.69 (22.6% des jours)
- **volatility** : high_vol Sharpe +0.57 (31.0% des jours) ; low_vol Sharpe -0.08 (31.8% des jours) ; normal_vol Sharpe +0.49 (37.2% des jours)
- **crisis** : no_crisis Sharpe +0.39 (100.0% des jours)
- **character** : mean_reverting Sharpe +1.10 (29.6% des jours) ; neutral Sharpe +0.39 (39.2% des jours) ; trending Sharpe -0.25 (31.2% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 8 configurations déclarée avant exécution ; stabilité des paramètres 29.4% ; PBO 0.19 ; ratio OOS/IS +1.05.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 10 trades / an sur la classe ; exposition moyenne 96.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Marchés sans tendance persistante, retournements en V (2020), coûts de portage élevés.

Observées sur l'OOS : volatility = low_vol (Sharpe -0.08), character = trending (Sharpe -0.25).

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 10% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.39, robustness 0.90, oos_stability 0.71, drawdown 0.43, cost_sensitivity 0.97, parameter_stability 0.29, capacity 0.50, regime_diversity 0.80, statistical_confidence 0.00, composite 0.56
