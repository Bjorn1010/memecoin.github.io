/**
 * Land-rate estimation from the bot's own ledger.
 *
 * The land rate is never a configured constant. It is estimated from observed
 * outcomes, segmented, with a hierarchical back-off so that a segment with two
 * observations borrows strength from its parent instead of producing a
 * confident nonsense number.
 *
 * Three outcomes are tracked separately because they cost different amounts
 * (see costs/fees.ts):
 *   success      -> we paid base + priority + tip, and earned the profit;
 *   reverted     -> included but failed: we paid base + priority, earned nothing;
 *   notIncluded  -> never landed: we paid nothing.
 *
 * The estimator is a Dirichlet-multinomial posterior mean. The prior is
 * deliberately pessimistic (most attempts assumed not to land) so that a new
 * segment has to earn its optimism with evidence.
 */

export type SendOutcome = "success" | "reverted" | "notIncluded";

export interface OutcomeCounts {
  success: number;
  reverted: number;
  notIncluded: number;
}

export interface LandRateEstimate {
  pSuccess: number;
  pReverted: number;
  pNotIncluded: number;
  /** Real observations backing this estimate at the level actually used. */
  samples: number;
  /** Which segment level produced it: 0 = most specific. */
  levelUsed: number;
  /** True when the estimate is the bare prior (no data at any level). */
  priorOnly: boolean;
}

export interface LandRateConfig {
  /**
   * Prior counts. `priorStrength` is spread over the three outcomes using
   * `priorSuccessShare`; the rest is split between reverted and notIncluded.
   * A larger strength means more evidence is needed to move off the prior.
   */
  priorStrength: number;
  priorSuccessShare: number;
  priorRevertedShare: number;
  /** Below this many observations, back off to a less specific segment. */
  minSamplesPerSegment: number;
}

export const DEFAULT_LAND_RATE_CONFIG: LandRateConfig = {
  // 20 pseudo-observations: 1 success, 4 reverted, 15 not included.
  // Pessimistic on purpose — see module docstring.
  priorStrength: 20,
  priorSuccessShare: 0.05,
  priorRevertedShare: 0.2,
  minSamplesPerSegment: 25,
};

/**
 * A segment key, most specific component first. `estimate` walks this list from
 * the full key down to the empty (global) key, stopping at the first level with
 * enough observations.
 *
 * Typical key: [poolPair, familyPair, profitBucket, senderKind, hourOfDay].
 */
export type SegmentKey = readonly string[];

function keyOf(parts: SegmentKey): string {
  return parts.join("|");
}

export function emptyCounts(): OutcomeCounts {
  return { success: 0, reverted: 0, notIncluded: 0 };
}

export function totalOf(c: OutcomeCounts): number {
  return c.success + c.reverted + c.notIncluded;
}

export class LandRateEstimator {
  private readonly counts = new Map<string, OutcomeCounts>();

  constructor(private readonly config: LandRateConfig = DEFAULT_LAND_RATE_CONFIG) {}

  /**
   * Record an outcome. The observation is credited to the full key and to every
   * prefix of it, so parents aggregate their children automatically.
   */
  record(segment: SegmentKey, outcome: SendOutcome): void {
    for (let n = segment.length; n >= 0; n--) {
      const k = keyOf(segment.slice(0, n));
      let c = this.counts.get(k);
      if (!c) {
        c = emptyCounts();
        this.counts.set(k, c);
      }
      c[outcome] += 1;
    }
  }

  /** Raw observations at exactly this segment level (no back-off). */
  rawCounts(segment: SegmentKey): OutcomeCounts {
    return this.counts.get(keyOf(segment)) ?? emptyCounts();
  }

  estimate(segment: SegmentKey): LandRateEstimate {
    const { minSamplesPerSegment } = this.config;
    for (let n = segment.length; n >= 0; n--) {
      const c = this.counts.get(keyOf(segment.slice(0, n)));
      const total = c ? totalOf(c) : 0;
      const isGlobal = n === 0;
      if (c && (total >= minSamplesPerSegment || isGlobal)) {
        return {
          ...this.posterior(c),
          samples: total,
          levelUsed: segment.length - n,
          priorOnly: total === 0,
        };
      }
    }
    return {
      ...this.posterior(emptyCounts()),
      samples: 0,
      levelUsed: segment.length,
      priorOnly: true,
    };
  }

  private posterior(c: OutcomeCounts): Pick<
    LandRateEstimate,
    "pSuccess" | "pReverted" | "pNotIncluded"
  > {
    const { priorStrength, priorSuccessShare, priorRevertedShare } = this.config;
    const aS = priorStrength * priorSuccessShare;
    const aR = priorStrength * priorRevertedShare;
    const aN = priorStrength * (1 - priorSuccessShare - priorRevertedShare);
    const denom = priorStrength + totalOf(c);
    return {
      pSuccess: (aS + c.success) / denom,
      pReverted: (aR + c.reverted) / denom,
      pNotIncluded: (aN + c.notIncluded) / denom,
    };
  }

  /** Serialise for the ledger so estimates survive a restart. */
  snapshot(): Record<string, OutcomeCounts> {
    return Object.fromEntries(this.counts);
  }

  restore(snapshot: Record<string, OutcomeCounts>): void {
    this.counts.clear();
    for (const [k, v] of Object.entries(snapshot)) {
      this.counts.set(k, { ...v });
    }
  }
}

/**
 * Bucket a profit figure so segments stay coarse enough to accumulate data.
 * Powers of two of 10 000 lamports, capped, so the label set stays small.
 */
export function profitBucket(lamports: bigint): string {
  if (lamports <= 0n) return "p<=0";
  const unit = 10_000n;
  let bucket = 0;
  let edge = unit;
  while (lamports >= edge && bucket < 12) {
    edge *= 2n;
    bucket++;
  }
  return `p${bucket}`;
}

/** Coarse latency bucket in milliseconds, for the same reason. */
export function latencyBucket(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "lNA";
  const edges = [50, 100, 200, 400, 800, 1600, 3200];
  for (let i = 0; i < edges.length; i++) {
    if (ms < edges[i]!) return `l${i}`;
  }
  return `l${edges.length}`;
}

export function hourBucket(timestampMs: number): string {
  return `h${new Date(timestampMs).getUTCHours()}`;
}
