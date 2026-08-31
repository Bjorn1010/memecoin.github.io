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
  // free key at console.groq.com. Verified live against the account's actual /v1/models
  // list on 2026-08-31 — Groq's lineup turns over fast (llama-3.3-70b-versatile, the
  // obvious pick from training-era docs, was already gone/404). Tried groq/compound-mini
  // next (its own rate-limit headers advertised 70000 tokens/min) but it's an
  // orchestrator that silently routes each call through llama-3.3-70b AND gpt-oss-120b
  // (see its usage_breakdown) — those two only get 12000 / 8000 tokens/min each on this
  // account, so real throughput was actually worse, not better. openai/gpt-oss-120b
  // called directly avoids the double-dip: one sub-model, one budget, ~1800 tokens/call
  // measured live against the real system prompt -> roughly 4 decisions/min sustainable
  // on the free tier (see maxDecisionCallsPerMinute below, tuned to match).
  groqApiKey: process.env.GROQ_API_KEY ?? null,
  model: process.env.ALX_MODEL ?? "openai/gpt-oss-120b",

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
  // openai/gpt-oss-120b's free tier gives 8000 tokens/min. A 20-minute live run measured
  // real per-call cost at 2100-2500 tokens (higher than the ~1800 first estimated,
  // because reasoning length scales with how many red flags the model finds) — 4/min
  // still 429'd repeatedly (4 x ~2400 > 8000). 3/min (x ~2500 = 7500) leaves margin.
  // On pump.fun's real firehose, far more than 3/min will cross the eligibility
  // threshold — most get skipped, which is the honest tradeoff of a free-tier bot, not
  // a bug. Raise this only after moving to Groq's paid Dev Tier, or a bigger-budget model.
  maxDecisionCallsPerMinute: Number(process.env.ALX_MAX_DECISIONS_PER_MINUTE ?? 3),
  inactiveTokenPruneMs: Number(process.env.ALX_INACTIVE_PRUNE_MS ?? 15 * 60_000),

  // Independent safety net — never fully delegate risk control to the LLM's own
  // judgment. Checked every tick regardless of what the agent last decided.
  hardStopLossPct: Number(process.env.ALX_HARD_STOP_LOSS_PCT ?? 0.5),
  maxHoldSeconds: Number(process.env.ALX_MAX_HOLD_SECONDS ?? 30 * 60),

  trackedWallets: parseTrackedWallets(process.env.ALX_TRACKED_WALLETS),

  memoryFilePath: process.env.ALX_MEMORY_FILE ?? "./data/alx-agent-memory.json",
  memoryMaxEntries: Number(process.env.ALX_MEMORY_MAX_ENTRIES ?? 50),
};
