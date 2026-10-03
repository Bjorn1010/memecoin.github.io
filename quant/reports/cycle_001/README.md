# Cycle de recherche 001

Protocole `8139517b1c052a74` · marchés `b46a80343adc21cf` · code `6e1b507` · 1133 essais enregistrés · 13 min.

> **Notes de reprise (ajoutées à la main).** Le cycle a planté pendant la validation (bruit de signal
> sur les stratégies de portefeuille) puis a été repris au commit `6e1b507` avec la configuration de
> marchés figée du cycle 1 (`configs/markets_cycle1.yaml`), sans réenregistrer ses essais. La reprise
> a aussi exécuté les deux hypothèses combinées pré-enregistrées pour le cycle 2 (colonne « multi ») :
> elles apparaissent donc dans ce rapport et ont été comptées une fois de plus comme essais (sens
> conservateur). Le membre crypto de `trend_multiclass` utilisait ici les données Yahoo invalidées ;
> la version qui compte est celle du cycle 2 (Binance).

## Résultat en une phrase

**Aucune stratégie n'atteint PAPER TEST.** 42 restent PROMISING (elles passent le walk-forward mais échouent à au moins une porte statistique ou de robustesse), toutes les autres sont rejetées.

| décision | nombre |
|---|---|
| REJECTED | 125 |
| PROMISING | 42 |

## Tableau des décisions (stratégie × classe d'actifs)

| stratégie | fx | indices | futures | equities | crypto | metals | commodities | multi |
|---|---|---|---|---|---|---|---|---|
| sma_cross | ◐ +0.08 | ◐ +0.16 | ◐ +0.13 | ◐ +0.39 | ✗ +0.13 | ✗ -0.03 | ✗ -0.01 |  |
| ema_cross | ✗ -0.03 | ◐ +0.12 | ✗ -0.03 | ◐ +0.22 | ✗ +0.20 | ◐ +0.00 | ✗ -0.08 |  |
| donchian | ✗ -0.07 | ✗ -0.16 | ✗ -0.03 | ✗ +0.04 | ✗ +0.98 | ✗ -0.05 | ◐ +0.27 |  |
| tsmom | ✗ -0.11 | ✗ -0.01 | ◐ +0.03 | ◐ +0.51 | ✗ +0.33 | ✗ -0.09 | ✗ +0.22 |  |
| adx_trend | ✗ -0.09 | ✗ -0.28 | ✗ -0.28 | ✗ -0.43 | ✗ +0.53 | ✗ +0.20 | ✗ -0.14 |  |
| rsi2 | ✗ -0.15 | ◐ +0.29 | ◐ +0.24 | ◐ +0.35 | ✗ +0.09 | ✗ -0.20 | ✗ -0.72 |  |
| rsi2_trend | ✗ -0.11 | ◐ +0.32 | ◐ +0.47 | ◐ +0.48 | ✗ -0.43 | ✗ -0.34 | ✗ -0.24 |  |
| bollinger_reversion | ✗ -0.12 | ◐ +0.36 | ◐ +0.09 | ◐ +0.50 | ✗ -0.74 | ◐ +0.14 | ✗ -0.15 |  |
| pullback | ✗ -0.13 | ◐ +0.25 | ◐ +0.43 | ◐ +0.47 | ✗ -0.12 | ✗ -0.43 | ✗ -0.37 |  |
| ibs | ✗ -0.58 | ✗ -0.02 | ◐ +0.28 | ◐ +0.37 | ✗ -1.17 | ✗ -0.34 | ✗ -0.65 |  |
| vol_breakout | ✗ -4.53 | ✗ -1.07 | ✗ -0.65 | ✗ -0.80 | ✗ +3.70 | ✗ +0.37 | ✗ -0.78 |  |
| nr7 | ✗ -0.17 | ✗ -0.91 | ✗ -0.74 | ✗ -0.84 | ✗ +2.48 | ✗ -0.21 | ✗ -0.10 |  |
| prev_hl_breakout | ✗ -0.15 | ✗ -0.84 | ✗ -0.23 | ✗ -1.00 | ✗ +2.74 | ✗ -0.19 | ✗ -0.08 |  |
| roc_accel | ✗ -0.14 | ✗ -0.43 | ✗ -0.22 | ✗ -0.38 | ✗ +1.09 | ✗ -0.05 | ◐ +0.24 |  |
| mtf_momentum | ✗ -0.05 | ◐ +0.41 | ◐ +0.44 | ◐ +0.63 | ✗ -0.13 | ✗ +0.10 | ✗ -0.06 |  |
| xs_momentum | ✗ -0.16 | ✗ -0.46 | ✗ -0.14 | ✗ -0.22 | ✗ | ✗ -0.31 | ◐ +0.04 |  |
| squeeze_breakout | ✗ -0.25 | ✗ -0.27 | ◐ +0.07 | ✗ -0.24 | ✗ +0.42 | ✗ -0.28 | ✗ -0.02 |  |
| atr_breakout | ✗ +0.04 | ✗ -0.33 | ✗ -0.42 | ✗ -0.20 | ✗ +0.24 | ◐ +0.18 | ◐ +0.51 |  |
| market_structure | ✗ -0.08 | ✗ -0.09 | ✗ -0.07 | ✗ +0.04 | ✗ -0.52 | ✗ -0.42 | ✗ +0.02 |  |
| liquidity_sweep | ✗ -0.23 | ✗ -0.07 | ✗ -0.11 | ◐ +0.10 | ✗ -0.90 | ✗ -0.14 | ✗ -0.47 |  |
| rejection | ✗ +0.02 | ◐ +0.06 | ✗ -0.13 | ✗ +0.10 | ✗ -0.32 | ◐ +0.39 | ✗ +0.05 |  |
| volume_spike | — | ✗ -0.15 | ◐ +0.05 | ✗ -0.23 | ✗ -0.07 | ◐ +0.68 | ✗ -0.02 |  |
| volume_divergence | — | ◐ +0.25 | ◐ +0.01 | ✗ -0.02 | ✗ -0.98 | ✗ -0.10 | ✗ -0.39 |  |
| pairs | ✗ -0.40 | ✗ -0.33 |  | ✗ -0.37 | ✗ | ✗ -0.43 | ✗ +0.93 |  |
| mr_equity_basket |  |  |  |  |  |  |  | ◐ +0.48 |
| trend_multiclass |  |  |  |  |  |  |  | ◐ +0.41 |

