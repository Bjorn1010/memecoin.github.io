import { describe, expect, it } from "vitest";
import {
  DEFAULT_TOKEN_POLICY,
  checkMint,
  summariseVerdict,
} from "../../src/risk/tokenFilters.js";
import { checkLimits, tradableCapital, type RiskLimits, type WalletSnapshot } from "../../src/risk/limits.js";
import { KillSwitch, DEFAULT_KILL_SWITCH_THRESHOLDS } from "../../src/risk/killSwitch.js";
import { isStateFresh, worstFreshness } from "../../src/search/freshness.js";
import {
  ExtensionId,
  TOKEN_2022_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  emptyExtensions,
} from "../../src/feed/decoder/token2022.js";
import type { MintState } from "../../src/types.js";

function mint(over: Partial<MintState> = {}): MintState {
  return {
    address: "Mint1111111111111111111111111111111111111111",
    decimals: 6,
    supply: 1_000_000_000_000_000n,
    programId: TOKEN_PROGRAM_ID,
    mintAuthority: null,
    freezeAuthority: null,
    extensions: emptyExtensions(),
    slot: 100,
    receivedAt: 1_000,
    source: "rpc",
    ...over,
  };
}

describe("token filters reject what we cannot price exactly (§29)", () => {
  it("accepts a plain, revoked SPL mint", () => {
    const v = checkMint(mint());
    expect(v.accepted).toBe(true);
    expect(summariseVerdict(v)).toBe("accepted");
  });

  it("rejects a transfer fee", () => {
    const v = checkMint(
      mint({
        programId: TOKEN_2022_PROGRAM_ID,
        extensions: {
          ...emptyExtensions(),
          present: [ExtensionId.TransferFeeConfig],
          transferFee: { basisPoints: 100, maximumFee: 10n ** 18n },
        },
      }),
    );
    expect(v.accepted).toBe(false);
    expect(v.rejections.map((r) => r.code)).toContain("transfer-fee");
  });

  it("rejects a transfer hook", () => {
    const v = checkMint(
      mint({
        programId: TOKEN_2022_PROGRAM_ID,
        extensions: { ...emptyExtensions(), present: [ExtensionId.TransferHook], hasTransferHook: true },
      }),
    );
    expect(v.rejections.map((r) => r.code)).toContain("transfer-hook");
  });

  it("rejects a permanent delegate, which could seize our balance", () => {
    const v = checkMint(
      mint({
        programId: TOKEN_2022_PROGRAM_ID,
        extensions: {
          ...emptyExtensions(),
          present: [ExtensionId.PermanentDelegate],
          hasPermanentDelegate: true,
        },
      }),
    );
    expect(v.rejections.map((r) => r.code)).toContain("permanent-delegate");
  });

  it("rejects a live freeze authority under the default policy", () => {
    const v = checkMint(mint({ freezeAuthority: "Freeze1111111111111111111111111111111111111" }));
    expect(v.rejections.map((r) => r.code)).toContain("freeze-authority");
  });

  it("allows a freeze authority when the operator explicitly opts in", () => {
    const v = checkMint(
      mint({ freezeAuthority: "Freeze1111111111111111111111111111111111111" }),
      { ...DEFAULT_TOKEN_POLICY, rejectFreezeAuthority: false },
    );
    expect(v.accepted).toBe(true);
  });

  it("fails CLOSED on an extension it has never heard of", () => {
    const v = checkMint(
      mint({
        programId: TOKEN_2022_PROGRAM_ID,
        extensions: { ...emptyExtensions(), present: [9999] },
      }),
    );
    expect(v.accepted).toBe(false);
    expect(v.rejections.map((r) => r.code)).toContain("unrecognised-extension");
  });

  it("allows purely cosmetic extensions", () => {
    const v = checkMint(
      mint({
        programId: TOKEN_2022_PROGRAM_ID,
        extensions: {
          ...emptyExtensions(),
          present: [ExtensionId.MetadataPointer, ExtensionId.TokenMetadata],
        },
      }),
    );
    expect(v.accepted).toBe(true);
  });

  it("rejects thin liquidity and brand-new pools", () => {
    const thin = checkMint(mint(), DEFAULT_TOKEN_POLICY, { poolLiquidityLamports: 1_000n });
    expect(thin.rejections.map((r) => r.code)).toContain("insufficient-liquidity");
    const young = checkMint(mint(), DEFAULT_TOKEN_POLICY, { poolAgeMs: 5_000 });
    expect(young.rejections.map((r) => r.code)).toContain("pool-too-young");
  });

  it("honours the blacklist and the whitelist", () => {
    const black = checkMint(mint(), { ...DEFAULT_TOKEN_POLICY, blacklist: new Set([mint().address]) });
    expect(black.rejections.map((r) => r.code)).toContain("blacklisted");
    const notWhite = checkMint(mint(), { ...DEFAULT_TOKEN_POLICY, whitelist: new Set(["other"]) });
    expect(notWhite.rejections.map((r) => r.code)).toContain("not-whitelisted");
  });

  it("reports every reason, not just the first", () => {
    const v = checkMint(
      mint({
        programId: TOKEN_2022_PROGRAM_ID,
        freezeAuthority: "F1111111111111111111111111111111111111111111",
        extensions: {
          ...emptyExtensions(),
          present: [ExtensionId.TransferFeeConfig, ExtensionId.TransferHook],
          transferFee: { basisPoints: 50, maximumFee: 1_000n },
          hasTransferHook: true,
        },
      }),
    );
    expect(v.rejections.length).toBeGreaterThanOrEqual(3);
  });
});

