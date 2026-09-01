"""Read-only HTTP API over the paper-trading state.

Deliberately read-only. The dashboard observes; it cannot start, stop, resize or
override anything. A control surface reachable over HTTP is how a monitoring tool
turns into an accident, and there is nothing here worth that risk — the loop is
controlled from the CLI, on the machine it runs on.

Serves the SQLite store in WAL mode, so it reads a live session without blocking it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..backtest.metrics import performance_metrics
from ..config import CONFIG
from ..live.state import Store

app = FastAPI(
    title="qt paper trading",
    description="Read-only monitoring for a paper-trading run. No real orders exist in this system.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store(CONFIG.state_db)
    return _store


def _resolve_run(run_id: str | None) -> str:
    rid = run_id or store().latest_run_id()
    if rid is None:
        raise HTTPException(404, "no runs recorded yet — start the paper loop first")
    return rid


def _clean(obj):
    """JSON-safe: NaN/Inf are not valid JSON and silently break the frontend."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if not np.isfinite(f) else f
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return _clean(df.replace([np.inf, -np.inf], np.nan).where(pd.notna(df), None).to_dict("records"))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "paper_only": True, "db": str(CONFIG.state_db)}


@app.get("/api/runs")
def runs() -> dict:
    return {"runs": _records(store().runs())}


@app.get("/api/summary")
def summary(run_id: str | None = None) -> dict:
    rid = _resolve_run(run_id)
    st = store()
    eq = st.equity_curve(rid)
    positions = st.positions_frame(rid)
    fills = st.fills(rid, limit=100_000)

    metrics: dict = {}
    if not eq.empty and len(eq) > 2:
        series = pd.Series(eq["equity"].to_numpy(), index=pd.to_datetime(eq["ts"], unit="ms", utc=True))

        class _R:  # duck-typed for performance_metrics
            equity = series
            returns = series.pct_change().fillna(0.0)
            weights = pd.DataFrame()
            costs = pd.Series(dtype="float64")
            trades = pd.DataFrame()

        # Infer the bar frequency from the equity stamps rather than assuming it.
        gaps = np.diff(eq["ts"].to_numpy())
        bar_seconds = float(np.median(gaps)) / 1000.0 if gaps.size else 3600.0
        metrics = performance_metrics(_R(), bars_per_year=365 * 24 * 3600 / max(bar_seconds, 1.0))

    total_costs = float(
        fills[["commission", "spread_cost", "impact_cost"]].sum().sum()
    ) if not fills.empty else 0.0

    return _clean(
        {
            "run_id": rid,
            "metrics": metrics,
            "n_fills": int(len(fills)),
            "total_costs": total_costs,
            "positions": _records(positions),
            "latest": _records(eq.tail(1))[0] if not eq.empty else None,
            "paper_only": True,
        }
    )


@app.get("/api/equity")
def equity(run_id: str | None = None, limit: int = Query(5000, ge=1, le=100_000)) -> dict:
    rid = _resolve_run(run_id)
    return {"run_id": rid, "equity": _records(store().equity_curve(rid, limit))}


@app.get("/api/fills")
def fills(run_id: str | None = None, limit: int = Query(200, ge=1, le=5000)) -> dict:
    rid = _resolve_run(run_id)
    return {"run_id": rid, "fills": _records(store().fills(rid, limit))}


@app.get("/api/decisions")
def decisions(run_id: str | None = None, limit: int = Query(200, ge=1, le=5000)) -> dict:
    """Why the book looks the way it does: signal, requested weight, allowed weight."""
    rid = _resolve_run(run_id)
    return {"run_id": rid, "decisions": _records(store().decisions(rid, limit))}


@app.get("/api/bars")
def bars(symbol: str, run_id: str | None = None, limit: int = Query(1000, ge=1, le=20_000)) -> dict:
    rid = _resolve_run(run_id)
    return {"run_id": rid, "symbol": symbol, "bars": _records(store().bars(rid, symbol, limit))}


@app.get("/api/alphas")
def alphas() -> dict:
    """The alpha library with its stated rationales — the strategy's documentation."""
    from .. import alphas as A

    return {"alphas": _records(A.describe())}


@app.get("/api/features")
def features() -> dict:
    from .. import features as F

    reg = F.registry()
    return {
        "groups": [
            {"name": n, "description": g.description, "warmup": g.warmup, "tags": list(g.tags)}
            for n, g in sorted(reg.items())
        ]
    }


@app.get("/api/lake")
def lake() -> dict:
    from ..data import Catalog

    return {"inventory": _records(Catalog().inventory())}


# The built dashboard, when present, is served from the same origin.
_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@app.get("/")
def index():
    index_file = _WEB_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "qt paper-trading API. Build the dashboard with `npm --prefix web run build`.",
        "endpoints": [
            "/api/health", "/api/runs", "/api/summary", "/api/equity",
            "/api/fills", "/api/decisions", "/api/bars?symbol=...",
            "/api/alphas", "/api/features", "/api/lake",
        ],
    }


def mount_static() -> None:
    """Mount the built dashboard assets if they exist."""
    if _WEB_DIST.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=_WEB_DIST / "assets"), name="assets")


mount_static()
