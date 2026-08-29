import { config } from "./config.js";
import { EngineManager } from "./engine/engineManager.js";
import { createApiServer } from "./api/server.js";

async function main() {
  console.log("[mayhem-bot] starting — paper trading only, no real funds at risk");
  console.log("[mayhem-bot] tracking wallets:", config.mayhemWallets.join(", "));

  const engine = new EngineManager(config.mayhemWallets);

  engine.on("monitor_status", (s) => {
    console.log(`[monitor] ${s.wallet.slice(0, 6)}… -> ${s.state}${s.detail ? ` (${s.detail})` : ""}`);
  });
  engine.on("mayhem_event", (e) => {
    console.log(
      `[mayhem] ${e.kind.toUpperCase()} ${e.mint.slice(0, 6)}… ${e.tokenAmount.toFixed(2)} tok @ ${e.priceSol.toFixed(10)} SOL`,
    );
  });
  engine.on("trade", (t) => {
    console.log(
      `[paper:${t.strategyId}] ${t.side.toUpperCase()} ${t.mint.slice(0, 6)}… reason=${t.reason} price=${t.priceSol.toFixed(10)} sol=${t.solAmount.toFixed(4)}`,
    );
  });

  await engine.start();
  createApiServer(engine, config.port);

  process.on("SIGINT", () => {
    console.log("\n[mayhem-bot] shutting down");
    engine.stop();
    process.exit(0);
  });
}

main().catch((err) => {
  console.error("[mayhem-bot] fatal error", err);
  process.exit(1);
});
