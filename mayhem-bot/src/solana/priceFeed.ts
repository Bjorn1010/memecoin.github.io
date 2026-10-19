import { getBondingCurvePrice } from "./bondingCurve.js";
import { getDexscreenerQuote } from "./dexscreener.js";
import { SOL_DECIMALS, TOKEN_DECIMALS } from "./constants.js";

export interface PriceQuote {
  priceSol: number;
  /** Only present pre-migration, when we can read the curve's real reserves for slippage math. */
  solReservesUi?: number;
  tokenReservesUi?: number;
  /** Only present post-migration: depth of the DEX pool this price came from, in USD. */
  liquidityUsd?: number;
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

  const dex = await getDexscreenerQuote(mint);
  // Migrated: no reserves to model slippage from, so the pool's reported depth travels with
  // the price and callers decide whether it is deep enough to trade on that assumption.
  if (dex) return { priceSol: dex.priceSol, liquidityUsd: dex.liquidityUsd };

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