✗ REJECTED · ◐ PROMISING · ● PAPER TEST · — non applicable · chiffre = Sharpe walk-forward OOS après coûts.

## Le meilleur de N : Reality Check (White) et SPA (Hansen)

| classe | stratégies | p RC | p SPA | meilleure | t |
|---|---|---|---|---|---|
| fx | 22 | 0.999 | 1.000 | sma_cross | +0.35 |
| indices | 24 | 0.133 | 0.154 | mtf_momentum | +2.29 |
| futures | 23 | 0.210 | 0.276 | rsi2_trend | +2.08 |
| equities | 24 | 0.039 | 0.034 | mtf_momentum | +2.88 |
| crypto | 22 | 0.004 | 0.000 | vol_breakout | +6.33 |
| metals | 24 | 0.579 | 0.135 | volume_spike | +2.43 |
| commodities | 24 | 0.067 | 0.120 | pairs | +2.51 |
| multi | 2 | 0.010 | 0.010 | mr_equity_basket | +2.74 |
| _global | 165 | 0.182 | 0.001 | crypto:vol_breakout | +4.53 |

Lecture : p > 0,05 = le meilleur résultat de la classe est compatible avec ce que la recherche du meilleur parmi N stratégies sans edge produirait par chance.

## Survivants de la première porte

