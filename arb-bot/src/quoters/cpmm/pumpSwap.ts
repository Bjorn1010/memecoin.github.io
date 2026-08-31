/**
 * Exact quoter for PumpSwap (pump.fun AMM), program
 * `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`.
 *
 * REFERENCES (read 2026-08-31, see ASSUMPTIONS.md #PS-1..#PS-6):
 *  - The program's own Anchor IDL, fetched from its on-chain IDL account
 *    (`5fLnXNNoZcZt9Qku6HARM3un3Ttm2cGsR7gN9Zp1R7h3`) — authoritative for
 *    account layouts, instruction discriminators and account ordering.
 *  - `@pump-fun/pump-swap-sdk` 1.19.0 TypeScript sources (`src/sdk/buy.ts`,
 *    `sell.ts`, `fees.ts`, `util.ts`, `pda.ts`) — pump.fun's own reference
 *    implementation of the swap math. Transcribed literally below.
 *  - pump-fun/pump-public-docs `docs/FEE_PROGRAM_README.md` — the official
 *    specification of the dynamic fee tiers and market-cap formula.
 *
 * ECONOMIC NOTE, measured from the live `FeeConfig`
 * (`5PHirr8joyTMp9JMm6nW7hNDVyEYdkzDqazxPD7RaTjx`) on 2026-08-31: canonical
 * pump pools charge a TOTAL of 125 bps below a 420 SOL market cap, decaying to
 * 30 bps above ~98 000 SOL. Non-canonical pools pay the flat 30 bps. The
 * cheapest possible PumpSwap round leg is therefore 30 bps and the low-cap
 * long tail costs 125 bps per leg — this dominates the arbitrage economics and
 * is why the bot reads the tiers live instead of assuming a constant.
 */
import { ceilDiv, floorDiv } from "../../util/bigintMath.js";
import type { PoolSnapshot, QuoteResult, SwapDirection } from "../../types.js";
import { UnquotableError, type QuoteContext, type Quoter } from "../Quoter.js";

export const PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P";
export const PUMP_AMM_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA";
export const PUMP_FEE_PROGRAM_ID = "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ";
export const SYSTEM_PROGRAM_ID = "11111111111111111111111111111111";

/** `disable_flags` bits on GlobalConfig, from the IDL docs. */
const DISABLE_BUY = 1 << 3;
const DISABLE_SELL = 1 << 4;

export const BPS_DENOMINATOR = 10_000n;

export interface PumpFees {
  lpFeeBps: bigint;
  protocolFeeBps: bigint;
  creatorFeeBps: bigint;
}

export interface PumpFeeTier {
  marketCapLamportsThreshold: bigint;
  fees: PumpFees;
}

export interface PumpFeeConfig {
  address: string;
  flatFees: PumpFees;
  feeTiers: PumpFeeTier[];
  stableFeeTiers: PumpFeeTier[];
}

export interface PumpGlobalConfig {
  address: string;
  lpFeeBasisPoints: bigint;
  protocolFeeBasisPoints: bigint;
  coinCreatorFeeBasisPoints: bigint;
  disableFlags: number;
  protocolFeeRecipients: string[];
}

export interface PumpSwapPoolData {
  creator: string;
  coinCreator: string;
  baseMint: string;
  quoteMint: string;
  poolBaseTokenAccount: string;
  poolQuoteTokenAccount: string;
  baseTokenProgram: string;
  quoteTokenProgram: string;
  isMayhemMode: boolean;
  /**
   * `Pool.virtual_quote_reserves` (i128). The on-chain IDL account for the
   * program does not yet list this field but the deployed pool accounts are
   * 301 bytes — larger than the 245 the older layout needs — and pump's own
   * SDK reads it at this offset. Anchor zero-initialises reserve space, so a
   * program without the field yields 0, which is exactly the SDK's default.
   */
  virtualQuoteReserves: bigint;
  /** Live SPL balances of the two pool token accounts. */
  poolBaseAmount: bigint;
  poolQuoteAmount: bigint;
  /**
   * `isPumpPool(baseMint, pool.creator)` = `pool.creator == PDA(["pool-authority",
   * baseMint], PUMP_PROGRAM_ID)`. Precomputed at pool registration so the
   * quoter stays a pure function (PDA derivation needs sha256).
   */
  isCanonicalPumpPool: boolean;
  globalConfig: PumpGlobalConfig;
  feeConfig: PumpFeeConfig | null;
}

