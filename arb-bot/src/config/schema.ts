/**
 * Configuration.
 *
 * Rule from the brief, enforced here: no economically significant constant is
 * hardcoded (§4). Everything that decides whether we trade — profit floors,
 * staleness bounds, trade caps, tip policy, land-rate priors, screener weights
 * — comes through this schema, so the same binary can be recalibrated from
 * measured data without a code change.
 *
 * Values are parsed into bigints of base units at the edge. Nothing downstream
 * ever sees a string or a float for an amount.
 */
import { z } from "zod";
import { solStringToLamports } from "../util/bigintMath.js";

const lamports = z
  .string()
  .transform((v, ctx) => {
    try {
      return solStringToLamports(v);
    } catch {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: `not a decimal SOL amount: ${v}` });
      return z.NEVER;
    }
  });

const positiveInt = z.coerce.number().int().positive();
const nonNegativeInt = z.coerce.number().int().nonnegative();
const bpsSchema = z.coerce.number().int().min(0).max(10_000);

export const WSOL_MINT = "So11111111111111111111111111111111111111112";

export const ConfigSchema = z.object({
  // --- mode -----------------------------------------------------------------
  mode: z.enum(["observe", "paper", "live", "replay"]),

  // --- connectivity ---------------------------------------------------------
  rpcHttpUrl: z.string().url(),
  rpcWsUrl: z.string().url(),
  commitment: z.enum(["processed", "confirmed", "finalized"]).default("confirmed"),

  // --- RPC budget (§18) -----------------------------------------------------
  rpcRequestsPerSecond: z.coerce.number().positive().default(8),
  rpcBurstCapacity: positiveInt.default(20),
  maxSubscriptions: positiveInt.default(90),

  // --- capital and risk (§28) ----------------------------------------------
  /** WSOL the bot may deploy. */
  maxTradeSize: lamports.default("0.25"),
  /** Ceiling on residual non-base exposure before we stop. */
  maxTokenExposure: lamports.default("0.02"),
  maxInFlightTx: positiveInt.default(1),
  maxDailyLoss: lamports.default("0.15"),
  /** Native SOL never spent, kept for fees. */
  feeReserve: lamports.default("0.02"),
  /** Below this the trade is dust and not worth a transaction. */
  minTradeSize: lamports.default("0.01"),

  // --- profitability bars (§21) --------------------------------------------
  /**
   * Profit we insist on keeping if the transaction lands, on top of every cost.
   *
   * DELIBERATELY CONSERVATIVE and NOT tuned: no data existed when it was set.
   * `npm run report` prints the realised distribution against this bar; lower
   * it only when the data says the bar is leaving money on the table.
   */
  minProfit: lamports.default("0.0008"),
  /** Expected value must clear this, not merely zero, to cover model error. */
  minExpectedValue: lamports.default("0.0002"),

  // --- freshness (§20) ------------------------------------------------------
  maxStateAgeSlots: positiveInt.default(4),
  maxStateAgeMs: positiveInt.default(1_500),
  /** Feed silence longer than this invalidates every quote at once. */
  feedStallMs: positiveInt.default(30_000),

  // --- compute and fees (§17) ----------------------------------------------
  /** Safety margin added to the simulated CU usage. */
  computeUnitMarginBps: bpsSchema.default(2_000),
  /** Hard ceiling so a bad simulation cannot buy a huge CU limit. */
  maxComputeUnitLimit: positiveInt.default(400_000),
  /** Ceiling on the CU price, in micro-lamports per CU. */
  maxComputeUnitPriceMicroLamports: z.coerce.bigint().default(50_000n),

  // --- tip policy (§6) ------------------------------------------------------
  useJito: z.coerce.boolean().default(false),
  jitoBlockEngineUrl: z.string().url().optional(),
  minTip: lamports.default("0.00001"),
  maxTip: lamports.default("0.002"),
  maxTipShareBps: bpsSchema.default(3_000),

  // --- screener (§23, §24) --------------------------------------------------
  maxWatchedPools: positiveInt.default(20),
  screenerIntervalMs: positiveInt.default(60_000),
  screenerEntryMargin: z.coerce.number().nonnegative().default(0.25),
  screenerMinScore: z.coerce.number().default(0.1),
  screenerMinResidencyMs: positiveInt.default(600_000),
  screenerCooldownMs: positiveInt.default(1_800_000),

  // --- token policy (§29) ---------------------------------------------------
  rejectFreezeAuthority: z.coerce.boolean().default(true),
  rejectMintAuthority: z.coerce.boolean().default(false),
  minPoolLiquidity: lamports.default("0.5"),
  minPoolAgeMs: nonNegativeInt.default(600_000),
  blacklistMints: z.string().default(""),
  whitelistMints: z.string().default(""),

  // --- land rate (§16) ------------------------------------------------------
  landRatePriorStrength: z.coerce.number().positive().default(20),
  landRatePriorSuccessShare: z.coerce.number().min(0).max(1).default(0.05),
  landRateMinSamples: positiveInt.default(25),

  // --- execution ------------------------------------------------------------
  /**
   * Slippage tolerance on leg 1, in bps. Zero means the transaction reverts if
   * the first leg returns even one base unit less than quoted. Non-zero trades
   * a lower profit for a higher land rate; see README "leg 1 tolerance".
   */
  leg1ToleranceBps: bpsSchema.default(0),
  /** How long an in-flight opportunity holds its lock before being released. */
  opportunityLockTimeoutMs: positiveInt.default(30_000),

  // --- storage and safety ---------------------------------------------------
  dataDir: z.string().default("./data"),
  walletKeypairPath: z.string().optional(),
  /** Must be literally "true" for --live to start. */
  liveTrading: z.coerce.boolean().default(false),
  /** Second, independent confirmation for --live (§27). */
  liveConfirmation: z.string().default(""),
});

