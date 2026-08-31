// Fetch an Anchor IDL published on-chain for a given program id.
// Anchor stores it at createWithSeed(findProgramAddress([], programId)[0], "anchor:idl", programId).
import { Connection, PublicKey } from "@solana/web3.js";
import { inflate } from "node:zlib";
import { promisify } from "node:util";
import { writeFileSync } from "node:fs";

const inflateAsync = promisify(inflate);
const rpc = process.env.RPC_HTTP_URL ?? "https://api.mainnet-beta.solana.com";
const conn = new Connection(rpc, "confirmed");

const programId = new PublicKey(process.argv[2]);
const out = process.argv[3];

const [base] = PublicKey.findProgramAddressSync([], programId);
const idlAddr = await PublicKey.createWithSeed(base, "anchor:idl", programId);
console.log("program:", programId.toBase58());
console.log("idl account:", idlAddr.toBase58());

const info = await conn.getAccountInfo(idlAddr);
if (!info) {
  console.log("NO on-chain IDL account");
  process.exit(2);
}
// 8 disc + 32 authority + 4 len
const len = info.data.readUInt32LE(40);
const compressed = info.data.subarray(44, 44 + len);
const json = (await inflateAsync(compressed)).toString("utf8");
writeFileSync(out, json);
console.log("wrote", out, json.length, "bytes");
