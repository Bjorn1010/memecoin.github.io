import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtPct, fmtPrice, shortAddr, timeAgo } from "../lib/format";
import type { PortfolioSnapshot, StrategyView } from "../lib/types";
import { EquityChart } from "./EquityChart";
import { GearIcon, PlayIcon, ResetIcon, StopIcon } from "./icons";

export function StrategyCard({
  view,
  prices,
  onEdit,
}: {
  view: StrategyView;
  prices: Record<string, number>;
  onEdit: () => void;
}) {
  const { config, snapshot, openPositions } = view;
  const [equity, setEquity] = useState<PortfolioSnapshot[]>([]);

  useEffect(() => {
    api.equity(config.id, 500).then(setEquity).catch(() => {});
  }, [config.id]);

  useEffect(() => {
    setEquity((prev) => [...prev, snapshot].slice(-500));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot.timestamp]);

  const totalPnl = snapshot.realizedPnlSol + snapshot.unrealizedPnlSol;
  const pnlPct = config.startingBalanceSol > 0 ? totalPnl / config.startingBalanceSol : 0;
  const deployedPct = config.startingBalanceSol > 0 ? snapshot.solDeployed / config.startingBalanceSol : 0;
  const isBankrupt = openPositions.length === 0 && snapshot.solBalance <= config.priorityFeeSol;

  async function toggleEnabled() {
    await api.updateStrategy({ ...config, enabled: !config.enabled });
  }

  async function reset() {
    if (!confirm(`Réinitialiser "${config.name}" au solde de départ (${config.startingBalanceSol} SOL) ?`)) return;
    await api.resetStrategy(config.id);
  }

  return (
    <div
      className={`flex flex-col overflow-hidden rounded-xl border bg-panel shadow-card transition-colors ${
        config.enabled ? "border-border" : "border-border/50 opacity-70"
      }`}
    >
      <div
        className={`h-[2px] w-full ${totalPnl >= 0 ? "bg-up/60" : "bg-down/60"} ${!config.enabled && "opacity-30"}`}
      />

      <div className="flex items-start justify-between gap-3 p-4 pb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 shrink-0 rounded-full ${config.enabled ? "bg-up pulse-live" : "bg-dim"}`}
              title={config.enabled ? "actif" : "en pause"}
            />
            <h3 className="truncate font-semibold text-white">{config.name}</h3>
            {isBankrupt && (
              <span className="shrink-0 rounded-full bg-down/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-down">
                Compte épuisé
              </span>
            )}
          </div>
          <p className="mt-1 text-[12px] leading-snug text-muted">{config.description}</p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button
            onClick={reset}
            title="Réinitialiser le solde"
            className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-borderLight hover:text-white"
          >
            <ResetIcon className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={toggleEnabled}
            title={config.enabled ? "Mettre en pause" : "Reprendre"}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-borderLight hover:text-white"
          >
            {config.enabled ? <StopIcon className="h-3.5 w-3.5" /> : <PlayIcon className="h-3.5 w-3.5" />}
          </button>
          <button
            onClick={onEdit}
            title="Réglages"
            className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-borderLight hover:text-white"
          >
            <GearIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="flex items-end justify-between px-4">
        <div>
          <div className={`tabular font-mono text-2xl font-bold leading-tight ${totalPnl >= 0 ? "text-up" : "text-down"}`}>
            {totalPnl >= 0 ? "+" : ""}
            {totalPnl.toFixed(4)} <span className="text-sm font-medium text-dim">SOL</span>
          </div>
          <div className={`tabular font-mono text-xs font-medium ${totalPnl >= 0 ? "text-up" : "text-down"}`}>
            {fmtPct(pnlPct)}
          </div>
        </div>
        <div className="text-right text-[11px] leading-tight text-muted">
          <div className="tabular">équité {snapshot.equitySol.toFixed(3)} SOL</div>
          <div className="tabular">réalisé {snapshot.realizedPnlSol >= 0 ? "+" : ""}{snapshot.realizedPnlSol.toFixed(3)}</div>
        </div>
      </div>

      <div className="mx-4 mt-3 flex overflow-hidden rounded-lg border border-border/80">
        <div className="flex-1 border-r border-border/80 px-3 py-2">
          <div className="text-[10px] font-medium uppercase tracking-wide text-dim">SOL déployé</div>
          <div className="tabular font-mono text-[13px] font-semibold text-white">
            {snapshot.solDeployed.toFixed(3)}{" "}
            <span className="font-sans text-[10px] font-normal text-dim">
              / {config.startingBalanceSol} · {(deployedPct * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        <div className="flex-1 px-3 py-2">
          <div className="text-[10px] font-medium uppercase tracking-wide text-dim">Frais payés</div>
          <div className="tabular font-mono text-[13px] font-semibold text-warn">
            {snapshot.totalFeesSol.toFixed(4)}
          </div>
        </div>
      </div>

      <EquityChart data={equity} startingBalance={config.startingBalanceSol} />

      <div className="border-t border-border">
        {openPositions.length === 0 ? (
          <div className="p-3 text-center text-xs text-dim">Aucune position ouverte</div>
        ) : (
          <table className="w-full text-xs">
            <tbody>
              {openPositions.map((pos) => {
                const price = prices[pos.mint];
                const changePct = price != null ? (price - pos.avgEntryPriceSol) / pos.avgEntryPriceSol : null;
                return (
                  <tr key={pos.mint} className="border-b border-border/50 last:border-0 hover:bg-panel2/50">
                    <td className="px-4 py-1.5 font-mono text-muted">{shortAddr(pos.mint)}</td>
                    <td className="px-2 py-1.5 font-mono tabular text-dim">{fmtPrice(pos.avgEntryPriceSol)}</td>
                    <td
                      className={`px-2 py-1.5 text-right font-mono tabular font-medium ${
                        changePct != null && changePct >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {changePct != null ? fmtPct(changePct) : "…"}
                    </td>
                    <td className="px-4 py-1.5 text-right text-dim">{timeAgo(pos.openedAt)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
