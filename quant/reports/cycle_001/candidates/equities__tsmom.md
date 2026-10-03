# tsmom — equities
**Décision : PROMISING** — Sharpe déflaté 0.00 sur 1133 essais (< 0.9); P(drawdown > 25 %) = 21% au Monte Carlo (> 10%)
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
`qt/lab/strategies.py::tsmom` — baseline `{'lookback': 252}`, candidat retenu par le walk-forward `{'lookback': 252}` (configuration la plus souvent choisie). Dimensionnement de recherche : chaque instrument à 10% de volatilité (fenêtre 60 j, levier max 3.0), panier équipondéré en risque de la classe.
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
| Sharpe | +0.38 | +0.38 |
| CAGR | 2.6% | 2.6% |
| volatilité | 7.5% | 7.5% |
| drawdown max | -20.3% | -20.3% |
| Sortino | +0.46 | +0.46 |
| Calmar | +0.13 | +0.13 |
| trades | 954 | 954 |
| taux de réussite | 32.3% | 32.3% |
| profit factor | 2.02 | 2.02 |
| espérance / trade | +8.9 bp | +8.9 bp |
| exposition | 95.2% | 95.2% |
| skew | -0.46 | -0.46 |
| kurtosis | 9.3 | 9.3 |
| CVaR 5 % | -1.2% | -1.2% |
| récupération max (jours) | 1503 | 1503 |
| années | 21.0 | 21.0 |

Le candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.
## 7. Hors échantillon
| métrique | walk-forward OOS |
|---|---|
| Sharpe | +0.51 |
| CAGR | 3.7% |
| volatilité | 7.8% |
| drawdown max | -24.2% |
| Sortino | +0.63 |
| Calmar | +0.15 |
| trades | n/a |
| taux de réussite | n/a |
| profit factor | n/a |
| espérance / trade | n/a |
| exposition | n/a |
| skew | -0.50 |
| kurtosis | 8.6 |
| CVaR 5 % | -1.2% |
| récupération max (jours) | 1029 |
| années | 17.0 |

Périodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.
## 8. Walk-forward
Sharpe OOS +0.51 ; années positives 76.5% ; stabilité des paramètres 64.7% ; baseline sans sélection sur les mêmes années +0.52 ; ratio OOS/IS +1.38.

| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |
|---|---|---|---|---|
| 2003 | 2000-2002 | lookback=126 | -0.41 | +0.62 |
| 2004 | 2000-2003 | lookback=126 | -0.21 | +0.68 |
| 2005 | 2000-2004 | lookback=126 | -0.05 | -0.53 |
| 2006 | 2001-2005 | lookback=252 | +0.20 | +1.19 |
| 2007 | 2002-2006 | lookback=252 | +0.59 | +0.98 |
| 2008 | 2003-2007 | lookback=252 | +0.80 | +0.21 |
| 2009 | 2004-2008 | lookback=378 | +0.69 | -1.28 |
| 2010 | 2005-2009 | lookback=252 | +0.33 | +0.76 |
| 2011 | 2006-2010 | lookback=252 | +0.37 | +0.28 |
| 2012 | 2007-2011 | lookback=252 | +0.28 | +1.50 |
| 2013 | 2008-2012 | lookback=252 | +0.25 | +2.45 |
| 2014 | 2009-2013 | lookback=252 | +0.64 | +1.35 |
| 2015 | 2010-2014 | lookback=252 | +1.13 | +0.35 |
| 2016 | 2011-2015 | lookback=252 | +1.09 | -0.77 |
| 2017 | 2012-2016 | lookback=252 | +1.05 | +2.38 |
| 2018 | 2013-2017 | lookback=378 | +1.24 | -0.25 |
| 2019 | 2014-2018 | lookback=378 | +0.54 | +1.86 |

## 9. Robustesse
Score 85.7% sur 14 perturbations ; ratio voisins/optimum +0.76.

