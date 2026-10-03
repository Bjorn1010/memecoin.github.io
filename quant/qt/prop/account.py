"""One prop-firm account: its state, its limits, its status.

The account turns the firm's rules into two numbers that drive everything else:

* daily headroom — how much can still be lost today before the daily limit;
* total headroom — how much can still be lost before the drawdown floor.

Those are the account's real risk budget. The notional account size is not: a
"$100k account" with a 10 % static drawdown is $10k of risk capital, and with a
trailing drawdown it can be much less after a winning streak.

Status machine:
    ACTIVE ──(headroom low)──► RISK_REDUCTION ──(recovered)──► ACTIVE
      │                                │
      ├──(daily limit nearly used / target reached / manual)──► PAUSED
      └──(limit breached / kill switch)──► EMERGENCY_STOP   (manual reset only)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from .rules import Program

ACTIVE, PAUSED, RISK_REDUCTION, EMERGENCY_STOP = "ACTIVE", "PAUSED", "RISK_REDUCTION", "EMERGENCY_STOP"


@dataclass
class AccountPolicy:
    """Our own safety margins, stricter than the firm's limits."""

    daily_buffer: float = 0.80  # stop trading the day at 80 % of the daily limit used
    total_buffer: float = 0.85  # emergency at 85 % of the total drawdown used
    risk_reduction_at: float = 0.50  # halve risk once half of the drawdown budget is used
    risk_reduction_multiplier: float = 0.5


