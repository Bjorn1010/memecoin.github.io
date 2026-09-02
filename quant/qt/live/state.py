"""Durable state for the paper-trading loop.

SQLite, because the requirements are exactly what SQLite is good at: a single writer,
crash-safe, zero administration, and readable by any tool without the application
running. If the process dies mid-session, the book is on disk and the loop resumes
from it rather than silently restarting flat — a restart that quietly resets the
portfolio is the paper-trading equivalent of losing your position.

Everything a decision depended on is stored alongside the decision: the signal, the
weight the model asked for, the weight risk allowed, and why it was cut. Reconstructing
"why did it do that" three weeks later from prices alone is impossible, and that
question is most of what running a system consists of.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running',
    note        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bars (
    run_id  TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    ts      INTEGER NOT NULL,
    open    REAL, high REAL, low REAL, close REAL,
    volume  REAL, quote_volume REAL, trades REAL,
    buy_volume REAL, sell_volume REAL,
    PRIMARY KEY (run_id, symbol, ts)
);

CREATE TABLE IF NOT EXISTS decisions (
    run_id        TEXT NOT NULL,
    ts            INTEGER NOT NULL,
    symbol        TEXT NOT NULL,
    signal        REAL,
    target_weight REAL,   -- what the strategy asked for
    allowed_weight REAL,  -- what risk permitted
    risk_scale    REAL,
    risk_reason   TEXT,
    equity        REAL,
    PRIMARY KEY (run_id, symbol, ts)
);

CREATE TABLE IF NOT EXISTS fills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    ts            INTEGER NOT NULL,
    symbol        TEXT NOT NULL,
    side          TEXT NOT NULL,
    qty           REAL NOT NULL,
    price         REAL NOT NULL,
    reference_price REAL,
    notional      REAL NOT NULL,
    commission    REAL NOT NULL,
    spread_cost   REAL NOT NULL,
    impact_cost   REAL NOT NULL,
    slippage_bps  REAL,
    reason        TEXT
);

CREATE TABLE IF NOT EXISTS equity (
    run_id    TEXT NOT NULL,
    ts        INTEGER NOT NULL,
    equity    REAL NOT NULL,
    cash      REAL NOT NULL,
    gross_exposure REAL NOT NULL,
    drawdown  REAL NOT NULL,
    halted    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, ts)
);

CREATE TABLE IF NOT EXISTS positions (
    run_id   TEXT NOT NULL,
    symbol   TEXT NOT NULL,
    qty      REAL NOT NULL,
    avg_price REAL NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_fills_run_ts ON fills(run_id, ts);
CREATE INDEX IF NOT EXISTS idx_equity_run_ts ON equity(run_id, ts);
CREATE INDEX IF NOT EXISTS idx_decisions_run_ts ON decisions(run_id, ts);
"""


@dataclass
class Position:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0

    def apply_fill(self, qty: float, price: float) -> float:
        """Update the position and return the realised PnL of this fill."""
        realised = 0.0
        if self.qty == 0 or (self.qty > 0) == (qty > 0):
            # Opening or adding: weighted-average the entry price.
            total = self.qty + qty
            if total != 0:
                self.avg_price = (self.avg_price * self.qty + price * qty) / total
            self.qty = total
        else:
            # Reducing or flipping: realise PnL on the closed portion.
            closing = min(abs(qty), abs(self.qty))
            direction = 1.0 if self.qty > 0 else -1.0
            realised = closing * (price - self.avg_price) * direction
            self.qty += qty
            if (self.qty > 0) != (direction > 0) and self.qty != 0:
                self.avg_price = price  # flipped through zero
            elif self.qty == 0:
                self.avg_price = 0.0
        return realised


@dataclass
class LiveState:
    run_id: str
    equity: float
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    halted: bool = False

    def position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol))


