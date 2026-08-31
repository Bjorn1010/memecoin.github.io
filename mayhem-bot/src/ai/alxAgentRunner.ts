import { PaperPortfolio, type PoolReserves } from "../engine/portfolio.js";
import type { TokenContext } from "./alxcooksPlaybook.js";
import type { WatchedTokenUpdate } from "./tokenWatcher.js";
import { getAlxCooksDecision } from "./llmClient.js";
import { MemoryStore } from "./memoryStore.js";
import { aiConfig } from "./aiConfig.js";

const STRATEGY_ID = "alxcooks-ai";

/**
 * Wires TokenWatcher updates -> LLM decision -> paper trade execution. Paper trading only,
 * same as the rest of mayhem-bot — this never touches a real wallet.
 *
 * Independent risk control on purpose: the LLM decides *when there's a real setup*, but a
 * fixed hard stop-loss, trailing profit-lock, and max hold time (aiConfig.hardStopLossPct /
 * trailingStopFromPeakPct / maxHoldSeconds) are enforced every tick regardless of what the
 * model last said — including when the model can't be reached at all (free-tier daily quota
 * exhaustion happened mid-run in testing; without the trailing lock, positions that were
 * already up double digits just rode the market back down with nothing managing them).
 * Never trust a single point of failure for risk management, model included.
 */
export class AlxAgentRunner {
  readonly portfolio = new PaperPortfolio(STRATEGY_ID, aiConfig.startingBalanceSol);
  readonly memory = new MemoryStore(aiConfig.memoryFilePath, aiConfig.memoryMaxEntries);
  private lastDecisionAtMs = new Map<string, number>();
  private latestUpdates = new Map<string, WatchedTokenUpdate>();
  // Global sliding window across ALL mints — pump.fun's firehose can make many tokens
  // cross the decision threshold within the same few seconds, which blew straight past
  // Groq's free-tier 30 req/min cap in testing (every extra call over the limit just
  // 429s, wasting the quota other tokens needed). This queues gracefully instead.
  private decisionCallTimestampsMs: number[] = [];
  // Position.solInvested shrinks proportionally on partial sells (see PaperPortfolio.sell),
  // so it alone can't tell us "% of the original bag still held" — track the original
  // commitment per mint ourselves, cleared once the position fully closes.
  private originalCommitmentSol = new Map<string, number>();

  async handleUpdate(update: WatchedTokenUpdate) {
    this.latestUpdates.set(update.mint, update);

    const holdsPosition = this.portfolio.positions.has(update.mint);
    if (!holdsPosition) {
      if (update.ageSeconds < aiConfig.minTokenAgeSecondsBeforeDecision) return;
      if (update.tradeCount < aiConfig.minTradesBeforeDecision) return;
      if (!this.portfolio.canOpen(aiConfig.maxConcurrentPositions)) return;
    }

    const lastAt = this.lastDecisionAtMs.get(update.mint) ?? 0;
    if (Date.now() - lastAt < aiConfig.decisionCooldownMs) return;
    if (!this.tryReserveDecisionSlot()) return; // global per-minute budget exhausted, skip quietly

    const position = this.portfolio.positions.get(update.mint);
    const context: TokenContext = {
      mint: update.mint,
      symbol: "", // folded into narrativeSummary — pump.fun trade events don't carry it separately
      name: "",
      narrativeSummary: update.narrativeSummary,
      ageSeconds: update.ageSeconds,
      liquiditySol: update.liquiditySol,
      holderCount: update.holderCount,
      currentPriceSol: update.currentPriceSol,
      avgTopHoldersEntryPriceSol: update.avgTopHoldersEntryPriceSol,
      ourAvgFillPriceSol: position?.avgEntryPriceSol ?? null,
      ourRemainingBagPct: position ? this.remainingBagPct(update.mint, position.solInvested) : null,
      walletCategoryCounts: update.walletCategoryCounts,
      trackedWalletActivity: update.trackedWalletActivity,
      recentPriceActionSummary: update.recentPriceActionSummary,
    };

    this.lastDecisionAtMs.set(update.mint, Date.now());
    const decision = await getAlxCooksDecision(context, this.memory.recent(10));
    if (!decision) return;

    console.log(
      `[alx-agent] ${update.mint.slice(0, 6)}… -> ${decision.action} (${decision.sizePct}%, conf=${decision.confidence}) — ${decision.reasoning}`,
    );
    if (decision.redFlags.length > 0) {
      console.log(`[alx-agent]   red flags: ${decision.redFlags.join("; ")}`);
    }

    this.executeDecision(update, decision.action, decision.sizePct, decision.memoryNote);
  }

  /** True and reserves a slot if we're under the per-minute decision-call budget. */
  private tryReserveDecisionSlot(): boolean {
    const cutoff = Date.now() - 60_000;
    this.decisionCallTimestampsMs = this.decisionCallTimestampsMs.filter((t) => t > cutoff);
    if (this.decisionCallTimestampsMs.length >= aiConfig.maxDecisionCallsPerMinute) return false;
    this.decisionCallTimestampsMs.push(Date.now());
    return true;
  }

  private remainingBagPct(mint: string, currentSolInvested: number): number {
    const original = this.originalCommitmentSol.get(mint);
    if (!original || original <= 0) return 100;
    return Math.round(Math.min((currentSolInvested / original) * 100, 100));
  }

