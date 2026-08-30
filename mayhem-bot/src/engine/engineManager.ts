import { EventEmitter } from "node:events";
import { MayhemMonitor } from "../solana/mayhemMonitor.js";
import { getCurrentQuote } from "../solana/priceFeed.js";
import { BondingCurveWatcher, type BondingCurveUpdate } from "../solana/bondingCurveWatcher.js";
import { StrategyRunner } from "./strategyRunner.js";
import { defaultStrategies } from "./presets.js";
import {
  clearPortfolioState,
  insertMayhemEvent,
  insertSnapshot,
  insertTrade,
  loadMigratedMints,
  loadPortfolioState,
  markMintMigrated,
  pruneOldData,
  savePortfolioState,
  upsertStrategyConfig,
} from "../db/db.js";
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
// Rolling retention for raw events/snapshots — see pruneOldData for why this is capped.
const DATA_RETENTION_MS = 2 * 60 * 60 * 1000;
const PRUNE_INTERVAL_MS = 10 * 60 * 1000;

// waitForMigration strategies (see presets.ts) watch a mint's bonding curve after Mayhem
// buys into it, waiting for the migration flag instead of entering right away. Most
// pump.fun launches never reach the ~85 SOL migration threshold at all, so a candidate
// that hasn't migrated within PENDING_MIGRATION_TTL_MS is given up on and unwatched —
// otherwise, at Mayhem's buy rate, the pending set (and its account-change subscriptions)
// would grow without bound.
// Sized from measured candidate supply: at the 35 SOL depth floor, ~3.5 distinct mints a
// minute qualify. A 10-minute TTL against 40 slots therefore ran right at capacity, and any
// mint that took longer than 10 minutes to migrate was dropped before it could — which is
// most of them, since a launch can sit near the threshold for a while. 25 minutes of watch
// time needs ~90 concurrent slots at that arrival rate, so 120 leaves headroom without being
// unbounded. Watch for WS subscription errors if this is raised much further.
const PENDING_MIGRATION_TTL_MS = 25 * 60 * 1000;
const MAX_PENDING_MIGRATION_WATCHES = 120;
// How long to keep trying to get a real post-migration market price for a mint whose curve
// just completed. DexScreener needs a few seconds to index a fresh pool; past this we give
// up on the entry rather than enter on a price we can't trust.
const MIGRATION_PRICE_TTL_MS = 90 * 1000;

// Only mints already within reach of the migration threshold are worth a watch slot. Of the
// ~51k observed Mayhem buys, the median pool holds 11 SOL and p90 is 64 SOL, while the mints
// that actually migrated were last seen between 23 and 75 SOL. Watching from 35 SOL up keeps
// essentially all realistic migrators while discarding ~85% of candidates, so a slot lasts
// long enough to still be watching when migration happens. Before this, slots were handed
// out first-come to a stream of ~5-10 distinct mints/second and evicted within seconds,
// which sampled an arbitrary sliver and produced roughly one post-migration entry per
// 10-15 minutes — far too few to judge the strategy on.
const MIN_MIGRATION_CANDIDATE_RESERVES_SOL = 35;

