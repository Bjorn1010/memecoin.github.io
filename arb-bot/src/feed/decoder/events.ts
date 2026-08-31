/**
 * Program event decoding.
 *
 * Both venues emit an event on every swap that contains the pre-trade reserves,
 * the input amount and the exact output the program computed. That makes a real
 * executed transaction a perfect oracle for the quoters: no simulation, no
 * assumptions, just "given this state and this input, the program produced this
 * output — do we?" (§8B).
 *
 * Two emission styles are handled:
 *  - Anchor `emit!`, which writes `Program data: <base64>` to the logs;
 *  - Anchor `emit_cpi!`, which invokes the program itself with the event as
 *    instruction data, prefixed by Anchor's event CPI tag.
 */
import { bs58Decode, bs58Encode } from "./token2022.js";

/** Anchor's `EVENT_IX_TAG_LE`, the 8-byte prefix on every `emit_cpi!` payload. */
export const ANCHOR_EVENT_CPI_TAG = Buffer.from([228, 69, 165, 46, 81, 203, 154, 29]);

export const RAYDIUM_SWAP_EVENT_DISCRIMINATOR = Buffer.from([64, 198, 205, 232, 38, 8, 113, 226]);
export const PUMP_BUY_EVENT_DISCRIMINATOR = Buffer.from([103, 244, 82, 31, 44, 245, 119, 119]);
export const PUMP_SELL_EVENT_DISCRIMINATOR = Buffer.from([62, 47, 55, 10, 165, 3, 220, 42]);

/** Every `Program data:` payload in a transaction's logs, decoded from base64. */
export function eventPayloadsFromLogs(logs: readonly string[]): Buffer[] {
  const out: Buffer[] = [];
  for (const line of logs) {
    const marker = "Program data: ";
    const i = line.indexOf(marker);
    if (i < 0) continue;
    const b64 = line.slice(i + marker.length).trim();
    try {
      out.push(Buffer.from(b64, "base64"));
    } catch {
      // A malformed log line is not worth failing a whole validation run over.
    }
  }
  return out;
}

/**
 * Event payloads carried by `emit_cpi!` inner instructions.
 * `datas` are the raw instruction data buffers of inner instructions whose
 * program id is the emitting program.
 */
export function eventPayloadsFromCpi(datas: readonly Buffer[]): Buffer[] {
  const out: Buffer[] = [];
  for (const d of datas) {
    if (d.length < 16) continue;
    if (!d.subarray(0, 8).equals(ANCHOR_EVENT_CPI_TAG)) continue;
    out.push(d.subarray(8));
  }
  return out;
}

/** Base58 instruction data as returned by `getTransaction` in json encoding. */
export function decodeInstructionData(data: string): Buffer {
  return Buffer.from(bs58Decode(data));
}

// --- Raydium CP-Swap SwapEvent ---------------------------------------------

export interface RaydiumSwapEvent {
  poolId: string;
  inputVaultBefore: bigint;
  outputVaultBefore: bigint;
  inputAmount: bigint;
  outputAmount: bigint;
  inputTransferFee: bigint;
  outputTransferFee: bigint;
  baseInput: boolean;
  inputMint: string;
  outputMint: string;
  tradeFee: bigint;
  creatorFee: bigint;
  creatorFeeOnInput: boolean;
}

export function parseRaydiumSwapEvent(payload: Buffer): RaydiumSwapEvent | null {
  if (payload.length < 8 || !payload.subarray(0, 8).equals(RAYDIUM_SWAP_EVENT_DISCRIMINATOR)) {
    return null;
  }
  // 8 disc + 32 pool + 6*8 + 1 + 32 + 32 + 8 + 8 + 1 = 170
  if (payload.length < 170) return null;
  let o = 8;
  const poolId = bs58Encode(payload.subarray(o, o + 32));
  o += 32;
  const u64 = (): bigint => {
    const v = payload.readBigUInt64LE(o);
    o += 8;
    return v;
  };
  const inputVaultBefore = u64();
  const outputVaultBefore = u64();
  const inputAmount = u64();
  const outputAmount = u64();
  const inputTransferFee = u64();
  const outputTransferFee = u64();
  const baseInput = payload.readUInt8(o) !== 0;
  o += 1;
  const inputMint = bs58Encode(payload.subarray(o, o + 32));
  o += 32;
  const outputMint = bs58Encode(payload.subarray(o, o + 32));
  o += 32;
  const tradeFee = u64();
  const creatorFee = u64();
  const creatorFeeOnInput = payload.readUInt8(o) !== 0;
  return {
    poolId,
    inputVaultBefore,
    outputVaultBefore,
    inputAmount,
    outputAmount,
    inputTransferFee,
    outputTransferFee,
    baseInput,
    inputMint,
    outputMint,
    tradeFee,
    creatorFee,
    creatorFeeOnInput,
  };
}

