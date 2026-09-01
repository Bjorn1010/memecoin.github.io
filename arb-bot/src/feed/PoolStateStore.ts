/**
 * Assembles decoded pool snapshots from raw account updates.
 *
 * A pool is never one account. Raydium needs its `PoolState` plus both vault
 * token accounts (the curve reads live vault balances, and the accrued-fee
 * counters that must be subtracted live in the pool account). PumpSwap needs
 * its `Pool` plus both pool token accounts. Both additionally depend on config
 * accounts that are shared across pools and that DO change — pump's fee tiers
 * live in one of them.
 *
 * The snapshot's slot is the OLDEST of its constituent accounts, never the
 * newest: a quote is only as fresh as the stalest number in it.
 */
import type { DexFamily, MintState, PoolSnapshot } from "../types.js";
import type { AccountUpdate } from "./MarketDataFeed.js";
import {
  buildRaydiumPoolData,
  decodeRaydiumAmmConfig,
  decodeRaydiumPoolState,
  type RaydiumPoolStateRaw,
} from "./decoder/raydiumCpmm.js";
import {
  buildPumpSwapPoolData,
  decodePumpFeeConfig,
  decodePumpGlobalConfig,
  decodePumpPool,
  type PumpPoolRaw,
} from "./decoder/pumpSwap.js";
import { decodeTokenAccount } from "./decoder/token2022.js";
import type { RaydiumCpmmAmmConfig } from "../quoters/cpmm/raydiumCpmm.js";
import type { PumpFeeConfig, PumpGlobalConfig } from "../quoters/cpmm/pumpSwap.js";

export interface StoredAccount {
  data: Buffer;
  owner: string;
  slot: number;
  receivedAt: number;
  source: "ws" | "rpc" | "replay";
}

export interface PoolRegistration {
  poolId: string;
  family: DexFamily;
  /** Account holding the pool state. */
  poolAccount: string;
  /** The two token accounts holding the reserves. */
  vaultA: string;
  vaultB: string;
  /** Raydium: the AmmConfig this pool points at. PumpSwap: unused. */
  configAccount?: string;
  /** Mints, cached from the pool account at registration. */
  mintA: string;
  mintB: string;
  /** PumpSwap only: whether pool.creator is the canonical pool authority PDA. */
  isCanonicalPumpPool?: boolean;
  /** Token programs owning each side, needed to build instructions. */
  programA: string;
  programB: string;
  registeredAt: number;
}

export interface PoolStateStoreDeps {
  /** PumpSwap global config account address. */
  pumpGlobalConfigAddress: string;
  /** pump fee program's FeeConfig account address. */
  pumpFeeConfigAddress: string;
}

export interface SnapshotFailure {
  poolId: string;
  reason: string;
}

export class PoolStateStore {
  private readonly accounts = new Map<string, StoredAccount>();
  private readonly pools = new Map<string, PoolRegistration>();
  private readonly mints = new Map<string, MintState>();
  private readonly decodeFailures = new Map<string, number>();
  private readonly subscribed = new Set<string>();

  constructor(private readonly deps: PoolStateStoreDeps) {}

  // --- registration ---------------------------------------------------------

  registerPool(reg: PoolRegistration): void {
    this.pools.set(reg.poolId, reg);
  }

  unregisterPool(poolId: string): void {
    this.pools.delete(poolId);
  }

  getRegistration(poolId: string): PoolRegistration | undefined {
    return this.pools.get(poolId);
  }

  registeredPools(): PoolRegistration[] {
    return [...this.pools.values()];
  }

  setMint(mint: MintState): void {
    this.mints.set(mint.address, mint);
  }

  getMint(address: string): MintState | undefined {
    return this.mints.get(address);
  }

  mintMap(): ReadonlyMap<string, MintState> {
    return this.mints;
  }

  /**
   * Every account that must be kept fresh for the registered pools, including
   * the shared config accounts. This is exactly what gets subscribed.
   */
  requiredAccounts(): string[] {
    const set = new Set<string>([this.deps.pumpGlobalConfigAddress, this.deps.pumpFeeConfigAddress]);
    for (const p of this.pools.values()) {
      set.add(p.poolAccount);
      set.add(p.vaultA);
      set.add(p.vaultB);
      if (p.configAccount) set.add(p.configAccount);
    }
    return [...set];
  }

