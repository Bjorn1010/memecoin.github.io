/**
 * Trade sizing.
 *
 * There is no fixed size anywhere in this bot. For every candidate cycle we
 * search for the input amount that maximises profit, subject to the pools'
 * depth, the configured maximum trade size and the capital actually available.
 *
 * WHY NOT JUST A TERNARY SEARCH
 * The exact profit function is the composition of two integer quoters with
 * ceiling/floor fee rounding, a `-1` base-unit adjustment inside PumpSwap's buy
 * path, and (on PumpSwap) a fee tier chosen from the pre-trade market cap. It is
 * *approximately* unimodal but not strictly so: it has flat plateaus and
 * one-unit sawtooth from rounding, which is exactly the condition under which a
 * naive ternary search converges to the wrong side (§13).
 *
 * So the search is three-stage and never assumes global unimodality:
 *   1. a coarse geometric grid over the whole feasible interval, which cannot
 *      be fooled by local sawtooth because it steps by ratios, not units;
 *   2. an analytic candidate from the closed-form two-CPMM optimum when the
 *      caller can supply one — evaluated with the exact quoters like any other
 *      candidate, never trusted on its own;
 *   3. a bounded local refinement around the best candidate: bisection on the
 *      bracket followed by an integer hill-climb with halving steps, which
 *      handles plateaus correctly.
 *
 * The objective is GROSS profit. Base fee, priority fee and the tip are either
 * constant in the trade size or monotone in the profit, so none of them moves
 * the argmax; the cost model is applied to the winner afterwards by
 * costs/profitNet.ts.
 */
import { bigintMax, isqrt } from "../util/bigintMath.js";

export interface SizingBounds {
  /** Smallest input worth evaluating; below this we call it dust. */
  minAmountIn: bigint;
  /** Largest input allowed: min(depth, MAX_TRADE_SIZE, capital). */
  maxAmountIn: bigint;
}

export type SizingBoundReason =
  | "none"
  | "pool-depth"
  | "max-trade-size"
  | "available-capital";

export interface SizingOptions {
  /** Number of points on the coarse geometric grid. */
  gridPoints: number;
  /** Maximum evaluations for the local refinement. */
  maxRefineSteps: number;
  /** Extra candidates to evaluate, e.g. the analytic optimum. */
  analyticCandidates?: bigint[];
}

export const DEFAULT_SIZING_OPTIONS: SizingOptions = {
  gridPoints: 40,
  maxRefineSteps: 64,
};

export interface SizingDiagnostics {
  evaluations: number;
  /**
   * True when the upper bound binds: the best profit found is also attained at
   * `maxAmountIn`, so a larger cap (more capital, deeper pool, higher
   * MAX_TRADE_SIZE) would have made at least as much money.
   *
   * Deliberately not "winner === maxAmountIn": integer truncation makes the
   * profit curve flat near the top, and the tie-break below prefers the
   * smallest size on a plateau, so the winner is frequently one unit under the
   * cap while still being fully constrained by it.
   */
  atUpperBound: boolean;
  /** True when the lower bound binds, by the same definition. */
  atLowerBound: boolean;
  boundReason: SizingBoundReason;
  /** Best gross profit seen anywhere during the search. */
  bestGrossProfit: bigint;
  /** Whether the analytic candidate (if any) turned out to be the winner. */
  analyticWon: boolean;
}

export interface SizingResult {
  optimalAmountIn: bigint;
  expectedAmountOut: bigint;
  expectedGrossProfit: bigint;
  diagnostics: SizingDiagnostics;
  /** False when nothing in the feasible interval turns a gross profit. */
  profitable: boolean;
}

/**
 * Evaluate a cycle at a given input size.
 * Returns null when the size is not quotable (depth exhausted, dust, ...).
 */
export type CycleEvaluator = (amountIn: bigint) => { amountOut: bigint } | null;

interface Candidate {
  amountIn: bigint;
  amountOut: bigint;
  profit: bigint;
}

