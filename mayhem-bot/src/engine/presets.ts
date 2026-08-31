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
 *
 * IMPORTANT — a "+1300%" post-migration result was measured and then found to be an
 * artifact, not alpha. Its entry had been booked at a price read off a bonding curve caught
 * mid-drain at migration (SOL side nearly empty => absurdly low price), then marked against
 * the real DexScreener price: a fabricated ~180x in 11 seconds on an already-migrated (i.e.
 * deep-liquidity) token, which is not physically possible. Entries now wait for a real
 * post-migration market price (see EngineManager.resolveMigrationEntries), and priceFeed no
 * longer falls back to a completed curve's price at all. Treat any pre-fix post-migration
 * number in the DB as invalid.
 *
 * With that corrected, nothing here is known to be profitable yet. The set below is
 * deliberately lean: the three clearly-dead immediate-copy strategies (copy-all,
 * big-buys-only, fast-exit — all down 88%+) are removed, `liquid-only` stays purely as a
 * control so post-migration's numbers can be compared against something, and the
 * post-migration family varies exactly ONE axis per variant (trail width, stop width,
 * position size) so a difference in outcome points at a specific cause. All variants share
 * the same live event stream and the same starting bankroll, so they are directly
 * comparable.
 */
const BASE = {
  startingBalanceSol: 2,
  positionSizeSol: 0.15,
  takeProfitPct: null,
  stopLossPct: 0.12,
  trailingStopPct: 0.25,
  trailingArmPct: 0.5,
  sellOnMayhemFullExit: true,
  // MESURÉ, pas supposé : 40 transactions Mayhem lues on-chain paient toutes exactement
  // 0.000025 SOL de frais. Le modèle facturait 0.003, soit 120x trop. Sur les 364 jambes de
  // liquid-only cela représentait 1.09 SOL de frais fictifs contre 0.009 réels — assez pour
  // ruiner un capital de 2 SOL à lui seul, et donc pour invalider toute conclusion de
  // rentabilité tirée avant cette mesure. Outil de mesure : src/tools/measureFees.ts.
  priorityFeeSol: 0.000025,
  minPoolLiquiditySol: null,
  waitForMigration: false,
  // Every variant deadlocked at 8/8 positions holding tokens Mayhem had abandoned 48-58
  // minutes earlier. On a constant-product curve no trades means no price movement, and
  // every exit here is price-driven, so neither the stop-loss nor the trailing stop can ever
  // fire on a dead token: the slot is held forever and no new entry is possible. That made
  // the variants a race to fill up with dead weight rather than a comparison of exit policy.
  // It also inflated equity, marking positions at the last price of something nobody trades.
  // The forced exit still prices its fill through simulateSell against the last known
  // reserves, so it books the AMM's price impact rather than the stale mark.
  maxHoldSeconds: 600,
} as const;

export const defaultStrategies: StrategyConfig[] = [
  {
    id: "liquid-only",
    name: "Référence (copie immédiate)",
    description:
      "Référence de comparaison. Copie immédiate, uniquement si le pool a au moins 40 SOL de réserves. SL -12% / trailing stop -25% armé à +50%. Les trois variantes ci-dessous ne changent qu'UN paramètre chacune par rapport à celle-ci.",
    kind: "generic",
    enabled: true,
    ...BASE,
    minMayhemBuySol: null,
    minPoolLiquiditySol: 40,
    maxConcurrentPositions: 8,
  },
  {
    id: "copy-pessimistic-fee",
    name: "Temoin frais pessimistes (0.003)",
    description:
      "TÉMOIN. Conserve l'ancienne hypothèse de frais (0.003 SOL/jambe) pendant que toutes les autres utilisent le coût réel mesuré on-chain (0.000025). Sert à chiffrer en continu ce que l'hypothèse erronée coûtait, et à garder une trace de l'erreur plutôt que de l'effacer.",
    kind: "generic",
    enabled: true,
    ...BASE,
    priorityFeeSol: 0.003,
    minPoolLiquiditySol: 40,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
  {
    id: "copy-deeper-pools",
    name: "Pools 250 SOL",
    description:
      "Pousse plus loin le seul axe qui a montré un signal : la profondeur du pool à l'entrée. Sur 67-87 allers-retours par variante, le filtre à 150 SOL perdait 0.0027 SOL par trade contre 0.0060 pour la référence à 40 SOL. Si la tendance tient, 250 SOL doit faire mieux encore ; sinon l'effet plafonne, ce qui est aussi une information. Remplace copy-tight-stop, dont l'hypothèse est réfutée (stop -6% : -0.478 SOL contre -0.489 pour la référence, soit aucun écart).",
    kind: "generic",
    enabled: true,
    ...BASE,
    minMayhemBuySol: null,
    minPoolLiquiditySol: 250,
    maxConcurrentPositions: 8,
  },
  {
    id: "copy-deep-pools",
    name: "Pools très profonds (150 SOL)",
    description:
      "Comme la référence, sauf le seuil de profondeur porté à 150 SOL. Teste si la profondeur du pool à l'entrée, seul filtre de qualité observable, sépare les trades gagnants des perdants.",
    kind: "generic",
    enabled: true,
    ...BASE,
    minMayhemBuySol: null,
    minPoolLiquiditySol: 150,
    maxConcurrentPositions: 8,
  },
  {
    id: "post-migration",
    name: "Après migration (sous observation)",
    description:
      "Conservée uniquement comme sonde. Sur 20 migrations détectées, les pools résultants valaient 1$ à 126$ (médiane ~6$) plusieurs heures après : il n'y a rien de tradable. Ne prendra une position que si un pool dépasse enfin 25000$ de profondeur, ce qui n'est jamais arrivé.",
    kind: "generic",
    enabled: true,
    ...BASE,
    waitForMigration: true,
    minMayhemBuySol: null,
    maxConcurrentPositions: 8,
  },
];
