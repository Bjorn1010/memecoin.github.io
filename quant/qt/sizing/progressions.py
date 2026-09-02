"""Bet-sizing progressions — martingale and its relatives, implemented and measured.

These systems are usually argued about rather than computed. That is a mistake in both
directions: the martingale is neither the free money its advocates claim nor the
mathematical impossibility its critics claim. It is a *specific, calculable* transform
of a return distribution, and the honest thing is to implement it and measure what it
does. The comparison harness in `compare_progressions` and the risk-of-ruin maths in
`ruin.py` do exactly that, so the numbers come from your data rather than from anyone's
opinion.

What the mathematics actually says, and it is worth being precise because the usual
summaries are wrong in both directions:

* A martingale **does** raise the probability of ending a session in profit. That part
  of the sales pitch is true, and it is why the system survives — most sessions do end
  green.
* It raises it by **converting many small wins into one rare catastrophic loss**. The
  expected value is unchanged if the underlying bet is fair, and stays negative if the
  underlying bet is negative. No sizing rule can turn a negative-expectancy bet into a
  positive-expectancy one — sizing scales outcomes, it does not create edge.
* With **finite capital** the doubling sequence terminates in bankruptcy with
  probability approaching one as the horizon grows. Capital required after n
  consecutive losses grows as 2^n − 1 units: eleven losses in a row on a 1-unit base
  needs 2,047 units. Eleven consecutive losses at 50/50 happens roughly once every
  2,048 sequences, which on 20 trades a day is about once a quarter.

The families implemented:

| Progression | After a LOSS | After a WIN | Character |
|---|---|---|---|
| Martingale | double | reset | many small wins, rare ruin |
| Anti-martingale (Paroli) | reset | double | many small losses, rare large win |
| D'Alembert | +1 unit | −1 unit | gentler martingale, same shape |
| Fibonacci | next in sequence | back two | gentler still, same shape |
| Fixed fractional | constant % of equity | constant % | cannot ruin, compounds |
| Fixed ratio | scales with accumulated profit | same | Jones's compromise |

The last two are what professionals actually use, and the reason is in the third column:
they have no ruin state. Everything above them in the table is a bet on not hitting a
losing streak whose arrival time is a known distribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd


@dataclass
class ProgressionState:
    """Mutable state a progression carries between bets."""

    base_unit: float
    current_unit: float
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    peak_unit: float = 0.0
    step: int = 0  # position in a sequence (Fibonacci, d'Alembert)

    def record(self, won: bool) -> None:
        if won:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        self.peak_unit = max(self.peak_unit, self.current_unit)


class Progression:
    """Base class: map (state, equity) -> next stake."""

    name = "base"

    def __init__(self, base_unit: float = 1.0, max_unit: float | None = None) -> None:
        self.base_unit = base_unit
        self.max_unit = max_unit

    def initial_state(self) -> ProgressionState:
        return ProgressionState(self.base_unit, self.base_unit, peak_unit=self.base_unit)

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        raise NotImplementedError

    def _cap(self, stake: float, equity: float) -> float:
        """Stakes are capped by the table limit and by the money actually available.

        Both caps are the whole story for a martingale: the strategy's promise depends
        on being able to double indefinitely, and neither a real venue nor a real
        account allows that.
        """
        if self.max_unit is not None:
            stake = min(stake, self.max_unit)
        return max(min(stake, equity), 0.0)


class Martingale(Progression):
    """Double after every loss, reset after a win."""

    name = "martingale"

    def __init__(self, base_unit: float = 1.0, multiplier: float = 2.0, max_unit: float | None = None) -> None:
        super().__init__(base_unit, max_unit)
        self.multiplier = multiplier

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        state.current_unit = self.base_unit if won else state.current_unit * self.multiplier
        return self._cap(state.current_unit, equity)


class AntiMartingale(Progression):
    """Double after every win, reset after a loss (Paroli).

    The mirror image, and a genuinely different risk profile: it produces many small
    losses and occasional large wins, so it cannot be ruined by a losing streak. It
    gives back open profit instead, which is uncomfortable but survivable. This is the
    shape trend-following books have, whether or not they call it that.
    """

    name = "anti_martingale"

    def __init__(self, base_unit: float = 1.0, multiplier: float = 2.0, max_unit: float | None = None,
                 reset_after: int = 3) -> None:
        super().__init__(base_unit, max_unit)
        self.multiplier = multiplier
        self.reset_after = reset_after  # bank the run after this many wins

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        if not won:
            state.current_unit = self.base_unit
        elif state.consecutive_wins >= self.reset_after:
            state.current_unit = self.base_unit  # take the profit off the table
            state.consecutive_wins = 0
        else:
            state.current_unit = state.current_unit * self.multiplier
        return self._cap(state.current_unit, equity)


class DAlembert(Progression):
    """Add one unit after a loss, subtract one after a win.

    A linear martingale. It grows far more slowly, which makes it feel safer, and it has
    exactly the same structure: a long enough losing run still produces an unaffordable
    stake. It only postpones the arrival time.
    """

    name = "dalembert"

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        step = -1 if won else 1
        state.step = max(state.step + step, 0)
        state.current_unit = self.base_unit * (1 + state.step)
        return self._cap(state.current_unit, equity)


class Fibonacci(Progression):
    """Advance one place in the Fibonacci sequence on a loss, retreat two on a win."""

    name = "fibonacci"

    _SEQUENCE = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584]

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        state.step = max(state.step - 2, 0) if won else min(state.step + 1, len(self._SEQUENCE) - 1)
        state.current_unit = self.base_unit * self._SEQUENCE[state.step]
        return self._cap(state.current_unit, equity)


class FixedFractional(Progression):
    """Risk a constant fraction of current equity on every bet.

    The one with no ruin state: betting 2% of what you have left can never reach zero,
    because 2% of a shrinking number shrinks with it. It compounds gains and
    de-compounds losses automatically, which is the behaviour every other row in the
    table is trying and failing to approximate.
    """

    name = "fixed_fractional"

    def __init__(self, fraction: float = 0.02, max_unit: float | None = None) -> None:
        super().__init__(fraction, max_unit)
        self.fraction = fraction

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        state.current_unit = equity * self.fraction
        return self._cap(state.current_unit, equity)


class FixedRatio(Progression):
    """Ryan Jones's fixed ratio: add a contract per `delta` of accumulated profit.

    Sits between fixed-fractional and a flat stake. It scales up more slowly than
    fixed-fractional early on (when a drawdown would hurt most) and faster later, which
    is a defensible compromise for a small account.
    """

    name = "fixed_ratio"

    def __init__(self, base_unit: float = 1.0, delta: float = 5000.0, starting_equity: float = 100_000.0,
                 max_unit: float | None = None) -> None:
        super().__init__(base_unit, max_unit)
        self.delta = delta
        self.starting_equity = starting_equity

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        profit = max(equity - self.starting_equity, 0.0)
        # Contracts N satisfy profit = N(N-1)/2 * delta; invert the quadratic.
        contracts = (1 + np.sqrt(1 + 8 * profit / self.delta)) / 2
        state.current_unit = self.base_unit * max(contracts, 1.0)
        return self._cap(state.current_unit, equity)


class FlatStake(Progression):
    """Always the same stake. The control group."""

    name = "flat"

    def next_stake(self, state: ProgressionState, won: bool, equity: float) -> float:
        state.record(won)
        state.current_unit = self.base_unit
        return self._cap(state.current_unit, equity)


PROGRESSIONS: dict[str, Callable[..., Progression]] = {
    "flat": FlatStake,
    "martingale": Martingale,
    "anti_martingale": AntiMartingale,
    "dalembert": DAlembert,
    "fibonacci": Fibonacci,
    "fixed_fractional": FixedFractional,
    "fixed_ratio": FixedRatio,
}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
@dataclass
class ProgressionResult:
    name: str
    equity: pd.Series
    stakes: pd.Series
    final_equity: float
    ruined: bool
    ruin_bet: int | None
    max_stake: float
    max_drawdown: float
    n_bets: int
    max_consecutive_losses: int
    params: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "progression": self.name,
            "final_equity": self.final_equity,
            "total_return": self.final_equity / self.equity.iloc[0] - 1 if len(self.equity) else np.nan,
            "ruined": self.ruined,
            "ruin_bet": self.ruin_bet,
            "max_stake": self.max_stake,
            "max_stake_pct_of_start": self.max_stake / self.equity.iloc[0] if len(self.equity) else np.nan,
            "max_drawdown": self.max_drawdown,
            "max_consecutive_losses": self.max_consecutive_losses,
            "n_bets": self.n_bets,
        }


def simulate_progression(
    outcomes: np.ndarray | pd.Series,
    progression: Progression,
    *,
    starting_equity: float = 100_000.0,
    payoff: float = 1.0,
    ruin_threshold: float = 0.0,
) -> ProgressionResult:
    """Run a progression over a sequence of win/loss outcomes.

    `outcomes` is a boolean-like sequence (True = the bet won). `payoff` is the win/loss
    ratio: 1.0 means an even-money bet, 2.0 means wins pay double what losses cost.

    Ruin is checked *before* each bet, because that is when it actually bites: the
    system tells you to stake more than you have, and the sequence simply cannot
    continue. That moment — not a slow bleed — is how martingale accounts die.
    """
    outcomes = np.asarray(pd.Series(outcomes).astype(bool))
    state = progression.initial_state()

    equity = starting_equity
    equity_path = [equity]
    stakes: list[float] = []
    ruined = False
    ruin_bet = None
    max_consecutive = 0
    consecutive = 0

    # The first stake is the base; subsequent ones react to the previous outcome.
    stake = progression._cap(state.current_unit, equity)

    for i, won in enumerate(outcomes):
        if equity <= ruin_threshold or stake <= 0:
            ruined = True
            ruin_bet = i
            break
        # A progression that demands more than the account holds has already failed,
        # even if the arithmetic would let it continue on paper.
        if stake > equity:
            ruined = True
            ruin_bet = i
            break

        stakes.append(stake)
        equity += stake * payoff if won else -stake
        equity_path.append(equity)

        consecutive = 0 if won else consecutive + 1
        max_consecutive = max(max_consecutive, consecutive)

        stake = progression.next_stake(state, bool(won), equity)

    series = pd.Series(equity_path, name="equity")
    drawdown = (series / series.cummax() - 1).min() if len(series) > 1 else 0.0

    return ProgressionResult(
        name=progression.name,
        equity=series,
        stakes=pd.Series(stakes, name="stake"),
        final_equity=float(series.iloc[-1]),
        ruined=ruined,
        ruin_bet=ruin_bet,
        max_stake=float(max(stakes)) if stakes else 0.0,
        max_drawdown=float(drawdown),
        n_bets=len(stakes),
        max_consecutive_losses=max_consecutive,
        params={"payoff": payoff, "starting_equity": starting_equity},
    )


def compare_progressions(
    win_rate: float = 0.5,
    payoff: float = 1.0,
    *,
    n_bets: int = 1000,
    n_paths: int = 2000,
    starting_equity: float = 100_000.0,
    base_unit: float | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Monte Carlo every progression over the same outcome sequences.

    All progressions see the *identical* draws, so the comparison isolates the sizing
    rule rather than luck. The columns that matter are not the median — every
    progression looks fine at the median — but `ruin_rate` and the 5th percentile.
    That gap is the whole subject.
    """
    rng = np.random.default_rng(seed)
    base_unit = base_unit if base_unit is not None else starting_equity * 0.01

    builders = {
        "flat": lambda: FlatStake(base_unit),
        "martingale": lambda: Martingale(base_unit),
        "anti_martingale": lambda: AntiMartingale(base_unit),
        "dalembert": lambda: DAlembert(base_unit),
        "fibonacci": lambda: Fibonacci(base_unit),
        "fixed_fractional": lambda: FixedFractional(0.01),
        "fixed_ratio": lambda: FixedRatio(base_unit, delta=starting_equity * 0.05,
                                          starting_equity=starting_equity),
    }

    # One outcome matrix, shared across every progression.
    draws = rng.random((n_paths, n_bets)) < win_rate

    rows = []
    for name, build in builders.items():
        finals, ruins, max_stakes, drawdowns = [], 0, [], []
        for path in range(n_paths):
            res = simulate_progression(
                draws[path], build(), starting_equity=starting_equity, payoff=payoff
            )
            finals.append(res.final_equity)
            ruins += int(res.ruined)
            max_stakes.append(res.max_stake)
            drawdowns.append(res.max_drawdown)

        finals = np.asarray(finals)
        rows.append(
            {
                "progression": name,
                "ruin_rate": ruins / n_paths,
                "median_final": float(np.median(finals)),
                "mean_final": float(np.mean(finals)),
                "p05_final": float(np.percentile(finals, 5)),
                "p95_final": float(np.percentile(finals, 95)),
                "pct_profitable": float((finals > starting_equity).mean()),
                "median_max_stake": float(np.median(max_stakes)),
                "worst_drawdown": float(np.min(drawdowns)),
            }
        )

    out = pd.DataFrame(rows).set_index("progression")
    out.attrs["win_rate"] = win_rate
    out.attrs["payoff"] = payoff
    out.attrs["n_bets"] = n_bets
    out.attrs["n_paths"] = n_paths
    out.attrs["edge"] = win_rate * payoff - (1 - win_rate)
    return out


