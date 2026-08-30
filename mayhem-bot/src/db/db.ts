import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync, type SQLInputValue } from "node:sqlite";
import { config } from "../config.js";
import type { MayhemEvent, PortfolioSnapshot, StrategyConfig, Trade } from "../types.js";
import type { PortfolioState } from "../engine/portfolio.js";

// node:sqlite wants plain Record<string, SQLInputValue> objects; our domain types are
// structurally identical (numbers/strings only) but not indexable, so we bridge the type here.
function asParams(obj: object): Record<string, SQLInputValue> {
  return obj as unknown as Record<string, SQLInputValue>;
}

const dir = dirname(config.dbPath);
if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

export const db = new DatabaseSync(config.dbPath);
db.exec("PRAGMA journal_mode = WAL");

const schemaPath = new URL("./schema.sql", import.meta.url);
db.exec(readFileSync(schemaPath, "utf-8"));

export function insertMayhemEvent(e: MayhemEvent) {
  db.prepare(
    `INSERT OR IGNORE INTO mayhem_events
     (id, wallet, kind, mint, signature, slot, block_time, sol_amount, token_amount, price_sol, wallet_token_balance_after, detected_at_ms, sol_reserves_ui, token_reserves_ui)
     VALUES (@id, @wallet, @kind, @mint, @signature, @slot, @blockTime, @solAmount, @tokenAmount, @priceSol, @walletTokenBalanceAfter, @detectedAtMs, @solReservesUi, @tokenReservesUi)`,
  ).run(
    asParams({
      ...e,
      solReservesUi: e.solReservesUi ?? null,
      tokenReservesUi: e.tokenReservesUi ?? null,
    }),
  );
}

export function insertTrade(t: Trade) {
  db.prepare(
    `INSERT INTO trades (id, strategy_id, mint, side, reason, price_sol, token_amount, sol_amount, fee_sol, priority_fee_sol, slippage_pct, latency_ms, created_at)
     VALUES (@id, @strategyId, @mint, @side, @reason, @priceSol, @tokenAmount, @solAmount, @feeSol, @priorityFeeSol, @slippagePct, @latencyMs, @createdAt)`,
  ).run(asParams(t));
}

export function insertSnapshot(s: PortfolioSnapshot) {
  db.prepare(
    `INSERT INTO portfolio_snapshots (strategy_id, timestamp, sol_balance, unrealized_pnl_sol, realized_pnl_sol, equity_sol, sol_deployed, total_fees_sol)
     VALUES (@strategyId, @timestamp, @solBalance, @unrealizedPnlSol, @realizedPnlSol, @equitySol, @solDeployed, @totalFeesSol)`,
  ).run(asParams(s));
}

/**
 * Trims the raw firehose tables to a rolling window and reclaims the freed pages.
 *
 * mayhem_events grows at roughly 30k rows/hour (~5-10 Mayhem trades a second), which pushed
 * the committed DB past GitHub's 50MB advisory limit within a few hours and would hit the
 * hard 100MB cap — at which point pushes fail outright and the run history stops being
 * saved at all. Events are pure raw input: they are only needed live, to sanity-check a
 * fresh trade's fill price against the prices actually seen on-chain around it, so a couple
 * of hours is ample. What must survive is the small stuff — trades, portfolio_state,
 * migrated_mints — which together are a rounding error on the file size.
 */
export function pruneOldData(maxAgeMs: number) {
  const cutoff = Date.now() - maxAgeMs;
  const events = db.prepare(`DELETE FROM mayhem_events WHERE detected_at_ms < ?`).run(cutoff);
  const snaps = db.prepare(`DELETE FROM portfolio_snapshots WHERE timestamp < ?`).run(cutoff);
  const removed = Number(events.changes ?? 0) + Number(snaps.changes ?? 0);
  // VACUUM only when something substantial was freed: it rewrites the whole file, so running
  // it on every sweep would be wasted IO for no size win.
  if (removed > 10_000) db.exec("VACUUM");
  return removed;
}

export function markMintMigrated(mint: string) {
  db.prepare(`INSERT OR IGNORE INTO migrated_mints (mint, detected_at) VALUES (?, ?)`).run(mint, Date.now());
}

export function loadMigratedMints(): string[] {
  const rows = db.prepare(`SELECT mint FROM migrated_mints`).all() as { mint: string }[];
  return rows.map((r) => r.mint);
}

export function savePortfolioState(strategyId: string, state: PortfolioState) {
  db.prepare(
    `INSERT INTO portfolio_state (strategy_id, state_json, updated_at) VALUES (?, ?, ?)
     ON CONFLICT(strategy_id) DO UPDATE SET state_json = excluded.state_json, updated_at = excluded.updated_at`,
  ).run(strategyId, JSON.stringify(state), Date.now());
}

/** Returns the saved live state for a strategy, or null when there's nothing to resume
 * (first ever run, or a row too corrupt to parse — either way, start fresh). */
export function loadPortfolioState(strategyId: string): PortfolioState | null {
  const row = db.prepare(`SELECT state_json FROM portfolio_state WHERE strategy_id = ?`).get(strategyId) as
    | { state_json: string }
    | undefined;
  if (!row) return null;
  try {
    return JSON.parse(row.state_json) as PortfolioState;
  } catch {
    return null;
  }
}

export function clearPortfolioState(strategyId: string) {
  db.prepare(`DELETE FROM portfolio_state WHERE strategy_id = ?`).run(strategyId);
}

export function upsertStrategyConfig(cfg: StrategyConfig) {
  db.prepare(
    `INSERT INTO strategies (id, config_json) VALUES (?, ?)
     ON CONFLICT(id) DO UPDATE SET config_json = excluded.config_json`,
  ).run(cfg.id, JSON.stringify(cfg));
}

export function recentTrades(strategyId: string, limit = 200): Trade[] {
  const rows = db
    .prepare(
      `SELECT id, strategy_id as strategyId, mint, side, reason, price_sol as priceSol,
              token_amount as tokenAmount, sol_amount as solAmount, fee_sol as feeSol,
              priority_fee_sol as priorityFeeSol, slippage_pct as slippagePct,
              latency_ms as latencyMs, created_at as createdAt
       FROM trades WHERE strategy_id = ? ORDER BY created_at DESC LIMIT ?`,
    )
    .all(strategyId, limit) as unknown as Trade[];
  return rows;
}

export function equityCurve(strategyId: string, limit = 2000): PortfolioSnapshot[] {
  const rows = db
    .prepare(
      `SELECT strategy_id as strategyId, timestamp, sol_balance as solBalance,
              unrealized_pnl_sol as unrealizedPnlSol, realized_pnl_sol as realizedPnlSol, equity_sol as equitySol,
              sol_deployed as solDeployed, total_fees_sol as totalFeesSol
       FROM portfolio_snapshots WHERE strategy_id = ? ORDER BY timestamp DESC LIMIT ?`,
    )
    .all(strategyId, limit) as unknown as PortfolioSnapshot[];
  return rows.reverse();
}

export function recentMayhemEvents(limit = 100): MayhemEvent[] {
  const rows = db
    .prepare(
      `SELECT id, wallet, kind, mint, signature, slot, block_time as blockTime, sol_amount as solAmount,
              token_amount as tokenAmount, price_sol as priceSol, wallet_token_balance_after as walletTokenBalanceAfter,
              detected_at_ms as detectedAtMs, sol_reserves_ui as solReservesUi, token_reserves_ui as tokenReservesUi
       FROM mayhem_events ORDER BY detected_at_ms DESC LIMIT ?`,
    )
    .all(limit) as unknown as MayhemEvent[];
  return rows;
}
