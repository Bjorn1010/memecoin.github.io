import { getBondingCurvePrice } from "./bondingCurve.js";
import { getDexscreenerPrice } from "./dexscreener.js";
import { SOL_DECIMALS, TOKEN_DECIMALS } from "./constants.js";

export interface PriceQuote {
  priceSol: number;
  /** Only present pre-migration, when we can read the curve's real reserves for slippage math. */
  solReservesUi?: number;
  tokenReservesUi?: number;
}

/** Best-effort current price + pool depth, bonding curve first, DEX second. */
export async function getCurrentQuote(mint: string): Promise<PriceQuote | null> {
  const curve = await getBondingCurvePrice(mint);
  if (curve && !curve.complete) {
    return {
      priceSol: curve.priceSol,
      solReservesUi: Number(curve.virtualSolReserves) / 10 ** SOL_DECIMALS,
      tokenReservesUi: Number(curve.virtualTokenReserves) / 10 ** TOKEN_DECIMALS,
    };
  }

  const dex = await getDexscreenerPrice(mint);
  if (dex) return { priceSol: dex }; // migrated — deeper liquidity, no reserves to model slippage from

  return curve ? { priceSol: curve.priceSol } : null;
}

export async function getCurrentPriceSol(mint: string): Promise<number | null> {
  const quote = await getCurrentQuote(mint);
  return quote?.priceSol ?? null;
}
