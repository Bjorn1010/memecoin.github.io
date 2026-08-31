/**
 * The one function that decides whether money is likely to be made.
 *
 * `profitNet` is pure: it takes a sized cycle, a cost breakdown and a land-rate
 * estimate, and returns both the profit if the transaction lands and the
 * expected value of *attempting* it. Those two numbers are different and the
 * bot trades on the second one:
 *
 *   EV = P(success) x (gross - baseFee - priorityFee - tip)
 *      - P(reverted) x (baseFee + priorityFee)
 *      - P(notIncluded) x 0
 *
 * An opportunity with a positive gross profit and a negative EV is rejected
 * automatically (§16). That is the whole point of the module: at a 10% land
 * rate, one success has to pay for the fees of nine failures.
 */
import type { TransactionCosts } from "./fees.js";
import type { LandRateEstimate } from "./landRate.js";
import type { RejectReason } from "../types.js";

export interface ProfitInputs {
  /** amountOut - amountIn of the cycle, in base-asset lamports. */
  grossProfit: bigint;
  costs: TransactionCosts;
  landRate: LandRateEstimate;
  /** Profit we insist on keeping if the transaction lands. */
  minProfitLamports: bigint;
  /**
   * Require EV to exceed this, not merely zero. Covers model error: our land
   * rate, our CU estimate and our quote are all estimates.
   */
  minExpectedValueLamports: bigint;
}

export interface ProfitResult {
  grossProfit: bigint;
  /** Costs paid when the transaction lands and succeeds. */
  directCost: bigint;
  /** Profit if the transaction lands and succeeds. */
  netProfitIfLanded: bigint;
  /**
   * Expected value of making the attempt, in lamports. Scaled by 1e6 internally
   * to keep it in integers; exposed as a bigint of lamports (rounded toward
   * zero, i.e. against us for positive EV).
   */
  expectedValue: bigint;
  /**
   * Total cost we expect to pay per successful trade, including the fees burnt
   * on the reverted attempts in between. Reporting aid for §15.
   */
  expectedCostPerSuccess: bigint;
  shouldTrade: boolean;
  reason: RejectReason | "ok";
}

/** Fixed-point scale for probability arithmetic; keeps EV in integer math. */
const P_SCALE = 1_000_000n;

function probToFixed(p: number): bigint {
  if (!Number.isFinite(p) || p < 0) return 0n;
  if (p > 1) return P_SCALE;
  return BigInt(Math.round(p * Number(P_SCALE)));
}

export function profitNet(i: ProfitInputs): ProfitResult {
  const { grossProfit, costs, landRate, minProfitLamports, minExpectedValueLamports } = i;

  const directCost = costs.onSuccess;
  const netProfitIfLanded = grossProfit - directCost;

  const pS = probToFixed(landRate.pSuccess);
  const pR = probToFixed(landRate.pReverted);

  // EV in lamports * P_SCALE, then divided back down.
  const evScaled = pS * netProfitIfLanded - pR * costs.onRevert;
  // Round toward zero so a marginal EV never rounds itself into a trade.
  const expectedValue = evScaled / P_SCALE;

  const expectedCostPerSuccess =
    pS === 0n ? costs.onSuccess + costs.onRevert * 1000n : costs.onSuccess + (pR * costs.onRevert) / pS;

  let reason: ProfitResult["reason"] = "ok";
  if (grossProfit <= 0n) {
    reason = "not-profitable-gross";
  } else if (netProfitIfLanded <= 0n) {
    reason = "not-profitable-net";
  } else if (netProfitIfLanded < minProfitLamports) {
    reason = "below-min-profit";
  } else if (expectedValue < minExpectedValueLamports) {
    reason = "negative-expected-value";
  }

  return {
    grossProfit,
    directCost,
    netProfitIfLanded,
    expectedValue,
    expectedCostPerSuccess,
    shouldTrade: reason === "ok",
    reason,
  };
}

/**
 * The minimum gross profit that could possibly clear the bar, given costs and
 * the current land rate. Used to prune candidates before doing the expensive
 * sizing search, and reported so the operator can see the bar moving.
 *
 * Derived by solving `EV = minExpectedValue` for gross:
 *   pS x (gross - onSuccess) - pR x onRevert = minEV
 *   gross = onSuccess + (minEV + pR x onRevert) / pS
 * and taking the larger of that and the `minProfit` bar.
 */
export function breakEvenGrossProfit(i: {
  costs: TransactionCosts;
  landRate: LandRateEstimate;
  minProfitLamports: bigint;
  minExpectedValueLamports: bigint;
}): bigint {
  const pS = probToFixed(i.landRate.pSuccess);
  const pR = probToFixed(i.landRate.pReverted);
  const fromMinProfit = i.costs.onSuccess + i.minProfitLamports;
  if (pS === 0n) return fromMinProfit > 0n ? fromMinProfit * 1000n : 1n;
  const fromEv =
    i.costs.onSuccess + (i.minExpectedValueLamports * P_SCALE + pR * i.costs.onRevert + pS - 1n) / pS;
  return fromEv > fromMinProfit ? fromEv : fromMinProfit;
}