def martingale_capital_requirement(
    base_unit: float, n_losses: int, multiplier: float = 2.0
) -> dict:
    """Capital needed to survive `n_losses` consecutive losses, and how often that happens.

    The table this produces is the entire argument, and it is arithmetic rather than
    opinion: the capital requirement grows geometrically while the probability of
    needing it falls geometrically, and the product — the expected cost — does not
    shrink. What changes is only *when* you meet it.
    """
    total = base_unit * (multiplier**n_losses - 1) / (multiplier - 1) if multiplier != 1 else base_unit * n_losses
    prob_at_50 = 0.5**n_losses
    return {
        "n_consecutive_losses": n_losses,
        "capital_required": total,
        "units_required": total / base_unit if base_unit else np.nan,
        "next_stake": base_unit * multiplier**n_losses,
        "probability_at_50pct": prob_at_50,
        "expected_sequences_between": 1 / prob_at_50 if prob_at_50 > 0 else np.inf,
        "trades_until_expected_at_20_per_day": (1 / prob_at_50) / 20 if prob_at_50 > 0 else np.inf,
    }


def martingale_capital_table(
    base_unit: float = 100.0, max_losses: int = 15, multiplier: float = 2.0
) -> pd.DataFrame:
    """The requirement table across streak lengths."""
    rows = [martingale_capital_requirement(base_unit, n, multiplier) for n in range(1, max_losses + 1)]
    out = pd.DataFrame(rows)
    out["days_until_expected_at_20_per_day"] = out["trades_until_expected_at_20_per_day"]
    return out.drop(columns=["trades_until_expected_at_20_per_day"])
