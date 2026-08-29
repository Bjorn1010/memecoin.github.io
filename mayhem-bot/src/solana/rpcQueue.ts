import { RequestQueue } from "./requestQueue.js";
import { config } from "../config.js";

/** Single shared limiter for every RPC HTTP call (tx fetches + bonding curve reads),
 * so the two sources of load never combine to exceed the endpoint's real rate limit. */
export const rpcQueue = new RequestQueue(config.rpcMinGapMs);
