/**
 * Transaction sending.
 *
 * The second phase-1/phase-2 seam (§4). Two implementations ship:
 *
 *  - `RpcSender`: `sendTransaction` through the configured endpoint. A
 *    transaction that lands and reverts still pays its base and priority fees.
 *
 *  - `JitoSender`: submits the cycle as a single-transaction bundle to a Jito
 *    block engine. Per Jito's documentation a bundle whose transactions do not
 *    all succeed is rejected and never included, so a failed attempt costs
 *    nothing. That property is exposed as `revertCostsFees` and feeds straight
 *    into the expected-value calculation, where it matters enormously at a low
 *    land rate.
 *
 * VERIFIED against docs.jito.wtf on 2026-08-31 (see ASSUMPTIONS.md #JITO-1..4):
 *   base URL   https://<region>.mainnet.block-engine.jito.wtf
 *              (global: https://mainnet.block-engine.jito.wtf)
 *   bundles    POST /api/v1/bundles          method sendBundle
 *   tips       POST /api/v1/getTipAccounts   method getTipAccounts
 *   status     POST /api/v1/getBundleStatuses / getInflightBundleStatuses
 *   auth       none required for default sends
 *   rate limit 1 request per second per IP per region
 *   min tip    1000 lamports
 *
 * The endpoint is NOT defaulted anywhere in this file. It must be configured
 * explicitly, and the tip accounts are fetched from the block engine itself
 * rather than hardcoded, so a change on their side surfaces as a startup error
 * instead of as lamports sent to a stale address.
 */
import { PublicKey, VersionedTransaction } from "@solana/web3.js";
import type { RpcClient } from "../rpc/RpcClient.js";
import { RpcPriority } from "../rpc/RpcBudget.js";

export type SendOutcomeKind = "success" | "reverted" | "notIncluded";

export interface SendResult {
  /** Transaction signature, or the bundle id for a bundle send. */
  id: string;
  signature: string;
  sentAt: number;
}

export interface ConfirmResult {
  outcome: SendOutcomeKind;
  slot: number | null;
  error: string | null;
}

export interface TxSender {
  readonly kind: "rpc" | "jito";
  /**
   * Whether a failed attempt still costs base + priority fees. Drives the
   * expected-value model; see costs/fees.ts.
   */
  readonly revertCostsFees: boolean;
  /** Minimum useful tip for this transport, in lamports. */
  readonly minTipLamports: bigint;

  /** One-time setup: fetch tip accounts, validate the endpoint. */
  prepare(): Promise<void>;
  /** A tip destination, or null when this transport does not take tips. */
  tipAccount(): PublicKey | null;

  send(transaction: VersionedTransaction): Promise<SendResult>;
  confirm(result: SendResult, lastValidBlockHeight: number): Promise<ConfirmResult>;
}

// --- plain RPC --------------------------------------------------------------

export class RpcSender implements TxSender {
  readonly kind = "rpc" as const;
  readonly revertCostsFees = true;
  readonly minTipLamports = 0n;

  constructor(
    private readonly rpc: RpcClient,
    private readonly pollIntervalMs = 400,
  ) {}

  async prepare(): Promise<void> {
    // Nothing to set up; the RPC client is already validated by its first call.
  }

  tipAccount(): PublicKey | null {
    return null;
  }

  async send(transaction: VersionedTransaction): Promise<SendResult> {
    const raw = transaction.serialize();
    const signature = await this.rpc.call(RpcPriority.P0_Critical, (c) =>
      c.sendRawTransaction(raw, {
        // We simulated immediately before this; preflight would only add
        // latency and a second chance to be rate limited.
        skipPreflight: true,
        // Retries are ours to control, not the library's.
        maxRetries: 0,
      }),
    );
    return { id: signature, signature, sentAt: Date.now() };
  }

  async confirm(result: SendResult, lastValidBlockHeight: number): Promise<ConfirmResult> {
    for (;;) {
      const statuses = await this.rpc.call(RpcPriority.P0_Critical, (c) =>
        c.getSignatureStatuses([result.signature], { searchTransactionHistory: false }),
      );
      const status = statuses.value[0];
      if (status) {
        if (status.err) {
          return {
            outcome: "reverted",
            slot: status.slot ?? null,
            error: JSON.stringify(status.err),
          };
        }
        if (status.confirmationStatus === "confirmed" || status.confirmationStatus === "finalized") {
          return { outcome: "success", slot: status.slot ?? null, error: null };
        }
      }

      const height = await this.rpc.call(RpcPriority.P0_Critical, (c) => c.getBlockHeight());
      if (height > lastValidBlockHeight) {
        // The blockhash expired without the transaction being included: it will
        // never land, and it cost nothing.
        return { outcome: "notIncluded", slot: null, error: "blockhash expired" };
      }
      await sleep(this.pollIntervalMs);
    }
  }
}

// --- Jito bundles -----------------------------------------------------------

export interface JitoSenderConfig {
  /** Full block engine base URL. No default: it must be configured. */
  blockEngineUrl: string;
  /** Jito documents a floor of 1000 lamports. */
  minTipLamports?: bigint;
  requestTimeoutMs?: number;
  /** Jito's documented default is 1 request per second per IP per region. */
  minRequestIntervalMs?: number;
}

