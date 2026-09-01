/**
 * Pool discovery.
 *
 * Finds, for a given token, every WSOL pool we can quote exactly. A token with
 * fewer than two such pools cannot produce a two-leg cycle and is dropped
 * immediately — most tokens are dropped here, which is the point: discovery is
 * a filter, not a collector.
 *
 * PRIMARY PATH: derive candidate addresses locally and read them with one
 * `getMultipleAccounts`. Both venues put their pools at program-derived
 * addresses, so a token's pools can be found for the cost of a few hashes plus
 * a single batched read.
 *
 * FALLBACK PATH: `getProgramAccounts` with memcmp filters, which finds pools at
 * non-canonical addresses too. It is opt-in and charged heavily by the budget
 * because it is genuinely expensive: on the public endpoint a single such scan
 * of these programs does not complete at all, which is exactly why the primary
 * path exists.
 */
import { PublicKey } from "@solana/web3.js";
import { RpcPriority } from "../rpc/RpcBudget.js";
import type { RpcClient } from "../rpc/RpcClient.js";
import {
  RAYDIUM_CPMM_PROGRAM_ID,
  RAYDIUM_POOL_STATE_LEN,
  decodeRaydiumPoolState,
} from "../feed/decoder/raydiumCpmm.js";
import { PUMP_SWAP_PROGRAM_ID, decodePumpPool } from "../feed/decoder/pumpSwap.js";
import { decodeMint } from "../feed/decoder/token2022.js";
import type { PoolRegistration } from "../feed/PoolStateStore.js";
import type { MintState } from "../types.js";
import { WSOL_MINT } from "../config/schema.js";
import {
  pumpCanonicalPool,
  pumpFeeConfig,
  pumpGlobalConfig,
  pumpPoolAuthority,
  raydiumAmmConfig,
  raydiumPoolAddress,
} from "./pdas.js";

/** Byte offsets of the mint fields, used by the fallback memcmp filters. */
const RAYDIUM_TOKEN_0_MINT_OFFSET = 168;
const RAYDIUM_TOKEN_1_MINT_OFFSET = 200;
const PUMP_BASE_MINT_OFFSET = 43;
const PUMP_QUOTE_MINT_OFFSET = 75;

/**
 * Raydium `AmmConfig` indices to probe. Config 0 is the long-standing default;
 * the rest exist for other fee tiers. Probing a handful of indices costs
 * nothing locally and one batched read on-chain.
 */
export const DEFAULT_RAYDIUM_CONFIG_INDICES = [0, 1, 2, 3, 4, 5, 6, 7];

export interface DiscoveredPool extends PoolRegistration {
  /** Mint that is not the base asset. */
  intermediateMint: string;
}

export function pumpGlobalConfigAddress(): string {
  return pumpGlobalConfig().toBase58();
}

export function pumpFeeConfigAddress(): string {
  return pumpFeeConfig().toBase58();
}

/**
 * Derive every candidate pool address for a token, on both venues, without a
 * single network call.
 */
export function candidatePoolAddresses(
  mint: string,
  baseMint = WSOL_MINT,
  raydiumConfigIndices: readonly number[] = DEFAULT_RAYDIUM_CONFIG_INDICES,
): { address: string; family: "raydium-cpmm" | "pump-swap" }[] {
  const out: { address: string; family: "raydium-cpmm" | "pump-swap" }[] = [];
  for (const index of raydiumConfigIndices) {
    out.push({
      address: raydiumPoolAddress(raydiumAmmConfig(index), mint, baseMint).toBase58(),
      family: "raydium-cpmm",
    });
  }
  // pump.fun's canonical pool always has the token as base and WSOL as quote.
  out.push({ address: pumpCanonicalPool(mint, baseMint).toBase58(), family: "pump-swap" });
  return out;
}

