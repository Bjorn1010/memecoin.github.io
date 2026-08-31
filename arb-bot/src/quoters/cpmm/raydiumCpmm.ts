/**
 * Exact quoter for Raydium CP-Swap (constant product), program
 * `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C`.
 *
 * REFERENCE (read 2026-08-31, see ASSUMPTIONS.md #RAY-1..#RAY-5):
 *   github.com/raydium-io/raydium-cp-swap @ master
 *     programs/cp-swap/src/instructions/swap_base_input.rs
 *     programs/cp-swap/src/curve/calculator.rs      (CurveCalculator::swap_base_input)
 *     programs/cp-swap/src/curve/constant_product.rs (swap_base_input_without_fees)
 *     programs/cp-swap/src/curve/fees.rs             (ceil_div / floor_div)
 *     programs/cp-swap/src/states/pool.rs            (vault_amount_without_fee, ...)
 *   The IDL published on-chain by the program itself is v0.2.0 and its
 *   `AmmConfig` / `PoolState` field lists match that source field-for-field,
 *   so the deployed program is not ahead of the source we replicate.
 *
 * The two subtleties that a naive x*y=k implementation gets wrong:
 *  1. the reserves are NOT the vault balances — accrued protocol, fund and
 *     creator fees still sit in the vaults and are excluded from the curve
 *     (`PoolState::vault_amount_without_fee`);
 *  2. the trade fee is a CEILING division, and the creator fee is split off the
 *     total with a FLOOR division, so fees round against the trader twice.
 */
import { ceilDiv, floorDiv, mulDivFloor } from "../../util/bigintMath.js";
import type {
  MintState,
  PoolSnapshot,
  QuoteResult,
  SwapDirection,
} from "../../types.js";
import { UnquotableError, type QuoteContext, type Quoter } from "../Quoter.js";
import { transferFeeOn } from "../../feed/decoder/token2022.js";

/** `FEE_RATE_DENOMINATOR_VALUE` in curve/fees.rs. */
export const RAY_FEE_RATE_DENOMINATOR = 1_000_000n;

/** `PoolStatusBitIndex::Swap` is bit 2; the bit being SET disables swapping. */
const STATUS_BIT_SWAP = 4;

/** `CreatorFeeOn` discriminants, states/pool.rs. */
export const CREATOR_FEE_ON_BOTH = 0;
export const CREATOR_FEE_ON_TOKEN_0 = 1;
export const CREATOR_FEE_ON_TOKEN_1 = 2;

export interface RaydiumCpmmAmmConfig {
  address: string;
  tradeFeeRate: bigint;
  protocolFeeRate: bigint;
  fundFeeRate: bigint;
  creatorFeeRate: bigint;
}

/** Everything decoded from PoolState + the two vault token accounts. */
export interface RaydiumCpmmPoolData {
  ammConfig: RaydiumCpmmAmmConfig;
  token0Mint: string;
  token1Mint: string;
  token0Vault: string;
  token1Vault: string;
  token0Program: string;
  token1Program: string;
  observationKey: string;
  status: number;
  openTime: bigint;
  creatorFeeOn: number;
  enableCreatorFee: boolean;
  /** Raw SPL balances of the two vault token accounts. */
  vault0Amount: bigint;
  vault1Amount: bigint;
  /** Fee counters held inside the vaults, excluded from the curve. */
  protocolFeesToken0: bigint;
  protocolFeesToken1: bigint;
  fundFeesToken0: bigint;
  fundFeesToken1: bigint;
  creatorFeesToken0: bigint;
  creatorFeesToken1: bigint;
}

function asData(pool: PoolSnapshot): RaydiumCpmmPoolData {
  if (pool.family !== "raydium-cpmm") {
    throw new UnquotableError("wrong-family", `expected raydium-cpmm, got ${pool.family}`);
  }
  return pool.data as RaydiumCpmmPoolData;
}

/** `PoolState::vault_amount_without_fee` — the reserves the curve actually uses. */
export function raydiumEffectiveReserves(d: RaydiumCpmmPoolData): {
  reserve0: bigint;
  reserve1: bigint;
} {
  const fees0 = d.protocolFeesToken0 + d.fundFeesToken0 + d.creatorFeesToken0;
  const fees1 = d.protocolFeesToken1 + d.fundFeesToken1 + d.creatorFeesToken1;
  if (fees0 > d.vault0Amount || fees1 > d.vault1Amount) {
    // The program returns InsufficientVault here; there is no valid quote.
    throw new UnquotableError("empty-reserves", "accrued fees exceed vault balance");
  }
  return { reserve0: d.vault0Amount - fees0, reserve1: d.vault1Amount - fees1 };
}

/** `PoolState::is_creator_fee_on_input`. `zeroForOne` = input is token_0. */
export function raydiumIsCreatorFeeOnInput(creatorFeeOn: number, zeroForOne: boolean): boolean {
  switch (creatorFeeOn) {
    case CREATOR_FEE_ON_BOTH:
      return true;
    case CREATOR_FEE_ON_TOKEN_0:
      return zeroForOne;
    case CREATOR_FEE_ON_TOKEN_1:
      return !zeroForOne;
    default:
      throw new UnquotableError("pool-disabled", `unknown creator_fee_on=${creatorFeeOn}`);
  }
}

