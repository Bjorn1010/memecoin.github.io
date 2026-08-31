import type {
  DexFamily,
  MintState,
  PoolSnapshot,
  QuoteResult,
  SwapDirection,
} from "../types.js";

/**
 * Raised when a quoter is asked to price something it cannot price exactly.
 *
 * This is deliberately an error rather than a "best effort" number: an
 * approximate quote that looks like a real one is the single most expensive
 * bug this codebase can contain (§48 — never fill a gap with an invention).
 */
export class UnquotableError extends Error {
  constructor(
    readonly reason:
      | "unsupported-mint-extension"
      | "wrong-family"
      | "mint-not-in-pool"
      | "pool-disabled"
      | "pool-not-open"
      | "empty-reserves"
      | "amount-out-of-range"
      | "missing-input",
    message: string,
  ) {
    super(message);
    this.name = "UnquotableError";
  }
}

/**
 * Context every quoter may need beyond the pool snapshot itself: mint metadata
 * (decimals, supply, Token-2022 extensions) and the chain clock.
 */
export interface QuoteContext {
  /** Mint state by address. Must contain both mints of the pool. */
  mints: ReadonlyMap<string, MintState>;
  /** Current slot, used only for reporting freshness on the result. */
  currentSlot: number;
  /**
   * Unix timestamp (seconds) the swap would execute at. Raydium gates swaps on
   * `open_time`; we use the chain's most recent block time, not local time.
   */
  blockTimeSeconds: number;
}

export interface Quoter {
  readonly family: DexFamily;

  /**
   * Price `amountIn` of `direction.inputMint` through `pool`.
   *
   * Must replicate the on-chain program exactly, including rounding direction,
   * or throw `UnquotableError`. It must never return an approximation.
   */
  quote(
    pool: PoolSnapshot,
    amountIn: bigint,
    direction: SwapDirection,
    ctx: QuoteContext,
  ): QuoteResult;

  /**
   * Upper bound on a sane `amountIn` for this pool and direction. Used by the
   * sizing search to bracket its interval. Must be a value `quote()` accepts.
   */
  maxAmountIn(pool: PoolSnapshot, direction: SwapDirection, ctx: QuoteContext): bigint;

  /** Accounts that must be subscribed to keep this pool's snapshot fresh. */
  requiredAccounts(pool: PoolSnapshot): string[];
}
