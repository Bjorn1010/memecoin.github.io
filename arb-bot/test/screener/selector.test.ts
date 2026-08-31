import { describe, expect, it } from "vitest";
import { WatchlistSelector, DEFAULT_SELECTOR_CONFIG } from "../../src/screener/selector.js";
import { scorePool, rankPools, type PoolMetrics } from "../../src/screener/scorer.js";

function metrics(over: Partial<PoolMetrics> = {}): PoolMetrics {
  return {
    poolId: "pool",
    family: "raydium-cpmm",
    observationWindowMs: 3_600_000,
    opportunityCount: 0,
    netProfitableCount: 0,
    survivalMsP50: 0,
    vanishedBeforeWeCouldActCount: 0,
    netProfitMedianLamports: 0n,
    netProfitTotalLamports: 0n,
    usableDepthLamports: 0n,
    quoteErrors: 0,
    decodeErrors: 0,
    simulationFailures: 0,
    attempts: 0,
    landRate: 0,
    ...over,
  };
}

/** A pool that has never been watched: no data, so it scores zero. */
function unproven(poolId: string): ReturnType<typeof scorePool> {
  return scorePool(metrics({ poolId, observationWindowMs: 0 }));
}

function good(poolId: string, profit: bigint): ReturnType<typeof scorePool> {
  return scorePool(
    metrics({
      poolId,
      opportunityCount: 60,
      netProfitableCount: 40,
      survivalMsP50: 1_500,
      netProfitMedianLamports: profit,
      usableDepthLamports: 2_000_000_000n,
      landRate: 0.6,
      attempts: 20,
    }),
  );
}

describe("scorePool", () => {
  it("scores a pool with no data at zero and flags it", () => {
    const s = unproven("p");
    expect(s.score).toBe(0);
    expect(s.hasEnoughData).toBe(false);
  });

  it("rewards persistence, profit, frequency and depth", () => {
    expect(good("p", 2_000_000n).score).toBeGreaterThan(unproven("p").score);
  });

  it("penalises a pool whose opportunities vanish before we can act", () => {
    const contested = scorePool(
      metrics({
        poolId: "p",
        opportunityCount: 100,
        vanishedBeforeWeCouldActCount: 95,
        survivalMsP50: 50,
        netProfitMedianLamports: 2_000_000n,
      }),
    );
    const calm = scorePool(
      metrics({
        poolId: "p",
        opportunityCount: 100,
        vanishedBeforeWeCouldActCount: 2,
        survivalMsP50: 2_000,
        netProfitMedianLamports: 2_000_000n,
      }),
    );
    expect(contested.score).toBeLessThan(calm.score);
  });

  it("penalises unreliability, whether it shows up as errors or as failed sends", () => {
    const flaky = scorePool(
      metrics({ poolId: "p", opportunityCount: 50, quoteErrors: 40, netProfitMedianLamports: 1_000_000n }),
    );
    const clean = scorePool(
      metrics({ poolId: "p", opportunityCount: 50, netProfitMedianLamports: 1_000_000n }),
    );
    expect(flaky.score).toBeLessThan(clean.score);
  });

  it("explains itself", () => {
    expect(good("p", 1_000_000n).explanation).toMatch(/persist=.*profit=.*freq=/);
  });

  it("ranks pools with data ahead of pools without", () => {
    const ranked = rankPools([unproven("a"), good("b", 500_000n)]);
    expect(ranked[0]!.poolId).toBe("b");
  });
});

