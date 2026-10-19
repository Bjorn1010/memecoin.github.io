import { EventEmitter } from "node:events";
import { PublicKey } from "@solana/web3.js";
import { connection } from "./connection.js";
import { decodeBondingCurveAccountData, deriveBondingCurvePda } from "./bondingCurve.js";
import { SOL_DECIMALS, TOKEN_DECIMALS } from "./constants.js";

export interface BondingCurveUpdate {
  mint: string;
  priceSol: number;
  solReservesUi: number;
  tokenReservesUi: number;
  complete: boolean;
}

export declare interface BondingCurveWatcher {
  on(event: "update", listener: (u: BondingCurveUpdate) => void): this;
}

/**
 * Pushes a price update the instant a watched mint's bonding-curve account changes
 * on-chain, instead of waiting for the next poll. The 2026-08-29 paper-trading runs
 * measured stop-loss/trailing-stop fills landing 2-4x past their nominal threshold
 * (e.g. a -12% stop realizing at -30% to -45%) because the old fixed-interval poll
 * (every 2.5s) could miss most of a token's move between two samples — these
 * freshly-launched pump.fun bonding curves routinely swing 30-90%+ within that window.
 * `onAccountChange` at "processed" commitment reacts within roughly one slot instead,
 * with the account data already attached to the callback — no extra RPC round trip.
 *
 * Caller owns the watch/unwatch lifecycle (one call each per mint gaining/losing its
 * last open position across all strategies) — this class does no reference counting
 * of its own, just tracks which mints currently have a live subscription.
 */
export class BondingCurveWatcher extends EventEmitter {
  private subs = new Map<string, number>();

  isWatching(mint: string): boolean {
    return this.subs.has(mint);
  }

  watch(mint: string) {
    if (this.subs.has(mint)) return;
    const pda = deriveBondingCurvePda(new PublicKey(mint));
    const subId = connection.onAccountChange(
      pda,
      (accountInfo) => {
        const state = decodeBondingCurveAccountData(accountInfo.data);
        if (!state) return;
        this.emit("update", {
          mint,
          priceSol: state.priceSol,
          solReservesUi: Number(state.virtualSolReserves) / 10 ** SOL_DECIMALS,
          tokenReservesUi: Number(state.virtualTokenReserves) / 10 ** TOKEN_DECIMALS,
          complete: state.complete,
        });
      },
      "processed",
    );
    this.subs.set(mint, subId);
  }

  unwatch(mint: string) {
    const subId = this.subs.get(mint);
    if (subId == null) return;
    this.subs.delete(mint);
    connection.removeAccountChangeListener(subId).catch(() => {});
  }

  stopAll() {
    for (const subId of this.subs.values()) connection.removeAccountChangeListener(subId).catch(() => {});
    this.subs.clear();
  }
}
