/**
 * Binary decoders for PumpSwap and pump's fee program accounts.
 *
 * Offsets follow the Anchor (Borsh) layouts in the IDLs the two programs
 * publish on-chain. Borsh is unpadded, so fields are sequential.
 *
 * One field needs explaining. `Pool.virtual_quote_reserves` appears in
 * pump.fun's own SDK (v1.19.0) but not yet in the IDL the program publishes.
 * Live pool accounts are 301 bytes, comfortably past the 245 the older layout
 * needs, and Anchor zero-initialises reserve space — so reading an i128 at
 * offset 245 yields the real value if the field exists and 0 if it does not,
 * and 0 is exactly the SDK's own default. The decoder additionally refuses an
 * absurd value rather than trusting reserve bytes blindly.
 */
import type {
  PumpFeeConfig,
  PumpFeeTier,
  PumpFees,
  PumpGlobalConfig,
  PumpSwapPoolData,
} from "../../quoters/cpmm/pumpSwap.js";
import { DecodeError } from "./raydiumCpmm.js";
import { bs58Encode } from "./token2022.js";

export const PUMP_SWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA";
export const PUMP_FEE_PROGRAM_ID = "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ";

export const PUMP_POOL_DISCRIMINATOR = Buffer.from([241, 154, 109, 4, 17, 177, 109, 188]);
export const PUMP_GLOBAL_CONFIG_DISCRIMINATOR = Buffer.from([149, 8, 156, 202, 160, 252, 176, 217]);
export const PUMP_FEE_CONFIG_DISCRIMINATOR = Buffer.from([143, 52, 146, 187, 219, 123, 76, 155]);

/** Length of the Pool layout WITHOUT `virtual_quote_reserves`. */
export const PUMP_POOL_MIN_LEN = 245;
/** Length WITH it. Live accounts are larger still (reserve space). */
export const PUMP_POOL_LEN_WITH_VIRTUAL = 261;

/**
 * Owner AND discriminator. An Anchor discriminator is derived from the account
 * type's NAME, so two unrelated programs defining `Pool` produce identical
 * leading bytes; only the owner distinguishes them. See the note in
 * decoder/raydiumCpmm.ts for the mainnet account that proves this is real.
 */
