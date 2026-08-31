/**
 * One-time on-chain setup for live trading.
 *
 *   npm run setup
 *
 * Creates, idempotently:
 *   - the wallet's WSOL associated token account (the bot's base-asset account);
 *   - PumpSwap's per-wallet volume accumulator PDA, which its `buy` requires;
 *   - an address lookup table holding the accounts every cycle touches.
 *
 * The lookup table is not a nicety. A PumpSwap+Raydium cycle serialises to
 * 1281 bytes against Solana's 1232-byte limit, so without a table those cycles
 * cannot be built at all and the bot is restricted to same-venue arbitrage.
 *
 * This command SPENDS a small amount of SOL (rent for the token account and the
 * table, plus fees). It refuses to run without an explicitly configured wallet.
 */
import "dotenv/config";
import { readFileSync } from "node:fs";
import {
  Keypair,
  MessageV0,
  PublicKey,
  VersionedTransaction,
} from "@solana/web3.js";
import { loadConfig, WSOL_MINT } from "../config/schema.js";
import { RpcBudget, RpcPriority } from "../rpc/RpcBudget.js";
import { RpcClient } from "../rpc/RpcClient.js";
import { createAtaIdempotentIx, pumpInitUserVolumeAccumulatorIx } from "../exec/instructions.js";
import {
  createLookupTableInstructions,
  extendLookupTableInstructions,
  loadLookupTable,
  missingFromTable,
  staticLookupAddresses,
} from "../exec/lookupTable.js";
import { associatedTokenAddress, pumpUserVolumeAccumulator } from "../screener/pdas.js";
import { TOKEN_PROGRAM_ID } from "../feed/decoder/token2022.js";

function loadWallet(path: string): Keypair {
  const bytes = JSON.parse(readFileSync(path, "utf8")) as number[];
  if (!Array.isArray(bytes) || (bytes.length !== 64 && bytes.length !== 32)) {
    throw new Error("wallet keypair file does not contain a 32 or 64 byte key");
  }
  return bytes.length === 64
    ? Keypair.fromSecretKey(Uint8Array.from(bytes))
    : Keypair.fromSeed(Uint8Array.from(bytes));
}

async function send(
  rpc: RpcClient,
  wallet: Keypair,
  instructions: Parameters<typeof MessageV0.compile>[0]["instructions"],
  label: string,
): Promise<void> {
  const { blockhash, lastValidBlockHeight } = await rpc.getLatestBlockhash();
  const tx = new VersionedTransaction(
    MessageV0.compile({ payerKey: wallet.publicKey, instructions, recentBlockhash: blockhash }),
  );
  tx.sign([wallet]);
  const signature = await rpc.call(RpcPriority.P0_Critical, (c) =>
    c.sendRawTransaction(tx.serialize(), { maxRetries: 3 }),
  );
  await rpc.call(RpcPriority.P0_Critical, (c) =>
    c.confirmTransaction({ signature, blockhash, lastValidBlockHeight }, "confirmed"),
  );
  console.log(`  ${label}: ${signature}`);
}