export interface RaydiumSwapResult {
  /** Amount transferred out of the pool vault (before output transfer fee). */
  outputAmount: bigint;
  tradeFee: bigint;
  protocolFee: bigint;
  fundFee: bigint;
  creatorFee: bigint;
  inputAmountLessFees: bigint;
}

/**
 * `CurveCalculator::swap_base_input`, transcribed literally.
 *
 * `inputAmount` here is `actual_amount_in`, i.e. already net of any Token-2022
 * transfer fee on the input mint.
 */
export function raydiumSwapBaseInput(args: {
  inputAmount: bigint;
  inputVaultAmount: bigint;
  outputVaultAmount: bigint;
  tradeFeeRate: bigint;
  creatorFeeRate: bigint;
  protocolFeeRate: bigint;
  fundFeeRate: bigint;
  isCreatorFeeOnInput: boolean;
}): RaydiumSwapResult {
  const {
    inputAmount,
    inputVaultAmount,
    outputVaultAmount,
    tradeFeeRate,
    creatorFeeRate,
    protocolFeeRate,
    fundFeeRate,
    isCreatorFeeOnInput,
  } = args;

  let creatorFee = 0n;
  let tradeFee: bigint;
  let inputAmountLessFees: bigint;

  if (isCreatorFeeOnInput) {
    // Fees::trading_fee -> ceil_div
    const totalFee = ceilDiv(inputAmount * (tradeFeeRate + creatorFeeRate), RAY_FEE_RATE_DENOMINATOR);
    // Fees::split_creator_fee -> floor_div
    creatorFee =
      tradeFeeRate + creatorFeeRate === 0n
        ? 0n
        : floorDiv(totalFee * creatorFeeRate, tradeFeeRate + creatorFeeRate);
    tradeFee = totalFee - creatorFee;
    if (totalFee > inputAmount) {
      throw new UnquotableError("amount-out-of-range", "fees exceed input amount");
    }
    inputAmountLessFees = inputAmount - totalFee;
  } else {
    tradeFee = ceilDiv(inputAmount * tradeFeeRate, RAY_FEE_RATE_DENOMINATOR);
    if (tradeFee > inputAmount) {
      throw new UnquotableError("amount-out-of-range", "fees exceed input amount");
    }
    inputAmountLessFees = inputAmount - tradeFee;
  }

  const protocolFee = floorDiv(tradeFee * protocolFeeRate, RAY_FEE_RATE_DENOMINATOR);
  const fundFee = floorDiv(tradeFee * fundFeeRate, RAY_FEE_RATE_DENOMINATOR);

  // ConstantProductCurve::swap_base_input_without_fees — floor division.
  const denominator = inputVaultAmount + inputAmountLessFees;
  if (denominator === 0n) {
    throw new UnquotableError("empty-reserves", "zero denominator");
  }
  const outputAmountSwapped = floorDiv(inputAmountLessFees * outputVaultAmount, denominator);

  let outputAmount: bigint;
  if (isCreatorFeeOnInput) {
    outputAmount = outputAmountSwapped;
  } else {
    // Fees::creator_fee -> ceil_div
    creatorFee = ceilDiv(outputAmountSwapped * creatorFeeRate, RAY_FEE_RATE_DENOMINATOR);
    if (creatorFee > outputAmountSwapped) {
      throw new UnquotableError("amount-out-of-range", "creator fee exceeds output");
    }
    outputAmount = outputAmountSwapped - creatorFee;
  }

  if (outputAmountSwapped > outputVaultAmount) {
    throw new UnquotableError("amount-out-of-range", "output exceeds vault");
  }

  return { outputAmount, tradeFee, protocolFee, fundFee, creatorFee, inputAmountLessFees };
}

export class RaydiumCpmmQuoter implements Quoter {
  readonly family = "raydium-cpmm" as const;