export class JitoSender implements TxSender {
  readonly kind = "jito" as const;
  /**
   * A bundle whose transactions do not all succeed is rejected and never
   * included, so a failed attempt is free. This is the single most valuable
   * property of this transport for a bot with a low land rate.
   */
  readonly revertCostsFees = false;
  readonly minTipLamports: bigint;

  private tipAccounts: PublicKey[] = [];
  private nextTipIndex = 0;
  private lastRequestAt = 0;
  private readonly minRequestIntervalMs: number;
  private readonly timeoutMs: number;

  constructor(private readonly config: JitoSenderConfig) {
    if (!config.blockEngineUrl) {
      throw new Error("JitoSender requires an explicit block engine URL");
    }
    this.minTipLamports = config.minTipLamports ?? 1_000n;
    this.minRequestIntervalMs = config.minRequestIntervalMs ?? 1_100;
    this.timeoutMs = config.requestTimeoutMs ?? 10_000;
  }

  async prepare(): Promise<void> {
    const result = await this.rpcCall<string[]>("/api/v1/getTipAccounts", "getTipAccounts", []);
    if (!Array.isArray(result) || result.length === 0) {
      throw new Error("Jito getTipAccounts returned no accounts; refusing to send blind");
    }
    this.tipAccounts = result.map((a) => new PublicKey(a));
  }

  tipAccount(): PublicKey | null {
    if (this.tipAccounts.length === 0) return null;
    // Rotate: Jito's own guidance is to spread tips across the accounts.
    const account = this.tipAccounts[this.nextTipIndex % this.tipAccounts.length]!;
    this.nextTipIndex++;
    return account;
  }

  async send(transaction: VersionedTransaction): Promise<SendResult> {
    const encoded = Buffer.from(transaction.serialize()).toString("base64");
    const bundleId = await this.rpcCall<string>("/api/v1/bundles", "sendBundle", [
      [encoded],
      { encoding: "base64" },
    ]);
    const signature = signatureOf(transaction);
    return { id: bundleId, signature, sentAt: Date.now() };
  }

  async confirm(result: SendResult, _lastValidBlockHeight: number): Promise<ConfirmResult> {
    const deadline = Date.now() + 60_000;
    for (;;) {
      const statuses = await this.rpcCall<{ value?: { bundle_id: string; status: string }[] }>(
        "/api/v1/getInflightBundleStatuses",
        "getInflightBundleStatuses",
        [[result.id]],
      );
      const entry = statuses?.value?.[0];
      const status = entry?.status ?? "Pending";

      if (status === "Landed") {
        const landed = await this.rpcCall<{
          value?: { bundle_id: string; slot: number; err?: unknown }[];
        }>("/api/v1/getBundleStatuses", "getBundleStatuses", [[result.id]]);
        const detail = landed?.value?.[0];
        if (detail?.err && !isNullError(detail.err)) {
          return { outcome: "reverted", slot: detail.slot ?? null, error: JSON.stringify(detail.err) };
        }
        return { outcome: "success", slot: detail?.slot ?? null, error: null };
      }
      if (status === "Failed" || status === "Invalid") {
        // Not included: the bundle was dropped, and nothing was charged.
        return { outcome: "notIncluded", slot: null, error: `bundle ${status.toLowerCase()}` };
      }
      if (Date.now() > deadline) {
        return { outcome: "notIncluded", slot: null, error: "bundle status still pending at deadline" };
      }
      await sleep(1_000);
    }
  }

  private async rpcCall<T>(path: string, method: string, params: unknown[]): Promise<T> {
    await this.respectRateLimit();
    const url = `${this.config.blockEngineUrl.replace(/\/$/, "")}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`Jito ${method} returned HTTP ${response.status}`);
      }
      const body = (await response.json()) as { result?: T; error?: { message?: string } };
      if (body.error) throw new Error(`Jito ${method} error: ${body.error.message ?? "unknown"}`);
      return body.result as T;
    } finally {
      clearTimeout(timer);
    }
  }

  /** Jito documents one request per second per IP per region. */
  private async respectRateLimit(): Promise<void> {
    const wait = this.lastRequestAt + this.minRequestIntervalMs - Date.now();
    if (wait > 0) await sleep(wait);
    this.lastRequestAt = Date.now();
  }
}

function isNullError(err: unknown): boolean {
  if (err === null || err === undefined) return true;
  if (typeof err === "object" && err !== null && "Ok" in err) {
    return (err as { Ok: unknown }).Ok === null;
  }
  return false;
}

function signatureOf(transaction: VersionedTransaction): string {
  const sig = transaction.signatures[0];
  if (!sig) return "";
  return bs58(sig);
}

function bs58(bytes: Uint8Array): string {
  const ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let zeros = 0;
  while (zeros < bytes.length && bytes[zeros] === 0) zeros++;
  const digits: number[] = [];
  for (let i = zeros; i < bytes.length; i++) {
    let carry = bytes[i]!;
    for (let j = 0; j < digits.length; j++) {
      carry += digits[j]! << 8;
      digits[j] = carry % 58;
      carry = (carry / 58) | 0;
    }
    while (carry > 0) {
      digits.push(carry % 58);
      carry = (carry / 58) | 0;
    }
  }
  let out = "1".repeat(zeros);
  for (let i = digits.length - 1; i >= 0; i--) out += ALPHABET[digits[i]!];
  return out;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
