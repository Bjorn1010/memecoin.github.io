"""Turn a money target into a measurable quantity, and track what is actually earned.

A target expressed in currency per hour is not a statement about a strategy. It is a
statement about *capital*, because once a return rate is fixed the capital follows by
division. "$100 an hour" on a book of $10,000 is 8,760% a year; on $25 million it is
3.5%. The strategy in between is identical. This module exists so that arithmetic is
done before the work rather than discovered after it.

Two numbers, side by side, and the gap between them is the whole report:

* **Required.** What the target implies, given the capital actually committed.
* **Achieved.** What the paper record has actually earned per hour, from the recorded
  equity curve — not from a backtest, not from an assumption.

The reference points are there so "required" can be read against something. The highest
sustained return ever recorded by a fund open for three decades is Renaissance Medallion
at roughly 66% a year gross, closed to outside money and capped in capacity. A required
return above that is not ambitious, it is outside the recorded history of the industry,
and a system that quietly accepts such a target will meet it only by taking risk that
ends in ruin — which `qt.sizing.ruin` measures rather than debates.

Nothing here changes what the bot does. It changes what you can see about it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Hours in a year, by what "an hour of trading" is taken to mean. Crypto runs
# continuously; equities do not, and counting a target against hours the market is shut
# quietly triples it.
HOURS_PER_YEAR = {
    "crypto_24_7": 24 * 365,          # 8,760
    "us_market_hours": 6.5 * 252,     # 1,638
    "working_day": 8 * 250,           # 2,000
}

# What this bot actually does, measured rather than hoped: risk parity + 30% trend over
# 15 ETFs, 2010-2026, costs included (`scripts/research_trend.py`). These are the
# defaults for every "at what return?" argument below, because the alternative is a
# module whose defaults quietly describe a better strategy than the one that ships.
#
# This figure has been wrong once already, and in the flattering direction: it read 3.5%
# at a Sharpe of 1.10, which came from `combine_trend_and_allocator` being handed the
# risk-sized weights instead of the bounded signal. Corrected, the book runs at 6.6% a
# year for 6.8% volatility — a Sharpe of 0.97.
MEASURED_RETURN = 0.066
MEASURED_VOL = 0.068

# Published long-run annualised returns, for scale. These are what the required figure
# has to be read against; without them a percentage is just a number.
REFERENCES = {
    "Livret A / cash": 0.03,
    "S&P 500, long run": 0.10,
    "ce bot, mesuré (Sharpe 0,97)": MEASURED_RETURN,
    "meilleur hedge fund décennal typique": 0.20,
    "Buffett, 1965-2023": 0.198,
    "Medallion (fermé, plafonné), brut": 0.66,
}


@dataclass
class Objective:
    """A money target, the capital behind it, and the return it therefore requires."""

    target_per_hour: float = 100.0
    capital: float = 100_000.0
    hours_basis: str = "crypto_24_7"
    currency: str = "$"

    @property
    def hours_per_year(self) -> float:
        if self.hours_basis not in HOURS_PER_YEAR:
            raise ValueError(
                f"unknown hours_basis {self.hours_basis!r}; known: {sorted(HOURS_PER_YEAR)}"
            )
        return HOURS_PER_YEAR[self.hours_basis]

    @property
    def target_per_year(self) -> float:
        return self.target_per_hour * self.hours_per_year

    @property
    def required_return(self) -> float:
        """Annual return the target implies. The whole point of this module."""
        if self.capital <= 0:
            return float("inf")
        return self.target_per_year / self.capital

    def required_capital(self, at_return: float = MEASURED_RETURN) -> float:
        """Capital that would meet the target at a given annual return."""
        if at_return <= 0:
            return float("inf")
        return self.target_per_year / at_return

    def verdict(self) -> tuple[str, str]:
        """A blunt reading of the required return against recorded history."""
        r = self.required_return
        if r <= 0.10:
            return "atteignable", "sous le rendement long terme des actions"
        if r <= 0.25:
            return "ambitieux", "au niveau des meilleurs fonds sur une décennie"
        if r <= 0.66:
            return "hors de portée", "au-delà de Buffett, sous le record absolu"
        return (
            "impossible",
            "au-dessus du meilleur historique jamais enregistré (Medallion, ~66%/an, "
            "fonds fermé et plafonné)",
        )

    def to_dict(self) -> dict:
        verdict, note = self.verdict()
        return {
            "target_per_hour": self.target_per_hour,
            "hours_basis": self.hours_basis,
            "hours_per_year": self.hours_per_year,
            "target_per_year": round(self.target_per_year, 2),
            "capital": self.capital,
            "required_return": round(self.required_return, 4),
            "required_return_pct": f"{self.required_return * 100:,.1f}%",
            "verdict": verdict,
            "note": note,
        }


def capital_table(objective: Objective,
                  returns=(MEASURED_RETURN, 0.10, 0.20, 0.66)) -> pd.DataFrame:
    """Capital needed to hit the target, at each reference return.

    Reading this table is usually the moment the target becomes concrete: the same
    monthly income needs an order of magnitude less capital at 66% a year than at 3.5%,
    and the 66% column is a fund that has been closed since 1993.
    """
    rows = []
    for r in returns:
        label = next((k for k, v in REFERENCES.items() if abs(v - r) < 1e-9), f"{r:.1%}/an")
        rows.append({
            "rendement_annuel": f"{r * 100:,.1f}%",
            "référence": label,
            "capital_requis": round(objective.required_capital(r), 2),
        })
    return pd.DataFrame(rows)


def return_table(objective: Objective,
                 capitals=(1_000, 10_000, 100_000, 1_000_000, 10_000_000)) -> pd.DataFrame:
    """Return needed at each capital level, with the verdict attached to each."""
    rows = []
    for cap in capitals:
        probe = Objective(objective.target_per_hour, float(cap), objective.hours_basis)
        verdict, _ = probe.verdict()
        rows.append({
            "capital": cap,
            "rendement_requis": f"{probe.required_return * 100:,.1f}%",
            "verdict": verdict,
        })
    return pd.DataFrame(rows)


@dataclass
class Achieved:
    """What the paper record actually earned, per hour, from the recorded curve."""

    hours: float = 0.0
    pnl: float = 0.0
    per_hour: float = 0.0
    annualised_return: float = float("nan")
    cycles: int = 0
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "cycles": self.cycles,
            "hours_elapsed": round(self.hours, 1),
            "pnl": round(self.pnl, 2),
            "per_hour": round(self.per_hour, 4),
            "annualised_return": (round(self.annualised_return, 4)
                                  if np.isfinite(self.annualised_return) else None),
            "start": self.start.isoformat() if self.start is not None else None,
            "end": self.end.isoformat() if self.end is not None else None,
            "note": self.note,
        }


def achieved(store, run_id: str = "daily", *, objective: Objective | None = None) -> Achieved:
    """Measure realised currency-per-hour from the recorded equity curve.

    Deliberately measured over *wall-clock* hours between the first and last recorded
    cycle, not over hours the market was open. A target of "per hour" is a claim about
    elapsed time, and quietly switching to trading hours multiplies the result by five.

    A short record is reported with the caveat attached rather than annualised silently:
    two weeks of paper trading annualises to nonsense in either direction, and that
    nonsense is exactly what a hopeful reader will quote.
    """
    curve = store.equity_curve(run_id)
    if curve.empty or len(curve) < 2:
        return Achieved(cycles=int(len(curve)),
                        note="pas encore assez de cycles enregistrés pour mesurer quoi que ce soit")

    start = pd.Timestamp(int(curve["ts"].iloc[0]), unit="ms", tz="UTC")
    end = pd.Timestamp(int(curve["ts"].iloc[-1]), unit="ms", tz="UTC")
    hours = (end - start).total_seconds() / 3600.0
    pnl = float(curve["equity"].iloc[-1]) - float(curve["equity"].iloc[0])

    if hours <= 0:
        return Achieved(cycles=int(len(curve)), start=start, end=end,
                        note="tous les cycles portent le même horodatage")

    per_hour = pnl / hours
    years = hours / (24 * 365)
    first = float(curve["equity"].iloc[0])
    ann = float("nan")
    if first > 0 and years > 0:
        growth = float(curve["equity"].iloc[-1]) / first
        ann = growth ** (1 / years) - 1 if growth > 0 else float("nan")

    note = ""
    if hours < 24 * 30:
        note = (f"seulement {hours / 24:.1f} jours de trace — le rendement annualisé "
                "n'a aucune valeur informative à cette échéance")
    return Achieved(hours=hours, pnl=pnl, per_hour=per_hour, annualised_return=ann,
                    cycles=int(len(curve)), start=start, end=end, note=note)


def levers(objective: Objective, base_return: float = MEASURED_RETURN,
           base_vol: float = MEASURED_VOL) -> pd.DataFrame:
    """The honest ways to raise currency-per-hour, and what each actually costs.

    There are only four, and three of them are the same lever wearing different names.
    Raising volatility, raising leverage and moving to a faster market all buy return by
    buying risk; only raising capital buys it outright. The drawdown column is what the
    Sharpe implies at each risk level, and it is the number people skip.
    """
    rows = []
    for multiple in (1.0, 1.5, 2.0, 3.0):
        vol = base_vol * multiple
        ret = base_return * multiple           # Sharpe held constant: return scales with risk
        per_hour = ret * objective.capital / objective.hours_per_year
        # A rough but standard rule: a strategy spends time in drawdowns of roughly its
        # annual volatility, and a bad year reaches two to three times it.
        rows.append({
            "levier": f"{multiple:.1f}x le risque",
            "volatilité": f"{vol * 100:.0f}%",
            "rendement_attendu": f"{ret * 100:.1f}%",
            f"gain_par_heure": round(per_hour, 3),
            "drawdown_typique": f"−{vol * 100 * 1.5:.0f}%",
            "drawdown_mauvaise_année": f"−{vol * 100 * 3:.0f}%",
        })
    return pd.DataFrame(rows)


def report(objective: Objective, store=None, run_id: str = "daily") -> dict:
    """Required against achieved, with the gap named."""
    out: dict = {"objectif": objective.to_dict()}
    out["capital_requis"] = capital_table(objective).to_dict("records")
    out["rendement_requis_par_capital"] = return_table(objective).to_dict("records")
    out["leviers"] = levers(objective).to_dict("records")

    if store is not None:
        got = achieved(store, run_id, objective=objective)
        out["réalisé"] = got.to_dict()
        if got.cycles >= 2 and got.hours > 0:
            out["écart"] = {
                "visé_par_heure": objective.target_per_hour,
                "réalisé_par_heure": round(got.per_hour, 4),
                "ratio": (round(got.per_hour / objective.target_per_hour, 4)
                          if objective.target_per_hour else None),
            }
    return out
