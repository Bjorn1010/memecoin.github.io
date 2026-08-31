/**
 * The engine.
 *
 * One pipeline serves all three modes, because the only honest way to know that
 * `--paper` predicts `--live` is for them to run the same code with the last
 * step switched off:
 *
 *   feed -> decode -> cycles -> sizing -> costs -> risk -> build -> simulate
 *        -> decision -> [observe: stop | paper: stop | live: send]
 *
 * `--observe` additionally re-checks each opportunity after a series of delays
 * and records whether it was still there, which is the measurement that decides
 * whether our latency is survivable at all (§25).
 */
import {
  Keypair,
  MessageV0,
  PublicKey,
  SystemProgram,
  type VersionedMessage,
  type VersionedTransaction,
} from "@solana/web3.js";
import type { Config } from "./config/schema.js";
import { WSOL_MINT, parseMintList } from "./config/schema.js";
import type { RpcClient } from "./rpc/RpcClient.js";
import { RpcPriority } from "./rpc/RpcBudget.js";
import type { MarketDataFeed } from "./feed/MarketDataFeed.js";
import { PoolStateStore, type PoolRegistration } from "./feed/PoolStateStore.js";
import { RaydiumCpmmQuoter } from "./quoters/cpmm/raydiumCpmm.js";
import { PumpSwapQuoter } from "./quoters/cpmm/pumpSwap.js";
import type { Quoter } from "./quoters/Quoter.js";
import type { DexFamily, MintState, PoolSnapshot, RejectReason, SizedCycle } from "./types.js";
import { enumerateCycles, evaluateCycle } from "./search/opportunity.js";
import {
  isStateFresh,
  type FeedHealth,
  type FreshnessPolicy,
} from "./search/freshness.js";
import {
  computeTransactionCosts,
  decideTip,
  type ClusterFeeParams,
} from "./costs/fees.js";
import { profitNet } from "./costs/profitNet.js";
import {
  LandRateEstimator,
  hourBucket,
  latencyBucket,
  profitBucket,
  type SendOutcome,
} from "./costs/landRate.js";
import { checkLimits, type RiskLimits, type WalletSnapshot } from "./risk/limits.js";
import { checkMint, type TokenPolicy } from "./risk/tokenFilters.js";
import type { KillSwitch } from "./risk/killSwitch.js";
import { OpportunityLocks } from "./util/lock.js";
import { Ledger, type AttemptRecord } from "./obs/ledger.js";
import { decodeTokenAccount } from "./feed/decoder/token2022.js";
import type { Metrics } from "./obs/metrics.js";
import { buildArbitrageCycle, walletTokenAccount } from "./exec/transactionBuilder.js";
import { loadLookupTable } from "./exec/lookupTable.js";
import { computeUnitLimitFrom, isSlippageFailure, simulateCycle } from "./exec/simulator.js";
import type { TxSender } from "./exec/TxSender.js";
import { WatchlistSelector } from "./screener/selector.js";
import { scorePool, type PoolMetrics } from "./screener/scorer.js";
import {
  discoverActiveMints,
  discoverPoolsForMints,
  fetchMint,
  mintsWithMultiplePools,
  pumpFeeConfigAddress,
  pumpGlobalConfigAddress,
} from "./screener/discovery.js";
import { bpsOf } from "./util/bigintMath.js";

/** Delays at which an observed opportunity is re-checked (§25). */
export const SURVIVAL_PROBES_MS = [200, 500, 1_000, 5_000];

export interface EngineDeps {
  config: Config;
  rpc: RpcClient;
  feed: MarketDataFeed;
  ledger: Ledger;
  metrics: Metrics;
  killSwitch: KillSwitch;
  /** Null in observe mode: nothing is ever sent. */
  sender: TxSender | null;
  /** Null unless live: paper mode builds and simulates unsigned. */
  wallet: Keypair | null;
}

interface PoolActivity {
  opportunityCount: number;
  netProfitableCount: number;
  netProfitTotal: bigint;
  netProfits: bigint[];
  survivalMs: number[];
  vanishedFast: number;
  quoteErrors: number;
  usableDepth: bigint;
  firstSeen: number;
}

export class ArbEngine {
  private readonly store: PoolStateStore;
  private readonly quoters: ReadonlyMap<DexFamily, Quoter>;
  private readonly locks: OpportunityLocks;
  private readonly landRate: LandRateEstimator;
  private readonly selector: WatchlistSelector;
  private readonly tokenPolicy: TokenPolicy;
  private readonly riskLimits: RiskLimits;
  private readonly activity = new Map<string, PoolActivity>();
  private readonly registrations = new Map<string, PoolRegistration>();

  private cluster: ClusterFeeParams | null = null;
  private lookupTables: import("@solana/web3.js").AddressLookupTableAccount[] = [];
  private epoch = 0n;
  private blockTimeSeconds = Math.floor(Date.now() / 1000);
  private dailyRealisedPnl = 0n;
  private dailyKey = "";
  private running = false;
  private evaluating = false;
  private evaluateScheduled: NodeJS.Timeout | null = null;
  private screenerTimer: NodeJS.Timeout | null = null;
  private inFlight = 0;
  private walletState: WalletSnapshot = {
    nativeLamports: 0n,
    baseTokenLamports: 0n,
    tokenExposureLamports: 0n,
    inFlightTx: 0,
  };

