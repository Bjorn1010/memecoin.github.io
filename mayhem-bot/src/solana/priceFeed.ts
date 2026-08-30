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

  // Deliberately NOT falling back to a completed curve's price: once a curve completes its
  // SOL side has been drained into the new AMM pool, so the price derived from it is
  // meaningless (typically near zero) rather than merely stale. Returning it here is what
  // let a draining-curve price be booked as a real entry and manufacture a fake ~180x win.
  // No price is strictly better than a fabricated one — callers already handle null.
  if (curve && !curve.complete) return { priceSol: curve.priceSol };
  return null;
}

export async function getCurrentPriceSol(mint: string): Promise<number | null> {
  const quote = await getCurrentQuote(mint);
  return quote?.priceSol ?? null;
}
