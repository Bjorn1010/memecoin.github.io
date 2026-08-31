/**
 * Token admission policy.
 *
 * Fail-closed by construction: a mint is rejected unless every property we rely
 * on is verified. A token whose transfer behaviour we cannot compute exactly
 * makes our profit assertion meaningless, so it is refused outright rather than
 * "handled later" (§29).
 *
 * Every rejection carries a machine-readable code so the screener can penalise
 * the pool and the report can show which class of token is wasting our time.
 */
import type { MintState } from "../types.js";
import { BENIGN_MINT_EXTENSIONS, ExtensionId, TOKEN_2022_PROGRAM_ID, TOKEN_PROGRAM_ID } from "../feed/decoder/token2022.js";

export type TokenRejectCode =
  | "unknown-token-program"
  | "transfer-fee"
  | "transfer-hook"
  | "non-transferable"
  | "permanent-delegate"
  | "default-frozen"
  | "confidential-transfers"
  | "unrecognised-extension"
  | "freeze-authority"
  | "mint-authority"
  | "decimals-out-of-range"
  | "zero-supply"
  | "blacklisted"
  | "not-whitelisted"
  | "insufficient-liquidity"
  | "pool-too-young";

export interface TokenPolicy {
  /** Reject a mint that can still be frozen by an authority. */
  rejectFreezeAuthority: boolean;
  /**
   * Reject a mint whose supply can still be inflated. Most legitimate
   * memecoins revoke this; a live mint authority means the "reserves" we quote
   * against can be diluted between our quote and our execution.
   */
  rejectMintAuthority: boolean;
  /** Allowed decimals range. Anything outside is a sign of something odd. */
  minDecimals: number;
  maxDecimals: number;
  /** Minimum usable depth, in base-asset lamports, for the pool to be tradable. */
  minPoolLiquidityLamports: bigint;
  /** Pools younger than this are refused: too little history to price risk. */
  minPoolAgeMs: number;
  /** Mints never traded, whatever else says. */
  blacklist: ReadonlySet<string>;
  /** When non-empty, only these mints may be traded. */
  whitelist: ReadonlySet<string>;
}

export const DEFAULT_TOKEN_POLICY: TokenPolicy = {
  rejectFreezeAuthority: true,
  rejectMintAuthority: false,
  minDecimals: 0,
  maxDecimals: 18,
  minPoolLiquidityLamports: 500_000_000n, // 0.5 SOL of usable depth
  minPoolAgeMs: 10 * 60_000,
  blacklist: new Set<string>(),
  whitelist: new Set<string>(),
};

export interface TokenVerdict {
  accepted: boolean;
  rejections: { code: TokenRejectCode; detail: string }[];
}

export interface TokenCheckContext {
  /** Usable depth of the pool this mint would be traded through. */
  poolLiquidityLamports?: bigint;
  /** Age of the pool in ms, if known. */
  poolAgeMs?: number;
}

export function checkMint(
  mint: MintState,
  policy: TokenPolicy = DEFAULT_TOKEN_POLICY,
  ctx: TokenCheckContext = {},
): TokenVerdict {
  const rejections: TokenVerdict["rejections"] = [];
  const reject = (code: TokenRejectCode, detail: string): void => {
    rejections.push({ code, detail });
  };

  if (policy.blacklist.has(mint.address)) {
    reject("blacklisted", "mint is on the blacklist");
  }
  if (policy.whitelist.size > 0 && !policy.whitelist.has(mint.address)) {
    reject("not-whitelisted", "a whitelist is configured and this mint is not on it");
  }

  if (mint.programId !== TOKEN_PROGRAM_ID && mint.programId !== TOKEN_2022_PROGRAM_ID) {
    reject("unknown-token-program", `owner program ${mint.programId} is not a token program`);
  }

  if (mint.decimals < policy.minDecimals || mint.decimals > policy.maxDecimals) {
    reject("decimals-out-of-range", `decimals=${mint.decimals}`);
  }
  if (mint.supply === 0n) {
    reject("zero-supply", "supply is zero, the pool cannot be priced");
  }

  if (policy.rejectFreezeAuthority && mint.freezeAuthority !== null) {
    reject("freeze-authority", `freeze authority ${mint.freezeAuthority} can freeze our account mid-cycle`);
  }
  if (policy.rejectMintAuthority && mint.mintAuthority !== null) {
    reject("mint-authority", `mint authority ${mint.mintAuthority} can dilute the reserves`);
  }

  const ext = mint.extensions;
  if (ext.transferFee && ext.transferFee.basisPoints > 0) {
    reject("transfer-fee", `transfer fee of ${ext.transferFee.basisPoints} bps makes the cycle non-deterministic`);
  }
  if (ext.hasTransferHook) {
    reject("transfer-hook", "a transfer hook can run arbitrary code and change the cost of a transfer");
  }
  if (ext.nonTransferable) {
    reject("non-transferable", "the mint cannot be transferred at all");
  }
  if (ext.hasPermanentDelegate) {
    reject("permanent-delegate", "a permanent delegate can move our balance without our signature");
  }
  if (ext.defaultAccountStateFrozen) {
    reject("default-frozen", "new token accounts are created frozen");
  }
  if (ext.hasConfidentialTransfers) {
    reject("confidential-transfers", "confidential transfer machinery is not modelled");
  }

  // Fail closed on anything we do not recognise, including extensions that did
  // not exist when this was written.
  for (const id of ext.present) {
    if (BENIGN_MINT_EXTENSIONS.has(id)) continue;
    // The specific ones above already produced a precise message.
    if (
      id === ExtensionId.TransferFeeConfig ||
      id === ExtensionId.TransferHook ||
      id === ExtensionId.NonTransferable ||
      id === ExtensionId.PermanentDelegate ||
      id === ExtensionId.DefaultAccountState ||
      id === ExtensionId.ConfidentialTransferMint ||
      id === ExtensionId.ConfidentialTransferFeeConfig
    ) {
      continue;
    }
    reject("unrecognised-extension", `extension id ${id} is not on the benign allowlist`);
  }

  if (ctx.poolLiquidityLamports !== undefined && ctx.poolLiquidityLamports < policy.minPoolLiquidityLamports) {
    reject(
      "insufficient-liquidity",
      `usable depth ${ctx.poolLiquidityLamports} < ${policy.minPoolLiquidityLamports}`,
    );
  }
  if (ctx.poolAgeMs !== undefined && ctx.poolAgeMs < policy.minPoolAgeMs) {
    reject("pool-too-young", `pool age ${ctx.poolAgeMs}ms < ${policy.minPoolAgeMs}ms`);
  }

  return { accepted: rejections.length === 0, rejections };
}

/** Convenience for the hot path: accepted or not, with the first reason. */
export function summariseVerdict(v: TokenVerdict): string {
  if (v.accepted) return "accepted";
  return v.rejections.map((r) => r.code).join(",");
}
