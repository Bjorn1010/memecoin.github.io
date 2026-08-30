/** Raw on-chain event detected from a tracked Mayhem wallet. */
export type MayhemEventKind = "buy" | "sell" | "full_exit";

export interface MayhemEvent {
  id: string;
  wallet: string;
  kind: MayhemEventKind;
  mint: string;
  signature: string;
  slot: number;
  blockTime: number; // unix seconds
  solAmount: number; // absolute SOL moved (excluding fees)
  tokenAmount: number; // absolute token UI amount moved
  priceSol: number; // SOL per token at time of trade
  walletTokenBalanceAfter: number; // Mayhem's remaining UI balance of this mint after the trade
  detectedAtMs: number; // local clock time we finished processing this event
  /** Bonding curve reserves right after this trade, when known (fast log-decoded path only).
   * Lets us simulate OUR OWN fill against the real AMM curve instead of just reusing
   * Mayhem's fill price — the same trade size hits a different, worse price for us. */
  solReservesUi?: number;
  tokenReservesUi?: number;
}

export type ExitReason =
  | "take_profit"
  | "stop_loss"
  | "trailing_stop"
  | "mayhem_full_exit"
  | "max_hold_time"
  | "manual";

export interface Trade {
  id: string;
  strategyId: string;
  mint: string;
  side: "buy" | "sell";
  reason: string; // entry trigger or ExitReason
  priceSol: number; // effective fill price, after slippage
  tokenAmount: number;
  solAmount: number; // net SOL moved (what you actually paid / actually received)
  feeSol: number; // Padre/pump.fun platform fee (1% of notional)
  priorityFeeSol: number; // flat network/priority-tip cost
  slippagePct: number; // (fill price vs pre-trade spot price) - 0 when no pool depth was known
  latencyMs: number; // time between the mayhem on-chain event and our paper fill
  createdAt: number;
}

export interface Position {
  mint: string;
  strategyId: string;
  tokenAmount: number;
  avgEntryPriceSol: number;
  solInvested: number;
  openedAt: number;
  peakPriceSol: number; // for trailing stop tracking
  entryEventId: string;
}

export interface PortfolioSnapshot {
  strategyId: string;
  timestamp: number;
  solBalance: number;
  unrealizedPnlSol: number;
  realizedPnlSol: number;
  equitySol: number;
  solDeployed: number; // sum of cost basis currently in open positions — "combien le bot a acheté"
  totalFeesSol: number; // cumulative platform fees + priority fees paid, ever
}

export interface StrategyConfig {
  id: string;
  name: string;
  description: string;
  kind: string; // strategy implementation key
  enabled: boolean;
  startingBalanceSol: number;
  positionSizeSol: number;
  takeProfitPct: number | null; // e.g. 0.1 = +10%
  stopLossPct: number | null; // e.g. 0.1 = -10%
  trailingStopPct: number | null; // e.g. 0.2 = -20% from peak
  maxHoldSeconds: number | null;
  sellOnMayhemFullExit: boolean;
  minMayhemBuySol: number | null; // ignore mayhem buys smaller than this
  minPoolLiquiditySol: number | null; // ignore entries into pools shallower than this (SOL-side reserves) — thin pools mean brutal AMM slippage
  maxConcurrentPositions: number;
  priorityFeeSol: number; // flat simulated priority/tip fee paid per trade, each side
  /** Don't copy the buy on the bonding curve at all — watch the mint and only enter once
   * it migrates off pump.fun onto a real AMM pool, trading whatever deeper liquidity that
   * pool has instead of the ~16 SOL median reserves Mayhem snipes into pre-migration. */
  waitForMigration: boolean;
}
