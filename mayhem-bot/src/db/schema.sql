CREATE TABLE IF NOT EXISTS mayhem_events (
  id TEXT PRIMARY KEY,
  wallet TEXT NOT NULL,
  kind TEXT NOT NULL,
  mint TEXT NOT NULL,
  signature TEXT NOT NULL,
  slot INTEGER NOT NULL,
  block_time INTEGER NOT NULL,
  sol_amount REAL NOT NULL,
  token_amount REAL NOT NULL,
  price_sol REAL NOT NULL,
  wallet_token_balance_after REAL NOT NULL,
  detected_at_ms INTEGER NOT NULL,
  sol_reserves_ui REAL,
  token_reserves_ui REAL
);

CREATE TABLE IF NOT EXISTS trades (
  id TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL,
  mint TEXT NOT NULL,
  side TEXT NOT NULL,
  reason TEXT NOT NULL,
  price_sol REAL NOT NULL,
  token_amount REAL NOT NULL,
  sol_amount REAL NOT NULL,
  fee_sol REAL NOT NULL DEFAULT 0,
  priority_fee_sol REAL NOT NULL DEFAULT 0,
  slippage_pct REAL NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  strategy_id TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  sol_balance REAL NOT NULL,
  unrealized_pnl_sol REAL NOT NULL,
  realized_pnl_sol REAL NOT NULL,
  equity_sol REAL NOT NULL,
  sol_deployed REAL NOT NULL DEFAULT 0,
  total_fees_sol REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  config_json TEXT NOT NULL
);

-- Live portfolio state (balance, realized PnL, fees, open positions) per strategy, so a
-- restart resumes where it left off instead of silently resetting every strategy back to
-- its starting bankroll. This environment recycles the container whenever the session goes
-- idle, so without this the bot can never build up a track record longer than one sitting.
-- Mints whose bonding curve has completed. Their curve keeps emitting pump.fun trade events
-- afterwards, but those describe a pool that no longer sets the price, so we must never let
-- them back into the price/reserves caches. Persisted because a restart would otherwise
-- forget and start trusting stale curve data again.
CREATE TABLE IF NOT EXISTS migrated_mints (
  mint TEXT PRIMARY KEY,
  detected_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_state (
  strategy_id TEXT PRIMARY KEY,
  state_json TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id, created_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_strategy ON portfolio_snapshots(strategy_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_mint ON mayhem_events(mint);