interface PendingMigration {
  entryEventId: string;
  mayhemBuySolAmount: number;
  firstSeenAt: number;
  solReservesUi: number;
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
  private awaitingMigrationPrice = new Map<string, PendingMigration>();
  private migratedMints = new Set<string>(loadMigratedMints());
  private runners = new Map<string, StrategyRunner>();
  private priceCache = new Map<string, number>();
  private reservesCache = new Map<string, PoolReserves>();
  private tickTimer: NodeJS.Timeout | null = null;
  private snapshotTimer: NodeJS.Timeout | null = null;
  private pruneTimer: NodeJS.Timeout | null = null;
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
      const runner = new StrategyRunner(cfg);
      // Resume the live portfolio across restarts. This environment recycles the container
      // whenever the session goes idle, and portfolios live in memory, so without this every
      // restart silently rewound each strategy to its starting bankroll — making a
      // multi-hour track record impossible to build no matter how long the bot ran.
      const saved = loadPortfolioState(cfg.id);
      if (saved) {
        runner.portfolio.restore(saved);
        console.log(
          `[engine] ${cfg.id} repris: solde=${runner.portfolio.solBalance.toFixed(4)} SOL, ` +
            `realise=${runner.portfolio.realizedPnlSol.toFixed(4)} SOL, ${runner.portfolio.positions.size} position(s)`,
        );
      }
      this.runners.set(cfg.id, runner);
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
    // Drop the persisted state too, or the next restart would resurrect the very portfolio
    // this reset was meant to wipe.
    clearPortfolioState(id);
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
    pruneOldData(DATA_RETENTION_MS);
    this.pruneTimer = setInterval(() => pruneOldData(DATA_RETENTION_MS), PRUNE_INTERVAL_MS);
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
    this.awaitingMigrationPrice.clear();
    if (this.tickTimer) clearInterval(this.tickTimer);
    if (this.snapshotTimer) clearInterval(this.snapshotTimer);
    if (this.pruneTimer) clearInterval(this.pruneTimer);
    this.tickTimer = null;
    this.snapshotTimer = null;
    this.pruneTimer = null;
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
   * account-change subscriptions indefinitely. Slots are rationed by how close a pool
   * actually is to migrating (see MIN_MIGRATION_CANDIDATE_RESERVES_SOL): candidates below
   * the floor are ignored outright, and at capacity the shallowest pool being watched is
   * dropped for a deeper newcomer, so watches concentrate on the mints most likely to
   * migrate while we're still looking. */
  private trackMigrationCandidate(event: MayhemEvent) {
    if (this.pendingMigration.has(event.mint)) return;
    if (this.migratedMints.has(event.mint)) return;
    if ([...this.runners.values()].some((r) => r.portfolio.positions.has(event.mint))) return;

    const reserves = event.solReservesUi;
    if (reserves == null || reserves < MIN_MIGRATION_CANDIDATE_RESERVES_SOL) return;

    if (this.pendingMigration.size >= MAX_PENDING_MIGRATION_WATCHES) {
      let shallowestMint: string | null = null;
      let shallowest = Infinity;
      for (const [mint, p] of this.pendingMigration) {
        if (p.solReservesUi < shallowest) {
          shallowest = p.solReservesUi;
          shallowestMint = mint;
        }
      }
      // Everything already queued is a better bet than this one — leave the queue alone.
      if (shallowestMint == null || shallowest >= reserves) return;
      this.pendingMigration.delete(shallowestMint);
    }

    this.pendingMigration.set(event.mint, {
      entryEventId: event.id,
      mayhemBuySolAmount: event.solAmount,
      firstSeenAt: Date.now(),
      solReservesUi: reserves,
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

    // A migrated mint's bonding curve keeps emitting pump.fun trade events, but it no longer
    // sets the price — the real market is the new AMM pool. Writing those curve numbers back
    // into the caches is what undid the migration cleanup in handleBondingCurveUpdate and let
    // sells simulate against a dead pool: it booked one exit 22x above any price ever seen
    // on-chain, and labelled another "stop_loss" on a +176% move (the exit threshold was
    // checked against the cached price while the fill price came from those stale reserves).
    // For these mints only priceTick's DexScreener quote is trustworthy.
    if (!this.migratedMints.has(event.mint)) {
      this.priceCache.set(event.mint, event.priceSol);
      if (event.solReservesUi != null && event.tokenReservesUi != null) {
        this.reservesCache.set(event.mint, {
          solReservesUi: event.solReservesUi,
          tokenReservesUi: event.tokenReservesUi,
        });
      }
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
    // A completed curve describes a pool that no longer trades: its SOL side has been
    // drained into the new AMM pool, so both its reserves AND the price derived from them
    // are garbage — often a near-zero price from an all-but-empty SOL side. Feeding that
    // into priceCache poisons every downstream consumer (it manufactured a fake ~180x
    // "win" by booking an entry at a draining-curve price and marking it against the real
    // DexScreener price). Drop both cache entries and let priceTick repopulate the price
    // from the real post-migration market instead.
    if (u.complete) {
      if (!this.migratedMints.has(u.mint)) {
        this.migratedMints.add(u.mint);
        markMintMigrated(u.mint);
      }
      this.priceCache.delete(u.mint);
      this.reservesCache.delete(u.mint);
    } else {
      this.priceCache.set(u.mint, u.priceSol);
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
      // Don't enter here: the only price available at this instant is the dead curve's.
      // Hand off to priceTick, which resolves a real market price before entering.
      this.pendingMigration.delete(u.mint);
      this.awaitingMigrationPrice.set(u.mint, { ...pending, firstSeenAt: Date.now() });
    }
    this.syncWatchedMints();
  }

  /** Second half of a waitForMigration entry: once a candidate's curve has completed, we
   * need a price from the mint's NEW market (DexScreener) before we can enter — the curve
   * price at completion is meaningless. Retried each priceTick until a sane price shows up
   * or the mint is given up on, since DexScreener typically takes a few seconds to index a
   * freshly migrated pool. */
  private async resolveMigrationEntries() {
    if (this.awaitingMigrationPrice.size === 0) return;
    const now = Date.now();

    for (const [mint, pending] of [...this.awaitingMigrationPrice]) {
      if (now - pending.firstSeenAt > MIGRATION_PRICE_TTL_MS) {
        this.awaitingMigrationPrice.delete(mint);
        continue;
      }

      const quote = await getCurrentQuote(mint);
      // A migrated mint has no bonding-curve reserves any more; a quote that still carries
      // them is the dead curve being read again, not the new pool — keep waiting.
      if (!quote || !(quote.priceSol > 0) || quote.solReservesUi != null) continue;

      this.awaitingMigrationPrice.delete(mint);
      this.priceCache.set(mint, quote.priceSol);
      for (const runner of this.runners.values()) {
        const t = runner.enterAfterMigration(mint, quote.priceSol, pending.entryEventId, pending.mayhemBuySolAmount);
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
    await this.resolveMigrationEntries();

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
      // Persisted on the same cadence as snapshots so an unannounced container recycle
      // loses at most SNAPSHOT_MS of progress instead of the whole run.
      savePortfolioState(runner.config.id, runner.portfolio.serialize());
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
