from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from qt.monitoring.decay import OK, PAUSE, WATCH, detect_decay
from qt.monitoring.snapshot import account_view, dashboard, render_text, strategy_view
from qt.oms.kill_switch import KillSwitch
from qt.prop.account import PropAccount
from qt.prop.rules import parse_firm


def test_same_distribution_is_not_flagged():
    rng = np.random.default_rng(0)
    bt = rng.normal(0.002, 0.01, 2000)
    live = rng.normal(0.002, 0.01, 80)
    assert detect_decay(bt, live).status in (OK, WATCH)


def test_lost_edge_pauses_and_never_reoptimises():
    rng = np.random.default_rng(1)
    bt = rng.normal(0.004, 0.01, 2000)
    live = rng.normal(-0.004, 0.01, 80)
    rep = detect_decay(bt, live)
    assert rep.status == PAUSE
    assert "aucune ré-optimisation" in rep.action


def test_too_few_trades_is_watch_not_a_verdict():
    rep = detect_decay(np.ones(100), np.array([-1.0, -1.0]))
    assert rep.status == WATCH


def test_slippage_blowout_pauses():
    rng = np.random.default_rng(2)
    bt = rng.normal(0.002, 0.01, 2000)
    rep = detect_decay(bt, rng.normal(0.002, 0.01, 60), expected_slippage_bps=1.0,
                       live_slippage_bps=np.full(60, 3.0))
    assert rep.status == PAUSE


def test_dashboard_renders():
    f = parse_firm({"firm": "f", "status": "template", "rules_verified": False,
                    "programs": [{"name": "p", "phase": "challenge", "account_size": 10_000, "max_total_drawdown": 0.1,
                                  "max_daily_loss": 0.05}]})
    a = PropAccount("a", "f", f.programs[0])
    a.on_mark(9_900, datetime(2026, 1, 5, tzinfo=timezone.utc))
    d = dashboard([account_view(a, kill_switch=KillSwitch())],
                  [strategy_view("s", n_signals=3, live_trades=[0.01, -0.005], expected_edge=0.002)])
    txt = render_text(d)
    assert "a" in txt and "ACTIVE" in txt
