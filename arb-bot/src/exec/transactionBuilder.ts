/**
 * Atomic cycle construction.
 *
 * THE ATOMICITY ARGUMENT (§5), in full, because it is the load-bearing claim of
 * the whole bot:
 *
 *   Leg 1 asks for an EXACT amount of the intermediate token while capping the
 *   base spent (`swap_base_output` on Raydium, `buy` on PumpSwap). So after leg
 *   1 we hold exactly `intermediateAmount`, and we have spent AT MOST
 *   `amountIn`.
 *
 *   Leg 2 sells exactly that amount and demands a minimum output
 *   (`swap_base_input`'s `minimum_amount_out`, `sell`'s `min_quote_amount_out`)
 *   set to `amountIn + minProfit`.
 *
 *   Both programs enforce their bound with a `require`, so if either fails the
 *   whole transaction reverts. On success the base-asset balance is up by at
 *   least `minProfit`, and the intermediate balance is back where it started
 *   because leg 2 sold precisely what leg 1 produced.
 *
 * No on-chain program of our own is needed for this, and none is included: the
 * two venues already expose the exact bounds the assertion requires. What
 * `minProfit` must cover is the part the on-chain assertion CANNOT see — the
 * base fee, the priority fee, the tip and any rent — because those are paid in
 * native SOL rather than in the asset being asserted on. costs/profitNet.ts
 * sizes it accordingly.
 */
import {
  ComputeBudgetProgram,
  MessageV0,
  PublicKey,
  VersionedTransaction,
  type AddressLookupTableAccount,
  type TransactionInstruction,
} from "@solana/web3.js";
import type { MintState, PoolSnapshot, SizedCycle } from "../types.js";
import type { RaydiumCpmmPoolData } from "../quoters/cpmm/raydiumCpmm.js";
import type { PumpSwapPoolData } from "../quoters/cpmm/pumpSwap.js";
import {
  InstructionBuildError,
  createAtaIdempotentIx,
  pumpBuyIx,
  pumpSellIx,
  raydiumSwapBaseInputIx,
  raydiumSwapBaseOutputIx,
  tipIx,
} from "./instructions.js";
import { associatedTokenAddress } from "../screener/pdas.js";
import { TOKEN_PROGRAM_ID } from "../feed/decoder/token2022.js";

/** Hard limit on a serialized Solana transaction. */
export const MAX_TRANSACTION_BYTES = 1232;

export interface BuildCycleArgs {
  sized: SizedCycle;
  buyPool: PoolSnapshot;
  sellPool: PoolSnapshot;
  mints: ReadonlyMap<string, MintState>;
  payer: PublicKey;
  /** The wallet's base-asset (WSOL) token account. */
  baseTokenAccount: PublicKey;
  /** The wallet's token account for the intermediate mint. */
  intermediateTokenAccount: PublicKey;
  /** Profit the transaction must clear on-chain or revert. */
  minProfitLamports: bigint;
  computeUnitLimit: number;
  computeUnitPriceMicroLamports: bigint;
  tip?: { account: PublicKey; lamports: bigint };
  /** Include an idempotent ATA creation for the intermediate mint. */
  createIntermediateAta: boolean;
  recentBlockhash: string;
  lookupTables?: AddressLookupTableAccount[];
}

export interface BuiltCycle {
  transaction: VersionedTransaction;
  /** The on-chain bound leg 2 will enforce. */
  minimumOutLamports: bigint;
  /** The cap leg 1 will enforce. */
  maximumInLamports: bigint;
  /** Exact intermediate amount leg 1 produces and leg 2 consumes. */
  intermediateAmount: bigint;
  instructionCount: number;
  serializedBytes: number;
  accountCount: number;
}

export class CycleBuildError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CycleBuildError";
  }
}