/** Read the candidate addresses and keep the ones that are real pools. */
export async function discoverPoolsForMint(
  rpc: RpcClient,
  mint: string,
  baseMint = WSOL_MINT,
  raydiumConfigIndices: readonly number[] = DEFAULT_RAYDIUM_CONFIG_INDICES,
): Promise<DiscoveredPool[]> {
  const candidates = candidatePoolAddresses(mint, baseMint, raydiumConfigIndices);
  const accounts = await rpc.getAccounts(
    candidates.map((c) => c.address),
    RpcPriority.P3_Screener,
  );

  const out: DiscoveredPool[] = [];
  const now = Date.now();
  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i]!;
    const acc = accounts[i];
    if (!acc) continue;
    const pool = toRegistration(candidate.family, acc.address, acc.data, acc.owner, baseMint, now);
    if (pool) out.push(pool);
  }
  return out;
}

/** Batched variant: one `getMultipleAccounts` round for many mints at once. */
export async function discoverPoolsForMints(
  rpc: RpcClient,
  mints: readonly string[],
  baseMint = WSOL_MINT,
  raydiumConfigIndices: readonly number[] = DEFAULT_RAYDIUM_CONFIG_INDICES,
): Promise<Map<string, DiscoveredPool[]>> {
  const candidates: { mint: string; address: string; family: "raydium-cpmm" | "pump-swap" }[] = [];
  for (const mint of mints) {
    for (const c of candidatePoolAddresses(mint, baseMint, raydiumConfigIndices)) {
      candidates.push({ mint, ...c });
    }
  }
  const accounts = await rpc.getAccounts(
    candidates.map((c) => c.address),
    RpcPriority.P3_Screener,
  );

  const byMint = new Map<string, DiscoveredPool[]>();
  const now = Date.now();
  for (let i = 0; i < candidates.length; i++) {
    const candidate = candidates[i]!;
    const acc = accounts[i];
    if (!acc) continue;
    const pool = toRegistration(candidate.family, acc.address, acc.data, acc.owner, baseMint, now);
    if (!pool) continue;
    const list = byMint.get(candidate.mint);
    if (list) list.push(pool);
    else byMint.set(candidate.mint, [pool]);
  }
  return byMint;
}

function toRegistration(
  family: "raydium-cpmm" | "pump-swap",
  address: string,
  data: Buffer,
  owner: string,
  baseMint: string,
  now: number,
): DiscoveredPool | null {
  try {
    if (family === "raydium-cpmm") {
      const pool = decodeRaydiumPoolState(data, owner);
      // A pool that does not actually trade the base asset is not ours.
      if (pool.token0Mint !== baseMint && pool.token1Mint !== baseMint) return null;
      return {
        poolId: address,
        family,
        poolAccount: address,
        vaultA: pool.token0Vault,
        vaultB: pool.token1Vault,
        configAccount: pool.ammConfigAddress,
        mintA: pool.token0Mint,
        mintB: pool.token1Mint,
        programA: pool.token0Program,
        programB: pool.token1Program,
        intermediateMint: pool.token0Mint === baseMint ? pool.token1Mint : pool.token0Mint,
        registeredAt: now,
      };
    }
    const pool = decodePumpPool(data, owner);
    if (pool.baseMint !== baseMint && pool.quoteMint !== baseMint) return null;
    return {
      poolId: address,
      family,
      poolAccount: address,
      vaultA: pool.poolBaseTokenAccount,
      vaultB: pool.poolQuoteTokenAccount,
      mintA: pool.baseMint,
      mintB: pool.quoteMint,
      isCanonicalPumpPool: pool.creator === pumpPoolAuthority(pool.baseMint).toBase58(),
      programA: "",
      programB: "",
      intermediateMint: pool.baseMint === baseMint ? pool.quoteMint : pool.baseMint,
      registeredAt: now,
    };
  } catch {
    // Not a pool account of this family, or a layout we do not recognise.
    return null;
  }
}

// --- optional deep scan ----------------------------------------------------

/**
 * Find pools at non-canonical addresses. Expensive; call it deliberately, not
 * on a schedule, and expect a public endpoint to refuse it outright.
 */
