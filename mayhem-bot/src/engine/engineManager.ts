import { EventEmitter } from "node:events";
import { MayhemMonitor } from "../solana/mayhemMonitor.js";
import { getCurrentQuote } from "../solana/priceFeed.js";
import { BondingCurveWatcher, type BondingCurveUpdate } from "../solana/bondingCurveWatcher.js";
import { StrategyRunner } from "./strategyRunner.js";
import { defaultStrategies } from "./presets.js";
import { insertMayhemEvent, insertSnapshot, insertTrade, upsertStrategyConfig } from "../db/db.js";
import type { PoolReserves } from "./portfolio.js";
import type { MayhemEvent, StrategyConfig, Trade } from "../types.js";

// Now a slow safety net, not the primary exit-latency path: real-time price updates come
// from bondingCurveWatcher's onAccountChange push (see there for why the fixed-interval
// version alone let stop-loss/trailing-stop fills blow through their nominal threshold).
// This loop still matters for maxHoldSeconds (a time-based exit, not price-driven — a quiet
// mint sees no account-change events at all) and for migrated tokens (DexScreener fallback,
// no bonding-curve account to subscribe to).
const PRICE_TICK_MS = 2_500;
const SNAPSHOT_MS = 5_000;

// waitForMigration strategies (see presets.ts) watch a mint's bonding curve after Mayhem
// buys into it, waiting for the migration flag instead of entering right away. Most
// pump.fun launches never reach the ~85 SOL migration threshold at all, so a candidate
// that hasn't migrated within PENDING_MIGRATION_TTL_MS is given up on and unwatched —
// otherwise, at Mayhem's buy rate, the pending set (and its account-change subscriptions)
// would grow without bound.
const PENDING_MIGRATION_TTL_MS = 10 * 60 * 1000;
const MAX_PENDING_MIGRATION_WATCHES = 40;

interface PendingMigration {
  entryEventId: string;
  mayhemBuySolAmount: number;
  firstSeenAt: number;
}

export declare interface EngineManager {
  on(event: "mayhem_event", listener: (e: MayhemEvent) => void): this;
  on(event: "trade", listener: (t: Trade) => void): this;
  on(event: "snapshot", listener: () => void): this;
  on(event: "monitor_status", listener: (s: { wallet: string; state: string; detail?: string }) => void): this;
  on(event: "bot_status", listener: (s: { running: boolean }) => void): this;
}

export class EngineManager extends EventEmitter {
  private monitor: MayhemMonitor;
  private watcher = new BondingCurveWatcher();
  private watchedMints = new Set<string>();
  private pendingMigration = new Map<string, PendingMigration>();
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
    this.watcher.on("update", (u) => this.handleBondingCurveUpdate(u));

    // presets.ts is the source of truth: nothing exposes an API to edit a strategy's config
    // at runtime, so a persisted row is never anything but a stale copy of a past boot's
    // defaults. Always load fresh from presets.ts and overwrite the persisted mirror,
    // so an edit to presets.ts actually takes effect on the next restart.
    for (const cfg of defaultStrategies) {
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
    this.syncWatchedMints();
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
    this.watcher.stopAll();
    this.watchedMints.clear();
    this.pendingMigration.clear();
    if (this.tickTimer) clearInterval(this.tickTimer);
    if (this.snapshotTimer) clearInterval(this.snapshotTimer);
    this.tickTimer = null;
    this.snapshotTimer = null;
    this.emit("bot_status", { running: false });
  }

  /** Keeps the live account-change subscriptions in sync with what's actually open across
   * every strategy, plus whatever waitForMigration is still waiting to see migrate — one
   * subscription per mint no matter how many strategies/watchers care about it, torn down
   * the moment nothing does anymore. Called after anything that can open or close a
   * position or add/remove a pending migration candidate. */
  private syncWatchedMints() {
    const wantedMints = new Set<string>(this.pendingMigration.keys());
    for (const runner of this.runners.values()) {
      for (const mint of runner.portfolio.positions.keys()) wantedMints.add(mint);
    }
    for (const mint of wantedMints) {
      if (!this.watchedMints.has(mint)) {
        this.watcher.watch(mint);
        this.watchedMints.add(mint);
      }
    }
    for (const mint of this.watchedMints) {
      if (!wantedMints.has(mint)) {
        this.watcher.unwatch(mint);
        this.watchedMints.delete(mint);
      }
    }
  }

