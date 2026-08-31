/**
 * Replay feed.
 *
 * Plays captured account updates back through the exact same pipeline the live
 * bot runs, at a configurable speed, with sending structurally impossible. That
 * makes §34 real rather than aspirational: a threshold change, a different
 * sizing grid or a new screener weighting can be scored against recorded
 * history instead of against an opinion.
 *
 * The capture format is one JSON object per line, written by `--observe`:
 *   { "address": "...", "data": "<base64>", "owner": "...", "lamports": "0",
 *     "slot": 123, "receivedAt": 1690000000000 }
 */
import { createReadStream, existsSync } from "node:fs";
import { createInterface } from "node:readline";
import {
  BaseMarketDataFeed,
  type AccountUpdate,
  type FeedStats,
} from "../MarketDataFeed.js";

export interface CapturedUpdate {
  address: string;
  data: string;
  owner: string;
  lamports: string;
  slot: number;
  receivedAt: number;
}

export interface ReplayFeedConfig {
  path: string;
  /**
   * 0 replays as fast as the consumer allows; 1 replays in real time; 10 is ten
   * times faster than real time.
   */
  speed: number;
  /** Stop after this many updates. 0 means no limit. */
  limit: number;
}

export class ReplayFeed extends BaseMarketDataFeed {
  private slot = 0;
  private running = false;
  private readonly subscribed = new Set<string>();
  private counters = { updatesReceived: 0, unknownUpdates: 0, lastUpdateAt: 0 };
  private finished: Promise<void> | null = null;

  constructor(private readonly config: ReplayFeedConfig) {
    super();
    if (!existsSync(config.path)) {
      throw new Error(`replay capture not found: ${config.path}`);
    }
  }

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;
    this.emitStatus({ kind: "connected", at: Date.now() });
    this.finished = this.play();
  }

  /** Resolves when the whole capture has been replayed. */
  waitForCompletion(): Promise<void> {
    return this.finished ?? Promise.resolve();
  }

  async stop(): Promise<void> {
    this.running = false;
    this.emitStatus({ kind: "disconnected", reason: "replay stopped", at: Date.now() });
  }

  async subscribe(addresses: readonly string[]): Promise<void> {
    for (const a of addresses) this.subscribed.add(a);
  }

  async unsubscribe(addresses: readonly string[]): Promise<void> {
    for (const a of addresses) this.subscribed.delete(a);
  }

  subscriptions(): string[] {
    return [...this.subscribed];
  }

  currentSlot(): number {
    return this.slot;
  }

  stats(): FeedStats {
    return {
      subscribed: this.subscribed.size,
      updatesReceived: this.counters.updatesReceived,
      reconnects: 0,
      unknownUpdates: this.counters.unknownUpdates,
      lastUpdateAt: this.counters.lastUpdateAt,
      lastSlot: this.slot,
      connected: this.running,
    };
  }

  private async play(): Promise<void> {
    const stream = createReadStream(this.config.path, { encoding: "utf8" });
    const lines = createInterface({ input: stream, crlfDelay: Infinity });
    let previousReceivedAt: number | null = null;
    let count = 0;

    for await (const line of lines) {
      if (!this.running) break;
      const trimmed = line.trim();
      if (trimmed.length === 0) continue;

      let record: CapturedUpdate;
      try {
        record = JSON.parse(trimmed) as CapturedUpdate;
      } catch {
        continue; // a truncated final line is normal
      }

      if (this.config.speed > 0 && previousReceivedAt !== null) {
        const gap = (record.receivedAt - previousReceivedAt) / this.config.speed;
        if (gap > 0) await sleep(Math.min(gap, 5_000));
      }
      previousReceivedAt = record.receivedAt;

      if (record.slot > this.slot) {
        this.slot = record.slot;
        this.emitSlot(this.slot);
      }

      const update: AccountUpdate = {
        address: record.address,
        data: Buffer.from(record.data, "base64"),
        owner: record.owner,
        lamports: BigInt(record.lamports || "0"),
        slot: record.slot,
        // Rewrite the wall clock to now so freshness checks behave as they did
        // live; the ORIGINAL gaps between updates are preserved by the sleep
        // above, which is what actually matters.
        receivedAt: Date.now(),
      };
      this.counters.updatesReceived++;
      this.counters.lastUpdateAt = update.receivedAt;
      this.emitAccount(update);

      count++;
      if (this.config.limit > 0 && count >= this.config.limit) break;
    }

    lines.close();
    stream.close();
    this.running = false;
    this.emitStatus({ kind: "disconnected", reason: "replay complete", at: Date.now() });
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
