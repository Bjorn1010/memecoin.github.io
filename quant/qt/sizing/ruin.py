"""Risk of ruin, optimal f, and the maths that decides how much to bet.

The question "how much should I bet" has an exact answer under known assumptions, and
the answer is almost always smaller than intuition suggests. Three results, each
answering a different practical question:

* **Risk of ruin** (`risk_of_ruin`, `risk_of_ruin_simulation`) — given an edge, a
  payoff and a bet size, what is the probability of losing everything? The classical
  gambler's-ruin formula answers it in closed form for fixed stakes, and it is
  startling: a 55% edge betting 10% of capital per trade still ruins roughly 1 account
  in 8 over a long enough horizon.

* **Kelly** (`kelly_fraction`) — the stake that maximises long-run growth. Also the
  stake that produces drawdowns nobody can hold. Full Kelly on a realistic edge means
  routine 50% drawdowns, and the moment your edge estimate is *too high* — which it
  usually is, because it was selected for being high — full Kelly is above the
  growth-optimal point and compounds *downward*.

* **Optimal f** (`optimal_f`) — Ralph Vince's empirical version: search directly over
  the actual trade sequence for the fraction that maximises terminal wealth, rather
  than assuming a binary payoff. More honest about fat tails, and it inherits the same
  warning, because it is optimised on the very sample it is evaluated on.

The practical conclusion these three agree on: bet a fraction of the theoretical
optimum, because the optimum is computed from an edge you have over-estimated. Quarter
Kelly is the usual choice and `kelly_fraction` defaults to it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def risk_of_ruin(
    win_rate: float, payoff: float = 1.0, *, bet_fraction: float = 0.01,
    ruin_level: float = 0.0, n_units: int | None = None,
) -> float:
    """Probability of eventual ruin under fixed fractional-of-initial-capital betting.

    Uses the classical gambler's-ruin result. With `n_units` capital units and a
    per-bet win probability p on an even-money bet, ruin probability is

        ((1-p)/p)^N   when p > 0.5, and 1 when p <= 0.5.

    Note the second half: **with no edge, ruin is certain given enough time**, whatever
    the bet size. Bet size changes how long it takes, not whether it happens.

    For payoff != 1 the bet is converted to an equivalent even-money bet with the same
    expectancy, which is exact for the growth question and a close approximation for
    the ruin probability.
    """
    if not 0 < win_rate < 1:
        return float("nan")

    edge = win_rate * payoff - (1 - win_rate)
    if edge <= 0:
        return 1.0  # no edge: ruin is certain in the limit

    if n_units is None:
        usable = 1.0 - ruin_level
        n_units = int(max(usable / max(bet_fraction, 1e-9), 1))

    # Equivalent even-money win probability preserving expectancy per unit risked.
    p_eq = (edge + 1.0) / (payoff + 1.0) if payoff > 0 else win_rate
    p_eq = float(np.clip(p_eq, 1e-9, 1 - 1e-9))
    if p_eq <= 0.5:
        return 1.0

    ratio = (1 - p_eq) / p_eq
    # ratio^N underflows to 0 for large N, which is the correct limit.
    return float(np.clip(ratio**n_units, 0.0, 1.0))


def risk_of_ruin_simulation(
    win_rate: float, payoff: float = 1.0, *, bet_fraction: float = 0.02,
    n_bets: int = 1000, n_paths: int = 5000, ruin_level: float = 0.2, seed: int = 0,
    compounding: bool = True,
) -> dict:
    """Monte Carlo risk of ruin, with `ruin_level` as a *practical* ruin threshold.

    Two departures from the textbook formula, both deliberate:

    * Ruin here means losing `ruin_level` of the account (default 20%), not reaching
      literally zero. Nobody keeps trading a strategy after an 80% drawdown, so zero is
      the wrong threshold for a decision.
    * `compounding=True` bets a fraction of *current* equity, which is what a real
      system does and which makes literal ruin impossible — so the practical threshold
      is the only meaningful one.
    """
    rng = np.random.default_rng(seed)
    wins = rng.random((n_paths, n_bets)) < win_rate

    equity = np.ones(n_paths)
    peak = np.ones(n_paths)
    ruined = np.zeros(n_paths, dtype=bool)
    ruin_step = np.full(n_paths, -1)

    for step in range(n_bets):
        stake = bet_fraction * equity if compounding else np.full(n_paths, bet_fraction)
        stake = np.minimum(stake, equity)
        pnl = np.where(wins[:, step], stake * payoff, -stake)
        equity = np.maximum(equity + pnl, 0.0)
        peak = np.maximum(peak, equity)

        newly = (~ruined) & (equity <= peak * (1 - ruin_level))
        ruin_step[newly] = step
        ruined |= newly

    return {
        "ruin_probability": float(ruined.mean()),
        "median_final": float(np.median(equity)),
        "p05_final": float(np.percentile(equity, 5)),
        "p95_final": float(np.percentile(equity, 95)),
        "median_ruin_bet": float(np.median(ruin_step[ruined])) if ruined.any() else None,
        "pct_profitable": float((equity > 1.0).mean()),
        "edge_per_bet": win_rate * payoff - (1 - win_rate),
        "bet_fraction": bet_fraction,
        "ruin_level": ruin_level,
        "compounding": compounding,
    }


def kelly_fraction(win_rate: float, payoff: float = 1.0, *, fraction: float = 0.25) -> dict:
    """Kelly stake and the fractional version actually worth using.

    f* = p - (1-p)/b for a binary bet. Returns both the full and fractional stake plus
    the expected growth rate, and — the number nobody computes and everybody needs —
    the drawdown implied by betting it.
    """
    if not 0 < win_rate < 1 or payoff <= 0:
        return {"full_kelly": np.nan, "fractional_kelly": np.nan, "edge": np.nan}

    full = win_rate - (1 - win_rate) / payoff
    edge = win_rate * payoff - (1 - win_rate)

    def growth(f: float) -> float:
        if f <= 0:
            return 0.0
        # Expected log growth per bet; negative means the stake compounds downward.
        up, down = 1 + f * payoff, 1 - f
        if up <= 0 or down <= 0:
            return float("-inf")
        return win_rate * np.log(up) + (1 - win_rate) * np.log(down)

    return {
        "full_kelly": float(full),
        "fractional_kelly": float(full * fraction),
        "fraction_used": fraction,
        "edge": float(edge),
        "growth_full": float(growth(full)) if full > 0 else 0.0,
        "growth_fractional": float(growth(full * fraction)) if full > 0 else 0.0,
        # Fractional Kelly keeps most of the growth for a fraction of the variance;
        # this ratio is why half or quarter Kelly is the standard choice.
        "growth_retained": float(growth(full * fraction) / growth(full)) if full > 0 and growth(full) > 0 else np.nan,
        # A rough but sound rule: expected maximum drawdown under Kelly betting is
        # approximately the Kelly fraction itself, so full Kelly on a 20% edge means
        # routinely living through a 20%+ drawdown.
        "approx_max_drawdown_full": float(min(full, 1.0)),
        "approx_max_drawdown_fractional": float(min(full * fraction, 1.0)),
        "note": (
            "full Kelly is growth-optimal only if the edge estimate is exact. It never "
            "is, and an over-estimated edge puts full Kelly past the peak, where it "
            "compounds downward."
        ),
    }


def optimal_f(returns: pd.Series | np.ndarray, *, n_grid: int = 200) -> dict:
    """Ralph Vince's optimal f: the fraction maximising terminal wealth on this sample.

    Searches directly over the realised trade sequence rather than assuming a binary
    payoff, so it respects the actual distribution including its tails. The result is
    the *largest* fraction anyone should consider, not a recommendation — it is fitted
    to the sample it is scored on, and the single worst trade in that sample sets the
    bound. One trade worse than anything seen so far moves the answer a long way.
    """
    r = pd.Series(returns).replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    if r.size < 20:
        return {"optimal_f": np.nan, "reason": "need at least 20 trades"}

    worst = r.min()
    if worst >= 0:
        return {"optimal_f": 1.0, "reason": "no losing trade in the sample — f is unbounded here"}

    fractions = np.linspace(0.01, 0.99, n_grid)
    twr = []
    for f in fractions:
        # Vince's terminal wealth relative: each trade scaled by f/|worst loss|.
        holding = 1.0 + f * (r / abs(worst))
        if np.any(holding <= 0):
            twr.append(0.0)
            continue
        twr.append(float(np.exp(np.sum(np.log(holding)))))

    twr = np.asarray(twr)
    best = int(np.argmax(twr))
    f_opt = float(fractions[best])

    return {
        "optimal_f": f_opt,
        "twr_at_optimal": float(twr[best]),
        "worst_trade": float(worst),
        # The per-trade risk implied: f of the account divided by the worst loss.
        "implied_risk_per_trade": f_opt,
        "half_f": f_opt / 2,
        "quarter_f": f_opt / 4,
        "n_trades": int(r.size),
        "curve": pd.DataFrame({"f": fractions, "twr": twr}),
        "warning": (
            "optimal f is fitted to this exact sequence and is bounded by its single "
            "worst trade; a worse trade than any seen shifts it substantially. Trade a "
            "fraction of it."
        ),
    }


def drawdown_probability(
    win_rate: float, payoff: float = 1.0, *, bet_fraction: float = 0.02,
    drawdown: float = 0.2, n_bets: int = 1000, n_paths: int = 5000, seed: int = 0,
) -> dict:
    """Probability of experiencing a drawdown of at least `drawdown` at some point.

    The question a risk limit actually needs answered. A strategy with a positive edge
    still breaches a 20% drawdown surprisingly often, and setting a stop-trading rule
    tighter than this probability guarantees you stop a working strategy.
    """
    rng = np.random.default_rng(seed)
    wins = rng.random((n_paths, n_bets)) < win_rate

    equity = np.ones(n_paths)
    peak = np.ones(n_paths)
    breached = np.zeros(n_paths, dtype=bool)
    worst = np.zeros(n_paths)

    for step in range(n_bets):
        stake = bet_fraction * equity
        equity = equity + np.where(wins[:, step], stake * payoff, -stake)
        equity = np.maximum(equity, 1e-12)
        peak = np.maximum(peak, equity)
        dd = equity / peak - 1.0
        worst = np.minimum(worst, dd)
        breached |= dd <= -drawdown

    return {
        "drawdown_threshold": drawdown,
        "probability_of_breach": float(breached.mean()),
        "median_worst_drawdown": float(np.median(worst)),
        "p95_worst_drawdown": float(np.percentile(worst, 5)),
        "edge_per_bet": win_rate * payoff - (1 - win_rate),
        "advice": (
            f"a stop-trading rule tighter than {abs(np.percentile(worst, 5)):.0%} would "
            "halt this strategy in 5% of its normal futures"
        ),
    }


def sizing_report(win_rate: float, payoff: float = 1.0, *, bet_fractions=None) -> pd.DataFrame:
    """Ruin probability and growth across candidate bet sizes.

    The table that answers "how much" directly. Read down the `ruin_probability` column
    and find where it becomes unacceptable — that, not the growth column, is where the
    limit belongs.
    """
    bet_fractions = bet_fractions if bet_fractions is not None else [0.005, 0.01, 0.02, 0.05, 0.10, 0.25]
    kelly = kelly_fraction(win_rate, payoff)

    rows = []
    for f in bet_fractions:
        sim = risk_of_ruin_simulation(win_rate, payoff, bet_fraction=f, n_paths=2000, n_bets=500)
        rows.append(
            {
                "bet_fraction": f,
                "vs_full_kelly": f / kelly["full_kelly"] if kelly["full_kelly"] and kelly["full_kelly"] > 0 else np.nan,
                "ruin_prob_20pct_dd": sim["ruin_probability"],
                "median_final": sim["median_final"],
                "p05_final": sim["p05_final"],
                "pct_profitable": sim["pct_profitable"],
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["full_kelly"] = kelly["full_kelly"]
    out.attrs["quarter_kelly"] = kelly["fractional_kelly"]
    out.attrs["edge"] = kelly["edge"]
    return out
