import { fmtPrice, shortAddr, timeAgo } from "../lib/format";
import type { StrategyConfig, Trade } from "../lib/types";

const REASON_LABEL: Record<string, string> = {
  copy_mayhem_buy: "copie achat",
  take_profit: "take profit",
  stop_loss: "stop loss",
  trailing_stop: "trailing stop",
  mayhem_full_exit: "mayhem a tout vendu",
  max_hold_time: "durée max atteinte",
};

export function TradeFeed({ trades, strategies }: { trades: Trade[]; strategies: StrategyConfig[] }) {
  const nameOf = (id: string) => strategies.find((s) => s.id === id)?.name ?? id;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-panel shadow-card">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-[13px] font-semibold">Ce que fait le bot</h3>
        <p className="text-[11px] text-dim">Frais Padre 1% + priorité + slippage AMM inclus dans chaque fill</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {trades.length === 0 ? (
          <div className="p-6 text-center text-xs text-dim">Aucun trade encore</div>
        ) : (
          trades.map((t) => {
            const totalCost = t.feeSol + t.priorityFeeSol;
            return (
              <div key={t.id} className="border-b border-border/50 px-4 py-2.5 text-xs hover:bg-panel2/40">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-10 shrink-0 rounded px-1.5 py-0.5 text-center font-mono text-[11px] font-bold ${
                      t.side === "buy" ? "bg-up/10 text-up" : "bg-down/10 text-down"
                    }`}
                  >
                    {t.side === "buy" ? "BUY" : "SELL"}
                  </span>
                  <span className="font-mono text-muted">{shortAddr(t.mint)}</span>
                  <span className="ml-auto font-mono tabular font-medium text-white">
                    {fmtPrice(t.priceSol)} SOL
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[10.5px] text-dim">
                  <span>
                    {nameOf(t.strategyId)} · {REASON_LABEL[t.reason] ?? t.reason}
                    {t.side === "buy" && t.latencyMs > 0 ? ` · ${t.latencyMs}ms` : ""}
                  </span>
                  <span>{timeAgo(t.createdAt)}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-[10.5px] text-dim">
                  <span title="Frais plateforme + priorité">frais -{totalCost.toFixed(5)} SOL</span>
                  {Math.abs(t.slippagePct) > 0.0001 && (
                    <span className={t.slippagePct < 0 ? "text-down/80" : "text-up/80"} title="Slippage AMM">
                      slip {t.slippagePct >= 0 ? "+" : ""}
                      {(t.slippagePct * 100).toFixed(2)}%
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