  /** Accounts belonging to exactly one pool, for unsubscribing on eviction. */
  accountsExclusiveTo(poolId: string): string[] {
    const target = this.pools.get(poolId);
    if (!target) return [];
    const others = [...this.pools.values()].filter((p) => p.poolId !== poolId);
    const usedElsewhere = new Set<string>([
      this.deps.pumpGlobalConfigAddress,
      this.deps.pumpFeeConfigAddress,
    ]);
    for (const p of others) {
      usedElsewhere.add(p.poolAccount);
      usedElsewhere.add(p.vaultA);
      usedElsewhere.add(p.vaultB);
      if (p.configAccount) usedElsewhere.add(p.configAccount);
    }
    const mine = [target.poolAccount, target.vaultA, target.vaultB];
    if (target.configAccount) mine.push(target.configAccount);
    return mine.filter((a) => !usedElsewhere.has(a));
  }

  // --- ingestion ------------------------------------------------------------

  applyUpdate(update: AccountUpdate, source: StoredAccount["source"] = "ws"): void {
    const existing = this.accounts.get(update.address);
    // Out-of-order delivery is possible after a reconnect; never let an older
    // slot overwrite a newer one.
    if (existing && existing.slot > update.slot) return;
    this.accounts.set(update.address, {
      data: update.data,
      owner: update.owner,
      slot: update.slot,
      receivedAt: update.receivedAt,
      source,
    });
  }

  getAccount(address: string): StoredAccount | undefined {
    return this.accounts.get(address);
  }

  /** Tell the store which accounts a live subscription currently covers. */
  setSubscribed(addresses: readonly string[]): void {
    this.subscribed.clear();
    for (const a of addresses) this.subscribed.add(a);
  }

  isSubscribed(address: string): boolean {
    return this.subscribed.has(address);
  }

  hasAllAccountsFor(poolId: string): boolean {
    const reg = this.pools.get(poolId);
    if (!reg) return false;
    const needed = [reg.poolAccount, reg.vaultA, reg.vaultB];
    if (reg.configAccount) needed.push(reg.configAccount);
    if (reg.family === "pump-swap") {
      needed.push(this.deps.pumpGlobalConfigAddress, this.deps.pumpFeeConfigAddress);
    }
    return needed.every((a) => this.accounts.has(a));
  }

  decodeFailureCount(poolId: string): number {
    return this.decodeFailures.get(poolId) ?? 0;
  }

  // --- snapshots ------------------------------------------------------------

  /**
   * Build the quoter's view of a pool, or return the reason we cannot.
   * Never returns a partially-populated snapshot: a missing vault balance would
   * silently become a zero reserve.
   */
  buildSnapshot(poolId: string): { snapshot: PoolSnapshot } | { failure: SnapshotFailure } {
    const reg = this.pools.get(poolId);
    if (!reg) return { failure: { poolId, reason: "pool is not registered" } };

    try {
      return reg.family === "raydium-cpmm"
        ? { snapshot: this.buildRaydium(reg) }
        : { snapshot: this.buildPumpSwap(reg) };
    } catch (e) {
      this.decodeFailures.set(poolId, (this.decodeFailures.get(poolId) ?? 0) + 1);
      return {
        failure: { poolId, reason: e instanceof Error ? e.message : String(e) },
      };
    }
  }

  /** Snapshots for every pool that currently has a complete, decodable state. */
  allSnapshots(): { snapshots: PoolSnapshot[]; failures: SnapshotFailure[] } {
    const snapshots: PoolSnapshot[] = [];
    const failures: SnapshotFailure[] = [];
    for (const poolId of this.pools.keys()) {
      const r = this.buildSnapshot(poolId);
      if ("snapshot" in r) snapshots.push(r.snapshot);
      else failures.push(r.failure);
    }
    return { snapshots, failures };
  }

  private require(address: string, what: string): StoredAccount {
    const a = this.accounts.get(address);
    if (!a) throw new Error(`${what} account ${address} has not been received yet`);
    return a;
  }

