import { PublicKey } from "@solana/web3.js";
import { connection } from "../solana/connection.js";
import { deriveBondingCurvePda } from "../solana/bondingCurve.js";

/** Dumps a bonding curve account's raw fields, to check what our decoder is actually reading. */
async function main() {
  for (const m of process.argv.slice(2)) {
    const pda = deriveBondingCurvePda(new PublicKey(m));
    const info = await connection.getAccountInfo(pda, "processed");
    if (!info) {
      console.log(`${m.slice(0, 8)} : compte INEXISTANT (ferme)`);
      continue;
    }
    const d = info.data;
    const u64 = (o: number) => d.readBigUInt64LE(o);
    console.log(`${m.slice(0, 8)} len=${d.length}`);
    console.log(`   vTok=${u64(8)} vSol=${u64(16)} rTok=${u64(24)} rSol=${u64(32)} supply=${u64(40)}`);
    console.log(`   octet48=${d[48]} octets48..56=[${[...d.subarray(48, 56)].join(",")}]`);
  }
  process.exit(0);
}
void main();
