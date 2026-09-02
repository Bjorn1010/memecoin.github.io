"""Why the book holds what it holds — every weight decomposed into its formula.

The orchestrator emits weights. A weight is a conclusion, and a conclusion you cannot
take apart is one you cannot disagree with, which means you cannot supervise the system
running it. This module reverses the calculation: for each instrument it reports every
intermediate term, in the order they are applied, so any number on the final line can be
traced back to a price.

## The chain, in full

Each step is a formula, and each is computed here alongside its inputs.

**1. Trend, per horizon.** For horizon *h* bars,

        z_h = (log P_t − log P_{t−h}) / (σ_daily × √h)

  The denominator matters more than the numerator. A 5% move over 32 days and a 5% move
  over 256 days are not the same evidence, and dividing by the volatility of an *h*-bar
  move under a random walk is what makes horizons comparable. Without the √h the slow
  horizons silently dominate the average.

**2. Combined signal.**

        s = tanh( mean(z_h) / scale ),  h ∈ {32, 64, 128, 256}

  tanh rather than a clip: a linear signal keeps growing with the size of a move, so the
  largest position is always taken at the most extended point of a trend — exactly where
  reversals happen. tanh saturates.

**3. Volatility.**

        σ_ann = EWMA_60(r) × √252

**4. Risk budget per leg.**

        w_trend = s × (target_vol / n) / σ_ann

  Direction from the signal, size from the risk. Equal notional across instruments would
  mean the 35%-vol leg dominates the book's variance and the 6%-vol leg is decorative.

**5. Blend with the static allocator.**

        w = (1 − b)·w_alloc + b·(|w_alloc| × s),  b = 0.7

  The allocator decides how risk is spread between instruments; the trend decides how
  much of it to take. Measured at b = 0.7: Sharpe 1.10 against 0.79 for the allocator
  alone.

**6. Portfolio volatility target.**

        k = target_vol / σ_portfolio(trailing 60, lagged 1)

  Computed on the volatility of the *book*, not the average of the instruments' — those
  differ by exactly the diversification the book was built to capture. Lagged one bar, so
  the scalar applied at *t* cannot contain *t*'s own return.

**7. Limits, applied last.** Per-instrument cap, then gross, scaled rather than
truncated. Truncating the largest legs concentrates the portfolio at the moment its risk
is highest — and applying the caps *before* step 6 lets the scalar walk a position back
through its own ceiling, which it did on the first live cycle.

## Reading the verdict

BUY and SELL name the direction of the *change* the book is being asked to make, not a
prediction. A position already held at its target weight produces HOLD however strong the
signal is, because there is nothing to do. That distinction is the difference between a
trading system and a forecast, and conflating them is how a strategy ends up paying the
spread to express a view it already holds.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..strategies.trend import TrendSpec


@dataclass
class Term:
    """One step of the calculation: what it is, what it produced, how."""

    name: str
    value: float
    formula: str
    detail: str = ""


def trend_terms(prices: pd.Series, spec: TrendSpec | None = None) -> list[Term]:
    """Step 1 and 2: the per-horizon z-scores and the signal they average to."""
    spec = spec or TrendSpec()
    log_price = np.log(prices.astype("float64"))
    returns = log_price.diff()
    daily_vol = returns.ewm(span=spec.vol_window,
                            min_periods=max(spec.vol_window // 2, 5)).std(bias=False)

    sigma = float(daily_vol.iloc[-1])
    terms: list[Term] = []
    zs: list[float] = []

    for h in spec.horizons:
        if len(log_price) <= h:
            continue
        move = float(log_price.iloc[-1] - log_price.iloc[-1 - h])
        scale = sigma * np.sqrt(h)
        z = move / scale if scale > 0 else float("nan")
        zs.append(z)
        terms.append(Term(
            name=f"z({h}j)",
            value=z,
            formula=f"(log P_t − log P_t−{h}) / (σ × √{h})",
            detail=f"mouvement {move * 100:+.2f}% ÷ ({sigma * 100:.2f}% × {np.sqrt(h):.1f})",
        ))

    if not zs:
        return terms

    mean_z = float(np.nanmean(zs))
    signal = float(np.tanh(mean_z / max(spec.scale, 1e-9)))
    terms.append(Term("moyenne des z", mean_z, "mean(z_h)",
                      f"sur {len(zs)} horizons"))
    terms.append(Term("signal", signal, "tanh(mean(z_h) / scale)",
                      "borné dans [−1, 1] ; tanh sature au lieu de croître"))
    return terms


def volatility_term(prices: pd.Series, spec: TrendSpec | None = None) -> Term:
    """Step 3."""
    spec = spec or TrendSpec()
    returns = np.log(prices.astype("float64")).diff()
    ann = float(returns.ewm(span=spec.vol_window,
                            min_periods=max(spec.vol_window // 2, 5)
                            ).std(bias=False).iloc[-1] * np.sqrt(spec.bars_per_year))
    return Term("volatilité annualisée", ann, "EWMA_60(r) × √252",
                f"{ann * 100:.1f}% par an")


def verdict(current: float, target: float, *, band: float = 0.005) -> tuple[str, float]:
    """What to *do*, which is not the same as what the signal says.

    A position already at its target produces HOLD however strong the view, because there
    is nothing to trade. Paying the spread to express a view you already hold is one of
    the commonest ways a system leaks money while looking busy.
    """
    delta = target - current
    if abs(delta) < band:
        return "CONSERVER", delta
    if delta > 0:
        return "ACHETER" if target > 0 else "RÉDUIRE LE SHORT", delta
    return "VENDRE" if target < 0 else "RÉDUIRE LE LONG", delta


def explain_symbol(
    prices: pd.Series,
    symbol: str,
    *,
    target_weight: float,
    current_weight: float = 0.0,
    spec: TrendSpec | None = None,
    portfolio_scalar: float | None = None,
) -> dict:
    """The full calculation for one instrument, term by term."""
    spec = spec or TrendSpec()
    terms = trend_terms(prices, spec)
    vol = volatility_term(prices, spec)
    signal = next((t.value for t in terms if t.name == "signal"), float("nan"))

    action, delta = verdict(current_weight, target_weight)
    last = float(prices.iloc[-1])

    return {
        "symbole": symbol,
        "prix": round(last, 2),
        "signal": round(signal, 4) if np.isfinite(signal) else None,
        "volatilité": round(vol.value, 4),
        "poids_actuel": round(current_weight, 5),
        "poids_cible": round(target_weight, 5),
        "variation": round(delta, 5),
        "action": action,
        "termes": [
            {"terme": t.name, "valeur": round(t.value, 4) if np.isfinite(t.value) else None,
             "formule": t.formula, "détail": t.detail}
            for t in terms + [vol]
        ],
        "scalaire_portefeuille": (round(portfolio_scalar, 4)
                                  if portfolio_scalar is not None else None),
    }


def explain_book(
    prices: pd.DataFrame,
    target_weights: pd.Series,
    *,
    current_weights: dict[str, float] | None = None,
    spec: TrendSpec | None = None,
    portfolio_scalar: float | None = None,
) -> pd.DataFrame:
    """One row per instrument: signal, volatility, weight, and what to do about it.

    Sorted by the size of the change rather than the size of the position, because the
    rows that need attention are the ones that are moving.
    """
    spec = spec or TrendSpec()
    current = current_weights or {}
    rows = []
    for symbol in target_weights.index:
        if symbol not in prices.columns:
            continue
        series = prices[symbol].dropna()
        if len(series) < max(spec.horizons) + 5:
            continue
        detail = explain_symbol(
            series, symbol,
            target_weight=float(target_weights[symbol]),
            current_weight=float(current.get(symbol, 0.0)),
            spec=spec, portfolio_scalar=portfolio_scalar,
        )
        rows.append({k: v for k, v in detail.items() if k != "termes"})

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.reindex(frame["variation"].abs().sort_values(ascending=False).index)


def portfolio_terms(prices: pd.DataFrame, weights: pd.DataFrame,
                    spec: TrendSpec | None = None,
                    target_vol: float = 0.10, window: int = 60) -> list[Term]:
    """Step 6, shown explicitly: what the book's own volatility was, and the scalar.

    Reported separately from the per-instrument terms because it is the one number that
    multiplies every position at once — when the book doubles overnight without a single
    signal changing, this is why.
    """
    returns = np.log(prices.astype("float64")).diff()
    aligned = returns.reindex(index=weights.index, columns=weights.columns)
    port = (weights.shift(1) * aligned).sum(axis=1)

    realised = port.rolling(window, min_periods=max(window // 2, 10)).std(ddof=0) * np.sqrt(252)
    latest = float(realised.iloc[-1]) if len(realised) else float("nan")
    scalar = target_vol / latest if np.isfinite(latest) and latest > 0 else float("nan")

    return [
        Term("volatilité réalisée du livre", latest,
             "std_60(Σ w_{t−1}·r_t) × √252",
             f"{latest * 100:.1f}% par an — celle du PORTEFEUILLE, pas la moyenne des lignes"),
        Term("scalaire de risque", scalar, "cible / réalisée",
             f"{target_vol * 100:.0f}% ÷ {latest * 100:.1f}% — décalé d'une barre"),
        Term("exposition brute", float(weights.iloc[-1].abs().sum()), "Σ |w_i|",
             "après plafonds, appliqués APRÈS la mise à l'échelle"),
    ]