describe("WatchlistSelector", () => {
  const config = { ...DEFAULT_SELECTOR_CONFIG, maxWatched: 2, minResidencyMs: 1_000, cooldownMs: 60_000 };

  it("admits unproven pools into free slots — otherwise it can never bootstrap", () => {
    // This is the cold-start deadlock: a pool that has never been watched has
    // no observations, so it scores zero, so a score floor on entry would keep
    // it out forever and the watchlist would stay permanently empty.
    const s = new WatchlistSelector(config);
    const { watchlist, changes } = s.update([unproven("a"), unproven("b")], 0);
    expect(watchlist).toHaveLength(2);
    expect(changes.every((c) => c.action === "enter")).toBe(true);
    expect(changes[0]!.reason).toMatch(/trial/);
  });

  it("evicts a pool that failed to justify its trial, once residency has passed", () => {
    const s = new WatchlistSelector(config);
    s.update([unproven("a"), unproven("b")], 0);
    // Before residency elapses, nothing is evicted.
    expect(s.update([unproven("a"), unproven("b")], 500).watchlist).toHaveLength(2);
    const after = s.update([unproven("a"), unproven("b")], 5_000);
    expect(after.watchlist).toHaveLength(0);
    expect(after.changes.every((c) => c.action === "exit")).toBe(true);
  });

  it("keeps a pool that proved itself", () => {
    const s = new WatchlistSelector(config);
    s.update([unproven("a")], 0);
    const after = s.update([good("a", 3_000_000n)], 5_000);
    expect(after.watchlist.map((e) => e.poolId)).toContain("a");
  });

  it("does not churn on noise: a challenger must clear the margin", () => {
    const s = new WatchlistSelector({ ...config, entryMarginScore: 1.0 });
    s.update([good("a", 3_000_000n), good("b", 3_000_000n)], 0);
    const after = s.update(
      [good("a", 3_000_000n), good("b", 3_000_000n), good("c", 3_100_000n)],
      10_000,
    );
    expect(after.watchlist.map((e) => e.poolId).sort()).toEqual(["a", "b"]);
  });

  it("lets a clearly better challenger displace the weakest incumbent", () => {
    const s = new WatchlistSelector({ ...config, entryMarginScore: 0.01 });
    s.update([good("a", 100_000n), good("b", 100_000n)], 0);
    const after = s.update(
      [good("a", 100_000n), good("b", 100_000n), good("c", 5_000_000n)],
      10_000,
    );
    expect(after.watchlist.map((e) => e.poolId)).toContain("c");
    expect(after.watchlist).toHaveLength(2);
  });

  it("never evicts a pool still inside its grace period", () => {
    const s = new WatchlistSelector({ ...config, entryMarginScore: 0.01, minResidencyMs: 60_000 });
    s.update([good("a", 100_000n), good("b", 100_000n)], 0);
    const after = s.update(
      [good("a", 100_000n), good("b", 100_000n), good("c", 9_000_000n)],
      1_000,
    );
    expect(after.watchlist).toHaveLength(2);
    expect(after.watchlist.map((e) => e.poolId).sort()).toEqual(["a", "b"]);
  });

  it("does not re-admit a pool it just evicted", () => {
    // Eviction frees a slot, and the evicted pool is instantly the best
    // candidate for it. Without a cooldown the watchlist would churn forever
    // without ever changing.
    const s = new WatchlistSelector(config);
    s.update([unproven("a")], 0);
    s.update([unproven("a")], 5_000);
    expect(s.current()).toHaveLength(0);
    const immediately = s.update([unproven("a")], 5_001);
    expect(immediately.watchlist).toHaveLength(0);
    // Once the cooldown expires it may be tried again.
    const later = s.update([unproven("a")], 200_000);
    expect(later.watchlist.map((e) => e.poolId)).toEqual(["a"]);
  });

  it("records every entry and exit with a reason", () => {
    const s = new WatchlistSelector(config);
    s.update([unproven("a")], 0);
    s.update([], 5_000);
    const log = s.auditLog();
    expect(log).toHaveLength(1);
    expect(log[0]!.exitReason).toBeTruthy();
    expect(log[0]!.exitedAt).toBeGreaterThan(0);
  });

  it("can be told to drop a pool immediately, e.g. on a risk rejection", () => {
    const s = new WatchlistSelector(config);
    s.update([unproven("a")], 0);
    const change = s.evict("a", "token failed the risk filter", 10);
    expect(change?.action).toBe("exit");
    expect(s.current()).toHaveLength(0);
  });
});