async function main(): Promise<void> {
  // Setup borrows the live schema for its wallet requirement but does not need
  // the live confirmation gates, so it loads as paper and checks the one field
  // it actually needs.
  const config = loadConfig("paper");
  if (!config.walletKeypairPath) {
    console.error("WALLET_KEYPAIR_PATH must be set: setup signs and pays for on-chain accounts.");
    process.exit(2);
  }
  const wallet = loadWallet(config.walletKeypairPath);
  const rpc = new RpcClient(config.rpcHttpUrl, new RpcBudget(), { commitment: config.commitment });

  console.log(`wallet: ${wallet.publicKey.toBase58()}`);
  const balance = await rpc.call(RpcPriority.P0_Critical, (c) => c.getBalance(wallet.publicKey));
  console.log(`balance: ${balance} lamports`);
  if (balance < 20_000_000) {
    console.error("Fund the wallet with at least ~0.02 SOL before running setup.");
    process.exit(2);
  }

  // --- 1. WSOL token account ------------------------------------------------
  const wsolAta = associatedTokenAddress(
    WSOL_MINT,
    wallet.publicKey,
    new PublicKey(TOKEN_PROGRAM_ID),
  );
  const wsolInfo = await rpc.getAccount(wsolAta.toBase58(), RpcPriority.P0_Critical);
  if (wsolInfo) {
    console.log(`WSOL account already exists: ${wsolAta.toBase58()}`);
  } else {
    console.log(`creating WSOL account ${wsolAta.toBase58()}`);
    await send(
      rpc,
      wallet,
      [
        createAtaIdempotentIx({
          payer: wallet.publicKey,
          owner: wallet.publicKey,
          mint: new PublicKey(WSOL_MINT),
          tokenProgram: new PublicKey(TOKEN_PROGRAM_ID),
        }),
      ],
      "wsol ata",
    );
  }

  // --- 2. PumpSwap user volume accumulator ---------------------------------
  const uva = pumpUserVolumeAccumulator(wallet.publicKey);
  const uvaInfo = await rpc.getAccount(uva.toBase58(), RpcPriority.P0_Critical);
  if (uvaInfo) {
    console.log(`pump volume accumulator already exists: ${uva.toBase58()}`);
  } else {
    console.log(`creating pump volume accumulator ${uva.toBase58()}`);
    try {
      await send(
        rpc,
        wallet,
        [pumpInitUserVolumeAccumulatorIx(wallet.publicKey, wallet.publicKey)],
        "volume accumulator",
      );
    } catch (e) {
      // Without it, PumpSwap `buy` will fail — so this is reported loudly
      // rather than swallowed, but it does not block the rest of setup.
      console.error(
        `  FAILED: ${e instanceof Error ? e.message : e}\n` +
          "  PumpSwap buy legs will not work until this account exists.",
      );
    }
  }

  // --- 3. address lookup table ---------------------------------------------
  const wanted = staticLookupAddresses(wallet.publicKey);
  if (config.lookupTableAddress) {
    const existing = await loadLookupTable(rpc.connection, config.lookupTableAddress);
    if (!existing) {
      console.error(`LOOKUP_TABLE_ADDRESS ${config.lookupTableAddress} holds no table.`);
      process.exit(2);
    }
    const missing = missingFromTable(existing, wanted);
    if (missing.length === 0) {
      console.log(`lookup table ${config.lookupTableAddress} already has every static address`);
    } else {
      console.log(`extending lookup table with ${missing.length} addresses`);
      await send(
        rpc,
        wallet,
        extendLookupTableInstructions({
          authority: wallet.publicKey,
          payer: wallet.publicKey,
          lookupTable: new PublicKey(config.lookupTableAddress),
          addresses: missing,
        }),
        "extend table",
      );
    }
  } else {
    const recentSlot = await rpc.getSlot(RpcPriority.P0_Critical);
    // The table address is derived from a recent slot; use one comfortably in
    // the past so the program still considers it valid when it lands.
    const { instructions, lookupTableAddress } = createLookupTableInstructions({
      authority: wallet.publicKey,
      payer: wallet.publicKey,
      recentSlot: recentSlot - 1,
      addresses: wanted,
    });
    console.log(`creating lookup table ${lookupTableAddress.toBase58()}`);
    // Create first, then extend: extension of a table created in the same
    // transaction is rejected until the table is initialised.
    await send(rpc, wallet, [instructions[0]!], "create table");
    if (instructions.length > 1) {
      await send(rpc, wallet, instructions.slice(1), "fill table");
    }
    console.log("");
    console.log("Add this to your .env:");
    console.log(`  LOOKUP_TABLE_ADDRESS=${lookupTableAddress.toBase58()}`);
    console.log(`  WALLET_PUBLIC_KEY=${wallet.publicKey.toBase58()}`);
  }

  console.log("\nSetup complete. A lookup table needs one slot to activate before use.");
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
