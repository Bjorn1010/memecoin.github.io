/**
 * Instruction encoders for the two venues.
 *
 * Discriminators, argument order and account order all come from the IDLs the
 * programs publish on-chain, and are quoted in the comments so a reviewer can
 * check them without leaving the file. Getting the account ORDER wrong is the
 * classic way to build a transaction that simulates fine against the wrong
 * account and then does something else entirely on-chain, so each list is
 * written out index by index.
 */
import {
  PublicKey,
  SystemProgram,
  TransactionInstruction,
  type AccountMeta,
} from "@solana/web3.js";
import {
  ASSOCIATED_TOKEN_PROGRAM,
  PUMP_AMM_PROGRAM,
  PUMP_FEE_PROGRAM,
  RAYDIUM_CPMM_PROGRAM,
  SYSTEM_PROGRAM,
  associatedTokenAddress,
  pumpCreatorVaultAuthority,
  pumpEventAuthority,
  pumpFeeConfig,
  pumpGlobalConfig,
  pumpGlobalVolumeAccumulator,
  pumpUserVolumeAccumulator,
  raydiumAuthority,
  raydiumObservation,
} from "../screener/pdas.js";

export const RAYDIUM_SWAP_BASE_INPUT_DISC = Buffer.from([143, 190, 90, 218, 196, 30, 51, 222]);
export const RAYDIUM_SWAP_BASE_OUTPUT_DISC = Buffer.from([55, 217, 98, 86, 163, 74, 180, 173]);
export const PUMP_BUY_DISC = Buffer.from([102, 6, 61, 18, 1, 218, 235, 234]);
export const PUMP_SELL_DISC = Buffer.from([51, 230, 133, 164, 1, 127, 131, 173]);

export class InstructionBuildError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InstructionBuildError";
  }
}

function u64(value: bigint): Buffer {
  if (value < 0n || value > 0xffff_ffff_ffff_ffffn) {
    throw new InstructionBuildError(`u64 out of range: ${value}`);
  }
  const b = Buffer.alloc(8);
  b.writeBigUInt64LE(value);
  return b;
}

function meta(pubkey: PublicKey, isSigner: boolean, isWritable: boolean): AccountMeta {
  return { pubkey, isSigner, isWritable };
}

// --- Raydium CP-Swap -------------------------------------------------------

export interface RaydiumSwapAccounts {
  payer: PublicKey;
  ammConfig: PublicKey;
  poolState: PublicKey;
  userInputTokenAccount: PublicKey;
  userOutputTokenAccount: PublicKey;
  inputVault: PublicKey;
  outputVault: PublicKey;
  inputTokenProgram: PublicKey;
  outputTokenProgram: PublicKey;
  inputTokenMint: PublicKey;
  outputTokenMint: PublicKey;
}

/**
 * Account order, from the IDL:
 *  0 payer [s] | 1 authority (PDA) | 2 amm_config | 3 pool_state [w]
 *  4 input_token_account [w] | 5 output_token_account [w]
 *  6 input_vault [w] | 7 output_vault [w]
 *  8 input_token_program | 9 output_token_program
 * 10 input_token_mint | 11 output_token_mint | 12 observation_state [w]
 */
function raydiumSwapMetas(a: RaydiumSwapAccounts): AccountMeta[] {
  return [
    meta(a.payer, true, false),
    meta(raydiumAuthority(), false, false),
    meta(a.ammConfig, false, false),
    meta(a.poolState, false, true),
    meta(a.userInputTokenAccount, false, true),
    meta(a.userOutputTokenAccount, false, true),
    meta(a.inputVault, false, true),
    meta(a.outputVault, false, true),
    meta(a.inputTokenProgram, false, false),
    meta(a.outputTokenProgram, false, false),
    meta(a.inputTokenMint, false, false),
    meta(a.outputTokenMint, false, false),
    meta(raydiumObservation(a.poolState), false, true),
  ];
}

/** `swap_base_input(amount_in, minimum_amount_out)`. */
export function raydiumSwapBaseInputIx(
  accounts: RaydiumSwapAccounts,
  amountIn: bigint,
  minimumAmountOut: bigint,
): TransactionInstruction {
  return new TransactionInstruction({
    programId: RAYDIUM_CPMM_PROGRAM,
    keys: raydiumSwapMetas(accounts),
    data: Buffer.concat([RAYDIUM_SWAP_BASE_INPUT_DISC, u64(amountIn), u64(minimumAmountOut)]),
  });
}

/**
 * `swap_base_output(max_amount_in, amount_out)`.
 *
 * Note the argument order: the maximum input comes FIRST. Swapping the two
 * would build a transaction that asks to receive `max_amount_in` tokens while
 * capping the spend at `amount_out` — usually an instant revert, but on the
 * wrong pool it could be an expensive success.
 */
export function raydiumSwapBaseOutputIx(
  accounts: RaydiumSwapAccounts,
  maxAmountIn: bigint,
  amountOut: bigint,
): TransactionInstruction {
  return new TransactionInstruction({
    programId: RAYDIUM_CPMM_PROGRAM,
    keys: raydiumSwapMetas(accounts),
    data: Buffer.concat([RAYDIUM_SWAP_BASE_OUTPUT_DISC, u64(maxAmountIn), u64(amountOut)]),
  });
}

// --- PumpSwap --------------------------------------------------------------

