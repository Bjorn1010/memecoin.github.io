interface HolderState {
  tokenAmount: number;
  costBasisSol: number;
}

/**
 * Tracks, per mint, every wallet's running token balance and cost basis purely from
 * observed trade events — the same drift caveat as WalletBalanceTracker applies (a missed
 * event can drift it from true on-chain state over a long session). Used to derive the
 * "Avg Top 10 Holders Entry" reference line the agent's reasoning leans on.
 */
export class HolderTracker {
  private perMint = new Map<string, Map<string, HolderState>>();

  private forMint(mint: string): Map<string, HolderState> {
    let m = this.perMint.get(mint);
    if (!m) {
      m = new Map();
      this.perMint.set(mint, m);
    }
    return m;
  }

  applyTrade(mint: string, wallet: string, isBuy: boolean, tokenAmount: number, solAmount: number) {
    const holders = this.forMint(mint);
    const existing = holders.get(wallet) ?? { tokenAmount: 0, costBasisSol: 0 };

    if (isBuy) {
      existing.tokenAmount += tokenAmount;
      existing.costBasisSol += solAmount;
    } else {
      const avgEntry = existing.tokenAmount > 0 ? existing.costBasisSol / existing.tokenAmount : 0;
      const sold = Math.min(tokenAmount, existing.tokenAmount);
      existing.tokenAmount -= sold;
      existing.costBasisSol = Math.max(existing.costBasisSol - avgEntry * sold, 0);
    }

    if (existing.tokenAmount <= 0) {
      holders.delete(wallet);
    } else {
      holders.set(wallet, existing);
    }
  }

  /** Weighted average entry price (SOL per token) of the current top N holders by balance. */
  getTopHoldersAvgEntryPriceSol(mint: string, topN = 10): number | null {
    const holders = this.perMint.get(mint);
    if (!holders || holders.size === 0) return null;

    const top = [...holders.values()].sort((a, b) => b.tokenAmount - a.tokenAmount).slice(0, topN);
    const totalTokens = top.reduce((sum, h) => sum + h.tokenAmount, 0);
    const totalCost = top.reduce((sum, h) => sum + h.costBasisSol, 0);
    if (totalTokens <= 0) return null;

    return totalCost / totalTokens;
  }

  getHolderCount(mint: string): number {
    return this.perMint.get(mint)?.size ?? 0;
  }

  prune(mint: string) {
    this.perMint.delete(mint);
  }
}
