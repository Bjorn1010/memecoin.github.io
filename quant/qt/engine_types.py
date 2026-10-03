"""Objects that cross layer boundaries: signal → risk → prop translation → execution.

They are deliberately plain data. A `Signal` carries a direction and a stop distance
and NO size: size is the risk layer's and the account's business, which is what lets
one signal be traded on N accounts with N different rule sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Signal:
    strategy: str
    symbol: str
    asset_class: str
    side: int  # +1 long, -1 short, 0 flat (close)
    reference_price: float
    stop_distance: float  # in price units; the loss per unit if the stop is hit
    timestamp: datetime
    conviction: float = 1.0  # in [0, 1]; never above 1
    holding: str = "swing"  # "intraday" | "swing" — whether the position may cross sessions
    signal_id: str = ""

    def __post_init__(self) -> None:
        if self.side not in (-1, 0, 1):
            raise ValueError("side must be -1, 0 or +1")
        if self.side and not self.stop_distance > 0:
            raise ValueError("a directional signal needs a positive stop distance")
        if not 0 <= self.conviction <= 1:
            raise ValueError("conviction must be in [0, 1]")


@dataclass(frozen=True)
class RiskBudget:
    """Output of the global risk engine for one signal, before any account constraint."""

    signal: Signal
    risk_fraction: float  # fraction of an account's risk budget this signal may use
    reasons: tuple[str, ...] = field(default_factory=tuple)