| classe | stratégie | config | Sharpe WF | robustesse | DSR | PBO | P(DD>25 %) | décision | raison principale |
|---|---|---|---|---|---|---|---|---|---|
| metals | [volume_spike](candidates/metals__volume_spike.md) | {'k': 1.5, 'hold': 1} | +0.68 | 82.4% | 0.00 | 0.25 | 0.0% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [rsi2_trend](candidates/equities__rsi2_trend.md) | {'threshold': 5, 'trend': 200} | +0.48 | 90.0% | 0.00 | 0.55 | 0.0% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [mtf_momentum](candidates/equities__mtf_momentum.md) | {'long': 250, 'short': 3, 'hold': 10} | +0.63 | 92.3% | 0.00 | 0.12 | 3.9% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| commodities | [atr_breakout](candidates/commodities__atr_breakout.md) | {'k': 2.0, 'hold': 5} | +0.51 | 80.0% | 0.00 | 0.15 | 0.0% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| metals | [rejection](candidates/metals__rejection.md) | {'wick': 0.5, 'lookback': 20, 'hold': 5} | +0.39 | 88.5% | 0.00 | 0.14 | 0.1% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [bollinger_reversion](candidates/equities__bollinger_reversion.md) | {'n': 10, 'k': 1.5} | +0.50 | 90.0% | 0.00 | 0.43 | 1.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [tsmom](candidates/equities__tsmom.md) | {'lookback': 252} | +0.51 | 85.7% | 0.00 | 0.08 | 20.6% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [rsi2](candidates/futures__rsi2.md) | {'length': 4, 'threshold': 5} | +0.24 | 90.0% | 0.00 | 0.39 | 0.0% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [pullback](candidates/equities__pullback.md) | {'lookback': 3, 'trend': 200, 'max_hold': 10} | +0.47 | 92.3% | 0.00 | 0.23 | 0.6% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| multi | [mr_equity_basket](candidates/multi__mr_equity_basket.md) | {'members': (('rsi2_trend', 'indices'), ('bollinger_reversion', 'indices'), ('pullback', 'indices'), ('ibs', 'indices'), ('rsi2_trend', 'equities'), ('bollinger_reversion', 'equities'), ('pullback', 'equities'), ('ibs', 'equities'), ('rsi2_trend', 'futures'), ('bollinger_reversion', 'futures'), ('pullback', 'futures'), ('ibs', 'futures'))} | +0.48 | 62.5% | 0.00 | n/a | 4.2% | PROMISING | robustesse 62% (< 70%) |
| futures | [mtf_momentum](candidates/futures__mtf_momentum.md) | {'long': 250, 'short': 3, 'hold': 10} | +0.44 | 92.3% | 0.00 | 0.37 | 6.7% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| multi | [trend_multiclass](candidates/multi__trend_multiclass.md) | {'members': (('tsmom', 'fx'), ('sma_cross', 'fx'), ('donchian', 'fx'), ('tsmom', 'indices'), ('sma_cross', 'indices'), ('donchian', 'indices'), ('tsmom', 'futures'), ('sma_cross', 'futures'), ('donchian', 'futures'), ('tsmom', 'equities'), ('sma_cross', 'equities'), ('donchian', 'equities'), ('tsmom', 'crypto'), ('sma_cross', 'crypto'), ('donchian', 'crypto'), ('tsmom', 'metals'), ('sma_cross', 'metals'), ('donchian', 'metals'), ('tsmom', 'commodities'), ('sma_cross', 'commodities'), ('donchian', 'commodities'))} | +0.41 | 75.0% | 0.00 | n/a | 12.9% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [bollinger_reversion](candidates/indices__bollinger_reversion.md) | {'n': 10, 'k': 1.5} | +0.36 | 90.0% | 0.00 | 0.08 | 8.5% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| metals | [atr_breakout](candidates/metals__atr_breakout.md) | {'k': 1.5, 'hold': 5} | +0.18 | 80.0% | 0.00 | 0.25 | 0.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [rsi2_trend](candidates/indices__rsi2_trend.md) | {'threshold': 15, 'trend': 200} | +0.32 | 90.0% | 0.00 | 0.77 | 0.1% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| metals | [bollinger_reversion](candidates/metals__bollinger_reversion.md) | {'n': 10, 'k': 2.5} | +0.14 | 55.0% | 0.00 | 0.25 | 0.0% | PROMISING | robustesse 55% (< 70%) |
| futures | [rsi2_trend](candidates/futures__rsi2_trend.md) | {'threshold': 15, 'trend': 100} | +0.47 | 75.0% | 0.00 | 0.44 | 0.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [mtf_momentum](candidates/indices__mtf_momentum.md) | {'long': 250, 'short': 10, 'hold': 10} | +0.41 | 92.3% | 0.00 | 0.58 | 6.3% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [sma_cross](candidates/equities__sma_cross.md) | {'fast': 100, 'slow': 200} | +0.39 | 90.0% | 0.00 | 0.19 | 10.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [rsi2](candidates/equities__rsi2.md) | {'length': 2, 'threshold': 10} | +0.35 | 90.0% | 0.00 | 0.62 | 0.9% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| commodities | [roc_accel](candidates/commodities__roc_accel.md) | {'n': 60, 'm': 10} | +0.24 | 85.0% | 0.00 | 0.38 | 1.0% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [ibs](candidates/futures__ibs.md) | {'threshold': 0.3, 'hold': 3} | +0.28 | 75.0% | 0.00 | 0.13 | 17.4% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [pullback](candidates/futures__pullback.md) | {'lookback': 3, 'trend': 200, 'max_hold': 10} | +0.43 | 84.6% | 0.00 | 0.69 | 2.5% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [ibs](candidates/equities__ibs.md) | {'threshold': 0.1, 'hold': 3} | +0.37 | 85.0% | 0.00 | 0.18 | 1.4% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [ema_cross](candidates/equities__ema_cross.md) | {'fast': 50, 'slow': 150} | +0.22 | 90.0% | 0.00 | 0.00 | 26.9% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [pullback](candidates/indices__pullback.md) | {'lookback': 10, 'trend': 200, 'max_hold': 10} | +0.25 | 92.3% | 0.00 | 0.04 | 0.1% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [bollinger_reversion](candidates/futures__bollinger_reversion.md) | {'n': 10, 'k': 2.0} | +0.09 | 80.0% | 0.00 | 0.40 | 0.5% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [sma_cross](candidates/futures__sma_cross.md) | {'fast': 100, 'slow': 300} | +0.13 | 85.0% | 0.00 | 0.64 | 28.1% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| commodities | [donchian](candidates/commodities__donchian.md) | {'entry': 55, 'exit': 20, 'stop_atr': 2.0} | +0.27 | 92.3% | 0.00 | 0.58 | 0.5% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [rsi2](candidates/indices__rsi2.md) | {'length': 3, 'threshold': 15} | +0.29 | 75.0% | 0.00 | 0.22 | 2.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [volume_divergence](candidates/futures__volume_divergence.md) | {'lookback': 10, 'hold': 3} | +0.01 | 70.0% | 0.00 | 0.23 | 7.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [ema_cross](candidates/indices__ema_cross.md) | {'fast': 50, 'slow': 150} | +0.12 | 90.0% | 0.00 | 0.00 | 43.5% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [sma_cross](candidates/indices__sma_cross.md) | {'fast': 100, 'slow': 300} | +0.16 | 90.0% | 0.00 | 0.31 | 25.7% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| equities | [liquidity_sweep](candidates/equities__liquidity_sweep.md) | {'lookback': 10, 'hold': 5} | +0.10 | 65.0% | 0.00 | 0.27 | 10.0% | PROMISING | robustesse 65% (< 70%) |
| indices | [rejection](candidates/indices__rejection.md) | {'wick': 0.66, 'lookback': 20, 'hold': 5} | +0.06 | 65.4% | 0.00 | 0.19 | 0.1% | PROMISING | robustesse 65% (< 70%) |
| futures | [squeeze_breakout](candidates/futures__squeeze_breakout.md) | {'n': 20, 'quantile': 0.2, 'window': 126, 'hold': 10} | +0.07 | 43.8% | 0.00 | 0.03 | 1.5% | PROMISING | robustesse 44% (< 70%) |
| futures | [tsmom](candidates/futures__tsmom.md) | {'lookback': 378} | +0.03 | 71.4% | 0.00 | 0.45 | 23.2% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| indices | [volume_divergence](candidates/indices__volume_divergence.md) | {'lookback': 10, 'hold': 3} | +0.25 | 55.0% | 0.00 | 0.04 | 12.0% | PROMISING | robustesse 55% (< 70%) |
| metals | [ema_cross](candidates/metals__ema_cross.md) | {'fast': 50, 'slow': 150} | +0.00 | 85.0% | 0.00 | 0.40 | 64.0% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |
| futures | [volume_spike](candidates/futures__volume_spike.md) | {'k': 2.0, 'hold': 5} | +0.05 | 25.0% | 0.00 | 0.07 | 0.2% | PROMISING | robustesse 25% (< 70%) |
| fx | [sma_cross](candidates/fx__sma_cross.md) | {'fast': 50, 'slow': 100} | +0.08 | 60.0% | 0.00 | 0.10 | 75.4% | PROMISING | robustesse 60% (< 70%) |
| commodities | [xs_momentum](candidates/commodities__xs_momentum.md) | {'lookback': 252, 'skip': 0} | +0.04 | 76.5% | 0.00 | 0.35 | 83.5% | PROMISING | Sharpe déflaté 0.00 sur 1133 essais (< 0.9) |

