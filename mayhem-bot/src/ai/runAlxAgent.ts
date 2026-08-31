import { TokenWatcher } from "./tokenWatcher.js";
import { AlxAgentRunner } from "./alxAgentRunner.js";
import { aiConfig } from "./aiConfig.js";

/**
 * Standalone entrypoint for the alxcooks-style AI reasoning agent — fully separate process
 * from the main mayhem-bot (npm run dev / src/index.ts). Run with:
 *
 *   npx tsx src/ai/runAlxAgent.ts
 *
 * Requires ANTHROPIC_API_KEY in the environment (or .env) to actually make decisions —
 * without it, the agent will watch and log tokens but every decision call is skipped.
 * Also strongly recommends a paid RPC (RPC_HTTP_URL / RPC_WS_URL, same vars as the rest of
 * the project) — this watches the ENTIRE pump.fun program, a much heavier subscription
 * than mayhem-bot's fixed 2-wallet watch, and free public RPCs will struggle under it.
 */
async function main() {
  console.log("[alx-agent] starting — paper trading only, no real funds at risk");
  if (!aiConfig.anthropicApiKey) {
    console.log("[alx-agent] WARNING: ANTHROPIC_API_KEY not set — will watch but never decide.");
  }
  console.log(
    `[alx-agent] tracked wallets: ${aiConfig.trackedWallets.map((w) => `${w.label} (${w.address.slice(0, 6)}…)`).join(", ")}`,
  );

  const watcher = new TokenWatcher();
  const runner = new AlxAgentRunner();

  watcher.on("status", (s) => console.log(`[alx-agent] watcher status: ${s.state}${s.detail ? ` (${s.detail})` : ""}`));
  watcher.on("update", (u) => void runner.handleUpdate(u));

  await watcher.start();
  const hardStopInterval = setInterval(() => runner.tickAllHardStops(), 5_000);

  process.on("SIGINT", () => {
    console.log("\n[alx-agent] shutting down");
    clearInterval(hardStopInterval);
    watcher.stop();
    process.exit(0);
  });
}

main().catch((err) => {
  console.error("[alx-agent] fatal error", err);
  process.exit(1);
});
