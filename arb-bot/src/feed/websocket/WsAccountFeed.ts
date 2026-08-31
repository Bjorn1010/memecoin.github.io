/**
 * Phase 1 market data: raw `accountSubscribe` over a WebSocket.
 *
 * Written against the JSON-RPC subscription protocol directly rather than
 * through a client library, for three reasons that all cost money if they go
 * wrong:
 *  - subscriptions are a hard, small budget on a free tier, so the bot has to
 *    know exactly how many it holds and which ones (§19);
 *  - a silent reconnect that loses subscriptions is indistinguishable from a
 *    quiet market, and would have the bot quoting stale state forever. Here a
 *    reconnect explicitly resubscribes everything and says so;
 *  - a socket that stops delivering without closing is a real failure mode, so
 *    staleness is detected on a timer and forces a reconnect.
 */
import WebSocket from "ws";
import {
  BaseMarketDataFeed,
  type AccountUpdate,
  type FeedStats,
} from "../MarketDataFeed.js";

export interface WsAccountFeedConfig {
  endpoint: string;
  commitment: "processed" | "confirmed" | "finalized";
  /** Reconnect backoff, doubling to the cap. */
  reconnectInitialMs: number;
  reconnectMaxMs: number;
  /** Force a reconnect if nothing at all arrives for this long. */
  stallTimeoutMs: number;
  /** Ping interval to keep intermediaries from dropping an idle socket. */
  pingIntervalMs: number;
  /** Hard cap on subscriptions, matching the provider's limit. */
  maxSubscriptions: number;
}

export const DEFAULT_WS_CONFIG: Omit<WsAccountFeedConfig, "endpoint"> = {
  commitment: "confirmed",
  reconnectInitialMs: 500,
  reconnectMaxMs: 30_000,
  stallTimeoutMs: 60_000,
  pingIntervalMs: 20_000,
  maxSubscriptions: 90,
};

export class SubscriptionLimitError extends Error {
  constructor(requested: number, limit: number) {
    super(`subscription limit reached: ${requested} requested, limit is ${limit}`);
    this.name = "SubscriptionLimitError";
  }
}

interface PendingRequest {
  resolve: (value: unknown) => void;
  reject: (e: Error) => void;
  timer: NodeJS.Timeout;
}

export class WsAccountFeed extends BaseMarketDataFeed {
  private ws: WebSocket | null = null;
  private nextRequestId = 1;
  private readonly pending = new Map<number, PendingRequest>();
  /** address -> server subscription id (absent while (re)subscribing). */
  private readonly subIdByAddress = new Map<string, number>();
  private readonly addressBySubId = new Map<number, string>();
  /** Everything we want to be subscribed to, whether or not we currently are. */
  private readonly desired = new Set<string>();

  private slot = 0;
  private slotSubId: number | null = null;
  private running = false;
  private reconnectDelay: number;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pingTimer: NodeJS.Timeout | null = null;
  private stallTimer: NodeJS.Timeout | null = null;

  private counters = {
    updatesReceived: 0,
    reconnects: 0,
    unknownUpdates: 0,
    lastUpdateAt: 0,
  };

