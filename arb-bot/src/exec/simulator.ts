/**
 * Pre-send simulation.
 *
 * Three jobs, all of which exist because guessing any of them costs money:
 *  1. measure compute units instead of guessing them (§17), so the CU limit is
 *     neither so low the transaction fails nor so high we overpay the priority
 *     fee on units we never use;
 *  2. re-confirm the profit against the chain's own arithmetic immediately
 *     before sending, and ABANDON if it no longer clears the bar (§20) — there
 *     is no "send it anyway" path in this file;
 *  3. measure the divergence between our quote and the simulation, which is the
 *     early warning that a quoter has drifted from the deployed program.
 */
import {
  VersionedTransaction,
  type SimulatedTransactionResponse,
} from "@solana/web3.js";
import type { RpcClient } from "../rpc/RpcClient.js";
import { RpcPriority } from "../rpc/RpcBudget.js";
import { decodeTokenAccount } from "../feed/decoder/token2022.js";
import { bpsOf } from "../util/bigintMath.js";
import { priorityFeeLamports } from "../costs/fees.js";

export interface SimulationOutcome {
  ok: boolean;
  /** Compute units the transaction actually consumed. */
  unitsConsumed: number | null;
  /** Base-asset balance the simulation leaves us with, when observable. */
  baseBalanceAfter: bigint | null;
  /** Realised profit according to the simulation. */
  simulatedProfit: bigint | null;
  /** |simulated - expected| in bps of expected, when both are known. */
  divergenceBps: number | null;
  /** Program error, if the simulation failed. */
  error: string | null;
  logs: string[];
  slot: number;
}

export interface SimulateCycleArgs {
  rpc: RpcClient;
  transaction: VersionedTransaction;
  /** The wallet's base-asset token account, read back after simulation. */
  baseTokenAccount: string;
  /** Base balance before the cycle, to derive the simulated profit. */
  baseBalanceBefore: bigint;
  /** Profit our quoter predicted, for the divergence measurement. */
  expectedProfit: bigint;
}

export async function simulateCycle(args: SimulateCycleArgs): Promise<SimulationOutcome> {
  let response: { value: SimulatedTransactionResponse; context: { slot: number } };
  try {
    response = await args.rpc.simulate(
      args.transaction,
      {
        sigVerify: false,
        // Our blockhash may be a few slots old by now; let the node substitute a
        // current one so a stale blockhash cannot masquerade as a program error.
        replaceRecentBlockhash: true,
        commitment: "confirmed",
        accounts: { encoding: "base64", addresses: [args.baseTokenAccount] },
      },
      RpcPriority.P1_HotSimulation,
    );
  } catch (e) {
    return {
      ok: false,
      unitsConsumed: null,
      baseBalanceAfter: null,
      simulatedProfit: null,
      divergenceBps: null,
      error: e instanceof Error ? e.message : String(e),
      logs: [],
      slot: 0,
    };
  }

  const value = response.value;
  const logs = value.logs ?? [];
  const unitsConsumed = typeof value.unitsConsumed === "number" ? value.unitsConsumed : null;

  if (value.err) {
    return {
      ok: false,
      unitsConsumed,
      baseBalanceAfter: null,
      simulatedProfit: null,
      divergenceBps: null,
      error: describeSimulationError(value.err, logs),
      logs,
      slot: response.context.slot,
    };
  }

  let baseBalanceAfter: bigint | null = null;
  const account = value.accounts?.[0];
  if (account && Array.isArray(account.data) && typeof account.data[0] === "string") {
    try {
      baseBalanceAfter = decodeTokenAccount(Buffer.from(account.data[0], "base64")).amount;
    } catch {
      baseBalanceAfter = null;
    }
  }

  const simulatedProfit =
    baseBalanceAfter === null ? null : baseBalanceAfter - args.baseBalanceBefore;
  const divergenceBps =
    simulatedProfit === null || args.expectedProfit === 0n
      ? null
      : bpsOf(
          simulatedProfit > args.expectedProfit
            ? simulatedProfit - args.expectedProfit
            : args.expectedProfit - simulatedProfit,
          args.expectedProfit < 0n ? -args.expectedProfit : args.expectedProfit,
        );

  return {
    ok: true,
    unitsConsumed,
    baseBalanceAfter,
    simulatedProfit,
    divergenceBps,
    error: null,
    logs,
    slot: response.context.slot,
  };
}

/**
 * Turn a simulated CU measurement into the limit we will actually set.
 *
 * A margin is added because the state moves between simulation and execution
 * and a different code path (an extra tick crossed, an account newly created)
 * can cost more. The result is capped so a nonsense measurement cannot buy an
 * enormous priority fee.
 */
export function computeUnitLimitFrom(
  unitsConsumed: number | null,
  marginBps: number,
  maxLimit: number,
  fallback = 200_000,
): number {
  const measured = unitsConsumed ?? fallback;
  const withMargin = Math.ceil(measured * (1 + marginBps / 10_000));
  return Math.max(1_000, Math.min(withMargin, maxLimit));
}

/**
 * Check our priority-fee formula against the cluster's own answer.
 *
 * `getFeeForMessage` returns what the node will actually charge for exactly
 * this message. If our model disagrees, every expected-value computation
 * downstream is wrong, so this is called once at startup and the result is
 * reported rather than assumed.
 */
export async function verifyPriorityFeeModel(
  rpc: RpcClient,
  transaction: VersionedTransaction,
  computeUnitLimit: number,
  computeUnitPriceMicroLamports: bigint,
  lamportsPerSignature: bigint,
  numSignatures: number,
): Promise<{ agrees: boolean; ours: bigint; cluster: bigint | null }> {
  const cluster = await rpc.getFeeForMessage(transaction.message, RpcPriority.P0_Critical);
  const ours =
    lamportsPerSignature * BigInt(numSignatures) +
    priorityFeeLamports(computeUnitLimit, computeUnitPriceMicroLamports);
  return { agrees: cluster !== null && cluster === ours, ours, cluster };
}

function describeSimulationError(err: unknown, logs: readonly string[]): string {
  const base = typeof err === "string" ? err : JSON.stringify(err);
  // The program's own error line is far more useful than the instruction index.
  const programError = logs.find(
    (l) => l.includes("Error Message:") || l.includes("custom program error"),
  );
  return programError ? `${base} (${programError.trim()})` : base;
}

/** Slippage-bound failures are expected and cheap; distinguish them. */
export function isSlippageFailure(outcome: SimulationOutcome): boolean {
  if (outcome.ok) return false;
  const haystack = [outcome.error ?? "", ...outcome.logs].join(" ");
  return /ExceededSlippage|slippage|max_quote_amount_in|min_quote_amount_out|TooLittleSolReceived|TooMuchSolRequired/i.test(
    haystack,
  );
}
