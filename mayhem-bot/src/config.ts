import "dotenv/config";

function requireEnvList(name: string, fallback: string[]): string[] {
  const raw = process.env[name];
  if (!raw) return fallback;
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export const config = {
  rpcHttpUrl: process.env.RPC_HTTP_URL ?? "https://api.mainnet-beta.solana.com",
  rpcWsUrl: process.env.RPC_WS_URL ?? "wss://api.mainnet-beta.solana.com",
  mayhemWallets: requireEnvList("MAYHEM_WALLETS", [
    "BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s",
    "Gygj9QQby4j2jryqyqBHvLP7ctv2SaANgh4sCb69BUpA",
  ]),
  port: Number(process.env.PORT ?? 8787),
  dbPath: process.env.DB_PATH ?? "./data/mayhem-bot.db",
  // Minimum gap between getParsedTransaction calls. Public RPC needs this conservative;
  // drop it (e.g. 50-100) once RPC_HTTP_URL points at a paid Helius/QuickNode/Triton key.
  rpcMinGapMs: Number(process.env.RPC_MIN_GAP_MS ?? 350),
};
