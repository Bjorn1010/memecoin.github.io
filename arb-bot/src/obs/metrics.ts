/**
 * In-process metrics.
 *
 * Deliberately answers the four questions from §49 rather than counting
 * everything: is the strategy bad, is the infrastructure too slow, is a quoter
 * wrong, or is inclusion too expensive? Each of those has a distinct counter
 * here, and the reject reasons are never merged into a single "skipped" total.
 */
import type { AttemptOutcome, RejectReason } from "../types.js";

export class Histogram {
  private readonly samples: number[] = [];
  private readonly cap: number;

  constructor(cap = 10_000) {
    this.cap = cap;
  }

  record(value: number): void {
    if (!Number.isFinite(value)) return;
    if (this.samples.length >= this.cap) this.samples.shift();
    this.samples.push(value);
  }

  get count(): number {
    return this.samples.length;
  }

  percentile(p: number): number {
    if (this.samples.length === 0) return 0;
    const sorted = [...this.samples].sort((a, b) => a - b);
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
    return sorted[index]!;
  }

  mean(): number {
    if (this.samples.length === 0) return 0;
    return this.samples.reduce((s, v) => s + v, 0) / this.samples.length;
  }

  summary(): { count: number; p50: number; p95: number; p99: number; mean: number } {
    return {
      count: this.count,
      p50: this.percentile(50),
      p95: this.percentile(95),
      p99: this.percentile(99),
      mean: this.mean(),
    };
  }
}

export class Metrics {
  readonly startedAt = Date.now();

  // --- funnel: never collapsed into one number (§6, §37) ---
  cyclesEvaluated = 0;
  cyclesGrossProfitable = 0;
  readonly rejects = new Map<RejectReason, number>();
  readonly outcomes = new Map<AttemptOutcome, number>();

  // --- money ---
  expectedNetPnl = 0n;
  realisedNetPnl = 0n;
  feesPaid = 0n;
  tipsPaid = 0n;
  readonly pnlByPool = new Map<string, bigint>();
  readonly pnlByFamilyPair = new Map<string, bigint>();

  // --- latency, the infrastructure question ---
  readonly detectionLatency = new Histogram();
  readonly decisionLatency = new Histogram();
  readonly sendLatency = new Histogram();
  readonly totalLatency = new Histogram();
  readonly stateAgeSlots = new Histogram();

  // --- correctness, the quoter question ---
  readonly quoteDivergenceBps = new Histogram();
  simulationFailures = 0;
  decodeFailures = 0;

  // --- infrastructure health ---
  rpcErrors = 0;
  feedReconnects = 0;

  // --- compute ---
  readonly computeUnits = new Histogram();

  reject(reason: RejectReason): void {
    this.rejects.set(reason, (this.rejects.get(reason) ?? 0) + 1);
  }

  outcome(kind: AttemptOutcome): void {
    this.outcomes.set(kind, (this.outcomes.get(kind) ?? 0) + 1);
  }

  addPoolPnl(poolId: string, delta: bigint): void {
    this.pnlByPool.set(poolId, (this.pnlByPool.get(poolId) ?? 0n) + delta);
  }

  addFamilyPairPnl(pair: string, delta: bigint): void {
    this.pnlByFamilyPair.set(pair, (this.pnlByFamilyPair.get(pair) ?? 0n) + delta);
  }

  /** Attempts that were actually sent, i.e. cost something or could have. */
  get sent(): number {
    return (
      (this.outcomes.get("sent-not-landed") ?? 0) +
      (this.outcomes.get("landed-profitable") ?? 0) +
      (this.outcomes.get("landed-unprofitable") ?? 0)
    );
  }

  get landed(): number {
    return (
      (this.outcomes.get("landed-profitable") ?? 0) + (this.outcomes.get("landed-unprofitable") ?? 0)
    );
  }

  /** Measured land rate for this run. Null until something has been sent. */
  get landRate(): number | null {
    return this.sent === 0 ? null : this.landed / this.sent;
  }

  uptimeMs(): number {
    return Date.now() - this.startedAt;
  }
}