  private buildRaydium(reg: PoolRegistration): PoolSnapshot {
    const poolAcc = this.require(reg.poolAccount, "pool");
    const vaultAAcc = this.require(reg.vaultA, "vault A");
    const vaultBAcc = this.require(reg.vaultB, "vault B");
    if (!reg.configAccount) throw new Error("raydium pool registered without an AmmConfig");
    const configAcc = this.require(reg.configAccount, "amm config");

    const pool: RaydiumPoolStateRaw = decodeRaydiumPoolState(poolAcc.data, poolAcc.owner);
    const ammConfig: RaydiumCpmmAmmConfig = decodeRaydiumAmmConfig(
      reg.configAccount,
      configAcc.data,
      configAcc.owner,
    );

    // The registration cached which vault is which; verify against the pool
    // account every time rather than trusting a cache that may predate a
    // pool-state change.
    const vault0Acc = pool.token0Vault === reg.vaultA ? vaultAAcc : vaultBAcc;
    const vault1Acc = pool.token1Vault === reg.vaultB ? vaultBAcc : vaultAAcc;
    if (pool.token0Vault !== reg.vaultA && pool.token0Vault !== reg.vaultB) {
      throw new Error(`pool ${reg.poolId} vault0 ${pool.token0Vault} is not a registered vault`);
    }

    const v0 = decodeTokenAccount(vault0Acc.data, vault0Acc.owner);
    const v1 = decodeTokenAccount(vault1Acc.data, vault1Acc.owner);
    if (v0.mint !== pool.token0Mint || v1.mint !== pool.token1Mint) {
      throw new Error(
        `vault mints (${v0.mint}/${v1.mint}) do not match pool mints (${pool.token0Mint}/${pool.token1Mint})`,
      );
    }

    const data = buildRaydiumPoolData({
      pool,
      ammConfig,
      vault0Amount: v0.amount,
      vault1Amount: v1.amount,
    });

    // Freshness is measured over the VOLATILE accounts only. The AmmConfig
    // changes about never, so it is read once and then sits at whatever slot it
    // was read at; folding it into the minimum would pin every snapshot to
    // startup and make the whole watchlist permanently "stale". We still watch
    // it — a fee change must reach us — but its age says nothing about whether
    // our reserves are current.
    const parts = [poolAcc, vault0Acc, vault1Acc];
    return {
      family: "raydium-cpmm",
      poolId: reg.poolId,
      mintA: pool.token0Mint,
      mintB: pool.token1Mint,
      slot: Math.min(...parts.map((p) => p.slot)),
      receivedAt: Math.min(...parts.map((p) => p.receivedAt)),
      source: poolAcc.source,
      accounts: [reg.poolAccount, pool.token0Vault, pool.token1Vault, reg.configAccount],
      subscribed: [reg.poolAccount, pool.token0Vault, pool.token1Vault].every((a) =>
        this.subscribed.has(a),
      ),
      data,
    };
  }

  private buildPumpSwap(reg: PoolRegistration): PoolSnapshot {
    const poolAcc = this.require(reg.poolAccount, "pool");
    const globalAcc = this.require(this.deps.pumpGlobalConfigAddress, "pump global config");
    const feeAcc = this.require(this.deps.pumpFeeConfigAddress, "pump fee config");

    const pool: PumpPoolRaw = decodePumpPool(poolAcc.data, poolAcc.owner);
    const globalConfig: PumpGlobalConfig = decodePumpGlobalConfig(
      this.deps.pumpGlobalConfigAddress,
      globalAcc.data,
      globalAcc.owner,
    );
    const feeConfig: PumpFeeConfig = decodePumpFeeConfig(
      this.deps.pumpFeeConfigAddress,
      feeAcc.data,
      feeAcc.owner,
    );

    const baseAcc = this.require(pool.poolBaseTokenAccount, "pool base token account");
    const quoteAcc = this.require(pool.poolQuoteTokenAccount, "pool quote token account");
    const base = decodeTokenAccount(baseAcc.data, baseAcc.owner);
    const quote = decodeTokenAccount(quoteAcc.data, quoteAcc.owner);
    if (base.mint !== pool.baseMint || quote.mint !== pool.quoteMint) {
      throw new Error(
        `pool token account mints (${base.mint}/${quote.mint}) do not match pool mints (${pool.baseMint}/${pool.quoteMint})`,
      );
    }

    const data = buildPumpSwapPoolData({
      pool,
      globalConfig,
      feeConfig,
      isCanonicalPumpPool: reg.isCanonicalPumpPool ?? false,
      baseTokenProgram: baseAcc.owner,
      quoteTokenProgram: quoteAcc.owner,
      poolBaseAmount: base.amount,
      poolQuoteAmount: quote.amount,
    });

    // Volatile accounts only — see the note in buildRaydium. The global and fee
    // configs are subscribed so a fee-tier change reaches us immediately, but
    // their slot is not a measure of our data's freshness.
    const parts = [poolAcc, baseAcc, quoteAcc];
    return {
      family: "pump-swap",
      poolId: reg.poolId,
      mintA: pool.baseMint,
      mintB: pool.quoteMint,
      slot: Math.min(...parts.map((p) => p.slot)),
      receivedAt: Math.min(...parts.map((p) => p.receivedAt)),
      source: poolAcc.source,
      accounts: [
        reg.poolAccount,
        pool.poolBaseTokenAccount,
        pool.poolQuoteTokenAccount,
        this.deps.pumpGlobalConfigAddress,
        this.deps.pumpFeeConfigAddress,
      ],
      subscribed: [reg.poolAccount, pool.poolBaseTokenAccount, pool.poolQuoteTokenAccount].every(
        (a) => this.subscribed.has(a),
      ),
      data,
    };
  }
}