  constructor(private readonly deps: EngineDeps) {
    const c = deps.config;
    this.store = new PoolStateStore({
      pumpGlobalConfigAddress: pumpGlobalConfigAddress(),
      pumpFeeConfigAddress: pumpFeeConfigAddress(),
    });
    this.quoters = new Map<DexFamily, Quoter>([
      ["raydium-cpmm", new RaydiumCpmmQuoter()],
      ["pump-swap", new PumpSwapQuoter()],
    ]);
    this.locks = new OpportunityLocks(c.opportunityLockTimeoutMs, (key, heldMs) => {
      console.warn(`[lock] released ${key} after ${heldMs}ms without an explicit release`);
    });
    this.landRate = new LandRateEstimator({
      priorStrength: c.landRatePriorStrength,
      priorSuccessShare: c.landRatePriorSuccessShare,
      priorRevertedShare: 0.2,
      minSamplesPerSegment: c.landRateMinSamples,
    });
    const restored = deps.ledger.loadLandRate<Record<string, never>>();
    if (restored) this.landRate.restore(restored);

    this.selector = new WatchlistSelector({
      maxWatched: c.maxWatchedPools,
      entryMarginScore: c.screenerEntryMargin,
      minScoreToStay: c.screenerMinScore,
      minResidencyMs: c.screenerMinResidencyMs,
      cooldownMs: c.screenerCooldownMs,
    });
    this.tokenPolicy = {
      rejectFreezeAuthority: c.rejectFreezeAuthority,
      rejectMintAuthority: c.rejectMintAuthority,
      minDecimals: 0,
      maxDecimals: 18,
      minPoolLiquidityLamports: c.minPoolLiquidity,
      minPoolAgeMs: c.minPoolAgeMs,
      blacklist: parseMintList(c.blacklistMints),
      whitelist: parseMintList(c.whitelistMints),
    };
    this.riskLimits = {
      maxTradeSizeLamports: c.maxTradeSize,
      maxTokenExposureLamports: c.maxTokenExposure,
      maxInFlightTx: c.maxInFlightTx,
      maxDailyLossLamports: c.maxDailyLoss,
      reserveLamports: c.feeReserve,
    };
  }

  // --- lifecycle ------------------------------------------------------------

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;
    const { rpc, feed, config } = this.deps;

    this.epoch = await rpc.getEpoch(RpcPriority.P0_Critical);
    this.blockTimeSeconds = await rpc.getBlockTimeSeconds(RpcPriority.P0_Critical);
    this.cluster = await this.readClusterFeeParams();

    await this.loadLookupTables();
    if (this.deps.sender) await this.deps.sender.prepare();
    if (this.deps.wallet) await this.refreshWallet();

    feed.on("account", (u) => {
      this.store.applyUpdate(u, config.mode === "replay" ? "replay" : "ws");
      // Observe mode captures raw state so the run can be replayed against a
      // different configuration later without touching the network again.
      if (config.mode === "observe") this.deps.ledger.writeState(u);
      this.scheduleEvaluation();
    });
    feed.on("status", (s) => {
      if (s.kind === "disconnected" || s.kind === "stalled") {
        this.deps.metrics.feedReconnects++;
        console.warn(`[feed] ${s.kind}: ${JSON.stringify(s)}`);
      } else if (s.kind === "resubscribed") {
        console.log(`[feed] resubscribed ${s.count} accounts`);
      }
    });
    feed.on("error", (e) => {
      this.deps.metrics.rpcErrors++;
      console.warn(`[feed] error: ${e.message}`);
    });

    this.warnIfSimulationIsBlind();
    await feed.start();
    // The shared config accounts must be watched: pump's fee tiers live in one
    // of them, and a fee change we did not see would make every quote wrong.
    await feed.subscribe([pumpGlobalConfigAddress(), pumpFeeConfigAddress()]);
    await this.primeSharedAccounts();

