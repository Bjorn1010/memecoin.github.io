import { nanoid } from "nanoid";
import { PLATFORM_FEE_PCT } from "../solana/constants.js";
import { simulateBuy, simulateSell } from "./amm.js";
import type { Position, PortfolioSnapshot, Trade } from "../types.js";

export interface PoolReserves {
  solReservesUi: number;
  tokenReservesUi: number;
}

/**
 * A fully virtual (paper) trading account for one strategy. No wallet, no real funds —
 * but every fill goes through the same cost model a real Padre trade would: the platform's
 * 1% fee on both legs, a flat priority/network fee per transaction, and AMM slippage computed
 * against the pool's actual reserves at that moment (when known) instead of a free, flat
 * price. The goal is that these numbers don't surprise you when the strategy goes live.
 */
export class PaperPortfolio {
  solBalance: number;
  realizedPnlSol = 0;
  totalFeesSol = 0;
  positions = new Map<string, Position>();
  trades: Trade[] = [];

  constructor(
    public strategyId: string,
    startingBalanceSol: number,
  ) {
    this.solBalance = startingBalanceSol;
  }

  canOpen(maxConcurrentPositions: number): boolean {
    return this.positions.size < maxConcurrentPositions;
  }

  buy(opts: {
    mint: string;
    priceSol: number; // fallback spot price, used only when pool reserves aren't known
    solAmount: number; // intended notional to spend, before platform fee
    reason: string;
    latencyMs: number;
    entryEventId: string;
    priorityFeeSol: number;
    poolReserves?: PoolReserves;
  }): Trade | null {
    if (opts.priceSol <= 0 && !opts.poolReserves) return null;
    if (this.solBalance <= opts.priorityFeeSol) return null; // can't even cover the network fee

    const spend = Math.min(opts.solAmount, Math.max(this.solBalance - opts.priorityFeeSol, 0));
    if (spend <= 0) return null;

    const feeSol = spend * PLATFORM_FEE_PCT;
    const notionalAfterFee = spend - feeSol;

    const fill = opts.poolReserves
      ? simulateBuy(notionalAfterFee, opts.poolReserves.solReservesUi, opts.poolReserves.tokenReservesUi)
      : { avgPriceSol: opts.priceSol, slippagePct: 0 };
    if (fill.avgPriceSol <= 0) return null;

    const tokenAmount = notionalAfterFee / fill.avgPriceSol;
    const totalCost = spend; // fee is already baked into what left the wallet

    const existing = this.positions.get(opts.mint);
    if (existing) {
      const totalTokens = existing.tokenAmount + tokenAmount;
      const combinedCost = existing.solInvested + totalCost;
      existing.tokenAmount = totalTokens;
      existing.solInvested = combinedCost;
      existing.avgEntryPriceSol = combinedCost / totalTokens;
      existing.peakPriceSol = Math.max(existing.peakPriceSol, fill.avgPriceSol);
    } else {
      this.positions.set(opts.mint, {
        mint: opts.mint,
        strategyId: this.strategyId,
        tokenAmount,
        avgEntryPriceSol: fill.avgPriceSol,
        solInvested: totalCost,
        openedAt: Date.now(),
        peakPriceSol: fill.avgPriceSol,
        entryEventId: opts.entryEventId,
      });
    }

    this.solBalance -= spend + opts.priorityFeeSol;
    this.totalFeesSol += feeSol + opts.priorityFeeSol;

    const trade: Trade = {
      id: nanoid(),
      strategyId: this.strategyId,
      mint: opts.mint,
      side: "buy",
      reason: opts.reason,
      priceSol: fill.avgPriceSol,
      tokenAmount,
      solAmount: spend,
      feeSol,
      priorityFeeSol: opts.priorityFeeSol,
      slippagePct: fill.slippagePct,
      latencyMs: opts.latencyMs,
      createdAt: Date.now(),
    };
    this.trades.push(trade);
    return trade;
  }

  sell(opts: {
    mint: string;
    priceSol: number;
    reason: string;
    latencyMs: number;
    fraction?: number;
    priorityFeeSol: number;
    poolReserves?: PoolReserves;
  }): Trade | null {
    const pos = this.positions.get(opts.mint);
    if (!pos) return null;
    if (opts.priceSol <= 0 && !opts.poolReserves) return null;

    const fraction = opts.fraction ?? 1;
    const tokenAmount = pos.tokenAmount * fraction;

    const fill = opts.poolReserves
      ? simulateSell(tokenAmount, opts.poolReserves.solReservesUi, opts.poolReserves.tokenReservesUi)
      : { avgPriceSol: opts.priceSol, slippagePct: 0 };
    if (fill.avgPriceSol <= 0) return null;

    const grossProceeds = tokenAmount * fill.avgPriceSol;
    const feeSol = grossProceeds * PLATFORM_FEE_PCT;
    const netProceeds = grossProceeds - feeSol;
    const costBasis = pos.avgEntryPriceSol * tokenAmount;
    const pnl = netProceeds - costBasis - opts.priorityFeeSol;

    // On a large enough dust position, netProceeds can be smaller than the flat priority
    // fee (a real wallet would still just pay the fee out of whatever's left) — clamp so
    // the paper balance never goes negative and the equity/PnL display stays sane.
    this.solBalance = Math.max(0, this.solBalance + netProceeds - opts.priorityFeeSol);
    this.realizedPnlSol += pnl;
    this.totalFeesSol += feeSol + opts.priorityFeeSol;

    if (fraction >= 1) {
      this.positions.delete(opts.mint);
    } else {
      pos.tokenAmount -= tokenAmount;
      pos.solInvested -= costBasis;
    }

    const trade: Trade = {
      id: nanoid(),
      strategyId: this.strategyId,
      mint: opts.mint,
      side: "sell",
      reason: opts.reason,
      priceSol: fill.avgPriceSol,
      tokenAmount,
      solAmount: netProceeds,
      feeSol,
      priorityFeeSol: opts.priorityFeeSol,
      slippagePct: fill.slippagePct,
      latencyMs: opts.latencyMs,
      createdAt: Date.now(),
    };
    this.trades.push(trade);
    return trade;
  }

  markPrice(mint: string, priceSol: number) {
    const pos = this.positions.get(mint);
    if (pos && priceSol > pos.peakPriceSol) pos.peakPriceSol = priceSol;
  }

  solDeployed(): number {
    let total = 0;
    for (const pos of this.positions.values()) total += pos.solInvested;
    return total;
  }

  unrealizedPnlSol(prices: Map<string, number>): number {
    let total = 0;
    for (const pos of this.positions.values()) {
      const price = prices.get(pos.mint);
      if (price == null) continue;
      total += pos.tokenAmount * price - pos.solInvested;
    }
    return total;
  }

  snapshot(prices: Map<string, number>): PortfolioSnapshot {
    const unrealized = this.unrealizedPnlSol(prices);
    const positionsValue = [...this.positions.values()].reduce((sum, pos) => {
      const price = prices.get(pos.mint) ?? pos.avgEntryPriceSol;
      return sum + pos.tokenAmount * price;
    }, 0);
    return {
      strategyId: this.strategyId,
      timestamp: Date.now(),
      solBalance: this.solBalance,
      unrealizedPnlSol: unrealized,
      realizedPnlSol: this.realizedPnlSol,
      equitySol: this.solBalance + positionsValue,
      solDeployed: this.solDeployed(),
      totalFeesSol: this.totalFeesSol,
    };
  }
}
