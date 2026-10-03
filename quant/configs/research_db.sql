-- Schéma de la base de recherche, version PostgreSQL.
-- Miroir de qt/lab/database.py (SQLite par défaut). Append-only : aucune requête DELETE n'est prévue.

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
    experiment_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    holdout_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    period          TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    market          TEXT NOT NULL,
    consulted_at    TEXT NOT NULL,
    cycle_id        INTEGER NOT NULL,
    result_json     TEXT,
    UNIQUE (period, strategy, market)
);
CREATE TABLE IF NOT EXISTS decisions (
    decision_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    trade_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
