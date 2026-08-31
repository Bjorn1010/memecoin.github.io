import { PublicKey } from "@solana/web3.js";
import { connection } from "../solana/connection.js";
import { rpcQueue } from "../solana/rpcQueue.js";

export interface TokenMetadata {
  name: string;
  symbol: string;
  uri: string;
  description?: string;
  imageUrl?: string;
}

/**
 * pump.fun mints are Token-2022 with the metadata embedded directly in the mint account
 * (the `tokenMetadata` extension) rather than a separate classic Metaplex Metadata PDA —
 * verified on-chain against a live pump.fun mint on 2026-08-31 (the older Metaplex PDA
 * lookup returned nothing for the same mint). This is the SPL-standard extension, so it's
 * stable across pump.fun's own program/router changes — unlike hand-decoding their
 * CreateEvent, which has visibly evolved (BondingCurveV3, V2BuyExactInPumpFun, etc.).
 */
export async function fetchTokenMetadata(mintAddress: string): Promise<TokenMetadata | null> {
  try {
    const mint = new PublicKey(mintAddress);
    const info = await rpcQueue.run(() => connection.getParsedAccountInfo(mint));
    const parsed = info.value?.data;
    if (!parsed || typeof parsed !== "object" || !("parsed" in parsed)) return null;

    const extensions = (parsed as { parsed?: { info?: { extensions?: unknown[] } } }).parsed?.info?.extensions;
    if (!Array.isArray(extensions)) return null;

    const tokenMetadataExt = extensions.find(
      (e): e is { extension: string; state: { name: string; symbol: string; uri: string } } =>
        typeof e === "object" && e !== null && (e as { extension?: string }).extension === "tokenMetadata",
    );
    if (!tokenMetadataExt) return null;

    const { name, symbol, uri } = tokenMetadataExt.state;
    const meta: TokenMetadata = { name, symbol, uri };

    const offchain = await fetchOffchainJson(uri);
    if (offchain) {
      if (typeof offchain.description === "string") meta.description = offchain.description;
      if (typeof offchain.image === "string") meta.imageUrl = offchain.image;
    }

    return meta;
  } catch {
    return null;
  }
}

/** Best-effort fetch of the off-chain metadata JSON (description/image). Never throws. */
async function fetchOffchainJson(uri: string): Promise<{ description?: string; image?: string } | null> {
  if (!uri) return null;
  try {
    const res = await fetch(uri, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return null;
    return (await res.json()) as { description?: string; image?: string };
  } catch {
    return null;
  }
}
