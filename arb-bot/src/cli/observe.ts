/**
 * Observation mode.
 *
 *   npm run observe
 *
 * Watches, measures and records. No transaction is ever built for sending and
 * no wallet is loaded: `bootstrap("observe")` constructs the engine without a
 * sender at all, so there is no code path that could transmit.
 *
 * The output that matters is `data/<run>/observations.jsonl`, which records for
 * every opportunity whether it still existed 200ms, 500ms, 1s and 5s later.
 * That single measurement decides whether this strategy is viable from this
 * machine at all. Run `npm run report -- --observe <path>` to summarise it.
 */
import { bootstrap } from "./run.js";

async function main(): Promise<void> {
  const { ledger } = await bootstrap("observe");
  console.log("\nObserving. No capital is at risk; nothing will be sent.");
  console.log(`Raw state is being captured to ${ledger.paths.state} for --replay.`);
  console.log("Press Ctrl-C to stop and print the summary.\n");
  // The engine drives itself from feed events; hold the process open.
  await new Promise<void>(() => {});
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
