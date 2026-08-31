/**
 * The RPC budget.
 *
 * On a free tier the RPC is a scarce economic resource, not an infinite API.
 * Every call in the bot goes through this token bucket, and every call declares
 * a priority. When the bucket is empty the highest priority waiter is served
 * first, so a screener sweep can never starve the simulation of a live
 * opportunity (§18).
 *
 * A 429 puts the whole bucket into exponential backoff: continuing to hammer a
 * rate-limited endpoint is how a free tier becomes a banned tier.
 */

export enum RpcPriority {
  /** Safety and critical state: balances, kill-switch checks, blockhash. */
  P0_Critical = 0,
  /** Simulating an opportunity we are about to send. */
  P1_HotSimulation = 1,
  /** State needed to trade: account refreshes for watched pools. */
  P2_TradingState = 2,
  /** Screener sweeps. */
  P3_Screener = 3,
  /** Statistics, maintenance, reporting. */
  P4_Maintenance = 4,
}

export interface RpcBudgetConfig {
  /** Sustained rate, in requests per second. */
  refillPerSecond: number;
  /** Burst size. */
  capacity: number;
  /** Backoff applied on the first 429, doubling up to the cap. */
  backoffInitialMs: number;
  backoffMaxMs: number;
  /** Requests waiting longer than this are rejected rather than queued forever. */
  maxWaitMs: number;
}

export const DEFAULT_RPC_BUDGET: RpcBudgetConfig = {
  refillPerSecond: 8,
  capacity: 20,
  backoffInitialMs: 500,
  backoffMaxMs: 30_000,
  maxWaitMs: 15_000,
};

export interface RpcBudgetStats {
  granted: number;
  rejected: number;
  rateLimitHits: number;
  currentTokens: number;
  queueDepth: number;
  backoffUntil: number;
  grantedByPriority: Record<number, number>;
  rejectedByPriority: Record<number, number>;
  totalWaitMs: number;
}

export class RpcBudgetExhaustedError extends Error {
  constructor(readonly priority: RpcPriority, readonly waitedMs: number) {
    super(`RPC budget exhausted: waited ${waitedMs}ms at priority P${priority}`);
    this.name = "RpcBudgetExhaustedError";
  }
}

interface Waiter {
  priority: RpcPriority;
  cost: number;
  enqueuedAt: number;
  resolve: () => void;
  reject: (e: Error) => void;
  timer: NodeJS.Timeout;
}

export class RpcBudget {
  private tokens: number;
  private lastRefill: number;
  private backoffUntil = 0;
  private backoffMs: number;
  private readonly waiters: Waiter[] = [];
  private pumpTimer: NodeJS.Timeout | null = null;

  private stats: RpcBudgetStats = {
    granted: 0,
    rejected: 0,
    rateLimitHits: 0,
    currentTokens: 0,
    queueDepth: 0,
    backoffUntil: 0,
    grantedByPriority: {},
    rejectedByPriority: {},
    totalWaitMs: 0,
  };

  constructor(
    private readonly config: RpcBudgetConfig = DEFAULT_RPC_BUDGET,
    private readonly now: () => number = Date.now,
  ) {
    this.tokens = config.capacity;
    this.lastRefill = now();
    this.backoffMs = config.backoffInitialMs;
  }

  /**
   * Wait for permission to make `cost` requests at `priority`.
   * Throws RpcBudgetExhaustedError if the wait exceeds `maxWaitMs`.
   */
  async acquire(priority: RpcPriority, cost = 1): Promise<void> {
    this.refill();
    if (this.canServeNow(cost)) {
      this.take(cost, priority, 0);
      return;
    }

    return new Promise<void>((resolve, reject) => {
      const enqueuedAt = this.now();
      const waiter: Waiter = {
        priority,
        cost,
        enqueuedAt,
        resolve,
        reject,
        timer: setTimeout(() => {
          this.removeWaiter(waiter);
          this.stats.rejected++;
          this.stats.rejectedByPriority[priority] = (this.stats.rejectedByPriority[priority] ?? 0) + 1;
          reject(new RpcBudgetExhaustedError(priority, this.now() - enqueuedAt));
        }, this.config.maxWaitMs),
      };
      this.waiters.push(waiter);
      this.stats.queueDepth = this.waiters.length;
      this.schedulePump();
    });
  }

