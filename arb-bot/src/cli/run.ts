/**
 * Shared bootstrap for the running modes.
 *
 * The safety gates live here, once, so that no mode can accidentally skip one:
 * a wallet is only ever loaded for `--live`, and `--live` refuses to start
 * unless every required limit is configured and the operator has given a second
 * explicit confirmation (§27).
 */
import "dotenv/config";
import { readFileSync } from "node:fs";
import { Keypair } from "@solana/web3.js";
import { loadConfig, describeConfig, type Config } from "../config/schema.js";
import { RpcBudget } from "../rpc/RpcBudget.js";
import { RpcClient } from "../rpc/RpcClient.js";
import { WsAccountFeed, DEFAULT_WS_CONFIG } from "../feed/websocket/WsAccountFeed.js";
import { Ledger, makeRunId } from "../obs/ledger.js";
import { Metrics } from "../obs/metrics.js";
import { KillSwitch, DEFAULT_KILL_SWITCH_THRESHOLDS } from "../risk/killSwitch.js";
import { JitoSender, RpcSender, type TxSender } from "../exec/TxSender.js";
import { ArbEngine } from "../engine.js";
import { renderRunSummary } from "../obs/reports.js";
import { existsSync, readFileSync as read, writeFileSync } from "node:fs";
import { join } from "node:path";

export interface RunHandles {
  config: Config;
  engine: ArbEngine;
  metrics: Metrics;
  ledger: Ledger;
}

/**
 * Load a keypair from a Solana CLI style JSON array file.
 *
 * The key is read, used to construct the Keypair, and never logged, never
 * written to the ledger and never included in an error message. The only thing
 * that leaves this function is the public key.
 */
function loadWallet(path: string): Keypair {
  let raw: string;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    throw new Error(`cannot read the wallet keypair at ${path}`);
  }
  let bytes: number[];
  try {
    bytes = JSON.parse(raw) as number[];
  } catch {
    throw new Error("wallet keypair file is not a JSON array of bytes");
  }
  if (!Array.isArray(bytes) || (bytes.length !== 64 && bytes.length !== 32)) {
    throw new Error("wallet keypair file does not contain a 32 or 64 byte key");
  }
  return bytes.length === 64
    ? Keypair.fromSecretKey(Uint8Array.from(bytes))
    : Keypair.fromSeed(Uint8Array.from(bytes));
}

export async function bootstrap(mode: Config["mode"]): Promise<RunHandles> {
  const config = loadConfig(mode);
  console.log(`[config] ${JSON.stringify(describeConfig(config), null, 2)}`);

  const runId = makeRunId();
  const ledger = new Ledger(config.dataDir, runId);
  const metrics = new Metrics();

  const budget = new RpcBudget({
    refillPerSecond: config.rpcRequestsPerSecond,
    capacity: config.rpcBurstCapacity,
    backoffInitialMs: 500,
    backoffMaxMs: 30_000,
    maxWaitMs: 20_000,
  });
  const rpc = new RpcClient(config.rpcHttpUrl, budget, { commitment: config.commitment });

  const feed = new WsAccountFeed({
    ...DEFAULT_WS_CONFIG,
    endpoint: config.rpcWsUrl,
    commitment: config.commitment,
    maxSubscriptions: config.maxSubscriptions,
  });

  // The kill switch persists across restarts: a tripped bot stays tripped until
  // a human clears it, which is the entire point of having one.
  const killSwitchPath = join(config.dataDir, "kill-switch.json");
  const killSwitch = new KillSwitch(DEFAULT_KILL_SWITCH_THRESHOLDS, {
    load: () => {
      if (!existsSync(killSwitchPath)) return null;
      try {
        return JSON.parse(read(killSwitchPath, "utf8"));
      } catch {
        return null;
      }
    },
    save: (state) => writeFileSync(killSwitchPath, JSON.stringify(state, null, 2), "utf8"),
  });

  if (killSwitch.tripped && mode === "live") {
    const s = killSwitch.snapshot();
    throw new Error(
      `kill switch is tripped (${s.trigger}: ${s.detail}). Clear ${killSwitchPath} deliberately, after understanding why it tripped, to resume.`,
    );
  }

  let sender: TxSender | null = null;
  let wallet: Keypair | null = null;

  if (mode === "live") {
    if (!config.walletKeypairPath) throw new Error("WALLET_KEYPAIR_PATH is required for --live");
    wallet = loadWallet(config.walletKeypairPath);
    console.log(`[wallet] ${wallet.publicKey.toBase58()}`);
    sender = config.useJito
      ? new JitoSender({ blockEngineUrl: config.jitoBlockEngineUrl! })
      : new RpcSender(rpc);
  } else if (mode === "paper") {
    // Paper mode needs a sender only for its cost characteristics, never to
    // send: the engine has no code path that transmits outside live mode.
    sender = config.useJito
      ? new JitoSender({ blockEngineUrl: config.jitoBlockEngineUrl! })
      : new RpcSender(rpc);
  }

  const engine = new ArbEngine({ config, rpc, feed, ledger, metrics, killSwitch, sender, wallet });

  const shutdown = async (signal: string): Promise<void> => {
    console.log(`\n[${signal}] shutting down`);
    await engine.stop();
    console.log(renderRunSummary(metrics, budget.getStats(), ledger.paths));
    process.exit(0);
  };
  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  await engine.start();
  console.log(`[run] mode=${mode} runId=${runId} ledger=${ledger.paths.attempts}`);

  const summaryTimer = setInterval(() => {
    console.log(renderRunSummary(metrics, budget.getStats(), ledger.paths));
  }, 60_000);
  summaryTimer.unref?.();

  return { config, engine, metrics, ledger };
}
