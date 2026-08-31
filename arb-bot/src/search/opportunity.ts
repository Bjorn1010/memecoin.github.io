/**
 * Cycle discovery and evaluation.
 *
 * A cycle is base -> intermediate -> base through two different pools, executed
 * atomically in one transaction. Only two-leg cycles are supported: they fit in
 * one transaction comfortably, their profit assertion is exact (see
 * exec/transactionBuilder.ts) and their failure modes are enumerable.
 *
 * Nothing here talks to the network. It takes decoded snapshots in and returns
 * ranked, sized, costed opportunities out, so the whole decision path can be
 * replayed offline from captured state (§34).
 */
import type {
  CycleCandidate,
  DexFamily,
  PoolSnapshot,
  QuoteResult,
  RejectReason,
  SizedCycle,
} from "../types.js";
import { UnquotableError, type QuoteContext, type Quoter } from "../quoters/Quoter.js";
import {
  DEFAULT_SIZING_OPTIONS,
  closedFormTwoCpmmOptimum,
  optimalTradeSize,
  type SizingBoundReason,
  type SizingOptions,
  type SizingResult,
} from "./sizing.js";
import { bigintMin } from "../util/bigintMath.js";
import { isStateFresh, type FeedHealth, type FreshnessPolicy } from "./freshness.js";
import {
  raydiumEffectiveReserves,
  raydiumOutputFeeRate,
  raydiumTotalInputFeeRate,
  RAY_FEE_RATE_DENOMINATOR,
  type RaydiumCpmmPoolData,
} from "../quoters/cpmm/raydiumCpmm.js";
import {
  BPS_DENOMINATOR,
  pumpComputeFeesBps,
  type PumpSwapPoolData,
} from "../quoters/cpmm/pumpSwap.js";

export interface OpportunitySearchLimits {
  /** Hard cap on a single trade, from config. */
  maxTradeSizeLamports: bigint;
  /** What the wallet can actually deploy right now. */
  availableCapitalLamports: bigint;
  /** Below this, do not bother: the fixed costs dwarf the trade. */
  minTradeSizeLamports: bigint;
}

export interface EvaluatedOpportunity {
  cycle: CycleCandidate;
  sized: SizedCycle | null;
  sizing: SizingResult;
  rejected: RejectReason | null;
  /** Populated when a quoter refused; useful to spot decoding problems. */
  quoteError?: string;
}

/** Enumerate every ordered pair of distinct pools sharing an intermediate mint. */
export function enumerateCycles(
  pools: readonly PoolSnapshot[],
  baseMint: string,
): CycleCandidate[] {
  const byIntermediate = new Map<string, PoolSnapshot[]>();
  for (const p of pools) {
    const intermediate =
      p.mintA === baseMint ? p.mintB : p.mintB === baseMint ? p.mintA : null;
    if (!intermediate) continue;
    const list = byIntermediate.get(intermediate);
    if (list) list.push(p);
    else byIntermediate.set(intermediate, [p]);
  }

  const out: CycleCandidate[] = [];
  for (const [intermediateMint, list] of byIntermediate) {
    if (list.length < 2) continue;
    for (const buy of list) {
      for (const sell of list) {
        if (buy.poolId === sell.poolId) continue;
        out.push({
          baseMint,
          intermediateMint,
          buyPoolId: buy.poolId,
          buyFamily: buy.family,
          sellPoolId: sell.poolId,
          sellFamily: sell.family,
        });
      }
    }
  }
  return out;
}

export interface EvaluateCycleArgs {
  cycle: CycleCandidate;
  buyPool: PoolSnapshot;
  sellPool: PoolSnapshot;
  quoters: ReadonlyMap<DexFamily, Quoter>;
  ctx: QuoteContext;
  limits: OpportunitySearchLimits;
  freshness: FreshnessPolicy;
  feed: FeedHealth;
  nowMs: number;
  sizingOptions?: SizingOptions;
}