function asData(pool: PoolSnapshot): PumpSwapPoolData {
  if (pool.family !== "pump-swap") {
    throw new UnquotableError("wrong-family", `expected pump-swap, got ${pool.family}`);
  }
  return pool.data as PumpSwapPoolData;
}

/** `util.ts::fee` — ceiling division, NOT floor (the buy.ts comment is wrong). */
export function pumpFee(amount: bigint, basisPoints: bigint): bigint {
  if (basisPoints === 0n || amount === 0n) return 0n;
  return ceilDiv(amount * basisPoints, BPS_DENOMINATOR);
}

/** `util.ts::poolMarketCap`. */
export function pumpPoolMarketCap(args: {
  baseMintSupply: bigint;
  baseReserve: bigint;
  quoteReserve: bigint;
}): bigint {
  if (args.baseReserve === 0n) {
    throw new UnquotableError("empty-reserves", "base reserve is zero");
  }
  return floorDiv(args.quoteReserve * args.baseMintSupply, args.baseReserve);
}

/** `fees.ts::calculateFeeTier`, transcribed literally including the fallbacks. */
export function calculateFeeTier(feeTiers: readonly PumpFeeTier[], marketCap: bigint): PumpFees {
  const firstTier = feeTiers[0];
  if (!firstTier) {
    throw new UnquotableError("missing-input", "fee config has no tiers");
  }
  if (marketCap < firstTier.marketCapLamportsThreshold) {
    return firstTier.fees;
  }
  for (let i = feeTiers.length - 1; i >= 0; i--) {
    const tier = feeTiers[i]!;
    if (marketCap >= tier.marketCapLamportsThreshold) return tier.fees;
  }
  return firstTier.fees;
}

/** `fees.ts::computeFeesBps`. */
export function pumpComputeFeesBps(args: {
  globalConfig: PumpGlobalConfig;
  feeConfig: PumpFeeConfig | null;
  isCanonicalPumpPool: boolean;
  baseMintSupply: bigint;
  baseReserve: bigint;
  /** Must already include virtualQuoteReserves, as the SDK does. */
  quoteReserve: bigint;
}): PumpFees {
  const { feeConfig } = args;
  if (feeConfig != null) {
    if (!args.isCanonicalPumpPool) return feeConfig.flatFees;
    const marketCap = pumpPoolMarketCap({
      baseMintSupply: args.baseMintSupply,
      baseReserve: args.baseReserve,
      quoteReserve: args.quoteReserve,
    });
    return calculateFeeTier(feeConfig.feeTiers, marketCap);
  }
  return {
    lpFeeBps: args.globalConfig.lpFeeBasisPoints,
    protocolFeeBps: args.globalConfig.protocolFeeBasisPoints,
    creatorFeeBps: args.globalConfig.coinCreatorFeeBasisPoints,
  };
}

export interface PumpSellResult {
  quoteAmountOut: bigint;
  lpFee: bigint;
  protocolFee: bigint;
  coinCreatorFee: bigint;
  finalQuote: bigint;
  fees: PumpFees;
}

