import { Connection, PublicKey } from "@solana/web3.js";
const rpc = process.env.RPC_HTTP_URL ?? "https://api.mainnet-beta.solana.com";
const conn = new Connection(rpc, "confirmed");
const PUMP_AMM = new PublicKey("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA");
const PUMP_FEE = new PublicKey("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ");
const POOL_DISC = Buffer.from([241,154,109,4,17,177,109,188]);

const sigs = await conn.getSignaturesForAddress(PUMP_AMM, { limit: 12 });
console.log("recent sigs:", sigs.length);
const pools = new Set();
for (const s of sigs) {
  if (s.err) continue;
  const tx = await conn.getTransaction(s.signature, { maxSupportedTransactionVersion: 0, commitment: "confirmed" });
  if (!tx) continue;
  const keys = tx.transaction.message.getAccountKeys({ accountKeysFromLookups: tx.meta?.loadedAddresses });
  for (const ix of tx.transaction.message.compiledInstructions) {
    const prog = keys.get(ix.programIdIndex);
    if (!prog?.equals(PUMP_AMM)) continue;
    const disc = Buffer.from(ix.data).subarray(0, 8).toString("hex");
    // buy=66063d1201daebea, sell=33e685a4017f85ad, buy_exact_quote_in=c62e1552b4d9e870
    if (["66063d1201daebea", "33e685a4017f85ad", "c62e1552b4d9e870"].includes(disc)) {
      pools.add(keys.get(ix.accountKeyIndexes[0]).toBase58());
    }
  }
  if (pools.size >= 4) break;
}
console.log("pools found:", [...pools]);

const infos = await conn.getMultipleAccountsInfo([...pools].slice(0,4).map(p=>new PublicKey(p)));
infos.forEach((i, n) => {
  if (!i) return console.log("pool", n, "MISSING");
  console.log(`pool[${n}] owner=${i.owner.toBase58()} size=${i.data.length} discOK=${i.data.subarray(0,8).equals(POOL_DISC)}`);
});

// GlobalConfig + FeeConfig
const [globalConfig] = PublicKey.findProgramAddressSync([Buffer.from("global_config")], PUMP_AMM);
const [feeConfig] = PublicKey.findProgramAddressSync([Buffer.from("fee_config"), PUMP_AMM.toBuffer()], PUMP_FEE);
console.log("\nglobal_config PDA:", globalConfig.toBase58());
console.log("fee_config PDA:", feeConfig.toBase58());
const [gc, fc] = await conn.getMultipleAccountsInfo([globalConfig, feeConfig]);
console.log("global_config size:", gc?.data.length, "owner:", gc?.owner.toBase58());
console.log("fee_config size:", fc?.data.length, "owner:", fc?.owner.toBase58());
if (fc) console.log("fee_config b64:", fc.data.toString("base64"));