class Store:
    """Thin SQLite wrapper. One connection, WAL mode, explicit transactions."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # WAL lets the dashboard read while the loop writes.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    @contextmanager
    def tx(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ------------------------------------------------------------------ runs
    def start_run(self, run_id: str, config: dict, note: str = "") -> None:
        with self.tx() as c:
            c.execute(
                "INSERT OR REPLACE INTO runs(run_id, started_at, config_json, status, note) VALUES (?,?,?,?,?)",
                (run_id, int(pd.Timestamp.now("UTC").value // 10**6), json.dumps(config, default=str), "running", note),
            )

    def finish_run(self, run_id: str, status: str = "stopped") -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))

    def runs(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM runs ORDER BY started_at DESC", self.conn)

    def latest_run_id(self) -> str | None:
        row = self.conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return row["run_id"] if row else None

    # ------------------------------------------------------------------ bars
    def record_bar(self, run_id: str, symbol: str, bar: dict) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO bars
                   (run_id, symbol, ts, open, high, low, close, volume, quote_volume, trades,
                    buy_volume, sell_volume)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, symbol, int(bar["ts"]), bar.get("open"), bar.get("high"), bar.get("low"),
                    bar.get("close"), bar.get("volume"), bar.get("quote_volume"), bar.get("trades"),
                    bar.get("buy_volume"), bar.get("sell_volume"),
                ),
            )

    def bars(self, run_id: str, symbol: str, limit: int = 5000) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM bars WHERE run_id=? AND symbol=? ORDER BY ts DESC LIMIT ?",
            self.conn, params=(run_id, symbol, limit),
        ).sort_values("ts").reset_index(drop=True)

    # ------------------------------------------------------------- decisions
    def record_decision(self, run_id: str, ts: int, symbol: str, **kw) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO decisions
                   (run_id, ts, symbol, signal, target_weight, allowed_weight, risk_scale, risk_reason, equity)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, int(ts), symbol, kw.get("signal"), kw.get("target_weight"),
                    kw.get("allowed_weight"), kw.get("risk_scale"), kw.get("risk_reason", ""),
                    kw.get("equity"),
                ),
            )

    def decisions(self, run_id: str, limit: int = 500) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM decisions WHERE run_id=? ORDER BY ts DESC LIMIT ?",
            self.conn, params=(run_id, limit),
        )

    # ----------------------------------------------------------------- fills
    def record_fill(self, run_id: str, ts: int, symbol: str, **kw) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT INTO fills
                   (run_id, ts, symbol, side, qty, price, reference_price, notional,
                    commission, spread_cost, impact_cost, slippage_bps, reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, int(ts), symbol, kw["side"], kw["qty"], kw["price"],
                    kw.get("reference_price"), kw["notional"], kw.get("commission", 0.0),
                    kw.get("spread_cost", 0.0), kw.get("impact_cost", 0.0),
                    kw.get("slippage_bps"), kw.get("reason", ""),
                ),
            )

    def fills(self, run_id: str, limit: int = 500) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM fills WHERE run_id=? ORDER BY ts DESC LIMIT ?",
            self.conn, params=(run_id, limit),
        )

    # ---------------------------------------------------------------- equity
    def record_equity(self, run_id: str, ts: int, equity: float, cash: float,
                      gross_exposure: float, drawdown: float, halted: bool) -> None:
        with self.tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO equity(run_id, ts, equity, cash, gross_exposure, drawdown, halted)
                   VALUES (?,?,?,?,?,?,?)""",
                (run_id, int(ts), equity, cash, gross_exposure, drawdown, int(halted)),
            )

    def equity_curve(self, run_id: str, limit: int = 10000) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM equity WHERE run_id=? ORDER BY ts DESC LIMIT ?",
            self.conn, params=(run_id, limit),
        ).sort_values("ts").reset_index(drop=True)

    # ------------------------------------------------------------- positions
    def save_positions(self, run_id: str, positions: dict[str, Position], ts: int) -> None:
        with self.tx() as c:
            for symbol, pos in positions.items():
                c.execute(
                    """INSERT OR REPLACE INTO positions(run_id, symbol, qty, avg_price, updated_at)
                       VALUES (?,?,?,?,?)""",
                    (run_id, symbol, pos.qty, pos.avg_price, int(ts)),
                )

    def load_positions(self, run_id: str) -> dict[str, Position]:
        rows = self.conn.execute(
            "SELECT symbol, qty, avg_price FROM positions WHERE run_id=?", (run_id,)
        ).fetchall()
        return {r["symbol"]: Position(r["symbol"], r["qty"], r["avg_price"]) for r in rows}

    def positions_frame(self, run_id: str) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM positions WHERE run_id=?", self.conn, params=(run_id,))

    def close(self) -> None:
        self.conn.close()


def state_to_dict(state: LiveState) -> dict:
    return {
        "run_id": state.run_id,
        "equity": state.equity,
        "cash": state.cash,
        "halted": state.halted,
        "positions": {s: asdict(p) for s, p in state.positions.items()},
    }