@dataclass
class PropAccount:
    account_id: str
    firm: str
    program: Program
    policy: AccountPolicy = field(default_factory=AccountPolicy)
    balance: float = 0.0
    equity: float = 0.0
    status: str = ACTIVE
    status_reason: str = ""
    day: str | None = None
    day_start_balance: float = 0.0
    day_start_equity: float = 0.0
    high_water: float = 0.0  # for trailing drawdown
    trading_days: set = field(default_factory=set)
    daily_pnl: dict = field(default_factory=dict)
    open_positions: dict = field(default_factory=dict)  # symbol -> {"qty", "notional", "risk"}
    breaches: list = field(default_factory=list)
    target_reached: bool = False

    def __post_init__(self) -> None:
        if self.balance == 0.0:
            self.balance = self.equity = self.program.account_size
        self.day_start_balance = self.day_start_equity = self.balance
        self.high_water = self.balance

    # ---------------------------------------------------------------- limits
    def _local_day(self, ts: datetime) -> str:
        return ts.astimezone(ZoneInfo(self.program.daily_reset_tz)).date().isoformat()

    @property
    def daily_floor(self) -> float | None:
        p = self.program
        if p.daily_loss_amount is None:
            return None
        if p.daily_loss_basis == "balance":
            base = self.day_start_balance
        elif p.daily_loss_basis == "equity":
            base = self.day_start_equity
        else:
            base = max(self.day_start_balance, self.day_start_equity)
        return base - p.daily_loss_amount

    @property
    def total_floor(self) -> float:
        p = self.program
        if p.drawdown_type == "static":
            return p.account_size - p.total_drawdown_amount
        floor = self.high_water - p.total_drawdown_amount
        if p.trailing_lock_at_start:
            floor = min(floor, p.account_size)
        return floor

    def headroom(self) -> dict:
        daily = None if self.daily_floor is None else self.equity - self.daily_floor
        total = self.equity - self.total_floor
        return {"daily": daily, "total": total,
                "daily_used": None if daily is None else 1 - daily / self.program.daily_loss_amount,
                "total_used": 1 - total / self.program.total_drawdown_amount}

    def risk_budget(self) -> float:
        """Money that may still be lost, under our buffers — never more than the firm allows."""
        h = self.headroom()
        p = self.program
        total = h["total"] - (1 - self.policy.total_buffer) * p.total_drawdown_amount
        budget = total
        if h["daily"] is not None:
            daily = h["daily"] - (1 - self.policy.daily_buffer) * p.daily_loss_amount
            budget = min(budget, daily)
        return max(budget, 0.0)

    def risk_multiplier(self) -> float:
        if self.status in (PAUSED, EMERGENCY_STOP):
            return 0.0
        if self.status == RISK_REDUCTION:
            return self.policy.risk_reduction_multiplier
        return 1.0

    # ---------------------------------------------------------------- updates
    def on_mark(self, equity: float, ts: datetime, *, balance: float | None = None) -> str:
        """Feed the latest equity. Returns the status after the update."""
        day = self._local_day(ts)
        if self.day is None:
            self.day = day
        elif day != self.day:
            self._roll_day(day)
        self.equity = float(equity)
        if balance is not None:
            self.balance = float(balance)
        if self.program.drawdown_type == "trailing_intraday":
            self.high_water = max(self.high_water, self.equity)
        self.daily_pnl[self.day] = self.equity - self.day_start_equity
        self._evaluate()
        return self.status

    def record_trade_day(self, ts: datetime) -> None:
        self.trading_days.add(self._local_day(ts))

    def _roll_day(self, new_day: str) -> None:
        if self.program.drawdown_type == "trailing_eod":
            self.high_water = max(self.high_water, self.balance, self.equity)
        self.day = new_day
        self.day_start_balance = self.balance
        self.day_start_equity = self.equity
        if self.status == PAUSED and self.status_reason.startswith("daily"):
            self.status, self.status_reason = ACTIVE, ""

    def _evaluate(self) -> None:
        if self.status == EMERGENCY_STOP:
            return
        p = self.program
        if self.daily_floor is not None and self.equity <= self.daily_floor:
            self._stop(f"limite de perte journalière franchie ({self.equity:.2f} ≤ {self.daily_floor:.2f})")
            return
        if self.equity <= self.total_floor:
            self._stop(f"drawdown maximal franchi ({self.equity:.2f} ≤ {self.total_floor:.2f})")
            return
        h = self.headroom()
        if h["total_used"] >= self.policy.total_buffer:
            self._stop(f"{h['total_used']:.0%} du drawdown autorisé consommé (tampon {self.policy.total_buffer:.0%})",
                       breach=False)
            return
        if h["daily_used"] is not None and h["daily_used"] >= self.policy.daily_buffer:
            self.status, self.status_reason = PAUSED, f"daily: {h['daily_used']:.0%} de la perte journalière utilisée"
            return
        target = p.profit_target_amount
        if target is not None and self.equity - p.account_size >= target:
            self.target_reached = True
            if len(self.trading_days) >= p.min_trading_days:
                self.status, self.status_reason = PAUSED, "objectif atteint : ne plus risquer le compte"
                return
        if self.status == PAUSED and self.status_reason.startswith("manuel"):
            return  # a manual pause holds until resume()
        self.status = RISK_REDUCTION if h["total_used"] >= self.policy.risk_reduction_at else ACTIVE
        self.status_reason = "moitié du drawdown consommée : risque réduit" if self.status == RISK_REDUCTION else ""

    def _stop(self, reason: str, breach: bool = True) -> None:
        self.status, self.status_reason = EMERGENCY_STOP, reason
        if breach:
            self.breaches.append(reason)

    def pause(self, reason: str) -> None:
        if self.status != EMERGENCY_STOP:
            self.status, self.status_reason = PAUSED, f"manuel : {reason}"

    def resume(self, reason: str) -> None:
        """Manual. An EMERGENCY_STOP is resumed only by an explicit human call."""
        self.status, self.status_reason = ACTIVE, f"reprise manuelle : {reason}"
        self._evaluate()

    def consistency_ok(self) -> tuple[bool, str]:
        rule = self.program.consistency_rule
        if not rule:
            return True, ""
        profits = [v for v in self.daily_pnl.values() if v > 0]
        total = self.equity - self.program.account_size
        if total <= 0 or not profits:
            return True, ""
        share = max(profits) / total
        limit = rule.get("max_day_share_of_profit", 1.0)
        return share <= limit, f"meilleur jour = {share:.0%} du profit (limite {limit:.0%})"

    def snapshot(self) -> dict:
        h = self.headroom()
        return {"account_id": self.account_id, "firm": self.firm, "program": self.program.name,
                "balance": self.balance, "equity": self.equity, "status": self.status, "reason": self.status_reason,
                "drawdown_used": h["total_used"], "daily_used": h["daily_used"], "risk_budget": self.risk_budget(),
                "daily_pnl": self.daily_pnl.get(self.day, 0.0), "trading_days": len(self.trading_days),
                "open_positions": dict(self.open_positions),
                "exposure": sum(abs(p.get("notional", 0.0)) for p in self.open_positions.values())}
