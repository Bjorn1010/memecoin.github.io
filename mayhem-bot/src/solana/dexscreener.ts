interface DexScreenerPair {
  priceNative: string;
  priceUsd: string;
  liquidity?: { usd?: number };
}

export interface DexQuote {
  priceSol: number;
  /** Reported depth of the pool this price came from, in USD. We have no reserves for a
   * migrated token, so fills against it are modelled with zero slippage — an assumption that
   * only holds while the pool is deep enough for our position to be negligible in it. This
   * is what lets a caller check that before trusting the price. */
  liquidityUsd: number;
}

const cache = new Map<string, { quote: DexQuote; at: number }>();
const CACHE_MS = 3_000;

/** Fallback spot price (SOL per token) once a coin has migrated off the pump.fun curve. */
export async function getDexscreenerQuote(mintAddress: string): Promise<DexQuote | null> {
  const cached = cache.get(mintAddress);
  if (cached && Date.now() - cached.at < CACHE_MS) return cached.quote;

  try {
    const res = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${mintAddress}`);
    if (!res.ok) return null;
    const json = (await res.json()) as { pairs?: DexScreenerPair[] };
    if (!json.pairs || json.pairs.length === 0) return null;

    const best = json.pairs.reduce((a, b) =>
      (a.liquidity?.usd ?? 0) >= (b.liquidity?.usd ?? 0) ? a : b,
    );
    const price = Number(best.priceNative);
    if (!Number.isFinite(price) || price <= 0) return null;

    const quote: DexQuote = { priceSol: price, liquidityUsd: best.liquidity?.usd ?? 0 };
    cache.set(mintAddress, { quote, at: Date.now() });
    return quote;
  } catch {
    return null;
  }
}
