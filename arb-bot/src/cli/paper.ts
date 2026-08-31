/**
 * Paper mode.
 *
 *   npm run paper
 *
 * Runs the complete pipeline — feed, quoting, sizing, costs, risk, transaction
 * construction and on-chain simulation — and stops immediately before sending.
 * The transaction is built and simulated exactly as it would be in live mode,
 * so the compute-unit measurement, the quote-versus-simulation divergence and
 * the rejection reasons are all real numbers rather than projections.
 *
 * What this mode CANNOT tell you is the land rate: nothing is sent, so nothing
 * lands. Treat any expected PnL printed here as an upper bound that assumes
 * perfect inclusion.
 */
import { bootstrap } from "./run.js";

async function main(): Promise<void> {
  await bootstrap("paper");
  console.log("\nPaper trading. Transactions are built and simulated, never sent.");
  console.log("Expected PnL here assumes every transaction lands; it will not.\n");
  await new Promise<void>(() => {});
}

main().catch((e) => {
  console.error(e instanceof Error ? e.message : e);
  process.exit(1);
});