export function evaluateCycle(args: EvaluateCycleArgs): EvaluatedOpportunity {
  const { cycle, buyPool, sellPool, quoters, ctx, limits, freshness, feed, nowMs } = args;
  const emptySizing: SizingResult = {
    optimalAmountIn: 0n,
    expectedAmountOut: 0n,
    expectedGrossProfit: 0n,
    profitable: false,
    diagnostics: {
      evaluations: 0,
      atUpperBound: false,
      atLowerBound: false,
      boundReason: "none",
      bestGrossProfit: 0n,
      analyticWon: false,
    },
  };

  const buyQuoter = quoters.get(buyPool.family);
  const sellQuoter = quoters.get(sellPool.family);
  if (!buyQuoter || !sellQuoter) {
    return { cycle, sized: null, sizing: emptySizing, rejected: "no-cycle" };
  }

  // Freshness gate before any work: a stale pair is not worth quoting.
  for (const p of [buyPool, sellPool]) {
    const v = isStateFresh(p, feed, nowMs, freshness);
    if (!v.fresh) {
      return { cycle, sized: null, sizing: emptySizing, rejected: "stale-state" };
    }
  }

  const buyDirection = { inputMint: cycle.baseMint, outputMint: cycle.intermediateMint };
  const sellDirection = { inputMint: cycle.intermediateMint, outputMint: cycle.baseMint };

  // Upper bound on the trade: the tightest of depth, config cap and capital.
  let boundReason: SizingBoundReason = "pool-depth";
  let upper: bigint;
  try {
    upper = buyQuoter.maxAmountIn(buyPool, buyDirection, ctx);
  } catch (e) {
    return {
      cycle,
      sized: null,
      sizing: emptySizing,
      rejected: "no-cycle",
      quoteError: describeError(e),
    };
  }
  if (limits.maxTradeSizeLamports < upper) {
    upper = limits.maxTradeSizeLamports;
    boundReason = "max-trade-size";
  }
  if (limits.availableCapitalLamports < upper) {
    upper = limits.availableCapitalLamports;
    boundReason = "available-capital";
  }

  if (upper < limits.minTradeSizeLamports) {
    return { cycle, sized: null, sizing: emptySizing, rejected: "size-below-dust" };
  }

  let lastError: unknown = null;
  let lastLegs: [QuoteResult, QuoteResult] | null = null;

  const evaluate = (amountIn: bigint): { amountOut: bigint } | null => {
    try {
      const leg1 = buyQuoter.quote(buyPool, amountIn, buyDirection, ctx);
      if (leg1.amountOut <= 0n) return null;
      const leg2 = sellQuoter.quote(sellPool, leg1.amountOut, sellDirection, ctx);
      lastLegs = [leg1, leg2];
      return { amountOut: leg2.amountOut };
    } catch (e) {
      if (e instanceof UnquotableError) {
        lastError = e;
        return null;
      }
      throw e;
    }
  };

  const analytic = analyticCandidate(buyPool, sellPool, cycle, ctx);

  const sizing = optimalTradeSize(
    evaluate,
    { minAmountIn: limits.minTradeSizeLamports, maxAmountIn: upper },
    boundReason,
    {
      ...(args.sizingOptions ?? DEFAULT_SIZING_OPTIONS),
      analyticCandidates: analytic === null ? [] : [analytic],
    },
  );

  if (!sizing.profitable) {
    return {
      cycle,
      sized: null,
      sizing,
      rejected: sizing.optimalAmountIn === 0n && lastError ? "no-cycle" : "not-profitable-gross",
      ...(lastError ? { quoteError: describeError(lastError) } : {}),
    };
  }

  // Re-quote at the winning size so the returned legs are exactly the ones the
  // transaction builder will use. `lastLegs` may be from a probe elsewhere.
  let legs: [QuoteResult, QuoteResult];
  try {
    const leg1 = buyQuoter.quote(buyPool, sizing.optimalAmountIn, buyDirection, ctx);
    const leg2 = sellQuoter.quote(sellPool, leg1.amountOut, sellDirection, ctx);
    legs = [leg1, leg2];
  } catch (e) {
    return {
      cycle,
      sized: null,
      sizing,
      rejected: "no-cycle",
      quoteError: describeError(e),
    };
  }
  void lastLegs;

  if (legs[0].exactness !== "exact" || legs[1].exactness !== "exact") {
    return { cycle, sized: null, sizing, rejected: "quote-unverified" };
  }

  const sized: SizedCycle = {
    ...cycle,
    amountIn: sizing.optimalAmountIn,
    intermediateAmount: legs[0].amountOut,
    amountOut: legs[1].amountOut,
    grossProfit: legs[1].amountOut - sizing.optimalAmountIn,
    slot: Math.min(buyPool.slot, sellPool.slot),
    receivedAt: Math.min(buyPool.receivedAt, sellPool.receivedAt),
    legs,
  };

  return { cycle, sized, sizing, rejected: null };
}

