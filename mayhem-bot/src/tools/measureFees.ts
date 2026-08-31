import { connection } from "../solana/connection.js";
import { rpcQueue } from "../solana/rpcQueue.js";

/** Reads the real on-chain fee actually paid on a sample of Mayhem transactions, so the
 * simulation's priorityFeeSol stops being an unverified assumption. */
async function main() {
  const sigs = process.argv.slice(2);
  const fees: number[] = [];
  for (const sig of sigs) {
    try {
      const tx = await rpcQueue.run(() =>
        connection.getTransaction(sig, { maxSupportedTransactionVersion: 0, commitment: "confirmed" }),
      );
      if (tx?.meta?.fee != null) fees.push(tx.meta.fee / 1e9);
    } catch {
      /* signature trop ancienne pour le noeud, ignorer */
    }
  }
  if (fees.length === 0) {
    console.log("aucune transaction recuperee");
    process.exit(0);
  }
  fees.sort((a, b) => a - b);
  const p = (q: number) => fees[Math.floor(fees.length * q)];
  console.log(`n=${fees.length} frais reels (SOL/transaction)`);
  console.log(`  min=${fees[0].toFixed(6)}  p25=${p(0.25).toFixed(6)}  median=${p(0.5).toFixed(6)}`);
  console.log(`  p75=${p(0.75).toFixed(6)}  p90=${p(0.9).toFixed(6)}  max=${fees[fees.length - 1].toFixed(6)}`);
  console.log(`  moyenne=${(fees.reduce((a, b) => a + b, 0) / fees.length).toFixed(6)}`);
  console.log(`  hypothese actuelle du modele: 0.003000`);
  process.exit(0);
}
void main();
