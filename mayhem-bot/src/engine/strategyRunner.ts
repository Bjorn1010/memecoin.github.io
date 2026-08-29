import { PaperPortfolio, type PoolReserves } from "./portfolio.js";
import type { MayhemEvent, StrategyConfig, Trade } from "../types.js";

/**
 * Generic, config-driven strategy: every StrategyConfig combination (entry filter,
 * take-profit, stop-loss, max hold time, copy-the-dump exit) runs through this same
 * runner against its own isolated PaperPortfolio. This is how "test several strategies
 * at once" works — spin up N configs, compare results live, same fee/slippage model for all.
 */
export class StrategyRunner {
  portfolio: PaperPortfolio;

  constructor(public config: StrategyConfig) {
    this.portfolio = new PaperPortfolio(config.id, config.startingBalanceSol);
  }

  /** React to a live Mayhem on-chain event: possible entry, or an immediate copy-the-dump exit. */
  onMayhemEvent(event: MayhemEvent): Trade[] {
    if (!this.config.enabled) return [];
    const latencyMs = Date.now() - event.detectedAtMs;
    const trades: Trade[] = [];
    const poolReserves: PoolReserves | undefined =
      event.solReservesUi != null && event.tokenReservesUi != null
        ? { solReservesUi: event.solReservesUi, tokenReservesUi: event.tokenReservesUi }
        : undefined;

    const holdsPosition = this.portfolio.positions.has(event.mint);

    if (event.kind === "full_exit" && holdsPosition && this.config.sellOnMayhemFullExit) {
      const t = this.portfolio.sell({
        mint: event.mint,
        priceSol: event.priceSol,
        reason: "mayhem_full_exit",
        latencyMs,
        priorityFeeSol: this.config.priorityFeeSol,
        poolReserves,
      });
      if (t) trades.push(t);
      return trades;
    }

    if (event.kind !== "buy") return trades;
    if (holdsPosition) return trades; // already in this coin, let exits manage it
    if (this.config.minMayhemBuySol != null && event.solAmount < this.config.minMayhemBuySol) return trades;
    if (!this.portfolio.canOpen(this.config.maxConcurrentPositions)) return trades;

    const t = this.portfolio.buy({
      mint: event.mint,
      priceSol: event.priceSol,
      solAmount: this.config.positionSizeSol,
      reason: "copy_mayhem_buy",
      latencyMs,
      entryEventId: event.id,
      priorityFeeSol: this.config.priorityFeeSol,
      poolReserves,
    });
    if (t) trades.push(t);
    return trades;
  }

  /** Periodic price-driven exit check (take-profit / stop-loss / max hold). */
  tick(prices: Map<string, number>, reserves: Map<string, PoolReserves>): Trade[] {
    if (!this.config.enabled) return [];
    const trades: Trade[] = [];

    for (const pos of [...this.portfolio.positions.values()]) {
      const price = prices.get(pos.mint);
      if (price == null) continue;

      this.portfolio.markPrice(pos.mint, price);
      const changePct = (price - pos.avgEntryPriceSol) / pos.avgEntryPriceSol;
      const drawdownFromPeakPct = (price - pos.peakPriceSol) / pos.peakPriceSol;
      const heldSeconds = (Date.now() - pos.openedAt) / 1000;

      let reason: string | null = null;
      if (this.config.stopLossPct != null && changePct <= -this.config.stopLossPct) {
        reason = "stop_loss";
      } else if (this.config.takeProfitPct != null && changePct >= this.config.takeProfitPct) {
        reason = "take_profit";
      } else if (
        this.config.trailingStopPct != null &&
        drawdownFromPeakPct <= -this.config.trailingStopPct &&
        changePct > 0
      ) {
        reason = "trailing_stop";
      } else if (this.config.maxHoldSeconds != null && heldSeconds >= this.config.maxHoldSeconds) {
        reason = "max_hold_time";
      }

      if (reason) {
        const t = this.portfolio.sell({
          mint: pos.mint,
          priceSol: price,
          reason,
          latencyMs: 0,
          priorityFeeSol: this.config.priorityFeeSol,
          poolReserves: reserves.get(pos.mint),
        });
        if (t) trades.push(t);
      }
    }

    return trades;
  }
}
