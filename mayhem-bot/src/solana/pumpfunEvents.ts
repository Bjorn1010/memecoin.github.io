import { createHash } from "node:crypto";
import { PublicKey } from "@solana/web3.js";
import { SOL_DECIMALS, TOKEN_DECIMALS } from "./constants.js";

/**
 * Anchor programs emit structured events via `emit!`/`emit_cpi!`, which show up in a
 * transaction's own logs as a "Program data: <base64>" line — no separate RPC call needed
 * to read them. Every event is prefixed with an 8-byte discriminator = the first 8 bytes
 * of sha256("event:<EventName>"), a fixed Anchor convention (not pump.fun-specific).
 * pump.fun's TradeEvent carries everything we need — mint, exact amounts, direction, trader,
 * and the bonding curve's post-trade reserves — straight from the source of truth, faster
 * than any getParsedTransaction round trip could ever be.
 */
const TRADE_EVENT_DISCRIMINATOR = createHash("sha256").update("event:TradeEvent").digest().subarray(0, 8);

export interface PumpfunTradeEvent {
  mint: string;
  solAmount: number; // UI amount for this specific trade
  tokenAmount: number; // UI amount for this specific trade
  isBuy: boolean;
  user: string;
  timestamp: number;
  virtualSolReserves: bigint;
  virtualTokenReserves: bigint;
}

function decodeTradeEvent(data: Buffer): PumpfunTradeEvent | null {
  // mint(32) solAmount(8) tokenAmount(8) isBuy(1) user(32) timestamp(8)
  // virtualSolReserves(8) virtualTokenReserves(8) [+ more fields in newer versions, ignored]
  const MIN_LEN = 32 + 8 + 8 + 1 + 32 + 8 + 8 + 8;
  if (data.length < MIN_LEN) return null;

  let offset = 0;
  const mint = new PublicKey(data.subarray(offset, offset + 32)).toBase58();
  offset += 32;
  const solAmountRaw = data.readBigUInt64LE(offset);
  offset += 8;
  const tokenAmountRaw = data.readBigUInt64LE(offset);
  offset += 8;
  const isBuy = data.readUInt8(offset) === 1;
  offset += 1;
  const user = new PublicKey(data.subarray(offset, offset + 32)).toBase58();
  offset += 32;
  const timestamp = Number(data.readBigInt64LE(offset));
  offset += 8;
  const virtualSolReserves = data.readBigUInt64LE(offset);
  offset += 8;
  const virtualTokenReserves = data.readBigUInt64LE(offset);

  return {
    mint,
    solAmount: Number(solAmountRaw) / 10 ** SOL_DECIMALS,
    tokenAmount: Number(tokenAmountRaw) / 10 ** TOKEN_DECIMALS,
    isBuy,
    user,
    timestamp,
    virtualSolReserves,
    virtualTokenReserves,
  };
}

/** Scans a transaction's raw log lines for pump.fun TradeEvents — 0, 1, or (rarely) more. */
export function parseTradeEventsFromLogs(logs: string[]): PumpfunTradeEvent[] {
  const events: PumpfunTradeEvent[] = [];

  for (const line of logs) {
    const prefix = "Program data: ";
    if (!line.startsWith(prefix)) continue;

    let data: Buffer;
    try {
      data = Buffer.from(line.slice(prefix.length).trim(), "base64");
    } catch {
      continue;
    }
    if (data.length < 8 || !data.subarray(0, 8).equals(TRADE_EVENT_DISCRIMINATOR)) continue;

    const event = decodeTradeEvent(data.subarray(8));
    if (event) events.push(event);
  }

  return events;
}