export function buildArbitrageCycle(args: BuildCycleArgs): BuiltCycle {
  const { sized, minProfitLamports } = args;

  if (sized.amountIn <= 0n || sized.intermediateAmount <= 0n) {
    throw new CycleBuildError("cycle has a non-positive leg amount");
  }
  if (sized.buyPoolId === sized.sellPoolId) {
    throw new CycleBuildError("buy and sell legs use the same pool");
  }

  // The bound that makes the transaction self-asserting.
  const minimumOut = sized.amountIn + minProfitLamports;
  const maximumIn = sized.amountIn;

  const instructions: TransactionInstruction[] = [
    ComputeBudgetProgram.setComputeUnitLimit({ units: args.computeUnitLimit }),
    ComputeBudgetProgram.setComputeUnitPrice({
      microLamports: args.computeUnitPriceMicroLamports,
    }),
  ];

  const intermediateProgram = tokenProgramFor(args.mints, sized.intermediateMint);
  if (args.createIntermediateAta) {
    instructions.push(
      createAtaIdempotentIx({
        payer: args.payer,
        owner: args.payer,
        mint: new PublicKey(sized.intermediateMint),
        tokenProgram: intermediateProgram,
      }),
    );
  }

  instructions.push(
    buildBuyLeg({
      pool: args.buyPool,
      payer: args.payer,
      baseMint: sized.baseMint,
      intermediateMint: sized.intermediateMint,
      baseTokenAccount: args.baseTokenAccount,
      intermediateTokenAccount: args.intermediateTokenAccount,
      exactIntermediateOut: sized.intermediateAmount,
      maxBaseIn: maximumIn,
    }),
  );

  instructions.push(
    buildSellLeg({
      pool: args.sellPool,
      payer: args.payer,
      baseMint: sized.baseMint,
      intermediateMint: sized.intermediateMint,
      baseTokenAccount: args.baseTokenAccount,
      intermediateTokenAccount: args.intermediateTokenAccount,
      exactIntermediateIn: sized.intermediateAmount,
      minBaseOut: minimumOut,
    }),
  );

  if (args.tip && args.tip.lamports > 0n) {
    // Last, so that a revert on the profit assertion takes the tip with it.
    instructions.push(tipIx(args.payer, args.tip.account, args.tip.lamports));
  }

  const message = MessageV0.compile({
    payerKey: args.payer,
    instructions,
    recentBlockhash: args.recentBlockhash,
    addressLookupTableAccounts: args.lookupTables ?? [],
  });
  const transaction = new VersionedTransaction(message);

  // One signature is added at signing time; account for it in the size check.
  const serializedBytes = transaction.serialize().length + 64;
  if (serializedBytes > MAX_TRANSACTION_BYTES) {
    throw new CycleBuildError(
      `transaction is ${serializedBytes} bytes, over the ${MAX_TRANSACTION_BYTES} limit — ` +
        `use an address lookup table (npm run setup:alt) to compress the static accounts`,
    );
  }

  return {
    transaction,
    minimumOutLamports: minimumOut,
    maximumInLamports: maximumIn,
    intermediateAmount: sized.intermediateAmount,
    instructionCount: instructions.length,
    serializedBytes,
    accountCount: message.staticAccountKeys.length,
  };
}

interface LegArgs {
  pool: PoolSnapshot;
  payer: PublicKey;
  baseMint: string;
  intermediateMint: string;
  baseTokenAccount: PublicKey;
  intermediateTokenAccount: PublicKey;
}

/** Leg 1: base in (capped), exact intermediate out. */
function buildBuyLeg(
  a: LegArgs & { exactIntermediateOut: bigint; maxBaseIn: bigint },
): TransactionInstruction {
  if (a.pool.family === "raydium-cpmm") {
    const d = a.pool.data as RaydiumCpmmPoolData;
    const { inputVault, outputVault, inputProgram, outputProgram } = raydiumSides(
      d,
      a.baseMint,
      a.intermediateMint,
    );
    return raydiumSwapBaseOutputIx(
      {
        payer: a.payer,
        ammConfig: new PublicKey(d.ammConfig.address),
        poolState: new PublicKey(a.pool.poolId),
        userInputTokenAccount: a.baseTokenAccount,
        userOutputTokenAccount: a.intermediateTokenAccount,
        inputVault,
        outputVault,
        inputTokenProgram: inputProgram,
        outputTokenProgram: outputProgram,
        inputTokenMint: new PublicKey(a.baseMint),
        outputTokenMint: new PublicKey(a.intermediateMint),
      },
      a.maxBaseIn,
      a.exactIntermediateOut,
    );
  }

  const d = a.pool.data as PumpSwapPoolData;
  assertPumpTradable(d, a.pool.poolId);
  if (d.quoteMint !== a.baseMint || d.baseMint !== a.intermediateMint) {
    throw new CycleBuildError(
      `pump pool ${a.pool.poolId} is ${d.baseMint}/${d.quoteMint}, cannot buy ${a.intermediateMint} with ${a.baseMint}`,
    );
  }
  return pumpBuyIx(
    pumpAccounts(d, a.pool.poolId, a.payer, a.intermediateTokenAccount, a.baseTokenAccount),
    a.exactIntermediateOut,
    a.maxBaseIn,
  );
}

