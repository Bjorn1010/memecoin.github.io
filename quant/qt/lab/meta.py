"""Simple model vs ML filter (meta-labeling), compared out of sample.

The primary signal keeps deciding the side. The ML model only estimates
P(trade successful | features at the signal bar) and skips trades below a threshold.
It is kept only if it beats "take every trade" out of sample — otherwise the simple
model stays.

Validation is walk-forward by year with an embargo of the longest holding period, so
a trade whose outcome overlaps the test year can never be in the training set (the
overlapping-label leak that makes meta-labeling look brilliant in-sample).

Run only on a primary signal that has passed the research gates: a filter trained on
a signal with no edge learns noise, and its "improvement" is a fitted artefact.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .strategies import rsi, sma
from .simulate import wilder_atr

FEATURES = ["vol_pct", "trend_dist", "ma_slope", "rsi14", "atr_pct", "ret5", "ret20", "dow", "side"]


def entry_features(trades: pd.DataFrame, bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Features known at the close of the signal bar (the bar before entry)."""
    cache = {}
    for s, b in bars.items():
        c = b["close"]
        r = np.log(c).diff()
        vol = r.rolling(20).std()
        f = pd.DataFrame({
            "vol_pct": vol.rolling(252, min_periods=60).rank(pct=True),
            "trend_dist": c / sma(c, 200) - 1,
            "ma_slope": sma(c, 50).pct_change(20),
            "rsi14": rsi(c, 14),
            "atr_pct": wilder_atr(b, 14) / c,
            "ret5": c.pct_change(5),
            "ret20": c.pct_change(20),
            "dow": pd.Series(b.index.dayofweek, index=b.index).astype(float),
        })
        cache[s] = f.shift(1)  # the signal bar is the one before the entry bar
    rows = []
    for _, t in trades.iterrows():
        f = cache[t["symbol"]]
        if t["entry_ts"] not in f.index:
            rows.append({k: np.nan for k in FEATURES})
            continue
        row = f.loc[t["entry_ts"]].to_dict()
        row["side"] = float(t["side"])
        rows.append(row)
    return pd.DataFrame(rows, index=trades.index)


def compare_meta(trades: pd.DataFrame, bars: dict[str, pd.DataFrame], *, min_train: int = 200,
                 threshold: float = 0.5, seed: int = 0) -> dict:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    t = trades.sort_values("entry_ts").reset_index(drop=True)
    X = entry_features(t, bars)
    y = (t["net"] > 0).astype(int)
    ok = X.notna().all(axis=1)
    t, X, y = t[ok].reset_index(drop=True), X[ok].reset_index(drop=True), y[ok].reset_index(drop=True)
    if len(t) < min_train + 50:
        return {"ran": False, "reason": f"{len(t)} trades : trop peu pour entraîner et tester un filtre"}
    embargo = pd.Timedelta(days=int(t["bars"].max() * 1.5) + 1)
    years = sorted(t["entry_ts"].dt.year.unique())
    models = {
        "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=500)),
        "gradient_boosting": lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=150,
                                                                     learning_rate=0.05, random_state=seed),
    }
    taken = {k: [] for k in models}
    baseline = []
    for yr in years:
        test = t["entry_ts"].dt.year == yr
        start = t.loc[test, "entry_ts"].min()
        train = t["exit_ts"] < start - embargo
        if train.sum() < min_train or test.sum() == 0:
            continue
        baseline.append(t.loc[test, "net"])
        for name, make in models.items():
            m = make()
            m.fit(X[train], y[train])
            p = m.predict_proba(X[test])[:, 1]
            taken[name].append(t.loc[test, "net"][p >= threshold])
    if not baseline:
        return {"ran": False, "reason": "pas assez d'années d'entraînement"}
    base = pd.concat(baseline)
    out = {"ran": True, "n_oos_trades": int(len(base)),
           "take_all": {"mean_net": float(base.mean()), "sum_net": float(base.sum()), "n": int(len(base))}}
    for name, parts in taken.items():
        s = pd.concat(parts) if parts else pd.Series(dtype=float)
        out[name] = {"mean_net": float(s.mean()) if len(s) else float("nan"), "sum_net": float(s.sum()),
                     "n": int(len(s)), "share_taken": float(len(s) / len(base))}
    best = max(models, key=lambda k: out[k]["sum_net"])
    # The filter must improve TOTAL net result, not only the average of the trades it
    # keeps: skipping 90 % of trades can raise the average and lower the money made.
    improves = out[best]["sum_net"] > out["take_all"]["sum_net"] and out[best]["mean_net"] > out["take_all"]["mean_net"]
    out["verdict"] = (f"le filtre {best} améliore l'OOS : à valider comme essai supplémentaire" if improves
                      else "le ML n'améliore pas l'OOS : on garde le modèle simple")
    return out
