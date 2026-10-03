"""Prop-firm rules as data: one YAML file per firm, strictly validated.

The engine contains no rule of any particular firm. A firm is a file in
configs/prop_firms/; adding firm N means adding a file. Rules change often, so each
file carries its source and the date it was read, and `rules_verified` stays false
until someone has checked it against the firm's official documents.

Validation is strict on purpose: an unknown key is an error, not a warning. A
constraint silently ignored because of a typo ("max_daly_loss") is exactly the one
that fails the account.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

STATUSES = ("template", "draft", "paper", "small_live", "active", "retired")
PHASES = ("challenge", "verification", "funded")
DRAWDOWN_TYPES = ("static", "trailing_intraday", "trailing_eod")
DAILY_BASES = ("balance", "equity", "balance_or_equity_start_of_day")
ASSET_CLASSES = ("fx", "indices", "futures", "equities", "crypto", "metals", "commodities")


class RuleError(ValueError):
    pass


@dataclass(frozen=True)
class Program:
    name: str
    phase: str
    account_size: float
    currency: str = "USD"
    profit_target: float | None = None  # fraction of account size; None for funded
    max_daily_loss: float | None = None  # fraction of account size (or of the basis)
    daily_loss_basis: str = "balance_or_equity_start_of_day"
    daily_reset_tz: str = "UTC"
    max_total_drawdown: float = 0.10
    drawdown_type: str = "static"
    trailing_lock_at_start: bool = False  # trailing floor stops at the starting balance
    min_trading_days: int = 0
    max_calendar_days: int | None = None
    leverage: dict = field(default_factory=dict)  # asset class -> max notional / equity
    max_position_lots: float | None = None
    allowed_instruments: tuple[str, ...] = ASSET_CLASSES
    trading_hours: dict | None = None  # {"start": "HH:MM", "end": "HH:MM", "tz": ...}
    news_restriction: dict = field(default_factory=lambda: {"enabled": False})
    weekend_holding: bool = True
    overnight_holding: bool = True
    consistency_rule: dict | None = None  # {"max_day_share_of_profit": 0.4}
    payout: dict = field(default_factory=dict)
    other_constraints: tuple[str, ...] = ()

    @property
    def daily_loss_amount(self) -> float | None:
        return None if self.max_daily_loss is None else self.max_daily_loss * self.account_size

    @property
    def total_drawdown_amount(self) -> float:
        return self.max_total_drawdown * self.account_size

    @property
    def profit_target_amount(self) -> float | None:
        return None if self.profit_target is None else self.profit_target * self.account_size


@dataclass(frozen=True)
class FirmConfig:
    firm: str
    status: str
    rules_verified: bool
    programs: tuple[Program, ...]
    source_url: str | None = None
    retrieved_at: str | None = None
    notes: str = ""
    path: str | None = None

    def program(self, name: str) -> Program:
        for p in self.programs:
            if p.name == name:
                return p
        raise KeyError(f"{self.firm}: pas de programme '{name}'")


_PROGRAM_FIELDS = {f.name for f in fields(Program)}
_FIRM_FIELDS = {"firm", "status", "rules_verified", "source_url", "retrieved_at", "programs", "notes"}


def _check_fraction(name: str, value, *, allow_none: bool = True) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, (int, float)) or not 0 < float(value) < 1:
        raise RuleError(f"{name} doit être une fraction dans ]0, 1[, reçu {value!r}")


def parse_program(raw: dict, firm: str) -> Program:
    unknown = set(raw) - _PROGRAM_FIELDS
    if unknown:
        raise RuleError(f"{firm}: clés inconnues {sorted(unknown)} — corriger plutôt qu'ignorer")
    for req in ("name", "phase", "account_size", "max_total_drawdown"):
        if req not in raw:
            raise RuleError(f"{firm}: champ obligatoire manquant '{req}'")
    if raw["phase"] not in PHASES:
        raise RuleError(f"{firm}: phase '{raw['phase']}' inconnue {PHASES}")
    if raw.get("drawdown_type", "static") not in DRAWDOWN_TYPES:
        raise RuleError(f"{firm}: drawdown_type '{raw['drawdown_type']}' inconnu {DRAWDOWN_TYPES}")
    if raw.get("daily_loss_basis", "balance_or_equity_start_of_day") not in DAILY_BASES:
        raise RuleError(f"{firm}: daily_loss_basis inconnu")
    if not float(raw["account_size"]) > 0:
        raise RuleError(f"{firm}: account_size doit être > 0")
    for frac in ("profit_target", "max_daily_loss", "max_total_drawdown"):
        _check_fraction(f"{firm}.{frac}", raw.get(frac), allow_none=frac != "max_total_drawdown")
    if raw.get("max_daily_loss") is not None and raw["max_daily_loss"] > raw["max_total_drawdown"]:
        raise RuleError(f"{firm}: perte journalière > drawdown total, incohérent")
    allowed = tuple(raw.get("allowed_instruments", ASSET_CLASSES))
    bad = set(allowed) - set(ASSET_CLASSES)
    if bad:
        raise RuleError(f"{firm}: classes d'actifs inconnues {sorted(bad)}")
    lev = raw.get("leverage") or {}
    if set(lev) - set(ASSET_CLASSES):
        raise RuleError(f"{firm}: levier pour une classe inconnue {sorted(set(lev) - set(ASSET_CLASSES))}")
    kwargs = dict(raw)
    kwargs["allowed_instruments"] = allowed
    kwargs["other_constraints"] = tuple(raw.get("other_constraints") or ())
    kwargs["account_size"] = float(raw["account_size"])
    return Program(**kwargs)


def parse_firm(raw: dict, path: str | None = None) -> FirmConfig:
    unknown = set(raw) - _FIRM_FIELDS
    if unknown:
        raise RuleError(f"clés inconnues au niveau firme : {sorted(unknown)}")
    for req in ("firm", "status", "rules_verified", "programs"):
        if req not in raw:
            raise RuleError(f"champ obligatoire manquant '{req}'")
    if raw["status"] not in STATUSES:
        raise RuleError(f"{raw['firm']}: statut '{raw['status']}' inconnu {STATUSES}")
    if raw["status"] in ("small_live", "active") and not raw["rules_verified"]:
        raise RuleError(f"{raw['firm']}: statut {raw['status']} interdit tant que rules_verified est false")
    if raw["rules_verified"] and not raw.get("source_url"):
        raise RuleError(f"{raw['firm']}: rules_verified sans source_url")
    programs = tuple(parse_program(p, raw["firm"]) for p in raw["programs"])
    return FirmConfig(firm=raw["firm"], status=raw["status"], rules_verified=bool(raw["rules_verified"]),
                      programs=programs, source_url=raw.get("source_url"), retrieved_at=raw.get("retrieved_at"),
                      notes=raw.get("notes", ""), path=path)


def load_firm(path: str | Path) -> FirmConfig:
    p = Path(path)
    return parse_firm(yaml.safe_load(p.read_text()), str(p))


def load_all(directory: str | Path) -> dict[str, FirmConfig]:
    out = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        cfg = load_firm(p)
        if cfg.firm in out:
            raise RuleError(f"firme '{cfg.firm}' définie deux fois")
        out[cfg.firm] = cfg
    return out
