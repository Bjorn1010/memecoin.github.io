import { describe, expect, it } from "vitest";
import {
  computeTransactionCosts,
  decideTip,
  lockedCapital,
  priorityFeeLamports,
  type ClusterFeeParams,
} from "../../src/costs/fees.js";
import { breakEvenGrossProfit, profitNet } from "../../src/costs/profitNet.js";
import {
  DEFAULT_LAND_RATE_CONFIG,
  LandRateEstimator,
  latencyBucket,
  profitBucket,
} from "../../src/costs/landRate.js";

const CLUSTER: ClusterFeeParams = {
  lamportsPerSignature: 5_000n,
  tokenAccountRentLamports: 2_039_280n,
  slot: 1_000,
};

function costs(
  over: { cuLimit?: number; cuPrice?: bigint; tip?: bigint; revertCostsFees?: boolean } = {},
) {
  return computeTransactionCosts({
    cluster: CLUSTER,
    numSignatures: 1,
    computeUnitLimit: over.cuLimit ?? 200_000,
    computeUnitPriceMicroLamports: over.cuPrice ?? 10_000n,
    tipLamports: over.tip ?? 0n,
    revertCostsFees: over.revertCostsFees ?? true,
  });
}

/** A land rate estimate with the given success probability. */
function landRate(pSuccess: number, pReverted = 0.1) {
  return {
    pSuccess,
    pReverted,
    pNotIncluded: Math.max(0, 1 - pSuccess - pReverted),
    samples: 500,
    levelUsed: 0,
    priorOnly: false,
  };
}

describe("priority fee", () => {
  it("is a ceiling division of CU limit times CU price", () => {
    // 200 000 CU at 10 000 micro-lamports = 2e9 micro-lamports = 2000 lamports.
    expect(priorityFeeLamports(200_000, 10_000n)).toBe(2_000n);
    // Anything with a remainder rounds UP.
    expect(priorityFeeLamports(1, 1n)).toBe(1n);
    expect(priorityFeeLamports(999_999, 1n)).toBe(1n);
    expect(priorityFeeLamports(1_000_001, 1n)).toBe(2n);
  });

  it("is zero when either factor is zero", () => {
    expect(priorityFeeLamports(0, 10_000n)).toBe(0n);
    expect(priorityFeeLamports(200_000, 0n)).toBe(0n);
  });
});

describe("transaction costs distinguish the three outcomes", () => {
  it("charges the tip only on success, and nothing at all when not included", () => {
    const c = costs({ tip: 50_000n });
    expect(c.baseFee).toBe(5_000n);
    expect(c.priorityFee).toBe(2_000n);
    expect(c.onSuccess).toBe(57_000n);
    // A reverted transaction still pays fees but the tip transfer reverts too.
    expect(c.onRevert).toBe(7_000n);
    // A transaction that never lands costs nothing: fees are only charged on
    // inclusion. Getting this wrong makes every EV pessimistic.
    expect(c.onNotIncluded).toBe(0n);
  });

  it("scales the base fee with the signature count", () => {
    const c = computeTransactionCosts({
      cluster: CLUSTER,
      numSignatures: 2,
      computeUnitLimit: 0,
      computeUnitPriceMicroLamports: 0n,
      tipLamports: 0n,
      revertCostsFees: true,
    });
    expect(c.baseFee).toBe(10_000n);
  });

  it("charges nothing on a failure when the transport drops failed attempts", () => {
    // A Jito bundle that does not fully succeed is never included, so a failed
    // attempt is free. That single bit is what makes a low land rate survivable.
    const bundled = costs({ tip: 50_000n, revertCostsFees: false });
    expect(bundled.onRevert).toBe(0n);
    expect(bundled.onSuccess).toBe(57_000n);
  });

  it("free failures turn a rejected opportunity into a viable one", () => {
    const landing = landRate(0.05, 0.7);
    const shared = {
      grossProfit: 300_000n,
      landRate: landing,
      minProfitLamports: 10_000n,
      minExpectedValueLamports: 0n,
    };
    const viaRpc = profitNet({ ...shared, costs: costs({ revertCostsFees: true }) });
    const viaBundle = profitNet({ ...shared, costs: costs({ revertCostsFees: false }) });
    expect(viaRpc.expectedValue).toBeLessThan(viaBundle.expectedValue);
    expect(viaBundle.expectedCostPerSuccess).toBeLessThan(viaRpc.expectedCostPerSuccess);
  });
});

describe("locked capital is capital, not cost", () => {
  it("counts one rent per token account we keep open", () => {
    const l = lockedCapital(CLUSTER, 3);
    expect(l.wsolAccountRent).toBe(2_039_280n);
    expect(l.intermediateAccountRent).toBe(6_117_840n);
    expect(l.total).toBe(8_157_120n);
  });
});

