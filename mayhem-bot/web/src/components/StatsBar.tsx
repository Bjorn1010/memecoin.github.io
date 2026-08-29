import type { StrategyView } from "../lib/types";
import { StatTile } from "./StatTile";
import { CoinsStackIcon, ReceiptIcon, WalletIcon } from "./icons";

export function StatsBar({ strategies }: { strategies: StrategyView[] }) {
  let equity = 0;
  let pnl = 0;
  let deployed = 0;
  let fees = 0;
  let startingTotal = 0;

  for (const s of strategies) {
    equity += s.snapshot.equitySol;
    pnl += s.snapshot.realizedPnlSol + s.snapshot.unrealizedPnlSol;
    deployed += s.snapshot.solDeployed;
    fees += s.snapshot.totalFeesSol;
    startingTotal += s.config.startingBalanceSol;
  }

  const pnlPct = startingTotal > 0 ? pnl / startingTotal : 0;

  return (
    <div className="flex flex-wrap gap-3 border-b border-border bg-bg px-6 py-3">
      <StatTile label="Équité totale" value={`${equity.toFixed(3)} SOL`} icon={<WalletIcon className="h-5 w-5" />} />
      <StatTile
        label="PNL total"
        value={`${pnl >= 0 ? "+" : ""}${pnl.toFixed(3)} SOL`}
        sub={`${pnlPct >= 0 ? "+" : ""}${(pnlPct * 100).toFixed(1)}%`}
        tone={pnl >= 0 ? "up" : "down"}
      />
      <StatTile
        label="SOL déployé"
        value={`${deployed.toFixed(3)} SOL`}
        sub="en position actuellement"
        icon={<CoinsStackIcon className="h-5 w-5" />}
      />
      <StatTile
        label="Frais payés"
        value={`${fees.toFixed(4)} SOL`}
        sub="frais Padre 1% + priorité"
        icon={<ReceiptIcon className="h-5 w-5" />}
      />
    </div>
  );
}
