/**
 * Pool scoring.
 *
 * The screener runs off the critical path and answers one question: which pools
 * deserve one of our scarce WebSocket subscriptions? It scores them from
 * measurements the observer collected, never from intuition about which DEX is
 * "hot".
 *
 * The score is deliberately explainable: `scorePool` returns every normalised
 * component and its weighted contribution, so an operator can see *why* a pool
 * ranks where it does and can recalibrate the weights against realised PnL
 * rather than trusting an opaque number (§23).
 */

export interface PoolMetrics {
  poolId: string;
  family: string;
  /** How long we have been watching, in ms. Zero means no data. */
  observationWindowMs: number;

  // --- frequency ---
  /** Distinct opportunities seen (gross-profitable, before costs). */
  opportunityCount: number;
  /** Of those, how many still cleared the bar after all costs. */
  netProfitableCount: number;

  // --- persistence / competition ---
  /**
   * Median lifetime of an opportunity: from first observed to the moment the
   * price gap closed. This is the number that decides whether our latency is
   * even in the game.
   */
  survivalMsP50: number;
  /** Opportunities that vanished faster than our own decision latency. */
  vanishedBeforeWeCouldActCount: number;

  // --- profit ---
  /** Median net profit of the net-profitable opportunities, in lamports. */
  netProfitMedianLamports: bigint;
  /** Sum of net profit across the window, in lamports. */
  netProfitTotalLamports: bigint;

  // --- liquidity ---
  /**
   * Depth actually available at the profitable trade size, in base-asset
   * lamports. Not TVL: a deep pool that only supports a dust-sized profitable
   * trade is worthless to us.
   */
  usableDepthLamports: bigint;

  // --- reliability ---
  quoteErrors: number;
  decodeErrors: number;
  simulationFailures: number;
  /** Attempts actually sent from this pool, for the failure rate. */
  attempts: number;
  /** Measured probability that a send on this pool lands and succeeds. */
  landRate: number;
}

export interface ScoreWeights {
  persistence: number;
  netProfit: number;
  frequency: number;
  liquidity: number;
  competition: number;
  failureRate: number;
}

/**
 * Starting weights.
 *
 * These are a STARTING POINT, not an optimum: no data existed when they were
 * written. `npm run report` prints realised PnL per pool alongside the score
 * that pool had, which is the input for recalibrating them. Treat any claim
 * that these are tuned as false until that comparison has been run.
 */
export const DEFAULT_SCORE_WEIGHTS: ScoreWeights = {
  persistence: 1.0,
  netProfit: 1.5,
  frequency: 1.0,
  liquidity: 0.5,
  competition: 1.5,
  failureRate: 1.0,
};

export interface ScoreNormalisation {
  /** Survival time at which persistence scores 1.0. */
  survivalMsFull: number;
  /** Opportunities per hour at which frequency scores 1.0. */
  opportunitiesPerHourFull: number;
  /** Median net profit at which the profit component scores 1.0. */
  netProfitFullLamports: bigint;
  /** Usable depth at which liquidity scores 1.0. */
  usableDepthFullLamports: bigint;
}

export const DEFAULT_NORMALISATION: ScoreNormalisation = {
  survivalMsFull: 2_000,
  opportunitiesPerHourFull: 20,
  netProfitFullLamports: 1_000_000n, // 0.001 SOL
  usableDepthFullLamports: 1_000_000_000n, // 1 SOL
};

export interface ScoreComponent {
  /** Normalised to [0, 1]. */
  value: number;
  weight: number;
  /** value * weight, signed: penalties are negative. */
  contribution: number;
}

export interface PoolScore {
  poolId: string;
  score: number;
  components: {
    persistence: ScoreComponent;
    netProfit: ScoreComponent;
    frequency: ScoreComponent;
    liquidity: ScoreComponent;
    competition: ScoreComponent;
    failureRate: ScoreComponent;
  };
  /** Human-readable reason, logged on every watchlist change. */
  explanation: string;
  /** False when the window is too short for the score to mean anything. */
  hasEnoughData: boolean;
}

