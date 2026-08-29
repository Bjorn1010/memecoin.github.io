import type { BotStatus, MayhemEvent, PortfolioSnapshot, StrategyConfig, StrategyView, Trade } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  strategies: () => fetch("/api/strategies").then((r) => json<StrategyView[]>(r)),
  updateStrategy: (cfg: StrategyConfig) =>
    fetch(`/api/strategies/${cfg.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    }).then((r) => json<{ ok: boolean }>(r)),
  resetStrategy: (strategyId: string) =>
    fetch(`/api/strategies/${strategyId}/reset`, { method: "POST" }).then((r) => json<{ ok: boolean }>(r)),
  trades: (strategyId: string, limit = 200) =>
    fetch(`/api/strategies/${strategyId}/trades?limit=${limit}`).then((r) => json<Trade[]>(r)),
  equity: (strategyId: string, limit = 2000) =>
    fetch(`/api/strategies/${strategyId}/equity?limit=${limit}`).then((r) => json<PortfolioSnapshot[]>(r)),
  events: (limit = 150) => fetch(`/api/events?limit=${limit}`).then((r) => json<MayhemEvent[]>(r)),
  prices: () => fetch("/api/prices").then((r) => json<Record<string, number>>(r)),
  botStatus: () => fetch("/api/bot/status").then((r) => json<BotStatus>(r)),
  startBot: () => fetch("/api/bot/start", { method: "POST" }).then((r) => json<BotStatus>(r)),
  stopBot: () => fetch("/api/bot/stop", { method: "POST" }).then((r) => json<BotStatus>(r)),
};