// --- PumpSwap SellEvent / BuyEvent -----------------------------------------

export interface PumpSellEvent {
  kind: "sell";
  baseAmountIn: bigint;
  poolBaseTokenReserves: bigint;
  poolQuoteTokenReserves: bigint;
  quoteAmountOut: bigint;
  lpFeeBasisPoints: bigint;
  lpFee: bigint;
  protocolFeeBasisPoints: bigint;
  protocolFee: bigint;
  userQuoteAmountOut: bigint;
  pool: string;
  coinCreator: string;
  coinCreatorFeeBasisPoints: bigint;
  coinCreatorFee: bigint;
  /**
   * Extra fee legs present in the deployed program but NOT modelled by
   * pump.fun's published quote helpers. If either is non-zero on a pool, our
   * quote would be wrong and the pool must not be traded.
   */
  cashbackFeeBasisPoints: bigint;
  cashback: bigint;
  buybackFeeBasisPoints: bigint;
  buybackFee: bigint;
}

/**
 * SellEvent layout, in declaration order:
 *   timestamp i64 | base_amount_in u64 | min_quote_amount_out u64
 *   | user_base_token_reserves u64 | user_quote_token_reserves u64
 *   | pool_base_token_reserves u64 | pool_quote_token_reserves u64
 *   | quote_amount_out u64 | lp_fee_basis_points u64 | lp_fee u64
 *   | protocol_fee_basis_points u64 | protocol_fee u64
 *   | quote_amount_out_without_lp_fee u64 | user_quote_amount_out u64
 *   | pool pk | user pk | user_base_token_account pk
 *   | user_quote_token_account pk | protocol_fee_recipient pk
 *   | protocol_fee_recipient_token_account pk | coin_creator pk
 *   | coin_creator_fee_basis_points u64 | coin_creator_fee u64
 *   | cashback_fee_basis_points u64 | cashback u64
 *   | buyback_fee_basis_points u64 | buyback_fee u64
 */
export function parsePumpSellEvent(payload: Buffer): PumpSellEvent | null {
  if (payload.length < 8 || !payload.subarray(0, 8).equals(PUMP_SELL_EVENT_DISCRIMINATOR)) {
    return null;
  }
  let o = 8;
  const u64 = (): bigint => {
    const v = payload.readBigUInt64LE(o);
    o += 8;
    return v;
  };
  const pk = (): string => {
    const v = bs58Encode(payload.subarray(o, o + 32));
    o += 32;
    return v;
  };
  const need = 8 + 8 * 14 + 32 * 7 + 8 * 6;
  if (payload.length < need) return null;

  o += 8; // timestamp
  const baseAmountIn = u64();
  o += 8; // min_quote_amount_out
  o += 8; // user_base_token_reserves
  o += 8; // user_quote_token_reserves
  const poolBaseTokenReserves = u64();
  const poolQuoteTokenReserves = u64();
  const quoteAmountOut = u64();
  const lpFeeBasisPoints = u64();
  const lpFee = u64();
  const protocolFeeBasisPoints = u64();
  const protocolFee = u64();
  o += 8; // quote_amount_out_without_lp_fee
  const userQuoteAmountOut = u64();
  const pool = pk();
  pk(); // user
  pk(); // user_base_token_account
  pk(); // user_quote_token_account
  pk(); // protocol_fee_recipient
  pk(); // protocol_fee_recipient_token_account
  const coinCreator = pk();
  const coinCreatorFeeBasisPoints = u64();
  const coinCreatorFee = u64();
  const cashbackFeeBasisPoints = u64();
  const cashback = u64();
  const buybackFeeBasisPoints = u64();
  const buybackFee = u64();

  return {
    kind: "sell",
    baseAmountIn,
    poolBaseTokenReserves,
    poolQuoteTokenReserves,
    quoteAmountOut,
    lpFeeBasisPoints,
    lpFee,
    protocolFeeBasisPoints,
    protocolFee,
    userQuoteAmountOut,
    pool,
    coinCreator,
    coinCreatorFeeBasisPoints,
    coinCreatorFee,
    cashbackFeeBasisPoints,
    cashback,
    buybackFeeBasisPoints,
    buybackFee,
  };
}