function describeError(e: unknown): string {
  if (e instanceof UnquotableError) return `${e.reason}: ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}

/**
 * Best-effort closed-form starting point.
 *
 * Only produced when both legs charge their fee on the input side, which is the
 * case the closed form models. Otherwise we return null and rely on the grid;
 * an analytic candidate that models the wrong fee structure is worse than none.
 */
function analyticCandidate(
  buyPool: PoolSnapshot,
  sellPool: PoolSnapshot,
  cycle: CycleCandidate,
  ctx: QuoteContext,
): bigint | null {
  const leg1 = inputSideCpmm(buyPool, cycle.baseMint, cycle.intermediateMint, ctx);
  const leg2 = inputSideCpmm(sellPool, cycle.intermediateMint, cycle.baseMint, ctx);
  if (!leg1 || !leg2) return null;
  return closedFormTwoCpmmOptimum({
    x1: leg1.reserveIn,
    y1: leg1.reserveOut,
    y2: leg2.reserveIn,
    x2: leg2.reserveOut,
    r1Num: leg1.feeDen - leg1.feeNum,
    r1Den: leg1.feeDen,
    r2Num: leg2.feeDen - leg2.feeNum,
    r2Den: leg2.feeDen,
  });
}

interface InputSideCpmm {
  reserveIn: bigint;
  reserveOut: bigint;
  feeNum: bigint;
  feeDen: bigint;
}

function inputSideCpmm(
  pool: PoolSnapshot,
  inputMint: string,
  outputMint: string,
  ctx: QuoteContext,
): InputSideCpmm | null {
  if (pool.family === "raydium-cpmm") {
    const d = pool.data as RaydiumCpmmPoolData;
    const zeroForOne = inputMint === d.token0Mint;
    if (!zeroForOne && inputMint !== d.token1Mint) return null;
    // The creator fee can be charged on the output; the closed form does not
    // model that, so decline rather than mislead the search.
    if (raydiumOutputFeeRate(d, zeroForOne) !== 0n) return null;
    let reserves;
    try {
      reserves = raydiumEffectiveReserves(d);
    } catch {
      return null;
    }
    return {
      reserveIn: zeroForOne ? reserves.reserve0 : reserves.reserve1,
      reserveOut: zeroForOne ? reserves.reserve1 : reserves.reserve0,
      feeNum: raydiumTotalInputFeeRate(d, zeroForOne),
      feeDen: RAY_FEE_RATE_DENOMINATOR,
    };
  }

  if (pool.family === "pump-swap") {
    const d = pool.data as PumpSwapPoolData;
    // Only the buy direction (quote in) charges on the input side. The sell
    // direction charges on the output, so it is not modelled here.
    if (inputMint !== d.quoteMint || outputMint !== d.baseMint) return null;
    const baseMint = ctx.mints.get(d.baseMint);
    if (!baseMint) return null;
    const effectiveQuote = d.poolQuoteAmount + d.virtualQuoteReserves;
    if (effectiveQuote <= 0n || d.poolBaseAmount <= 0n) return null;
    let fees;
    try {
      fees = pumpComputeFeesBps({
        globalConfig: d.globalConfig,
        feeConfig: d.feeConfig,
        isCanonicalPumpPool: d.isCanonicalPumpPool,
        baseMintSupply: baseMint.supply,
        baseReserve: d.poolBaseAmount,
        quoteReserve: effectiveQuote,
      });
    } catch {
      return null;
    }
    const creatorBps = d.coinCreator === "11111111111111111111111111111111" ? 0n : fees.creatorFeeBps;
    return {
      reserveIn: effectiveQuote,
      reserveOut: d.poolBaseAmount,
      feeNum: fees.lpFeeBps + fees.protocolFeeBps + creatorBps,
      feeDen: BPS_DENOMINATOR,
    };
  }

  return null;
}

/** Convenience: the tightest upper bound across a set of limits. */
export function upperBoundFor(limits: OpportunitySearchLimits, depth: bigint): bigint {
  return bigintMin(depth, limits.maxTradeSizeLamports, limits.availableCapitalLamports);
}
