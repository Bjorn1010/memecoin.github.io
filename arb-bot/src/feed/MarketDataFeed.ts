/**
 * The market data interface.
 *
 * This is one of the two seams that make the phase 1 -> phase 2 migration a
 * substitution rather than a rewrite (§4). Phase 1 fills it with WebSocket
 * `accountSubscribe`; phase 2 can fill it with Geyser/gRPC, and nothing above
 * this line changes. `ReplayFeed` fills it from captured state so the entire
 * decision path runs offline.
 */
import { EventEmitter } from "node:events";

export interface AccountUpdate {
  address: string;
  data: Buffer;
  owner: string;
  lamports: bigint;
  /** Slot the update is valid at, from the subscription's context. */
  slot: number;
  /** Local wall clock when the update reached us. */
  receivedAt: number;
}

export type FeedStatus =
  | { kind: "connecting"; attempt: number }
  | { kind: "connected"; at: number }
  | { kind: "disconnected"; reason: string; at: number }
  | { kind: "resubscribed"; count: number; at: number }
  | { kind: "subscription-failed"; address: string; reason: string }
  | { kind: "stalled"; sinceMs: number };

export interface FeedStats {
  subscribed: number;
  updatesReceived: number;
  reconnects: number;
  /** Updates dropped because we were not subscribed to that account. */
  unknownUpdates: number;
  lastUpdateAt: number;
  lastSlot: number;
  connected: boolean;
}

export interface MarketDataFeedEvents {
  account: (update: AccountUpdate) => void;
  slot: (slot: number) => void;
  status: (status: FeedStatus) => void;
  error: (error: Error) => void;
}

export interface MarketDataFeed {
  start(): Promise<void>;
  stop(): Promise<void>;

  /** Subscribe to accounts. Idempotent per address. */
  subscribe(addresses: readonly string[]): Promise<void>;
  unsubscribe(addresses: readonly string[]): Promise<void>;

  /** Addresses currently subscribed. */
  subscriptions(): string[];
  /** Best known current slot. */
  currentSlot(): number;
  stats(): FeedStats;

  on<E extends keyof MarketDataFeedEvents>(event: E, listener: MarketDataFeedEvents[E]): this;
  off<E extends keyof MarketDataFeedEvents>(event: E, listener: MarketDataFeedEvents[E]): this;
}

/** Shared emitter plumbing so implementations only write transport code. */
export abstract class BaseMarketDataFeed extends EventEmitter implements MarketDataFeed {
  abstract start(): Promise<void>;
  abstract stop(): Promise<void>;
  abstract subscribe(addresses: readonly string[]): Promise<void>;
  abstract unsubscribe(addresses: readonly string[]): Promise<void>;
  abstract subscriptions(): string[];
  abstract currentSlot(): number;
  abstract stats(): FeedStats;

  override on<E extends keyof MarketDataFeedEvents>(
    event: E,
    listener: MarketDataFeedEvents[E],
  ): this {
    return super.on(event, listener as (...args: unknown[]) => void);
  }

  override off<E extends keyof MarketDataFeedEvents>(
    event: E,
    listener: MarketDataFeedEvents[E],
  ): this {
    return super.off(event, listener as (...args: unknown[]) => void);
  }

  protected emitAccount(update: AccountUpdate): void {
    this.emit("account", update);
  }
  protected emitSlot(slot: number): void {
    this.emit("slot", slot);
  }
  protected emitStatus(status: FeedStatus): void {
    this.emit("status", status);
  }
  protected emitError(error: Error): void {
    // An unhandled 'error' event throws in Node; only emit when someone cares.
    if (this.listenerCount("error") > 0) this.emit("error", error);
  }
}