/** `sell.ts::sellBaseInput` — base in, quote out. */
export function pumpSellBaseInput(args: {
  base: bigint;
  baseReserve: bigint;
  quoteReserve: bigint;
  virtualQuoteReserves: bigint;
  baseMintSupply: bigint;
  coinCreatorIsDefault: boolean;
  globalConfig: PumpGlobalConfig;
  feeConfig: PumpFeeConfig | null;
  isCanonicalPumpPool: boolean;
}): PumpSellResult {
  if (args.baseReserve === 0n || args.quoteReserve === 0n) {
    throw new UnquotableError("empty-reserves", "baseReserve or quoteReserve is zero");
  }
  const effectiveQuoteReserve = args.quoteReserve + args.virtualQuoteReserves;
  if (effectiveQuoteReserve <= 0n) {
    throw new UnquotableError("empty-reserves", "effective quote reserve is not positive");
  }

  const quoteAmountOut = floorDiv(effectiveQuoteReserve * args.base, args.baseReserve + args.base);

  const fees = pumpComputeFeesBps({
    globalConfig: args.globalConfig,
    feeConfig: args.feeConfig,
    isCanonicalPumpPool: args.isCanonicalPumpPool,
    baseMintSupply: args.baseMintSupply,
    baseReserve: args.baseReserve,
    quoteReserve: effectiveQuoteReserve,
  });

  const lpFee = pumpFee(quoteAmountOut, fees.lpFeeBps);
  const protocolFee = pumpFee(quoteAmountOut, fees.protocolFeeBps);
  const coinCreatorFee = args.coinCreatorIsDefault
    ? 0n
    : pumpFee(quoteAmountOut, fees.creatorFeeBps);

  // The program can only pay out of real reserves.
  if (args.quoteReserve < quoteAmountOut - lpFee) {
    throw new UnquotableError(
      "amount-out-of-range",
      "insufficient real quote reserves to cover the sell output",
    );
  }

  const finalQuote = quoteAmountOut - lpFee - protocolFee - coinCreatorFee;
  if (finalQuote < 0n) {
    throw new UnquotableError("amount-out-of-range", "fees exceed total output");
  }

  return { quoteAmountOut, lpFee, protocolFee, coinCreatorFee, finalQuote, fees };
}

export interface PumpBuyResult {
  baseAmountOut: bigint;
  effectiveQuote: bigint;
  lpFee: bigint;
  protocolFee: bigint;
  coinCreatorFee: bigint;
  fees: PumpFees;
}

/** `buy.ts::buyQuoteInput` — quote in, base out. Matches `buy_exact_quote_in`. */
export function pumpBuyQuoteInput(args: {
  quote: bigint;
  baseReserve: bigint;
  quoteReserve: bigint;
  virtualQuoteReserves: bigint;
  baseMintSupply: bigint;
  coinCreatorIsDefault: boolean;
  globalConfig: PumpGlobalConfig;
  feeConfig: PumpFeeConfig | null;
  isCanonicalPumpPool: boolean;
}): PumpBuyResult {
  if (args.baseReserve === 0n || args.quoteReserve === 0n) {
    throw new UnquotableError("empty-reserves", "baseReserve or quoteReserve is zero");
  }
  const effectiveQuoteReserve = args.quoteReserve + args.virtualQuoteReserves;
  if (effectiveQuoteReserve <= 0n) {
    throw new UnquotableError("empty-reserves", "effective quote reserve is not positive");
  }

  const fees = pumpComputeFeesBps({
    globalConfig: args.globalConfig,
    feeConfig: args.feeConfig,
    isCanonicalPumpPool: args.isCanonicalPumpPool,
    baseMintSupply: args.baseMintSupply,
    baseReserve: args.baseReserve,
    quoteReserve: effectiveQuoteReserve,
  });

  const creatorBps = args.coinCreatorIsDefault ? 0n : fees.creatorFeeBps;
  const totalFeeBps = fees.lpFeeBps + fees.protocolFeeBps + creatorBps;
  const denominator = BPS_DENOMINATOR + totalFeeBps;

  let effectiveQuote = floorDiv(args.quote * BPS_DENOMINATOR, denominator);

  const lpFee = pumpFee(effectiveQuote, fees.lpFeeBps);
  const protocolFee = pumpFee(effectiveQuote, fees.protocolFeeBps);
  const coinCreatorFee = pumpFee(effectiveQuote, creatorBps);
  const totalWithFees = effectiveQuote + lpFee + protocolFee + coinCreatorFee;
  if (totalWithFees > args.quote) {
    effectiveQuote = effectiveQuote - (totalWithFees - args.quote);
  }

  // buy.ts subtracts one base unit before applying the curve. Reproduced
  // exactly: dropping it would over-quote every single buy by a hair.
  const inputAmount = effectiveQuote - 1n;
  if (inputAmount <= 0n) {
    throw new UnquotableError("amount-out-of-range", "quote amount too small after fees");
  }

  const baseAmountOut = floorDiv(args.baseReserve * inputAmount, effectiveQuoteReserve + inputAmount);
  if (baseAmountOut <= 0n) {
    throw new UnquotableError("amount-out-of-range", "buy would receive zero base tokens");
  }

  return { baseAmountOut, effectiveQuote, lpFee, protocolFee, coinCreatorFee, fees };
}

