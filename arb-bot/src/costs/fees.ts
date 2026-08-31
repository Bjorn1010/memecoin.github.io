/**
 * Solana transaction cost model.
 *
 * Nothing here is hardcoded from memory: `lamportsPerSignature` and the
 * rent-exempt minimum are supplied by the caller, which reads them from the
 * cluster (`getFeeForMessage`, `getMinimumBalanceForRentExemption`). The pure
 * functions below only combine them, so they are testable without a network
 * and stay correct if the cluster's fee parameters change.
 *
 * REFERENCE (#SOL-1, #SOL-2 in ASSUMPTIONS.md):
 *  - Priority fee = ceil(compute_unit_limit * compute_unit_price / 1e6), where
 *    compute_unit_price is in micro-lamports per compute unit. The ceiling is
 *    verified empirically at runtime by `verifyPriorityFeeModel` in
 *    exec/simulator.ts, which compares this formula against `getFeeForMessage`
 *    for the exact message we are about to send.
 */
import { ceilDiv } from "../util/bigintMath.js";

export const MICRO_LAMPORTS_PER_LAMPORT = 1_000_000n;

/** Cluster-supplied fee parameters. Never guessed — see module docstring. */
export interface ClusterFeeParams {
  /** From `getFeeForMessage` on a 1-signature message with no priority fee. */
  lamportsPerSignature: bigint;
  /** `getMinimumBalanceForRentExemption(165)` — an SPL token account. */
  tokenAccountRentLamports: bigint;
  /** Slot the parameters were read at, for staleness reporting. */
  slot: number;
}

export interface TransactionCostInputs {
  cluster: ClusterFeeParams;
  /** Number of signatures the transaction carries (usually 1). */
  numSignatures: number;
  /** The CU limit we will set via ComputeBudgetProgram. */
  computeUnitLimit: number;
  /** The CU price we will set, in micro-lamports per CU. */
  computeUnitPriceMicroLamports: bigint;
  /** Jito (or equivalent) tip, in lamports. 0 when not using a tip. */
  tipLamports: bigint;
  /**
   * Whether a transaction that lands and REVERTS still costs fees.
   *
   * True for a plain RPC send: the transaction is included, it fails, and the
   * base and priority fees are charged anyway.
   *
   * False when sending as a Jito bundle: the block engine's documented
   * behaviour is that a bundle whose transactions do not all succeed is
   * rejected and never included, so nothing is charged. That single bit
   * transforms the economics at a low land rate — it is the difference between
   * paying for every failure and paying only for successes — so it is a
   * property of the sender, not a constant.
   */
  revertCostsFees: boolean;
}

export interface TransactionCosts {
  baseFee: bigint;
  priorityFee: bigint;
  tip: bigint;
  /**
   * What we pay if the transaction is included and SUCCEEDS.
   * Base + priority + tip.
   */
  onSuccess: bigint;
  /**
   * What we pay if the attempt fails after being sent.
   *
   * On a plain RPC send the transaction is included, reverts, and still pays
   * the base and priority fees; the tip is an instruction inside the same
   * transaction so it reverts with everything else. Sent as a Jito bundle, a
   * failing transaction is not included at all and this is zero.
   */
  onRevert: bigint;
  /**
   * What we pay if the transaction is never included at all: nothing. Fees on
   * Solana are only charged for transactions that make it into a block.
   */
  onNotIncluded: bigint;
}

export function priorityFeeLamports(
  computeUnitLimit: number,
  computeUnitPriceMicroLamports: bigint,
): bigint {
  if (computeUnitLimit < 0) throw new RangeError("computeUnitLimit must be >= 0");
  if (computeUnitPriceMicroLamports < 0n) throw new RangeError("price must be >= 0");
  if (computeUnitLimit === 0 || computeUnitPriceMicroLamports === 0n) return 0n;
  return ceilDiv(BigInt(computeUnitLimit) * computeUnitPriceMicroLamports, MICRO_LAMPORTS_PER_LAMPORT);
}

