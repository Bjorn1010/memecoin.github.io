/**
 * Address lookup table.
 *
 * NOT an optimisation — a requirement. A cycle that crosses PumpSwap and
 * Raydium touches around thirty accounts, and measured, such a transaction
 * serialises to 1281 bytes against Solana's 1232-byte limit. Without a lookup
 * table the bot can only ever trade Raydium-to-Raydium cycles, which throws
 * away most of the opportunity set it was built for.
 *
 * A lookup table replaces each 32-byte account key with a 1-byte index, so
 * putting the ~20 addresses that appear in EVERY cycle into one table saves
 * roughly 600 bytes and brings mixed-venue cycles comfortably inside the limit.
 *
 * The table is created once by `npm run setup` and its address goes in the
 * environment. Tables are owned by the wallet that created them and can be
 * extended later as the watchlist changes.
 */
import {
  AddressLookupTableProgram,
  PublicKey,
  type AddressLookupTableAccount,
  type Connection,
  type TransactionInstruction,
} from "@solana/web3.js";
import {
  ASSOCIATED_TOKEN_PROGRAM,
  PUMP_AMM_PROGRAM,
  PUMP_FEE_PROGRAM,
  RAYDIUM_CPMM_PROGRAM,
  SYSTEM_PROGRAM,
  pumpEventAuthority,
  pumpFeeConfig,
  pumpGlobalConfig,
  pumpGlobalVolumeAccumulator,
  pumpUserVolumeAccumulator,
  raydiumAuthority,
} from "../screener/pdas.js";
import { TOKEN_2022_PROGRAM_ID, TOKEN_PROGRAM_ID } from "../feed/decoder/token2022.js";

export const COMPUTE_BUDGET_PROGRAM = new PublicKey("ComputeBudget111111111111111111111111111111");

/** A lookup table holds at most 256 addresses. */
export const MAX_LOOKUP_TABLE_ADDRESSES = 256;

/**
 * Addresses that appear in every cycle, whatever the pools.
 *
 * `user` is included because the wallet's own key and its derived accounts show
 * up in both legs; putting them in the table pays for itself immediately.
 */
export function staticLookupAddresses(user: PublicKey): PublicKey[] {
  return [
    // programs
    RAYDIUM_CPMM_PROGRAM,
    PUMP_AMM_PROGRAM,
    PUMP_FEE_PROGRAM,
    new PublicKey(TOKEN_PROGRAM_ID),
    new PublicKey(TOKEN_2022_PROGRAM_ID),
    ASSOCIATED_TOKEN_PROGRAM,
    SYSTEM_PROGRAM,
    COMPUTE_BUDGET_PROGRAM,
    // shared PDAs
    raydiumAuthority(),
    pumpGlobalConfig(),
    pumpFeeConfig(),
    pumpEventAuthority(),
    pumpGlobalVolumeAccumulator(),
    pumpUserVolumeAccumulator(user),
  ];
}

/** Per-pool addresses worth adding once a pool is on the watchlist. */
export function poolLookupAddresses(pools: readonly {
  poolAccount: string;
  vaultA: string;
  vaultB: string;
  configAccount?: string;
}[]): PublicKey[] {
  const out: PublicKey[] = [];
  for (const p of pools) {
    out.push(new PublicKey(p.poolAccount), new PublicKey(p.vaultA), new PublicKey(p.vaultB));
    if (p.configAccount) out.push(new PublicKey(p.configAccount));
  }
  return out;
}

export interface CreateLookupTableResult {
  instructions: TransactionInstruction[];
  lookupTableAddress: PublicKey;
}

/**
 * Instructions to create a table and fill it with the static addresses.
 *
 * `recentSlot` must be a slot the cluster considers recent; the table's address
 * is derived from it, so passing a stale slot produces an address the program
 * will reject.
 */
export function createLookupTableInstructions(args: {
  authority: PublicKey;
  payer: PublicKey;
  recentSlot: number;
  addresses: PublicKey[];
}): CreateLookupTableResult {
  const [createIx, lookupTableAddress] = AddressLookupTableProgram.createLookupTable({
    authority: args.authority,
    payer: args.payer,
    recentSlot: args.recentSlot,
  });

  const instructions: TransactionInstruction[] = [createIx];
  // `extendLookupTable` is bounded by transaction size, so chunk it.
  for (let i = 0; i < args.addresses.length; i += 20) {
    instructions.push(
      AddressLookupTableProgram.extendLookupTable({
        payer: args.payer,
        authority: args.authority,
        lookupTable: lookupTableAddress,
        addresses: args.addresses.slice(i, i + 20),
      }),
    );
  }
  return { instructions, lookupTableAddress };
}

export function extendLookupTableInstructions(args: {
  authority: PublicKey;
  payer: PublicKey;
  lookupTable: PublicKey;
  addresses: PublicKey[];
}): TransactionInstruction[] {
  const out: TransactionInstruction[] = [];
  for (let i = 0; i < args.addresses.length; i += 20) {
    out.push(
      AddressLookupTableProgram.extendLookupTable({
        payer: args.payer,
        authority: args.authority,
        lookupTable: args.lookupTable,
        addresses: args.addresses.slice(i, i + 20),
      }),
    );
  }
  return out;
}

/**
 * Load a table for use in message compilation.
 *
 * Returns null when the address holds no table, so the caller can say so
 * plainly rather than silently building oversized transactions.
 */
export async function loadLookupTable(
  connection: Connection,
  address: string,
): Promise<AddressLookupTableAccount | null> {
  const result = await connection.getAddressLookupTable(new PublicKey(address));
  return result.value ?? null;
}

/** Addresses already in a table, so `setup` only extends with what is missing. */
export function missingFromTable(
  table: AddressLookupTableAccount | null,
  wanted: readonly PublicKey[],
): PublicKey[] {
  const present = new Set((table?.state.addresses ?? []).map((a) => a.toBase58()));
  const seen = new Set<string>();
  const out: PublicKey[] = [];
  for (const a of wanted) {
    const k = a.toBase58();
    if (present.has(k) || seen.has(k)) continue;
    seen.add(k);
    out.push(a);
  }
  return out;
}