export type Config = z.infer<typeof ConfigSchema>;

const ENV_KEYS: Record<keyof Config, string> = {
  mode: "MODE",
  rpcHttpUrl: "RPC_HTTP_URL",
  rpcWsUrl: "RPC_WS_URL",
  commitment: "COMMITMENT",
  rpcRequestsPerSecond: "RPC_REQUESTS_PER_SECOND",
  rpcBurstCapacity: "RPC_BURST_CAPACITY",
  maxSubscriptions: "MAX_SUBSCRIPTIONS",
  maxTradeSize: "MAX_TRADE_SIZE",
  maxTokenExposure: "MAX_TOKEN_EXPOSURE",
  maxInFlightTx: "MAX_IN_FLIGHT_TX",
  maxDailyLoss: "MAX_DAILY_LOSS",
  feeReserve: "FEE_RESERVE",
  minTradeSize: "MIN_TRADE_SIZE",
  minProfit: "MIN_PROFIT",
  minExpectedValue: "MIN_EXPECTED_VALUE",
  maxStateAgeSlots: "MAX_STATE_AGE_SLOTS",
  maxStateAgeMs: "MAX_STATE_AGE_MS",
  feedStallMs: "FEED_STALL_MS",
  computeUnitMarginBps: "COMPUTE_UNIT_MARGIN_BPS",
  maxComputeUnitLimit: "MAX_COMPUTE_UNIT_LIMIT",
  maxComputeUnitPriceMicroLamports: "MAX_COMPUTE_UNIT_PRICE",
  useJito: "USE_JITO",
  jitoBlockEngineUrl: "JITO_BLOCK_ENGINE_URL",
  minTip: "MIN_TIP",
  maxTip: "MAX_TIP",
  maxTipShareBps: "MAX_TIP_SHARE_BPS",
  maxWatchedPools: "MAX_WATCHED_POOLS",
  screenerIntervalMs: "SCREENER_INTERVAL_MS",
  screenerEntryMargin: "SCREENER_ENTRY_MARGIN",
  screenerMinScore: "SCREENER_MIN_SCORE",
  screenerMinResidencyMs: "SCREENER_MIN_RESIDENCY_MS",
  screenerCooldownMs: "SCREENER_COOLDOWN_MS",
  rejectFreezeAuthority: "REJECT_FREEZE_AUTHORITY",
  rejectMintAuthority: "REJECT_MINT_AUTHORITY",
  minPoolLiquidity: "MIN_POOL_LIQUIDITY",
  minPoolAgeMs: "MIN_POOL_AGE_MS",
  blacklistMints: "BLACKLIST_MINTS",
  whitelistMints: "WHITELIST_MINTS",
  landRatePriorStrength: "LAND_RATE_PRIOR_STRENGTH",
  landRatePriorSuccessShare: "LAND_RATE_PRIOR_SUCCESS_SHARE",
  landRateMinSamples: "LAND_RATE_MIN_SAMPLES",
  leg1ToleranceBps: "LEG1_TOLERANCE_BPS",
  opportunityLockTimeoutMs: "OPPORTUNITY_LOCK_TIMEOUT_MS",
  dataDir: "DATA_DIR",
  walletKeypairPath: "WALLET_KEYPAIR_PATH",
  liveTrading: "LIVE_TRADING",
  liveConfirmation: "LIVE_CONFIRMATION",
};

