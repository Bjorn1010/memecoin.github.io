import type { StrategyConfig } from "../types.js";

/**
 * Every strategy shares the same, simple risk rule so the numbers mean something:
 * stop loss at -10% (cut it immediately), take profit at +10% (bank it immediately).
 * They differ on exactly one axis each, so you can actually tell what's driving the
 * result apart — not four grids of unrelated numbers.
 */
const BASE = {
  startingBalanceSol: 2,
  positionSizeSol: 0.15,
  takeProfitPct: 0.1,
  stopLossPct: 0.1,
  trailingStopPct: null,
  sellOnMayhemFullExit: true,
  priorityFeeSol: 0.003,
} as const;

export const defaultStrategies: StrategyConfig[] = [
  {
    id: "copy-all",
    name: "Copie tout",
    description: "Copie chaque achat de Mayhem sans filtre. SL -10% / TP +10%.",
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
    description: "N'entre que si Mayhem met plus de 0.05 SOL. SL -10% / TP +10%.",
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
    description: "Comme Copie tout, mais force la sortie après 3 min max. SL -10% / TP +10%.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: 180,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
  {
    id: "no-time-limit",
    name: "Sans limite de temps",
    description: "Comme Copie tout, mais laisse la position vivre tant que SL/TP/dump ne déclenchent pas.",
    kind: "generic",
    enabled: true,
    ...BASE,
    maxHoldSeconds: null,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
];