describe("profitNet", () => {
  const minProfit = 10_000n;
  const minEv = 0n;

  it("accepts a trade that is profitable gross AND net AND in expectation", () => {
    const r = profitNet({
      grossProfit: 200_000n,
      costs: costs({ tip: 20_000n }),
      landRate: landRate(0.5),
      minProfitLamports: minProfit,
      minExpectedValueLamports: minEv,
    });
    expect(r.netProfitIfLanded).toBe(200_000n - 27_000n);
    expect(r.shouldTrade).toBe(true);
    expect(r.reason).toBe("ok");
    expect(r.expectedValue).toBeGreaterThan(0n);
  });

  it("rejects gross-positive but net-negative (the classic trap)", () => {
    const r = profitNet({
      grossProfit: 5_000n, // less than the 7 000 of base + priority
      costs: costs(),
      landRate: landRate(0.9),
      minProfitLamports: minProfit,
      minExpectedValueLamports: minEv,
    });
    expect(r.grossProfit).toBeGreaterThan(0n);
    expect(r.netProfitIfLanded).toBeLessThan(0n);
    expect(r.shouldTrade).toBe(false);
    expect(r.reason).toBe("not-profitable-net");
  });

  it("rejects net-positive but below the minimum profit floor", () => {
    const r = profitNet({
      grossProfit: 12_000n, // net 5 000, floor is 10 000
      costs: costs(),
      landRate: landRate(0.9),
      minProfitLamports: minProfit,
      minExpectedValueLamports: minEv,
    });
    expect(r.netProfitIfLanded).toBe(5_000n);
    expect(r.reason).toBe("below-min-profit");
  });

  it("rejects a healthy trade when the land rate makes the EV negative (§16)", () => {
    // Net profit 13 000 if it lands, but it lands 1% of the time and reverts
    // 60% of the time paying 7 000 each. EV = 0.01*13000 - 0.6*7000 < 0.
    const r = profitNet({
      grossProfit: 20_000n,
      costs: costs(),
      landRate: landRate(0.01, 0.6),
      minProfitLamports: minProfit,
      minExpectedValueLamports: minEv,
    });
    expect(r.netProfitIfLanded).toBeGreaterThan(minProfit);
    expect(r.expectedValue).toBeLessThan(0n);
    expect(r.shouldTrade).toBe(false);
    expect(r.reason).toBe("negative-expected-value");
  });

  it("a high revert rate is more damaging than a high drop rate", () => {
    const base = { grossProfit: 100_000n, costs: costs(), minProfitLamports: minProfit, minExpectedValueLamports: minEv };
    const dropped = profitNet({ ...base, landRate: landRate(0.2, 0.0) });
    const reverting = profitNet({ ...base, landRate: landRate(0.2, 0.8) });
    // Same success probability; the reverting case burns fees on every miss.
    expect(reverting.expectedValue).toBeLessThan(dropped.expectedValue);
  });

  it("reports the true cost of a success including the failures paid for", () => {
    const r = profitNet({
      grossProfit: 100_000n,
      costs: costs(),
      landRate: landRate(0.1, 0.5),
      minProfitLamports: minProfit,
      minExpectedValueLamports: minEv,
    });
    // 5 reverts per success at 7 000 each, plus the 7 000 of the success.
    expect(r.expectedCostPerSuccess).toBe(7_000n + 35_000n);
  });

  it("never trades on a zero or negative gross profit", () => {
    for (const gross of [0n, -1n, -1_000_000n]) {
      const r = profitNet({
        grossProfit: gross,
        costs: costs(),
        landRate: landRate(0.99, 0),
        minProfitLamports: 0n,
        minExpectedValueLamports: 0n,
      });
      expect(r.shouldTrade).toBe(false);
      expect(r.reason).toBe("not-profitable-gross");
    }
  });
});

describe("breakEvenGrossProfit", () => {
  it("rises as the land rate falls", () => {
    const args = {
      costs: costs(),
      minProfitLamports: 10_000n,
      minExpectedValueLamports: 1_000n,
    };
    const good = breakEvenGrossProfit({ ...args, landRate: landRate(0.8, 0.1) });
    const bad = breakEvenGrossProfit({ ...args, landRate: landRate(0.05, 0.5) });
    expect(bad).toBeGreaterThan(good);
  });

  it("is a real bar: a gross profit just under it is rejected", () => {
    const landing = landRate(0.3, 0.4);
    const args = {
      costs: costs(),
      landRate: landing,
      minProfitLamports: 10_000n,
      minExpectedValueLamports: 1_000n,
    };
    const bar = breakEvenGrossProfit(args);
    const under = profitNet({ ...args, grossProfit: bar - 1n });
    expect(under.shouldTrade).toBe(false);
    const over = profitNet({ ...args, grossProfit: bar + 1_000n });
    expect(over.shouldTrade).toBe(true);
  });
});