export class ConfigError extends Error {
  constructor(readonly issues: string[]) {
    super(`invalid configuration:\n  - ${issues.join("\n  - ")}`);
    this.name = "ConfigError";
  }
}

/**
 * Build the config from the environment.
 *
 * Ambiguity is fatal, never defaulted away: `--live` with a missing wallet or a
 * missing confirmation refuses to start rather than starting cautiously (§27).
 */
export function loadConfig(
  mode: Config["mode"],
  env: NodeJS.ProcessEnv = process.env,
): Config {
  const raw: Record<string, unknown> = { mode };
  for (const [key, envName] of Object.entries(ENV_KEYS)) {
    if (key === "mode") continue;
    const v = env[envName];
    if (v !== undefined && v !== "") raw[key] = v;
  }

  const parsed = ConfigSchema.safeParse(raw);
  if (!parsed.success) {
    throw new ConfigError(
      parsed.error.issues.map((i) => `${ENV_KEYS[i.path[0] as keyof Config] ?? i.path.join(".")}: ${i.message}`),
    );
  }
  const config = parsed.data;

  const issues: string[] = [];
  if (config.minTradeSize > config.maxTradeSize) {
    issues.push("MIN_TRADE_SIZE is larger than MAX_TRADE_SIZE");
  }
  if (config.minTip > config.maxTip) {
    issues.push("MIN_TIP is larger than MAX_TIP");
  }
  if (config.useJito && !config.jitoBlockEngineUrl) {
    issues.push("USE_JITO is set but JITO_BLOCK_ENGINE_URL is missing");
  }
  if (config.maxWatchedPools * 3 + 2 > config.maxSubscriptions) {
    issues.push(
      `MAX_WATCHED_POOLS=${config.maxWatchedPools} needs ${config.maxWatchedPools * 3 + 2} subscriptions but MAX_SUBSCRIPTIONS=${config.maxSubscriptions}`,
    );
  }
  if (mode === "live") {
    if (!config.liveTrading) issues.push("LIVE_TRADING must be true to run --live");
    if (config.liveConfirmation !== "I_UNDERSTAND_THIS_SPENDS_REAL_SOL") {
      issues.push(
        'LIVE_CONFIRMATION must be exactly "I_UNDERSTAND_THIS_SPENDS_REAL_SOL" to run --live',
      );
    }
    if (!config.walletKeypairPath) issues.push("WALLET_KEYPAIR_PATH is required for --live");
    if (config.maxDailyLoss <= 0n) issues.push("MAX_DAILY_LOSS must be set for --live");
    if (config.maxTradeSize <= 0n) issues.push("MAX_TRADE_SIZE must be set for --live");
    if (config.minProfit <= 0n) issues.push("MIN_PROFIT must be positive for --live");
  }
  if (issues.length > 0) throw new ConfigError(issues);

  return config;
}

export function parseMintList(value: string): Set<string> {
  return new Set(
    value
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0),
  );
}

/** Redacted view for logs: never print anything derived from a key file. */
export function describeConfig(c: Config): Record<string, string> {
  return {
    mode: c.mode,
    rpcHttpUrl: redactUrl(c.rpcHttpUrl),
    rpcWsUrl: redactUrl(c.rpcWsUrl),
    maxTradeSize: c.maxTradeSize.toString(),
    minProfit: c.minProfit.toString(),
    minExpectedValue: c.minExpectedValue.toString(),
    maxDailyLoss: c.maxDailyLoss.toString(),
    maxStateAgeSlots: String(c.maxStateAgeSlots),
    maxStateAgeMs: String(c.maxStateAgeMs),
    maxWatchedPools: String(c.maxWatchedPools),
    useJito: String(c.useJito),
    walletKeypairPath: c.walletKeypairPath ? "<set>" : "<unset>",
  };
}

/** API keys commonly live in the RPC URL path or query; never log them. */
function redactUrl(url: string): string {
  try {
    const u = new URL(url);
    const host = u.host;
    const hasSecret = u.pathname.length > 1 || u.search.length > 0;
    return `${u.protocol}//${host}${hasSecret ? "/<redacted>" : ""}`;
  } catch {
    return "<unparseable>";
  }
}