## Invalidations (vérification indépendante des données)

| classe | stratégie | décision du protocole | décision finale | raison |
|---|---|---|---|---|
| crypto | sma_cross | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | ema_cross | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | donchian | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | tsmom | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | adx_trend | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | rsi2 | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | rsi2_trend | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | bollinger_reversion | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | pullback | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | ibs | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | vol_breakout | PAPER TEST | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | nr7 | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | prev_hl_breakout | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | roc_accel | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | mtf_momentum | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | xs_momentum | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | squeeze_breakout | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | atr_breakout | PROMISING | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | market_structure | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | liquidity_sweep | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | rejection | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | volume_spike | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | volume_divergence | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |
| crypto | pairs | REJECTED | REJECTED | INVALIDÉ (données) : données Yahoo crypto invalidées : les hauts/bas journaliers de l'agrégat ne sont pas ceux d'une plateforme négociable. vol_breakout affichait un Sharpe walk-forward de +3,70 et a passé le test et le holdout ; sur Binance (barres journalières et rejeu horaire, scripts/verify_intraday_breakout.py) la même règle donne −2,1 à +0,7. Classe refaite sur Binance au cycle 2. |

Ces stratégies ont passé (ou auraient pu passer) les portes statistiques sur des données fausses. C'est la démonstration que les tests statistiques ne protègent pas d'un problème de données : seule une vérification sur une source indépendante l'a révélé.