describe("tip policy", () => {
  const policy = {
    minTipLamports: 1_000n,
    maxTipLamports: 100_000n,
    maxTipShareBps: 3_000n, // 30%
    minProfitLamports: 10_000n,
  };

  it("takes the configured share when everything fits", () => {
    const d = decideTip({ grossProfit: 200_000n, baseFee: 5_000n, priorityFee: 2_000n, policy });
    // profitBeforeTip = 193 000; 30% = 57 900.
    expect(d.tipLamports).toBe(57_900n);
    expect(d.profitAfterTip).toBe(135_100n);
    expect(d.viable).toBe(true);
  });

  it("never tips more than the profit floor allows", () => {
    const d = decideTip({ grossProfit: 25_000n, baseFee: 5_000n, priorityFee: 2_000n, policy });
    // profitBeforeTip = 18 000, floor 10 000 -> at most 8 000 of headroom.
    expect(d.tipLamports).toBeLessThanOrEqual(8_000n);
    expect(d.profitAfterTip).toBeGreaterThanOrEqual(10_000n);
    expect(d.viable).toBe(true);
  });

  it("respects the absolute ceiling", () => {
    const d = decideTip({ grossProfit: 10_000_000n, baseFee: 5_000n, priorityFee: 2_000n, policy });
    expect(d.tipLamports).toBe(100_000n);
  });

  it("refuses the opportunity when the floor tip would break the profit floor", () => {
    const tightPolicy = { ...policy, minTipLamports: 50_000n };
    const d = decideTip({ grossProfit: 25_000n, baseFee: 5_000n, priorityFee: 2_000n, policy: tightPolicy });
    expect(d.viable).toBe(false);
    expect(d.reason).toBe("profit-below-floor-after-tip");
  });

  it("refuses before tipping at all when costs already eat the profit", () => {
    const d = decideTip({ grossProfit: 8_000n, baseFee: 5_000n, priorityFee: 2_000n, policy });
    expect(d.viable).toBe(false);
    expect(d.reason).toBe("profit-below-floor-before-tip");
    expect(d.tipLamports).toBe(0n);
  });
});

describe("LandRateEstimator", () => {
  it("starts pessimistic and says so", () => {
    const e = new LandRateEstimator();
    const est = e.estimate(["poolA", "famX"]);
    expect(est.priorOnly).toBe(true);
    expect(est.pSuccess).toBeCloseTo(DEFAULT_LAND_RATE_CONFIG.priorSuccessShare, 6);
  });

  it("moves toward the evidence as observations accumulate", () => {
    const e = new LandRateEstimator();
    for (let i = 0; i < 500; i++) e.record(["poolA", "famX"], "success");
    const est = e.estimate(["poolA", "famX"]);
    expect(est.pSuccess).toBeGreaterThan(0.9);
    expect(est.priorOnly).toBe(false);
    expect(est.levelUsed).toBe(0);
  });

  it("backs off to the parent segment when the child is too sparse", () => {
    const e = new LandRateEstimator();
    // Plenty of data on the parent, almost none on this specific child.
    for (let i = 0; i < 200; i++) e.record(["poolB", "other"], "success");
    e.record(["poolB", "rare"], "reverted");
    const est = e.estimate(["poolB", "rare"]);
    expect(est.levelUsed).toBeGreaterThan(0);
    expect(est.samples).toBeGreaterThan(100);
    expect(est.pSuccess).toBeGreaterThan(0.5);
  });

  it("aggregates children into every prefix automatically", () => {
    const e = new LandRateEstimator();
    e.record(["p", "f", "b"], "success");
    e.record(["p", "f", "c"], "reverted");
    expect(e.rawCounts(["p"])).toEqual({ success: 1, reverted: 1, notIncluded: 0 });
    expect(e.rawCounts(["p", "f", "b"])).toEqual({ success: 1, reverted: 0, notIncluded: 0 });
  });

  it("survives a restart through snapshot/restore", () => {
    const a = new LandRateEstimator();
    for (let i = 0; i < 100; i++) a.record(["x"], "notIncluded");
    const b = new LandRateEstimator();
    b.restore(a.snapshot());
    expect(b.estimate(["x"])).toEqual(a.estimate(["x"]));
  });

  it("keeps probabilities normalised", () => {
    const e = new LandRateEstimator();
    e.record(["z"], "success");
    e.record(["z"], "reverted");
    e.record(["z"], "notIncluded");
    const est = e.estimate(["z"]);
    expect(est.pSuccess + est.pReverted + est.pNotIncluded).toBeCloseTo(1, 9);
  });
});

describe("bucketing keeps segments coarse enough to learn", () => {
  it("buckets profit by powers of two and caps the label set", () => {
    expect(profitBucket(-5n)).toBe("p<=0");
    expect(profitBucket(1n)).toBe("p0");
    expect(profitBucket(10_000n)).toBe("p1");
    expect(profitBucket(10n ** 18n)).toBe("p12");
  });

  it("buckets latency into a small number of bands", () => {
    expect(latencyBucket(10)).toBe("l0");
    expect(latencyBucket(150)).toBe("l2");
    expect(latencyBucket(99_999)).toBe("l7");
    expect(latencyBucket(Number.NaN)).toBe("lNA");
  });
});
