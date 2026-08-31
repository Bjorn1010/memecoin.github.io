/**
 * Address derivations for both venues.
 *
 * Every pool and vault address we need is a program-derived address, which
 * turns discovery from an expensive `getProgramAccounts` scan into a handful of
 * local hashes plus one `getMultipleAccounts`. On a free endpoint that is the
 * difference between a screener that runs and one that spends its whole budget
 * on a single sweep — the public endpoint would not complete a single
 * program-account scan of these programs at all.
 *
 * SEEDS (from the programs' own sources, see ASSUMPTIONS.md #PDA-1..#PDA-6):
 *   Raydium CP-Swap
 *     amm_config   = ["amm_config", index as u16 big-endian]
 *     pool_state   = ["pool", amm_config, token_0_mint, token_1_mint]
 *                    with the constraint token_0_mint < token_1_mint
 *     vault        = ["pool_vault", pool_state, mint]
 *     observation  = ["observation", pool_state]
 *     authority    = ["vault_and_lp_mint_auth_seed"]
 *   PumpSwap
 *     pool           = ["pool", index as u16 little-endian, creator, base_mint, quote_mint]
 *     pool authority = ["pool-authority", base_mint] on the PUMP program
 *     global_config  = ["global_config"]
 *     event authority= ["__event_authority"]
 *     creator vault  = ["creator_vault", coin_creator]
 *     fee_config     = ["fee_config", pump_amm_program] on the fee program
 *
 * A Raydium pool may also be a plain keypair account rather than the canonical
 * PDA; those are found by the optional deep scan, not here.
 */
import { PublicKey } from "@solana/web3.js";

export const RAYDIUM_CPMM_PROGRAM = new PublicKey("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C");
export const PUMP_AMM_PROGRAM = new PublicKey("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA");
export const PUMP_PROGRAM = new PublicKey("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P");
export const PUMP_FEE_PROGRAM = new PublicKey("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ");
export const ASSOCIATED_TOKEN_PROGRAM = new PublicKey("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL");
export const SYSTEM_PROGRAM = new PublicKey("11111111111111111111111111111111");

function pda(seeds: (Buffer | Uint8Array)[], program: PublicKey): PublicKey {
  return PublicKey.findProgramAddressSync(seeds, program)[0];
}

function u16be(value: number): Buffer {
  const b = Buffer.alloc(2);
  b.writeUInt16BE(value);
  return b;
}

function u16le(value: number): Buffer {
  const b = Buffer.alloc(2);
  b.writeUInt16LE(value);
  return b;
}

// --- Raydium ---------------------------------------------------------------

export function raydiumAuthority(): PublicKey {
  return pda([Buffer.from("vault_and_lp_mint_auth_seed")], RAYDIUM_CPMM_PROGRAM);
}

export function raydiumAmmConfig(index: number): PublicKey {
  return pda([Buffer.from("amm_config"), u16be(index)], RAYDIUM_CPMM_PROGRAM);
}

/** Canonical mint ordering: the program requires token_0_mint < token_1_mint. */
export function orderMints(a: string, b: string): [string, string] {
  const ab = new PublicKey(a).toBuffer();
  const bb = new PublicKey(b).toBuffer();
  return Buffer.compare(ab, bb) < 0 ? [a, b] : [b, a];
}

export function raydiumPoolAddress(ammConfig: PublicKey, mintX: string, mintY: string): PublicKey {
  const [m0, m1] = orderMints(mintX, mintY);
  return pda(
    [
      Buffer.from("pool"),
      ammConfig.toBuffer(),
      new PublicKey(m0).toBuffer(),
      new PublicKey(m1).toBuffer(),
    ],
    RAYDIUM_CPMM_PROGRAM,
  );
}

export function raydiumVault(pool: PublicKey, mint: string): PublicKey {
  return pda(
    [Buffer.from("pool_vault"), pool.toBuffer(), new PublicKey(mint).toBuffer()],
    RAYDIUM_CPMM_PROGRAM,
  );
}

export function raydiumObservation(pool: PublicKey): PublicKey {
  return pda([Buffer.from("observation"), pool.toBuffer()], RAYDIUM_CPMM_PROGRAM);
}

// --- PumpSwap --------------------------------------------------------------

export function pumpPoolAuthority(baseMint: string): PublicKey {
  return pda([Buffer.from("pool-authority"), new PublicKey(baseMint).toBuffer()], PUMP_PROGRAM);
}

export function pumpPoolAddress(
  index: number,
  creator: PublicKey,
  baseMint: string,
  quoteMint: string,
): PublicKey {
  return pda(
    [
      Buffer.from("pool"),
      u16le(index),
      creator.toBuffer(),
      new PublicKey(baseMint).toBuffer(),
      new PublicKey(quoteMint).toBuffer(),
    ],
    PUMP_AMM_PROGRAM,
  );
}

/** The pool pump.fun itself creates when a bonding curve completes. */
export function pumpCanonicalPool(baseMint: string, quoteMint: string): PublicKey {
  return pumpPoolAddress(0, pumpPoolAuthority(baseMint), baseMint, quoteMint);
}

export function pumpGlobalConfig(): PublicKey {
  return pda([Buffer.from("global_config")], PUMP_AMM_PROGRAM);
}

export function pumpEventAuthority(): PublicKey {
  return pda([Buffer.from("__event_authority")], PUMP_AMM_PROGRAM);
}

export function pumpCreatorVaultAuthority(coinCreator: string): PublicKey {
  return pda(
    [Buffer.from("creator_vault"), new PublicKey(coinCreator).toBuffer()],
    PUMP_AMM_PROGRAM,
  );
}

export function pumpFeeConfig(): PublicKey {
  return pda([Buffer.from("fee_config"), PUMP_AMM_PROGRAM.toBuffer()], PUMP_FEE_PROGRAM);
}

export function pumpGlobalVolumeAccumulator(): PublicKey {
  return pda([Buffer.from("global_volume_accumulator")], PUMP_AMM_PROGRAM);
}

export function pumpUserVolumeAccumulator(user: PublicKey): PublicKey {
  return pda([Buffer.from("user_volume_accumulator"), user.toBuffer()], PUMP_AMM_PROGRAM);
}

// --- SPL -------------------------------------------------------------------

/** Associated token address, allowing an off-curve owner (a PDA). */
export function associatedTokenAddress(
  mint: string,
  owner: PublicKey,
  tokenProgram: PublicKey,
): PublicKey {
  return pda(
    [owner.toBuffer(), tokenProgram.toBuffer(), new PublicKey(mint).toBuffer()],
    ASSOCIATED_TOKEN_PROGRAM,
  );
}
