export interface EquityPoint {
  ts: number;
  equity: number;
  cash: number;
  gross_exposure: number;
  drawdown: number;
  halted: number;
}

export interface Fill {
  ts: number;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  notional: number;
  commission: number;
  spread_cost: number;
  impact_cost: number;
  slippage_bps: number | null;
  reason: string;
}

export interface Decision {
  ts: number;
  symbol: string;
  signal: number | null;
  target_weight: number | null;
  allowed_weight: number | null;
  risk_scale: number | null;
  risk_reason: string;
  equity: number | null;
}

export interface PositionRow {
  symbol: string;
  qty: number;
  avg_price: number;
}

export interface Summary {
  run_id: string;
  metrics: Record<string, number | null>;
  n_fills: number;
  total_costs: number;
  positions: PositionRow[];
  latest: EquityPoint | null;
  paper_only: boolean;
}

export interface AlphaRow {
  name: string;
  family: string;
  horizon_bars: number;
  rationale: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return (await res.json()) as T;
}

export const api = {
  summary: () => get<Summary>("/api/summary"),
  equity: () => get<{ equity: EquityPoint[] }>("/api/equity?limit=5000"),
  fills: () => get<{ fills: Fill[] }>("/api/fills?limit=100"),
  decisions: () => get<{ decisions: Decision[] }>("/api/decisions?limit=100"),
  alphas: () => get<{ alphas: AlphaRow[] }>("/api/alphas"),
  runs: () => get<{ runs: { run_id: string; started_at: number; status: string }[] }>("/api/runs"),
};