  /**
   * Tell the budget a request was rate limited. Applies exponential backoff to
   * every priority — a 429 is a statement about the endpoint, not about the
   * request that happened to trigger it.
   */
  noteRateLimited(): void {
    this.stats.rateLimitHits++;
    const t = this.now();
    this.backoffUntil = t + this.backoffMs;
    this.stats.backoffUntil = this.backoffUntil;
    this.backoffMs = Math.min(this.backoffMs * 2, this.config.backoffMaxMs);
    this.schedulePump();
  }

  /** Tell the budget a request succeeded, so backoff can decay. */
  noteSuccess(): void {
    if (this.backoffMs > this.config.backoffInitialMs) {
      this.backoffMs = Math.max(this.config.backoffInitialMs, Math.floor(this.backoffMs / 2));
    }
  }

  getStats(): RpcBudgetStats {
    this.refill();
    return {
      ...this.stats,
      currentTokens: Math.floor(this.tokens),
      queueDepth: this.waiters.length,
      backoffUntil: this.backoffUntil,
      grantedByPriority: { ...this.stats.grantedByPriority },
      rejectedByPriority: { ...this.stats.rejectedByPriority },
    };
  }

  /** Release every waiter with an error. Used on shutdown. */
  drain(reason: string): void {
    while (this.waiters.length > 0) {
      const w = this.waiters.pop()!;
      clearTimeout(w.timer);
      w.reject(new Error(`RPC budget draining: ${reason}`));
    }
    if (this.pumpTimer) {
      clearTimeout(this.pumpTimer);
      this.pumpTimer = null;
    }
  }

  private canServeNow(cost: number): boolean {
    return this.now() >= this.backoffUntil && this.tokens >= cost;
  }

  private take(cost: number, priority: RpcPriority, waitedMs: number): void {
    this.tokens -= cost;
    this.stats.granted++;
    this.stats.grantedByPriority[priority] = (this.stats.grantedByPriority[priority] ?? 0) + 1;
    this.stats.totalWaitMs += waitedMs;
  }

  private refill(): void {
    const t = this.now();
    const elapsed = (t - this.lastRefill) / 1000;
    if (elapsed <= 0) return;
    this.tokens = Math.min(this.config.capacity, this.tokens + elapsed * this.config.refillPerSecond);
    this.lastRefill = t;
  }

  private removeWaiter(w: Waiter): void {
    const i = this.waiters.indexOf(w);
    if (i >= 0) this.waiters.splice(i, 1);
    this.stats.queueDepth = this.waiters.length;
  }

  /**
   * Serve waiters best-priority-first, oldest-first within a priority.
   * Called on a timer rather than on every acquire so a burst of low-priority
   * work cannot spin the event loop.
   */
  private pump(): void {
    this.pumpTimer = null;
    this.refill();

    const t = this.now();
    if (t < this.backoffUntil) {
      this.schedulePump();
      return;
    }

    this.waiters.sort((a, b) =>
      a.priority !== b.priority ? a.priority - b.priority : a.enqueuedAt - b.enqueuedAt,
    );

    while (this.waiters.length > 0) {
      const next = this.waiters[0]!;
      if (this.tokens < next.cost) break;
      this.waiters.shift();
      clearTimeout(next.timer);
      this.take(next.cost, next.priority, t - next.enqueuedAt);
      next.resolve();
    }
    this.stats.queueDepth = this.waiters.length;

    if (this.waiters.length > 0) this.schedulePump();
  }

  private schedulePump(): void {
    if (this.pumpTimer || this.waiters.length === 0) return;
    const t = this.now();
    const backoffWait = Math.max(0, this.backoffUntil - t);
    // Time until at least one token is available.
    const deficit = Math.max(0, (this.waiters[0]?.cost ?? 1) - this.tokens);
    const refillWait = deficit > 0 ? (deficit / this.config.refillPerSecond) * 1000 : 0;
    const delay = Math.max(5, Math.ceil(Math.max(backoffWait, refillWait)));
    this.pumpTimer = setTimeout(() => this.pump(), delay);
    // Do not hold the process open just to refill a bucket.
    this.pumpTimer.unref?.();
  }
}

/** True when an error from an RPC call looks like a rate limit. */
export function isRateLimitError(e: unknown): boolean {
  if (!e) return false;
  const message = e instanceof Error ? e.message : String(e);
  return (
    message.includes("429") ||
    /too many requests/i.test(message) ||
    /rate limit/i.test(message)
  );
}
