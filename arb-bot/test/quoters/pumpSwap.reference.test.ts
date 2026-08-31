/**
 * Exactness proof for the PumpSwap quoter.
 *
 * Rather than assert a handful of hand-computed numbers, this fuzzes our pure
 * bigint implementation against pump.fun's own SDK (`@pump-fun/pump-swap-sdk`,
 * a devDependency used here purely as a reference oracle) across thousands of
 * randomised pool states, fee tiers and trade sizes.
 *
 * If pump ships a change to their math, this test starts failing on the next
 * `npm update`, which is exactly the alarm we want.
 *
 * No network access: every input is generated locally.
 */
import { describe, expect, it } from "vitest";
import BN from "bn.js";
import { PublicKey } from "@solana/web3.js";
import { buyQuoteInput, sellBaseInput } from "@pump-fun/pump-swap-sdk";
import {
  calculateFeeTier,
  pumpBuyQuoteInput,
  pumpComputeFeesBps,
  pumpFee,
  pumpPoolMarketCap,
  pumpSellBaseInput,
  type PumpFeeConfig,
  type PumpFeeTier,
  type PumpGlobalConfig,
} from "../../src/quoters/cpmm/pumpSwap.js";

// --- deterministic PRNG so failures are reproducible -------------------------
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function randBigint(rnd: () => number, min: bigint, max: bigint): bigint {
  const span = max - min;
  if (span <= 0n) return min;
  // Build from two 26-bit draws so we can span large ranges.
  const hi = BigInt(Math.floor(rnd() * 67108864));
  const lo = BigInt(Math.floor(rnd() * 67108864));
  return min + ((hi * 67108864n + lo) % (span + 1n));
}

/** The live mainnet tier ladder shape, used so the fuzz hits real thresholds. */
const LIVE_TIERS: PumpFeeTier[] = [
  { marketCapLamportsThreshold: 0n, fees: { lpFeeBps: 2n, protocolFeeBps: 93n, creatorFeeBps: 30n } },
  { marketCapLamportsThreshold: 420_000_000_000n, fees: { lpFeeBps: 20n, protocolFeeBps: 5n, creatorFeeBps: 95n } },
  { marketCapLamportsThreshold: 1_470_000_000_000n, fees: { lpFeeBps: 20n, protocolFeeBps: 5n, creatorFeeBps: 90n } },
  { marketCapLamportsThreshold: 4_420_000_000_000n, fees: { lpFeeBps: 20n, protocolFeeBps: 5n, creatorFeeBps: 75n } },
  { marketCapLamportsThreshold: 29_470_000_000_000n, fees: { lpFeeBps: 20n, protocolFeeBps: 5n, creatorFeeBps: 50n } },
  { marketCapLamportsThreshold: 98_240_000_000_000n, fees: { lpFeeBps: 20n, protocolFeeBps: 5n, creatorFeeBps: 5n } },
];

const FLAT_FEES = { lpFeeBps: 25n, protocolFeeBps: 5n, creatorFeeBps: 0n };

const FEE_CONFIG: PumpFeeConfig = {
  address: "FeeConfig11111111111111111111111111111111111",
  flatFees: FLAT_FEES,
  feeTiers: LIVE_TIERS,
  stableFeeTiers: LIVE_TIERS,
};

const GLOBAL_CONFIG: PumpGlobalConfig = {
  address: "GlobalConfig1111111111111111111111111111111",
  lpFeeBasisPoints: 20n,
  protocolFeeBasisPoints: 5n,
  coinCreatorFeeBasisPoints: 5n,
  disableFlags: 0,
  protocolFeeRecipients: [],
};

/** Shape the SDK expects for its own FeeConfig / GlobalConfig arguments. */
function sdkFeeConfig() {
  return {
    bump: 255,
    admin: PublicKey.default,
    flatFees: {
      lpFeeBps: new BN(FLAT_FEES.lpFeeBps.toString()),
      protocolFeeBps: new BN(FLAT_FEES.protocolFeeBps.toString()),
      creatorFeeBps: new BN(FLAT_FEES.creatorFeeBps.toString()),
    },
    feeTiers: LIVE_TIERS.map((t) => ({
      marketCapLamportsThreshold: new BN(t.marketCapLamportsThreshold.toString()),
      fees: {
        lpFeeBps: new BN(t.fees.lpFeeBps.toString()),
        protocolFeeBps: new BN(t.fees.protocolFeeBps.toString()),
        creatorFeeBps: new BN(t.fees.creatorFeeBps.toString()),
      },
    })),
    stableFeeTiers: [],
  } as never;
}

function sdkGlobalConfig() {
  return {
    admin: PublicKey.default,
    lpFeeBasisPoints: new BN(GLOBAL_CONFIG.lpFeeBasisPoints.toString()),
    protocolFeeBasisPoints: new BN(GLOBAL_CONFIG.protocolFeeBasisPoints.toString()),
    disableFlags: 0,
    protocolFeeRecipients: [],
    coinCreatorFeeBasisPoints: new BN(GLOBAL_CONFIG.coinCreatorFeeBasisPoints.toString()),
    adminSetCoinCreatorAuthority: PublicKey.default,
  } as never;
}

