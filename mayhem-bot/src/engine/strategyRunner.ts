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
    // waitForMigration strategies never buy on the bonding curve itself — EngineManager
    // watches the mint instead and calls enterAfterMigration() once it's off the curve.
    if (this.config.waitForMigration) return trades;
    // No reserves means we cannot model this fill at all, and entering anyway is not a
    // harmless approximation — it manufactures profit. The entry gets booked at the raw
    // event price with zero slippage, while the matching exit goes through simulateSell()
    // against whatever reserves have landed in the cache by then. The two legs end up priced
    // off different bases, which produced eight consecutive 3.5x-13x round trips on one mint
    // in under four seconds each. It also silently defeated the depth filter below: with
    // reserves unknown, a `>= 40 SOL` requirement admitted a pool that never held more than
    // 27 SOL. Roughly 4% of Mayhem buy events arrive without reserves; skipping them costs
    // little and is the only honest option.
    if (!poolReserves) return trades;
    if (this.config.minPoolLiquiditySol != null && poolReserves.solReservesUi < this.config.minPoolLiquiditySol) {
      return trades; // pool too thin — AMM slippage would eat the trade alive
    }
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

  /** Entry path for waitForMigration strategies: called once a mint Mayhem bought
   * pre-migration has just come off the bonding curve. No bonding-curve reserves exist for
   * the new AMM pool (DexScreener gives us spot price only), so this fill has no simulated
   * slippage — a known, disclosed simplification, not a claim that post-migration fills are
   * actually free. */
  enterAfterMigration(mint: string, priceSol: number, entryEventId: string, mayhemBuySolAmount: number): Trade | null {
    if (!this.config.enabled) return null;
    if (!this.config.waitForMigration) return null;
    if (this.portfolio.positions.has(mint)) return null;
    if (this.config.minMayhemBuySol != null && mayhemBuySolAmount < this.config.minMayhemBuySol) return null;
    if (!this.portfolio.canOpen(this.config.maxConcurrentPositions)) return null;

    return this.portfolio.buy({
      mint,
      priceSol,
      solAmount: this.config.positionSizeSol,
      reason: "copy_mayhem_buy_post_migration",
      latencyMs: 0,
      entryEventId,
      priorityFeeSol: this.config.priorityFeeSol,
    });
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
      // Armed off the peak ever reached, not the current price — a one-way ratchet. A
      // position that pumped to +200% and has since fallen back to +40% has already proven
      // itself a tail winner; it must stay eligible for the trailing stop even though its
      // current gain has dropped back under trailingArmPct, or a big pullback-then-crash
      // would ride all the way down to stop_loss instead of locking in the gain it had.
      const peakGainPct = (pos.peakPriceSol - pos.avgEntryPriceSol) / pos.avgEntryPriceSol;
      const heldSeconds = (Date.now() - pos.openedAt) / 1000;

      let reason: string | null = null;
      if (this.config.stopLossPct != null && changePct <= -this.config.stopLossPct) {
        reason = "stop_loss";
      } else if (this.config.takeProfitPct != null && changePct >= this.config.takeProfitPct) {
        reason = "take_profit";
      } else if (
        this.config.trailingStopPct != null &&
        drawdownFromPeakPct <= -this.config.trailingStopPct &&
        peakGainPct >= (this.config.trailingArmPct ?? 0)
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