export function optimalTradeSize(
  evaluate: CycleEvaluator,
  bounds: SizingBounds,
  boundReason: SizingBoundReason = "none",
  options: SizingOptions = DEFAULT_SIZING_OPTIONS,
): SizingResult {
  const lo = bigintMax(1n, bounds.minAmountIn);
  const hi = bounds.maxAmountIn;
  let evaluations = 0;
  let analyticWon = false;

  const tryAt = (amountIn: bigint): Candidate | null => {
    if (amountIn < lo || amountIn > hi) return null;
    evaluations++;
    const r = evaluate(amountIn);
    if (!r) return null;
    return { amountIn, amountOut: r.amountOut, profit: r.amountOut - amountIn };
  };

  if (hi < lo) {
    return emptyResult(evaluations, boundReason);
  }

  // Held in an object rather than a bare `let` so that the helper below can
  // update it without the compiler losing track of the narrowed type.
  const state: { best: Candidate | null } = { best: null };
  const consider = (c: Candidate | null, fromAnalytic = false): void => {
    if (!c) return;
    const b = state.best;
    // Strictly greater profit wins. On a tie we keep the SMALLER size: the
    // profit curve has flat plateaus from integer truncation, and on a plateau
    // the smaller trade earns the same money with less capital at risk and less
    // price impact.
    if (!b || c.profit > b.profit || (c.profit === b.profit && c.amountIn < b.amountIn)) {
      state.best = c;
      analyticWon = fromAnalytic;
    }
  };

  // --- stage 1: coarse geometric grid ---------------------------------------
  const grid = geometricGrid(lo, hi, Math.max(4, options.gridPoints));
  for (const point of grid) consider(tryAt(point));

  // --- stage 2: analytic candidates ----------------------------------------
  for (const candidate of options.analyticCandidates ?? []) {
    if (candidate >= lo && candidate <= hi) consider(tryAt(candidate), true);
    // The closed form ignores integer rounding; probe its immediate neighbours.
    for (const delta of [-1n, 1n]) {
      const n = candidate + delta;
      if (n >= lo && n <= hi) consider(tryAt(n), true);
    }
  }

  const afterGrid = state.best;
  if (!afterGrid) {
    return emptyResult(evaluations, boundReason);
  }

  // --- stage 3: local refinement -------------------------------------------
  // Bracket the winner with its grid neighbours, then hill-climb with halving
  // steps. Halving handles plateaus: a step that finds an equal value keeps
  // moving, a step that finds a worse value shrinks.
  const idx = grid.findIndex((g) => g === afterGrid.amountIn);
  const lowerNeighbour = idx > 0 ? grid[idx - 1]! : lo;
  const upperNeighbour = idx >= 0 && idx < grid.length - 1 ? grid[idx + 1]! : hi;

  let step = (upperNeighbour - lowerNeighbour) / 4n;
  if (step < 1n) step = 1n;
  let budget = options.maxRefineSteps;

  while (step >= 1n && budget > 0) {
    const current = state.best!;
    const before = current.profit;
    const up = tryAt(current.amountIn + step);
    const down = tryAt(current.amountIn - step);
    budget -= 2;

    consider(up);
    consider(down);

    if (state.best!.profit <= before) {
      // No improvement at this scale: look closer.
      step /= 2n;
    }
  }

  const winner: Candidate = state.best!;

  // A bound binds when the best profit we found is also available AT that
  // bound: pushing the cap out would then have been worth at least as much.
  const atBound = (edge: bigint): boolean => {
    if (winner.amountIn === edge) return true;
    const r = evaluate(edge);
    evaluations++;
    return r !== null && r.amountOut - edge >= winner.profit;
  };

  return {
    optimalAmountIn: winner.amountIn,
    expectedAmountOut: winner.amountOut,
    expectedGrossProfit: winner.profit,
    profitable: winner.profit > 0n,
    diagnostics: {
      evaluations,
      atUpperBound: atBound(hi),
      atLowerBound: atBound(lo),
      boundReason,
      bestGrossProfit: winner.profit,
      analyticWon,
    },
  };
}

