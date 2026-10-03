"""Prop-firm onboarding: a firm moves one status at a time, each step justified.

    template → draft → paper → small_live → active        (retired from anywhere)

* draft:       rules collected from the firm's documents (source_url + retrieved_at)
* paper:       rules_verified, adapter written, simulated account passes the rule tests
* small_live:  ≥ 20 paper days whose rule tracking matched the firm's own dashboard;
               a HUMAN approval file exists
* active:      ≥ 20 small-live days without reconciliation mismatch; HUMAN approval

No transition to a status involving real money happens without an explicit approval
artefact, and nothing in this codebase writes one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .rules import FirmConfig

ORDER = ("template", "draft", "paper", "small_live", "active")
REAL_MONEY = ("small_live", "active")


@dataclass(frozen=True)
class Evidence:
    paper_days_matching: int = 0
    small_live_days_clean: int = 0
    approval_file: str | None = None  # path to a human-written approval note


def can_transition(firm: FirmConfig, target: str, evidence: Evidence) -> tuple[bool, list[str]]:
    reasons = []
    if target == "retired":
        return True, []
    if target not in ORDER:
        return False, [f"statut inconnu {target}"]
    cur = ORDER.index(firm.status) if firm.status in ORDER else -1
    if ORDER.index(target) != cur + 1:
        reasons.append(f"{firm.status} → {target} : une étape à la fois")
    if target in ("draft", "paper") and not firm.source_url:
        reasons.append("règles sans source documentée")
    if target in ("paper",) + REAL_MONEY and not firm.rules_verified:
        reasons.append("rules_verified est false")
    if target == "small_live" and evidence.paper_days_matching < 20:
        reasons.append(f"{evidence.paper_days_matching} jours de paper conformes (< 20)")
    if target == "active" and evidence.small_live_days_clean < 20:
        reasons.append(f"{evidence.small_live_days_clean} jours small-live sans écart (< 20)")
    if target in REAL_MONEY and not (evidence.approval_file and Path(evidence.approval_file).exists()):
        reasons.append("aucune approbation humaine écrite : le capital réel n'est jamais activé automatiquement")
    return not reasons, reasons


def may_use_real_capital(firm: FirmConfig, evidence: Evidence) -> bool:
    return (firm.status in REAL_MONEY and firm.rules_verified
            and bool(evidence.approval_file and Path(evidence.approval_file).exists()))
