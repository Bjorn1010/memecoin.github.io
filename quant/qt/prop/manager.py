"""Multi-account engine: 1 strategy × N firms × N accounts, with failure isolation.

* Routing: the same signal goes to every eligible account, translated separately.
* Isolation: an account that is paused, stopped, or that raises while being translated
  affects only itself. One account hitting its daily limit does not stop the others.
* Allocation: each account's share of a signal is driven by its *risk budget* (the
  money it can still lose under its rules and our buffers), never by its notional size.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..engine_types import RiskBudget
from .account import EMERGENCY_STOP, PropAccount
from .translator import InstrumentSpec, Translation, TranslatorPolicy, translate


@dataclass
class MultiAccountManager:
    accounts: dict[str, PropAccount] = field(default_factory=dict)
    policy: TranslatorPolicy = field(default_factory=TranslatorPolicy)
    errors: list[dict] = field(default_factory=list)

    def add(self, account: PropAccount) -> None:
        if account.account_id in self.accounts:
            raise ValueError(f"compte {account.account_id} déjà enregistré")
        self.accounts[account.account_id] = account

    def route(self, budget: RiskBudget, spec: InstrumentSpec) -> list[Translation]:
        out = []
        for acc in self.accounts.values():
            try:
                out.append(translate(budget, acc, spec, self.policy))
            except Exception as exc:  # noqa: BLE001 — isolate: one account's bug is not everyone's
                self.errors.append({"account": acc.account_id, "error": repr(exc)})
                acc.pause(f"erreur de traduction : {exc!r}")
                out.append(Translation(account_id=acc.account_id, accepted=False,
                                       reasons=[f"erreur isolée : {exc!r}"]))
        return out

    def allocation(self) -> dict:
        """Risk, capital and exposure allocation across accounts."""
        budgets = {}
        for k, a in self.accounts.items():
            try:
                budgets[k] = a.risk_budget() * a.risk_multiplier()
            except Exception as exc:  # noqa: BLE001 — a broken account gets no budget, others keep theirs
                self.errors.append({"account": k, "error": repr(exc)})
                a.pause(f"erreur de budget : {exc!r}")
                budgets[k] = 0.0
        total = sum(budgets.values())
        rows = {}
        for k, a in self.accounts.items():
            try:
                exposure = a.snapshot()["exposure"]
            except Exception:  # noqa: BLE001
                exposure = float("nan")
            rows[k] = {
                "status": a.status,
                "notional_size": a.program.account_size,
                "risk_capital": a.program.total_drawdown_amount,  # what the firm actually lets you lose
                "risk_budget_now": budgets[k],
                "risk_share": budgets[k] / total if total > 0 else 0.0,
                "exposure": exposure,
            }
        return {"accounts": rows, "total_risk_budget": total,
                "total_notional": sum(a.program.account_size for a in self.accounts.values()),
                "stopped": [k for k, a in self.accounts.items() if a.status == EMERGENCY_STOP]}