/** Leg 2: exact intermediate in, minimum base out — the profit assertion. */
function buildSellLeg(
  a: LegArgs & { exactIntermediateIn: bigint; minBaseOut: bigint },
): TransactionInstruction {
  if (a.pool.family === "raydium-cpmm") {
    const d = a.pool.data as RaydiumCpmmPoolData;
    const { inputVault, outputVault, inputProgram, outputProgram } = raydiumSides(
      d,
      a.intermediateMint,
      a.baseMint,
    );
    return raydiumSwapBaseInputIx(
      {
        payer: a.payer,
        ammConfig: new PublicKey(d.ammConfig.address),
        poolState: new PublicKey(a.pool.poolId),
        userInputTokenAccount: a.intermediateTokenAccount,
        userOutputTokenAccount: a.baseTokenAccount,
        inputVault,
        outputVault,
        inputTokenProgram: inputProgram,
        outputTokenProgram: outputProgram,
        inputTokenMint: new PublicKey(a.intermediateMint),
        outputTokenMint: new PublicKey(a.baseMint),
      },
      a.exactIntermediateIn,
      a.minBaseOut,
    );
  }

  const d = a.pool.data as PumpSwapPoolData;
  assertPumpTradable(d, a.pool.poolId);
  if (d.baseMint !== a.intermediateMint || d.quoteMint !== a.baseMint) {
    throw new CycleBuildError(
      `pump pool ${a.pool.poolId} is ${d.baseMint}/${d.quoteMint}, cannot sell ${a.intermediateMint} for ${a.baseMint}`,
    );
  }
  return pumpSellIx(
    pumpAccounts(d, a.pool.poolId, a.payer, a.intermediateTokenAccount, a.baseTokenAccount),
    a.exactIntermediateIn,
    a.minBaseOut,
  );
}

function raydiumSides(
  d: RaydiumCpmmPoolData,
  inputMint: string,
  outputMint: string,
): {
  inputVault: PublicKey;
  outputVault: PublicKey;
  inputProgram: PublicKey;
  outputProgram: PublicKey;
} {
  const zeroForOne = inputMint === d.token0Mint;
  if (!zeroForOne && inputMint !== d.token1Mint) {
    throw new CycleBuildError(`mint ${inputMint} is not in raydium pool`);
  }
  const expectedOut = zeroForOne ? d.token1Mint : d.token0Mint;
  if (expectedOut !== outputMint) {
    throw new CycleBuildError(`raydium pool does not pair ${inputMint} with ${outputMint}`);
  }
  return {
    inputVault: new PublicKey(zeroForOne ? d.token0Vault : d.token1Vault),
    outputVault: new PublicKey(zeroForOne ? d.token1Vault : d.token0Vault),
    inputProgram: new PublicKey(zeroForOne ? d.token0Program : d.token1Program),
    outputProgram: new PublicKey(zeroForOne ? d.token1Program : d.token0Program),
  };
}

/**
 * PumpSwap pools in "mayhem mode" pay their protocol fee to a reserved
 * recipient set we do not model, so we refuse to build against them rather
 * than guess a recipient and have the program reject the transaction — or
 * worse, accept it and pay the wrong account.
 */
function assertPumpTradable(d: PumpSwapPoolData, poolId: string): void {
  if (d.isMayhemMode) {
    throw new CycleBuildError(
      `pump pool ${poolId} is in mayhem mode; its fee recipient set is not modelled`,
    );
  }
  if (d.globalConfig.protocolFeeRecipients.length === 0) {
    throw new CycleBuildError("pump global config lists no protocol fee recipient");
  }
}

function pumpAccounts(
  d: PumpSwapPoolData,
  poolId: string,
  user: PublicKey,
  userBaseTokenAccount: PublicKey,
  userQuoteTokenAccount: PublicKey,
) {
  const recipient = d.globalConfig.protocolFeeRecipients.find(
    (r) => r !== "11111111111111111111111111111111",
  );
  if (!recipient) throw new CycleBuildError("no usable pump protocol fee recipient");
  return {
    pool: new PublicKey(poolId),
    user,
    baseMint: new PublicKey(d.baseMint),
    quoteMint: new PublicKey(d.quoteMint),
    userBaseTokenAccount,
    userQuoteTokenAccount,
    poolBaseTokenAccount: new PublicKey(d.poolBaseTokenAccount),
    poolQuoteTokenAccount: new PublicKey(d.poolQuoteTokenAccount),
    protocolFeeRecipient: new PublicKey(recipient),
    baseTokenProgram: new PublicKey(d.baseTokenProgram || TOKEN_PROGRAM_ID),
    quoteTokenProgram: new PublicKey(d.quoteTokenProgram || TOKEN_PROGRAM_ID),
    coinCreator: new PublicKey(d.coinCreator),
  };
}

function tokenProgramFor(mints: ReadonlyMap<string, MintState>, mint: string): PublicKey {
  const m = mints.get(mint);
  if (!m) throw new CycleBuildError(`mint state missing for ${mint}`);
  return new PublicKey(m.programId);
}

/** Where the wallet's token account for a mint lives. */
export function walletTokenAccount(
  mints: ReadonlyMap<string, MintState>,
  mint: string,
  owner: PublicKey,
): PublicKey {
  return associatedTokenAddress(mint, owner, tokenProgramFor(mints, mint));
}

export { InstructionBuildError };