## Ensemble

Pool : PROMISING (exploratoire), 42 stratégies ; retenues pour diversification (|corrélation| < 0,7) : 37. Flux = walk-forward OOS (période de recherche).

| schéma | Sharpe | CAGR | volatilité | drawdown max |
|---|---|---|---|---|
| equal_weight | +0.59 | 1.0% | 1.7% | -3.4% |
| inverse_vol | +0.64 | 1.1% | 1.8% | -2.7% |
| risk_parity | +0.57 | 0.9% | 1.6% | -2.4% |

Ratio de diversification (inverse-vol) : 2.14. Corrélation moyenne entre membres : 0.10.

## Dimensionnement

Sur metals/volume_spike (flux walk-forward OOS, signal inchangé) :

| méthode | Sharpe | CAGR | drawdown max | levier moyen |
|---|---|---|---|---|
| fixed_fractional | +0.68 | 2.6% | -8.6% | 1.00 |
| volatility_target | +0.61 | 5.1% | -23.5% | 2.57 |
| fractional_kelly | +0.33 | 2.6% | -26.0% | 1.72 |

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
| crypto | BTC-USD | 2014-09-17 | 12.04 | A | — |
| crypto | ETH-USD | 2017-11-09 | 8.9 | A | — |
| crypto | LTC-USD | 2014-09-17 | 12.04 | A | — |
| crypto | XRP-USD | 2017-11-09 | 8.9 | A | — |
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
