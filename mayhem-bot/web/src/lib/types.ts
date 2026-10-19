export type MayhemEventKind = "buy" | "sell" | "full_exit";

export interface MayhemEvent {
  id: string;
  wallet: string;
  kind: MayhemEventKind;
  mint: string;
  signature: string;
  slot: number;
  blockTime: number;
  solAmount: number;
  tokenAmount: number;
  priceSol: number;
  walletTokenBalanceAfter: number;
  detectedAtMs: number;
}

export interface Trade {
  id: string;
  strategyId: string;
  mint: string;
  side: "buy" | "sell";
  reason: string;
  priceSol: number;
  tokenAmount: number;
  solAmount: number;
  feeSol: number;
  priorityFeeSol: number;
  slippagePct: number;
  latencyMs: number;
  createdAt: number;
}

export interface Position {
  mint: string;
  strategyId: string;
  tokenAmount: number;
  avgEntryPriceSol: number;
  solInvested: number;
  openedAt: number;
  peakPriceSol: number;
  entryEventId: string;
}

export interface PortfolioSnapshot {
  strategyId: string;
  timestamp: number;
  solBalance: number;
  unrealizedPnlSol: number;
  realizedPnlSol: number;
  equitySol: number;
  solDeployed: number;
  totalFeesSol: number;
}

export interface StrategyConfig {
  id: string;
  name: string;
  description: string;
  kind: string;
  enabled: boolean;
  startingBalanceSol: number;
  positionSizeSol: number;
  takeProfitPct: number | null;
  stopLossPct: number | null;
  trailingStopPct: number | null;
  maxHoldSeconds: number | null;
  sellOnMayhemFullExit: boolean;
  minMayhemBuySol: number | null;
  minPoolLiquiditySol: number | null;
  maxConcurrentPositions: number;
  priorityFeeSol: number;
}

export interface StrategyView {
  config: StrategyConfig;
  snapshot: PortfolioSnapshot;
  openPositions: Position[];
}

export interface SnapshotPush {
  strategies: StrategyView[];
  prices: Record<string, number>;
}

export interface MonitorStatus {
  wallet: string;
  state: "subscribed" | "error";
  detail?: string;
}

export interface BotStatus {
  running: boolean;
}