export async function deepScanPoolsForMint(
  rpc: RpcClient,
  mint: string,
  baseMint = WSOL_MINT,
): Promise<DiscoveredPool[]> {
  const out: DiscoveredPool[] = [];
  const now = Date.now();

  for (const [mintOffset, baseOffset] of [
    [RAYDIUM_TOKEN_0_MINT_OFFSET, RAYDIUM_TOKEN_1_MINT_OFFSET],
    [RAYDIUM_TOKEN_1_MINT_OFFSET, RAYDIUM_TOKEN_0_MINT_OFFSET],
  ] as const) {
    const accounts = await rpc.getProgramAccounts(
      RAYDIUM_CPMM_PROGRAM_ID,
      [
        { dataSize: RAYDIUM_POOL_STATE_LEN },
        { memcmp: { offset: mintOffset, bytes: mint } },
        { memcmp: { offset: baseOffset, bytes: baseMint } },
      ],
      RpcPriority.P3_Screener,
    );
    for (const a of accounts) {
      const reg = toRegistration("raydium-cpmm", a.address, a.data, a.owner, baseMint, now);
      if (reg) out.push(reg);
    }
  }

  const pumpAccounts = await rpc.getProgramAccounts(
    PUMP_SWAP_PROGRAM_ID,
    [
      { memcmp: { offset: PUMP_BASE_MINT_OFFSET, bytes: mint } },
      { memcmp: { offset: PUMP_QUOTE_MINT_OFFSET, bytes: baseMint } },
    ],
    RpcPriority.P3_Screener,
  );
  for (const a of pumpAccounts) {
    const reg = toRegistration("pump-swap", a.address, a.data, a.owner, baseMint, now);
    if (reg) out.push(reg);
  }

  return out;
}

/**
 * Build the token universe from recent on-chain activity.
 *
 * Sampling recent transactions on the two programs is far cheaper than scanning
 * every pool account, and it biases the universe toward tokens that are
 * actually trading — which is where a price gap can appear at all.
 */
export async function discoverActiveMints(
  rpc: RpcClient,
  options: { transactionsPerVenue: number; baseMint?: string } = { transactionsPerVenue: 60 },
): Promise<Map<string, number>> {
  const baseMint = options.baseMint ?? WSOL_MINT;
  const counts = new Map<string, number>();
  const bump = (mint: string): void => {
    if (mint === baseMint) return;
    counts.set(mint, (counts.get(mint) ?? 0) + 1);
  };

  for (const programId of [PUMP_SWAP_PROGRAM_ID, RAYDIUM_CPMM_PROGRAM_ID]) {
    let sigs;
    try {
      sigs = await rpc.call(RpcPriority.P3_Screener, (c) =>
        c.getSignaturesForAddress(new PublicKey(programId), {
          limit: options.transactionsPerVenue,
        }),
      );
    } catch {
      continue;
    }

    for (const s of sigs) {
      if (s.err) continue;
      let tx;
      try {
        tx = await rpc.call(RpcPriority.P3_Screener, (c) =>
          c.getTransaction(s.signature, {
            maxSupportedTransactionVersion: 0,
            commitment: "confirmed",
          }),
        );
      } catch {
        continue;
      }
      if (!tx?.meta) continue;
      // Token balances name every mint the transaction touched, without needing
      // to decode any instruction.
      for (const b of [...(tx.meta.preTokenBalances ?? []), ...(tx.meta.postTokenBalances ?? [])]) {
        if (b.mint) bump(b.mint);
      }
    }
  }
  return counts;
}

/** Fetch and decode a mint account into the risk filter's view of it. */
export async function fetchMint(
  rpc: RpcClient,
  address: string,
  currentEpoch: bigint,
  priority: RpcPriority = RpcPriority.P3_Screener,
): Promise<MintState | null> {
  const acc = await rpc.getAccount(address, priority);
  if (!acc) return null;
  try {
    return decodeMint({
      address,
      data: acc.data,
      programId: acc.owner,
      slot: acc.slot,
      receivedAt: acc.receivedAt,
      source: "rpc",
      currentEpoch,
    });
  } catch {
    return null;
  }
}

/** Mints with at least two quotable pools — the only ones worth watching. */
export function mintsWithMultiplePools(
  pools: readonly DiscoveredPool[],
): Map<string, DiscoveredPool[]> {
  const byMint = new Map<string, DiscoveredPool[]>();
  for (const p of pools) {
    const list = byMint.get(p.intermediateMint);
    if (list) list.push(p);
    else byMint.set(p.intermediateMint, [p]);
  }
  for (const [mint, list] of byMint) {
    if (list.length < 2) byMint.delete(mint);
  }
  return byMint;
}