describe("hard limits", () => {
  const limits: RiskLimits = {
    maxTradeSizeLamports: 1_000_000_000n,
    maxTokenExposureLamports: 50_000_000n,
    maxInFlightTx: 1,
    maxDailyLossLamports: 150_000_000n,
    reserveLamports: 20_000_000n,
  };
  const wallet: WalletSnapshot = {
    nativeLamports: 100_000_000n,
    baseTokenLamports: 2_000_000_000n,
    tokenExposureLamports: 0n,
    inFlightTx: 0,
  };
  const base = { limits, wallet, amountIn: 500_000_000n, costOnSuccess: 60_000n, dailyRealisedPnl: 0n };

  it("allows a trade inside every limit", () => {
    expect(checkLimits(base).allowed).toBe(true);
  });

  it("blocks once the daily loss limit is reached", () => {
    const v = checkLimits({ ...base, dailyRealisedPnl: -150_000_000n });
    expect(v.allowed).toBe(false);
    expect(v.reason).toBe("kill-switch");
  });

  it("blocks a second concurrent transaction", () => {
    const v = checkLimits({ ...base, wallet: { ...wallet, inFlightTx: 1 } });
    expect(v.allowed).toBe(false);
    expect(v.detail).toMatch(/in flight/);
  });

  it("blocks a trade above MAX_TRADE_SIZE", () => {
    const v = checkLimits({ ...base, amountIn: 2_000_000_000n });
    expect(v.allowed).toBe(false);
    expect(v.detail).toMatch(/MAX_TRADE_SIZE/);
  });

  it("blocks when residual token exposure is over the ceiling", () => {
    const v = checkLimits({ ...base, wallet: { ...wallet, tokenExposureLamports: 60_000_000n } });
    expect(v.allowed).toBe(false);
    expect(v.detail).toMatch(/exposure/);
  });

  it("blocks when the native SOL reserve would be breached", () => {
    const v = checkLimits({ ...base, wallet: { ...wallet, nativeLamports: 20_010_000n } });
    expect(v.allowed).toBe(false);
    expect(v.detail).toMatch(/reserve/);
  });

  it("caps tradable capital at the smaller of balance and MAX_TRADE_SIZE", () => {
    expect(tradableCapital(wallet, limits)).toBe(1_000_000_000n);
    expect(tradableCapital({ ...wallet, baseTokenLamports: 10n }, limits)).toBe(10n);
  });
});

