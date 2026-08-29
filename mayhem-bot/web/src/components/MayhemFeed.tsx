import { fmtPrice, shortAddr, timeAgo } from "../lib/format";
import type { MayhemEvent } from "../lib/types";

const KIND_STYLE: Record<MayhemEvent["kind"], string> = {
  buy: "text-up border-up/30 bg-up/10",
  sell: "text-down border-down/30 bg-down/10",
  full_exit: "text-warn border-warn/30 bg-warn/10",
};

const KIND_LABEL: Record<MayhemEvent["kind"], string> = {
  buy: "BUY",
  sell: "SELL",
  full_exit: "DUMP TOTAL",
};

export function MayhemFeed({ events }: { events: MayhemEvent[] }) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-panel shadow-card">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-[13px] font-semibold">Activité on-chain</h3>
        <p className="text-[11px] text-dim">Wallets Mayhem suivis en direct</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="p-6 text-center text-xs text-dim">En attente de la première transaction…</div>
        ) : (
          events.map((e) => (
            <div key={e.id} className="flex items-center gap-2 border-b border-border/50 px-4 py-2 text-xs hover:bg-panel2/40">
              <span
                className={`w-[72px] shrink-0 rounded border px-1.5 py-0.5 text-center font-mono text-[10.5px] font-bold ${KIND_STYLE[e.kind]}`}
              >
                {KIND_LABEL[e.kind]}
              </span>
              <span className="font-mono text-muted">{shortAddr(e.mint)}</span>
              <span className="ml-auto font-mono tabular text-white">{e.tokenAmount.toFixed(1)} tok</span>
              <span className="font-mono tabular text-dim">@ {fmtPrice(e.priceSol)}</span>
              <span className="w-8 shrink-0 text-right text-dim">{timeAgo(e.detectedAtMs)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
