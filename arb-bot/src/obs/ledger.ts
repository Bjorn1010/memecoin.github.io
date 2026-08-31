/**
 * The ledger.
 *
 * Append-only JSONL, one record per line, never rewritten. It is the only
 * source of truth for the land rate, for realised PnL and for every question in
 * §49 ("is the problem the strategy or the infrastructure?"), so it records the
 * whole decision — including the ones that did not become transactions.
 *
 * Two rules are enforced structurally rather than by discipline:
 *  - the five attempt outcomes are separate fields and are never collapsed into
 *    a single "success" boolean (§6);
 *  - nothing derived from a private key is writable. `writeAttempt` takes a
 *    typed record with no field that could hold one, and the writer refuses any
 *    value that looks like a secret.
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { AttemptOutcome, DexFamily, RejectReason } from "../types.js";

export interface AttemptRecord {
  /** Wall clock at detection. */
  timestamp: number;
  /** Slot the opportunity was detected at. */
  slot: number;
  mode: "observe" | "paper" | "live" | "replay";

  buyPoolId: string;
  sellPoolId: string;
  buyFamily: DexFamily;
  sellFamily: DexFamily;
  baseMint: string;
  intermediateMint: string;

  amountIn: string;
  expectedIntermediate: string;
  expectedAmountOut: string;
  expectedGrossProfit: string;
  expectedNetProfit: string;
  expectedValue: string;
  /** Realised profit in base lamports, once known. Null until then. */
  actualProfit: string | null;

  computeUnitsSimulated: number | null;
  computeUnitLimit: number | null;
  priorityFeeLamports: string;
  tipLamports: string;
  baseFeeLamports: string;

  /** Age of the oldest account in the quote, in slots and ms. */
  stateAgeSlots: number;
  stateAgeMs: number;

  detectionLatencyMs: number;
  decisionLatencyMs: number;
  sendLatencyMs: number | null;
  totalLatencyMs: number;

  outcome: AttemptOutcome;
  rejectReason: RejectReason | null;
  failureReason: string | null;
  signature: string | null;
  landedSlot: number | null;

  /** Divergence between our quote and the simulation, in bps. */
  quoteDivergenceBps: number | null;
  landRateUsed: number;
  landRateSamples: number;
}

export interface ObservationRecord {
  timestamp: number;
  slot: number;
  buyPoolId: string;
  sellPoolId: string;
  intermediateMint: string;
  optimalAmountIn: string;
  grossProfit: string;
  netProfit: string;
  spreadBps: number;
  /**
   * Whether the same opportunity was still profitable after each delay. This is
   * the measurement that decides whether our latency is survivable at all
   * (§25).
   */
  survival: { afterMs: number; stillProfitable: boolean; grossProfit: string }[];
}

export interface WatchlistChangeRecord {
  timestamp: number;
  poolId: string;
  action: "enter" | "exit";
  reason: string;
  score: number;
}

/**
 * Patterns that must never reach disk. A base58 string of 80+ characters is the
 * shape of a secret key; a 64-number JSON array is the shape of a keypair file.
 */
const SECRET_SHAPES = [/[1-9A-HJ-NP-Za-km-z]{80,}/, /\[\s*\d{1,3}\s*(,\s*\d{1,3}\s*){63,}\]/];

export class SecretInLedgerError extends Error {
  constructor(field: string) {
    super(`refusing to write a value that looks like a secret (field ${field})`);
    this.name = "SecretInLedgerError";
  }
}

function assertNoSecrets(record: object): void {
  for (const [key, value] of Object.entries(record)) {
    if (typeof value !== "string") continue;
    for (const shape of SECRET_SHAPES) {
      if (shape.test(value)) throw new SecretInLedgerError(key);
    }
  }
}

export class Ledger {
  private readonly attemptsPath: string;
  private readonly observationsPath: string;
  private readonly watchlistPath: string;
  private readonly landRatePath: string;

  constructor(dataDir: string, runId: string) {
    const dir = join(dataDir, runId);
    mkdirSync(dir, { recursive: true });
    this.attemptsPath = join(dir, "attempts.jsonl");
    this.observationsPath = join(dir, "observations.jsonl");
    this.watchlistPath = join(dir, "watchlist.jsonl");
    this.landRatePath = join(dir, "land-rate.json");
  }

  get paths(): { attempts: string; observations: string; watchlist: string; landRate: string } {
    return {
      attempts: this.attemptsPath,
      observations: this.observationsPath,
      watchlist: this.watchlistPath,
      landRate: this.landRatePath,
    };
  }

  writeAttempt(record: AttemptRecord): void {
    assertNoSecrets(record);
    this.append(this.attemptsPath, record);
  }

  writeObservation(record: ObservationRecord): void {
    this.append(this.observationsPath, record);
  }

  writeWatchlistChange(record: WatchlistChangeRecord): void {
    this.append(this.watchlistPath, record);
  }

  saveLandRate(snapshot: unknown): void {
    mkdirSync(dirname(this.landRatePath), { recursive: true });
    appendOrReplace(this.landRatePath, JSON.stringify(snapshot, null, 2));
  }

  loadLandRate<T>(): T | null {
    if (!existsSync(this.landRatePath)) return null;
    try {
      return JSON.parse(readFileSync(this.landRatePath, "utf8")) as T;
    } catch {
      return null;
    }
  }

  private append(path: string, record: object): void {
    appendFileSync(path, JSON.stringify(record) + "\n", "utf8");
  }
}

function appendOrReplace(path: string, content: string): void {
  // A snapshot file is state, not a log: replace it wholesale.
  writeFileSync(path, content, "utf8");
}

/** Read a JSONL file back, skipping malformed lines rather than failing. */
export function readJsonl<T>(path: string): T[] {
  if (!existsSync(path)) return [];
  const out: T[] = [];
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (trimmed.length === 0) continue;
    try {
      out.push(JSON.parse(trimmed) as T);
    } catch {
      // A partially written last line is normal if the process was killed.
    }
  }
  return out;
}

/** Stable run id: sortable, filesystem-safe, no collisions within a second. */
export function makeRunId(now = new Date()): string {
  const pad = (n: number, w = 2): string => String(n).padStart(w, "0");
  return [
    now.getUTCFullYear(),
    pad(now.getUTCMonth() + 1),
    pad(now.getUTCDate()),
    "-",
    pad(now.getUTCHours()),
    pad(now.getUTCMinutes()),
    pad(now.getUTCSeconds()),
  ].join("");
}
