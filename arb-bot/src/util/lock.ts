/**
 * Per-opportunity locking (§22).
 *
 * Two attempts on the same pair of pools must never be in flight at once: the
 * second is priced against state the first is about to invalidate, so at best
 * it burns fees and at worst both land and the second is a loss.
 *
 * Locks time out. A lock leaked by a crash between acquire and release would
 * otherwise disable that pair permanently and silently — the worst kind of
 * failure, because the bot keeps running and simply stops making money there.
 */

export interface LockHandle {
  key: string;
  acquiredAt: number;
  release(): void;
}

export interface LockStats {
  held: number;
  acquired: number;
  rejected: number;
  timedOut: number;
}

export class OpportunityLocks {
  private readonly held = new Map<string, { acquiredAt: number; timer: NodeJS.Timeout }>();
  private stats: LockStats = { held: 0, acquired: 0, rejected: 0, timedOut: 0 };

  constructor(
    private readonly timeoutMs: number,
    private readonly onTimeout?: (key: string, heldMs: number) => void,
  ) {}

  /** Canonical key for a pair of pools, direction-independent. */
  static keyFor(poolA: string, poolB: string): string {
    return poolA < poolB ? `${poolA}:${poolB}` : `${poolB}:${poolA}`;
  }

  /** Returns null when the pair is already in flight. Never blocks. */
  tryAcquire(key: string, now = Date.now()): LockHandle | null {
    if (this.held.has(key)) {
      this.stats.rejected++;
      return null;
    }
    const timer = setTimeout(() => {
      const entry = this.held.get(key);
      if (!entry) return;
      this.held.delete(key);
      this.stats.timedOut++;
      this.stats.held = this.held.size;
      this.onTimeout?.(key, Date.now() - entry.acquiredAt);
    }, this.timeoutMs);
    timer.unref?.();

    this.held.set(key, { acquiredAt: now, timer });
    this.stats.acquired++;
    this.stats.held = this.held.size;

    let released = false;
    return {
      key,
      acquiredAt: now,
      release: () => {
        // Idempotent: a release in both a success path and a finally block is
        // the normal shape and must not corrupt the counters.
        if (released) return;
        released = true;
        const entry = this.held.get(key);
        if (!entry) return;
        clearTimeout(entry.timer);
        this.held.delete(key);
        this.stats.held = this.held.size;
      },
    };
  }

  isHeld(key: string): boolean {
    return this.held.has(key);
  }

  getStats(): LockStats {
    return { ...this.stats, held: this.held.size };
  }

  /** Release everything. Used on shutdown so timers do not outlive the run. */
  releaseAll(): void {
    for (const [, entry] of this.held) clearTimeout(entry.timer);
    this.held.clear();
    this.stats.held = 0;
  }
}
