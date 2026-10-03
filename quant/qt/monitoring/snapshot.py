"""Monitoring snapshot: one read-only dict with everything the dashboard shows.

Per account: equity, P&L, drawdown, positions, orders, exposure, risk budget, status,
slippage, latency, errors, kill-switch state. Per strategy: signals, trades, expected
edge vs realised edge, decay status. Read-only by design — a dashboard that can change
positions is an accident waiting for a mis-click.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np


def account_view(account, oms=None, kill_switch=None, latencies_ms: list[float] | None = None) -> dict:
    snap = account.snapshot()
    view = {**snap, "kill_switch": kill_switch.reason(account.account_id) if kill_switch else ""}
    if oms is not None:
        orders = list(oms.orders.values())
        view["open_orders"] = [o.order_id for o in orders if o.status.is_open]
        view["rejected_orders"] = sum(1 for o in orders if o.status.value == "rejected")
        view["errors"] = [e for e in oms.log if e["event"] in ("transport_error", "position_mismatch", "rejected")][-20:]
    if latencies_ms:
        view["latency_ms_p50"] = float(np.median(latencies_ms))
        view["latency_ms_p95"] = float(np.quantile(latencies_ms, 0.95))
    return view


def strategy_view(name: str, *, n_signals: int, live_trades: list[float], expected_edge: float,
                  decay=None, slippage_bps: list[float] | None = None) -> dict:
    lt = np.asarray(live_trades, dtype="float64")
    return {
        "strategy": name, "signals": n_signals, "trades": int(len(lt)),
        "expected_edge": expected_edge,
        "realized_edge": float(lt.mean()) if len(lt) else None,
        "slippage_bps_avg": float(np.mean(slippage_bps)) if slippage_bps else None,
        "decay_status": getattr(decay, "status", None),
        "decay_reasons": getattr(decay, "reasons", []),
    }


def dashboard(accounts: list[dict], strategies: list[dict], kill_switch=None) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "global_kill_switch": kill_switch.reason("*") if kill_switch and kill_switch.is_tripped("*") else "",
        "accounts": accounts,
        "strategies": strategies,
        "totals": {
            "equity": sum(a["equity"] for a in accounts),
            "exposure": sum(a.get("exposure", 0.0) for a in accounts),
            "accounts_by_status": {s: sum(1 for a in accounts if a["status"] == s)
                                   for s in {a["status"] for a in accounts}},
        },
    }


def render_text(d: dict) -> str:
    lines = [f"== monitoring {d['generated_at']} ==",
             f"kill switch global : {d['global_kill_switch'] or 'armé, non déclenché'}"]
    for a in d["accounts"]:
        lines.append(f"[{a['status']:14s}] {a['account_id']:20s} équité {a['equity']:>12,.2f}  "
                     f"P&L jour {a['daily_pnl']:>+10,.2f}  DD utilisé {a['drawdown_used']:>5.0%}  "
                     f"budget {a['risk_budget']:>10,.2f}  {a.get('reason', '')}")
    for s in d["strategies"]:
        lines.append(f"  {s['strategy']}: {s['trades']} trades, edge attendu {s['expected_edge']:+.4f}, "
                     f"réalisé {s['realized_edge'] if s['realized_edge'] is not None else 'n/a'} — {s['decay_status']}")
    return "\n".join(lines)
