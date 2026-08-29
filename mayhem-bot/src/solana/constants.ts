import { PublicKey } from "@solana/web3.js";

export const PUMPFUN_PROGRAM_ID = new PublicKey("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P");

export const SOL_DECIMALS = 9;
export const TOKEN_DECIMALS = 6; // standard for pump.fun-launched tokens

/** Padre/pump.fun platform trading fee — 1% of trade notional, taken on both buy and sell. */
export const PLATFORM_FEE_PCT = 0.01;