  /** Registers a mint Mayhem just bought as a migration candidate for waitForMigration
   * strategies, bounded by MAX_PENDING_MIGRATION_WATCHES since most pump.fun launches
   * never migrate and Mayhem buys often enough that an unbounded watchlist would pile up
   * account-change subscriptions indefinitely. At capacity, evicts the oldest candidate
   * instead of just refusing new ones — Mayhem buys at roughly 5-10/s, so a first-come,
   * never-rotated batch of watches would camp on whichever mints happened to fill the
   * list first instead of sampling the wider stream of buys over the run. */
  private trackMigrationCandidate(event: MayhemEvent) {
    if (this.pendingMigration.has(event.mint)) return;
    if ([...this.runners.values()].some((r) => r.portfolio.positions.has(event.mint))) return;
    if (this.pendingMigration.size >= MAX_PENDING_MIGRATION_WATCHES) {
      const oldestMint = this.pendingMigration.keys().next().value;
      if (oldestMint) this.pendingMigration.delete(oldestMint);
    }
    this.pendingMigration.set(event.mint, {
      entryEventId: event.id,
      mayhemBuySolAmount: event.solAmount,
      firstSeenAt: Date.now(),
    });
    this.syncWatchedMints();
  }

  /** Drops any migration candidate that's been waiting longer than PENDING_MIGRATION_TTL_MS
   * without migrating — most never do. */
  private sweepPendingMigrations() {
    if (this.pendingMigration.size === 0) return;
    const now = Date.now();
    let changed = false;
    for (const [mint, pending] of this.pendingMigration) {
      if (now - pending.firstSeenAt > PENDING_MIGRATION_TTL_MS) {
        this.pendingMigration.delete(mint);
        changed = true;
      }
    }
    if (changed) this.syncWatchedMints();
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

    if (event.kind === "buy" && [...this.runners.values()].some((r) => r.config.waitForMigration)) {
      this.trackMigrationCandidate(event);
    }
    this.syncWatchedMints();
  }

  /** Fires the instant a watched mint's bonding-curve account changes on-chain — this is
   * the low-latency path that actually catches a stop-loss/trailing-stop/take-profit
   * crossing close to when it happens, instead of waiting for the next priceTick(). Also
   * where a waitForMigration strategy actually enters, the moment its watched candidate's
   * curve reports complete. */
  private handleBondingCurveUpdate(u: BondingCurveUpdate) {
    this.priceCache.set(u.mint, u.priceSol);
    // Once complete, the bonding-curve reserves are a snapshot of a pool that no longer
    // trades — the mint's real liquidity is now on a separate AMM pool we have no reserves
    // for. Drop any cached reserves rather than let a stale/transitional curve-completion
    // reading get fed into simulateSell() as if it still described the live market (this
    // produced a nonsensical -40% "slippage" on the first post-migration exit).
    if (u.complete) {
      this.reservesCache.delete(u.mint);
    } else {
      this.reservesCache.set(u.mint, { solReservesUi: u.solReservesUi, tokenReservesUi: u.tokenReservesUi });
    }

    for (const runner of this.runners.values()) {
      const trades = runner.tick(this.priceCache, this.reservesCache);
      for (const t of trades) {
        insertTrade(t);
        this.emit("trade", t);
      }
    }

    const pending = this.pendingMigration.get(u.mint);
    if (u.complete && pending) {
      this.pendingMigration.delete(u.mint);
      for (const runner of this.runners.values()) {
        const t = runner.enterAfterMigration(u.mint, u.priceSol, pending.entryEventId, pending.mayhemBuySolAmount);
        if (t) {
          insertTrade(t);
          this.emit("trade", t);
        }
      }
    }
    this.syncWatchedMints();
  }

  /** Slow fallback sweep — see the PRICE_TICK_MS comment above for why this still runs
   * alongside the event-driven watcher instead of being replaced by it. Also where
   * abandoned migration candidates get swept out, independent of whether anything has an
   * open position right now. */
  private async priceTick() {
    this.sweepPendingMigrations();

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
    this.syncWatchedMints();
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
