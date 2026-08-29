import { Connection } from "@solana/web3.js";
import { config } from "../config.js";

// Default is "confirmed". We tried "processed" globally (lowest latency, but noisier —
// more pre-finalization notifications) and measured it backing up the RPC queue under a
// free-tier rate limit, making real end-to-end latency worse, not better. It's applied
// surgically instead: bondingCurve.ts reads price with "processed" (a plain poll, no
// notification volume impact), while the log subscription below stays "confirmed".
export const connection = new Connection(config.rpcHttpUrl, {
  wsEndpoint: config.rpcWsUrl,
  commitment: "confirmed",
});
