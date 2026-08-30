import type { StrategyConfig } from "../types.js";

/**
 * Tuned from a 30-minute live paper-trading run (2026-08-29, 4 strategies, ~9000 Mayhem
 * buy events, 200-250 of our own round trips each). The 4652f8a fix (TP +35%/SL -12% to
 * clear the ~11-12% round-trip cost floor) was necessary but not sufficient: all 4
 * strategies still lost 75-99.9% of their starting 2 SOL bankroll in the window.
 *
 * The reason isn't fees — measured AMM fill slippage over ~1700 trades averaged 0.05%,
 * nowhere near the assumed 5.5%. It's the *shape* of Mayhem's own returns. Reconstructing
 * Mayhem's own buy-to-exit price moves from raw on-chain events (6964 round trips, both
 * tracked wallets): median -47.6%, mean +26.7%. That gap is a lottery-ticket distribution —
 * 70.6% of Mayhem's own trades eventually go below -12%, but the 9.6% that clear +100%
 * contribute more combined return than the other 90.4% put together (672 trades >+100%
 * summed to +4700 percentage points; the entire population summed to +1850). A hard
 * +35% take-profit sells right into that dead zone: it exits before the tail move that
 * is the entire source of edge, while still eating every one of the frequent -12%+
 * losers. That's why every strategy bled out regardless of its own filter axis.
 *
 * Two more rounds after that fix (event-driven exits instead of 2.5s polling; a
 * post-migration-entry strategy) confirmed the exit side was already about as good as it
 * gets — realized stop-loss went from -30/-45% to -16/-24% against a -12% nominal, and a
 * single measured migration barely dented its 2 SOL bankroll — but every immediate-entry
 * strategy was still deeply negative. Two more changes, both aimed at the two things that
 * still didn't match the lottery-ticket shape:
 *
 * 1. trailingArmPct: the trailing stop used to arm on ANY profit at all (changePct > 0),
 *    meaning a real pump got sold on its first ordinary pullback before it had a chance to
 *    become one of the tail winners the whole strategy depends on. It now only arms once a
 *    position has been up 50%+ at its peak — past the point where a normal winner
 *    (+35-65% was the old average) would've already been forced out — while a move that
 *    never gets there still exits on the unchanged -12% stop-loss.
 * 2. `liquid-only`'s pool-depth floor was 10 SOL — below Mayhem's own median entry reserves
 *    (~16 SOL), so it barely filtered anything. Raised to 40 SOL, meaningfully above that
 *    median, to actually test whether avoiding the thinnest pools (where a single trade can
 *    move price 20-50%) helps, at the cost of far fewer qualifying entries.
 */
const BASE = {
  startingBalanceSol: 2,
  positionSizeSol: 0.15,
  takeProfitPct: null,
  stopLossPct: 0.12,
  trailingStopPct: 0.25,
  trailingArmPct: 0.5,
  sellOnMayhemFullExit: true,
  priorityFeeSol: 0.003,
  minPoolLiquiditySol: null,
  waitForMigration: false,
} as const;

export const defaultStrategies: StrategyConfig[] = [
  {
    id: "copy-all",
    name: "Copie tout",
    description: "Copie chaque achat de Mayhem sans filtre. SL -12% / trailing stop -25% armé à partir de +50%.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: null,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
  {
    id: "big-buys-only",
    name: "Grosses convictions",
    description: "N'entre que si Mayhem met plus de 0.05 SOL. SL -12% / trailing stop -25% armé à partir de +50%.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: null,
    minMayhemBuySol: 0.05,
    maxConcurrentPositions: 6,
  },
  {
    id: "fast-exit",
    name: "Sortie rapide",
    description: "Comme Copie tout, mais force la sortie après 3 min max. SL -12% / trailing stop -25% armé à partir de +50%.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 180,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
  {
    id: "liquid-only",
    name: "Pools liquides seulement",
    description:
      "N'entre que si le pool a au moins 40 SOL de réserves au moment du trade (bien au-dessus de la médiane ~16 SOL de Mayhem). SL -12% / trailing stop -25% armé à partir de +50%.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: null,
    minMayhemBuySol: null,
    minPoolLiquiditySol: 40,
    maxConcurrentPositions: 8,
  },
  {
    id: "post-migration",
    name: "Après migration seulement",
    description:
      "N'achète jamais sur la bonding curve : surveille les mints que Mayhem achète et n'entre qu'une fois le token migré vers un vrai pool AMM (liquidité bien plus profonde que les ~16 SOL médians que Mayhem snipe). SL -12% / trailing stop -25% armé à partir de +50%. La plupart des tokens ne migrent jamais — attends-toi à beaucoup moins de trades que les 4 autres stratégies.",
    kind: "generic",
    enabled: true,
    ...BASE,
    waitForMigration: true,
    maxHoldSeconds: null,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
];
