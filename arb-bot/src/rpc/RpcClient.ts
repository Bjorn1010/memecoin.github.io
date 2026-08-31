/**
 * Budgeted RPC client.
 *
 * Every request passes through `RpcBudget`, declares a priority, and reports
 * rate limiting back so the whole client backs off together. Nothing in the bot
 * is allowed to hold a raw `Connection`: an unbudgeted call is how a free tier
 * gets exhausted five minutes before the one opportunity that mattered.
 */
import {
  Connection,
  PublicKey,
  type AccountInfo,
  type Commitment,
  type GetProgramAccountsFilter,
  type Message,
  type SimulateTransactionConfig,
  type VersionedMessage,
  type VersionedTransaction,
} from "@solana/web3.js";
import { RpcBudget, RpcPriority, isRateLimitError } from "./RpcBudget.js";

export interface RpcAccount {
  address: string;
  data: Buffer;
  owner: string;
  lamports: bigint;
  slot: number;
  receivedAt: number;
}

export interface RpcClientOptions {
  commitment?: Commitment;
  /** Retries for transient (non-rate-limit) failures. */
  maxRetries?: number;
}

export class RpcClient {
  readonly connection: Connection;
  private readonly commitment: Commitment;
  private readonly maxRetries: number;
  private errorCount = 0;

  constructor(
    endpoint: string,
    readonly budget: RpcBudget,
    options: RpcClientOptions = {},
  ) {
    this.commitment = options.commitment ?? "confirmed";
    this.maxRetries = options.maxRetries ?? 2;
    this.connection = new Connection(endpoint, {
      commitment: this.commitment,
      // The bot manages its own retry and backoff through the budget; letting
      // web3.js retry underneath would make the budget a lie.
      disableRetryOnRateLimit: true,
    });
  }

  get errors(): number {
    return this.errorCount;
  }

  /** Run an arbitrary RPC call under the budget. */
  async call<T>(priority: RpcPriority, fn: (c: Connection) => Promise<T>, cost = 1): Promise<T> {
    let attempt = 0;
    for (;;) {
      await this.budget.acquire(priority, cost);
      try {
        const result = await fn(this.connection);
        this.budget.noteSuccess();
        return result;
      } catch (e) {
        this.errorCount++;
        if (isRateLimitError(e)) {
          this.budget.noteRateLimited();
          if (attempt++ < this.maxRetries) continue;
        } else if (attempt++ < this.maxRetries && isTransient(e)) {
          continue;
        }
        throw e;
      }
    }
  }

  async getSlot(priority: RpcPriority = RpcPriority.P0_Critical): Promise<number> {
    return this.call(priority, (c) => c.getSlot(this.commitment));
  }

  async getEpoch(priority: RpcPriority = RpcPriority.P4_Maintenance): Promise<bigint> {
    const info = await this.call(priority, (c) => c.getEpochInfo(this.commitment));
    return BigInt(info.epoch);
  }

  /** Most recent block time in unix seconds, for Raydium's `open_time` gate. */
  async getBlockTimeSeconds(priority: RpcPriority = RpcPriority.P2_TradingState): Promise<number> {
    const slot = await this.getSlot(priority);
    const t = await this.call(priority, (c) => c.getBlockTime(slot));
    return t ?? Math.floor(Date.now() / 1000);
  }

  async getAccount(address: string, priority: RpcPriority): Promise<RpcAccount | null> {
    const key = new PublicKey(address);
    const res = await this.call(priority, (c) =>
      c.getAccountInfoAndContext(key, this.commitment),
    );
    const receivedAt = Date.now();
    if (!res.value) return null;
    return toRpcAccount(address, res.value, res.context.slot, receivedAt);
  }

  async getAccounts(addresses: readonly string[], priority: RpcPriority): Promise<(RpcAccount | null)[]> {
    if (addresses.length === 0) return [];
    const out: (RpcAccount | null)[] = [];
    // getMultipleAccounts caps at 100 keys per request.
    for (let i = 0; i < addresses.length; i += 100) {
      const chunk = addresses.slice(i, i + 100);
      const res = await this.call(
        priority,
        (c) => c.getMultipleAccountsInfoAndContext(chunk.map((a) => new PublicKey(a)), this.commitment),
      );
      const receivedAt = Date.now();
      chunk.forEach((address, j) => {
        const info = res.value[j];
        out.push(info ? toRpcAccount(address, info, res.context.slot, receivedAt) : null);
      });
    }
    return out;
  }

  async getProgramAccounts(
    programId: string,
    filters: GetProgramAccountsFilter[],
    priority: RpcPriority,
    dataSlice?: { offset: number; length: number },
  ): Promise<RpcAccount[]> {
    const res = await this.call(
      priority,
      (c) =>
        c.getProgramAccounts(new PublicKey(programId), {
          commitment: this.commitment,
          filters,
          ...(dataSlice ? { dataSlice } : {}),
        }),
      // A program-account scan is far more expensive than a point read; charge
      // the budget accordingly so a screener sweep cannot drain it silently.
      5,
    );
    const receivedAt = Date.now();
    const slot = await this.getSlot(priority);
    return res.map((r) => toRpcAccount(r.pubkey.toBase58(), r.account, slot, receivedAt));
  }

  async getMinimumBalanceForRentExemption(bytes: number, priority: RpcPriority): Promise<bigint> {
    const v = await this.call(priority, (c) => c.getMinimumBalanceForRentExemption(bytes));
    return BigInt(v);
  }

  /** Fee for a specific message — the ground truth for the cost model. */
  async getFeeForMessage(
    message: Message | VersionedMessage,
    priority: RpcPriority,
  ): Promise<bigint | null> {
    const res = await this.call(priority, (c) => c.getFeeForMessage(message, this.commitment));
    return res.value === null ? null : BigInt(res.value);
  }

  async getLatestBlockhash(priority: RpcPriority = RpcPriority.P0_Critical): Promise<{
    blockhash: string;
    lastValidBlockHeight: number;
  }> {
    return this.call(priority, (c) => c.getLatestBlockhash(this.commitment));
  }

  async simulate(
    tx: VersionedTransaction,
    config: SimulateTransactionConfig,
    priority: RpcPriority = RpcPriority.P1_HotSimulation,
  ) {
    return this.call(priority, (c) => c.simulateTransaction(tx, config));
  }
}

function toRpcAccount(
  address: string,
  info: AccountInfo<Buffer>,
  slot: number,
  receivedAt: number,
): RpcAccount {
  return {
    address,
    data: info.data,
    owner: info.owner.toBase58(),
    lamports: BigInt(info.lamports),
    slot,
    receivedAt,
  };
}

function isTransient(e: unknown): boolean {
  const m = e instanceof Error ? e.message : String(e);
  return (
    /ECONNRESET|ETIMEDOUT|EAI_AGAIN|socket hang up|fetch failed/i.test(m) ||
    /50[234]/.test(m)
  );
}
