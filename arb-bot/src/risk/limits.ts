/**
 * Position and exposure limits.
 *
 * Everything here is a hard gate evaluated immediately before a send. Limits
 * are not advisory: a breach rejects the opportunity, it does not scale it
 * down, because a limit that silently resizes a trade hides the fact that the
 * bot is operating at its ceiling.
 */
import type { RejectReason } from "../types.js";

export interface RiskLimits {
  /** Largest single trade, in base-asset lamports. */
  maxTradeSizeLamports: bigint;
  /**
   * Largest total value we may hold in non-base tokens at any instant. In an
   * atomic cycle this should be zero between transactions; a non-zero value
   * means residue accumulated and something is wrong.
   */
  maxTokenExposureLamports: bigint;
  /** Concurrent transactions allowed in flight. */
  maxInFlightTx: number;
  /** Realised loss in a UTC day that trips the kill switch. */
  maxDailyLossLamports: bigint;
  /** Native SOL we always keep for fees, never traded. */
  reserveLamports: bigint;
}

export interface WalletSnapshot {
  /** Native SOL balance, used for fees. */
  nativeLamports: bigint;
  /** Base-asset (WSOL) balance available to trade. */
  baseTokenLamports: bigint;
  /** Value of intermediate tokens we are still holding, in base lamports. */
  tokenExposureLamports: bigint;
  inFlightTx: number;
}

export interface LimitCheckInput {
  limits: RiskLimits;
  wallet: WalletSnapshot;
  /** Trade we would like to place. */
  amountIn: bigint;
  /** Total lamports the transaction will cost if it succeeds. */
  costOnSuccess: bigint;
  /** Realised PnL so far today, negative when losing. */
  dailyRealisedPnl: bigint;
}

export interface LimitVerdict {
  allowed: boolean;
  reason: RejectReason | "ok";
  detail: string;
}

export function checkLimits(i: LimitCheckInput): LimitVerdict {
  const { limits, wallet, amountIn } = i;

  if (i.dailyRealisedPnl <= -limits.maxDailyLossLamports) {
    return {
      allowed: false,
      reason: "kill-switch",
      detail: `daily realised PnL ${i.dailyRealisedPnl} has reached the -${limits.maxDailyLossLamports} limit`,
    };
  }

  if (wallet.inFlightTx >= limits.maxInFlightTx) {
    return {
      allowed: false,
      reason: "risk-limit-exceeded",
      detail: `${wallet.inFlightTx} transactions already in flight (max ${limits.maxInFlightTx})`,
    };
  }

  if (amountIn > limits.maxTradeSizeLamports) {
    return {
      allowed: false,
      reason: "risk-limit-exceeded",
      detail: `trade size ${amountIn} exceeds MAX_TRADE_SIZE ${limits.maxTradeSizeLamports}`,
    };
  }

  if (amountIn > wallet.baseTokenLamports) {
    return {
      allowed: false,
      reason: "risk-limit-exceeded",
      detail: `trade size ${amountIn} exceeds the tradable base balance ${wallet.baseTokenLamports}`,
    };
  }

  if (wallet.tokenExposureLamports > limits.maxTokenExposureLamports) {
    return {
      allowed: false,
      reason: "risk-limit-exceeded",
      detail: `token exposure ${wallet.tokenExposureLamports} exceeds MAX_TOKEN_EXPOSURE ${limits.maxTokenExposureLamports}`,
    };
  }

  // Fees are paid in native SOL, which is a different pot from the WSOL we
  // trade with. Running it dry stops the bot dead, so keep a reserve.
  if (wallet.nativeLamports < i.costOnSuccess + limits.reserveLamports) {
    return {
      allowed: false,
      reason: "risk-limit-exceeded",
      detail: `native balance ${wallet.nativeLamports} below cost ${i.costOnSuccess} plus reserve ${limits.reserveLamports}`,
    };
  }

  return { allowed: true, reason: "ok", detail: "within limits" };
}

/** Capital the sizing search is allowed to use, after the fee reserve. */
export function tradableCapital(wallet: WalletSnapshot, limits: RiskLimits): bigint {
  const available = wallet.baseTokenLamports;
  const capped = available < limits.maxTradeSizeLamports ? available : limits.maxTradeSizeLamports;
  return capped > 0n ? capped : 0n;
}
