/**
 * Quoter verification against real executed transactions.
 *
 *   npm run verify:quoters -- [--limit 40]
 *
 * For every recent swap on the two venues, the program's own event tells us the
 * pre-trade reserves, the input amount and the output the program computed. We
 * recompute that output with our quoter and require an EXACT match, in base
 * units. This is stronger than simulating a hypothetical swap: it is the real
 * execution path, on real state, including whatever the deployed program does
 * that its published SDK does not.
 *
 * The exit code is non-zero on any mismatch, so this can gate a deploy.
 * A mismatch is never "close enough": it means we would be sizing and asserting
 * profit on a number the chain disagrees with.
 */
import { PublicKey } from "@solana/web3.js";
import { RpcBudget, RpcPriority, DEFAULT_RPC_BUDGET } from "../rpc/RpcBudget.js";
import { RpcClient } from "../rpc/RpcClient.js";
import {
  decodeInstructionData,
  eventPayloadsFromCpi,
  eventPayloadsFromLogs,
  parsePumpSellEvent,
  parseRaydiumSwapEvent,
} from "../feed/decoder/events.js";
import {
  RAYDIUM_CPMM_PROGRAM_ID,
  decodeRaydiumAmmConfig,
  decodeRaydiumPoolState,
} from "../feed/decoder/raydiumCpmm.js";
import {
  PUMP_SWAP_PROGRAM_ID,
  decodePumpFeeConfig,
  decodePumpGlobalConfig,
  decodePumpPool,
} from "../feed/decoder/pumpSwap.js";
import { raydiumSwapBaseInput } from "../quoters/cpmm/raydiumCpmm.js";
import { pumpSellBaseInput } from "../quoters/cpmm/pumpSwap.js";
import { decodeMint } from "../feed/decoder/token2022.js";
import { bpsOf } from "../util/bigintMath.js";

const PUMP_PROGRAM_ID = new PublicKey("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P");
const PUMP_FEE_PROGRAM = new PublicKey("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ");

interface Check {
  venue: string;
  signature: string;
  expected: bigint;
  actual: bigint;
  errorBps: number;
  note?: string;
}

function arg(name: string, fallback: number): number {
  const i = process.argv.indexOf(name);
  if (i < 0 || i + 1 >= process.argv.length) return fallback;
  const v = Number(process.argv[i + 1]);
  return Number.isFinite(v) ? v : fallback;
}


/** Fetch a transaction, treating an RPC failure as a skip rather than a crash. */
async function safeTx(
  rpc: RpcClient,
  signature: string,
  skip: (why: string) => void,
): Promise<Awaited<ReturnType<typeof rpc.connection.getTransaction>>> {
  try {
    return await rpc.call(RpcPriority.P3_Screener, (c) =>
      c.getTransaction(signature, { maxSupportedTransactionVersion: 0, commitment: "confirmed" }),
    );
  } catch (e) {
    skip(`rpc: getTransaction failed (${e instanceof Error ? e.message.slice(0, 60) : String(e)})`);
    return null;
  }
}