  constructor(private readonly config: WsAccountFeedConfig) {
    super();
    this.reconnectDelay = config.reconnectInitialMs;
  }

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;
    await this.connect(1);
  }

  async stop(): Promise<void> {
    this.running = false;
    this.clearTimers();
    for (const [, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new Error("feed stopped"));
    }
    this.pending.clear();
    const ws = this.ws;
    this.ws = null;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      await new Promise<void>((resolve) => {
        ws.once("close", () => resolve());
        ws.close();
        // Do not hang shutdown on a socket that refuses to close.
        setTimeout(() => resolve(), 2_000).unref?.();
      });
    }
  }

  async subscribe(addresses: readonly string[]): Promise<void> {
    const fresh = addresses.filter((a) => !this.desired.has(a));
    if (fresh.length === 0) return;
    if (this.desired.size + fresh.length > this.config.maxSubscriptions) {
      throw new SubscriptionLimitError(this.desired.size + fresh.length, this.config.maxSubscriptions);
    }
    for (const a of fresh) this.desired.add(a);
    if (this.isOpen()) await this.subscribeNow(fresh);
  }

  async unsubscribe(addresses: readonly string[]): Promise<void> {
    for (const address of addresses) {
      this.desired.delete(address);
      const subId = this.subIdByAddress.get(address);
      if (subId === undefined) continue;
      this.subIdByAddress.delete(address);
      this.addressBySubId.delete(subId);
      if (this.isOpen()) {
        try {
          await this.request("accountUnsubscribe", [subId]);
        } catch (e) {
          // Losing an unsubscribe is not fatal: the socket will be replaced on
          // the next reconnect and the subscription with it.
          this.emitError(asError(e));
        }
      }
    }
  }

  subscriptions(): string[] {
    return [...this.desired];
  }

  currentSlot(): number {
    return this.slot;
  }

  stats(): FeedStats {
    return {
      subscribed: this.subIdByAddress.size,
      updatesReceived: this.counters.updatesReceived,
      reconnects: this.counters.reconnects,
      unknownUpdates: this.counters.unknownUpdates,
      lastUpdateAt: this.counters.lastUpdateAt,
      lastSlot: this.slot,
      connected: this.isOpen(),
    };
  }

  // --- connection -----------------------------------------------------------

  private isOpen(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private async connect(attempt: number): Promise<void> {
    if (!this.running) return;
    this.emitStatus({ kind: "connecting", attempt });

    const ws = new WebSocket(this.config.endpoint);
    this.ws = ws;

    ws.on("open", () => {
      this.reconnectDelay = this.config.reconnectInitialMs;
      this.emitStatus({ kind: "connected", at: Date.now() });
      this.startTimers();
      void this.onOpen();
    });

    ws.on("message", (raw: WebSocket.RawData) => this.onMessage(raw));

    ws.on("close", (code, reason) => {
      this.handleDisconnect(`closed (${code} ${reason.toString().slice(0, 80)})`);
    });

    ws.on("error", (e) => {
      this.emitError(asError(e));
      // 'close' follows 'error'; let it drive the reconnect so we do not
      // schedule two reconnects for one failure.
    });
  }

  private async onOpen(): Promise<void> {
    // Slot first: freshness checks are meaningless without a current slot.
    try {
      const id = await this.request("slotSubscribe", []);
      this.slotSubId = typeof id === "number" ? id : null;
    } catch (e) {
      this.emitError(asError(e));
    }

    this.subIdByAddress.clear();
    this.addressBySubId.clear();
    const all = [...this.desired];
    if (all.length > 0) {
      await this.subscribeNow(all);
      this.emitStatus({ kind: "resubscribed", count: this.subIdByAddress.size, at: Date.now() });
    }
  }

  private async subscribeNow(addresses: readonly string[]): Promise<void> {
    // Sequential rather than parallel: a burst of a hundred subscribe calls is
    // exactly what a free endpoint rate limits.
    for (const address of addresses) {
      if (!this.desired.has(address) || !this.isOpen()) continue;
      try {
        const id = await this.request("accountSubscribe", [
          address,
          { encoding: "base64", commitment: this.config.commitment },
        ]);
        if (typeof id === "number") {
          this.subIdByAddress.set(address, id);
          this.addressBySubId.set(id, address);
        } else {
          this.emitStatus({
            kind: "subscription-failed",
            address,
            reason: `unexpected subscription id ${String(id)}`,
          });
        }
      } catch (e) {
        this.emitStatus({ kind: "subscription-failed", address, reason: asError(e).message });
      }
    }
  }

  private handleDisconnect(reason: string): void {
    this.clearTimers();
    this.subIdByAddress.clear();
    this.addressBySubId.clear();
    this.slotSubId = null;
    this.ws = null;
    for (const [, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new Error(`socket ${reason}`));
    }
    this.pending.clear();

    this.emitStatus({ kind: "disconnected", reason, at: Date.now() });
    if (!this.running) return;

    this.counters.reconnects++;
    const delay = this.reconnectDelay;
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.config.reconnectMaxMs);
    this.reconnectTimer = setTimeout(() => {
      void this.connect(this.counters.reconnects + 1);
    }, delay);
    this.reconnectTimer.unref?.();
  }

  private startTimers(): void {
    this.clearTimers();
    this.pingTimer = setInterval(() => {
      if (this.isOpen()) this.ws?.ping();
    }, this.config.pingIntervalMs);
    this.pingTimer.unref?.();

    this.stallTimer = setInterval(() => {
      const since = Date.now() - (this.counters.lastUpdateAt || Date.now());
      if (since > this.config.stallTimeoutMs) {
        this.emitStatus({ kind: "stalled", sinceMs: since });
        // A socket that is open but silent is worse than a closed one: it looks
        // healthy while every quote it feeds is stale.
        this.ws?.terminate();
      }
    }, Math.max(1_000, Math.floor(this.config.stallTimeoutMs / 2)));
    this.stallTimer.unref?.();
  }

  private clearTimers(): void {
    for (const t of [this.reconnectTimer, this.pingTimer, this.stallTimer]) {
      if (t) clearTimeout(t as NodeJS.Timeout);
    }
    if (this.pingTimer) clearInterval(this.pingTimer);
    if (this.stallTimer) clearInterval(this.stallTimer);
    this.reconnectTimer = null;
    this.pingTimer = null;
    this.stallTimer = null;
  }

  // --- protocol -------------------------------------------------------------

  private request(method: string, params: unknown[]): Promise<unknown> {
    return new Promise((resolve, reject) => {
      if (!this.isOpen()) {
        reject(new Error(`cannot send ${method}: socket is not open`));
        return;
      }
      const id = this.nextRequestId++;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out`));
      }, 15_000);
      timer.unref?.();
      this.pending.set(id, { resolve, reject, timer });
      this.ws!.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    });
  }

  private onMessage(raw: WebSocket.RawData): void {
    this.counters.lastUpdateAt = Date.now();
    let msg: JsonRpcMessage;
    try {
      msg = JSON.parse(raw.toString()) as JsonRpcMessage;
    } catch (e) {
      this.emitError(asError(e));
      return;
    }

    if (typeof msg.id === "number") {
      const p = this.pending.get(msg.id);
      if (!p) return;
      clearTimeout(p.timer);
      this.pending.delete(msg.id);
      if (msg.error) p.reject(new Error(`${msg.error.code}: ${msg.error.message}`));
      else p.resolve(msg.result);
      return;
    }

    if (msg.method === "slotNotification") {
      const slot = msg.params?.result?.slot;
      if (typeof slot === "number" && slot > this.slot) {
        this.slot = slot;
        this.emitSlot(slot);
      }
      return;
    }

    if (msg.method === "accountNotification") {
      const subId = msg.params?.subscription;
      const value = msg.params?.result?.value;
      const contextSlot = msg.params?.result?.context?.slot;
      if (typeof subId !== "number" || !value) return;
      const address = this.addressBySubId.get(subId);
      if (!address) {
        this.counters.unknownUpdates++;
        return;
      }
      const encoded = Array.isArray(value.data) ? value.data[0] : null;
      if (typeof encoded !== "string") return;

      const slot = typeof contextSlot === "number" ? contextSlot : this.slot;
      // An account notification carries a slot too; keep our clock honest even
      // if the slot subscription is lagging or absent.
      if (slot > this.slot) this.slot = slot;

      const update: AccountUpdate = {
        address,
        data: Buffer.from(encoded, "base64"),
        owner: typeof value.owner === "string" ? value.owner : "",
        lamports: typeof value.lamports === "number" ? BigInt(value.lamports) : 0n,
        slot,
        receivedAt: Date.now(),
      };
      this.counters.updatesReceived++;
      this.emitAccount(update);
    }
  }
}

interface JsonRpcMessage {
  id?: number;
  method?: string;
  result?: unknown;
  error?: { code: number; message: string };
  params?: {
    subscription?: number;
    result?: {
      slot?: number;
      context?: { slot?: number };
      value?: { data?: unknown; owner?: unknown; lamports?: unknown };
    };
  };
}

function asError(e: unknown): Error {
  return e instanceof Error ? e : new Error(String(e));
}