    await this.runScreener();
    this.screenerTimer = setInterval(() => {
      void this.runScreener().catch((e) => console.warn(`[screener] ${describe(e)}`));
    }, config.screenerIntervalMs);
    this.screenerTimer.unref?.();
  }

  async stop(): Promise<void> {
    this.running = false;
    if (this.screenerTimer) clearInterval(this.screenerTimer);
    if (this.evaluateScheduled) clearTimeout(this.evaluateScheduled);
    this.locks.releaseAll();
    await this.deps.feed.stop();
    this.deps.ledger.saveLandRate(this.landRate.snapshot());
  }

  private async readClusterFeeParams(): Promise<ClusterFeeParams> {
    const rent = await this.deps.rpc.getMinimumBalanceForRentExemption(165, RpcPriority.P0_Critical);
    // The base fee per signature is read from the cluster rather than assumed:
    // a one-signature message with no priority fee costs exactly one signature.
    const { blockhash } = await this.deps.rpc.getLatestBlockhash();
    const probe = buildFeeProbeMessage(blockhash);
    const fee = await this.deps.rpc.getFeeForMessage(probe, RpcPriority.P0_Critical);
    const slot = await this.deps.rpc.getSlot(RpcPriority.P0_Critical);
    if (fee === null) {
      throw new Error("cluster did not price a probe message; cannot build a cost model");
    }
    return { lamportsPerSignature: fee, tokenAccountRentLamports: rent, slot };
  }

  private async primeSharedAccounts(): Promise<void> {
    const addresses = [pumpGlobalConfigAddress(), pumpFeeConfigAddress()];
    const accounts = await this.deps.rpc.getAccounts(addresses, RpcPriority.P0_Critical);
    accounts.forEach((a) => {
      if (a) this.store.applyUpdate({ ...a }, "rpc");
    });
  }

  // --- screener -------------------------------------------------------------

  private async runScreener(): Promise<void> {
    const { rpc, config, ledger } = this.deps;
    const now = Date.now();

    const active = await discoverActiveMints(rpc, { transactionsPerVenue: 25 });
    const candidateMints = [...active.entries()]
      .filter(([m]) => m !== WSOL_MINT)
      .sort((a, b) => b[1] - a[1])
      .slice(0, Math.max(config.maxWatchedPools * 2, 20))
      .map(([m]) => m);
    if (candidateMints.length === 0) return;

    const byMint = await discoverPoolsForMints(rpc, candidateMints);
    const allPools = [...byMint.values()].flat();
    const cycleable = mintsWithMultiplePools(allPools);

    // Only mints that pass the risk filter can produce a tradable cycle, so
    // filter before spending subscriptions on them.
    const admitted: PoolRegistration[] = [];
    for (const [mint, pools] of cycleable) {
      let mintState = this.store.getMint(mint);
      if (!mintState) {
        const fetched = await fetchMint(rpc, mint, this.epoch);
        if (!fetched) continue;
        this.store.setMint(fetched);
        mintState = fetched;
      }
      const verdict = checkMint(mintState, this.tokenPolicy);
      if (!verdict.accepted) continue;
      admitted.push(...pools);
    }
    if (!this.store.getMint(WSOL_MINT)) {
      const wsol = await fetchMint(rpc, WSOL_MINT, this.epoch);
      if (wsol) this.store.setMint(wsol);
    }

    const scores = admitted.map((p) => scorePool(this.metricsFor(p.poolId, now)));
    const { changes } = this.selector.update(scores, now);

    for (const change of changes) {
      ledger.writeWatchlistChange({
        timestamp: change.at,
        poolId: change.poolId,
        action: change.action,
        reason: change.reason,
        score: change.score,
      });
      if (change.action === "enter") {
        const reg = admitted.find((p) => p.poolId === change.poolId);
        if (!reg) continue;
        this.registrations.set(reg.poolId, reg);
        this.store.registerPool(reg);
        try {
          await this.deps.feed.subscribe([reg.poolAccount, reg.vaultA, reg.vaultB, ...(reg.configAccount ? [reg.configAccount] : [])]);
          this.store.setSubscribed(this.deps.feed.subscriptions());
          await this.primePool(reg);
        } catch (e) {
          console.warn(`[screener] could not subscribe ${reg.poolId}: ${describe(e)}`);
          this.selector.evict(reg.poolId, `subscribe failed: ${describe(e)}`, now);
          this.store.unregisterPool(reg.poolId);
        }
      } else {
        const exclusive = this.store.accountsExclusiveTo(change.poolId);
        this.store.unregisterPool(change.poolId);
        this.registrations.delete(change.poolId);
        await this.deps.feed.unsubscribe(exclusive);
        this.store.setSubscribed(this.deps.feed.subscriptions());
      }
    }

    console.log(
      `[screener] ${cycleable.size} cycleable mints, watching ${this.selector.current().length} pools, ${changes.length} changes`,
    );
  }

  /** Fetch a newly watched pool's accounts once so it is quotable immediately. */
  private async primePool(reg: PoolRegistration): Promise<void> {
    const addresses = [reg.poolAccount, reg.vaultA, reg.vaultB];
    if (reg.configAccount) addresses.push(reg.configAccount);
    const accounts = await this.deps.rpc.getAccounts(addresses, RpcPriority.P2_TradingState);
    accounts.forEach((a) => {
      if (a) this.store.applyUpdate({ ...a }, "rpc");
    });
    for (const mint of [reg.mintA, reg.mintB]) {
      if (this.store.getMint(mint)) continue;
      const m = await fetchMint(this.deps.rpc, mint, this.epoch, RpcPriority.P2_TradingState);
      if (m) this.store.setMint(m);
    }
  }

  private metricsFor(poolId: string, now: number): PoolMetrics {
    const a = this.activity.get(poolId);
    const reg = this.registrations.get(poolId);
    const window = a ? now - a.firstSeen : 0;
    const landRate = this.landRate.estimate([poolId]).pSuccess;
    return {
      poolId,
      family: reg?.family ?? "unknown",
      observationWindowMs: window,
      opportunityCount: a?.opportunityCount ?? 0,
      netProfitableCount: a?.netProfitableCount ?? 0,
      survivalMsP50: a ? median(a.survivalMs) : 0,
      vanishedBeforeWeCouldActCount: a?.vanishedFast ?? 0,
      netProfitMedianLamports: a ? medianBigint(a.netProfits) : 0n,
      netProfitTotalLamports: a?.netProfitTotal ?? 0n,
      usableDepthLamports: a?.usableDepth ?? 0n,
      quoteErrors: a?.quoteErrors ?? 0,
      decodeErrors: this.store.decodeFailureCount(poolId),
      simulationFailures: 0,
      attempts: this.landRate.rawCounts([poolId]).success + this.landRate.rawCounts([poolId]).reverted,
      landRate,
    };
  }

  // --- evaluation -----------------------------------------------------------

  /**
   * Coalesce bursts of account updates into one evaluation. A single swap
   * touches three accounts; evaluating three times would triple the CPU cost
   * and, worse, triple the chance of racing ourselves into a double attempt.
   */
  private scheduleEvaluation(): void {
    if (this.evaluateScheduled || !this.running) return;
    this.evaluateScheduled = setTimeout(() => {
      this.evaluateScheduled = null;
      void this.evaluateAll().catch((e) => console.warn(`[engine] ${describe(e)}`));
    }, 5);
    this.evaluateScheduled.unref?.();
  }

  private async evaluateAll(): Promise<void> {
    if (this.evaluating || !this.running) return;
    this.evaluating = true;
    try {
      const detectedAt = Date.now();
      const { snapshots } = this.store.allSnapshots();
      if (snapshots.length < 2) return;

      const byId = new Map(snapshots.map((s) => [s.poolId, s]));
      const cycles = enumerateCycles(snapshots, WSOL_MINT);
      const currentSlot = this.deps.feed.currentSlot();
      const ctx = {
        mints: this.store.mintMap(),
        currentSlot,
        blockTimeSeconds: this.blockTimeSeconds,
      };

      let best: { sized: SizedCycle; buy: PoolSnapshot; sell: PoolSnapshot } | null = null;
      for (const cycle of cycles) {
        const buyPool = byId.get(cycle.buyPoolId);
        const sellPool = byId.get(cycle.sellPoolId);
        if (!buyPool || !sellPool) continue;

        this.deps.metrics.cyclesEvaluated++;
        const evaluated = evaluateCycle({
          cycle,
          buyPool,
          sellPool,
          quoters: this.quoters,
          ctx,
          limits: {
            maxTradeSizeLamports: this.deps.config.maxTradeSize,
            availableCapitalLamports: this.availableCapital(),
            minTradeSizeLamports: this.deps.config.minTradeSize,
          },
          freshness: this.freshnessPolicy(),
          feed: this.feedHealth(),
          nowMs: detectedAt,
        });

        if (evaluated.quoteError) this.bumpActivity(cycle.buyPoolId, (a) => a.quoteErrors++);
        if (evaluated.rejected) {
          this.deps.metrics.reject(evaluated.rejected);
          continue;
        }
        if (!evaluated.sized) continue;

        this.deps.metrics.cyclesGrossProfitable++;
        if (!best || evaluated.sized.grossProfit > best.sized.grossProfit) {
          best = { sized: evaluated.sized, buy: buyPool, sell: sellPool };
        }
      }

      if (best) await this.handleOpportunity(best.sized, best.buy, best.sell, detectedAt);
    } finally {
      this.evaluating = false;
    }
  }

  /**
   * Who the transaction is built for.
   *
   * Live signs with the wallet. Paper uses WALLET_PUBLIC_KEY when set, so the
   * simulation runs against real balances and its numbers mean something —
   * simulating from an account that holds no WSOL fails at leg 1 every time and
   * measures nothing. With neither, we fall back to a placeholder and say so.
   */
  private simulationPayer(): PublicKey {
    if (this.deps.wallet) return this.deps.wallet.publicKey;
    const configured = this.deps.config.walletPublicKey;
    if (configured) {
      try {
        return new PublicKey(configured);
      } catch {
        // Reported once at startup by warnIfSimulationIsBlind.
      }
    }
    return PLACEHOLDER_PAYER;
  }

  /** Say plainly when paper mode cannot produce a meaningful simulation. */
  private warnIfSimulationIsBlind(): void {
    if (this.deps.config.mode !== "paper") return;
    if (this.deps.wallet) return;
    const configured = this.deps.config.walletPublicKey;
    let usable = false;
    if (configured) {
      try {
        new PublicKey(configured);
        usable = true;
      } catch {
        console.warn(`[paper] WALLET_PUBLIC_KEY is not a valid public key: ${configured}`);
      }
    }
    if (!usable) {
      console.warn(
        "[paper] no WALLET_PUBLIC_KEY set: simulations will fail for lack of balance, so " +
          "compute-unit and quote-divergence numbers will be missing. Set it to a funded " +
          "wallet's PUBLIC key (no secret is needed) to make paper mode measure anything.",
      );
    }
  }

  /**
   * Load the address lookup table, and say clearly what its absence costs.
   * Without one, mixed-venue cycles simply cannot be built — they exceed the
   * transaction size limit — so the bot would silently trade a fraction of the
   * opportunities it found.
   */
  private async loadLookupTables(): Promise<void> {
    const address = this.deps.config.lookupTableAddress;
    if (!address) {
      if (this.deps.config.mode === "live" || this.deps.config.mode === "paper") {
        console.warn(
          "[alt] no LOOKUP_TABLE_ADDRESS configured. PumpSwap+Raydium cycles measure ~1281 bytes " +
            "against a 1232-byte limit and will be REFUSED at build time; only same-venue cycles " +
            "will trade. Run `npm run setup` to create one.",
        );
      }
      return;
    }
    try {
      const table = await loadLookupTable(this.deps.rpc.connection, address);
      if (!table) {
        console.warn(`[alt] no lookup table found at ${address}; mixed-venue cycles will be refused`);
        return;
      }
      this.lookupTables = [table];
      console.log(`[alt] loaded ${table.state.addresses.length} addresses from ${address}`);
    } catch (e) {
      console.warn(`[alt] could not load ${address}: ${describe(e)}`);
    }
  }

  private freshnessPolicy(): FreshnessPolicy {
    return {
      maxStateAgeMs: this.deps.config.maxStateAgeMs,
      maxStateAgeSlots: this.deps.config.maxStateAgeSlots,
      feedStallMs: this.deps.config.feedStallMs,
    };
  }

  private feedHealth(): FeedHealth {
    const stats = this.deps.feed.stats();
    return {
      connected: stats.connected,
      lastUpdateAt: stats.lastUpdateAt,
      dataSlot: this.deps.feed.currentSlot(),
    };
  }

  private availableCapital(): bigint {
    const cap = this.deps.config.maxTradeSize;
    // Observe and paper hold no capital, so the cap is the only constraint that
    // means anything. Live is bounded by what the wallet actually holds — a
    // zero balance there must size to zero, not to the cap, or every cycle is
    // sized against money we do not have and rejected one stage later.
    if (this.deps.config.mode !== "live") return cap;
    const balance = this.walletState.baseTokenLamports;
    return balance < cap ? balance : cap;
  }

  private async handleOpportunity(
    sized: SizedCycle,
    buyPool: PoolSnapshot,
    sellPool: PoolSnapshot,
    detectedAt: number,
  ): Promise<void> {
    const { config, metrics, ledger, killSwitch } = this.deps;
    const now = Date.now();
    const freshness = isStateFresh(
      {
        slot: sized.slot,
        receivedAt: sized.receivedAt,
        source: buyPool.source,
        subscribed: buyPool.subscribed && sellPool.subscribed,
      },
      this.feedHealth(),
      now,
      this.freshnessPolicy(),
    );

    this.recordActivity(sized, freshness.ageMs);

    const lockKey = OpportunityLocks.keyFor(sized.buyPoolId, sized.sellPoolId);
    const lock = this.locks.tryAcquire(lockKey, now);
    if (!lock) {
      metrics.reject("locked-in-flight");
      return;
    }

    try {
      if (killSwitch.tripped) {
        this.reject(sized, "kill-switch", detectedAt, freshness);
        return;
      }

      // --- cost model -------------------------------------------------------
      const cluster = this.cluster;
      if (!cluster) {
        this.reject(sized, "build-failed", detectedAt, freshness);
        return;
      }
      const sender = this.deps.sender;
      const revertCostsFees = sender ? sender.revertCostsFees : true;
      const segment = this.segmentFor(sized, freshness.ageMs, now);
      const landRate = this.landRate.estimate(segment);

      // Start from a conservative CU estimate; simulation replaces it below.
      const provisionalCuLimit = Math.min(config.maxComputeUnitLimit, 250_000);
      const cuPrice = config.maxComputeUnitPriceMicroLamports;
      const provisionalCosts = computeTransactionCosts({
        cluster,
        numSignatures: 1,
        computeUnitLimit: provisionalCuLimit,
        computeUnitPriceMicroLamports: cuPrice,
        tipLamports: 0n,
        revertCostsFees,
      });

      const tip = config.useJito
        ? decideTip({
            grossProfit: sized.grossProfit,
            baseFee: provisionalCosts.baseFee,
            priorityFee: provisionalCosts.priorityFee,
            policy: {
              minTipLamports: bigintMax(config.minTip, sender?.minTipLamports ?? 0n),
              maxTipLamports: config.maxTip,
              maxTipShareBps: BigInt(config.maxTipShareBps),
              minProfitLamports: config.minProfit,
            },
          })
        : { tipLamports: 0n, profitAfterTip: 0n, viable: true, reason: "ok" as const };

      if (!tip.viable) {
        this.reject(sized, "below-min-profit", detectedAt, freshness);
        return;
      }

      const costs = computeTransactionCosts({
        cluster,
        numSignatures: 1,
        computeUnitLimit: provisionalCuLimit,
        computeUnitPriceMicroLamports: cuPrice,
        tipLamports: tip.tipLamports,
        revertCostsFees,
      });

      const profit = profitNet({
        grossProfit: sized.grossProfit,
        costs,
        landRate,
        minProfitLamports: config.minProfit,
        minExpectedValueLamports: config.minExpectedValue,
      });

      // The screener scores on net profit; recordActivity only saw the gross
      // figure, which would rank an expensive pool as if its fees were free.
      this.bumpActivity(sized.buyPoolId, (act) => {
        act.netProfits.push(profit.netProfitIfLanded);
        if (act.netProfits.length > 500) act.netProfits.shift();
        act.netProfitTotal += profit.netProfitIfLanded;
        if (profit.netProfitIfLanded > 0n) act.netProfitableCount++;
      });

      if (!profit.shouldTrade) {
        this.reject(sized, profit.reason as RejectReason, detectedAt, freshness, {
          expectedNet: profit.netProfitIfLanded,
          expectedValue: profit.expectedValue,
          costs,
          landRate,
        });
        return;
      }

      // --- risk -------------------------------------------------------------
      const intermediate = this.store.getMint(sized.intermediateMint);
      if (!intermediate) {
        this.reject(sized, "risk-token-rejected", detectedAt, freshness);
        return;
      }
      const tokenVerdict = checkMint(intermediate, this.tokenPolicy, {
        poolLiquidityLamports: sized.legs[0].reserveIn,
      });
      if (!tokenVerdict.accepted) {
        this.reject(sized, "risk-token-rejected", detectedAt, freshness);
        return;
      }

      if (config.mode === "live") {
        const limitVerdict = checkLimits({
          limits: this.riskLimits,
          wallet: { ...this.walletState, inFlightTx: this.inFlight },
          amountIn: sized.amountIn,
          costOnSuccess: costs.onSuccess,
          dailyRealisedPnl: this.dailyRealisedPnl,
        });
        if (!limitVerdict.allowed) {
          console.warn(`[risk] ${limitVerdict.detail}`);
          this.reject(sized, limitVerdict.reason as RejectReason, detectedAt, freshness);
          return;
        }
      }

      // --- observe stops here ----------------------------------------------
      if (config.mode === "observe") {
        metrics.outcome("not-sent");
        metrics.expectedNetPnl += profit.netProfitIfLanded;
        this.writeAttempt(sized, detectedAt, freshness, {
          outcome: "not-sent",
          rejectReason: null,
          expectedNet: profit.netProfitIfLanded,
          expectedValue: profit.expectedValue,
          costs,
          landRate,
        });
        void this.probeSurvival(sized, buyPool, sellPool, detectedAt);
        return;
      }

      // --- build ------------------------------------------------------------
      const payer = this.simulationPayer();
      const mints = this.store.mintMap();
      let built;
      try {
        const { blockhash, lastValidBlockHeight } = await this.deps.rpc.getLatestBlockhash();
        built = {
          ...buildArbitrageCycle({
            sized,
            buyPool,
            sellPool,
            mints,
            payer,
            baseTokenAccount: walletTokenAccount(mints, sized.baseMint, payer),
            intermediateTokenAccount: walletTokenAccount(mints, sized.intermediateMint, payer),
            // The on-chain assertion is denominated in WSOL, but the base
            // fee, priority fee and tip are paid in native SOL, which the
            // assertion cannot see. Folding them into the bound means a landed
            // transaction is profitable NET, not merely gross — otherwise a
            // MIN_PROFIT set below the cost of a transaction would let the
            // chain happily confirm a losing trade.
            minProfitLamports: costs.onSuccess + config.minProfit,
            computeUnitLimit: provisionalCuLimit,
            computeUnitPriceMicroLamports: cuPrice,
            ...(tip.tipLamports > 0n && sender?.tipAccount()
              ? { tip: { account: sender.tipAccount()!, lamports: tip.tipLamports } }
              : {}),
            createIntermediateAta: true,
            recentBlockhash: blockhash,
            lookupTables: this.lookupTables,
          }),
          lastValidBlockHeight,
        };
      } catch (e) {
        console.warn(`[build] ${describe(e)}`);
        this.reject(sized, "build-failed", detectedAt, freshness);
        return;
      }

      // --- simulate ---------------------------------------------------------
      const decisionAt = Date.now();
      const baseAccount = walletTokenAccount(mints, sized.baseMint, payer);
      const simulation = await simulateCycle({
        rpc: this.deps.rpc,
        transaction: built.transaction,
        baseTokenAccount: baseAccount.toBase58(),
        baseBalanceBefore: this.walletState.baseTokenLamports,
        expectedProfit: sized.grossProfit,
      });

      if (simulation.unitsConsumed !== null) metrics.computeUnits.record(simulation.unitsConsumed);
      if (simulation.divergenceBps !== null) {
        metrics.quoteDivergenceBps.record(simulation.divergenceBps);
        const verdict = killSwitch.onQuoteDivergence(simulation.divergenceBps, Date.now());
        if (verdict !== "ok") {
          console.warn(
            `[quoter] simulation diverged from our quote by ${simulation.divergenceBps.toFixed(2)} bps (${verdict})`,
          );
        }
      }

      if (!simulation.ok) {
        metrics.simulationFailures++;
        // A slippage revert is the assertion doing its job on state that moved,
        // not a bug: the opportunity is simply gone.
        const reason: RejectReason = isSlippageFailure(simulation)
          ? "simulation-unprofitable"
          : "simulation-failed";
        if (reason === "simulation-failed") {
          console.warn(`[simulate] ${simulation.error ?? "unknown error"}`);
        }
        metrics.outcome("simulated-abandoned");
        this.reject(sized, reason, detectedAt, freshness, {
          expectedNet: profit.netProfitIfLanded,
          expectedValue: profit.expectedValue,
          costs,
          landRate,
          computeUnits: simulation.unitsConsumed,
          divergenceBps: simulation.divergenceBps,
        });
        return;
      }

      const cuLimit = computeUnitLimitFrom(
        simulation.unitsConsumed,
        config.computeUnitMarginBps,
        config.maxComputeUnitLimit,
      );
      const finalCosts = computeTransactionCosts({
        cluster,
        numSignatures: 1,
        computeUnitLimit: cuLimit,
        computeUnitPriceMicroLamports: cuPrice,
        tipLamports: tip.tipLamports,
        revertCostsFees,
      });
      const finalProfit = profitNet({
        grossProfit: simulation.simulatedProfit ?? sized.grossProfit,
        costs: finalCosts,
        landRate,
        minProfitLamports: config.minProfit,
        minExpectedValueLamports: config.minExpectedValue,
      });

      // Re-decide on the simulated numbers. There is no "try anyway" branch.
      if (!finalProfit.shouldTrade) {
        metrics.outcome("simulated-abandoned");
        this.reject(sized, finalProfit.reason as RejectReason, detectedAt, freshness, {
          expectedNet: finalProfit.netProfitIfLanded,
          expectedValue: finalProfit.expectedValue,
          costs: finalCosts,
          landRate,
          computeUnits: simulation.unitsConsumed,
          divergenceBps: simulation.divergenceBps,
        });
        return;
      }

      if (config.mode === "paper") {
        metrics.outcome("simulated-abandoned");
        metrics.expectedNetPnl += finalProfit.netProfitIfLanded;
        this.writeAttempt(sized, detectedAt, freshness, {
          outcome: "simulated-abandoned",
          rejectReason: null,
          expectedNet: finalProfit.netProfitIfLanded,
          expectedValue: finalProfit.expectedValue,
          costs: finalCosts,
          landRate,
          computeUnits: simulation.unitsConsumed,
          computeUnitLimit: cuLimit,
          divergenceBps: simulation.divergenceBps,
          decisionLatencyMs: decisionAt - detectedAt,
        });
        return;
      }

      // --- send (live only) -------------------------------------------------
      await this.sendLive({
        sized,
        buyPool,
        sellPool,
        built,
        cuLimit,
        cuPrice,
        tipLamports: tip.tipLamports,
        costs: finalCosts,
        landRate,
        segment,
        detectedAt,
        decisionAt,
        freshness,
        expectedNet: finalProfit.netProfitIfLanded,
        expectedValue: finalProfit.expectedValue,
        computeUnits: simulation.unitsConsumed,
        divergenceBps: simulation.divergenceBps,
      });
    } finally {
      lock.release();
    }
  }

  private async sendLive(a: {
    sized: SizedCycle;
    buyPool: PoolSnapshot;
    sellPool: PoolSnapshot;
    built: { transaction: VersionedTransaction; lastValidBlockHeight: number };
    cuLimit: number;
    cuPrice: bigint;
    tipLamports: bigint;
    costs: ReturnType<typeof computeTransactionCosts>;
    landRate: ReturnType<LandRateEstimator["estimate"]>;
    segment: readonly string[];
    detectedAt: number;
    decisionAt: number;
    freshness: ReturnType<typeof isStateFresh>;
    expectedNet: bigint;
    expectedValue: bigint;
    computeUnits: number | null;
    divergenceBps: number | null;
  }): Promise<void> {
    const { metrics, killSwitch, ledger } = this.deps;
    const wallet = this.deps.wallet;
    const sender = this.deps.sender;
    if (!wallet || !sender) throw new Error("live mode without a wallet or sender");

    this.inFlight++;
    const sendStart = Date.now();
    try {
      a.built.transaction.sign([wallet]);
      const result = await sender.send(a.built.transaction);
      const confirmation = await sender.confirm(result, a.built.lastValidBlockHeight);
      const sendLatency = Date.now() - sendStart;

      const outcome: SendOutcome =
        confirmation.outcome === "success"
          ? "success"
          : confirmation.outcome === "reverted"
            ? "reverted"
            : "notIncluded";
      this.landRate.record(a.segment, outcome);
      killSwitch.onSendOutcome(outcome === "success", Date.now());

      let realised = 0n;
      if (outcome === "success") {
        const before = this.walletState.baseTokenLamports;
        await this.refreshWallet();
        // The WSOL delta is the gross profit; base fee, priority fee and tip
        // all came out of native SOL and must all be subtracted. Subtracting
        // only the tip would overstate realised PnL by the fees on every trade.
        realised = this.walletState.baseTokenLamports - before - a.costs.onSuccess;
        metrics.realisedNetPnl += realised;
        this.addDailyPnl(realised);
        metrics.addPoolPnl(a.sized.buyPoolId, realised);
        metrics.addFamilyPairPnl(`${a.sized.buyFamily}->${a.sized.sellFamily}`, realised);
        metrics.outcome(realised > 0n ? "landed-profitable" : "landed-unprofitable");
        metrics.tipsPaid += a.costs.tip;
        metrics.feesPaid += a.costs.baseFee + a.costs.priorityFee;
        await this.checkResidual(a.sized.intermediateMint, a.sellPool);
      } else if (outcome === "reverted") {
        metrics.outcome("landed-unprofitable");
        metrics.feesPaid += a.costs.onRevert;
        this.addDailyPnl(-a.costs.onRevert);
        realised = -a.costs.onRevert;
      } else {
        metrics.outcome("sent-not-landed");
      }

      metrics.sendLatency.record(sendLatency);
      ledger.writeAttempt(
        this.attemptRecord(a.sized, a.detectedAt, a.freshness, {
          outcome:
            outcome === "success"
              ? realised > 0n
                ? "landed-profitable"
                : "landed-unprofitable"
              : outcome === "reverted"
                ? "landed-unprofitable"
                : "sent-not-landed",
          rejectReason: null,
          expectedNet: a.expectedNet,
          expectedValue: a.expectedValue,
          costs: a.costs,
          landRate: a.landRate,
          computeUnits: a.computeUnits,
          computeUnitLimit: a.cuLimit,
          divergenceBps: a.divergenceBps,
          decisionLatencyMs: a.decisionAt - a.detectedAt,
          sendLatencyMs: sendLatency,
          signature: result.signature,
          landedSlot: confirmation.slot,
          actualProfit: outcome === "success" ? realised : null,
          failureReason: confirmation.error,
        }),
      );
    } catch (e) {
      metrics.outcome("sent-not-landed");
      console.warn(`[send] ${describe(e)}`);
      this.landRate.record(a.segment, "notIncluded");
    } finally {
      this.inFlight--;
    }
  }

  /**
   * After a supposedly residue-free cycle, any leftover intermediate balance
   * means our model of the transaction is wrong. It is never explained away.
   */
  private async checkResidual(mint: string, sellPool: PoolSnapshot): Promise<void> {
    const wallet = this.deps.wallet;
    if (!wallet) return;
    const mints = this.store.mintMap();
    if (!mints.get(mint)) return;
    const account = walletTokenAccount(mints, mint, wallet.publicKey);
    const info = await this.deps.rpc.getAccount(account.toBase58(), RpcPriority.P0_Critical);
    if (!info) return;

    let residualTokens: bigint;
    try {
      residualTokens = decodeTokenAccount(info.data).amount;
    } catch {
      return; // an unreadable account is handled by the next refresh
    }
    if (residualTokens === 0n) return;

    // Value the residue in BASE lamports before comparing it to a lamport
    // threshold. Comparing a raw token amount against a lamport limit is a
    // units error: a six-decimal token would trip the alarm on dust worth
    // nothing, and an eighteen-decimal one would never trip it at all.
    let residualValue = 0n;
    try {
      const quoter = this.quoters.get(sellPool.family);
      if (quoter) {
        residualValue = quoter.quote(
          sellPool,
          residualTokens,
          { inputMint: mint, outputMint: WSOL_MINT },
          {
            mints,
            currentSlot: this.deps.feed.currentSlot(),
            blockTimeSeconds: this.blockTimeSeconds,
          },
        ).amountOut;
      }
    } catch {
      // If the residue cannot be priced we cannot say it is small, so treat it
      // as material rather than as zero.
      residualValue = this.riskLimits.maxTokenExposureLamports + 1n;
    }

    this.walletState.tokenExposureLamports = residualValue;
    const verdict = this.deps.killSwitch.onResidualBalance(residualValue, Date.now());
    if (verdict !== "ok") {
      console.warn(
        `[residual] ${residualTokens} of ${mint} (~${residualValue} lamports) left after a supposedly residue-free cycle (${verdict})`,
      );
    }
  }

  // --- observe-mode survival probing ---------------------------------------

  /**
   * Re-price the same cycle after a series of delays. This is the measurement
   * that answers "would this opportunity have survived our latency?", and it is
   * the single most important output of `--observe`.
   */
  private async probeSurvival(
    sized: SizedCycle,
    buyPool: PoolSnapshot,
    sellPool: PoolSnapshot,
    detectedAt: number,
  ): Promise<void> {
    const survival: { afterMs: number; stillProfitable: boolean; grossProfit: string }[] = [];
    for (const delay of SURVIVAL_PROBES_MS) {
      await sleep(delay - (Date.now() - detectedAt) > 0 ? delay - (Date.now() - detectedAt) : 0);
      if (!this.running) break;
      const fresh = this.store.buildSnapshot(sized.buyPoolId);
      const freshSell = this.store.buildSnapshot(sized.sellPoolId);
      if (!("snapshot" in fresh) || !("snapshot" in freshSell)) {
        survival.push({ afterMs: delay, stillProfitable: false, grossProfit: "0" });
        continue;
      }
      const evaluated = evaluateCycle({
        cycle: sized,
        buyPool: fresh.snapshot,
        sellPool: freshSell.snapshot,
        quoters: this.quoters,
        ctx: {
          mints: this.store.mintMap(),
          currentSlot: this.deps.feed.currentSlot(),
          blockTimeSeconds: this.blockTimeSeconds,
        },
        limits: {
          maxTradeSizeLamports: this.deps.config.maxTradeSize,
          availableCapitalLamports: this.availableCapital(),
          minTradeSizeLamports: this.deps.config.minTradeSize,
        },
        freshness: this.freshnessPolicy(),
        feed: this.feedHealth(),
        nowMs: Date.now(),
      });
      const profitable = Boolean(evaluated.sized && evaluated.sized.grossProfit > 0n);
      survival.push({
        afterMs: delay,
        stillProfitable: profitable,
        grossProfit: (evaluated.sized?.grossProfit ?? 0n).toString(),
      });
    }

    const lifetime = survival.filter((s) => s.stillProfitable).pop()?.afterMs ?? 0;
    this.bumpActivity(sized.buyPoolId, (a) => {
      a.survivalMs.push(lifetime);
      if (lifetime < 200) a.vanishedFast++;
    });

    this.deps.ledger.writeObservation({
      timestamp: detectedAt,
      slot: sized.slot,
      buyPoolId: sized.buyPoolId,
      sellPoolId: sized.sellPoolId,
      intermediateMint: sized.intermediateMint,
      optimalAmountIn: sized.amountIn.toString(),
      grossProfit: sized.grossProfit.toString(),
      netProfit: sized.grossProfit.toString(),
      spreadBps: bpsOf(sized.grossProfit, sized.amountIn),
      survival,
    });
  }

  // --- bookkeeping ----------------------------------------------------------

  private segmentFor(sized: SizedCycle, ageMs: number, now: number): string[] {
    return [
      `${sized.buyPoolId}:${sized.sellPoolId}`,
      `${sized.buyFamily}->${sized.sellFamily}`,
      profitBucket(sized.grossProfit),
      latencyBucket(ageMs),
      hourBucket(now),
    ];
  }

  private recordActivity(sized: SizedCycle, ageMs: number): void {
    this.bumpActivity(sized.buyPoolId, (a) => {
      a.opportunityCount++;
      // Net profit is recorded later, once the cost model has run: scoring on
      // gross would rank an expensive pool as if its fees were free.
      if (sized.legs[0].reserveIn > a.usableDepth) a.usableDepth = sized.legs[0].reserveIn;
    });
    this.deps.metrics.stateAgeSlots.record(sized.slot > 0 ? this.deps.feed.currentSlot() - sized.slot : 0);
    this.deps.metrics.detectionLatency.record(ageMs);
  }

  private bumpActivity(poolId: string, fn: (a: PoolActivity) => void): void {
    let a = this.activity.get(poolId);
    if (!a) {
      a = {
        opportunityCount: 0,
        netProfitableCount: 0,
        netProfitTotal: 0n,
        netProfits: [],
        survivalMs: [],
        vanishedFast: 0,
        quoteErrors: 0,
        usableDepth: 0n,
        firstSeen: Date.now(),
      };
      this.activity.set(poolId, a);
    }
    fn(a);
  }

  private addDailyPnl(delta: bigint): void {
    const key = new Date().toISOString().slice(0, 10);
    if (key !== this.dailyKey) {
      this.dailyKey = key;
      this.dailyRealisedPnl = 0n;
    }
    this.dailyRealisedPnl += delta;
    this.deps.killSwitch.onDailyPnl(this.dailyRealisedPnl, Date.now());
  }

  private async refreshWallet(): Promise<void> {
    const wallet = this.deps.wallet;
    if (!wallet) return;
    const native = await this.deps.rpc.call(RpcPriority.P0_Critical, (c) =>
      c.getBalance(wallet.publicKey),
    );
    this.walletState.nativeLamports = BigInt(native);

    const mints = this.store.mintMap();
    if (mints.get(WSOL_MINT)) {
      const account = walletTokenAccount(mints, WSOL_MINT, wallet.publicKey);
      const info = await this.deps.rpc.getAccount(account.toBase58(), RpcPriority.P0_Critical);
      if (info) {
        try {
          this.walletState.baseTokenLamports = decodeTokenAccount(info.data).amount;
        } catch {
          this.walletState.baseTokenLamports = 0n;
        }
      } else {
        this.walletState.baseTokenLamports = 0n;
      }
    }
  }

  private reject(
    sized: SizedCycle,
    reason: RejectReason,
    detectedAt: number,
    freshness: ReturnType<typeof isStateFresh>,
    extra?: Partial<AttemptExtras>,
  ): void {
    this.deps.metrics.reject(reason);
    this.writeAttempt(sized, detectedAt, freshness, {
      outcome: "not-sent",
      rejectReason: reason,
      expectedNet: extra?.expectedNet ?? 0n,
      expectedValue: extra?.expectedValue ?? 0n,
      costs: extra?.costs ?? null,
      landRate: extra?.landRate ?? null,
      computeUnits: extra?.computeUnits ?? null,
      divergenceBps: extra?.divergenceBps ?? null,
    });
  }

  private writeAttempt(
    sized: SizedCycle,
    detectedAt: number,
    freshness: ReturnType<typeof isStateFresh>,
    extras: AttemptExtras,
  ): void {
    this.deps.ledger.writeAttempt(this.attemptRecord(sized, detectedAt, freshness, extras));
  }

  private attemptRecord(
    sized: SizedCycle,
    detectedAt: number,
    freshness: ReturnType<typeof isStateFresh>,
    e: AttemptExtras,
  ): AttemptRecord {
    const now = Date.now();
    return {
      timestamp: detectedAt,
      slot: sized.slot,
      mode: this.deps.config.mode,
      buyPoolId: sized.buyPoolId,
      sellPoolId: sized.sellPoolId,
      buyFamily: sized.buyFamily,
      sellFamily: sized.sellFamily,
      baseMint: sized.baseMint,
      intermediateMint: sized.intermediateMint,
      amountIn: sized.amountIn.toString(),
      expectedIntermediate: sized.intermediateAmount.toString(),
      expectedAmountOut: sized.amountOut.toString(),
      expectedGrossProfit: sized.grossProfit.toString(),
      expectedNetProfit: (e.expectedNet ?? 0n).toString(),
      expectedValue: (e.expectedValue ?? 0n).toString(),
      actualProfit: e.actualProfit === undefined || e.actualProfit === null ? null : e.actualProfit.toString(),
      computeUnitsSimulated: e.computeUnits ?? null,
      computeUnitLimit: e.computeUnitLimit ?? null,
      priorityFeeLamports: (e.costs?.priorityFee ?? 0n).toString(),
      tipLamports: (e.costs?.tip ?? 0n).toString(),
      baseFeeLamports: (e.costs?.baseFee ?? 0n).toString(),
      stateAgeSlots: freshness.ageSlots,
      stateAgeMs: freshness.ageMs,
      detectionLatencyMs: freshness.ageMs,
      decisionLatencyMs: e.decisionLatencyMs ?? now - detectedAt,
      sendLatencyMs: e.sendLatencyMs ?? null,
      totalLatencyMs: now - detectedAt,
      outcome: e.outcome,
      rejectReason: e.rejectReason,
      failureReason: e.failureReason ?? null,
      signature: e.signature ?? null,
      landedSlot: e.landedSlot ?? null,
      quoteDivergenceBps: e.divergenceBps ?? null,
      landRateUsed: e.landRate?.pSuccess ?? 0,
      landRateSamples: e.landRate?.samples ?? 0,
    };
  }
}

