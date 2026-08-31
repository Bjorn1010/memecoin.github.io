/**
 * Watchlist selection.
 *
 * WebSocket subscriptions are a hard, small budget on a free RPC (§19), and
 * every pool costs three of them (pool state plus two vaults). This module
 * decides which pools hold those slots, with hysteresis so the watchlist does
 * not thrash on noise, and it records why every entry and exit happened.
 *
 * The bot applies the returned changes live: nothing here requires a restart.
 */
import { rankPools, type PoolScore } from "./scorer.js";

export interface WatchlistEntry {
  poolId: string;
  score: number;
  reason: string;
  enteredAt: number;
  /** Set when the pool leaves; kept for the audit log. */
  exitedAt?: number;
  exitReason?: string;
}

export interface SelectorConfig {
  /** How many pools may be watched at once. */
  maxWatched: number;
  /**
   * A challenger must beat the weakest incumbent by this margin to take its
   * slot. Without it the watchlist churns on measurement noise and every swap
   * costs a resubscribe plus a cold-start period with no data.
   */
  entryMarginScore: number;
  /** A pool below this score is dropped even if there is nothing to replace it. */
  minScoreToStay: number;
  /** Grace period during which a freshly added pool cannot be evicted. */
  minResidencyMs: number;
}

export const DEFAULT_SELECTOR_CONFIG: SelectorConfig = {
  maxWatched: 20,
  entryMarginScore: 0.25,
  minScoreToStay: 0.1,
  minResidencyMs: 10 * 60_000,
};

export interface SelectionChange {
  poolId: string;
  action: "enter" | "exit";
  reason: string;
  score: number;
  at: number;
}

export interface SelectionResult {
  watchlist: WatchlistEntry[];
  changes: SelectionChange[];
}

export class WatchlistSelector {
  private entries = new Map<string, WatchlistEntry>();
  private readonly history: WatchlistEntry[] = [];

  constructor(private readonly config: SelectorConfig = DEFAULT_SELECTOR_CONFIG) {}

  current(): WatchlistEntry[] {
    return [...this.entries.values()];
  }

  /** Every entry and exit ever made, for the report. */
  auditLog(): readonly WatchlistEntry[] {
    return this.history;
  }

  /**
   * Reconcile the watchlist against fresh scores.
   *
   * Order of operations matters: drop the unfit first (freeing slots), then
   * fill empty slots with the best challengers, then only swap when a
   * challenger clears the hysteresis margin.
   */
  update(scores: readonly PoolScore[], now: number): SelectionResult {
    const changes: SelectionChange[] = [];
    const byId = new Map(scores.map((s) => [s.poolId, s]));
    const { maxWatched, entryMarginScore, minScoreToStay, minResidencyMs } = this.config;

    // 1. Refresh incumbents' scores and drop those that fell below the floor.
    for (const entry of [...this.entries.values()]) {
      const s = byId.get(entry.poolId);
      if (s) entry.score = s.score;
      const residency = now - entry.enteredAt;
      if (residency < minResidencyMs) continue;

      if (!s) {
        this.exit(entry, "no longer scored (pool disappeared from the universe)", now, changes);
      } else if (s.score < minScoreToStay) {
        this.exit(entry, `score ${s.score.toFixed(3)} below floor ${minScoreToStay}`, now, changes);
      }
    }

    // 2. Fill free slots with the best challengers.
    const ranked = rankPools(scores).filter((s) => !this.entries.has(s.poolId));
    let challengerIndex = 0;
    while (this.entries.size < maxWatched && challengerIndex < ranked.length) {
      const c = ranked[challengerIndex++]!;
      if (c.score < minScoreToStay) break;
      this.enter(c, `free slot; ${c.explanation}`, now, changes);
    }

    // 3. Swap only on a clear margin, and never evict a pool still in its
    //    grace period — we would be throwing away data we just paid to collect.
    while (challengerIndex < ranked.length) {
      const challenger = ranked[challengerIndex]!;
      const evictable = [...this.entries.values()]
        .filter((e) => now - e.enteredAt >= minResidencyMs)
        .sort((a, b) => a.score - b.score);
      const weakest = evictable[0];
      if (!weakest) break;
      if (challenger.score <= weakest.score + entryMarginScore) break;

      this.exit(
        weakest,
        `displaced by ${challenger.poolId} (${challenger.score.toFixed(3)} > ${weakest.score.toFixed(3)} + ${entryMarginScore})`,
        now,
        changes,
      );
      this.enter(challenger, `displaced ${weakest.poolId}; ${challenger.explanation}`, now, changes);
      challengerIndex++;
    }

    return { watchlist: this.current(), changes };
  }

  /** Force a pool out, e.g. because the risk filter rejected its token. */
  evict(poolId: string, reason: string, now: number): SelectionChange | null {
    const entry = this.entries.get(poolId);
    if (!entry) return null;
    const changes: SelectionChange[] = [];
    this.exit(entry, reason, now, changes);
    return changes[0] ?? null;
  }

  private enter(score: PoolScore, reason: string, now: number, changes: SelectionChange[]): void {
    const entry: WatchlistEntry = {
      poolId: score.poolId,
      score: score.score,
      reason,
      enteredAt: now,
    };
    this.entries.set(score.poolId, entry);
    this.history.push(entry);
    changes.push({ poolId: score.poolId, action: "enter", reason, score: score.score, at: now });
  }

  private exit(
    entry: WatchlistEntry,
    reason: string,
    now: number,
    changes: SelectionChange[],
  ): void {
    entry.exitedAt = now;
    entry.exitReason = reason;
    this.entries.delete(entry.poolId);
    changes.push({ poolId: entry.poolId, action: "exit", reason, score: entry.score, at: now });
  }
}