function requireOwnerAndDiscriminator(
  data: Buffer,
  owner: string,
  expectedOwner: string,
  expected: Buffer,
  what: string,
): void {
  if (owner !== expectedOwner) {
    throw new DecodeError(what, `account is owned by ${owner}, not ${expectedOwner}`);
  }
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

/** Read a signed 128-bit little-endian integer. */
function readI128LE(data: Buffer, offset: number): bigint {
  const lo = data.readBigUInt64LE(offset);
  const hi = data.readBigUInt64LE(offset + 8);
  const unsigned = (hi << 64n) | lo;
  return unsigned >= 1n << 127n ? unsigned - (1n << 128n) : unsigned;
}

const POOL = {
  poolBump: 8,
  index: 9,
  creator: 11,
  baseMint: 43,
  quoteMint: 75,
  lpMint: 107,
  poolBaseTokenAccount: 139,
  poolQuoteTokenAccount: 171,
  lpSupply: 203,
  coinCreator: 211,
  isMayhemMode: 243,
  isCashbackCoin: 244,
  virtualQuoteReserves: 245,
} as const;

export interface PumpPoolRaw {
  index: number;
  creator: string;
  baseMint: string;
  quoteMint: string;
  lpMint: string;
  poolBaseTokenAccount: string;
  poolQuoteTokenAccount: string;
  lpSupply: bigint;
  coinCreator: string;
  isMayhemMode: boolean;
  isCashbackCoin: boolean;
  virtualQuoteReserves: bigint;
}

/**
 * Sanity ceiling for `virtual_quote_reserves`: far more lamports than exist.
 * A value beyond it means we are reading something that is not that field.
 */
const MAX_PLAUSIBLE_VIRTUAL_RESERVES = 1_000_000_000n * 1_000_000_000n; // 1e9 SOL

export function decodePumpPool(data: Buffer, owner: string): PumpPoolRaw {
  requireOwnerAndDiscriminator(
    data,
    owner,
    PUMP_SWAP_PROGRAM_ID,
    PUMP_POOL_DISCRIMINATOR,
    "PumpSwap Pool",
  );
  if (data.length < PUMP_POOL_MIN_LEN) {
    throw new DecodeError(
      "PumpSwap Pool",
      `account is ${data.length} bytes, need at least ${PUMP_POOL_MIN_LEN}`,
    );
  }

  let virtualQuoteReserves = 0n;
  if (data.length >= PUMP_POOL_LEN_WITH_VIRTUAL) {
    const v = readI128LE(data, POOL.virtualQuoteReserves);
    if (v > MAX_PLAUSIBLE_VIRTUAL_RESERVES || v < -MAX_PLAUSIBLE_VIRTUAL_RESERVES) {
      throw new DecodeError(
        "PumpSwap Pool",
        `virtual_quote_reserves=${v} is implausible; the layout may have changed`,
      );
    }
    virtualQuoteReserves = v;
  }

  return {
    index: data.readUInt16LE(POOL.index),
    creator: pubkey(data, POOL.creator),
    baseMint: pubkey(data, POOL.baseMint),
    quoteMint: pubkey(data, POOL.quoteMint),
    lpMint: pubkey(data, POOL.lpMint),
    poolBaseTokenAccount: pubkey(data, POOL.poolBaseTokenAccount),
    poolQuoteTokenAccount: pubkey(data, POOL.poolQuoteTokenAccount),
    lpSupply: data.readBigUInt64LE(POOL.lpSupply),
    coinCreator: pubkey(data, POOL.coinCreator),
    isMayhemMode: data.readUInt8(POOL.isMayhemMode) !== 0,
    isCashbackCoin: data.readUInt8(POOL.isCashbackCoin) !== 0,
    virtualQuoteReserves,
  };
}

const GLOBAL = {
  admin: 8,
  lpFeeBasisPoints: 40,
  protocolFeeBasisPoints: 48,
  disableFlags: 56,
  protocolFeeRecipients: 57,
  coinCreatorFeeBasisPoints: 313,
} as const;

export function decodePumpGlobalConfig(
  address: string,
  data: Buffer,
  owner: string,
): PumpGlobalConfig {
  requireOwnerAndDiscriminator(
    data,
    owner,
    PUMP_SWAP_PROGRAM_ID,
    PUMP_GLOBAL_CONFIG_DISCRIMINATOR,
    "PumpSwap GlobalConfig",
  );
  if (data.length < GLOBAL.coinCreatorFeeBasisPoints + 8) {
    throw new DecodeError("PumpSwap GlobalConfig", `account is ${data.length} bytes`);
  }
  const protocolFeeRecipients: string[] = [];
  for (let i = 0; i < 8; i++) {
    protocolFeeRecipients.push(pubkey(data, GLOBAL.protocolFeeRecipients + i * 32));
  }
  return {
    address,
    lpFeeBasisPoints: data.readBigUInt64LE(GLOBAL.lpFeeBasisPoints),
    protocolFeeBasisPoints: data.readBigUInt64LE(GLOBAL.protocolFeeBasisPoints),
    coinCreatorFeeBasisPoints: data.readBigUInt64LE(GLOBAL.coinCreatorFeeBasisPoints),
    disableFlags: data.readUInt8(GLOBAL.disableFlags),
    protocolFeeRecipients,
  };
}

/**
 * `FeeConfig` from the pump fee program.
 *
 *   bump u8 | admin pubkey | flat_fees Fees | fee_tiers Vec<FeeTier>
 *   | stable_fee_tiers Vec<FeeTier>
 *
 * with `Fees = { lp u64, protocol u64, creator u64 }` and
 * `FeeTier = { market_cap_lamports_threshold u128, fees Fees }`.
 */
export function decodePumpFeeConfig(
  address: string,
  data: Buffer,
  owner: string,
): PumpFeeConfig {
  requireOwnerAndDiscriminator(
    data,
    owner,
    PUMP_FEE_PROGRAM_ID,
    PUMP_FEE_CONFIG_DISCRIMINATOR,
    "pump FeeConfig",
  );
  let o = 8;
  o += 1; // bump
  o += 32; // admin

  const readFees = (): PumpFees => {
    if (o + 24 > data.length) throw new DecodeError("pump FeeConfig", "truncated Fees");
    const fees: PumpFees = {
      lpFeeBps: data.readBigUInt64LE(o),
      protocolFeeBps: data.readBigUInt64LE(o + 8),
      creatorFeeBps: data.readBigUInt64LE(o + 16),
    };
    o += 24;
    return fees;
  };

  const readU128 = (): bigint => {
    if (o + 16 > data.length) throw new DecodeError("pump FeeConfig", "truncated u128");
    const lo = data.readBigUInt64LE(o);
    const hi = data.readBigUInt64LE(o + 8);
    o += 16;
    return (hi << 64n) | lo;
  };

  const readTiers = (): PumpFeeTier[] => {
    if (o + 4 > data.length) throw new DecodeError("pump FeeConfig", "truncated vec length");
    const n = data.readUInt32LE(o);
    o += 4;
    if (n > 1024) throw new DecodeError("pump FeeConfig", `implausible tier count ${n}`);
    const tiers: PumpFeeTier[] = [];
    for (let i = 0; i < n; i++) {
      const marketCapLamportsThreshold = readU128();
      tiers.push({ marketCapLamportsThreshold, fees: readFees() });
    }
    return tiers;
  };

  const flatFees = readFees();
  const feeTiers = readTiers();
  const stableFeeTiers = readTiers();

  // The tier ladder must be non-decreasing in threshold for the official
  // selection algorithm to make sense. If it is not, we are misreading it.
  for (let i = 1; i < feeTiers.length; i++) {
    if (feeTiers[i]!.marketCapLamportsThreshold < feeTiers[i - 1]!.marketCapLamportsThreshold) {
      throw new DecodeError("pump FeeConfig", "fee tiers are not sorted by market cap");
    }
  }

  return { address, flatFees, feeTiers, stableFeeTiers };
}

export function buildPumpSwapPoolData(args: {
  pool: PumpPoolRaw;
  globalConfig: PumpGlobalConfig;
  feeConfig: PumpFeeConfig | null;
  isCanonicalPumpPool: boolean;
  baseTokenProgram: string;
  quoteTokenProgram: string;
  poolBaseAmount: bigint;
  poolQuoteAmount: bigint;
}): PumpSwapPoolData {
  const { pool } = args;
  return {
    creator: pool.creator,
    coinCreator: pool.coinCreator,
    baseMint: pool.baseMint,
    quoteMint: pool.quoteMint,
    poolBaseTokenAccount: pool.poolBaseTokenAccount,
    poolQuoteTokenAccount: pool.poolQuoteTokenAccount,
    baseTokenProgram: args.baseTokenProgram,
    quoteTokenProgram: args.quoteTokenProgram,
    isMayhemMode: pool.isMayhemMode,
    virtualQuoteReserves: pool.virtualQuoteReserves,
    poolBaseAmount: args.poolBaseAmount,
    poolQuoteAmount: args.poolQuoteAmount,
    isCanonicalPumpPool: args.isCanonicalPumpPool,
    globalConfig: args.globalConfig,
    feeConfig: args.feeConfig,
  };
}
