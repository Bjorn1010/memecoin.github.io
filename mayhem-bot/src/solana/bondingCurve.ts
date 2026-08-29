import { PublicKey } from "@solana/web3.js";
import { connection } from "./connection.js";
import { rpcQueue } from "./rpcQueue.js";
import { PUMPFUN_PROGRAM_ID, SOL_DECIMALS, TOKEN_DECIMALS } from "./constants.js";

export interface BondingCurveState {
  virtualTokenReserves: bigint;
  virtualSolReserves: bigint;
  realTokenReserves: bigint;
  realSolReserves: bigint;
  tokenTotalSupply: bigint;
  complete: boolean;
  priceSol: number;
}

function deriveBondingCurvePda(mint: PublicKey): PublicKey {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("bonding-curve"), mint.toBuffer()],
    PUMPFUN_PROGRAM_ID,
  );
  return pda;
}

/**
 * Reads the bonding curve account directly from chain and derives the current
 * spot price in SOL per whole token. Returns null once a coin has migrated off
 * the curve (account closed/emptied) — callers should fall back to DexScreener.
 */
export async function getBondingCurvePrice(mintAddress: string): Promise<BondingCurveState | null> {
  try {
    const mint = new PublicKey(mintAddress);
    const pda = deriveBondingCurvePda(mint);
    const info = await rpcQueue.run(() => connection.getAccountInfo(pda, "processed"));
    if (!info || info.data.length < 8 + 8 * 5) return null;

    const data = info.data;
    // 8-byte anchor discriminator, then 5 little-endian u64 fields, then a bool.
    let offset = 8;
    const virtualTokenReserves = data.readBigUInt64LE(offset);
    offset += 8;
    const virtualSolReserves = data.readBigUInt64LE(offset);
    offset += 8;
    const realTokenReserves = data.readBigUInt64LE(offset);
    offset += 8;
    const realSolReserves = data.readBigUInt64LE(offset);
    offset += 8;
    const tokenTotalSupply = data.readBigUInt64LE(offset);
    offset += 8;
    const complete = data.length > offset ? data.readUInt8(offset) === 1 : false;

    if (virtualTokenReserves === 0n) return null;

    const solReservesUi = Number(virtualSolReserves) / 10 ** SOL_DECIMALS;
    const tokenReservesUi = Number(virtualTokenReserves) / 10 ** TOKEN_DECIMALS;
    const priceSol = solReservesUi / tokenReservesUi;

    return {
      virtualTokenReserves,
      virtualSolReserves,
      realTokenReserves,
      realSolReserves,
      tokenTotalSupply,
      complete,
      priceSol,
    };
  } catch {
    return null;
  }
}
