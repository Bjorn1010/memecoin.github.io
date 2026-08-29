import type { StrategyConfig } from "../types.js";

/**
 * Tuned from live paper-trading data (2026-08-29, ~200 trades/strategy): round-trip cost
 * on a 0.15 SOL position is ~11-12% (2% platform fee + ~4% flat priority fee + ~5.5%
 * measured AMM slippage, since Mayhem often enters pools with only ~5 SOL of reserves).
 * The old 10%/10% SL/TP was smaller than that cost floor, so *every* trade — including
 * take-profit "wins" — was net negative. TP is now well above the cost floor so a win is
 * actually a win. They differ on exactly one axis each past that shared fix, so you can
 * tell what's driving the result apart — not four grids of unrelated numbers.
 */
const BASE = {
  startingBalanceSol: 2,
  positionSizeSol: 0.15,
  takeProfitPct: 0.35,
  stopLossPct: 0.12,
  trailingStopPct: null,
  sellOnMayhemFullExit: true,
  priorityFeeSol: 0.003,
  minPoolLiquiditySol: null,
} as const;

export const defaultStrategies: StrategyConfig[] = [
  {
    id: "copy-all",
    name: "Copie tout",
    description: "Copie chaque achat de Mayhem sans filtre. SL -12% / TP +35%.",
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
    description: "N'entre que si Mayhem met plus de 0.05 SOL. SL -12% / TP +35%.",
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
    description: "Comme Copie tout, mais force la sortie après 3 min max. SL -12% / TP +35%.",
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
      "N'entre que si le pool a au moins 10 SOL de réserves au moment du trade — évite le slippage AMM mesuré à 3-5%+ sur les pools les plus fins. SL -12% / TP +35%.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: null,
    minMayhemBuySol: null,
    minPoolLiquiditySol: 10,
    maxConcurrentPositions: 8,
  },
];
