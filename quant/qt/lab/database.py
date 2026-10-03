"""Research database: every experiment, including the rejected ones, append-only.

The deflated Sharpe ratio is only honest if `n_trials` counts everything that was
tried. This module is the only place the pipeline counts from, and it has no delete.
The holdout ledger enforces "consult once" with a UNIQUE constraint, so a second look
is an exception rather than a temptation.

SQLite by default (nothing to install, testable locally). The DDL is standard SQL and
is mirrored in configs/research_db.sql for PostgreSQL.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
    cycle_id        INTEGER PRIMARY KEY,
    started_at      TEXT NOT NULL,
    protocol_hash   TEXT NOT NULL,
    markets_hash    TEXT NOT NULL,
    git_commit      TEXT,
    notes           TEXT
);
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id      TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    asset_class     TEXT NOT NULL,
    source          TEXT NOT NULL,
    first_ts        TEXT,
    last_ts         TEXT,
    n_bars          INTEGER,
    content_hash    TEXT,
    audit_json      TEXT
);
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id          INTEGER NOT NULL REFERENCES cycles(cycle_id),
    timestamp         TEXT NOT NULL,
    stage             TEXT NOT NULL,
    strategy          TEXT NOT NULL,
    family            TEXT,
    market            TEXT NOT NULL,
    timeframe         TEXT NOT NULL,
    features          TEXT,
    parameters        TEXT NOT NULL,
    is_baseline       INTEGER NOT NULL DEFAULT 0,
    counts_as_trial   INTEGER NOT NULL DEFAULT 1,
    train_period      TEXT,
    validation_period TEXT,
    test_period       TEXT,
    cost_model        TEXT,
    slippage_model    TEXT,
    metrics_json      TEXT,
    decision          TEXT,
    reason            TEXT
);
CREATE TABLE IF NOT EXISTS holdout_ledger (
    holdout_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    period          TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    market          TEXT NOT NULL,
    consulted_at    TEXT NOT NULL,
    cycle_id        INTEGER NOT NULL,
    result_json     TEXT,
    UNIQUE (period, strategy, market)
);
CREATE TABLE IF NOT EXISTS decisions (
    decision_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        INTEGER NOT NULL,
    strategy        TEXT NOT NULL,
    market          TEXT NOT NULL,
    stage_reached   TEXT NOT NULL,
    decision        TEXT NOT NULL,
    score_json      TEXT,
    reason          TEXT,
    decided_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy        TEXT NOT NULL,
    market          TEXT NOT NULL,
    account         TEXT,
    symbol          TEXT NOT NULL,
    side            INTEGER NOT NULL,
    expected_entry  REAL, realized_entry REAL,
    expected_exit   REAL, realized_exit  REAL,
    expected_pnl    REAL, realized_pnl   REAL,
    slippage_bps    REAL, latency_ms     REAL,
    opened_at       TEXT, closed_at      TEXT
);
"""


class HoldoutAlreadyConsulted(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def dumps(obj) -> str:
    return json.dumps(_clean(obj), ensure_ascii=False, sort_keys=True, default=str)


class ResearchDB:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------------------------------------------------------------- cycles
    def start_cycle(self, protocol_hash: str, markets_hash: str, git_commit: str | None = None,
                    notes: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO cycles (started_at, protocol_hash, markets_hash, git_commit, notes) VALUES (?,?,?,?,?)",
            (_now(), protocol_hash, markets_hash, git_commit, notes))
        self.conn.commit()
        return int(cur.lastrowid)

    def record_dataset(self, dataset_id: str, **fields) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO datasets (dataset_id, symbol, asset_class, source, first_ts, last_ts, n_bars,"
            " content_hash, audit_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (dataset_id, fields["symbol"], fields["asset_class"], fields.get("source", "yahoo"),
             fields.get("first_ts"), fields.get("last_ts"), fields.get("n_bars"), fields.get("content_hash"),
             dumps(fields.get("audit", {}))))
        self.conn.commit()

    # ---------------------------------------------------------------- experiments
    def record_experiment(self, *, cycle_id: int, stage: str, strategy: str, family: str, market: str,
                          parameters: dict, metrics: dict, timeframe: str = "1d", is_baseline: bool = False,
                          counts_as_trial: bool = True, train_period: str | None = None,
                          validation_period: str | None = None, test_period: str | None = None,
                          cost_model: str | None = None, slippage_model: str | None = None,
                          features: str | None = None, decision: str | None = None,
                          reason: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO experiments (cycle_id, timestamp, stage, strategy, family, market, timeframe, features,"
            " parameters, is_baseline, counts_as_trial, train_period, validation_period, test_period, cost_model,"
            " slippage_model, metrics_json, decision, reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle_id, _now(), stage, strategy, family, market, timeframe, features, dumps(parameters),
             int(is_baseline), int(counts_as_trial), train_period, validation_period, test_period, cost_model,
             slippage_model, dumps(metrics), decision, reason))
        self.conn.commit()
        return int(cur.lastrowid)

    def n_trials(self) -> int:
        """Cumulative across ALL cycles: cycle 2 was designed by someone who saw cycle 1."""
        return int(self.conn.execute("SELECT COUNT(*) FROM experiments WHERE counts_as_trial = 1").fetchone()[0])

    def trial_sharpes(self) -> list[float]:
        rows = self.conn.execute("SELECT metrics_json FROM experiments WHERE counts_as_trial = 1").fetchall()
        out = []
        for (m,) in rows:
            s = json.loads(m or "{}").get("sharpe")
            if s is not None and np.isfinite(s):
                out.append(float(s))
        return out

    def experiments(self, **where) -> list[dict]:
        sql = "SELECT * FROM experiments"
        args: list = []
        if where:
            sql += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
            args = list(where.values())
        cur = self.conn.execute(sql, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ---------------------------------------------------------------- holdout
    def consult(self, *, period: str, strategy: str, market: str, cycle_id: int, result: dict) -> None:
        """Register a look at a sealed period. Raises if it was already looked at."""
        try:
            self.conn.execute(
                "INSERT INTO holdout_ledger (period, strategy, market, consulted_at, cycle_id, result_json)"
                " VALUES (?,?,?,?,?,?)", (period, strategy, market, _now(), cycle_id, dumps(result)))
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise HoldoutAlreadyConsulted(
                f"la période '{period}' a déjà été consultée pour {strategy} / {market} : "
                "la réutiliser en ferait un jeu de validation") from exc

    def was_consulted(self, *, period: str, strategy: str, market: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM holdout_ledger WHERE period=? AND strategy=? AND market=?",
                                (period, strategy, market)).fetchone()
        return row is not None

    # ---------------------------------------------------------------- decisions
    def record_decision(self, *, cycle_id: int, strategy: str, market: str, stage_reached: str,
                        decision: str, score: dict, reason: str) -> None:
        self.conn.execute(
            "INSERT INTO decisions (cycle_id, strategy, market, stage_reached, decision, score_json, reason,"
            " decided_at) VALUES (?,?,?,?,?,?,?,?)",
            (cycle_id, strategy, market, stage_reached, decision, dumps(score), reason, _now()))
        self.conn.commit()

    def decisions(self, cycle_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM decisions" + (" WHERE cycle_id = ?" if cycle_id else "")
        cur = self.conn.execute(sql, (cycle_id,) if cycle_id else ())
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
