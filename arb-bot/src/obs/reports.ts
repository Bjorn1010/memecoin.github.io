/**
 * Reports.
 *
 * Everything printed here exists to answer one of the four questions from §49:
 *   - why could this bot lose money?
 *   - is the problem the strategy or the infrastructure?
 *   - what number says stop trading?
 *   - what number says a better RPC is worth paying for?
 *
 * So the funnel is never collapsed: an opportunity that was never sent, one
 * abandoned at simulation, one sent that never landed, and one that landed and
 * lost money are four different diagnoses with four different fixes.
 */
import type { RpcBudgetStats } from "../rpc/RpcBudget.js";
import type { Metrics } from "./metrics.js";
import { readJsonl, type AttemptRecord, type ObservationRecord } from "./ledger.js";
import { lamportsToSolString } from "../util/bigintMath.js";

export function renderRunSummary(
  m: Metrics,
  budget: RpcBudgetStats,
  paths: { attempts: string; observations: string },
): string {
  const lines: string[] = [];
  const uptimeMin = (m.uptimeMs() / 60_000).toFixed(1);
  lines.push(`\n=== run summary (${uptimeMin} min) ===`);

  lines.push(
    `funnel: ${m.cyclesEvaluated} cycles evaluated -> ${m.cyclesGrossProfitable} gross profitable -> ${m.sent} sent -> ${m.landed} landed`,
  );
  if (m.rejects.size > 0) {
    const sorted = [...m.rejects.entries()].sort((a, b) => b[1] - a[1]);
    lines.push("rejects:");
    for (const [reason, n] of sorted) lines.push(`  ${String(n).padStart(7)}  ${reason}`);
  }
  if (m.outcomes.size > 0) {
    lines.push("outcomes:");
    for (const [outcome, n] of m.outcomes) lines.push(`  ${String(n).padStart(7)}  ${outcome}`);
  }

  const landRate = m.landRate;
  lines.push(
    `land rate: ${landRate === null ? "n/a (nothing sent)" : `${(landRate * 100).toFixed(1)}% over ${m.sent} sends`}`,
  );
  lines.push(
    `PnL: expected ${lamportsToSolString(m.expectedNetPnl)} SOL, realised ${lamportsToSolString(m.realisedNetPnl)} SOL ` +
      `(fees ${lamportsToSolString(m.feesPaid)}, tips ${lamportsToSolString(m.tipsPaid)})`,
  );

  const latency = m.totalLatency.summary();
  const detection = m.detectionLatency.summary();
  lines.push(
    `latency: state age p50 ${detection.p50.toFixed(0)}ms p95 ${detection.p95.toFixed(0)}ms p99 ${detection.p99.toFixed(0)}ms` +
      (latency.count > 0 ? `, total p50 ${latency.p50.toFixed(0)}ms p95 ${latency.p95.toFixed(0)}ms` : ""),
  );

  const cu = m.computeUnits.summary();
  if (cu.count > 0) {
    lines.push(`compute units: p50 ${cu.p50.toFixed(0)} p95 ${cu.p95.toFixed(0)} p99 ${cu.p99.toFixed(0)}`);
  }

  const div = m.quoteDivergenceBps.summary();
  if (div.count > 0) {
    lines.push(
      `quote vs simulation: p50 ${div.p50.toFixed(2)} bps, p95 ${div.p95.toFixed(2)} bps, max sample count ${div.count}`,
    );
  }

  lines.push(
    `rpc: ${budget.granted} granted, ${budget.rejected} rejected, ${budget.rateLimitHits} rate limits, ${m.rpcErrors} errors, ${m.simulationFailures} simulation failures`,
  );
  lines.push(`feed: ${m.feedReconnects} reconnects/stalls`);

  if (m.pnlByPool.size > 0) {
    lines.push("PnL by pool:");
    for (const [pool, pnl] of [...m.pnlByPool.entries()].sort((a, b) => (b[1] > a[1] ? 1 : -1))) {
      lines.push(`  ${lamportsToSolString(pnl).padStart(14)} SOL  ${pool}`);
    }
  }
  if (m.pnlByFamilyPair.size > 0) {
    lines.push("PnL by venue pair:");
    for (const [pair, pnl] of m.pnlByFamilyPair) {
      lines.push(`  ${lamportsToSolString(pnl).padStart(14)} SOL  ${pair}`);
    }
  }

  lines.push(`ledger: ${paths.attempts}`);
  lines.push(`observations: ${paths.observations}`);
  return lines.join("\n");
}

export interface ObserveReport {
  totalOpportunities: number;
  survivedByDelay: Record<number, number>;
  grossProfitable: number;
  netProfitable: number;
  medianGrossProfitLamports: bigint;
  byPool: Map<string, { count: number; totalGross: bigint; survived200ms: number }>;
  latencyCeilingMs: number | null;
}

/**
 * The report `--observe` exists to produce. It answers §25's ten questions from
 * the recorded observations, not from an estimate.
 */
