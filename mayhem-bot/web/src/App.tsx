import { useEffect, useState } from "react";
import { api } from "./lib/api";
import { useSocket } from "./lib/useSocket";
import type { MayhemEvent, StrategyConfig, StrategyView, Trade } from "./lib/types";
import { Header } from "./components/Header";
import { StatsBar } from "./components/StatsBar";
import { StrategyCard } from "./components/StrategyCard";
import { StrategyEditor } from "./components/StrategyEditor";
import { MayhemFeed } from "./components/MayhemFeed";
import { TradeFeed } from "./components/TradeFeed";

export default function App() {
  const socket = useSocket();
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [events, setEvents] = useState<MayhemEvent[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<StrategyConfig | null>(null);
  const [botRunning, setBotRunning] = useState<boolean | null>(null);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    api.strategies().then(setStrategies).catch(() => {});
    api.events(150).then(setEvents).catch(() => {});
    api.botStatus().then((s) => setBotRunning(s.running)).catch(() => {});
  }, []);

  useEffect(() => {
    if (socket.snapshot) {
      setStrategies(socket.snapshot.strategies);
      setPrices(socket.snapshot.prices);
    }
  }, [socket.snapshot]);

  useEffect(() => {
    if (socket.botRunning !== null) setBotRunning(socket.botRunning);
  }, [socket.botRunning]);

  useEffect(() => {
    if (socket.events.length > 0) setEvents((prev) => [...socket.events, ...prev].slice(0, 200));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socket.events.length]);

  useEffect(() => {
    if (socket.trades.length > 0) setTrades((prev) => [...socket.trades, ...prev].slice(0, 200));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socket.trades.length]);

  async function toggleBot() {
    setToggling(true);
    try {
      const res = botRunning ? await api.stopBot() : await api.startBot();
      setBotRunning(res.running);
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-bg bg-radial-fade text-white">
      <Header
        connected={socket.connected}
        lastMessageAt={socket.lastMessageAt}
        monitorStatus={socket.monitorStatus}
        botRunning={botRunning}
        onToggleBot={toggleBot}
        toggling={toggling}
      />

      <StatsBar strategies={strategies} />

      <main className="grid flex-1 grid-cols-[1fr_380px] gap-4 overflow-hidden p-4">
        <div className="grid auto-rows-min grid-cols-2 gap-4 overflow-y-auto pr-1">
          {strategies.map((view) => (
            <StrategyCard
              key={view.config.id}
              view={view}
              prices={prices}
              onEdit={() => setEditing(view.config)}
            />
          ))}
        </div>

        <div className="grid grid-rows-2 gap-4 overflow-hidden">
          <MayhemFeed events={events} />
          <TradeFeed trades={trades} strategies={strategies.map((s) => s.config)} />
        </div>
      </main>

      {editing && <StrategyEditor config={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
