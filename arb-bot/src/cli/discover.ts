/**
 * Pool discovery report.
 *
 *   npm run discover -- [--transactions 40] [--max-mints 15]
 *
 * Builds the token universe from recent on-chain activity, then finds every
 * WSOL pool we can quote exactly for each token, and prints which tokens have
 * the two or more pools a cycle needs.
 *
 * This is also the check that the memcmp offsets used for discovery are right:
 * every pool it returns is decoded and its mints verified against the mint we
 * searched for, so a wrong offset shows up as "0 pools" rather than as silence.
 */
import { RpcBudget, DEFAULT_RPC_BUDGET, RpcPriority } from "../rpc/RpcBudget.js";
import { RpcClient } from "../rpc/RpcClient.js";
import {
  discoverActiveMints,
  discoverPoolsForMints,
  fetchMint,
  mintsWithMultiplePools,
} from "../screener/discovery.js";
import { checkMint, DEFAULT_TOKEN_POLICY, summariseVerdict } from "../risk/tokenFilters.js";
import { WSOL_MINT } from "../config/schema.js";

function arg(name: string, fallback: number): number {
  const i = process.argv.indexOf(name);
  if (i < 0 || i + 1 >= process.argv.length) return fallback;
  const v = Number(process.argv[i + 1]);
  return Number.isFinite(v) ? v : fallback;
}

async function main(): Promise<void> {
  const endpoint = process.env.RPC_HTTP_URL ?? "https://api.mainnet-beta.solana.com";
  const transactions = arg("--transactions", 30);
  const maxMints = arg("--max-mints", 12);
  const rps = arg("--rps", 2);

  const rpc = new RpcClient(
    endpoint,
    new RpcBudget({
      ...DEFAULT_RPC_BUDGET,
      refillPerSecond: rps,
      capacity: Math.max(2, rps),
      maxWaitMs: 120_000,
      backoffMaxMs: 60_000,
    }),
    { maxRetries: 8 },
  );

  console.log(`discovering against ${endpoint}`);
  const epoch = await rpc.getEpoch(RpcPriority.P4_Maintenance);

  const active = await discoverActiveMints(rpc, { transactionsPerVenue: transactions });
  const ranked = [...active.entries()]
    .filter(([mint]) => mint !== WSOL_MINT)
    .sort((a, b) => b[1] - a[1])
    .slice(0, maxMints);
  console.log(`\n${active.size} distinct mints seen; probing the ${ranked.length} most active\n`);

  // One batched read for every candidate address of every mint: the whole
  // point of deriving addresses instead of scanning program accounts.
  const found = await discoverPoolsForMints(rpc, ranked.map(([m]) => m));
  const allPools = [];
  let probed = 0;
  for (const [mint, activity] of ranked) {
    const pools = found.get(mint) ?? [];
    probed++;
    allPools.push(...pools);

    const byFamily = pools.reduce<Record<string, number>>((acc, p) => {
      acc[p.family] = (acc[p.family] ?? 0) + 1;
      return acc;
    }, {});
    const families = Object.entries(byFamily)
      .map(([f, n]) => `${f}=${n}`)
      .join(" ");

    let risk = "";
    if (pools.length >= 2) {
      const m = await fetchMint(rpc, mint, epoch);
      risk = m ? ` risk=${summariseVerdict(checkMint(m, DEFAULT_TOKEN_POLICY))}` : " risk=mint-unreadable";
    }
    console.log(
      `  ${mint.slice(0, 8)}… activity=${activity} pools=${pools.length} ${families || "(none)"}${risk}`,
    );
  }

  const cycleable = mintsWithMultiplePools(allPools);
  console.log(`\n${probed} mints probed, ${cycleable.size} have two or more quotable WSOL pools:`);
  for (const [mint, pools] of cycleable) {
    console.log(`  ${mint}`);
    for (const p of pools) console.log(`    ${p.family.padEnd(13)} ${p.poolId}`);
  }

  const budget = rpc.budget.getStats();
  console.log(
    `\nRPC: ${budget.granted} granted, ${budget.rejected} rejected, ${budget.rateLimitHits} rate limits, ${rpc.errors} errors`,
  );

  if (allPools.length === 0) {
    console.log("\nNo pools found at all — the discovery filters are probably wrong.");
    process.exit(2);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
