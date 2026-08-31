/**
 * Heuristic approximation of the "spam / snipe / side / main / dev" wallet categories
 * seen on his Padre.gg terminal. We don't have access to whatever proprietary reputation
 * data Padre/Axiom use, so this is a deliberately simple, honest stand-in based only on
 * what's observable from raw trade events: timing relative to the token's first trade,
 * and trade size. Treat it as a first approximation, not a claim of parity with theirs.
 */
export type WalletCategory = "spam" | "snipe" | "side" | "main" | "dev";

export interface ClassifyInput {
  /** True if this is the very first trade event we've observed for this mint. */
  isFirstTradeForMint: boolean;
  secondsSinceMintFirstSeen: number;
  solAmount: number;
}

const SNIPE_WINDOW_SECONDS = 8;
const SPAM_MAX_SOL = 0.02;
const MAIN_MIN_SOL = 1;

export function classifyWallet(input: ClassifyInput): WalletCategory {
  if (input.isFirstTradeForMint) return "dev";
  if (input.secondsSinceMintFirstSeen <= SNIPE_WINDOW_SECONDS) return "snipe";
  if (input.solAmount < SPAM_MAX_SOL) return "spam";
  if (input.solAmount >= MAIN_MIN_SOL) return "main";
  return "side";
}

export function emptyCategoryCounts(): Record<WalletCategory, number> {
  return { spam: 0, snipe: 0, side: 0, main: 0, dev: 0 };
}