export interface PumpSwapAccounts {
  pool: PublicKey;
  user: PublicKey;
  baseMint: PublicKey;
  quoteMint: PublicKey;
  userBaseTokenAccount: PublicKey;
  userQuoteTokenAccount: PublicKey;
  poolBaseTokenAccount: PublicKey;
  poolQuoteTokenAccount: PublicKey;
  protocolFeeRecipient: PublicKey;
  baseTokenProgram: PublicKey;
  quoteTokenProgram: PublicKey;
  coinCreator: PublicKey;
}

/** The 19 accounts common to `buy` and `sell`, in IDL order. */
function pumpCommonMetas(a: PumpSwapAccounts): AccountMeta[] {
  const creatorVaultAuthority = pumpCreatorVaultAuthority(a.coinCreator.toBase58());
  return [
    meta(a.pool, false, true),
    meta(a.user, true, true),
    meta(pumpGlobalConfig(), false, false),
    meta(a.baseMint, false, false),
    meta(a.quoteMint, false, false),
    meta(a.userBaseTokenAccount, false, true),
    meta(a.userQuoteTokenAccount, false, true),
    meta(a.poolBaseTokenAccount, false, true),
    meta(a.poolQuoteTokenAccount, false, true),
    meta(a.protocolFeeRecipient, false, false),
    meta(
      associatedTokenAddress(a.quoteMint.toBase58(), a.protocolFeeRecipient, a.quoteTokenProgram),
      false,
      true,
    ),
    meta(a.baseTokenProgram, false, false),
    meta(a.quoteTokenProgram, false, false),
    meta(SYSTEM_PROGRAM, false, false),
    meta(ASSOCIATED_TOKEN_PROGRAM, false, false),
    meta(pumpEventAuthority(), false, false),
    meta(PUMP_AMM_PROGRAM, false, false),
    meta(
      associatedTokenAddress(a.quoteMint.toBase58(), creatorVaultAuthority, a.quoteTokenProgram),
      false,
      true,
    ),
    meta(creatorVaultAuthority, false, false),
  ];
}

/**
 * `sell(base_amount_in, min_quote_amount_out)`.
 *
 * This is the instruction that carries the cycle's profit assertion: setting
 * `min_quote_amount_out` to `amountIn + minProfit` makes the whole transaction
 * revert unless the round trip actually cleared that bar.
 *
 * Accounts: the 19 common ones, then fee_config, then fee_program.
 */
export function pumpSellIx(
  accounts: PumpSwapAccounts,
  baseAmountIn: bigint,
  minQuoteAmountOut: bigint,
): TransactionInstruction {
  return new TransactionInstruction({
    programId: PUMP_AMM_PROGRAM,
    keys: [
      ...pumpCommonMetas(accounts),
      meta(pumpFeeConfig(), false, false),
      meta(PUMP_FEE_PROGRAM, false, false),
    ],
    data: Buffer.concat([PUMP_SELL_DISC, u64(baseAmountIn), u64(minQuoteAmountOut)]),
  });
}

/**
 * `buy(base_amount_out, max_quote_amount_in, track_volume)`.
 *
 * Exact base out, capped quote in — the leg-1 shape that leaves no residue.
 * `track_volume` is an `OptionBool`, a one-byte struct wrapping a bool.
 *
 * Accounts: the 19 common ones, then global_volume_accumulator,
 * user_volume_accumulator, fee_config, fee_program. The user volume
 * accumulator is a per-wallet PDA that must already exist; the setup command
 * creates it once.
 */
export function pumpBuyIx(
  accounts: PumpSwapAccounts,
  baseAmountOut: bigint,
  maxQuoteAmountIn: bigint,
  trackVolume = false,
): TransactionInstruction {
  return new TransactionInstruction({
    programId: PUMP_AMM_PROGRAM,
    keys: [
      ...pumpCommonMetas(accounts),
      meta(pumpGlobalVolumeAccumulator(), false, false),
      meta(pumpUserVolumeAccumulator(accounts.user), false, true),
      meta(pumpFeeConfig(), false, false),
      meta(PUMP_FEE_PROGRAM, false, false),
    ],
    data: Buffer.concat([
      PUMP_BUY_DISC,
      u64(baseAmountOut),
      u64(maxQuoteAmountIn),
      Buffer.from([trackVolume ? 1 : 0]),
    ]),
  });
}

// --- SPL helpers -----------------------------------------------------------

/** `AssociatedTokenAccountInstruction::CreateIdempotent` is opcode 1. */
export function createAtaIdempotentIx(args: {
  payer: PublicKey;
  owner: PublicKey;
  mint: PublicKey;
  tokenProgram: PublicKey;
}): TransactionInstruction {
  const ata = associatedTokenAddress(args.mint.toBase58(), args.owner, args.tokenProgram);
  return new TransactionInstruction({
    programId: ASSOCIATED_TOKEN_PROGRAM,
    keys: [
      meta(args.payer, true, true),
      meta(ata, false, true),
      meta(args.owner, false, false),
      meta(args.mint, false, false),
      meta(SYSTEM_PROGRAM, false, false),
      meta(args.tokenProgram, false, false),
    ],
    data: Buffer.from([1]),
  });
}

/** A plain lamport transfer, used for the tip. */
export function tipIx(from: PublicKey, to: PublicKey, lamports: bigint): TransactionInstruction {
  return SystemProgram.transfer({
    fromPubkey: from,
    toPubkey: to,
    lamports,
  });
}
