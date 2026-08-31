import { describe, expect, it } from "vitest";
import {
  closedFormTwoCpmmOptimum,
  geometricGrid,
  optimalTradeSize,
  type CycleEvaluator,
} from "../../src/search/sizing.js";

/**
 * A two-leg constant-product cycle with input-side fees, in exact integer math.
 * Used as the objective for the sizing tests so the optimum is known
 * independently of the search.
 */
function cpmmCycle(args: {
  x1: bigint;
  y1: bigint;
  y2: bigint;
  x2: bigint;
  feeNum1: bigint;
  feeNum2: bigint;
  feeDen: bigint;
}): CycleEvaluator {
  return (amountIn) => {
    if (amountIn <= 0n) return null;
    const in1 = (amountIn * (args.feeDen - args.feeNum1)) / args.feeDen;
    if (in1 <= 0n) return null;
    const out1 = (in1 * args.y1) / (args.x1 + in1);
    if (out1 <= 0n) return null;
    const in2 = (out1 * (args.feeDen - args.feeNum2)) / args.feeDen;
    if (in2 <= 0n) return null;
    const out2 = (in2 * args.x2) / (args.y2 + in2);
    return { amountOut: out2 };
  };
}

/** Exhaustive best over a coarse sweep, as an independent oracle. */
function bruteForceBest(
  evaluate: CycleEvaluator,
  lo: bigint,
  hi: bigint,
  steps = 2000,
): { amountIn: bigint; profit: bigint } {
  let best = { amountIn: 0n, profit: -(2n ** 62n) };
  const stride = (hi - lo) / BigInt(steps) || 1n;
  for (let a = lo; a <= hi; a += stride) {
    const r = evaluate(a);
    if (!r) continue;
    const p = r.amountOut - a;
    if (p > best.profit) best = { amountIn: a, profit: p };
  }
  return best;
}

describe("geometricGrid", () => {
  it("always includes both endpoints and stays inside the interval", () => {
    const g = geometricGrid(10n, 1_000_000n, 20);
    expect(g[0]).toBe(10n);
    expect(g[g.length - 1]).toBe(1_000_000n);
    for (const v of g) {
      expect(v).toBeGreaterThanOrEqual(10n);
      expect(v).toBeLessThanOrEqual(1_000_000n);
    }
  });

  it("is sorted and free of duplicates", () => {
    const g = geometricGrid(1n, 10n ** 12n, 60);
    for (let i = 1; i < g.length; i++) expect(g[i]!).toBeGreaterThan(g[i - 1]!);
  });

  it("degenerates gracefully when the interval is a single point", () => {
    expect(geometricGrid(5n, 5n, 30)).toEqual([5n]);
  });
});

describe("closedFormTwoCpmmOptimum", () => {
  it("returns null when the cycle cannot be profitable in this direction", () => {
    // Perfectly balanced pools: fees guarantee a loss.
    const a = closedFormTwoCpmmOptimum({
      x1: 1_000_000_000n,
      y1: 1_000_000_000n,
      y2: 1_000_000_000n,
      x2: 1_000_000_000n,
      r1Num: 9_975n,
      r1Den: 10_000n,
      r2Num: 9_975n,
      r2Den: 10_000n,
    });
    expect(a).toBeNull();
  });

  it("lands within a hair of the true optimum on a dislocated pair", () => {
    const params = {
      x1: 1_000_000_000n,
      y1: 4_000_000_000_000n, // pool 1 gives a lot of Y for X
      y2: 3_000_000_000_000n,
      x2: 1_000_000_000n, // pool 2 gives comparatively more X back
      feeNum1: 25n,
      feeNum2: 25n,
      feeDen: 10_000n,
    };
    const analytic = closedFormTwoCpmmOptimum({
      x1: params.x1,
      y1: params.y1,
      y2: params.y2,
      x2: params.x2,
      r1Num: params.feeDen - params.feeNum1,
      r1Den: params.feeDen,
      r2Num: params.feeDen - params.feeNum2,
      r2Den: params.feeDen,
    });
    expect(analytic).not.toBeNull();

    const evaluate = cpmmCycle(params);
    const brute = bruteForceBest(evaluate, 1n, 500_000_000n, 5000);
    const atAnalytic = evaluate(analytic!)!;
    const analyticProfit = atAnalytic.amountOut - analytic!;
    // The closed form ignores integer truncation, so allow a hair of slack but
    // require it to be essentially as good as the brute-force winner.
    expect(analyticProfit).toBeGreaterThan((brute.profit * 9_999n) / 10_000n);
  });
});

