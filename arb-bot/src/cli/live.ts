/**
 * Live mode.
 *
 *   npm run live
 *
 * Spends real SOL. Refuses to start unless, all at once:
 *   LIVE_TRADING=true
 *   LIVE_CONFIRMATION=I_UNDERSTAND_THIS_SPENDS_REAL_SOL
 *   WALLET_KEYPAIR_PATH points at a dedicated wallet
 *   MAX_TRADE_SIZE, MAX_DAILY_LOSS and MIN_PROFIT are all set
 *   the kill switch is not tripped
 *
 * Those checks live in config/schema.ts and cli/run.ts and are not skippable
 * from here. Read the "Before going live" checklist in the README first: the
 * gates are necessary, not sufficient.
 */
import { bootstrap } from "./run.js";

async function main(): Promise<void> {
  const { config } = await bootstrap("live");
  console.log("\n*** LIVE. This spends real SOL. ***");
  console.log(`max trade ${config.maxTradeSize} lamports, daily loss limit ${config.maxDailyLoss} lamports`);
  console.log("Ctrl-C stops the bot and prints the summary.\n");
  await new Promise<void>(() => {});
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
