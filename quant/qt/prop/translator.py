"""Prop risk translator: one quantitative signal → a different size on every account.

The signal is identical for every account. What changes is how much of each account's
risk budget it may use, and every constraint of that account's rule file:

    risk money = min( risk_fraction × account risk budget,
                      per-trade cap × account size )
                 × status multiplier (RISK_REDUCTION halves it, PAUSED zeroes it)
    quantity   = risk money / (stop distance × contract multiplier)
    then capped by: max lots, leverage (notional ≤ leverage × equity), and refused if the
    instrument, the hour, a news blackout or a weekend hold is not allowed.

Nothing here can make a position larger than the signal's risk fraction allows; every
cap only reduces it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from ..brokers.models import OrderIntent, OrderType, make_client_order_id
from ..engine_types import RiskBudget
from .account import PropAccount


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    asset_class: str
    contract_multiplier: float = 1.0  # price move × multiplier × qty = P&L in account currency
    lot_size: float = 1.0  # quantity step
    min_qty: float = 0.0


@dataclass
class Translation:
    account_id: str
    accepted: bool
    quantity: float = 0.0
    risk_money: float = 0.0
    notional: float = 0.0
    capped_by: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    intent: OrderIntent | None = None


@dataclass(frozen=True)
class TranslatorPolicy:
    max_risk_per_trade: float = 0.005  # of account size — our cap, stricter than any firm
    news_calendar: tuple[tuple[datetime, str], ...] = ()


def _in_hours(ts: datetime, hours: dict) -> bool:
    tz = ZoneInfo(hours.get("tz", "UTC"))
    local = ts.astimezone(tz).time()
    start = time.fromisoformat(hours["start"])
    end = time.fromisoformat(hours["end"])
    return start <= local <= end if start <= end else (local >= start or local <= end)


def translate(budget: RiskBudget, account: PropAccount, spec: InstrumentSpec,
              policy: TranslatorPolicy | None = None) -> Translation:
    policy = policy or TranslatorPolicy()
    sig = budget.signal
    p = account.program
    t = Translation(account_id=account.account_id, accepted=False)

    if sig.side == 0:
        t.reasons.append("signal plat : la clôture des positions est gérée par l'OrderManager")
        return t
    mult = account.risk_multiplier()
    if mult == 0.0:
        t.reasons.append(f"compte {account.status} : {account.status_reason}")
        return t
    if spec.asset_class not in p.allowed_instruments:
        t.reasons.append(f"classe {spec.asset_class} non autorisée par {account.firm}/{p.name}")
        return t
    if p.trading_hours and not _in_hours(sig.timestamp, p.trading_hours):
        t.reasons.append("hors des horaires de trading du programme")
        return t
    news = p.news_restriction or {}
    if news.get("enabled"):
        before = news.get("minutes_before", 0) * 60
        after = news.get("minutes_after", 0) * 60
        for when, label in policy.news_calendar:
            dt = (sig.timestamp - when).total_seconds()
            if -before <= dt <= after:
                t.reasons.append(f"fenêtre d'annonce interdite : {label}")
                return t
    if sig.holding == "swing" and (not p.overnight_holding or not p.weekend_holding):
        if not p.overnight_holding or sig.timestamp.weekday() >= 4:
            t.reasons.append("le programme interdit de garder la position (nuit / week-end)")
            return t

    budget_money = account.risk_budget()
    risk_money = min(budget.risk_fraction * budget_money, policy.max_risk_per_trade * p.account_size)
    if budget.risk_fraction * budget_money > policy.max_risk_per_trade * p.account_size:
        t.capped_by.append("plafond de risque par trade")
    risk_money *= mult * sig.conviction
    if mult < 1:
        t.capped_by.append(f"statut {account.status} (× {mult})")
    if risk_money <= 0:
        t.reasons.append("budget de risque épuisé")
        return t

    qty = risk_money / (sig.stop_distance * spec.contract_multiplier)
    if p.max_position_lots is not None and qty > p.max_position_lots:
        qty = p.max_position_lots
        t.capped_by.append("lots maximum")
    lev = p.leverage.get(spec.asset_class)
    if lev:
        max_notional = lev * account.equity
        notional = qty * sig.reference_price * spec.contract_multiplier
        if notional > max_notional:
            qty = max_notional / (sig.reference_price * spec.contract_multiplier)
            t.capped_by.append(f"levier {lev}:1")
    qty = (qty // spec.lot_size) * spec.lot_size
    if qty <= 0 or qty < spec.min_qty:
        t.reasons.append("taille arrondie à zéro (compte trop petit pour ce stop)")
        return t

    t.accepted = True
    t.quantity = qty
    t.risk_money = qty * sig.stop_distance * spec.contract_multiplier
    t.notional = qty * sig.reference_price * spec.contract_multiplier
    t.intent = OrderIntent(
        account_id=account.account_id, symbol=sig.symbol, side=sig.side, quantity=qty,
        order_type=OrderType.MARKET,
        protective_stop=sig.reference_price - sig.side * sig.stop_distance,
        client_order_id=make_client_order_id(account.account_id, sig.strategy, sig.signal_id, sig.symbol, sig.side),
        strategy=sig.strategy)
    return t
