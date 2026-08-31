/**
 * Kill switch.
 *
 * Once tripped it STAYS tripped until a human clears it. That is the whole
 * point: the conditions that trip it (sustained losses, unexplained residual
 * balances, repeated simulation disagreement) are exactly the conditions under
 * which an automated reset would resume losing money.
 *
 * State is persisted to a file so a restart does not clear it. The in-memory
 * class is pure and testable; persistence is injected.
 */

export type KillSwitchTrigger =
  | "daily-loss"
  | "residual-balance"
  | "quote-divergence"
  | "consecutive-failures"
  | "manual";

export interface KillSwitchState {
  tripped: boolean;
  trigger: KillSwitchTrigger | null;
  detail: string;
  trippedAt: number | null;
}

export interface KillSwitchThresholds {
  /** Realised daily loss, in lamports, that trips the switch. */
  maxDailyLossLamports: bigint;
  /** Residual token value, in base lamports, that trips it. */
  maxResidualLamports: bigint;
  /** Consecutive residual alerts before we stop trading rather than warn. */
  maxResidualIncidents: number;
  /** Consecutive sends that landed and reverted before we stop. */
  maxConsecutiveFailures: number;
  /**
   * Quote-vs-simulation divergence, in basis points, that indicates a broken
   * quoter. One occurrence warns; `maxDivergenceIncidents` trips.
   */
  maxQuoteDivergenceBps: number;
  maxDivergenceIncidents: number;
}

export const DEFAULT_KILL_SWITCH_THRESHOLDS: KillSwitchThresholds = {
  maxDailyLossLamports: 150_000_000n, // 0.15 SOL
  maxResidualLamports: 10_000_000n, // 0.01 SOL
  maxResidualIncidents: 3,
  maxConsecutiveFailures: 15,
  maxQuoteDivergenceBps: 25,
  maxDivergenceIncidents: 3,
};

export interface KillSwitchPersistence {
  load(): KillSwitchState | null;
  save(state: KillSwitchState): void;
}

export class KillSwitch {
  private state: KillSwitchState = {
    tripped: false,
    trigger: null,
    detail: "",
    trippedAt: null,
  };
  private residualIncidents = 0;
  private divergenceIncidents = 0;
  private consecutiveFailures = 0;

  constructor(
    private readonly thresholds: KillSwitchThresholds = DEFAULT_KILL_SWITCH_THRESHOLDS,
    private readonly persistence?: KillSwitchPersistence,
  ) {
    const loaded = persistence?.load();
    if (loaded) this.state = loaded;
  }

  get tripped(): boolean {
    return this.state.tripped;
  }

  snapshot(): KillSwitchState {
    return { ...this.state };
  }

  /** Trip explicitly. Idempotent: the first trigger is the one recorded. */
  trip(trigger: KillSwitchTrigger, detail: string, now: number): void {
    if (this.state.tripped) return;
    this.state = { tripped: true, trigger, detail, trippedAt: now };
    this.persistence?.save(this.state);
  }

  /**
   * Clear the switch. Only ever called from an explicit operator action; there
   * is no code path that clears it automatically, by design.
   */
  reset(): void {
    this.state = { tripped: false, trigger: null, detail: "", trippedAt: null };
    this.residualIncidents = 0;
    this.divergenceIncidents = 0;
    this.consecutiveFailures = 0;
    this.persistence?.save(this.state);
  }

  onDailyPnl(dailyRealisedPnl: bigint, now: number): void {
    if (dailyRealisedPnl <= -this.thresholds.maxDailyLossLamports) {
      this.trip(
        "daily-loss",
        `realised PnL ${dailyRealisedPnl} reached the daily loss limit of -${this.thresholds.maxDailyLossLamports}`,
        now,
      );
    }
  }

  /**
   * Residual balances after a supposedly atomic cycle.
   *
   * A residue is never treated as normal. One over-threshold residue raises an
   * alert; a recurring one stops trading, because it means our model of what
   * the transaction does is wrong.
   */
  onResidualBalance(residualValueLamports: bigint, now: number): "ok" | "alert" | "tripped" {
    if (residualValueLamports <= this.thresholds.maxResidualLamports) return "ok";
    this.residualIncidents++;
    if (this.residualIncidents >= this.thresholds.maxResidualIncidents) {
      this.trip(
        "residual-balance",
        `${this.residualIncidents} residual balances above ${this.thresholds.maxResidualLamports}; the cycle is not closing cleanly`,
        now,
      );
      return "tripped";
    }
    return "alert";
  }

  onQuoteDivergence(divergenceBps: number, now: number): "ok" | "alert" | "tripped" {
    if (Math.abs(divergenceBps) <= this.thresholds.maxQuoteDivergenceBps) return "ok";
    this.divergenceIncidents++;
    if (this.divergenceIncidents >= this.thresholds.maxDivergenceIncidents) {
      this.trip(
        "quote-divergence",
        `${this.divergenceIncidents} quotes diverged from simulation by more than ${this.thresholds.maxQuoteDivergenceBps} bps; a quoter is wrong`,
        now,
      );
      return "tripped";
    }
    return "alert";
  }

  onSendOutcome(landedAndSucceeded: boolean, now: number): void {
    if (landedAndSucceeded) {
      this.consecutiveFailures = 0;
      return;
    }
    this.consecutiveFailures++;
    if (this.consecutiveFailures >= this.thresholds.maxConsecutiveFailures) {
      this.trip(
        "consecutive-failures",
        `${this.consecutiveFailures} consecutive attempts landed and reverted`,
        now,
      );
    }
  }

  /** Counters, for the report. */
  counters(): { residualIncidents: number; divergenceIncidents: number; consecutiveFailures: number } {
    return {
      residualIncidents: this.residualIncidents,
      divergenceIncidents: this.divergenceIncidents,
      consecutiveFailures: this.consecutiveFailures,
    };
  }
}