describe("optimalTradeSize", () => {
  const params = {
    x1: 2_000_000_000n,
    y1: 9_000_000_000_000n,
    y2: 8_000_000_000_000n,
    x2: 2_000_000_000n,
    feeNum1: 25n,
    feeNum2: 25n,
    feeDen: 10_000n,
  };
  const evaluate = cpmmCycle(params);

  it("beats every other size we probe (§35)", () => {
    const r = optimalTradeSize(evaluate, { minAmountIn: 1_000n, maxAmountIn: 1_000_000_000n });
    expect(r.profitable).toBe(true);

    const probes = [
      1_000n,
      10_000n,
      100_000n,
      1_000_000n,
      10_000_000n,
      100_000_000n,
      1_000_000_000n,
      r.optimalAmountIn / 2n,
      r.optimalAmountIn * 2n,
    ];
    for (const p of probes) {
      if (p < 1_000n || p > 1_000_000_000n) continue;
      const out = evaluate(p);
      if (!out) continue;
      expect(r.expectedGrossProfit).toBeGreaterThanOrEqual(out.amountOut - p);
    }
  });

  it("matches an independent brute-force sweep to within rounding", () => {
    const r = optimalTradeSize(evaluate, { minAmountIn: 1n, maxAmountIn: 1_000_000_000n });
    const brute = bruteForceBest(evaluate, 1n, 1_000_000_000n, 4000);
    expect(r.expectedGrossProfit).toBeGreaterThanOrEqual(brute.profit);
  });

  it("reports being pinned to MAX_TRADE_SIZE when the cap binds", () => {
    const r = optimalTradeSize(
      evaluate,
      { minAmountIn: 1_000n, maxAmountIn: 50_000n },
      "max-trade-size",
    );
    expect(r.diagnostics.atUpperBound).toBe(true);
    expect(r.diagnostics.boundReason).toBe("max-trade-size");
    // The winner may sit a unit or two below the cap: profit plateaus from
    // integer truncation and the search prefers the cheaper size on a tie.
    expect(r.optimalAmountIn).toBeGreaterThan(49_000n);
    expect(r.optimalAmountIn).toBeLessThanOrEqual(50_000n);
  });

  it("reports being pinned to pool depth when liquidity binds", () => {
    const shallow = cpmmCycle({ ...params, y1: 9_000_000n, x2: 2_000n });
    const r = optimalTradeSize(
      shallow,
      { minAmountIn: 1n, maxAmountIn: 1_000n },
      "pool-depth",
    );
    expect(r.diagnostics.boundReason).toBe("pool-depth");
  });

  it("finds no profit when the pools are aligned", () => {
    const flat = cpmmCycle({
      x1: 1_000_000_000n,
      y1: 1_000_000_000_000n,
      y2: 1_000_000_000_000n,
      x2: 1_000_000_000n,
      feeNum1: 25n,
      feeNum2: 25n,
      feeDen: 10_000n,
    });
    const r = optimalTradeSize(flat, { minAmountIn: 1_000n, maxAmountIn: 1_000_000_000n });
    expect(r.profitable).toBe(false);
    expect(r.expectedGrossProfit).toBeLessThanOrEqual(0n);
  });

  it("returns an empty result when the interval is empty", () => {
    const r = optimalTradeSize(evaluate, { minAmountIn: 1_000_000n, maxAmountIn: 1_000n });
    expect(r.profitable).toBe(false);
    expect(r.optimalAmountIn).toBe(0n);
  });

  it("handles an evaluator that refuses everything", () => {
    const r = optimalTradeSize(() => null, { minAmountIn: 1n, maxAmountIn: 1_000_000n });
    expect(r.profitable).toBe(false);
    expect(r.diagnostics.evaluations).toBeGreaterThan(0);
  });

  it("finds a small interior optimum when the dislocation barely clears fees", () => {
    // A 10 bps dislocation against 2 bps of round-trip fees on a deep pair.
    // The optimum is far below the cap, so neither bound should bind — this is
    // the shape of a genuine opportunity rather than a capital-limited one.
    const thin = cpmmCycle({
      x1: 1_000_000_000_000n,
      y1: 1_001_000_000_000_000n,
      y2: 1_000_000_000_000_000n,
      x2: 1_000_000_000_000n,
      feeNum1: 1n,
      feeNum2: 1n,
      feeDen: 10_000n,
    });
    const r = optimalTradeSize(thin, { minAmountIn: 1n, maxAmountIn: 1_000_000_000_000n });
    expect(r.profitable).toBe(true);
    expect(r.optimalAmountIn).toBeLessThan(1_000_000_000_000n);
    expect(r.diagnostics.atUpperBound).toBe(false);
    expect(r.diagnostics.atLowerBound).toBe(false);
  });

  it("a dislocation smaller than the fees is correctly found unprofitable", () => {
    // 1 bps of edge cannot pay 2 bps of fees. The search must say no, at every
    // size — this is the single most common real-world case.
    const unprofitable = cpmmCycle({
      x1: 1_000_000_000_000n,
      y1: 1_000_100_000_000_000n,
      y2: 1_000_000_000_000_000n,
      x2: 1_000_000_000_000n,
      feeNum1: 1n,
      feeNum2: 1n,
      feeDen: 10_000n,
    });
    const r = optimalTradeSize(unprofitable, { minAmountIn: 1n, maxAmountIn: 1_000_000_000_000n });
    expect(r.profitable).toBe(false);
  });

  it("uses the analytic candidate when one is supplied and it wins", () => {
    const analytic = closedFormTwoCpmmOptimum({
      x1: params.x1,
      y1: params.y1,
      y2: params.y2,
      x2: params.x2,
      r1Num: params.feeDen - params.feeNum1,
      r1Den: params.feeDen,
      r2Num: params.feeDen - params.feeNum2,
      r2Den: params.feeDen,
    })!;
    const withAnalytic = optimalTradeSize(
      evaluate,
      { minAmountIn: 1n, maxAmountIn: 1_000_000_000n },
      "none",
      { gridPoints: 8, maxRefineSteps: 4, analyticCandidates: [analytic] },
    );
    const withoutAnalytic = optimalTradeSize(
      evaluate,
      { minAmountIn: 1n, maxAmountIn: 1_000_000_000n },
      "none",
      { gridPoints: 8, maxRefineSteps: 4 },
    );
    // With a deliberately starved grid, the analytic hint should do at least as
    // well as the grid alone — that is the entire point of supplying it.
    expect(withAnalytic.expectedGrossProfit).toBeGreaterThanOrEqual(
      withoutAnalytic.expectedGrossProfit,
    );
  });
});
