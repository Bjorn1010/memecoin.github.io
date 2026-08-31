import { TokenWatcher } from "./tokenWatcher.js";
import { AlxAgentRunner } from "./alxAgentRunner.js";
import { aiConfig } from "./aiConfig.js";

/**
 * Standalone entrypoint for the alxcooks-style AI reasoning agent — fully separate process
 * from the main mayhem-bot (npm run dev / src/index.ts). Run with:
 *
 *   npx tsx src/ai/runAlxAgent.ts
 *
 * Requires GROQ_API_KEY in the environment (or .env) to actually make decisions — free,
 * no card required, get one at console.groq.com/keys. Without it, the agent will watch
 * and log tokens but every decision call is skipped.
 * Also strongly recommends a paid RPC (RPC_HTTP_URL / RPC_WS_URL — reuses whatever the
 * main mayhem-bot is already configured with, same env vars, no separate setup needed)
 * — this watches the ENTIRE pump.fun program, a much heavier subscription than
 * mayhem-bot's fixed 2-wallet watch, and free public RPCs will struggle under it.
 */
async function main() {
  console.log("[alx-agent] starting — paper trading only, no real funds at risk");
  if (!aiConfig.groqApiKey) {
    console.log("[alx-agent] WARNING: GROQ_API_KEY not set — will watch but never decide.");
    console.log("[alx-agent] get a free key at https://console.groq.com/keys");
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
  const summaryInterval = setInterval(() => runner.logSummary(), 60_000);

  const shutdown = () => {
    console.log("\n[alx-agent] shutting down");
    runner.logSummary();
    clearInterval(hardStopInterval);
    clearInterval(summaryInterval);
    watcher.stop();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((err) => {
  console.error("[alx-agent] fatal error", err);
  process.exit(1);
});