interface AttemptExtras {
  outcome: AttemptRecord["outcome"];
  rejectReason: RejectReason | null;
  expectedNet?: bigint;
  expectedValue?: bigint;
  costs?: ReturnType<typeof computeTransactionCosts> | null;
  landRate?: ReturnType<LandRateEstimator["estimate"]> | null;
  computeUnits?: number | null;
  computeUnitLimit?: number | null;
  divergenceBps?: number | null;
  decisionLatencyMs?: number;
  sendLatencyMs?: number | null;
  signature?: string | null;
  landedSlot?: number | null;
  actualProfit?: bigint | null;
  failureReason?: string | null;
}

/**
 * Stand-in payer for observe and paper mode, so a transaction can be built and
 * simulated without a key ever existing in the process.
 */
const PLACEHOLDER_PAYER = new PublicKey("11111111111111111111111111111112");

function buildFeeProbeMessage(blockhash: string): VersionedMessage {
  // A minimal one-signature message. Its fee is the base fee per signature.
  return MessageV0.compile({
    payerKey: PLACEHOLDER_PAYER,
    instructions: [
      SystemProgram.transfer({
        fromPubkey: PLACEHOLDER_PAYER,
        toPubkey: PLACEHOLDER_PAYER,
        lamports: 1,
      }),
    ],
    recentBlockhash: blockhash,
  });
}

function median(values: readonly number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)]!;
}

function medianBigint(values: readonly bigint[]): bigint {
  if (values.length === 0) return 0n;
  const sorted = [...values].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  return sorted[Math.floor(sorted.length / 2)]!;
}

function bigintMax(a: bigint, b: bigint): bigint {
  return a > b ? a : b;
}

function describe(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
