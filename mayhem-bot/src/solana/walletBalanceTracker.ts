const DUST_UI_AMOUNT = 0.000001;

/**
 * Tracks each watched wallet's running per-mint token balance purely from the trade events
 * we observe, so "did this sell empty the position" (the vault-dump signal) can be answered
 * without an extra RPC call. It only ever sees balance *changes* we detect ourselves, so a
 * missed event (rare — only when the log fast-path can't decode a trade and the RPC fallback
 * also drops it as stale) can drift it from the true on-chain balance over a long session.
 */
export class WalletBalanceTracker {
  private balances = new Map<string, Map<string, number>>();

  private forWallet(wallet: string): Map<string, number> {
    let m = this.balances.get(wallet);
    if (!m) {
      m = new Map();
      this.balances.set(wallet, m);
    }
    return m;
  }

  /** Applies a signed delta (positive = received, negative = sent) and returns the new balance. */
  applyDelta(wallet: string, mint: string, delta: number): number {
    const m = this.forWallet(wallet);
    const next = Math.max((m.get(mint) ?? 0) + delta, 0);
    m.set(mint, next);
    return next;
  }

  isEffectivelyZero(balance: number): boolean {
    return balance < DUST_UI_AMOUNT;
  }
}
