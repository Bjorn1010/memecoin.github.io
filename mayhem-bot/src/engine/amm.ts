/**
 * Constant-product AMM math (x*y=k), the same curve pump.fun's bonding curve runs on.
 * Given the pool's real reserves at the moment of the trade, this computes the *actual*
 * execution price for a given trade size — not the pre-trade spot price. This is what
 * "slippage" means in practice: the bigger the trade relative to pool depth, the further
 * the average fill price moves from the quote you saw a second earlier.
 */

export interface FillResult {
  /** Average price actually paid/received across the whole trade. */
  avgPriceSol: number;
  /** How far the average price moved from the pre-trade spot price, as a fraction (0.02 = 2%). */
  slippagePct: number;
}

/** Spending `solIn` SOL against reserves (solReserves, tokenReserves) — a market buy. */
export function simulateBuy(solIn: number, solReserves: number, tokenReserves: number): FillResult {
  const spotPrice = solReserves / tokenReserves;
  if (solIn <= 0 || solReserves <= 0 || tokenReserves <= 0) {
    return { avgPriceSol: spotPrice, slippagePct: 0 };
  }
  const k = solReserves * tokenReserves;
  const tokensOut = tokenReserves - k / (solReserves + solIn);
  const avgPriceSol = tokensOut > 0 ? solIn / tokensOut : spotPrice;
  return { avgPriceSol, slippagePct: spotPrice > 0 ? avgPriceSol / spotPrice - 1 : 0 };
}

/** Selling `tokensIn` tokens into reserves (solReserves, tokenReserves) — a market sell. */
export function simulateSell(tokensIn: number, solReserves: number, tokenReserves: number): FillResult {
  const spotPrice = solReserves / tokenReserves;
  if (tokensIn <= 0 || solReserves <= 0 || tokenReserves <= 0) {
    return { avgPriceSol: spotPrice, slippagePct: 0 };
  }
  const k = solReserves * tokenReserves;
  const solOut = solReserves - k / (tokenReserves + tokensIn);
  const avgPriceSol = tokensIn > 0 ? solOut / tokensIn : spotPrice;
  return { avgPriceSol, slippagePct: spotPrice > 0 ? avgPriceSol / spotPrice - 1 : 0 };
}
