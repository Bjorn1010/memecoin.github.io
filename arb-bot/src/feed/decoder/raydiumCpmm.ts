/**
 * Binary decoders for Raydium CP-Swap accounts.
 *
 * Offsets are derived from the program's Rust definitions, which the on-chain
 * IDL (v0.2.0) confirms field-for-field:
 *  - `PoolState` is `#[account(zero_copy(unsafe))] #[repr(C, packed)]`, so
 *    fields are laid out sequentially with NO alignment padding. Assuming
 *    natural alignment here would shift every field after `auth_bump` and
 *    silently produce plausible-looking garbage.
 *  - `AmmConfig` is a normal Anchor account, i.e. Borsh, which is also
 *    unpadded.
 *
 * Both decoders verify the 8-byte discriminator and the account length before
 * reading anything: a wrong account type must fail loudly, never decode.
 */
import type { RaydiumCpmmAmmConfig, RaydiumCpmmPoolData } from "../../quoters/cpmm/raydiumCpmm.js";
import { bs58Encode } from "./token2022.js";

export const RAYDIUM_CPMM_PROGRAM_ID = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C";

/** `PoolState` account discriminator, from the on-chain IDL. */
export const RAYDIUM_POOL_STATE_DISCRIMINATOR = Buffer.from([247, 237, 227, 245, 215, 195, 222, 70]);
/** `AmmConfig` account discriminator, from the on-chain IDL. */
export const RAYDIUM_AMM_CONFIG_DISCRIMINATOR = Buffer.from([218, 244, 33, 104, 203, 203, 43, 111]);

/** `PoolState::LEN` = 8 + 10*32 + 5 + 7*8 + 2 + 6 + 2*8 + 28*8. */
export const RAYDIUM_POOL_STATE_LEN = 637;
/** `AmmConfig::LEN` = 8 + 1 + 1 + 2 + 4*8 + 2*32 + 8 + 15*8. */
export const RAYDIUM_AMM_CONFIG_LEN = 236;

export class DecodeError extends Error {
  constructor(what: string, detail: string) {
    super(`failed to decode ${what}: ${detail}`);
    this.name = "DecodeError";
  }
}

function requireDiscriminator(data: Buffer, expected: Buffer, what: string): void {
  if (data.length < 8) throw new DecodeError(what, `account is ${data.length} bytes`);
  if (!data.subarray(0, 8).equals(expected)) {
    throw new DecodeError(
      what,
      `discriminator ${data.subarray(0, 8).toString("hex")} != ${expected.toString("hex")}`,
    );
  }
}

function pubkey(data: Buffer, offset: number): string {
  return bs58Encode(data.subarray(offset, offset + 32));
}

/** Field offsets, named so a reviewer can check them against the Rust struct. */
const POOL = {
  ammConfig: 8,
  poolCreator: 40,
  token0Vault: 72,
  token1Vault: 104,
  lpMint: 136,
  token0Mint: 168,
  token1Mint: 200,
  token0Program: 232,
  token1Program: 264,
  observationKey: 296,
  authBump: 328,
  status: 329,
  lpMintDecimals: 330,
  mint0Decimals: 331,
  mint1Decimals: 332,
  lpSupply: 333,
  protocolFeesToken0: 341,
  protocolFeesToken1: 349,
  fundFeesToken0: 357,
  fundFeesToken1: 365,
  openTime: 373,
  recentEpoch: 381,
  creatorFeeOn: 389,
  enableCreatorFee: 390,
  creatorFeesToken0: 397,
  creatorFeesToken1: 405,
} as const;

export interface RaydiumPoolStateRaw {
  ammConfigAddress: string;
  poolCreator: string;
  token0Vault: string;
  token1Vault: string;
  lpMint: string;
  token0Mint: string;
  token1Mint: string;
  token0Program: string;
  token1Program: string;
  observationKey: string;
  status: number;
  mint0Decimals: number;
  mint1Decimals: number;
  lpSupply: bigint;
  protocolFeesToken0: bigint;
  protocolFeesToken1: bigint;
  fundFeesToken0: bigint;
  fundFeesToken1: bigint;
  openTime: bigint;
  recentEpoch: bigint;
  creatorFeeOn: number;
  enableCreatorFee: boolean;
  creatorFeesToken0: bigint;
  creatorFeesToken1: bigint;
}

