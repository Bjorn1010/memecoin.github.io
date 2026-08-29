import { EventEmitter } from "node:events";
import { MayhemMonitor } from "../solana/mayhemMonitor.js";
import { getCurrentQuote } from "../solana/priceFeed.js";
import { StrategyRunner } from "./strategyRunner.js";
import { defaultStrategies } from "./presets.js";
import { insertMayhemEvent, insertSnapshot, insertTrade, loadStrategyConfigs, upsertStrategyConfig } from "../db/db.js";
import type { PoolReserves } from "./portfolio.js";
import type { MayhemEvent, StrategyConfig, Trade } from "../types.js";

const PRICE_TICK_MS = 2_500;
const SNAPSHOT_MS = 5_000;

export declare interface EngineManager {
  on(event: "mayhem_event", listener: (e: MayhemEvent) => void): this;
  on(event: "trade", listener: (t: Trade) => void): this;
  on(event: "snapshot", listener: () => void): this;
  on(event: "monitor_status", listener: (s: { wallet: string; state: string; detail?: string }) => void): this;
  on(event: "bot_status", listener: (s: { running: boolean }) => void): this;
}

export class EngineManager extends EventEmitter {
  private monitor: MayhemMonitor;
  private runners = new Map<string, StrategyRunner>();
  private priceCache = new Map<string, number>();
  private reservesCache = new Map<string, PoolReserves>();
  private tickTimer: NodeJS.Timeout | null = null;
  private snapshotTimer: NodeJS.Timeout | null = null;
  private walletStatuses = new Map<string, { wallet: string; state: string; detail?: string }>();
  private running = false;

  constructor(private wallets: string[]) {
    super();
    this.monitor = new MayhemMonitor(wallets);
    this.monitor.on("event", (event) => this.handleMayhemEvent(event));
    this.monitor.on("status", (s) => {
      this.walletStatuses.set(s.wallet, s);
      this.emit("monitor_status", s);
    });

    const persisted = loadStrategyConfigs();
    const configs = persisted.length > 0 ? persisted : defaultStrategies;
    for (const cfg of configs) {
      this.runners.set(cfg.id, new StrategyRunner(cfg));
      upsertStrategyConfig(cfg);
    }
  }

  listStrategies(): StrategyConfig[] {
    return [...this.runners.values()].map((r) => r.config);
  }

  getRunner(id: string): StrategyRunner | undefined {
    return this.runners.get(id);
  }

  updateStrategy(cfg: StrategyConfig) {
    const existing = this.runners.get(cfg.id);
    if (existing) {
      existing.config = cfg;
    } else {
      this.runners.set(cfg.id, new StrategyRunner(cfg));
    }
    upsertStrategyConfig(cfg);
  }

  /** Wipes a strategy's paper portfolio back to its starting balance — for when it's gone
   * bankrupt (or you just want a clean run) without restarting the whole bot. History in
   * the DB stays put, the equity curve just shows the reset as a jump back to baseline. */
  resetStrategy(id: string): boolean {
    const existing = this.runners.get(id);
    if (!existing) return false;
    const fresh = new StrategyRunner(existing.config);
    this.runners.set(id, fresh);
    insertSnapshot(fresh.portfolio.snapshot(this.priceCache));
    this.emit("snapshot");
    return true;
  }

  isRunning(): boolean {
    return this.running;
  }

  /** Starts (or resumes) live monitoring + the price/snapshot loops. Safe to call repeatedly. */
  async start() {
    if (this.running) return;
    this.running = true;
    this.walletStatuses.clear();
    await this.monitor.start();

    this.tickTimer = setInterval(() => void this.priceTick(), PRICE_TICK_MS);
    this.snapshotTimer = setInterval(() => this.snapshotAll(), SNAPSHOT_MS);
    this.emit("bot_status", { running: true });
  }

  /** Stops monitoring and freezes every strategy's state exactly where it is. Resumable via start(). */
  stop() {
    if (!this.running) return;
    this.running = false;
    this.monitor.stop();
    if (this.tickTimer) clearInterval(this.tickTimer);
    if (this.snapshotTimer) clearInterval(this.snapshotTimer);
    this.tickTimer = null;
    this.snapshotTimer = null;
    this.emit("bot_status", { running: false });
  }

  private handleMayhemEvent(event: MayhemEvent) {
    insertMayhemEvent(event);
    this.emit("mayhem_event", event);
    this.priceCache.set(event.mint, event.priceSol);
    if (event.solReservesUi != null && event.tokenReservesUi != null) {
      this.reservesCache.set(event.mint, {
        solReservesUi: event.solReservesUi,
        tokenReservesUi: event.tokenReservesUi,
      });
    }

    for (const runner of this.runners.values()) {
      const trades = runner.onMayhemEvent(event);
      for (const t of trades) {
        insertTrade(t);
        this.emit("trade", t);
      }
    }
  }

  private async priceTick() {
    const mints = new Set<string>();
    for (const runner of this.runners.values()) {
      for (const mint of runner.portfolio.positions.keys()) mints.add(mint);
    }
    if (mints.size === 0) return;

    const entries = await Promise.all(
      [...mints].map(async (mint) => {
        const quote = await getCurrentQuote(mint);
        return [mint, quote] as const;
      }),
    );

    for (const [mint, quote] of entries) {
      if (!quote) continue;
      this.priceCache.set(mint, quote.priceSol);
      if (quote.solReservesUi != null && quote.tokenReservesUi != null) {
        this.reservesCache.set(mint, { solReservesUi: quote.solReservesUi, tokenReservesUi: quote.tokenReservesUi });
      }
    }

    for (const runner of this.runners.values()) {
      const trades = runner.tick(this.priceCache, this.reservesCache);
      for (const t of trades) {
        insertTrade(t);
        this.emit("trade", t);
      }
    }
  }

  private snapshotAll() {
    for (const runner of this.runners.values()) {
      const snap = runner.portfolio.snapshot(this.priceCache);
      insertSnapshot(snap);
    }
    this.emit("snapshot");
  }

  currentPrices(): Record<string, number> {
    return Object.fromEntries(this.priceCache);
  }

  currentWalletStatuses() {
    return [...this.walletStatuses.values()];
  }
}
