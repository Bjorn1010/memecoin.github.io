"""Strategy decay detection: is the live record still drawn from the backtest's world?

Compares realised trades with the distribution the research produced. Several tests,
because decay shows up in different places — a lower average, a different shape,
a slow drift, worse fills:

* mean: one-sided t-test, live mean below the backtest mean;
* bootstrap band: live mean below the 5th percentile of means of n backtest trades;
* shape: two-sample Kolmogorov-Smirnov;
* drift: one-sided CUSUM on standardised trade results (k = 0.5, h = 6: measured
  2.8 % false alarms over 80 healthy trades, 81 % detection of a half-sigma drop;
  k = 0.25, h = 4 — the first setting tried — raised a false alarm 65 % of the time);
* win rate: one-sided binomial test;
* execution: realised slippage vs the cost model.

The only automatic action is PAUSE. The response to decay is PAUSE → INVESTIGATE →
RESEARCH, never "re-optimise on the last losses": fitting the parameters to the trades
that just lost is the fastest way to fit noise twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

OK, WATCH, PAUSE = "OK", "WATCH", "PAUSE"


@dataclass
class DecayReport:
    status: str
    n_live: int
    checks: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    action: str = ""


def detect_decay(backtest_trades: np.ndarray, live_trades: np.ndarray, *, expected_slippage_bps: float | None = None,
                 live_slippage_bps: np.ndarray | None = None, min_trades: int = 20, alpha: float = 0.01,
                 cusum_h: float = 6.0, cusum_k: float = 0.5, seed: int = 0) -> DecayReport:
    bt = np.asarray(backtest_trades, dtype="float64")
    lv = np.asarray(live_trades, dtype="float64")
    n = len(lv)
    rep = DecayReport(status=OK, n_live=n)
    if n < min_trades:
        rep.status = WATCH if n else OK
        rep.reasons.append(f"{n} trades réels (< {min_trades}) : trop tôt pour conclure")
        rep.action = "continuer à observer"
        return rep
    mu, sd = bt.mean(), bt.std(ddof=1)
    t = stats.ttest_1samp(lv, mu, alternative="less")
    rep.checks["mean_pvalue"] = float(t.pvalue)
    rng = np.random.default_rng(seed)
    means = rng.choice(bt, size=(2000, n), replace=True).mean(axis=1)
    lo = float(np.quantile(means, 0.05))
    rep.checks["live_mean"] = float(lv.mean())
    rep.checks["backtest_mean"] = float(mu)
    rep.checks["band_5pct"] = lo
    ks = stats.ks_2samp(lv, bt)
    rep.checks["ks_pvalue"] = float(ks.pvalue)
    z = (lv - mu) / sd if sd > 0 else np.zeros(n)
    c, cmin = 0.0, 0.0
    for x in z:
        c = min(0.0, c + x + cusum_k)
        cmin = min(cmin, c)
    rep.checks["cusum_min"] = float(cmin)
    p_bt = float((bt > 0).mean())
    wins = int((lv > 0).sum())
    rep.checks["win_rate_live"] = wins / n
    rep.checks["win_rate_backtest"] = p_bt
    rep.checks["win_rate_pvalue"] = float(stats.binomtest(wins, n, p_bt, alternative="less").pvalue)

    hard = []
    if t.pvalue < alpha:
        hard.append(f"moyenne réelle inférieure au backtest (p = {t.pvalue:.4f})")
    if cmin < -cusum_h:
        hard.append(f"dérive CUSUM ({cmin:.1f} < −{cusum_h})")
    if ks.pvalue < alpha:
        hard.append(f"distribution des trades différente (KS p = {ks.pvalue:.4f})")
    soft = []
    if lv.mean() < lo:
        soft.append("moyenne réelle sous le 5e centile attendu")
    if rep.checks["win_rate_pvalue"] < alpha:
        soft.append("taux de réussite significativement plus bas")
    if expected_slippage_bps and live_slippage_bps is not None and len(live_slippage_bps):
        ratio = float(np.mean(live_slippage_bps) / expected_slippage_bps)
        rep.checks["slippage_ratio"] = ratio
        if ratio > 1.5:
            hard.append(f"slippage réel = {ratio:.1f} × le modèle")
    if hard:
        rep.status, rep.reasons = PAUSE, hard + soft
        rep.action = "PAUSE → INVESTIGATE → RESEARCH (aucune ré-optimisation automatique)"
    elif soft:
        rep.status, rep.reasons = WATCH, soft
        rep.action = "surveillance renforcée"
    else:
        rep.action = "rien à signaler"
    return rep