| perturbation | type | Sharpe | tient ? |
|---|---|---|---|
| lookback +5 % | paramètre | +0.31 | oui |
| lookback −5 % | paramètre | +0.27 | oui |
| lookback +10 % | paramètre | +0.37 | oui |
| lookback −10 % | paramètre | +0.26 | oui |
| lookback +20 % | paramètre | +0.34 | oui |
| lookback −20 % | paramètre | +0.23 | oui |
| coûts × 1.25 | coûts | +0.37 | oui |
| coûts × 1.5 | coûts | +0.37 | oui |
| slippage + 2.0 bp | coûts | +0.36 | oui |
| entrée retardée d'1 barre | exécution | +0.39 | oui |
| sortie retardée d'1 barre | exécution | +0.40 | oui |
| signal bruité (5%) | signal | +0.44 | oui |
| sans les 5% meilleurs trades | dépendance | -0.36 | non |
| sans les 10% meilleurs trades | dépendance | -0.44 | non |

## 10. Monte Carlo
Bootstrap par blocs de 21 jours (2000 chemins) : drawdown max médian -19.6%, 5e centile -32.7% ; CAGR médian 2.6% [0.1% ; 5.0%] ; P(perte) 4.1%. P(drawdown au-delà de) : 10% → 100.0%, 20% → 46.9%, 25% → 20.6%, 35% → 3.2%, 50% → 0.1%.

Rééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : série perdante médiane 10 trades, 95e centile 14 ; P(perte) 0.7%. (Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)

## 11. Significativité statistique
Sharpe déflaté **0.000** sur 1133 essais cumulés (Sharpe attendu du meilleur essai par chance : +2.66) — indistinguishable from selection luck. PBO de la grille : 0.08. Reality Check / SPA sur les 24 stratégies de la classe : p = 0.039 / 0.034 (meilleure : mtf_momentum).

## 12. Capacité
Edge net moyen +95.4 bp par trade. Moitié de l'edge perdue en impact vers n/a, edge nul vers n/a (loi en racine carrée, coefficient 1).

## 13. Coûts
Modèle : 1.50 bp/côté (comm 0.5, demi-spread 0.5, slippage 0.5), portage 0.0% long / 1.0% short. Part des coûts dans le résultat brut : 2.0%. Sharpe avec coûts × 1,5 : +0.37.

## 14. Drawdown
Recherche : max -20.3%, moyen -7.0%, plus long passage sous l'eau 1503 jours. Walk-forward OOS : max -24.2%.

## 15. Dépendance aux régimes (sur l'OOS walk-forward)
- **direction** : bear Sharpe +0.54 (21.1% des jours) ; bull Sharpe +0.45 (61.8% des jours) ; sideways Sharpe +0.69 (17.1% des jours)
- **volatility** : high_vol Sharpe +0.21 (26.3% des jours) ; low_vol Sharpe +1.15 (31.8% des jours) ; normal_vol Sharpe +0.54 (41.9% des jours)
- **crisis** : no_crisis Sharpe +0.51 (100.0% des jours)
- **character** : mean_reverting Sharpe +0.55 (29.6% des jours) ; neutral Sharpe +0.78 (39.6% des jours) ; trending Sharpe +0.10 (30.8% des jours)

Dépendance détectée : aucune concentration > 80 % du PnL. Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.

## 16. Risque de sur-apprentissage
1133 essais enregistrés dans la base ; grille de 5 configurations déclarée avant exécution ; stabilité des paramètres 64.7% ; PBO 0.08 ; ratio OOS/IS +1.38.

## 17. Exigences pour une mise en œuvre réelle
- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;
- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;
- 45 trades / an sur la classe ; exposition moyenne 95.2% ;
- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.

## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)
Non simulée.

## 19. Conditions d'échec
Attendues a priori : Krachs de momentum (2009), marchés plats.

Observées sur l'OOS : aucun régime à Sharpe négatif.

## 20. Décision de recherche
**PROMISING**. - Sharpe déflaté 0.00 sur 1133 essais (< 0.9) - P(drawdown > 25 %) = 21% au Monte Carlo (> 10%)

Score interne (organise la file de recherche ; **n'est pas une prévision de performance**) : edge 0.51, robustness 0.86, oos_stability 0.76, drawdown 0.35, cost_sensitivity 0.96, parameter_stability 0.65, capacity 0.50, regime_diversity 1.00, statistical_confidence 0.00, composite 0.62
