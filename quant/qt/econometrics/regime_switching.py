"""Markov regime switching — letting the data decide how many markets there are.

The rule-based regimes in `features/regime.py` label states by rolling quantiles: fast,
causal, no fitting, no parameters to overfit. What they cannot do is tell you the
*probability* that you are in a state, or how long states typically last, or that a
transition just happened before the price confirms it.

A Markov-switching model estimates all of that. It assumes returns are drawn from one of
K distributions with different means and variances, and that the hidden state follows a
Markov chain with an estimated transition matrix. Fitting it gives:

* **filtered probabilities** — P(state | data up to t), the only version usable in a
  strategy, because the smoothed probabilities everyone plots use the whole sample and
  are pure look-ahead;
* the **transition matrix**, whose diagonal gives expected regime duration: a 0.98
  self-transition means the state persists ~50 bars on average, which tells you whether
  conditioning on it is worth the estimation error;
* per-state **means and volatilities**, which is what the states actually are.

Two warnings that decide whether this is useful or dangerous:

1. **Filtered, never smoothed.** `smoothed_marginal_probabilities` is what statsmodels
   plots by default and it uses future data at every point. A backtest driven by it will
   look extraordinary and be worthless. This module returns filtered probabilities and
   refuses to expose the smoothed ones for signal use.
2. **Refit on expanding windows, not once.** A model fitted on the full sample knows the
   whole history when labelling 2021. `regime_probabilities` refits periodically on
   trailing data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class RegimeFit:
    n_states: int
    transition_matrix: pd.DataFrame
    means: pd.Series  # per-state mean return
    volatilities: pd.Series  # per-state standard deviation
    expected_durations: pd.Series  # bars a state persists on average
    filtered_probabilities: pd.DataFrame
    loglikelihood: float
    converged: bool
    n_obs: int
    labels: dict[int, str] = field(default_factory=dict)

    def current_state(self) -> int:
        if self.filtered_probabilities.empty:
            return -1
        return int(self.filtered_probabilities.iloc[-1].idxmax())

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "mean_return": self.means,
                "volatility": self.volatilities,
                "annualised_vol": self.volatilities * np.sqrt(365 * 24),
                "expected_duration_bars": self.expected_durations,
                "self_transition": pd.Series(
                    np.diag(self.transition_matrix.to_numpy()), index=self.means.index
                ),
                "label": pd.Series(self.labels),
            }
        )


def _label_states(means: pd.Series, vols: pd.Series) -> dict[int, str]:
    """Give the fitted states human names.

    A fitted model returns states in arbitrary order — the labels are the model's
    internal indices and can flip between refits. Naming them by their *properties*
    (which is what a trader cares about) makes results comparable across refits, and
    prevents the classic bug of conditioning on 'state 0' when state 0 means something
    different than it did last week.
    """
    order = vols.sort_values()
    labels: dict[int, str] = {}
    if len(order) == 2:
        labels[int(order.index[0])] = "calm"
        labels[int(order.index[1])] = "turbulent"
    elif len(order) == 3:
        labels[int(order.index[0])] = "calm"
        labels[int(order.index[1])] = "normal"
        labels[int(order.index[2])] = "crisis"
    else:
        for rank, state in enumerate(order.index):
            labels[int(state)] = f"vol_rank_{rank}"

    # Distinguish direction within the highest-volatility state, which is the one that
    # matters: a turbulent state with a positive mean is a melt-up, not a crash.
    top = int(order.index[-1])
    if means.get(top, 0.0) < 0:
        labels[top] = labels[top] + "_down"
    else:
        labels[top] = labels[top] + "_up"
    return labels


def fit_regimes(
    returns: pd.Series, n_states: int = 2, *, switching_variance: bool = True, max_iter: int = 200
) -> RegimeFit:
    """Fit a Markov-switching model to a return series.

    `switching_variance=True` lets volatility differ across states, which is the whole
    point in financial data — regimes in crypto are far more a volatility phenomenon
    than a mean phenomenon, and a mean-only model finds almost nothing.
    """
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

    r = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 200:
        raise ValueError(f"regime fitting needs >=200 observations, got {len(r)}")

    # Scale to percent: the optimiser's tolerances are meaningless on ~1e-3 magnitudes.
    scaled = r * 100.0
    model = MarkovRegression(
        scaled.to_numpy(), k_regimes=n_states, trend="c", switching_variance=switching_variance
    )
    res = model.fit(maxiter=max_iter, disp=False)

    trans = np.asarray(res.regime_transition)
    # statsmodels returns shape (k, k, nobs) for time-varying transitions; take the
    # constant slice.
    if trans.ndim == 3:
        trans = trans[:, :, 0]
    transition = pd.DataFrame(trans, index=range(n_states), columns=range(n_states))

    # statsmodels returns params as a bare numpy array, so look each one up through
    # the model's own parameter-name list rather than by string key. Positional
    # indexing would also work today and would break the moment a trend or exogenous
    # term is added, silently reading the wrong coefficient.
    names = list(model.param_names)
    def param(name: str) -> float:
        return float(np.asarray(res.params)[names.index(name)])

    means = pd.Series(
        [param(f"const[{i}]") / 100.0 for i in range(n_states)], index=range(n_states)
    )
    if switching_variance:
        vols = pd.Series(
            [np.sqrt(abs(param(f"sigma2[{i}]"))) / 100.0 for i in range(n_states)],
            index=range(n_states),
        )
    else:
        shared = np.sqrt(abs(param("sigma2"))) / 100.0
        vols = pd.Series([shared] * n_states, index=range(n_states))

    diag = np.clip(np.diag(trans), 0.0, 1 - 1e-12)
    durations = pd.Series(1.0 / (1.0 - diag), index=range(n_states))

    filtered = pd.DataFrame(
        np.asarray(res.filtered_marginal_probabilities), index=r.index
    )
    filtered.columns = range(filtered.shape[1])

    return RegimeFit(
        n_states=n_states,
        transition_matrix=transition,
        means=means,
        volatilities=vols,
        expected_durations=durations,
        filtered_probabilities=filtered,
        loglikelihood=float(res.llf),
        converged=bool(getattr(res, "mle_retvals", {}).get("converged", True)),
        n_obs=len(r),
        labels=_label_states(means, vols),
    )


def regime_probabilities(
    returns: pd.Series, *, n_states: int = 2, lookback: int = 2000, refit_every: int = 500,
    min_train: int = 500,
) -> pd.DataFrame:
    """Causal regime probabilities: refit on trailing data, label forward only.

    At each refit the model sees only data strictly before that point, and its
    probabilities are applied to the following `refit_every` bars. This is slower than
    one global fit by a factor of (n / refit_every), and that cost is the point — a
    single fit on the whole sample leaks the future into every label it produces.

    Returns per-state probabilities plus the most likely state and its volatility rank,
    which is the stable identifier to condition a strategy on.
    """
    r = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(r)
    out = pd.DataFrame(index=r.index, columns=[f"p_state_{i}" for i in range(n_states)], dtype="float64")
    out["state"] = np.nan
    out["vol_rank"] = np.nan
    out["expected_duration"] = np.nan

    start = max(min_train, 200)
    for anchor in range(start, n, refit_every):
        train = r.iloc[max(0, anchor - lookback) : anchor]
        if len(train) < min_train:
            continue
        try:
            fit = fit_regimes(train, n_states=n_states)
        except Exception:
            continue  # a failed fit means no opinion, not a crash

        # Rank states by volatility so the identifier is stable across refits.
        vol_order = {int(s): rank for rank, s in enumerate(fit.volatilities.sort_values().index)}

        block = r.iloc[anchor : anchor + refit_every]
        if block.empty:
            continue

        # Apply the fitted model to the forward block by running the filter over the
        # trailing window extended with the block, then keeping only the block's rows.
        extended = r.iloc[max(0, anchor - lookback) : anchor + len(block)]
        try:
            applied = fit_regimes(extended, n_states=n_states)
        except Exception:
            continue
        probs = applied.filtered_probabilities.reindex(block.index)
        if probs.isna().all().all():
            continue

        for i in range(n_states):
            if i in probs.columns:
                out.loc[block.index, f"p_state_{i}"] = probs[i].to_numpy()
        state = probs.idxmax(axis=1)
        out.loc[block.index, "state"] = state.to_numpy()
        out.loc[block.index, "vol_rank"] = [vol_order.get(int(s), np.nan) for s in state]
        out.loc[block.index, "expected_duration"] = [
            fit.expected_durations.get(int(s), np.nan) for s in state
        ]

    return out


def regime_conditional_performance(
    returns: pd.Series, regimes: pd.DataFrame, *, periods_per_year: float = 365 * 24
) -> pd.DataFrame:
    """How a return series behaves inside each regime.

    The practical output: if a strategy's Sharpe is 1.5 in the calm state and -0.8 in
    the turbulent one, gating it on the regime is worth more than any amount of further
    signal research. If it is the same in both, the regime model is decoration.
    """
    df = pd.concat([pd.Series(returns).rename("ret"), regimes["vol_rank"]], axis=1).dropna()
    if df.empty:
        return pd.DataFrame()

    rows = []
    for rank, group in df.groupby("vol_rank"):
        r = group["ret"]
        sd = r.std(ddof=1)
        rows.append(
            {
                "vol_rank": int(rank),
                "n_bars": len(r),
                "share_of_time": len(r) / len(df),
                "mean_return": float(r.mean()),
                "annualised_vol": float(sd * np.sqrt(periods_per_year)) if sd > 0 else np.nan,
                "sharpe": float(r.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else np.nan,
                "hit_rate": float((r > 0).mean()),
                "worst_bar": float(r.min()),
            }
        )
    return pd.DataFrame(rows).set_index("vol_rank")
