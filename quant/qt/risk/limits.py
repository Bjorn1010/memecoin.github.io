"""The risk engine: hard limits that nothing upstream can widen.

This is the lowest layer of the system and the only one with the authority to say no.
Every target weight — whether it came from a rule, a model, an ensemble, or a human —
passes through `RiskEngine.apply` before it becomes a position. The engine can only
ever *reduce* exposure.

The limits are stateful because the important ones are: a daily loss limit needs to
know today's opening equity, a drawdown kill switch needs the running peak. State
lives here rather than in the strategy so that no strategy can forget to check it.

Breaker semantics, in the order they are evaluated:

1. **Drawdown kill** — peak-to-trough beyond the limit flattens the book and halts
   trading until a human resets. Not automatic: if the model is broken, an automatic
   restart just resumes losing money.
2. **Daily loss limit** — flattens and halts for the remainder of the session, then
   resumes on the next one. This one is automatic because a bad day is not evidence of
   a broken system.
3. **Leverage, concentration, count** — proportional scaling of the requested weights.

Every rejection is recorded with its reason, so the dashboard can show *why* the book
is smaller than the model asked for, instead of leaving it a mystery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..config import RiskLimits


@dataclass
class RiskState:
    equity: float
    peak_equity: float
    session_start_equity: float
    session_date: str
    halted: bool = False
    halt_reason: str = ""
    halted_until_session: str | None = None

    @property
    def drawdown(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return self.equity / self.peak_equity - 1.0

    @property
    def session_pnl(self) -> float:
        if self.session_start_equity <= 0:
            return 0.0
        return self.equity / self.session_start_equity - 1.0


@dataclass
class RiskDecision:
    weights: pd.Series
    scale: float
    reasons: list[str] = field(default_factory=list)
    halted: bool = False

    @property
    def blocked(self) -> bool:
        return self.halted or self.scale == 0.0


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None, starting_equity: float = 100_000.0) -> None:
        self.limits = limits or RiskLimits()
        self.state = RiskState(
            equity=starting_equity,
            peak_equity=starting_equity,
            session_start_equity=starting_equity,
            session_date="",
        )
        self.log: list[dict] = []

    # ------------------------------------------------------------- lifecycle
    def mark(self, equity: float, timestamp: pd.Timestamp | datetime | None = None) -> None:
        """Update equity and roll the session if the UTC date changed."""
        ts = pd.Timestamp(timestamp or datetime.now(timezone.utc))
        if ts.tz is None:
            ts = ts.tz_localize("UTC")
        date = ts.strftime("%Y-%m-%d")

        if date != self.state.session_date:
            # A daily-loss halt expires when the session that caused it ends. A
            # drawdown halt has `halted_until_session is None` and therefore survives
            # every session roll — it clears only via an explicit reset().
            if self.state.halted and self.state.halted_until_session not in (None, date):
                self.state.halted = False
                self.state.halt_reason = ""
                self.state.halted_until_session = None
            self.state.session_date = date
            self.state.session_start_equity = equity

        self.state.equity = equity
        self.state.peak_equity = max(self.state.peak_equity, equity)

    def reset(self) -> None:
        """Manual restart after a drawdown halt. Deliberately explicit."""
        self.state.halted = False
        self.state.halt_reason = ""
        self.state.halted_until_session = None
        self.state.peak_equity = self.state.equity

    # ---------------------------------------------------------------- checks
    def check_breakers(self, timestamp: pd.Timestamp | None = None) -> str | None:
        """Return a halt reason if a circuit breaker has tripped."""
        lim = self.limits
        if self.state.drawdown <= -abs(lim.max_drawdown):
            self.state.halted = True
            self.state.halt_reason = (
                f"max drawdown breached: {self.state.drawdown:.1%} <= -{lim.max_drawdown:.1%} "
                "(manual reset required)"
            )
            self.state.halted_until_session = None
            return self.state.halt_reason

        if self.state.session_pnl <= -abs(lim.max_daily_loss):
            self.state.halted = True
            self.state.halt_reason = (
                f"daily loss limit breached: {self.state.session_pnl:.1%} <= -{lim.max_daily_loss:.1%}"
            )
            # Resumes when the session rolls over.
            self.state.halted_until_session = self.state.session_date
            return self.state.halt_reason

        return self.state.halt_reason if self.state.halted else None

    # ----------------------------------------------------------------- apply
    def apply(
        self,
        target_weights: pd.Series,
        *,
        timestamp: pd.Timestamp | None = None,
        equity: float | None = None,
    ) -> RiskDecision:
        """Clamp requested weights to what the limits allow."""
        if equity is not None:
            self.mark(equity, timestamp)

        weights = target_weights.astype("float64").fillna(0.0)
        reasons: list[str] = []

        halt = self.check_breakers(timestamp)
        if halt:
            self._record(timestamp, "halt", halt, 0.0)
            return RiskDecision(pd.Series(0.0, index=weights.index), 0.0, [halt], halted=True)

        lim = self.limits

        # 1. Per-instrument concentration.
        capped = weights.clip(-lim.max_position_weight, lim.max_position_weight)
        if not np.allclose(capped.to_numpy(), weights.to_numpy(), equal_nan=True):
            reasons.append(f"position cap {lim.max_position_weight:.0%} applied")
        weights = capped

        # 2. Maximum number of simultaneous positions: keep the highest-conviction ones.
        active = weights[weights.abs() > 1e-9]
        if len(active) > lim.max_positions:
            keep = active.abs().nlargest(lim.max_positions).index
            weights = weights.where(weights.index.isin(keep), 0.0)
            reasons.append(f"trimmed to {lim.max_positions} positions")

        # 3. Gross leverage.
        gross = float(weights.abs().sum())
        scale = 1.0
        if gross > lim.max_gross_leverage and gross > 0:
            scale = lim.max_gross_leverage / gross
            weights = weights * scale
            reasons.append(f"gross leverage scaled {scale:.2f}x to {lim.max_gross_leverage:.1f}")

        # 4. Approaching the drawdown limit: de-risk before hitting the wall rather
        #    than trading full size right up to a hard stop.
        dd = self.state.drawdown
        soft_zone = 0.6 * abs(lim.max_drawdown)
        if dd < -soft_zone:
            severity = (abs(dd) - soft_zone) / max(abs(lim.max_drawdown) - soft_zone, 1e-9)
            derisk = float(np.clip(1.0 - severity, 0.2, 1.0))
            weights = weights * derisk
            scale *= derisk
            reasons.append(f"drawdown de-risk {derisk:.2f}x (dd {dd:.1%})")

        self._record(timestamp, "apply", "; ".join(reasons) if reasons else "ok", scale)
        return RiskDecision(weights, scale, reasons, halted=False)

    def _record(self, timestamp, action: str, reason: str, scale: float) -> None:
        self.log.append(
            {
                "ts": timestamp,
                "action": action,
                "reason": reason,
                "scale": scale,
                "equity": self.state.equity,
                "drawdown": self.state.drawdown,
                "session_pnl": self.state.session_pnl,
                "halted": self.state.halted,
            }
        )

    def log_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)

    def status(self) -> dict:
        return {
            "equity": self.state.equity,
            "peak_equity": self.state.peak_equity,
            "drawdown": self.state.drawdown,
            "session_pnl": self.state.session_pnl,
            "halted": self.state.halted,
            "halt_reason": self.state.halt_reason,
            "limits": {
                "target_annual_vol": self.limits.target_annual_vol,
                "max_gross_leverage": self.limits.max_gross_leverage,
                "max_position_weight": self.limits.max_position_weight,
                "max_daily_loss": self.limits.max_daily_loss,
                "max_drawdown": self.limits.max_drawdown,
                "max_positions": self.limits.max_positions,
                "kelly_fraction": self.limits.kelly_fraction,
            },
        }
