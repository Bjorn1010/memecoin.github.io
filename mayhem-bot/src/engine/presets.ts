import type { StrategyConfig } from "../types.js";

/**
 * Tuned from a 30-minute live paper-trading run (2026-08-29, 4 strategies, ~9000 Mayhem
 * buy events, 200-250 of our own round trips each). The 4652f8a fix (TP +35%/SL -12% to
 * clear the ~11-12% round-trip cost floor) was necessary but not sufficient: all 4
 * strategies still lost 75-99.9% of their starting 2 SOL bankroll in the window.
 *
 * The reason isn't fees — measured AMM fill slippage over ~1700 trades averaged 0.05%,
 * nowhere near the assumed 5.5% (Mayhem's buys land in deeper pools than expected; the
 * `liquid-only` >=10 SOL filter barely moved the outcome, confirming pool depth wasn't
 * the driver). It's the *shape* of Mayhem's own returns. Reconstructing Mayhem's own
 * buy-to-exit price moves from raw on-chain events (6964 round trips, both tracked
 * wallets): median -47.6%, mean +26.7%. That gap is a lottery-ticket distribution —
 * 70.6% of Mayhem's own trades eventually go below -12%, but the 9.6% that clear +100%
 * contribute more combined return than the other 90.4% put together (672 trades >+100%
 * summed to +4700 percentage points; the entire population summed to +1850). A hard
 * +35% take-profit sells right into that dead zone: it exits before the tail move that
 * is the entire source of edge, while still eating every one of the frequent -12%+
 * losers. That's why every strategy bled out regardless of its own filter axis.
 *
 * Fix: drop the hard take-profit and replace it with a trailing stop that only arms
 * once a position is already in profit (see StrategyRunner.tick — trailing only fires
 * when changePct > 0), so a pump can run to wherever it actually goes while giving back
 * at most trailingStopPct from its peak. Stop-loss stays at -12%: it was doing its job,
 * cutting positions well before the median -47.6% outcome plays out. sellOnMayhemFullExit
 * stays on as the backstop for positions the trailing stop hasn't armed yet.
 */
const BASE = {
  startingBalanceSol: 2,
  positionSizeSol: 0.15,
  takeProfitPct: null,
  stopLossPct: 0.12,
  trailingStopPct: 0.25,
  sellOnMayhemFullExit: true,
  priorityFeeSol: 0.003,
  minPoolLiquiditySol: null,
} as const;

export const defaultStrategies: StrategyConfig[] = [
  {
    id: "copy-all",
    name: "Copie tout",
    description: "Copie chaque achat de Mayhem sans filtre. SL -12% / trailing stop -25% (pas de TP fixe).",
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
    description: "N'entre que si Mayhem met plus de 0.05 SOL. SL -12% / trailing stop -25% (pas de TP fixe).",
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
    description: "Comme Copie tout, mais force la sortie après 3 min max. SL -12% / trailing stop -25%.",
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
      "N'entre que si le pool a au moins 10 SOL de réserves au moment du trade. SL -12% / trailing stop -25% (pas de TP fixe).",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: null,
    minMayhemBuySol: null,
    minPoolLiquiditySol: 10,
    maxConcurrentPositions: 8,
  },
];
