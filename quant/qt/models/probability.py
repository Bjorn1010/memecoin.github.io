"""The probability that the market goes up — calibrated, and honest about its spread.

A classifier's raw output is not a probability. Gradient boosting in particular produces
scores that cluster and are systematically overconfident: it will say 0.85 for cases that
resolve up 65% of the time. Trading on that number sizes every position wrong, and the
error is one-directional — always too large, always at the moment the model is most sure.

So this module does two things a raw model does not.

**It calibrates.** The score is mapped through isotonic regression fitted on data the
model did not train on, so that "0.60" means the outcome happens 60% of the time. Isotonic
rather than Platt scaling because it makes no assumption about the shape of the
distortion, and there is no reason to expect a sigmoid here.

**It measures the calibration and reports it.** A reliability curve — predicted
probability against realised frequency, in buckets — plus the Brier score and its
decomposition. Those numbers say whether the probability means anything, and they are
reported whether or not they flatter the model.

## Reading the output

Two numbers decide whether a probability is worth acting on, and they are different
questions:

* **Is it calibrated?** Does 0.60 mean 60%. Measured by the reliability curve.
* **Does it discriminate?** Does it ever say anything other than 0.50. A perfectly
  calibrated model that outputs the base rate for every observation is useless and will
  look excellent on every calibration metric. The spread of the predictions is what
  separates a model from a constant.

A model can be well calibrated and worthless. `probability_report` reports both, and the
spread first, because it is the one that is usually missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ProbabilityResult:
    """Calibrated probabilities, plus everything needed to judge them."""

    probabilities: pd.Series          # P(up), calibrated
    raw: pd.Series                    # the model's uncalibrated score
    outcomes: pd.Series               # 1 if up, 0 if down
    diagnostics: dict = field(default_factory=dict)
    reliability: pd.DataFrame = field(default_factory=pd.DataFrame)


def brier_score(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean squared error of a probability forecast. Lower is better; 0.25 is a coin flip."""
    return float(np.mean((probabilities - outcomes) ** 2))


def brier_decomposition(probabilities: np.ndarray, outcomes: np.ndarray,
                        n_bins: int = 10) -> dict:
    """Murphy's decomposition: reliability, resolution, uncertainty.

        Brier = reliability - resolution + uncertainty

    **Reliability** is calibration error — how far the realised frequency sits from the
    predicted probability. Lower is better, zero is perfect.

    **Resolution** is how much the forecast varies from the base rate in a way that
    matters. This is the term that separates a useful model from a constant one, and it
    is the term almost never reported. A model that always predicts the base rate has
    zero reliability error and zero resolution: perfectly calibrated, perfectly useless.

    **Uncertainty** is the base rate's own variance. It is a property of the problem, not
    the model, and nothing can reduce it.
    """
    base = float(np.mean(outcomes))
    uncertainty = base * (1 - base)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(probabilities, edges[1:-1]), 0, n_bins - 1)

    reliability = resolution = 0.0
    n = len(probabilities)
    for b in range(n_bins):
        mask = idx == b
        k = int(mask.sum())
        if k == 0:
            continue
        mean_p = float(np.mean(probabilities[mask]))
        mean_o = float(np.mean(outcomes[mask]))
        reliability += k / n * (mean_p - mean_o) ** 2
        resolution += k / n * (mean_o - base) ** 2

    return {
        "brier": brier_score(probabilities, outcomes),
        "reliability": reliability,      # calibration error — lower is better
        "resolution": resolution,        # skill — higher is better, 0 means constant
        "uncertainty": uncertainty,
        "base_rate": base,
    }


def reliability_curve(probabilities: np.ndarray, outcomes: np.ndarray,
                      n_bins: int = 10) -> pd.DataFrame:
    """Predicted probability against realised frequency, bucketed.

    The diagonal is perfect calibration. A curve below it means the model is
    overconfident — it says 0.80 for things that happen 0.65 of the time — which is the
    normal failure and the expensive one, because position size follows confidence.
    """
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(probabilities, edges[1:-1]), 0, n_bins - 1)

    rows = []
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        rows.append({
            "seau": f"{edges[b]:.1f}-{edges[b + 1]:.1f}",
            "n": int(mask.sum()),
            "probabilité_prédite": round(float(np.mean(probabilities[mask])), 4),
            "fréquence_réelle": round(float(np.mean(outcomes[mask])), 4),
            "écart": round(float(np.mean(probabilities[mask]) - np.mean(outcomes[mask])), 4),
        })
    return pd.DataFrame(rows)