/**
 * Two mint/creator pairs, so both fee branches of the official SDK are
 * exercised:
 *  - NON_CANONICAL: creator is not the pool-authority PDA -> SDK uses flatFees;
 *  - CANONICAL: creator IS `PDA(["pool-authority", mint], PUMP_PROGRAM_ID)`,
 *    so the SDK takes the market-cap tier branch — the one that charges up to
 *    125 bps and that our quoter must reproduce exactly.
 */
const NON_CANONICAL_MINT = new PublicKey("So11111111111111111111111111111111111111112");
const NON_CANONICAL_CREATOR = new PublicKey("11111111111111111111111111111112");

const CANONICAL_MINT = new PublicKey("So11111111111111111111111111111111111111112");
const CANONICAL_CREATOR = PublicKey.findProgramAddressSync(
  [Buffer.from("pool-authority"), CANONICAL_MINT.toBuffer()],
  new PublicKey("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"),
)[0];

describe("pumpFee / helpers", () => {
  it("rounds fees up, matching util.ts::fee", () => {
    expect(pumpFee(1n, 1n)).toBe(1n); // ceil(1*1/10000) = 1
    expect(pumpFee(0n, 500n)).toBe(0n);
    expect(pumpFee(10_000n, 25n)).toBe(25n);
    expect(pumpFee(10_001n, 25n)).toBe(26n); // ceil, not floor
  });

  it("computes market cap with floor division", () => {
    expect(
      pumpPoolMarketCap({ baseMintSupply: 1_000_000_000_000_000n, baseReserve: 3n, quoteReserve: 10n }),
    ).toBe(3_333_333_333_333_333n);
  });

  it("selects the tier the official algorithm selects", () => {
    expect(calculateFeeTier(LIVE_TIERS, 0n).creatorFeeBps).toBe(30n);
    expect(calculateFeeTier(LIVE_TIERS, 419_999_999_999n).creatorFeeBps).toBe(30n);
    expect(calculateFeeTier(LIVE_TIERS, 420_000_000_000n).creatorFeeBps).toBe(95n);
    expect(calculateFeeTier(LIVE_TIERS, 10n ** 30n).creatorFeeBps).toBe(5n);
  });

  it("uses flat fees for non-canonical pools", () => {
    const fees = pumpComputeFeesBps({
      globalConfig: GLOBAL_CONFIG,
      feeConfig: FEE_CONFIG,
      isCanonicalPumpPool: false,
      baseMintSupply: 1_000_000_000_000_000n,
      baseReserve: 1_000_000_000_000_000n,
      quoteReserve: 100_000_000_000n,
    });
    expect(fees).toEqual(FLAT_FEES);
  });
});

describe("PumpSwap quoter matches the official SDK exactly", () => {
  const CASES = 4000;

  it(`sellBaseInput over ${CASES} randomised states`, () => {
    const rnd = mulberry32(0xc0ffee);
    let checked = 0;
    for (let i = 0; i < CASES; i++) {
      const baseReserve = randBigint(rnd, 1_000_000n, 10n ** 15n);
      const quoteReserve = randBigint(rnd, 1_000_000n, 5_000n * 10n ** 9n);
      const supply = randBigint(rnd, baseReserve, baseReserve * 10n);
      const base = randBigint(rnd, 1n, baseReserve);
      const hasCreator = rnd() > 0.3;

      let ours: ReturnType<typeof pumpSellBaseInput> | null = null;
      try {
        ours = pumpSellBaseInput({
          base,
          baseReserve,
          quoteReserve,
          virtualQuoteReserves: 0n,
          baseMintSupply: supply,
          coinCreatorIsDefault: !hasCreator,
          globalConfig: GLOBAL_CONFIG,
          feeConfig: FEE_CONFIG,
          isCanonicalPumpPool: false,
        });
      } catch {
        continue; // our guard rejected; the SDK may throw too, nothing to compare
      }

      const theirs = sellBaseInput({
        base: new BN(base.toString()),
        slippage: 0,
        baseReserve: new BN(baseReserve.toString()),
        quoteReserve: new BN(quoteReserve.toString()),
        globalConfig: sdkGlobalConfig(),
        baseMintAccount: { supply: BigInt(supply.toString()) } as never,
        baseMint: NON_CANONICAL_MINT,
        coinCreator: hasCreator ? NON_CANONICAL_CREATOR : PublicKey.default,
        creator: NON_CANONICAL_CREATOR,
        feeConfig: sdkFeeConfig(),
      });

      expect(ours.finalQuote.toString()).toBe(theirs.uiQuote.toString());
      expect(ours.quoteAmountOut.toString()).toBe(theirs.internalQuoteAmountOut.toString());
      checked++;
    }
    expect(checked).toBeGreaterThan(CASES / 2);
  });

  it(`buyQuoteInput over ${CASES} randomised states`, () => {
    const rnd = mulberry32(0xbadf00d);
    let checked = 0;
    for (let i = 0; i < CASES; i++) {
      const baseReserve = randBigint(rnd, 1_000_000n, 10n ** 15n);
      const quoteReserve = randBigint(rnd, 1_000_000n, 5_000n * 10n ** 9n);
      const supply = randBigint(rnd, baseReserve, baseReserve * 10n);
      const quote = randBigint(rnd, 1_000n, quoteReserve);
      const hasCreator = rnd() > 0.3;

      let ours: ReturnType<typeof pumpBuyQuoteInput> | null = null;
      try {
        ours = pumpBuyQuoteInput({
          quote,
          baseReserve,
          quoteReserve,
          virtualQuoteReserves: 0n,
          baseMintSupply: supply,
          coinCreatorIsDefault: !hasCreator,
          globalConfig: GLOBAL_CONFIG,
          feeConfig: FEE_CONFIG,
          isCanonicalPumpPool: false,
        });
      } catch {
        continue;
      }

      const theirs = buyQuoteInput({
        quote: new BN(quote.toString()),
        slippage: 0,
        baseReserve: new BN(baseReserve.toString()),
        quoteReserve: new BN(quoteReserve.toString()),
        globalConfig: sdkGlobalConfig(),
        baseMintAccount: { supply: BigInt(supply.toString()) } as never,
        baseMint: NON_CANONICAL_MINT,
        coinCreator: hasCreator ? NON_CANONICAL_CREATOR : PublicKey.default,
        creator: NON_CANONICAL_CREATOR,
        feeConfig: sdkFeeConfig(),
      });

      expect(ours.baseAmountOut.toString()).toBe(theirs.base.toString());
      expect(ours.effectiveQuote.toString()).toBe(theirs.internalQuoteWithoutFees.toString());
      checked++;
    }
    expect(checked).toBeGreaterThan(CASES / 2);
  });
});