export function buildObserveReport(observationsPath: string): ObserveReport {
  const records = readJsonl<ObservationRecord>(observationsPath);
  const survivedByDelay: Record<number, number> = {};
  const byPool = new Map<string, { count: number; totalGross: bigint; survived200ms: number }>();
  const grossProfits: bigint[] = [];

  for (const r of records) {
    const gross = BigInt(r.grossProfit);
    grossProfits.push(gross);
    for (const s of r.survival) {
      if (s.stillProfitable) survivedByDelay[s.afterMs] = (survivedByDelay[s.afterMs] ?? 0) + 1;
    }
    const key = `${r.buyPoolId}:${r.sellPoolId}`;
    const entry = byPool.get(key) ?? { count: 0, totalGross: 0n, survived200ms: 0 };
    entry.count++;
    entry.totalGross += gross;
    if (r.survival.find((s) => s.afterMs === 200)?.stillProfitable) entry.survived200ms++;
    byPool.set(key, entry);
  }

  // The longest delay at which at least a tenth of opportunities still exist is
  // the practical ceiling on our end-to-end latency.
  let latencyCeilingMs: number | null = null;
  const delays = Object.keys(survivedByDelay)
    .map(Number)
    .sort((a, b) => a - b);
  for (const d of delays) {
    if (records.length > 0 && (survivedByDelay[d] ?? 0) / records.length >= 0.1) latencyCeilingMs = d;
  }

  return {
    totalOpportunities: records.length,
    survivedByDelay,
    grossProfitable: grossProfits.filter((g) => g > 0n).length,
    netProfitable: grossProfits.filter((g) => g > 0n).length,
    medianGrossProfitLamports: medianBigint(grossProfits),
    byPool,
    latencyCeilingMs,
  };
}

export function renderObserveReport(report: ObserveReport): string {
  const lines: string[] = ["=== observation report ==="];
  lines.push(`opportunities recorded: ${report.totalOpportunities}`);
  if (report.totalOpportunities === 0) {
    lines.push("");
    lines.push("No opportunities were recorded. That is itself the answer: at this latency,");
    lines.push("on these pools, there was nothing to take. Widen the watchlist or accept that");
    lines.push("this segment is not tradable from here.");
    return lines.join("\n");
  }

  lines.push(`median gross profit: ${lamportsToSolString(report.medianGrossProfitLamports)} SOL`);
  lines.push("survival after detection:");
  for (const delay of Object.keys(report.survivedByDelay).map(Number).sort((a, b) => a - b)) {
    const n = report.survivedByDelay[delay] ?? 0;
    const pct = ((n / report.totalOpportunities) * 100).toFixed(1);
    lines.push(`  +${String(delay).padStart(5)}ms  ${String(n).padStart(6)}  ${pct}%`);
  }
  lines.push(
    `practical latency ceiling: ${report.latencyCeilingMs === null ? "under 200ms — this segment is a speed game we cannot win" : `${report.latencyCeilingMs}ms`}`,
  );

  lines.push("by pool pair:");
  const ranked = [...report.byPool.entries()].sort((a, b) => (b[1].totalGross > a[1].totalGross ? 1 : -1));
  for (const [pair, s] of ranked.slice(0, 20)) {
    lines.push(
      `  ${lamportsToSolString(s.totalGross).padStart(14)} SOL  ${String(s.count).padStart(5)} opps  ` +
        `${((s.survived200ms / s.count) * 100).toFixed(0)}% survive 200ms  ${pair}`,
    );
  }
  return lines.join("\n");
}

/** Aggregate a ledger of attempts into the §37 view. */
export function renderAttemptReport(attemptsPath: string): string {
  const records = readJsonl<AttemptRecord>(attemptsPath);
  if (records.length === 0) return "no attempts recorded";

  const byOutcome = new Map<string, number>();
  const byReject = new Map<string, number>();
  let expected = 0n;
  let realised = 0n;
  const divergences: number[] = [];

  for (const r of records) {
    byOutcome.set(r.outcome, (byOutcome.get(r.outcome) ?? 0) + 1);
    if (r.rejectReason) byReject.set(r.rejectReason, (byReject.get(r.rejectReason) ?? 0) + 1);
    expected += BigInt(r.expectedNetProfit || "0");
    if (r.actualProfit) realised += BigInt(r.actualProfit);
    if (r.quoteDivergenceBps !== null) divergences.push(r.quoteDivergenceBps);
  }

  const lines = [`=== attempts (${records.length}) ===`];
  for (const [outcome, n] of byOutcome) lines.push(`  ${String(n).padStart(7)}  ${outcome}`);
  if (byReject.size > 0) {
    lines.push("rejects:");
    for (const [reason, n] of [...byReject.entries()].sort((a, b) => b[1] - a[1])) {
      lines.push(`  ${String(n).padStart(7)}  ${reason}`);
    }
  }
  lines.push(`expected net PnL: ${lamportsToSolString(expected)} SOL`);
  lines.push(`realised net PnL: ${lamportsToSolString(realised)} SOL`);
  if (divergences.length > 0) {
    const sorted = [...divergences].sort((a, b) => a - b);
    lines.push(
      `quote divergence: p50 ${sorted[Math.floor(sorted.length / 2)]!.toFixed(2)} bps, max ${sorted[sorted.length - 1]!.toFixed(2)} bps`,
    );
  }
  return lines.join("\n");
}

function medianBigint(values: readonly bigint[]): bigint {
  if (values.length === 0) return 0n;
  const sorted = [...values].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  return sorted[Math.floor(sorted.length / 2)]!;
}
