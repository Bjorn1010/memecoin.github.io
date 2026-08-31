import { EventEmitter } from "node:events";
import { connection } from "../solana/connection.js";
import { parseTradeEventsFromLogs } from "../solana/pumpfunEvents.js";
import { PUMPFUN_PROGRAM_ID } from "../solana/constants.js";
import { HolderTracker } from "./holderTracker.js";
import { classifyWallet, emptyCategoryCounts, type WalletCategory } from "./walletClassifier.js";
import { fetchTokenMetadata } from "./tokenMetadata.js";
import { aiConfig } from "./aiConfig.js";

const SEEN_MAX = 20_000;
const PRICE_HISTORY_MAX = 20;

interface TrackedWalletMatch {
  label: string;
}

interface WatchedToken {
  mint: string;
  firstSeenAtMs: number;
  lastUpdateAtMs: number;
  narrativeSummary: string; // "chargement…" until metadata resolves, then cached
  liquiditySol: number;
  solReservesUi: number;
  tokenReservesUi: number;
  priceHistory: number[]; // last N spot prices, oldest first
  tradeCount: number;
  walletCategoryCounts: Record<WalletCategory, number>;
  trackedWalletActivity: WatchedTokenUpdate["trackedWalletActivity"];
}

export interface WatchedTokenUpdate {
  mint: string;
  ageSeconds: number;
  currentPriceSol: number;
  liquiditySol: number;
  holderCount: number;
  avgTopHoldersEntryPriceSol: number | null;
  narrativeSummary: string;
  tradeCount: number;
  poolReserves: { solReservesUi: number; tokenReservesUi: number } | null;
  walletCategoryCounts: Record<WalletCategory, number>;
  trackedWalletActivity: Array<{
    label: string;
    action: "bought" | "sold";
    solAmount: number;
    secondsAgo: number;
  }>;
  recentPriceActionSummary: string;
}

export declare interface TokenWatcher {
  on(event: "update", listener: (u: WatchedTokenUpdate) => void): this;
  on(event: "status", listener: (s: { state: string; detail?: string }) => void): this;
}

/**
 * Subscribes to every pump.fun trade across the whole program (not a fixed wallet list —
 * see mayhemMonitor.ts for that pattern) to discover and follow new tokens as they launch.
 * This is a much higher-volume firehose than mayhem-bot's per-wallet subscriptions; a free
 * public RPC will likely rate-limit or drop under real load — a paid Helius/QuickNode
 * endpoint (same RPC_HTTP_URL/RPC_WS_URL env vars the rest of the project already uses) is
 * effectively required for this to run reliably for real.
 */
export class TokenWatcher extends EventEmitter {
  private tokens = new Map<string, WatchedToken>();
  private seen = new Set<string>();
  private holders = new HolderTracker();
  private sub: number | null = null;
  private pruneInterval: ReturnType<typeof setInterval> | null = null;
  private trackedByAddress = new Map<string, TrackedWalletMatch>(
    aiConfig.trackedWallets.map((w) => [w.address, { label: w.label }]),
  );

  async start() {
    try {
      this.sub = connection.onLogs(
        PUMPFUN_PROGRAM_ID,
        (logs) => {
          if (logs.err) return;
          this.handleLogs(logs.signature, logs.logs);
        },
        "confirmed",
      );
      this.emit("status", { state: "subscribed" });
    } catch (err) {
      this.emit("status", { state: "error", detail: String(err) });
    }

    this.pruneInterval = setInterval(() => this.pruneInactive(), 60_000);
  }