function emptyResult(evaluations: number, boundReason: SizingBoundReason): SizingResult {
  return {
    optimalAmountIn: 0n,
    expectedAmountOut: 0n,
    expectedGrossProfit: 0n,
    profitable: false,
    diagnostics: {
      evaluations,
      atUpperBound: false,
      atLowerBound: false,
      boundReason,
      bestGrossProfit: 0n,
      analyticWon: false,
    },
  };
}

/**
 * Geometric grid from `lo` to `hi` inclusive, deduplicated and sorted.
 * Geometric rather than linear because profit-vs-size on a CPMM is scale-free:
 * a linear grid wastes most of its points on sizes far beyond the optimum.
 */
export function geometricGrid(lo: bigint, hi: bigint, points: number): bigint[] {
  if (hi <= lo) return [lo];
  const out = new Set<bigint>([lo, hi]);
  // Work in floating point only to pick the *positions* of the samples; the
  // values themselves are exact bigints and every candidate is scored with the
  // exact integer quoters.
  const logLo = Math.log(Number(lo));
  const logHi = Math.log(Number(hi));
  if (Number.isFinite(logLo) && Number.isFinite(logHi) && logHi > logLo) {
    for (let i = 1; i < points - 1; i++) {
      const t = i / (points - 1);
      const v = Math.exp(logLo + t * (logHi - logLo));
      if (Number.isFinite(v) && v >= 1) {
        const b = BigInt(Math.floor(v));
        if (b >= lo && b <= hi) out.add(b);
      }
    }
  }
  return [...out].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

/**
 * Closed-form optimum for two constant-product pools whose fees are taken on
 * the INPUT side of each leg.
 *
 * Leg 1 swaps `a` of X into pool 1 (reserves x1, y1); leg 2 swaps the proceeds
 * back into X through pool 2 (reserves y2, x2). With `r1`, `r2` the fraction of
 * the input that survives each leg's fee, expressed as `num/den`:
 *
 *   out(a) = A*a / (B + C*a)      A = r1*r2*x2*y1
 *                                 B = x1*y2
 *                                 C = r1*y2 + r1*r2*y1
 *
 *   d/da [out(a) - a] = 0  =>  a* = (sqrt(A*B) - B) / C
 *
 * Returns null when no positive size is profitable (A <= B), which is the
 * common case and a cheap way to reject a cycle before any search.
 *
 * This is a HINT. Output-side fees (Raydium's creator fee in one of its modes),
 * PumpSwap's `-1` adjustment and every rounding step are not modelled here, so
 * the caller must score the result with the real quoters — `optimalTradeSize`
 * does exactly that.
 */
export function closedFormTwoCpmmOptimum(args: {
  /** Reserves of leg 1: input side x1, output side y1. */
  x1: bigint;
  y1: bigint;
  /** Reserves of leg 2: input side y2, output side x2. */
  y2: bigint;
  x2: bigint;
  /** Fee-surviving fraction of leg 1 as a rational, e.g. 9975/10000. */
  r1Num: bigint;
  r1Den: bigint;
  r2Num: bigint;
  r2Den: bigint;
}): bigint | null {
  const { x1, y1, y2, x2, r1Num, r1Den, r2Num, r2Den } = args;
  if (x1 <= 0n || y1 <= 0n || y2 <= 0n || x2 <= 0n) return null;
  if (r1Num <= 0n || r2Num <= 0n) return null;

  // Scale everything by (r1Den * r2Den) to stay in integers.
  const den = r1Den * r2Den;
  const A = r1Num * r2Num * x2 * y1; // scaled by den
  const B = x1 * y2 * den; // scaled by den
  const C = r1Num * y2 * r2Den + r1Num * r2Num * y1; // scaled by den

  if (C <= 0n) return null;
  if (A <= B) return null; // no profitable direction

  const root = isqrt(A * B);
  if (root <= B) return null;
  const a = (root - B) / C;
  return a > 0n ? a : null;
}
