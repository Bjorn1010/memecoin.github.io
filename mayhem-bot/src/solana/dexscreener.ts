interface DexScreenerPair {
  priceNative: string;
  priceUsd: string;
  liquidity?: { usd?: number };
}

const cache = new Map<string, { price: number; at: number }>();
const CACHE_MS = 3_000;

/** Fallback spot price (SOL per token) once a coin has migrated off the pump.fun curve. */
export async function getDexscreenerPrice(mintAddress: string): Promise<number | null> {
  const cached = cache.get(mintAddress);
  if (cached && Date.now() - cached.at < CACHE_MS) return cached.price;

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

    cache.set(mintAddress, { price, at: Date.now() });
    return price;
  } catch {
    return null;
  }
}