export function decodeRaydiumPoolState(data: Buffer): RaydiumPoolStateRaw {
  requireDiscriminator(data, RAYDIUM_POOL_STATE_DISCRIMINATOR, "Raydium PoolState");
  if (data.length < RAYDIUM_POOL_STATE_LEN) {
    throw new DecodeError(
      "Raydium PoolState",
      `account is ${data.length} bytes, need at least ${RAYDIUM_POOL_STATE_LEN}`,
    );
  }
  return {
    ammConfigAddress: pubkey(data, POOL.ammConfig),
    poolCreator: pubkey(data, POOL.poolCreator),
    token0Vault: pubkey(data, POOL.token0Vault),
    token1Vault: pubkey(data, POOL.token1Vault),
    lpMint: pubkey(data, POOL.lpMint),
    token0Mint: pubkey(data, POOL.token0Mint),
    token1Mint: pubkey(data, POOL.token1Mint),
    token0Program: pubkey(data, POOL.token0Program),
    token1Program: pubkey(data, POOL.token1Program),
    observationKey: pubkey(data, POOL.observationKey),
    status: data.readUInt8(POOL.status),
    mint0Decimals: data.readUInt8(POOL.mint0Decimals),
    mint1Decimals: data.readUInt8(POOL.mint1Decimals),
    lpSupply: data.readBigUInt64LE(POOL.lpSupply),
    protocolFeesToken0: data.readBigUInt64LE(POOL.protocolFeesToken0),
    protocolFeesToken1: data.readBigUInt64LE(POOL.protocolFeesToken1),
    fundFeesToken0: data.readBigUInt64LE(POOL.fundFeesToken0),
    fundFeesToken1: data.readBigUInt64LE(POOL.fundFeesToken1),
    openTime: data.readBigUInt64LE(POOL.openTime),
    recentEpoch: data.readBigUInt64LE(POOL.recentEpoch),
    creatorFeeOn: data.readUInt8(POOL.creatorFeeOn),
    enableCreatorFee: data.readUInt8(POOL.enableCreatorFee) !== 0,
    creatorFeesToken0: data.readBigUInt64LE(POOL.creatorFeesToken0),
    creatorFeesToken1: data.readBigUInt64LE(POOL.creatorFeesToken1),
  };
}

const CONFIG = {
  bump: 8,
  disableCreatePool: 9,
  index: 10,
  tradeFeeRate: 12,
  protocolFeeRate: 20,
  fundFeeRate: 28,
  createPoolFee: 36,
  protocolOwner: 44,
  fundOwner: 76,
  creatorFeeRate: 108,
} as const;

export function decodeRaydiumAmmConfig(address: string, data: Buffer): RaydiumCpmmAmmConfig {
  requireDiscriminator(data, RAYDIUM_AMM_CONFIG_DISCRIMINATOR, "Raydium AmmConfig");
  if (data.length < CONFIG.creatorFeeRate + 8) {
    throw new DecodeError("Raydium AmmConfig", `account is ${data.length} bytes`);
  }
  return {
    address,
    tradeFeeRate: data.readBigUInt64LE(CONFIG.tradeFeeRate),
    protocolFeeRate: data.readBigUInt64LE(CONFIG.protocolFeeRate),
    fundFeeRate: data.readBigUInt64LE(CONFIG.fundFeeRate),
    creatorFeeRate: data.readBigUInt64LE(CONFIG.creatorFeeRate),
  };
}

/**
 * Assemble the quoter's view of a pool from its three accounts.
 *
 * The vault balances come from the token accounts rather than from PoolState:
 * the program reads `input_vault.amount` live, so a cached reserve inside the
 * pool account would be the wrong number.
 */
export function buildRaydiumPoolData(args: {
  pool: RaydiumPoolStateRaw;
  ammConfig: RaydiumCpmmAmmConfig;
  vault0Amount: bigint;
  vault1Amount: bigint;
}): RaydiumCpmmPoolData {
  const { pool, ammConfig } = args;
  return {
    ammConfig,
    token0Mint: pool.token0Mint,
    token1Mint: pool.token1Mint,
    token0Vault: pool.token0Vault,
    token1Vault: pool.token1Vault,
    token0Program: pool.token0Program,
    token1Program: pool.token1Program,
    observationKey: pool.observationKey,
    status: pool.status,
    openTime: pool.openTime,
    creatorFeeOn: pool.creatorFeeOn,
    enableCreatorFee: pool.enableCreatorFee,
    vault0Amount: args.vault0Amount,
    vault1Amount: args.vault1Amount,
    protocolFeesToken0: pool.protocolFeesToken0,
    protocolFeesToken1: pool.protocolFeesToken1,
    fundFeesToken0: pool.fundFeesToken0,
    fundFeesToken1: pool.fundFeesToken1,
    creatorFeesToken0: pool.creatorFeesToken0,
    creatorFeesToken1: pool.creatorFeesToken1,
  };
}