export interface PumpBuyBaseResult {
  /** Total quote the user must provide, fees included. */
  totalQuoteIn: bigint;
  quoteAmountIn: bigint;
  lpFee: bigint;
  protocolFee: bigint;
  coinCreatorFee: bigint;
  fees: PumpFees;
}

/**
 * `buy.ts::buyBaseInput` — how much quote is needed for an EXACT base output.
 *
 * This is the leg-1 pricing for a cycle: asking for an exact amount of the
 * intermediate token makes leg 2's input deterministic, so the cycle closes
 * with no residue and the tolerance sits on the input side.
 */
export function pumpBuyBaseInput(args: {
  base: bigint;
  baseReserve: bigint;
  quoteReserve: bigint;
  virtualQuoteReserves: bigint;
  baseMintSupply: bigint;
  coinCreatorIsDefault: boolean;
  globalConfig: PumpGlobalConfig;
  feeConfig: PumpFeeConfig | null;
  isCanonicalPumpPool: boolean;
}): PumpBuyBaseResult {
  if (args.baseReserve === 0n || args.quoteReserve === 0n) {
    throw new UnquotableError("empty-reserves", "baseReserve or quoteReserve is zero");
  }
  if (args.base <= 0n) {
    throw new UnquotableError("amount-out-of-range", "base must be > 0");
  }
  if (args.base >= args.baseReserve) {
    throw new UnquotableError("amount-out-of-range", "cannot buy more base than the pool holds");
  }

  const effectiveQuoteReserve = args.quoteReserve + args.virtualQuoteReserves;
  if (effectiveQuoteReserve <= 0n) {
    throw new UnquotableError("empty-reserves", "effective quote reserve is not positive");
  }

  const quoteAmountIn = ceilDiv(effectiveQuoteReserve * args.base, args.baseReserve - args.base);

  const fees = pumpComputeFeesBps({
    globalConfig: args.globalConfig,
    feeConfig: args.feeConfig,
    isCanonicalPumpPool: args.isCanonicalPumpPool,
    baseMintSupply: args.baseMintSupply,
    baseReserve: args.baseReserve,
    quoteReserve: effectiveQuoteReserve,
  });

  const lpFee = pumpFee(quoteAmountIn, fees.lpFeeBps);
  const protocolFee = pumpFee(quoteAmountIn, fees.protocolFeeBps);
  const coinCreatorFee = args.coinCreatorIsDefault
    ? 0n
    : pumpFee(quoteAmountIn, fees.creatorFeeBps);

  return {
    totalQuoteIn: quoteAmountIn + lpFee + protocolFee + coinCreatorFee,
    quoteAmountIn,
    lpFee,
    protocolFee,
    coinCreatorFee,
    fees,
  };
}

export class PumpSwapQuoter implements Quoter {
  readonly family = "pump-swap" as const;

