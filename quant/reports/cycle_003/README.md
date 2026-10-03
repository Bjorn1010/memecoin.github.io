# Cycle de recherche 003

Protocole `a5638563517b1072` · marchés `8a5b4fb7113a3918` · code `ec09816` · 1301 essais enregistrés · 2 min.

## Résultat en une phrase

**Aucune stratégie n'atteint PAPER TEST.** 1 restent PROMISING (elles passent le walk-forward mais échouent à au moins une porte statistique ou de robustesse), toutes les autres sont rejetées.

| décision | nombre |
|---|---|
| PROMISING | 1 |

## Tableau des décisions (stratégie × classe d'actifs)

| stratégie | fx | indices | futures | equities | crypto | metals | commodities | multi |
|---|---|---|---|---|---|---|---|---|
| sma_cross |  |  |  |  |  |  |  |  |
| ema_cross |  |  |  |  |  |  |  |  |
| donchian |  |  |  |  |  |  |  |  |
| tsmom |  |  |  |  |  |  |  |  |
| adx_trend |  |  |  |  |  |  |  |  |
| rsi2 |  |  |  |  |  |  |  |  |
| rsi2_trend |  |  |  |  |  |  |  |  |
| bollinger_reversion |  |  |  |  |  |  |  |  |
| pullback |  |  |  |  |  |  |  |  |
| ibs |  |  |  |  |  |  |  |  |
| vol_breakout |  |  |  |  |  |  |  |  |
| nr7 |  |  |  |  |  |  |  |  |
| prev_hl_breakout |  |  |  |  |  |  |  |  |
| roc_accel |  |  |  |  |  |  |  |  |
| mtf_momentum |  |  |  |  |  |  |  |  |
| xs_momentum |  |  |  |  |  |  |  |  |
| squeeze_breakout |  |  |  |  |  |  |  |  |
| atr_breakout |  |  |  |  |  |  |  |  |
| market_structure |  |  |  |  |  |  |  |  |
| liquidity_sweep |  |  |  |  |  |  |  |  |
| rejection |  |  |  |  |  |  |  |  |
| volume_spike |  |  |  |  |  |  |  |  |
| volume_divergence |  |  |  |  |  |  |  |  |
| pairs |  |  |  |  |  |  |  |  |
| mr_equity_basket |  |  |  |  |  |  |  |  |
| trend_multiclass |  |  |  |  |  |  |  |  |
| lab_portfolio_c1 |  |  |  |  |  |  |  | ◐ +0.82 |

✗ REJECTED · ◐ PROMISING · ● PAPER TEST · — non applicable · chiffre = Sharpe walk-forward OOS après coûts.

## Le meilleur de N : Reality Check (White) et SPA (Hansen)

| classe | stratégies | p RC | p SPA | meilleure | t |
|---|---|---|---|---|---|
| multi | 1 | 0.000 | 0.000 | lab_portfolio_c1 | +4.49 |
| _global | 1 | 0.000 | 0.000 | multi:lab_portfolio_c1 | +4.49 |

Lecture : p > 0,05 = le meilleur résultat de la classe est compatible avec ce que la recherche du meilleur parmi N stratégies sans edge produirait par chance.

## Survivants de la première porte

| classe | stratégie | config | Sharpe WF | robustesse | DSR | PBO | P(DD>25 %) | décision | raison principale |
|---|---|---|---|---|---|---|---|---|---|
| multi | [lab_portfolio_c1](candidates/multi__lab_portfolio_c1.md) | {'members': (('sma_cross', 'fx', {'fast': 50, 'slow': 100}), ('sma_cross', 'indices', {'fast': 100, 'slow': 300}), ('ema_cross', 'indices', {'fast': 50, 'slow': 150}), ('rsi2', 'indices', {'length': 3, 'threshold': 15}), ('rsi2_trend', 'indices', {'threshold': 15, 'trend': 200}), ('bollinger_reversion', 'indices', {'n': 10, 'k': 1.5}), ('pullback', 'indices', {'lookback': 10, 'trend': 200, 'max_hold': 10}), ('mtf_momentum', 'indices', {'long': 250, 'short': 10, 'hold': 10}), ('rejection', 'indices', {'wick': 0.66, 'lookback': 20, 'hold': 5}), ('volume_divergence', 'indices', {'lookback': 10, 'hold': 3}), ('sma_cross', 'futures', {'fast': 100, 'slow': 300}), ('tsmom', 'futures', {'lookback': 378}), ('rsi2', 'futures', {'length': 4, 'threshold': 5}), ('rsi2_trend', 'futures', {'threshold': 15, 'trend': 100}), ('bollinger_reversion', 'futures', {'n': 10, 'k': 2.0}), ('pullback', 'futures', {'lookback': 3, 'trend': 200, 'max_hold': 10}), ('ibs', 'futures', {'threshold': 0.3, 'hold': 3}), ('mtf_momentum', 'futures', {'long': 250, 'short': 3, 'hold': 10}), ('squeeze_breakout', 'futures', {'n': 20, 'quantile': 0.2, 'window': 126, 'hold': 10}), ('volume_spike', 'futures', {'k': 2.0, 'hold': 5}), ('volume_divergence', 'futures', {'lookback': 10, 'hold': 3}), ('sma_cross', 'equities', {'fast': 100, 'slow': 200}), ('ema_cross', 'equities', {'fast': 50, 'slow': 150}), ('tsmom', 'equities', {'lookback': 252}), ('rsi2', 'equities', {'length': 2, 'threshold': 10}), ('rsi2_trend', 'equities', {'threshold': 5, 'trend': 200}), ('bollinger_reversion', 'equities', {'n': 10, 'k': 1.5}), ('pullback', 'equities', {'lookback': 3, 'trend': 200, 'max_hold': 10}), ('ibs', 'equities', {'threshold': 0.1, 'hold': 3}), ('mtf_momentum', 'equities', {'long': 250, 'short': 3, 'hold': 10}), ('liquidity_sweep', 'equities', {'lookback': 10, 'hold': 5}), ('ema_cross', 'metals', {'fast': 50, 'slow': 150}), ('bollinger_reversion', 'metals', {'n': 10, 'k': 2.5}), ('atr_breakout', 'metals', {'k': 1.5, 'hold': 5}), ('rejection', 'metals', {'wick': 0.5, 'lookback': 20, 'hold': 5}), ('volume_spike', 'metals', {'k': 1.5, 'hold': 1}), ('donchian', 'commodities', {'entry': 55, 'exit': 20, 'stop_atr': 2.0}), ('roc_accel', 'commodities', {'n': 60, 'm': 10}), ('xs_momentum', 'commodities', {'lookback': 252, 'skip': 0}), ('atr_breakout', 'commodities', {'k': 2.0, 'hold': 5}))} | +0.82 | 75.0% | 0.00 | n/a | 0.2% | PROMISING | test et holdout positifs mais PSR(test+holdout) = 0.75 (< 0.95) |

## Ensemble

Moins de deux survivants : pas d'ensemble à construire.

## Dimensionnement

Sur multi/lab_portfolio_c1 (flux walk-forward OOS, signal inchangé) :

| méthode | Sharpe | CAGR | drawdown max | levier moyen |
|---|---|---|---|---|
| fixed_fractional | +0.82 | 4.0% | -13.7% | 1.00 |
| volatility_target | +0.79 | 8.3% | -30.0% | 2.32 |
| fractional_kelly | +0.72 | 8.4% | -20.8% | 2.34 |

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