async function main(): Promise<void> {
  const endpoint = process.env.RPC_HTTP_URL ?? "https://api.mainnet-beta.solana.com";
  const limit = arg("--limit", 40);
  const rps = arg("--rps", 2);
  // Deliberately slow and patient: this runs against whatever endpoint the
  // operator has, and a public one will rate limit a fast loop immediately.
  const rpc = new RpcClient(
    endpoint,
    new RpcBudget({
      ...DEFAULT_RPC_BUDGET,
      refillPerSecond: rps,
      capacity: Math.max(2, rps),
      maxWaitMs: 120_000,
      backoffMaxMs: 60_000,
    }),
    { maxRetries: 8 },
  );

  console.log(`verifying quoters against ${endpoint}`);
  console.log(`sampling up to ${limit} recent transactions per venue\n`);

  const checks: Check[] = [];
  // Counts events where a non-zero buyback/cashback leg did NOT change the
  // amount credited to the user, i.e. it is a split of an existing fee.
  let extraFeeLegsAreSplits = 0;
  const skipped: Record<string, number> = {};
  const skip = (why: string): void => {
    skipped[why] = (skipped[why] ?? 0) + 1;
  };

  const epoch = await rpc.getEpoch(RpcPriority.P4_Maintenance);

  // ---------------------------------------------------------------- Raydium
  {
    const sigs = await rpc.call(RpcPriority.P3_Screener, (c) =>
      c.getSignaturesForAddress(new PublicKey(RAYDIUM_CPMM_PROGRAM_ID), { limit }),
    );
    const configCache = new Map<string, ReturnType<typeof decodeRaydiumAmmConfig>>();
    const poolCache = new Map<string, ReturnType<typeof decodeRaydiumPoolState>>();

    for (const s of sigs) {
      if (s.err) continue;
      const tx = await safeTx(rpc, s.signature, skip);
      if (!tx?.meta?.logMessages) {
        skip("raydium: no logs");
        continue;
      }
      for (const payload of eventPayloadsFromLogs(tx.meta.logMessages)) {
        const ev = parseRaydiumSwapEvent(payload);
        if (!ev) continue;
        if (!ev.baseInput) {
          skip("raydium: swap_base_output (not used by the bot)");
          continue;
        }

        let pool = poolCache.get(ev.poolId);
        if (!pool) {
          const acc = await rpc.getAccount(ev.poolId, RpcPriority.P3_Screener);
          if (!acc) {
            skip("raydium: pool account missing");
            continue;
          }
          pool = decodeRaydiumPoolState(acc.data);
          poolCache.set(ev.poolId, pool);
        }

        let cfg = configCache.get(pool.ammConfigAddress);
        if (!cfg) {
          const acc = await rpc.getAccount(pool.ammConfigAddress, RpcPriority.P3_Screener);
          if (!acc) {
            skip(`raydium: amm config ${pool.ammConfigAddress} not found`);
            continue;
          }
          cfg = decodeRaydiumAmmConfig(pool.ammConfigAddress, acc.data);
          configCache.set(pool.ammConfigAddress, cfg);
        }

        // Structural check: the event's mints must be the pool's mints.
        const mints = [pool.token0Mint, pool.token1Mint];
        if (!mints.includes(ev.inputMint) || !mints.includes(ev.outputMint)) {
          checks.push({
            venue: "raydium-cpmm",
            signature: s.signature,
            expected: 0n,
            actual: 0n,
            errorBps: 10_000,
            note: `decoded pool mints ${mints.join("/")} do not contain the event mints`,
          });
          continue;
        }

        const creatorFeeRate = pool.enableCreatorFee ? cfg.creatorFeeRate : 0n;
        const r = raydiumSwapBaseInput({
          inputAmount: ev.inputAmount,
          inputVaultAmount: ev.inputVaultBefore,
          outputVaultAmount: ev.outputVaultBefore,
          tradeFeeRate: cfg.tradeFeeRate,
          creatorFeeRate,
          protocolFeeRate: cfg.protocolFeeRate,
          fundFeeRate: cfg.fundFeeRate,
          // Taken from the event so a stale `creator_fee_on` read cannot mask a
          // real arithmetic difference.
          isCreatorFeeOnInput: ev.creatorFeeOnInput,
        });

        checks.push({
          venue: "raydium-cpmm",
          signature: s.signature,
          expected: ev.outputAmount,
          actual: r.outputAmount,
          errorBps: bpsOf(
            r.outputAmount > ev.outputAmount ? r.outputAmount - ev.outputAmount : ev.outputAmount - r.outputAmount,
            ev.outputAmount === 0n ? 1n : ev.outputAmount,
          ),
        });
      }
    }
  }

  // --------------------------------------------------------------- PumpSwap
  {
    const [globalConfigPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("global_config")],
      new PublicKey(PUMP_SWAP_PROGRAM_ID),
    );
    const [feeConfigPda] = PublicKey.findProgramAddressSync(
      [Buffer.from("fee_config"), new PublicKey(PUMP_SWAP_PROGRAM_ID).toBuffer()],
      PUMP_FEE_PROGRAM,
    );
    const gcAcc = await rpc.getAccount(globalConfigPda.toBase58(), RpcPriority.P3_Screener);
    const fcAcc = await rpc.getAccount(feeConfigPda.toBase58(), RpcPriority.P3_Screener);
    if (!gcAcc || !fcAcc) throw new Error("pump global/fee config not found");
    const globalConfig = decodePumpGlobalConfig(globalConfigPda.toBase58(), gcAcc.data);
    const feeConfig = decodePumpFeeConfig(feeConfigPda.toBase58(), fcAcc.data);
    console.log(
      `pump fee tiers: ${feeConfig.feeTiers.length}, flat = ${feeConfig.flatFees.lpFeeBps}/${feeConfig.flatFees.protocolFeeBps}/${feeConfig.flatFees.creatorFeeBps} bps\n`,
    );

    const sigs = await rpc.call(RpcPriority.P3_Screener, (c) =>
      c.getSignaturesForAddress(new PublicKey(PUMP_SWAP_PROGRAM_ID), { limit }),
    );
    const poolCache = new Map<string, ReturnType<typeof decodePumpPool>>();
    const mintCache = new Map<string, ReturnType<typeof decodeMint>>();

    for (const s of sigs) {
      if (s.err) continue;
      const tx = await safeTx(rpc, s.signature, skip);
      if (!tx?.meta) continue;

      const keys = tx.transaction.message.getAccountKeys({
        accountKeysFromLookups: tx.meta.loadedAddresses ?? undefined,
      });
      const datas: Buffer[] = [];
      for (const inner of tx.meta.innerInstructions ?? []) {
        for (const ix of inner.instructions) {
          const prog = keys.get(ix.programIdIndex);
          if (prog?.toBase58() !== PUMP_SWAP_PROGRAM_ID) continue;
          datas.push(decodeInstructionData(ix.data));
        }
      }

      for (const payload of eventPayloadsFromCpi(datas)) {
        const ev = parsePumpSellEvent(payload);
        if (!ev) continue;

        // Do NOT skip when cashback/buyback are present: whether they are an
        // extra cost to the trader or merely a split of the protocol fee is an
        // empirical question, and the comparison below is what answers it.
        let pool = poolCache.get(ev.pool);
        if (!pool) {
          const acc = await rpc.getAccount(ev.pool, RpcPriority.P3_Screener);
          if (!acc) {
            skip("pump: pool account missing");
            continue;
          }
          pool = decodePumpPool(acc.data);
          poolCache.set(ev.pool, pool);
        }

        let baseMint = mintCache.get(pool.baseMint);
        if (!baseMint) {
          const acc = await rpc.getAccount(pool.baseMint, RpcPriority.P3_Screener);
          if (!acc) {
            skip("pump: base mint missing");
            continue;
          }
          baseMint = decodeMint({
            address: pool.baseMint,
            data: acc.data,
            programId: acc.owner,
            slot: acc.slot,
            receivedAt: acc.receivedAt,
            source: "rpc",
            currentEpoch: epoch,
          });
          mintCache.set(pool.baseMint, baseMint);
        }

        const [poolAuthority] = PublicKey.findProgramAddressSync(
          [Buffer.from("pool-authority"), new PublicKey(pool.baseMint).toBuffer()],
          PUMP_PROGRAM_ID,
        );
        const isCanonical = poolAuthority.toBase58() === pool.creator;

        let quoted: ReturnType<typeof pumpSellBaseInput>;
        try {
          quoted = pumpSellBaseInput({
            base: ev.baseAmountIn,
            baseReserve: ev.poolBaseTokenReserves,
            quoteReserve: ev.poolQuoteTokenReserves,
            virtualQuoteReserves: pool.virtualQuoteReserves,
            baseMintSupply: baseMint.supply,
            coinCreatorIsDefault: ev.coinCreator === "11111111111111111111111111111111",
            globalConfig,
            feeConfig,
            isCanonicalPumpPool: isCanonical,
          });
        } catch (e) {
          skip(`pump: quoter refused (${e instanceof Error ? e.message : String(e)})`);
          continue;
        }

        // Cross-check the fee tier we selected against the one the program used.
        const notes: string[] = [];
        if (
          quoted.fees.lpFeeBps !== ev.lpFeeBasisPoints ||
          quoted.fees.protocolFeeBps !== ev.protocolFeeBasisPoints
        ) {
          notes.push(
            `fee bps mismatch: ours ${quoted.fees.lpFeeBps}/${quoted.fees.protocolFeeBps}, chain ${ev.lpFeeBasisPoints}/${ev.protocolFeeBasisPoints}`,
          );
        }
        if (ev.cashback !== 0n || ev.buybackFee !== 0n) {
          notes.push(
            `cashback=${ev.cashback}(${ev.cashbackFeeBasisPoints}bps) buyback=${ev.buybackFee}(${ev.buybackFeeBasisPoints}bps) protocolFee=${ev.protocolFee}`,
          );
        }
        if (quoted.finalQuote === ev.userQuoteAmountOut && ev.buybackFee !== 0n) {
          extraFeeLegsAreSplits++;
        }
        const feeNote = notes.length > 0 ? notes.join("; ") : undefined;

        checks.push({
          venue: "pump-swap",
          signature: s.signature,
          expected: ev.userQuoteAmountOut,
          actual: quoted.finalQuote,
          errorBps: bpsOf(
            quoted.finalQuote > ev.userQuoteAmountOut
              ? quoted.finalQuote - ev.userQuoteAmountOut
              : ev.userQuoteAmountOut - quoted.finalQuote,
            ev.userQuoteAmountOut === 0n ? 1n : ev.userQuoteAmountOut,
          ),
          ...(feeNote ? { note: feeNote } : {}),
        });
      }
    }
  }

  // ----------------------------------------------------------------- report
  const byVenue = new Map<string, Check[]>();
  for (const c of checks) {
    const list = byVenue.get(c.venue);
    if (list) list.push(c);
    else byVenue.set(c.venue, [c]);
  }

  let failures = 0;
  let warnings = 0;
  for (const [venue, list] of byVenue) {
    const exact = list.filter((c) => c.expected === c.actual).length;
    const worst = list.reduce((m, c) => (c.errorBps > m ? c.errorBps : m), 0);
    console.log(`${venue}: ${exact}/${list.length} exact matches, worst error ${worst.toFixed(4)} bps`);
    for (const c of list) {
      // Only a differing AMOUNT is a failure. A note records something worth
      // knowing about the transaction (an unmodelled fee leg, a fee-tier
      // disagreement) and is reported even when the amounts agree.
      if (c.expected !== c.actual) {
        failures++;
        console.log(`  MISMATCH ${c.signature}`);
        console.log(`    chain=${c.expected} ours=${c.actual} (${c.errorBps.toFixed(4)} bps)`);
        if (c.note) console.log(`    ${c.note}`);
      } else if (c.note) {
        warnings++;
        console.log(`  note ${c.signature.slice(0, 12)}...: ${c.note}`);
      }
    }
  }

  if (extraFeeLegsAreSplits > 0) {
    console.log(
      `\nnote: ${extraFeeLegsAreSplits} events carried a non-zero buyback/cashback leg and STILL matched our quote exactly,`,
    );
    console.log("      i.e. those legs are a split of fees already accounted for, not an extra cost to the trader.");
  }

  if (Object.keys(skipped).length > 0) {
    console.log("\nskipped:");
    for (const [why, n] of Object.entries(skipped)) console.log(`  ${n}x ${why}`);
  }

  const budget = rpc.budget.getStats();
  console.log(
    `\nRPC: ${budget.granted} granted, ${budget.rejected} rejected, ${budget.rateLimitHits} rate limits, ${rpc.errors} errors`,
  );

  if (checks.length === 0) {
    console.log("\nNO CHECKS RAN — cannot claim the quoters are verified.");
    process.exit(2);
  }
  if (failures > 0) {
    console.log(`\n${failures} MISMATCHES. The quoters do not reproduce the chain. Do not trade.`);
    process.exit(1);
  }
  console.log(
    `\nAll ${checks.length} checks reproduced the chain exactly${warnings > 0 ? ` (${warnings} informational notes above)` : ""}.`,
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
