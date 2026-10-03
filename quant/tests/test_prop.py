"""Prop-firm engine: rules as data, accounts as isolated state machines."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
import yaml

from qt.engine_types import RiskBudget, Signal
from qt.prop.account import ACTIVE, EMERGENCY_STOP, PAUSED, RISK_REDUCTION, PropAccount
from qt.prop.challenge import challenge_monte_carlo, run_path
from qt.prop.manager import MultiAccountManager
from qt.prop.onboarding import Evidence, can_transition, may_use_real_capital
from qt.prop.rules import RuleError, load_all, parse_firm
from qt.prop.translator import InstrumentSpec, TranslatorPolicy, translate

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)  # a Monday


def firm(**program_overrides):
    prog = {"name": "p", "phase": "challenge", "account_size": 100_000, "profit_target": 0.10,
            "max_daily_loss": 0.05, "daily_reset_tz": "UTC", "max_total_drawdown": 0.10,
            "drawdown_type": "static", "min_trading_days": 2,
            "leverage": {"fx": 30, "indices": 10, "metals": 10}, "allowed_instruments": ["fx", "indices", "metals"]}
    prog.update(program_overrides)
    return parse_firm({"firm": "f", "status": "template", "rules_verified": False, "programs": [prog]})


def account(**kw):
    f = firm(**kw)
    return PropAccount("acc", f.firm, f.programs[0])


def signal(side=1, price=100.0, stop=2.0, asset="indices", ts=T0, holding="swing"):
    return Signal("s", "X", asset, side, price, stop, ts, holding=holding, signal_id="sig1")


SPEC = InstrumentSpec("X", "indices", contract_multiplier=1.0, lot_size=0.01)


# ------------------------------------------------------------------ rules


def test_shipped_templates_load():
    firms = load_all("configs/prop_firms")
    assert len(firms) >= 3
    assert all(f.status == "template" and not f.rules_verified for f in firms.values())


def test_unknown_key_is_an_error_not_a_warning():
    raw = {"firm": "f", "status": "template", "rules_verified": False,
           "programs": [{"name": "p", "phase": "challenge", "account_size": 1000, "max_total_drawdown": 0.1,
                         "max_daly_loss": 0.05}]}
    with pytest.raises(RuleError, match="max_daly_loss"):
        parse_firm(raw)


def test_active_status_requires_verified_rules():
    raw = {"firm": "f", "status": "active", "rules_verified": False,
           "programs": [{"name": "p", "phase": "funded", "account_size": 1000, "max_total_drawdown": 0.1}]}
    with pytest.raises(RuleError, match="rules_verified"):
        parse_firm(raw)


def test_verified_rules_require_a_source():
    raw = {"firm": "f", "status": "draft", "rules_verified": True,
           "programs": [{"name": "p", "phase": "funded", "account_size": 1000, "max_total_drawdown": 0.1}]}
    with pytest.raises(RuleError, match="source_url"):
        parse_firm(raw)


def test_daily_loss_larger_than_total_is_rejected():
    with pytest.raises(RuleError):
        firm(max_daily_loss=0.2, max_total_drawdown=0.1)


# ------------------------------------------------------------------ account


def test_daily_loss_breach_stops_the_account():
    a = account()
    a.on_mark(100_000, T0)
    a.on_mark(94_900, T0 + timedelta(hours=1))
    assert a.status == EMERGENCY_STOP
    assert a.breaches


def test_daily_buffer_pauses_before_the_limit_and_resets_next_day():
    a = account()
    a.on_mark(100_000, T0)
    a.on_mark(95_900, T0 + timedelta(hours=1), balance=95_900)  # 82 % of the 5 % daily limit
    assert a.status == PAUSED
    a.on_mark(95_900, T0 + timedelta(days=1), balance=95_900)
    assert a.status in (ACTIVE, RISK_REDUCTION)


def test_unrealised_loss_carried_overnight_still_counts_on_a_balance_basis():
    a = account()
    a.on_mark(100_000, T0)
    a.on_mark(95_900, T0 + timedelta(hours=1))  # open position, balance untouched
    a.on_mark(95_900, T0 + timedelta(days=1))
    assert a.status == PAUSED  # max(balance, equity) at day start is still 100 000


def test_static_drawdown_floor_does_not_move_with_profits():
    a = account()
    a.on_mark(108_000, T0)
    assert a.total_floor == 90_000


def test_trailing_intraday_floor_follows_equity_highs():
    a = account(drawdown_type="trailing_intraday", max_total_drawdown=0.06, max_daily_loss=0.03)
    a.on_mark(100_000, T0)
    a.on_mark(103_000, T0 + timedelta(hours=1))
    assert a.total_floor == pytest.approx(97_000)
    a.on_mark(97_100, T0 + timedelta(days=1, hours=1))
    assert a.status == EMERGENCY_STOP  # 85 % buffer of the 6 % trailing drawdown consumed


def test_trailing_eod_only_moves_at_day_close():
    a = account(drawdown_type="trailing_eod", max_total_drawdown=0.04, max_daily_loss=None,
                trailing_lock_at_start=True)
    a.on_mark(100_000, T0)
    a.on_mark(102_000, T0 + timedelta(hours=2))
    assert a.total_floor == pytest.approx(96_000)  # intraday high not yet counted
    a.on_mark(102_000, T0 + timedelta(days=1))
    assert a.total_floor == pytest.approx(98_000)
    a.on_mark(106_000, T0 + timedelta(days=2))
    a.on_mark(106_000, T0 + timedelta(days=3))
    assert a.total_floor == pytest.approx(100_000)  # locked at the starting balance


def test_risk_reduction_after_half_the_drawdown():
    a = account(max_daily_loss=None)
    a.on_mark(100_000, T0)
    a.on_mark(94_500, T0 + timedelta(days=1))
    assert a.status == RISK_REDUCTION
    assert a.risk_multiplier() == 0.5


def test_target_reached_pauses_only_after_minimum_days():
    a = account()
    a.on_mark(100_000, T0)
    a.record_trade_day(T0)
    a.on_mark(110_500, T0 + timedelta(hours=3))
    assert a.status == ACTIVE  # one trading day, two required
    a.record_trade_day(T0 + timedelta(days=1))
    a.on_mark(110_600, T0 + timedelta(days=1))
    assert a.status == PAUSED


def test_risk_budget_is_the_headroom_not_the_notional():
    a = account()
    a.on_mark(100_000, T0)
    # daily: 5000 − 20 % buffer = 4000 ; total: 10 000 − 15 % = 8500 → 4000
    assert a.risk_budget() == pytest.approx(4_000)


def test_consistency_rule():
    a = account(consistency_rule={"max_day_share_of_profit": 0.4})
    a.on_mark(100_000, T0)
    a.on_mark(104_000, T0 + timedelta(hours=1))
    a.on_mark(104_500, T0 + timedelta(days=1))
    ok, msg = a.consistency_ok()
    assert not ok and "meilleur jour" in msg


# ------------------------------------------------------------------ translator


def test_same_signal_different_size_per_firm():
    budget = RiskBudget(signal(), risk_fraction=0.5)
    a1 = account()
    a2 = PropAccount("acc2", "g", firm(account_size=25_000, max_total_drawdown=0.06, max_daily_loss=0.03).programs[0])
    for a in (a1, a2):
        a.on_mark(a.program.account_size, T0)
    t1 = translate(budget, a1, SPEC)
    t2 = translate(budget, a2, SPEC)
    assert t1.accepted and t2.accepted
    assert t1.quantity != t2.quantity
    assert t1.intent.side == t2.intent.side == 1


def test_per_trade_cap_and_leverage_cap():
    a = account()
    a.on_mark(100_000, T0)
    t = translate(RiskBudget(signal(stop=0.01), 1.0), a, SPEC)
    assert "levier 10:1" in t.capped_by
    assert t.notional <= 10 * 100_000 + 1e-6


def test_disallowed_instrument_and_paused_account_are_refused():
    a = account()
    a.on_mark(100_000, T0)
    t = translate(RiskBudget(signal(asset="crypto"), 0.5), a, InstrumentSpec("X", "crypto"))
    assert not t.accepted
    a.pause("test")
    t = translate(RiskBudget(signal(), 0.5), a, SPEC)
    assert not t.accepted


def test_news_blackout_and_weekend_rule():
    a = account(news_restriction={"enabled": True, "minutes_before": 2, "minutes_after": 2}, weekend_holding=False)
    a.on_mark(100_000, T0)
    pol = TranslatorPolicy(news_calendar=((T0 + timedelta(minutes=1), "NFP"),))
    assert not translate(RiskBudget(signal(), 0.5), a, SPEC, pol).accepted
    friday = T0 + timedelta(days=4)
    assert not translate(RiskBudget(signal(ts=friday), 0.5), a, SPEC).accepted
    assert translate(RiskBudget(signal(ts=friday, holding="intraday"), 0.5), a, SPEC).accepted


def test_client_order_id_is_deterministic():
    a = account()
    a.on_mark(100_000, T0)
    t1 = translate(RiskBudget(signal(), 0.5), a, SPEC)
    t2 = translate(RiskBudget(signal(), 0.5), a, SPEC)
    assert t1.intent.client_order_id == t2.intent.client_order_id


# ------------------------------------------------------------------ multi-account


def test_one_failing_account_does_not_stop_the_others():
    m = MultiAccountManager()
    good = account()
    bad = account()
    bad.account_id = "bad"
    bad.risk_budget = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[assignment]
    stopped = account()
    stopped.account_id = "stopped"
    for a in (good, bad, stopped):
        a.on_mark(100_000, T0)
        m.add(a)
    stopped.on_mark(80_000, T0 + timedelta(hours=1))
    res = {t.account_id: t for t in m.route(RiskBudget(signal(), 0.5), SPEC)}
    assert res["acc"].accepted
    assert not res["bad"].accepted and bad.status == PAUSED
    assert not res["stopped"].accepted and stopped.status == EMERGENCY_STOP
    alloc = m.allocation()
    assert alloc["accounts"]["stopped"]["risk_share"] == 0.0


def test_allocation_uses_risk_capital_not_notional():
    m = MultiAccountManager()
    big = account()  # 100k, 10 % drawdown → 10k risk capital
    small = PropAccount("small", "g", firm(account_size=50_000, max_total_drawdown=0.04, max_daily_loss=None).programs[0])
    for a in (big, small):
        a.on_mark(a.program.account_size, T0)
        m.add(a)
    alloc = m.allocation()["accounts"]
    assert alloc["acc"]["risk_capital"] == pytest.approx(10_000)
    assert alloc["small"]["risk_capital"] == pytest.approx(2_000)


# ------------------------------------------------------------------ challenge + onboarding


def test_challenge_path_outcomes():
    p = firm().programs[0]
    flat = np.zeros(100)
    assert run_path(flat, flat, p, 1.0)[0] == "timeout"
    up = np.full(100, 0.01)
    assert run_path(up, np.zeros(100), p, 1.0)[0] == "passed"
    crash = np.array([-0.06] + [0.0] * 99)
    assert run_path(crash, crash, p, 1.0)[0] == "failed_daily"


def test_challenge_monte_carlo_risk_tradeoff():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2010-01-01", periods=2000, freq="B")
    r = pd.Series(rng.normal(0.0004, 0.006, 2000), index=idx)
    table = challenge_monte_carlo(r, r, firm().programs[0], scales=(0.5, 3.0), n_paths=300)
    lo, hi = table.iloc[0], table.iloc[1]
    assert hi["p_fail_daily"] + hi["p_fail_drawdown"] > lo["p_fail_daily"] + lo["p_fail_drawdown"]


def test_no_real_capital_without_human_approval(tmp_path):
    f = parse_firm({"firm": "f", "status": "paper", "rules_verified": True, "source_url": "https://x",
                    "programs": [{"name": "p", "phase": "funded", "account_size": 1000, "max_total_drawdown": 0.1}]})
    ok, why = can_transition(f, "small_live", Evidence(paper_days_matching=30))
    assert not ok and any("approbation" in r for r in why)
    approval = tmp_path / "approval.md"
    approval.write_text("approuvé par X le ...")
    ok, _ = can_transition(f, "small_live", Evidence(paper_days_matching=30, approval_file=str(approval)))
    assert ok
    assert not may_use_real_capital(f, Evidence(approval_file=str(approval)))  # still "paper"
    ok, why = can_transition(f, "active", Evidence(small_live_days_clean=50, approval_file=str(approval)))
    assert not ok  # one step at a time
