# Cycle de recherche 002

Protocole `8139517b1c052a74` · marchés `8a5b4fb7113a3918` · code `6e1b507` · 1300 essais enregistrés · 2 min.

## Résultat en une phrase

**Aucune stratégie n'atteint PAPER TEST.** 2 restent PROMISING (elles passent le walk-forward mais échouent à au moins une porte statistique ou de robustesse), toutes les autres sont rejetées.

| décision | nombre |
|---|---|
| REJECTED | 24 |
| PROMISING | 2 |

## Tableau des décisions (stratégie × classe d'actifs)

| stratégie | fx | indices | futures | equities | crypto | metals | commodities | multi |
|---|---|---|---|---|---|---|---|---|
| sma_cross |  |  |  |  | ✗ |  |  |  |
| ema_cross |  |  |  |  | ✗ |  |  |  |
| donchian |  |  |  |  | ✗ |  |  |  |
| tsmom |  |  |  |  | ✗ |  |  |  |
| adx_trend |  |  |  |  | ✗ |  |  |  |
| rsi2 |  |  |  |  | ✗ |  |  |  |
| rsi2_trend |  |  |  |  | ✗ |  |  |  |
| bollinger_reversion |  |  |  |  | ✗ |  |  |  |
| pullback |  |  |  |  | ✗ |  |  |  |
| ibs |  |  |  |  | ✗ |  |  |  |
| vol_breakout |  |  |  |  | ✗ |  |  |  |
| nr7 |  |  |  |  | ✗ |  |  |  |
| prev_hl_breakout |  |  |  |  | ✗ |  |  |  |
| roc_accel |  |  |  |  | ✗ |  |  |  |
| mtf_momentum |  |  |  |  | ✗ |  |  |  |
| xs_momentum |  |  |  |  | ✗ |  |  |  |
| squeeze_breakout |  |  |  |  | ✗ |  |  |  |
| atr_breakout |  |  |  |  | ✗ |  |  |  |
| market_structure |  |  |  |  | ✗ |  |  |  |
| liquidity_sweep |  |  |  |  | ✗ |  |  |  |
| rejection |  |  |  |  | ✗ |  |  |  |
| volume_spike |  |  |  |  | ✗ |  |  |  |
| volume_divergence |  |  |  |  | ✗ |  |  |  |
| pairs |  |  |  |  | ✗ |  |  |  |
| mr_equity_basket |  |  |  |  |  |  |  | ◐ +0.48 |
| trend_multiclass |  |  |  |  |  |  |  | ◐ +0.36 |

✗ REJECTED · ◐ PROMISING · ● PAPER TEST · — non applicable · chiffre = Sharpe walk-forward OOS après coûts.

## Le meilleur de N : Reality Check (White) et SPA (Hansen)

| classe | stratégies | p RC | p SPA | meilleure | t |
|---|---|---|---|---|---|
| multi | 2 | 0.010 | 0.010 | mr_equity_basket | +2.74 |
| _global | 2 | 0.010 | 0.010 | multi:mr_equity_basket | +2.74 |

Lecture : p > 0,05 = le meilleur résultat de la classe est compatible avec ce que la recherche du meilleur parmi N stratégies sans edge produirait par chance.

## Survivants de la première porte

| classe | stratégie | config | Sharpe WF | robustesse | DSR | PBO | P(DD>25 %) | décision | raison principale |
|---|---|---|---|---|---|---|---|---|---|
| multi | [mr_equity_basket](candidates/multi__mr_equity_basket.md) | {'members': (('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures'))} | +0.48 | 62.5% | 0.00 | n/a | 4.2% | PROMISING | robustesse 62% (< 70%) |
| multi | [trend_multiclass](candidates/multi__trend_multiclass.md) | {'members': (('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities'))} | +0.36 | 75.0% | 0.00 | n/a | 16.6% | PROMISING | Sharpe déflaté 0.00 sur 1300 essais (< 0.9) |

## Ensemble

Pool : PROMISING (exploratoire), 2 stratégies ; retenues pour diversification (|corrélation| < 0,7) : 2. Flux = walk-forward OOS (période de recherche).

| schéma | Sharpe | CAGR | volatilité | drawdown max |
|---|---|---|---|---|
| equal_weight | +0.50 | 2.1% | 4.3% | -9.3% |
| inverse_vol | +0.51 | 2.1% | 4.2% | -9.2% |
| risk_parity | +0.50 | 2.1% | 4.2% | -9.2% |

Ratio de diversification (inverse-vol) : 1.41. Corrélation moyenne entre membres : 0.02.

## Dimensionnement

Sur multi/mr_equity_basket (flux walk-forward OOS, signal inchangé) :

| méthode | Sharpe | CAGR | drawdown max | levier moyen |
|---|---|---|---|---|
| fixed_fractional | +0.48 | 3.0% | -18.1% | 1.00 |
| volatility_target | +0.43 | 4.5% | -37.0% | 1.90 |
| fractional_kelly | +0.33 | 3.5% | -29.5% | 1.81 |

ATR / volatilité par instrument et parité de risque entre instruments sont déjà appliqués dans le flux unitaire (chaque instrument dimensionné à 10 % de vol, pondération égale en risque). Kelly plein non testé : il sur-parie dès que l'edge est mal estimé.

## Machine learning / méta-labeling

Non exécuté : aucun signal primaire n'a atteint PAPER TEST. Un filtre ML entraîné sur un signal sans edge validé apprend le bruit, et son « amélioration » serait un artefact ajusté. Le code (`qt/lab/meta.py`, régression logistique vs gradient boosting, walk-forward purgé) est prêt.

