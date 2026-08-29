import { shortAddr } from "../lib/format";
import type { MonitorStatus } from "../lib/types";
import { BoltIcon, PlayIcon, StopIcon } from "./icons";

export function Header({
  connected,
  lastMessageAt,
  monitorStatus,
  botRunning,
  onToggleBot,
  toggling,
}: {
  connected: boolean;
  lastMessageAt: number | null;
  monitorStatus: Record<string, MonitorStatus>;
  botRunning: boolean | null;
  onToggleBot: () => void;
  toggling: boolean;
}) {
  const latencyMs = lastMessageAt ? Date.now() - lastMessageAt : null;
  const wallets = Object.values(monitorStatus);
  const isRunning = botRunning === true;

  return (
    <header className="flex items-center justify-between border-b border-border bg-panel/80 px-6 py-3 backdrop-blur">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accentDim text-accent shadow-glow">
            <BoltIcon className="h-4.5 w-4.5" />
          </div>
          <div>
            <h1 className="text-[15px] font-bold leading-none tracking-tight">Mayhem Bot</h1>
            <span className="text-[10px] font-medium uppercase tracking-wider text-dim">Paper trading terminal</span>
          </div>
        </div>

        <button
          onClick={onToggleBot}
          disabled={toggling || botRunning === null}
          className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-[13px] font-semibold transition-all disabled:opacity-50 ${
            isRunning
              ? "bg-up/10 text-up ring-1 ring-inset ring-up/30 hover:bg-up/15"
              : "bg-down/10 text-down ring-1 ring-inset ring-down/30 hover:bg-down/15"
          }`}
        >
          {isRunning ? <StopIcon className="h-3.5 w-3.5" /> : <PlayIcon className="h-3.5 w-3.5" />}
          {toggling ? "…" : isRunning ? "Bot actif — Stop" : "Bot arrêté — Start"}
          {isRunning && <span className="h-1.5 w-1.5 rounded-full bg-up pulse-live" />}
        </button>
      </div>

      <div className="flex items-center gap-5 text-sm">
        <div className="flex items-center gap-1.5">
          {wallets.length === 0 ? (
            <span className="text-xs text-dim">wallets…</span>
          ) : (
            wallets.map((w) => (
              <span
                key={w.wallet}
                title={w.detail}
                className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[11px] ${
                  w.state === "subscribed" ? "border-up/25 text-up" : "border-down/25 text-down"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${w.state === "subscribed" ? "bg-up" : "bg-down"}`} />
                {shortAddr(w.wallet)}
              </span>
            ))
          )}
        </div>

        <div className="flex items-center gap-1.5 text-xs">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-up" : "bg-down"}`} />
          <span className="text-muted">
            {connected ? (latencyMs != null ? `live · ${latencyMs}ms` : "live") : "déconnecté"}
          </span>
        </div>
      </div>
    </header>
  );
}
