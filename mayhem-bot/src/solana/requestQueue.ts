interface QueueItem<T> {
  task: () => Promise<T>;
  resolve: (v: T) => void;
  reject: (e: unknown) => void;
  enqueuedAt: number;
}

/**
 * True single-flight rate limiter: at most one RPC call in the air at any time, with at
 * least `minGapMs` between the END of one call and the START of the next. This matters
 * because web3.js retries 429s internally with its own backoff (up to several seconds) —
 * a limiter that only paces *start* times (not completions) lets retrying calls pile up
 * concurrently, which trips the RPC's rate limit even harder and snowballs. Serializing on
 * completion is what actually keeps requests-in-flight capped at 1.
 *
 * `maxAgeMs` additionally drops anything that's been waiting too long: a Mayhem buy signal
 * that's 20+ seconds stale by the time we'd fetch it is worthless for a low-latency copy
 * bot — better to skip it and stay current than to keep working through a growing backlog.
 */
export class RequestQueue {
  private queue: QueueItem<unknown>[] = [];
  private pumping = false;

  constructor(
    private minGapMs: number,
    private maxAgeMs = 20_000,
  ) {}

  run<T>(task: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push({ task, resolve, reject, enqueuedAt: Date.now() } as QueueItem<unknown>);
      void this.pump();
    });
  }

  get pending(): number {
    return this.queue.length;
  }

  private async pump() {
    if (this.pumping) return;
    this.pumping = true;

    while (this.queue.length > 0) {
      const item = this.queue.shift()!;

      if (Date.now() - item.enqueuedAt > this.maxAgeMs) {
        item.reject(new Error("stale: dropped from RPC queue"));
        continue;
      }

      try {
        const result = await item.task();
        item.resolve(result);
      } catch (err) {
        item.reject(err);
      }

      if (this.queue.length > 0) {
        await new Promise((r) => setTimeout(r, this.minGapMs));
      }
    }

    this.pumping = false;
  }
}
