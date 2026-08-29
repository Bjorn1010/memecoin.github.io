import { createServer } from "node:http";
import express from "express";
import cors from "cors";
import { WebSocketServer, WebSocket } from "ws";
import type { EngineManager } from "../engine/engineManager.js";
import { equityCurve, recentMayhemEvents, recentTrades } from "../db/db.js";
import type { StrategyConfig } from "../types.js";

function buildStrategiesPayload(engine: EngineManager) {
  const prices = new Map(Object.entries(engine.currentPrices()));
  return engine.listStrategies().map((cfg) => {
    const runner = engine.getRunner(cfg.id)!;
    return {
      config: cfg,
      snapshot: runner.portfolio.snapshot(prices),
      openPositions: [...runner.portfolio.positions.values()],
    };
  });
}

export function createApiServer(engine: EngineManager, port: number) {
  const app = express();
  app.use(cors());
  app.use(express.json());

  app.get("/api/strategies", (_req, res) => {
    res.json(buildStrategiesPayload(engine));
  });

  app.put("/api/strategies/:id", (req, res) => {
    const cfg = req.body as StrategyConfig;
    if (cfg.id !== req.params.id) {
      res.status(400).json({ error: "id mismatch" });
      return;
    }
    engine.updateStrategy(cfg);
    res.json({ ok: true });
  });

  app.post("/api/strategies/:id/reset", (req, res) => {
    const ok = engine.resetStrategy(req.params.id);
    if (!ok) {
      res.status(404).json({ error: "unknown strategy" });
      return;
    }
    res.json({ ok: true });
  });

  app.get("/api/strategies/:id/trades", (req, res) => {
    res.json(recentTrades(req.params.id, Number(req.query.limit ?? 200)));
  });

  app.get("/api/strategies/:id/equity", (req, res) => {
    res.json(equityCurve(req.params.id, Number(req.query.limit ?? 2000)));
  });

  app.get("/api/events", (req, res) => {
    res.json(recentMayhemEvents(Number(req.query.limit ?? 150)));
  });

  app.get("/api/prices", (_req, res) => {
    res.json(engine.currentPrices());
  });

  app.get("/api/bot/status", (_req, res) => {
    res.json({ running: engine.isRunning() });
  });

  app.post("/api/bot/start", async (_req, res) => {
    await engine.start();
    res.json({ running: engine.isRunning() });
  });

  app.post("/api/bot/stop", (_req, res) => {
    engine.stop();
    res.json({ running: engine.isRunning() });
  });

  const httpServer = createServer(app);
  const wss = new WebSocketServer({ server: httpServer, path: "/ws" });

  function broadcast(type: string, payload: unknown) {
    const message = JSON.stringify({ type, payload, ts: Date.now() });
    for (const client of wss.clients) {
      if (client.readyState === WebSocket.OPEN) client.send(message);
    }
  }

  wss.on("connection", (ws) => {
    ws.send(JSON.stringify({ type: "bot_status", payload: { running: engine.isRunning() }, ts: Date.now() }));
    for (const status of engine.currentWalletStatuses()) {
      ws.send(JSON.stringify({ type: "monitor_status", payload: status, ts: Date.now() }));
    }
    ws.send(
      JSON.stringify({
        type: "snapshot",
        payload: { strategies: buildStrategiesPayload(engine), prices: engine.currentPrices() },
        ts: Date.now(),
      }),
    );
  });

  engine.on("mayhem_event", (e) => broadcast("mayhem_event", e));
  engine.on("trade", (t) => broadcast("trade", t));
  engine.on("monitor_status", (s) => broadcast("monitor_status", s));
  engine.on("bot_status", (s) => broadcast("bot_status", s));
  engine.on("snapshot", () => {
    broadcast("snapshot", { strategies: buildStrategiesPayload(engine), prices: engine.currentPrices() });
  });

  httpServer.listen(port, () => {
    console.log(`[api] dashboard API + ws listening on http://localhost:${port}`);
  });

  return httpServer;
}