## Données

| classe | instrument | début | années | note | problèmes |
|---|---|---|---|---|---|
| fx | EURUSD=X | 2003-12-01 | 22.84 | B | 67 barres OHLC incohérentes (réparées : high/low recalculés); 2 trous de plus de 5 jours (max 18) |
| fx | GBPUSD=X | 2003-12-01 | 22.84 | A | 50 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 6) |
| fx | USDJPY=X | 1996-10-30 | 29.92 | B | 162 barres OHLC incohérentes (réparées : high/low recalculés); 2 trous de plus de 5 jours (max 18) |
| fx | AUDUSD=X | 2006-05-16 | 20.38 | B | 94 barres OHLC incohérentes (réparées : high/low recalculés); 1 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| fx | USDCAD=X | 2003-09-17 | 23.04 | A | 43 barres OHLC incohérentes (réparées : high/low recalculés); 1 barres le week-end sur un marché fermé le week-end |
| fx | USDCHF=X | 2003-09-17 | 23.04 | B | 63 barres OHLC incohérentes (réparées : high/low recalculés); 1 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| fx | NZDUSD=X | 2003-12-01 | 22.84 | B | 304 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 6) |
| indices | SPY | 1993-01-29 | 33.67 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| indices | QQQ | 1999-03-10 | 27.56 | A | 1 trous de plus de 5 jours (max 7) |
| indices | DIA | 1998-01-20 | 28.7 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| indices | IWM | 2000-05-26 | 26.35 | A | 1 trous de plus de 5 jours (max 7) |
| indices | EWG | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7); 1 séquences de ≥ 5 clôtures identiques |
| indices | EWU | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7); 3 séquences de ≥ 5 clôtures identiques |
| indices | EWJ | 1996-03-18 | 30.54 | A | 1 trous de plus de 5 jours (max 7) |
| indices | FEZ | 2002-10-21 | 23.95 | A | — |
| futures | ES=F | 2000-09-18 | 26.04 | C | 73 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 10 barres OHLC incohérentes (réparées : high/low recalculés) |
| futures | NQ=F | 2000-09-18 | 26.04 | C | 191 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 23 barres OHLC incohérentes (réparées : high/low recalculés) |
| futures | YM=F | 2002-04-05 | 24.49 | C | 57 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables); 26 barres OHLC incohérentes (réparées : high/low recalculés) |
| futures | RTY=F | 2017-07-10 | 9.23 | C | 40 jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables) |
| futures | ZN=F | 2000-09-21 | 26.03 | A | 20 barres OHLC incohérentes (réparées : high/low recalculés); 1 trous de plus de 5 jours (max 12) |
| futures | ZB=F | 2000-09-21 | 26.03 | A | 10 barres OHLC incohérentes (réparées : high/low recalculés) |
| equities | XLK | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| equities | XLF | 1998-12-22 | 27.78 | B | 1 trous de plus de 5 jours (max 7); 3 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| equities | XLE | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| equities | XLV | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| equities | XLI | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| equities | XLY | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| equities | XLP | 1998-12-22 | 27.78 | B | 1 trous de plus de 5 jours (max 7); 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| equities | XLU | 1998-12-22 | 27.78 | B | 1 trous de plus de 5 jours (max 7); 1 ticks suspects (saut > 10 écarts robustes annulé le lendemain) |
| equities | XLB | 1998-12-22 | 27.78 | A | 1 trous de plus de 5 jours (max 7) |
| crypto | BTCUSDT | 2017-08-17 | 9.12 | C | ouverture périmée : ouverture = clôture de la veille dans 67% des séances |
| crypto | ETHUSDT | 2017-08-17 | 9.12 | C | ouverture périmée : ouverture = clôture de la veille dans 39% des séances |
| crypto | LTCUSDT | 2017-12-13 | 8.8 | C | ouverture périmée : ouverture = clôture de la veille dans 42% des séances |
| crypto | XRPUSDT | 2018-05-04 | 8.41 | C | ouverture périmée : ouverture = clôture de la veille dans 40% des séances |
| metals | GLD | 2004-11-18 | 21.87 | A | — |
| metals | SLV | 2006-04-28 | 20.43 | A | — |
| metals | PPLT | 2010-01-08 | 16.73 | A | — |
| metals | CPER | 2011-11-15 | 14.88 | C | 2 ticks suspects (saut > 10 écarts robustes annulé le lendemain); 6 séquences de ≥ 5 clôtures identiques |
| commodities | USO | 2006-04-10 | 20.48 | A | — |
| commodities | UNG | 2007-04-18 | 19.46 | A | — |
| commodities | DBA | 2007-01-05 | 19.74 | A | — |
| commodities | DBC | 2006-02-06 | 20.65 | A | — |
| commodities | DBB | 2007-01-05 | 19.74 | A | — |

## Hypothèses différées

- **opening_range_breakout** — exige de l'intraday sur plusieurs années ; Yahoo ne fournit que 60 jours en 5 minutes. Recherche intraday antérieure de ce dépôt (journal/RAPPORT_DAY_TRADING.md) : non rentable après coûts.
- **session_breakout** — exige des données FX intraday horodatées par session (Dukascopy) non encore intégrées.
- **factor_model** — exige des fondamentaux point-in-time ; les sources gratuites ne les fournissent pas sans biais de survie et de révision.