export function computeTransactionCosts(i: TransactionCostInputs): TransactionCosts {
  if (i.numSignatures < 1) throw new RangeError("a transaction needs at least one signature");
  const baseFee = i.cluster.lamportsPerSignature * BigInt(i.numSignatures);
  const priorityFee = priorityFeeLamports(i.computeUnitLimit, i.computeUnitPriceMicroLamports);
  const tip = i.tipLamports;
  return {
    baseFee,
    priorityFee,
    tip,
    onSuccess: baseFee + priorityFee + tip,
    onRevert: i.revertCostsFees ? baseFee + priorityFee : 0n,
    onNotIncluded: 0n,
  };
}

/**
 * Capital that must sit idle for the bot to operate, as opposed to a cost.
 *
 * Rent for a token account is refundable when the account is closed, so it is
 * NOT subtracted from profit. It is however capital we cannot trade with, and
 * the risk module accounts for it when checking that we can afford a trade.
 */
export interface LockedCapital {
  /** One WSOL account we keep permanently funded. */
  wsolAccountRent: bigint;
  /** One token account per intermediate mint we hold an ATA for. */
  intermediateAccountRent: bigint;
  total: bigint;
}

export function lockedCapital(
  cluster: ClusterFeeParams,
  intermediateAtaCount: number,
): LockedCapital {
  const wsolAccountRent = cluster.tokenAccountRentLamports;
  const intermediateAccountRent = cluster.tokenAccountRentLamports * BigInt(Math.max(0, intermediateAtaCount));
  return {
    wsolAccountRent,
    intermediateAccountRent,
    total: wsolAccountRent + intermediateAccountRent,
  };
}

/**
 * Tip sizing.
 *
 * The tip is bounded three ways and the tightest bound wins:
 *  - a hard floor, because a tip below the auction's dust level buys nothing;
 *  - a hard ceiling in lamports;
 *  - a fraction of the profit that is left after the non-tip costs.
 *
 * If the resulting tip would leave less than `minProfitLamports` on the table,
 * the caller is told to skip the opportunity rather than to tip less: a trade
 * that only clears because we underpaid for inclusion is a trade that will not
 * land, and an unlanded trade with a real cost is worse than no trade.
 */
export interface TipPolicy {
  minTipLamports: bigint;
  maxTipLamports: bigint;
  /** Share of post-cost profit we are willing to give up, in basis points. */
  maxTipShareBps: bigint;
  /** Profit we insist on keeping after every cost including the tip. */
  minProfitLamports: bigint;
}

export interface TipDecision {
  tipLamports: bigint;
  /** Profit left after base fee, priority fee and this tip. */
  profitAfterTip: bigint;
  /** False when no tip in the allowed range leaves us above minProfit. */
  viable: boolean;
  reason: "ok" | "profit-below-floor-before-tip" | "profit-below-floor-after-tip";
}

export function decideTip(args: {
  grossProfit: bigint;
  baseFee: bigint;
  priorityFee: bigint;
  policy: TipPolicy;
}): TipDecision {
  const { grossProfit, baseFee, priorityFee, policy } = args;
  const profitBeforeTip = grossProfit - baseFee - priorityFee;

  if (profitBeforeTip <= policy.minProfitLamports) {
    return {
      tipLamports: 0n,
      profitAfterTip: profitBeforeTip,
      viable: false,
      reason: "profit-below-floor-before-tip",
    };
  }

  // The most we could tip and still keep the floor.
  const headroom = profitBeforeTip - policy.minProfitLamports;
  const shareCap = (profitBeforeTip * policy.maxTipShareBps) / 10_000n;

  let tip = shareCap;
  if (tip > policy.maxTipLamports) tip = policy.maxTipLamports;
  if (tip > headroom) tip = headroom;
  if (tip < policy.minTipLamports) tip = policy.minTipLamports;

  // The floor tip may itself break the profit floor.
  if (tip > headroom) {
    return {
      tipLamports: tip,
      profitAfterTip: profitBeforeTip - tip,
      viable: false,
      reason: "profit-below-floor-after-tip",
    };
  }

  return {
    tipLamports: tip,
    profitAfterTip: profitBeforeTip - tip,
    viable: true,
    reason: "ok",
  };
}