  quote(
    pool: PoolSnapshot,
    amountIn: bigint,
    direction: SwapDirection,
    ctx: QuoteContext,
  ): QuoteResult {
    const d = asData(pool);

    if ((d.status & STATUS_BIT_SWAP) !== 0) {
      throw new UnquotableError("pool-disabled", `swap disabled by status=${d.status}`);
    }
    if (BigInt(ctx.blockTimeSeconds) < d.openTime) {
      throw new UnquotableError("pool-not-open", `open_time=${d.openTime} not reached`);
    }
    if (amountIn <= 0n) {
      throw new UnquotableError("amount-out-of-range", "amountIn must be > 0");
    }

    const zeroForOne = direction.inputMint === d.token0Mint;
    if (!zeroForOne && direction.inputMint !== d.token1Mint) {
      throw new UnquotableError("mint-not-in-pool", `${direction.inputMint} not in pool`);
    }
    const expectedOut = zeroForOne ? d.token1Mint : d.token0Mint;
    if (direction.outputMint !== expectedOut) {
      throw new UnquotableError("mint-not-in-pool", `output mint mismatch`);
    }

    const inputMint = requireMint(ctx, direction.inputMint);
    const outputMint = requireMint(ctx, direction.outputMint);

    // swap_base_input.rs: actual_amount_in = amount_in - transfer_fee(input_mint)
    const inputTransferFee = transferFeeOn(inputMint, amountIn);
    const actualAmountIn = amountIn - inputTransferFee;
    if (actualAmountIn <= 0n) {
      throw new UnquotableError("amount-out-of-range", "input transfer fee consumes the input");
    }

    const { reserve0, reserve1 } = raydiumEffectiveReserves(d);
    const reserveIn = zeroForOne ? reserve0 : reserve1;
    const reserveOut = zeroForOne ? reserve1 : reserve0;
    if (reserveIn === 0n || reserveOut === 0n) {
      throw new UnquotableError("empty-reserves", "a side of the pool is empty");
    }

    const creatorFeeRate = d.enableCreatorFee ? d.ammConfig.creatorFeeRate : 0n;
    const isCreatorFeeOnInput = raydiumIsCreatorFeeOnInput(d.creatorFeeOn, zeroForOne);

    const r = raydiumSwapBaseInput({
      inputAmount: actualAmountIn,
      inputVaultAmount: reserveIn,
      outputVaultAmount: reserveOut,
      tradeFeeRate: d.ammConfig.tradeFeeRate,
      creatorFeeRate,
      protocolFeeRate: d.ammConfig.protocolFeeRate,
      fundFeeRate: d.ammConfig.fundFeeRate,
      isCreatorFeeOnInput,
    });

    // The program credits the user `output_amount` minus the output mint's
    // transfer fee, and it is that net figure the slippage check compares.
    const outputTransferFee = transferFeeOn(outputMint, r.outputAmount);
    const amountReceived = r.outputAmount - outputTransferFee;
    if (amountReceived <= 0n) {
      throw new UnquotableError("amount-out-of-range", "output transfer fee consumes the output");
    }

    const feeInInput =
      inputTransferFee + (isCreatorFeeOnInput ? r.tradeFee + r.creatorFee : r.tradeFee);
    const feeInOutput = outputTransferFee + (isCreatorFeeOnInput ? 0n : r.creatorFee);

    return {
      family: this.family,
      poolId: pool.poolId,
      direction,
      amountIn,
      amountOut: amountReceived,
      fees: {
        inInputToken: feeInInput,
        inOutputToken: feeInOutput,
        breakdown: {
          tradeFee: r.tradeFee,
          protocolFee: r.protocolFee,
          fundFee: r.fundFee,
          creatorFee: r.creatorFee,
          inputTransferFee,
          outputTransferFee,
        },
      },
      reserveIn,
      reserveOut,
      slot: pool.slot,
      receivedAt: pool.receivedAt,
      exactness: "exact",
      maxAmountIn: this.maxAmountIn(pool, direction, ctx),
    };
  }

  /**
   * The curve itself never runs out (output asymptotes to the reserve), but a
   * quote whose size approaches the reserve is economically meaningless and
   * numerically fragile. We bound input at the input-side reserve, which the
   * program tolerates and beyond which price impact is ~100%.
   */
  maxAmountIn(pool: PoolSnapshot, direction: SwapDirection, _ctx: QuoteContext): bigint {
    const d = asData(pool);
    const zeroForOne = direction.inputMint === d.token0Mint;
    const { reserve0, reserve1 } = raydiumEffectiveReserves(d);
    return zeroForOne ? reserve0 : reserve1;
  }

  requiredAccounts(pool: PoolSnapshot): string[] {
    const d = asData(pool);
    return [pool.poolId, d.token0Vault, d.token1Vault];
  }
}

function requireMint(ctx: QuoteContext, mint: string): MintState {
  const m = ctx.mints.get(mint);
  if (!m) throw new UnquotableError("missing-input", `mint state missing for ${mint}`);
  return m;
}

/** Exported for the sizing module's analytic branch. */
export function raydiumTotalInputFeeRate(d: RaydiumCpmmPoolData, zeroForOne: boolean): bigint {
  const creatorFeeRate = d.enableCreatorFee ? d.ammConfig.creatorFeeRate : 0n;
  return raydiumIsCreatorFeeOnInput(d.creatorFeeOn, zeroForOne)
    ? d.ammConfig.tradeFeeRate + creatorFeeRate
    : d.ammConfig.tradeFeeRate;
}

/** Output-side fee rate (0 unless the creator fee is charged on the output). */
export function raydiumOutputFeeRate(d: RaydiumCpmmPoolData, zeroForOne: boolean): bigint {
  const creatorFeeRate = d.enableCreatorFee ? d.ammConfig.creatorFeeRate : 0n;
  return raydiumIsCreatorFeeOnInput(d.creatorFeeOn, zeroForOne) ? 0n : creatorFeeRate;
}

/** Convenience for tests and the sizing bracket. */
export { mulDivFloor };