  /** Prints equity/PNL — without this, "did it make money" required reconstructing it
   *  by hand from scattered BUY/SELL log lines, which is how the sizing and rate-limit
   *  bugs almost got missed in the first live run. */
  logSummary() {
    const prices = new Map<string, number>();
    for (const [mint, update] of this.latestUpdates) {
      if (update.currentPriceSol > 0) prices.set(mint, update.currentPriceSol);
    }
    const snap = this.portfolio.snapshot(prices);
    const wins = this.portfolio.trades.filter((t) => t.side === "sell" && t.reason !== "hard_stop_loss").length;
    const stopLosses = this.portfolio.trades.filter((t) => t.reason === "hard_stop_loss").length;

    console.log(
      `[alx-agent] === résumé === equity=${snap.equitySol.toFixed(4)} SOL (départ ${aiConfig.startingBalanceSol}) ` +
        `| réalisé=${snap.realizedPnlSol.toFixed(4)} | non-réalisé=${snap.unrealizedPnlSol.toFixed(4)} | ` +
        `positions ouvertes=${this.portfolio.positions.size} | trades=${this.portfolio.trades.length} ` +
        `(sorties normales=${wins}, hard-stops=${stopLosses}) | frais cumulés=${snap.totalFeesSol.toFixed(4)}`,
    );
  }

  /** Runs the hard-stop safety net over every open position, using the last known price. */
  tickAllHardStops() {
    for (const mint of this.portfolio.positions.keys()) {
      const update = this.latestUpdates.get(mint);
      if (update && update.currentPriceSol > 0) this.checkHardStops(mint, update.currentPriceSol);
    }
  }

  /** Independent safety net — enforced every tick regardless of what the LLM last decided. */
  checkHardStops(mint: string, currentPriceSol: number) {
    const pos = this.portfolio.positions.get(mint);
    if (!pos) return;

    this.portfolio.markPrice(mint, currentPriceSol);
    const changePct = (currentPriceSol - pos.avgEntryPriceSol) / pos.avgEntryPriceSol;
    const heldSeconds = (Date.now() - pos.openedAt) / 1000;

    const drawdownFromPeakPct = (pos.peakPriceSol - currentPriceSol) / pos.peakPriceSol;
    const stillInProfit = currentPriceSol > pos.avgEntryPriceSol;

    if (changePct <= -aiConfig.hardStopLossPct) {
      this.sell(mint, currentPriceSol, "hard_stop_loss", 1);
    } else if (stillInProfit && drawdownFromPeakPct >= aiConfig.trailingStopFromPeakPct) {
      this.sell(mint, currentPriceSol, "trailing_stop_profit_lock", 1);
    } else if (heldSeconds >= aiConfig.maxHoldSeconds) {
      this.sell(mint, currentPriceSol, "max_hold_time", 1);
    }
  }

  private executeDecision(
    update: WatchedTokenUpdate,
    action: string,
    sizePct: number,
    memoryNote: string | undefined,
  ) {
    const poolReserves: PoolReserves | undefined = update.poolReserves ?? undefined;

    switch (action) {
      case "enter_scout":
      case "scale_in": {
        // sizePct is already the model's intended fraction of the normal position size
        // (see the "Précisions sur sizePct" block in buildDecisionPrompt) — enter_scout
        // vs scale_in is what signals caution, not a second multiplier stacked on top.
        const solAmount = aiConfig.positionSizeSol * (Math.min(Math.max(sizePct, 0), 100) / 100 || 0.3);
        const t = this.portfolio.buy({
          mint: update.mint,
          priceSol: update.currentPriceSol,
          solAmount,
          reason: action,
          latencyMs: 0,
          entryEventId: update.mint,
          priorityFeeSol: aiConfig.priorityFeeSol,
          poolReserves,
        });
        if (t) {
          const prior = this.originalCommitmentSol.get(update.mint) ?? 0;
          this.originalCommitmentSol.set(update.mint, prior + t.solAmount);
          console.log(`[alx-agent]   BUY ${t.solAmount.toFixed(3)} SOL @ ${t.priceSol}`);
        }
        break;
      }
      case "scale_out":
      case "exit_full": {
        const fraction = action === "exit_full" ? 1 : Math.min(Math.max(sizePct / 100, 0), 1) || 0.2;
        this.sell(update.mint, update.currentPriceSol, action, fraction, poolReserves);
        break;
      }
      case "skip":
      case "hold":
      default:
        break;
    }

    if (memoryNote) this.memory.add(memoryNote);
  }

  private sell(mint: string, priceSol: number, reason: string, fraction: number, poolReserves?: PoolReserves) {
    const t = this.portfolio.sell({
      mint,
      priceSol,
      reason,
      latencyMs: 0,
      fraction,
      priorityFeeSol: aiConfig.priorityFeeSol,
      poolReserves,
    });
    if (t) {
      console.log(`[alx-agent]   SELL (${reason}) ${t.tokenAmount.toFixed(2)} tok @ ${t.priceSol}`);
      if (fraction >= 1) {
        this.originalCommitmentSol.delete(mint);
        this.memory.add(
          `Sortie complète sur ${mint.slice(0, 6)}… (${reason}), PNL réalisé cumulé de la stratégie: ${this.portfolio.realizedPnlSol.toFixed(4)} SOL.`,
        );
      }
    }
  }
}