def fit_calibrated(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    n_splits: int = 4,
    embargo: int = 24,
    horizon: int = 6,
    model_factory=None,
    prior_strength: float = 50.0,
):
    """Fit a model and its calibrator on disjoint data, walking forward.

    The calibrator must never see the data the model trained on: a model is overconfident
    precisely on its training set, so calibrating there teaches the calibrator to trust
    scores it should not. Each fold trains on the past, calibrates on a held-out slice,
    and predicts the future — the only arrangement whose numbers transfer.

    Returns out-of-sample calibrated probabilities for every observation the walk covers.
    """
    from sklearn.isotonic import IsotonicRegression

    if model_factory is None:
        from lightgbm import LGBMClassifier

        def model_factory():
            return LGBMClassifier(n_estimators=200, num_leaves=15, learning_rate=0.05,
                                  min_child_samples=40, subsample=0.8,
                                  colsample_bytree=0.8, verbose=-1, random_state=0)

    n = len(X)
    fold = n // (n_splits + 1)
    raw_out = pd.Series(np.nan, index=X.index, dtype="float64")
    cal_out = pd.Series(np.nan, index=X.index, dtype="float64")

    for k in range(1, n_splits + 1):
        train_end = k * fold
        # A slice of the training window is set aside for the calibrator alone.
        calib_start = max(train_end - fold // 3, 0)
        fit_idx = np.arange(0, max(calib_start - horizon - embargo, 0))
        cal_idx = np.arange(calib_start, train_end)
        test_idx = np.arange(train_end + horizon + embargo,
                             min(train_end + fold, n))

        if len(fit_idx) < 300 or len(cal_idx) < 100 or len(test_idx) < 50:
            continue

        model = model_factory()
        model.fit(X.iloc[fit_idx], y.iloc[fit_idx])

        cal_scores = model.predict_proba(X.iloc[cal_idx])[:, 1]
        cal_truth = y.iloc[cal_idx].to_numpy()
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(cal_scores, cal_truth)

        test_scores = model.predict_proba(X.iloc[test_idx])[:, 1]
        raw_out.iloc[test_idx] = test_scores
        cal_out.iloc[test_idx] = shrink_to_evidence(
            iso.predict(test_scores), test_scores, cal_scores, cal_truth,
            prior_strength=prior_strength,
        )

    return cal_out, raw_out


def shrink_to_evidence(
    calibrated: np.ndarray,
    scores: np.ndarray,
    calibration_scores: np.ndarray,
    calibration_outcomes: np.ndarray,
    *,
    prior_strength: float = 50.0,
    n_bins: int = 10,
) -> np.ndarray:
    """Pull each probability back toward the base rate by what the evidence supports.

    Isotonic regression is free to output 0.0 and 1.0, and it will do so from a handful
    of observations. Measured on the Nasdaq, the buckets producing the extreme
    probabilities held 4, 10 and 16 observations — the model announced 99.8% and the
    market rose 25% of the time. That is not a property of markets; it is a calibrator
    taking noise literally.

    The fix is the standard one. Treat each region of the score as a Beta-Binomial: the
    posterior mean of `k` successes in `n` trials against a prior centred on the base
    rate with weight `prior_strength` is

        p̂ = (k + s·b) / (n + s)

    With sixteen observations and a prior weight of fifty, a bucket that came up 100%
    reports about 0.60 rather than 1.00 — which is what sixteen observations actually
    entitle anyone to say. As the bucket fills, the prior fades and the estimate
    converges on the empirical frequency.

    `prior_strength` is the number of observations the base rate is worth. Fifty is
    deliberately firm: at short horizons the honest prior is "this is a coin flip", and
    a signal has to work to overcome it.

    `scores` are the raw model scores that produced `calibrated`, and they are required
    rather than optional. The evidence behind a probability lives in the score's
    neighbourhood, not the probability's: isotonic maps one scale onto the other, and a
    boosted model's scores routinely bunch inside 0.4–0.6 while the calibrated output
    spans 0–1. Counting the calibration set in probability space therefore reads the
    wrong bucket — usually an empty one next to a crowded one — and the count that comes
    back is a plausible number computed from the wrong place.
    """
    p = np.asarray(calibrated, dtype="float64")
    if len(calibration_scores) == 0:
        return p

    base = float(np.mean(calibration_outcomes))
    cal = np.asarray(calibration_scores, dtype="float64")

    # How many calibration observations sit near each score, so the shrinkage reflects
    # the evidence behind *that* region rather than the sample as a whole. The bins span
    # the observed score range rather than [0, 1]: scores that all land inside 0.45–0.55
    # would otherwise fall into one or two bins of a [0, 1] grid, every count would come
    # back near the full sample size, and nothing would be shrunk at all.
    lo, hi = float(cal.min()), float(cal.max())
    if hi <= lo:
        n_local = np.full(p.shape, float(len(cal)))
    else:
        edges = np.linspace(lo, hi, n_bins + 1)
        cal_bin = np.clip(np.digitize(cal, edges[1:-1]), 0, n_bins - 1)
        counts = np.bincount(cal_bin, minlength=n_bins).astype("float64")

        out_bin = np.clip(np.digitize(np.asarray(scores, dtype="float64"), edges[1:-1]),
                          0, n_bins - 1)
        n_local = counts[out_bin]

    # k is what that probability implies happened in the bucket; the posterior mean then
    # blends it with the prior in proportion to the evidence.
    k = p * n_local
    denominator = n_local + prior_strength

    # A score landing in a region the calibrator never saw has no evidence at all, so it
    # gets the base rate rather than a division by zero. With prior_strength=0 that would
    # otherwise be 0/0 — a NaN probability, which every downstream comparison silently
    # treats as False and which therefore reads as "do not trade" for the wrong reason.
    out = np.where(denominator > 0, k + prior_strength * base, base * np.ones_like(p))
    return np.where(denominator > 0, out / np.where(denominator > 0, denominator, 1.0), base)


def probability_report(probabilities: pd.Series, outcomes: pd.Series,
                       raw: pd.Series | None = None) -> ProbabilityResult:
    """Everything needed to decide whether this probability is worth acting on."""
    ok = probabilities.notna() & outcomes.notna()
    p = probabilities[ok].to_numpy()
    o = outcomes[ok].to_numpy().astype("float64")

    if len(p) < 50:
        return ProbabilityResult(probabilities, raw if raw is not None else probabilities,
                                 outcomes, {"note": "trop peu d'observations"})

    decomposition = brier_decomposition(p, o)
    curve = reliability_curve(p, o)

    # The spread is reported first because it is the number usually missing. A model
    # that never leaves the base rate is perfectly calibrated and completely useless.
    spread = float(np.std(p))
    span = float(np.quantile(p, 0.95) - np.quantile(p, 0.05))

    diagnostics = {
        "observations": int(len(p)),
        "écart_type_des_probabilités": round(spread, 4),
        "amplitude_5e_95e": round(span, 4),
        "probabilité_min": round(float(p.min()), 4),
        "probabilité_max": round(float(p.max()), 4),
        **{k: round(v, 5) for k, v in decomposition.items()},
        # Brier of always predicting the base rate. If the model does not beat this, it
        # has added nothing at all.
        "brier_du_taux_de_base": round(float(np.mean((decomposition["base_rate"] - o) ** 2)), 5),
    }
    diagnostics["gain_sur_le_taux_de_base"] = round(
        diagnostics["brier_du_taux_de_base"] - diagnostics["brier"], 5)

    if span < 0.05:
        diagnostics["verdict"] = (
            "le modèle ne s'écarte pratiquement jamais du taux de base — "
            "calibré peut-être, mais sans contenu"
        )
    elif diagnostics["gain_sur_le_taux_de_base"] <= 0:
        diagnostics["verdict"] = (
            "le modèle fait moins bien que prédire toujours le taux de base"
        )
    else:
        diagnostics["verdict"] = "le modèle apporte quelque chose ; reste à savoir si ça couvre les coûts"

    return ProbabilityResult(probabilities, raw if raw is not None else probabilities,
                             outcomes, diagnostics, curve)


def edge_from_probability(p_up: float, payoff_ratio: float = 1.0,
                          cost_fraction: float = 0.0) -> float:
    """Expected value of a bet at this probability, net of cost, per unit risked.

        E = p·b − (1−p)·1 − c

    Positive means the bet is worth taking. The cost term is what turns most
    short-horizon probabilities negative: at 12bps a round trip against a 30bps move,
    `cost_fraction` is 0.4 and a probability of 0.55 is not enough.
    """
    return p_up * payoff_ratio - (1.0 - p_up) - cost_fraction


def required_probability(payoff_ratio: float = 1.0, cost_fraction: float = 0.0) -> float:
    """The probability at which a bet breaks even. Below it, the bet loses on average.

    Solving E = 0 for p:  p = (1 + c) / (1 + b)
    """
    return (1.0 + cost_fraction) / (1.0 + payoff_ratio)