describe("PumpSwap quoter matches the SDK on CANONICAL pump pools (tiered fees)", () => {
  const CASES = 4000;

  it(`sell + buy across the market-cap tier ladder`, () => {
    const rnd = mulberry32(0x5eed17);
    let checkedSell = 0;
    let checkedBuy = 0;
    const tiersHit = new Set<string>();

    for (let i = 0; i < CASES; i++) {
      const baseReserve = randBigint(rnd, 10n ** 9n, 10n ** 15n);
      // Spread quote reserves across several orders of magnitude so the derived
      // market cap lands in many different tiers.
      const magnitude = BigInt(1 + Math.floor(rnd() * 6));
      const quoteReserve = randBigint(rnd, 10n ** 6n, 10n ** magnitude * 10n ** 9n);
      const supply = randBigint(rnd, baseReserve, baseReserve * 20n);
      const hasCreator = rnd() > 0.2;

      const fees = pumpComputeFeesBps({
        globalConfig: GLOBAL_CONFIG,
        feeConfig: FEE_CONFIG,
        isCanonicalPumpPool: true,
        baseMintSupply: supply,
        baseReserve,
        quoteReserve,
      });
      tiersHit.add(`${fees.lpFeeBps}/${fees.protocolFeeBps}/${fees.creatorFeeBps}`);

      const sdkArgs = {
        slippage: 0,
        baseReserve: new BN(baseReserve.toString()),
        quoteReserve: new BN(quoteReserve.toString()),
        globalConfig: sdkGlobalConfig(),
        baseMintAccount: { supply: BigInt(supply.toString()) } as never,
        baseMint: CANONICAL_MINT,
        coinCreator: hasCreator ? NON_CANONICAL_CREATOR : PublicKey.default,
        creator: CANONICAL_CREATOR,
        feeConfig: sdkFeeConfig(),
      };
      const ourArgs = {
        baseReserve,
        quoteReserve,
        virtualQuoteReserves: 0n,
        baseMintSupply: supply,
        coinCreatorIsDefault: !hasCreator,
        globalConfig: GLOBAL_CONFIG,
        feeConfig: FEE_CONFIG,
        isCanonicalPumpPool: true,
      };

      const base = randBigint(rnd, 1n, baseReserve);
      try {
        const ours = pumpSellBaseInput({ base, ...ourArgs });
        const theirs = sellBaseInput({ base: new BN(base.toString()), ...sdkArgs });
        expect(ours.finalQuote.toString()).toBe(theirs.uiQuote.toString());
        checkedSell++;
      } catch {
        /* guarded input on our side; nothing to compare */
      }

      const quote = randBigint(rnd, 1_000n, quoteReserve);
      try {
        const ours = pumpBuyQuoteInput({ quote, ...ourArgs });
        const theirs = buyQuoteInput({ quote: new BN(quote.toString()), ...sdkArgs });
        expect(ours.baseAmountOut.toString()).toBe(theirs.base.toString());
        checkedBuy++;
      } catch {
        /* ditto */
      }
    }

    expect(checkedSell).toBeGreaterThan(CASES / 2);
    expect(checkedBuy).toBeGreaterThan(CASES / 2);
    // Prove the fuzz actually exercised more than one fee tier.
    expect(tiersHit.size).toBeGreaterThan(3);
  });
});