describe("kill switch", () => {
  it("trips on the daily loss limit and stays tripped", () => {
    const k = new KillSwitch();
    k.onDailyPnl(-150_000_000n, 1);
    expect(k.tripped).toBe(true);
    expect(k.snapshot().trigger).toBe("daily-loss");
    // Nothing short of an explicit reset clears it, not even a winning day.
    k.onDailyPnl(1_000_000_000n, 2);
    expect(k.tripped).toBe(true);
  });

  it("keeps the FIRST trigger when several conditions fire", () => {
    const k = new KillSwitch();
    k.onDailyPnl(-200_000_000n, 1);
    k.trip("manual", "operator", 2);
    expect(k.snapshot().trigger).toBe("daily-loss");
  });

  it("warns on one residual balance and stops on a recurring one", () => {
    const k = new KillSwitch();
    expect(k.onResidualBalance(1_000n, 1)).toBe("ok");
    expect(k.onResidualBalance(50_000_000n, 2)).toBe("alert");
    expect(k.onResidualBalance(50_000_000n, 3)).toBe("alert");
    expect(k.onResidualBalance(50_000_000n, 4)).toBe("tripped");
    expect(k.tripped).toBe(true);
  });

  it("stops trading when the quoter keeps disagreeing with simulation", () => {
    const k = new KillSwitch();
    expect(k.onQuoteDivergence(5, 1)).toBe("ok");
    for (let i = 0; i < 2; i++) expect(k.onQuoteDivergence(100, i + 2)).toBe("alert");
    expect(k.onQuoteDivergence(100, 5)).toBe("tripped");
  });

  it("resets its consecutive-failure counter on any success", () => {
    const k = new KillSwitch();
    for (let i = 0; i < DEFAULT_KILL_SWITCH_THRESHOLDS.maxConsecutiveFailures - 1; i++) {
      k.onSendOutcome(false, i);
    }
    expect(k.tripped).toBe(false);
    k.onSendOutcome(true, 100);
    expect(k.counters().consecutiveFailures).toBe(0);
    expect(k.tripped).toBe(false);
  });

  it("survives a restart through persistence", () => {
    let saved: ReturnType<KillSwitch["snapshot"]> | null = null;
    const persistence = {
      load: () => saved,
      save: (s: ReturnType<KillSwitch["snapshot"]>) => {
        saved = s;
      },
    };
    const first = new KillSwitch(DEFAULT_KILL_SWITCH_THRESHOLDS, persistence);
    first.trip("manual", "stop", 42);
    const afterRestart = new KillSwitch(DEFAULT_KILL_SWITCH_THRESHOLDS, persistence);
    expect(afterRestart.tripped).toBe(true);
    expect(afterRestart.snapshot().detail).toBe("stop");
  });

  it("only clears on an explicit reset", () => {
    const k = new KillSwitch();
    k.trip("manual", "stop", 1);
    k.reset();
    expect(k.tripped).toBe(false);
  });
});

describe("state freshness (§20)", () => {
  const policy = { maxStateAgeSlots: 3, maxStateAgeMs: 500 };

  it("accepts fresh state", () => {
    const v = isStateFresh({ slot: 100, receivedAt: 1_000 }, 101, 1_200, policy);
    expect(v.fresh).toBe(true);
    expect(v.reason).toBeNull();
  });

  it("rejects state that is too many slots old", () => {
    const v = isStateFresh({ slot: 100, receivedAt: 1_000 }, 110, 1_100, policy);
    expect(v.fresh).toBe(false);
    expect(v.reason).toBe("slot-age");
  });

  it("rejects state that is fresh by slot but stale by wall clock", () => {
    // A stalled process: the slot number we last saw is close, but that was
    // seconds ago and the world has moved on.
    const v = isStateFresh({ slot: 100, receivedAt: 1_000 }, 101, 9_000, policy);
    expect(v.fresh).toBe(false);
    expect(v.reason).toBe("wall-age");
  });

  it("flags, but does not reject, state ahead of our slot tracker", () => {
    const v = isStateFresh({ slot: 200, receivedAt: 1_000 }, 100, 1_100, policy);
    expect(v.fresh).toBe(true);
    expect(v.reason).toBe("future-slot");
  });

  it("takes the worst of several accounts", () => {
    const v = worstFreshness(
      [
        { slot: 100, receivedAt: 1_000 },
        { slot: 90, receivedAt: 1_000 },
      ],
      101,
      1_100,
      policy,
    );
    expect(v.fresh).toBe(false);
    expect(v.ageSlots).toBe(11);
  });
});
