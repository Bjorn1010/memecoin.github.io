import "dotenv/config";

function parseTrackedWallets(raw: string | undefined): Array<{ address: string; label: string }> {
  if (!raw) {
    // Default: alxcooks's own wallet, confirmed via his verified pump.fun profile
    // (see conversation — pump.fun/profile/alxcooks, on-chain buy verified on 2026-08-31).
    return [{ address: "89HbgWduLwoxcofWpmn1EiF9wEdpgkNDEyPjzZ72mkDi", label: "alxcooks" }];
  }
  return raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [address, label] = entry.split(":");
      return { address: address.trim(), label: (label ?? address).trim() };
    });
}

/**
 * Config for the alxcooks-style AI reasoning agent. Fully separate from the main
 * mayhem-bot config (../config.ts) — this agent watches ALL new pump.fun tokens,
 * not just a fixed set of copied wallets, and decides via LLM calls instead of
 * fixed TP/SL rules.
 */
export const aiConfig = {
  // Groq: OpenAI-compatible endpoint, genuinely free tier (no card required), and fast
  // enough for a scalping use case — matters more here than for a one-off query. Get a
  // free key at console.groq.com. llama-3.3-70b-versatile is the best-reasoning free
  // model as of 2026-08; swap to llama-3.1-8b-instant via ALX_MODEL for a much higher
  // daily quota (14 400 req/day vs a few hundred) if 70b's free-tier limit gets tight.
  groqApiKey: process.env.GROQ_API_KEY ?? null,
  model: process.env.ALX_MODEL ?? "llama-3.3-70b-versatile",

  startingBalanceSol: Number(process.env.ALX_STARTING_BALANCE_SOL ?? 2),
  positionSizeSol: Number(process.env.ALX_POSITION_SIZE_SOL ?? 0.1),
  maxConcurrentPositions: Number(process.env.ALX_MAX_CONCURRENT_POSITIONS ?? 5),
  priorityFeeSol: Number(process.env.ALX_PRIORITY_FEE_SOL ?? 0.003),

  // Discovery/decision gating — avoids burning LLM calls on brand-new, no-data tokens
  // or re-asking on every single trade tick for the same mint.
  maxWatchedTokens: Number(process.env.ALX_MAX_WATCHED_TOKENS ?? 40),
  minTokenAgeSecondsBeforeDecision: Number(process.env.ALX_MIN_TOKEN_AGE_SECONDS ?? 15),
  minTradesBeforeDecision: Number(process.env.ALX_MIN_TRADES_BEFORE_DECISION ?? 5),
  decisionCooldownMs: Number(process.env.ALX_DECISION_COOLDOWN_MS ?? 20_000),
  inactiveTokenPruneMs: Number(process.env.ALX_INACTIVE_PRUNE_MS ?? 15 * 60_000),

  // Independent safety net — never fully delegate risk control to the LLM's own
  // judgment. Checked every tick regardless of what the agent last decided.
  hardStopLossPct: Number(process.env.ALX_HARD_STOP_LOSS_PCT ?? 0.5),
  maxHoldSeconds: Number(process.env.ALX_MAX_HOLD_SECONDS ?? 30 * 60),

  trackedWallets: parseTrackedWallets(process.env.ALX_TRACKED_WALLETS),

  memoryFilePath: process.env.ALX_MEMORY_FILE ?? "./data/alx-agent-memory.json",
  memoryMaxEntries: Number(process.env.ALX_MEMORY_MAX_ENTRIES ?? 50),
};