  quote(
    pool: PoolSnapshot,
    amountIn: bigint,
    direction: SwapDirection,
    ctx: QuoteContext,
  ): QuoteResult {
    const d = asData(pool);
    if (amountIn <= 0n) {
      throw new UnquotableError("amount-out-of-range", "amountIn must be > 0");
    }

    const baseMint = ctx.mints.get(d.baseMint);
    if (!baseMint) {
      throw new UnquotableError("missing-input", `mint state missing for ${d.baseMint}`);
    }
    // PumpSwap's own quote math models no Token-2022 transfer fee. If the base
    // mint charges one, our numbers and the program's would diverge, so we
    // refuse rather than quote something we know to be wrong.
    if (baseMint.extensions.transferFee && baseMint.extensions.transferFee.basisPoints > 0) {
      throw new UnquotableError(
        "unsupported-mint-extension",
        "base mint charges a Token-2022 transfer fee; PumpSwap math does not model it",
      );
    }

    const coinCreatorIsDefault = d.coinCreator === SYSTEM_PROGRAM_ID;
    const common = {
      baseReserve: d.poolBaseAmount,
      quoteReserve: d.poolQuoteAmount,
      virtualQuoteReserves: d.virtualQuoteReserves,
      baseMintSupply: baseMint.supply,
      coinCreatorIsDefault,
      globalConfig: d.globalConfig,
      feeConfig: d.feeConfig,
      isCanonicalPumpPool: d.isCanonicalPumpPool,
    };

    if (direction.inputMint === d.quoteMint && direction.outputMint === d.baseMint) {
      if ((d.globalConfig.disableFlags & DISABLE_BUY) !== 0) {
        throw new UnquotableError("pool-disabled", "buy disabled by global config");
      }
      const r = pumpBuyQuoteInput({ quote: amountIn, ...common });
      return {
        family: this.family,
        poolId: pool.poolId,
        direction,
        amountIn,
        amountOut: r.baseAmountOut,
        fees: {
          inInputToken: r.lpFee + r.protocolFee + r.coinCreatorFee,
          inOutputToken: 0n,
          breakdown: {
            lpFee: r.lpFee,
            protocolFee: r.protocolFee,
            coinCreatorFee: r.coinCreatorFee,
            lpFeeBps: r.fees.lpFeeBps,
            protocolFeeBps: r.fees.protocolFeeBps,
            creatorFeeBps: coinCreatorIsDefault ? 0n : r.fees.creatorFeeBps,
          },
        },
        reserveIn: d.poolQuoteAmount + d.virtualQuoteReserves,
        reserveOut: d.poolBaseAmount,
        slot: pool.slot,
        receivedAt: pool.receivedAt,
        exactness: "exact",
        maxAmountIn: this.maxAmountIn(pool, direction, ctx),
      };
    }

    if (direction.inputMint === d.baseMint && direction.outputMint === d.quoteMint) {
      if ((d.globalConfig.disableFlags & DISABLE_SELL) !== 0) {
        throw new UnquotableError("pool-disabled", "sell disabled by global config");
      }
      const r = pumpSellBaseInput({ base: amountIn, ...common });
      return {
        family: this.family,
        poolId: pool.poolId,
        direction,
        amountIn,
        amountOut: r.finalQuote,
        fees: {
          inInputToken: 0n,
          inOutputToken: r.lpFee + r.protocolFee + r.coinCreatorFee,
          breakdown: {
            lpFee: r.lpFee,
            protocolFee: r.protocolFee,
            coinCreatorFee: r.coinCreatorFee,
            lpFeeBps: r.fees.lpFeeBps,
            protocolFeeBps: r.fees.protocolFeeBps,
            creatorFeeBps: coinCreatorIsDefault ? 0n : r.fees.creatorFeeBps,
          },
        },
        reserveIn: d.poolBaseAmount,
        reserveOut: d.poolQuoteAmount + d.virtualQuoteReserves,
        slot: pool.slot,
        receivedAt: pool.receivedAt,
        exactness: "exact",
        maxAmountIn: this.maxAmountIn(pool, direction, ctx),
      };
    }

    throw new UnquotableError(
      "mint-not-in-pool",
      `direction ${direction.inputMint}->${direction.outputMint} does not match pool mints`,
    );
  }

  maxAmountIn(pool: PoolSnapshot, direction: SwapDirection, _ctx: QuoteContext): bigint {
    const d = asData(pool);
    if (direction.inputMint === d.quoteMint) {
      const eff = d.poolQuoteAmount + d.virtualQuoteReserves;
      return eff > 0n ? eff : 0n;
    }
    return d.poolBaseAmount;
  }

  requiredAccounts(pool: PoolSnapshot): string[] {
    const d = asData(pool);
    return [pool.poolId, d.poolBaseTokenAccount, d.poolQuoteTokenAccount];
  }
}