  stop() {
    if (this.sub != null) connection.removeOnLogsListener(this.sub).catch(() => {});
    if (this.pruneInterval) clearInterval(this.pruneInterval);
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

  private handleLogs(signature: string, logs: string[]) {
    if (!this.markSeen(signature)) return;
    const events = parseTradeEventsFromLogs(logs);
    for (const event of events) this.handleTrade(event, signature);
  }

  private handleTrade(
    event: {
      mint: string;
      user: string;
      isBuy: boolean;
      solAmount: number;
      tokenAmount: number;
      virtualSolReserves: bigint;
      virtualTokenReserves: bigint;
    },
    _signature: string,
  ) {
    const nowMs = Date.now();
    let token = this.tokens.get(event.mint);
    const isFirstTradeForMint = !token;

    if (!token) {
      if (this.tokens.size >= aiConfig.maxWatchedTokens) return; // bounded discovery load
      token = {
        mint: event.mint,
        firstSeenAtMs: nowMs,
        lastUpdateAtMs: nowMs,
        narrativeSummary: "(métadonnées en cours de récupération…)",
        liquiditySol: 0,
        solReservesUi: 0,
        tokenReservesUi: 0,
        priceHistory: [],
        tradeCount: 0,
        walletCategoryCounts: emptyCategoryCounts(),
        trackedWalletActivity: [],
      };
      this.tokens.set(event.mint, token);
      void this.resolveMetadata(event.mint);
    }

    const secondsSinceFirstSeen = (nowMs - token.firstSeenAtMs) / 1000;
    const category = classifyWallet({
      isFirstTradeForMint,
      secondsSinceMintFirstSeen: secondsSinceFirstSeen,
      solAmount: event.solAmount,
    });

    this.holders.applyTrade(event.mint, event.user, event.isBuy, event.tokenAmount, event.solAmount);
    token.walletCategoryCounts[category] += 1;
    token.tradeCount += 1;
    token.lastUpdateAtMs = nowMs;

    const solReservesUi = Number(event.virtualSolReserves) / 1e9;
    const tokenReservesUi = Number(event.virtualTokenReserves) / 1e6;
    const priceSol = tokenReservesUi > 0 ? solReservesUi / tokenReservesUi : 0;
    token.liquiditySol = solReservesUi;
    token.solReservesUi = solReservesUi;
    token.tokenReservesUi = tokenReservesUi;
    token.priceHistory.push(priceSol);
    if (token.priceHistory.length > PRICE_HISTORY_MAX) token.priceHistory.shift();

    const tracked = this.trackedByAddress.get(event.user);
    if (tracked) {
      token.trackedWalletActivity.unshift({
        label: tracked.label,
        action: event.isBuy ? "bought" : "sold",
        solAmount: event.solAmount,
        secondsAgo: 0,
      });
      token.trackedWalletActivity = token.trackedWalletActivity.slice(0, 5);
    }

    this.emit("update", this.buildUpdate(token));
  }

  private async resolveMetadata(mint: string) {
    const meta = await fetchTokenMetadata(mint);
    const token = this.tokens.get(mint);
    if (!token) return; // pruned before metadata came back
    token.narrativeSummary = meta
      ? `${meta.name} (${meta.symbol})${meta.description ? " — " + meta.description : ""}`
      : "(narratif indisponible — métadonnées introuvables)";
  }

  private buildUpdate(token: WatchedToken): WatchedTokenUpdate {
    const nowMs = Date.now();
    const currentPriceSol = token.priceHistory[token.priceHistory.length - 1] ?? 0;
    return {
      mint: token.mint,
      ageSeconds: Math.round((nowMs - token.firstSeenAtMs) / 1000),
      currentPriceSol,
      liquiditySol: token.liquiditySol,
      holderCount: this.holders.getHolderCount(token.mint),
      avgTopHoldersEntryPriceSol: this.holders.getTopHoldersAvgEntryPriceSol(token.mint, 10),
      narrativeSummary: token.narrativeSummary,
      tradeCount: token.tradeCount,
      poolReserves:
        token.tokenReservesUi > 0
          ? { solReservesUi: token.solReservesUi, tokenReservesUi: token.tokenReservesUi }
          : null,
      walletCategoryCounts: { ...token.walletCategoryCounts },
      trackedWalletActivity: token.trackedWalletActivity.map((a) => ({ ...a })),
      recentPriceActionSummary: summarizePriceAction(token.priceHistory),
    };
  }

  private pruneInactive() {
    const cutoff = Date.now() - aiConfig.inactiveTokenPruneMs;
    for (const [mint, token] of this.tokens) {
      if (token.lastUpdateAtMs < cutoff) {
        this.tokens.delete(mint);
        this.holders.prune(mint);
      }
    }
  }
}

function summarizePriceAction(history: number[]): string {
  if (history.length < 2) return "pas assez de données de prix encore";
  const first = history[0];
  const last = history[history.length - 1];
  const changePct = first > 0 ? ((last - first) / first) * 100 : 0;
  let downTicks = 0;
  for (let i = 1; i < history.length; i++) if (history[i] < history[i - 1]) downTicks++;
  const direction = changePct >= 0 ? "monte" : "baisse";
  return `${direction} de ${Math.abs(changePct).toFixed(0)}% sur les ${history.length} derniers trades, ${downTicks} mèches vendeuses`;
}
