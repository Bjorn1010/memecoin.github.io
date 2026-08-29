import { useEffect, useRef, useState } from "react";
import type { BotStatus, MayhemEvent, MonitorStatus, SnapshotPush, Trade } from "./types";

interface SocketState {
  connected: boolean;
  lastMessageAt: number | null;
  events: MayhemEvent[];
  trades: Trade[];
  snapshot: SnapshotPush | null;
  monitorStatus: Record<string, MonitorStatus>;
  botRunning: boolean | null;
}

const MAX_FEED = 200;

export function useSocket() {
  const [state, setState] = useState<SocketState>({
    connected: false,
    lastMessageAt: null,
    events: [],
    trades: [],
    snapshot: null,
    monitorStatus: {},
    botRunning: null,
  });
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retryDelay = 1000;

    function connect() {
      if (cancelled) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        retryDelay = 1000;
        setState((s) => ({ ...s, connected: true }));
      };

      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (!cancelled) {
          setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 1.5, 10_000);
        }
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (raw) => {
        const msg = JSON.parse(raw.data as string) as { type: string; payload: unknown; ts: number };
        setState((s) => {
          const next = { ...s, lastMessageAt: msg.ts };
          if (msg.type === "mayhem_event") {
            next.events = [msg.payload as MayhemEvent, ...s.events].slice(0, MAX_FEED);
          } else if (msg.type === "trade") {
            next.trades = [msg.payload as Trade, ...s.trades].slice(0, MAX_FEED);
          } else if (msg.type === "snapshot") {
            next.snapshot = msg.payload as SnapshotPush;
          } else if (msg.type === "monitor_status") {
            const status = msg.payload as MonitorStatus;
            next.monitorStatus = { ...s.monitorStatus, [status.wallet]: status };
          } else if (msg.type === "bot_status") {
            next.botRunning = (msg.payload as BotStatus).running;
          }
          return next;
        });
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return state;
}
