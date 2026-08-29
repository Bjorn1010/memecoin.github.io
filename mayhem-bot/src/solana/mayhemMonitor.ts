import { EventEmitter } from "node:events";
import { PublicKey } from "@solana/web3.js";
import { nanoid } from "nanoid";
import { connection } from "./connection.js";
import { parseMayhemTransaction } from "./txParser.js";
import { parseTradeEventsFromLogs } from "./pumpfunEvents.js";
import { WalletBalanceTracker } from "./walletBalanceTracker.js";
import { rpcQueue } from "./rpcQueue.js";
import type { MayhemEvent } from "../types.js";

const SEEN_MAX = 5000;
const FALLBACK_MAX_QUEUE_DEPTH = 5;

export declare interface MayhemMonitor {
  on(event: "event", listener: (e: MayhemEvent) => void): this;
  on(event: "status", listener: (s: { wallet: string; state: "subscribed" | "error"; detail?: string }) => void): this;
}

/**
 * Subscribes to live logs for every tracked Mayhem wallet and emits a normalized
 * MayhemEvent as soon as a buy/sell/full-exit is detected on-chain.
 *
 * Fast path (the common case): pump.fun emits a TradeEvent straight into the transaction's
 * own logs, which we already receive for free with every onLogs notification. Decoding it
 * there means zero extra RPC round trips — this is what actually gets us to "least latency
 * possible", not further RPC tuning. Mayhem only trades bonding-curve pump.fun coins, so this
 * covers effectively all real signal.
 *
 * Slow path (rare fallback): if a transaction doesn't decode as a pump.fun TradeEvent (an
 * unexpected instruction shape, program upgrade, etc.), and the RPC queue isn't already
 * backed up, we fetch the full parsed transaction the old way so nothing real gets missed.
 */
export class MayhemMonitor extends EventEmitter {
  private seen = new Set<string>();
  private subs: number[] = [];
  private balances = new WalletBalanceTracker();

  constructor(private wallets: string[]) {
    super();
  }

  async start() {
    for (const wallet of this.wallets) {
      try {
        const pubkey = new PublicKey(wallet);
        const subId = connection.onLogs(
          pubkey,
          (logs) => {
            if (logs.err) return;
            this.handleLogs(wallet, logs.signature, logs.logs);
          },
          "confirmed",
        );
        this.subs.push(subId);
        this.emit("status", { wallet, state: "subscribed" });
      } catch (err) {
        this.emit("status", { wallet, state: "error", detail: String(err) });
      }
    }
  }

  private markSeen(signature: string): boolean {
    if (this.seen.has(signature)) return false;
    this.seen.add(signature);
    if (this.seen.size > SEEN_MAX) {
      const first = this.seen.values().next().value;
      if (first) this.seen.delete(first);
    }
    return true;
  }

  private handleLogs(wallet: string, signature: string, logs: string[]) {
    if (!this.markSeen(signature)) return;
    const receivedAtMs = Date.now();

    const tradeEvents = parseTradeEventsFromLogs(logs).filter((e) => e.user === wallet);

    if (tradeEvents.length > 0) {
      for (const trade of tradeEvents) {
        const delta = trade.isBuy ? trade.tokenAmount : -trade.tokenAmount;
        const balanceAfter = this.balances.applyDelta(wallet, trade.mint, delta);
        const solReservesUi = Number(trade.virtualSolReserves) / 1e9;
        const tokenReservesUi = Number(trade.virtualTokenReserves) / 1e6;
        const priceSol =
          tokenReservesUi > 0
            ? solReservesUi / tokenReservesUi
            : trade.tokenAmount > 0
              ? trade.solAmount / trade.tokenAmount
              : 0;

        const event: MayhemEvent = {
          id: nanoid(),
          wallet,
          kind: trade.isBuy ? "buy" : this.balances.isEffectivelyZero(balanceAfter) ? "full_exit" : "sell",
          mint: trade.mint,
          signature,
          slot: 0,
          blockTime: trade.timestamp,
          solAmount: trade.solAmount,
          tokenAmount: trade.tokenAmount,
          priceSol,
          walletTokenBalanceAfter: balanceAfter,
          detectedAtMs: receivedAtMs,
          solReservesUi,
          tokenReservesUi,
        };
        this.emit("event", event);
      }
      return;
    }

    if (rpcQueue.pending < FALLBACK_MAX_QUEUE_DEPTH) {
      void this.fallbackToRpc(wallet, signature, receivedAtMs);
    }
  }

  private async fallbackToRpc(wallet: string, signature: string, receivedAtMs: number) {
    try {
      const tx = await rpcQueue.run(() =>
        connection.getParsedTransaction(signature, {
          maxSupportedTransactionVersion: 0,
          commitment: "confirmed",
        }),
      );
      if (!tx) return;

      const parsed = parseMayhemTransaction(wallet, signature, tx, wallet);
      for (const p of parsed) {
        const event: MayhemEvent = { ...p, id: nanoid(), detectedAtMs: receivedAtMs };
        this.emit("event", event);
      }
    } catch (err) {
      if (err instanceof Error && err.message.startsWith("stale:")) return;
      this.emit("status", { wallet, state: "error", detail: String(err) });
    }
  }

  stop() {
    for (const id of this.subs) connection.removeOnLogsListener(id).catch(() => {});
    this.subs = [];
  }
}
