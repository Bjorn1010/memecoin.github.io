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
 * Two layers of risk control, on purpose: the LLM decides *when there's a real setup*, but
 * a fixed hard stop-loss / max hold time (aiConfig.hardStopLossPct / maxHoldSeconds) is
 * enforced independently every tick, regardless of what the model last said. Never trust a
 * single point of failure for risk management, model included.
 */
export class AlxAgentRunner {
  readonly portfolio = new PaperPortfolio(STRATEGY_ID, aiConfig.startingBalanceSol);
  readonly memory = new MemoryStore(aiConfig.memoryFilePath, aiConfig.memoryMaxEntries);
  private lastDecisionAtMs = new Map<string, number>();
  private latestUpdates = new Map<string, WatchedTokenUpdate>();
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
    this.lastDecisionAtMs.set(update.mint, lastAt); // set below once the call actually fires

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

  private remainingBagPct(mint: string, currentSolInvested: number): number {
    const original = this.originalCommitmentSol.get(mint);
    if (!original || original <= 0) return 100;
    return Math.round(Math.min((currentSolInvested / original) * 100, 100));
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

    if (changePct <= -aiConfig.hardStopLossPct) {
      this.sell(mint, currentPriceSol, "hard_stop_loss", 1);
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
        const solAmount = aiConfig.positionSizeSol * (action === "enter_scout" ? 0.3 : 1) * (sizePct / 100 || 1);
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
