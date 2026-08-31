/**
 * Replay mode.
 *
 *   npm run replay -- --state data/<run>/state.jsonl [--speed 10] [--limit 0]
 *
 * Feeds captured account state back through the identical decision pipeline.
 * Nothing is sent: the engine is constructed with no sender and no wallet, and
 * the feed has no network connection at all.
 *
 * Use it to answer "what would a different MIN_PROFIT / sizing grid / staleness
 * bound have done?" against recorded history. Change the environment variables,
 * re-run against the same capture, compare the two reports.
 */
import "dotenv/config";
import { loadConfig, describeConfig } from "../config/schema.js";
import { RpcBudget } from "../rpc/RpcBudget.js";
import { RpcClient } from "../rpc/RpcClient.js";
import { ReplayFeed } from "../feed/replay/ReplayFeed.js";
import { Ledger, makeRunId } from "../obs/ledger.js";
import { Metrics } from "../obs/metrics.js";
import { KillSwitch } from "../risk/killSwitch.js";
import { ArbEngine } from "../engine.js";
import { renderRunSummary } from "../obs/reports.js";

function flag(name: string, fallback: string): string {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1]! : fallback;
}

async function main(): Promise<void> {
  const statePath = flag("--state", "");
  if (!statePath) {
    console.error("usage: npm run replay -- --state data/<run>/state.jsonl");
    process.exit(2);
  }

  const config = loadConfig("replay");
  console.log(`[config] ${JSON.stringify(describeConfig(config), null, 2)}`);

  const ledger = new Ledger(config.dataDir, `replay-${makeRunId()}`);
  const metrics = new Metrics();
  const budget = new RpcBudget({
    refillPerSecond: config.rpcRequestsPerSecond,
    capacity: config.rpcBurstCapacity,
    backoffInitialMs: 500,
    backoffMaxMs: 30_000,
    maxWaitMs: 20_000,
  });
  // The RPC is still used for mint metadata and the fee probe; the market data
  // itself comes entirely from the capture.
  const rpc = new RpcClient(config.rpcHttpUrl, budget, { commitment: config.commitment });
  const feed = new ReplayFeed({
    path: statePath,
    speed: Number(flag("--speed", "10")),
    limit: Number(flag("--limit", "0")),
  });

  const engine = new ArbEngine({
    config,
    rpc,
    feed,
    ledger,
    metrics,
    killSwitch: new KillSwitch(),
    sender: null,
    wallet: null,
  });

  await engine.start();
  await feed.waitForCompletion();
  await engine.stop();
  console.log(renderRunSummary(metrics, budget.getStats(), ledger.paths));
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