function saturate(value: number, full: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  if (full <= 0) return 0;
  const r = value / full;
  return r >= 1 ? 1 : r;
}

function saturateBig(value: bigint, full: bigint): number {
  if (value <= 0n || full <= 0n) return 0;
  if (value >= full) return 1;
  // Scale through Number only after bounding the ratio to [0, 1].
  return Number((value * 1_000_000n) / full) / 1_000_000;
}

export interface ScoreOptions {
  weights?: ScoreWeights;
  normalisation?: ScoreNormalisation;
  /** Below this many observations the score is reported but flagged. */
  minObservations?: number;
}

export function scorePool(m: PoolMetrics, options: ScoreOptions = {}): PoolScore {
  const weights = options.weights ?? DEFAULT_SCORE_WEIGHTS;
  const norm = options.normalisation ?? DEFAULT_NORMALISATION;
  const minObservations = options.minObservations ?? 10;

  const hours = m.observationWindowMs / 3_600_000;
  const opportunitiesPerHour = hours > 0 ? m.opportunityCount / hours : 0;

  const persistence = saturate(m.survivalMsP50, norm.survivalMsFull);
  const netProfit = saturateBig(m.netProfitMedianLamports, norm.netProfitFullLamports);
  const frequency = saturate(opportunitiesPerHour, norm.opportunitiesPerHourFull);
  const liquidity = saturateBig(m.usableDepthLamports, norm.usableDepthFullLamports);

  // Competition: the share of opportunities that were gone before we could act.
  const competition =
    m.opportunityCount > 0 ? m.vanishedBeforeWeCouldActCount / m.opportunityCount : 0;

  // Reliability: anything that made this pool unusable when we tried to use it.
  const reliabilityDenominator = m.opportunityCount + m.attempts;
  const failures = m.quoteErrors + m.decodeErrors + m.simulationFailures;
  const failureFromErrors =
    reliabilityDenominator > 0 ? failures / reliabilityDenominator : 0;
  const failureFromLanding = m.attempts > 0 ? 1 - m.landRate : 0;
  const failureRate = Math.min(1, Math.max(failureFromErrors, failureFromLanding));

  const components = {
    persistence: comp(persistence, weights.persistence, 1),
    netProfit: comp(netProfit, weights.netProfit, 1),
    frequency: comp(frequency, weights.frequency, 1),
    liquidity: comp(liquidity, weights.liquidity, 1),
    competition: comp(competition, weights.competition, -1),
    failureRate: comp(failureRate, weights.failureRate, -1),
  };

  const score = Object.values(components).reduce((s, c) => s + c.contribution, 0);

  const explanation = [
    `persist=${persistence.toFixed(2)}(${m.survivalMsP50}ms)`,
    `profit=${netProfit.toFixed(2)}(${m.netProfitMedianLamports})`,
    `freq=${frequency.toFixed(2)}(${opportunitiesPerHour.toFixed(1)}/h)`,
    `liq=${liquidity.toFixed(2)}`,
    `-compet=${competition.toFixed(2)}`,
    `-fail=${failureRate.toFixed(2)}`,
  ].join(" ");

  return {
    poolId: m.poolId,
    score,
    components,
    explanation,
    hasEnoughData: m.opportunityCount >= minObservations && m.observationWindowMs > 0,
  };
}

function comp(value: number, weight: number, sign: 1 | -1): ScoreComponent {
  return { value, weight, contribution: sign * value * weight };
}

/** Rank pools best-first. Pools without enough data sort last, not first. */
export function rankPools(scores: readonly PoolScore[]): PoolScore[] {
  return [...scores].sort((a, b) => {
    if (a.hasEnoughData !== b.hasEnoughData) return a.hasEnoughData ? -1 : 1;
    return b.score - a.score;
  });
}
