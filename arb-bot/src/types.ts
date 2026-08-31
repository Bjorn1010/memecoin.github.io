/**
 * Core domain types shared across the bot.
 *
 * Design rules enforced here:
 *  - every amount is a bigint of base units;
 *  - every piece of on-chain state carries the slot it was observed at and the
 *    wall-clock time we received it, so staleness is always computable;
 *  - a quote always states which reserves it used, so a quote can be replayed
 *    and audited after the fact.
 */

/** Families of AMM we can quote exactly. Adding one means adding a Quoter. */
export type DexFamily = "raydium-cpmm" | "pump-swap";

/** How confident we are that a quoter reproduces on-chain execution exactly. */
export type Exactness =
  /** Replicates the on-chain program instruction-for-instruction. */
  | "exact"
  /** Structure known but at least one input is assumed. Never traded live. */
  | "unverified";

export interface StateMeta {
  /** Slot the underlying account data was observed at. */
  slot: number;
  /** Local monotonic-ish wall clock (Date.now()) when we received it. */
  receivedAt: number;
  /** Where the state came from, for debugging feed problems. */
  source: "ws" | "rpc" | "replay";
}

/** A decoded SPL / Token-2022 token account balance with freshness metadata. */
export interface TokenAccountState extends StateMeta {
  address: string;
  mint: string;
  owner: string;
  amount: bigint;
}

/** Mint-level facts needed both for quoting and for risk filtering. */
export interface MintState extends StateMeta {
  address: string;
  decimals: number;
  supply: bigint;
  /** Owning program: SPL Token or Token-2022. */
  programId: string;
  mintAuthority: string | null;
  freezeAuthority: string | null;
  /** Parsed Token-2022 extensions, empty for classic SPL mints. */
  extensions: MintExtensionSummary;
}

export interface MintExtensionSummary {
  /** Raw extension type ids found on the mint (Token-2022 TLV). */
  present: number[];
  /** Transfer fee config, if the TransferFeeConfig extension is present. */
  transferFee: {
    /** Basis points charged on transfer at the current epoch. */
    basisPoints: number;
    maximumFee: bigint;
  } | null;
  /** True if a transfer hook program is configured (makes cost non-deterministic for us). */
  hasTransferHook: boolean;
  /** True if the mint is non-transferable. */
  nonTransferable: boolean;
  /** True if the mint has a permanent delegate (a third party can move our balance). */
  hasPermanentDelegate: boolean;
  /** True if the mint has default account state = frozen. */
  defaultAccountStateFrozen: boolean;
  /** True if the mint carries confidential-transfer machinery we do not model. */
  hasConfidentialTransfers: boolean;
}

/** Direction of a swap through a pool, expressed by mints to avoid index bugs. */
export interface SwapDirection {
  inputMint: string;
  outputMint: string;
}

/** Everything a quoter needs about one pool, already decoded and fresh-stamped. */
export interface PoolSnapshot {
  family: DexFamily;
  poolId: string;
  /** Mints traded by the pool. */
  mintA: string;
  mintB: string;
  /** Slot of the *oldest* account making up this snapshot. */
  slot: number;
  /** receivedAt of the *oldest* account making up this snapshot. */
  receivedAt: number;
  source: StateMeta["source"];
  /** Addresses of every account this snapshot is derived from. */
  accounts: string[];
  /**
   * True when every volatile account behind this snapshot is covered by a live
   * subscription. A subscribed account is current even if we read it over RPC
   * minutes ago: the subscription would have told us about any change since.
   */
  subscribed: boolean;
  /** Family-specific decoded payload. Narrowed by the quoter. */
  data: unknown;
}

export interface QuoteFees {
  /** Fee charged in units of the input token. */
  inInputToken: bigint;
  /** Fee charged in units of the output token. */
  inOutputToken: bigint;
  /** Named breakdown for auditing; keys are family-specific. */
  breakdown: Record<string, bigint>;
}

export interface QuoteResult {
  family: DexFamily;
  poolId: string;
  direction: SwapDirection;
  amountIn: bigint;
  /** Amount credited to the user's output token account, net of every fee. */
  amountOut: bigint;
  fees: QuoteFees;
  /** Effective reserves used, after any protocol-side adjustment. */
  reserveIn: bigint;
  reserveOut: bigint;
  slot: number;
  receivedAt: number;
  exactness: Exactness;
  /**
   * Largest amountIn this quote function is willing to price for this pool.
   * Beyond it the result is not meaningful (depth exhausted / program would
   * revert). Sizing must respect this.
   */
  maxAmountIn: bigint;
}

/** A candidate two-leg cycle: base -> intermediate -> base, atomically. */
export interface CycleCandidate {
  /** The asset we start and end in. Always WSOL in the current build. */
  baseMint: string;
  intermediateMint: string;
  /** Pool used for leg 1 (base -> intermediate). */
  buyPoolId: string;
  buyFamily: DexFamily;
  /** Pool used for leg 2 (intermediate -> base). */
  sellPoolId: string;
  sellFamily: DexFamily;
}

export interface SizedCycle extends CycleCandidate {
  amountIn: bigint;
  intermediateAmount: bigint;
  amountOut: bigint;
  grossProfit: bigint;
  /** Oldest slot across every account used by both legs. */
  slot: number;
  receivedAt: number;
  legs: [QuoteResult, QuoteResult];
}

/** Why an opportunity did not become a sent transaction. Never merged in metrics. */
export type RejectReason =
  | "no-cycle"
  | "stale-state"
  | "not-profitable-gross"
  | "not-profitable-net"
  | "negative-expected-value"
  | "below-min-profit"
  | "size-below-dust"
  | "depth-limited-unprofitable"
  | "risk-token-rejected"
  | "risk-limit-exceeded"
  | "kill-switch"
  | "locked-in-flight"
  | "quote-unverified"
  | "simulation-failed"
  | "simulation-disagrees"
  | "simulation-unprofitable"
  | "build-failed"
  | "rpc-budget-exhausted"
  | "send-failed";

/** Terminal outcome of an attempt. These five buckets are never mixed (§6). */
export type AttemptOutcome =
  | "not-sent"
  | "simulated-abandoned"
  | "sent-not-landed"
  | "landed-profitable"
  | "landed-unprofitable";
