"""Regime detection — the state variable that decides which alpha is allowed to speak.

Nearly every strategy is regime-conditional. Trend following makes its money in high-
vol trending states and bleeds in quiet ranges; mean reversion does the exact
opposite. A model trained across both without a regime input has to learn to be two
different models at once from the same parameters, and usually settles for being a
mediocre average of the two.

Two implementations, deliberately:

* `regime` — rule-based on *rolling* quantiles. Fully causal, no fitting, no
  parameters to overfit. This is the default.
* `fit_gmm_regimes` — an unsupervised mixture model, refit periodically on an
  expanding window so that the label at time t is produced by a model that only ever
  saw data before t. Slower and heavier, offered for research, never fit in one shot
  on the full sample (which is the standard way this technique is misused).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import log_returns, register, safe_div


@register("regime", description="Causal rule-based volatility and trend regimes", warmup=720, tags=("regime", "core"))
def regimes(bars: pd.DataFrame) -> pd.DataFrame:
    c = bars["close"].astype("float64")
    r = log_returns(c)
    out: dict[str, pd.Series] = {}

    vol = r.ewm(span=168, min_periods=48).std()
    # Percentile of current vol within its own trailing year-ish of history.
    vol_pct = vol.rolling(720, min_periods=168).rank(pct=True)
    out["vol_pct"] = vol_pct
    out["vol_low"] = (vol_pct < 0.33).astype("float64")
    out["vol_high"] = (vol_pct > 0.67).astype("float64")
    # Vol expanding vs contracting: the transition matters more than the level.
    out["vol_expanding"] = (vol > vol.shift(24)).astype("float64")

    fast = c.ewm(span=48, min_periods=24).mean()
    slow = c.ewm(span=336, min_periods=96).mean()
    trend_strength = safe_div(fast - slow, c)
    trend_pct = trend_strength.rolling(720, min_periods=168).rank(pct=True)
    out["trend_strength"] = trend_strength
    out["trend_pct"] = trend_pct
    out["trend_up"] = (trend_pct > 0.67).astype("float64")
    out["trend_down"] = (trend_pct < 0.33).astype("float64")

    # Efficiency ratio (Kaufman): net move over summed absolute moves. Near 1 the
    # market is travelling in a straight line; near 0 it is chopping.
    for w in (24, 72, 168):
        net = (c - c.shift(w)).abs()
        path = c.diff().abs().rolling(w, min_periods=max(w // 4, 3)).sum()
        out[f"efficiency_{w}"] = safe_div(net, path)

    # Composite 2x2 state, encoded as one integer the model can split on directly.
    state = (out["vol_high"] * 2 + out["trend_up"]).where(vol_pct.notna())
    out["state"] = state
    # A cheap "how long have we been here" clock: regime persistence is real and a
    # freshly-changed regime behaves differently from a mature one.
    changed = (state != state.shift(1)).astype("float64")
    out["state_age"] = changed.groupby(changed.cumsum()).cumcount().astype("float64")
    return pd.DataFrame(out, index=bars.index)


def fit_gmm_regimes(
    bars: pd.DataFrame,
    n_states: int = 3,
    refit_every: int = 720,
    min_train: int = 2000,
    random_state: int = 0,
) -> pd.DataFrame:
    """Unsupervised regime labels from a Gaussian mixture, fit only on past data.

    At each refit point the model is trained on everything strictly before that point
    and then used to label the following `refit_every` bars. This is slower than one
    global fit by a factor of (n_bars / refit_every), and that cost is the entire
    point: a single global fit leaks the future into every label it produces.
    """
    from sklearn.mixture import GaussianMixture

    c = bars["close"].astype("float64")
    r = log_returns(c)
    feats = pd.DataFrame(
        {
            "ret": r,
            "vol": r.rolling(24, min_periods=12).std(),
            "absret": r.abs().rolling(24, min_periods=12).mean(),
            "trend": safe_div(c.ewm(span=48, min_periods=24).mean() - c.ewm(span=336, min_periods=96).mean(), c),
        }
    ).replace([np.inf, -np.inf], np.nan)

    labels = pd.Series(np.nan, index=bars.index, dtype="float64")
    probs = pd.DataFrame(np.nan, index=bars.index, columns=[f"p{i}" for i in range(n_states)])

    n = len(feats)
    start = max(min_train, 100)
    for anchor in range(start, n, refit_every):
        train = feats.iloc[:anchor].dropna()
        if len(train) < min_train // 2:
            continue
        gm = GaussianMixture(n_components=n_states, covariance_type="full", random_state=random_state)
        gm.fit(train.to_numpy())
        block = feats.iloc[anchor : anchor + refit_every]
        valid = block.dropna()
        if valid.empty:
            continue
        pred = gm.predict(valid.to_numpy())
        proba = gm.predict_proba(valid.to_numpy())
        labels.loc[valid.index] = pred.astype("float64")
        probs.loc[valid.index] = proba

    out = probs.copy()
    out["gmm_state"] = labels
    return out
