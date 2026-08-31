/**
 * Transaction construction tests.
 *
 * The two things that matter here and cannot be checked by reading:
 *  1. the profit assertion is actually encoded in the instruction data, with
 *    the right bound, in the right argument slot;
 *  2. the transaction FITS. A Raydium+PumpSwap cycle touches around thirty
 *     accounts, and Solana's 1232-byte limit is roughly thirty-two account keys
 *     plus overhead, so "does it fit" is a real question with a real answer
 *     rather than a formality.
 */
import { describe, expect, it } from "vitest";
import { AddressLookupTableAccount, Keypair, PublicKey } from "@solana/web3.js";
import {
  MAX_TRANSACTION_BYTES,
  buildArbitrageCycle,
  CycleBuildError,
} from "../../src/exec/transactionBuilder.js";
import {
  PUMP_BUY_DISC,
  PUMP_SELL_DISC,
  RAYDIUM_SWAP_BASE_INPUT_DISC,
  RAYDIUM_SWAP_BASE_OUTPUT_DISC,
} from "../../src/exec/instructions.js";
import type { MintState, PoolSnapshot, SizedCycle, QuoteResult } from "../../src/types.js";
import { emptyExtensions, TOKEN_PROGRAM_ID } from "../../src/feed/decoder/token2022.js";
import { CREATOR_FEE_ON_BOTH, type RaydiumCpmmPoolData } from "../../src/quoters/cpmm/raydiumCpmm.js";
import type { PumpSwapPoolData } from "../../src/quoters/cpmm/pumpSwap.js";
import { staticLookupAddresses } from "../../src/exec/lookupTable.js";

const WSOL = "So11111111111111111111111111111111111111112";
const TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const BLOCKHASH = "GfVcyD4kkTrj4bKc7WA9sZCin9JDbdT4Zkd3EittNR1W";
const PAYER = Keypair.generate().publicKey;

function mint(address: string): MintState {
  return {
    address,
    decimals: 6,
    supply: 1_000_000_000_000_000n,
    programId: TOKEN_PROGRAM_ID,
    mintAuthority: null,
    freezeAuthority: null,
    extensions: emptyExtensions(),
    slot: 1,
    receivedAt: 1,
    source: "replay",
  };
}

const MINTS = new Map([
  [WSOL, mint(WSOL)],
  [TOKEN, mint(TOKEN)],
]);

function key(): string {
  return Keypair.generate().publicKey.toBase58();
}

function raydiumPool(poolId: string): PoolSnapshot {
  const data: RaydiumCpmmPoolData = {
    ammConfig: {
      address: key(),
      tradeFeeRate: 2_500n,
      protocolFeeRate: 120_000n,
      fundFeeRate: 40_000n,
      creatorFeeRate: 0n,
    },
    token0Mint: WSOL,
    token1Mint: TOKEN,
    token0Vault: key(),
    token1Vault: key(),
    token0Program: TOKEN_PROGRAM_ID,
    token1Program: TOKEN_PROGRAM_ID,
    observationKey: key(),
    status: 0,
    openTime: 0n,
    creatorFeeOn: CREATOR_FEE_ON_BOTH,
    enableCreatorFee: false,
    vault0Amount: 1_000_000_000_000n,
    vault1Amount: 2_000_000_000_000n,
    protocolFeesToken0: 0n,
    protocolFeesToken1: 0n,
    fundFeesToken0: 0n,
    fundFeesToken1: 0n,
    creatorFeesToken0: 0n,
    creatorFeesToken1: 0n,
  };
  return {
    family: "raydium-cpmm",
    poolId,
    mintA: WSOL,
    mintB: TOKEN,
    slot: 1,
    receivedAt: 1,
    source: "replay",
    accounts: [poolId],
    subscribed: true,
    data,
  };
}

function pumpPool(poolId: string, over: Partial<PumpSwapPoolData> = {}): PoolSnapshot {
  const data: PumpSwapPoolData = {
    creator: key(),
    coinCreator: key(),
    baseMint: TOKEN,
    quoteMint: WSOL,
    poolBaseTokenAccount: key(),
    poolQuoteTokenAccount: key(),
    baseTokenProgram: TOKEN_PROGRAM_ID,
    quoteTokenProgram: TOKEN_PROGRAM_ID,
    isMayhemMode: false,
    virtualQuoteReserves: 0n,
    poolBaseAmount: 2_000_000_000_000n,
    poolQuoteAmount: 1_000_000_000_000n,
    isCanonicalPumpPool: true,
    globalConfig: {
      address: key(),
      lpFeeBasisPoints: 20n,
      protocolFeeBasisPoints: 5n,
      coinCreatorFeeBasisPoints: 5n,
      disableFlags: 0,
      protocolFeeRecipients: [key(), key()],
    },
    feeConfig: null,
    ...over,
  };
  return {
    family: "pump-swap",
    poolId,
    mintA: TOKEN,
    mintB: WSOL,
    slot: 1,
    receivedAt: 1,
    source: "replay",
    accounts: [poolId],
    subscribed: true,
    data,
  };
}

function leg(): QuoteResult {
  return {
    family: "raydium-cpmm",
    poolId: "p",
    direction: { inputMint: WSOL, outputMint: TOKEN },
    amountIn: 1n,
    amountOut: 1n,
    fees: { inInputToken: 0n, inOutputToken: 0n, breakdown: {} },
    reserveIn: 1n,
    reserveOut: 1n,
    slot: 1,
    receivedAt: 1,
    exactness: "exact",
    maxAmountIn: 1n,
  };
}

function cycle(buyPoolId: string, sellPoolId: string, buyFamily: PoolSnapshot["family"], sellFamily: PoolSnapshot["family"]): SizedCycle {
  return {
    baseMint: WSOL,
    intermediateMint: TOKEN,
    buyPoolId,
    buyFamily,
    sellPoolId,
    sellFamily,
    amountIn: 100_000_000n,
    intermediateAmount: 199_000_000n,
    amountOut: 100_500_000n,
    grossProfit: 500_000n,
    slot: 1,
    receivedAt: 1,
    legs: [leg(), leg()],
  };
}

/**
 * A lookup table covering every static address plus both pools' accounts —
 * what `npm run setup` produces, modelled locally so the size effect can be
 * tested without a network.
 */
function tableCovering(...pools: PoolSnapshot[]): AddressLookupTableAccount {
  const addresses = [...staticLookupAddresses(PAYER)];
  for (const p of pools) {
    if (p.family === "raydium-cpmm") {
      const d = p.data as RaydiumCpmmPoolData;
      addresses.push(
        new PublicKey(p.poolId),
        new PublicKey(d.token0Vault),
        new PublicKey(d.token1Vault),
        new PublicKey(d.ammConfig.address),
        new PublicKey(d.observationKey),
      );
    } else {
      const d = p.data as PumpSwapPoolData;
      addresses.push(
        new PublicKey(p.poolId),
        new PublicKey(d.poolBaseTokenAccount),
        new PublicKey(d.poolQuoteTokenAccount),
        new PublicKey(d.coinCreator),
        ...d.globalConfig.protocolFeeRecipients.map((r) => new PublicKey(r)),
      );
    }
  }
  return new AddressLookupTableAccount({
    key: new PublicKey(key()),
    state: {
      deactivationSlot: 2n ** 64n - 1n,
      lastExtendedSlot: 0,
      lastExtendedSlotStartIndex: 0,
      addresses,
    },
  });
}

function build(
  buyPool: PoolSnapshot,
  sellPool: PoolSnapshot,
  minProfit = 10_000n,
  lookupTables: AddressLookupTableAccount[] = [],
) {
  return buildArbitrageCycle({
    lookupTables,
    sized: cycle(buyPool.poolId, sellPool.poolId, buyPool.family, sellPool.family),
    buyPool,
    sellPool,
    mints: MINTS,
    payer: PAYER,
    baseTokenAccount: new PublicKey(key()),
    intermediateTokenAccount: new PublicKey(key()),
    minProfitLamports: minProfit,
    computeUnitLimit: 250_000,
    computeUnitPriceMicroLamports: 10_000n,
    createIntermediateAta: true,
    recentBlockhash: BLOCKHASH,
  });
}

describe("the profit assertion is encoded on-chain", () => {
  it("bounds leg 2's minimum output at the input plus the profit floor", () => {
    const built = build(raydiumPool(key()), pumpPool(key()));
    expect(built.minimumOutLamports).toBe(100_000_000n + 10_000n);
    expect(built.maximumInLamports).toBe(100_000_000n);

    // Find the pump `sell` instruction and read its second argument back out.
    const message = built.transaction.message;
    const sell = message.compiledInstructions.find((ix) =>
      Buffer.from(ix.data).subarray(0, 8).equals(PUMP_SELL_DISC),
    );
    expect(sell).toBeDefined();
    const data = Buffer.from(sell!.data);
    expect(data.readBigUInt64LE(8)).toBe(199_000_000n); // exact base in
    expect(data.readBigUInt64LE(16)).toBe(100_010_000n); // min quote out
  });

  it("asks leg 1 for an exact intermediate amount with a capped spend", () => {
    const built = build(raydiumPool(key()), pumpPool(key()));
    const buy = built.transaction.message.compiledInstructions.find((ix) =>
      Buffer.from(ix.data).subarray(0, 8).equals(RAYDIUM_SWAP_BASE_OUTPUT_DISC),
    );
    expect(buy).toBeDefined();
    const data = Buffer.from(buy!.data);
    // swap_base_output takes max_amount_in FIRST, then amount_out.
    expect(data.readBigUInt64LE(8)).toBe(100_000_000n);
    expect(data.readBigUInt64LE(16)).toBe(199_000_000n);
  });

  it("uses pump `buy` for leg 1 and Raydium `swap_base_input` for leg 2 in the other direction", () => {
    // Needs the lookup table: this direction is the oversized one.
    const buy = pumpPool(key());
    const sell = raydiumPool(key());
    const built = build(buy, sell, 10_000n, [tableCovering(buy, sell)]);
    const discs = built.transaction.message.compiledInstructions.map((ix) =>
      Buffer.from(ix.data).subarray(0, 8).toString("hex"),
    );
    expect(discs).toContain(PUMP_BUY_DISC.toString("hex"));
    expect(discs).toContain(RAYDIUM_SWAP_BASE_INPUT_DISC.toString("hex"));
  });

  it("sells exactly what leg 1 buys, so the cycle leaves no residue", () => {
    const built = build(raydiumPool(key()), pumpPool(key()));
    expect(built.intermediateAmount).toBe(199_000_000n);
  });
});

describe("transaction size, the constraint that decides what is buildable", () => {
  it("a Raydium -> Raydium cycle fits comfortably", () => {
    const built = build(raydiumPool(key()), raydiumPool(key()));
    expect(built.serializedBytes).toBeLessThan(MAX_TRANSACTION_BYTES);
  });

  it("reports the real serialized size, signature included", () => {
    const built = build(raydiumPool(key()), raydiumPool(key()));
    // Sanity: a two-swap transaction is not tiny and not absurd.
    expect(built.serializedBytes).toBeGreaterThan(400);
    expect(built.accountCount).toBeGreaterThan(15);
  });

  it("a mixed-venue cycle does NOT fit without a lookup table", () => {
    // Measured, not assumed: PumpSwap's 23 accounts plus Raydium's overflow the
    // 1232-byte limit. This is why the lookup table is a requirement rather
    // than an optimisation, and why the builder must refuse loudly instead of
    // letting the transaction be rejected at send time.
    expect(() => build(pumpPool(key()), raydiumPool(key()))).toThrow(CycleBuildError);
    try {
      build(pumpPool(key()), raydiumPool(key()));
    } catch (e) {
      expect((e as Error).message).toMatch(/over the 1232 limit/);
      expect((e as Error).message).toMatch(/lookup table/);
    }
  });

  it("and DOES fit with one — this is what makes cross-venue arbitrage possible", () => {
    const buy = pumpPool(key());
    const sell = raydiumPool(key());
    const built = build(buy, sell, 10_000n, [tableCovering(buy, sell)]);
    expect(built.serializedBytes).toBeLessThan(MAX_TRANSACTION_BYTES);
  });
});

describe("the builder refuses what it cannot price or address correctly", () => {
  it("refuses a pump pool in mayhem mode, whose fee recipients we do not model", () => {
    expect(() => build(raydiumPool(key()), pumpPool(key(), { isMayhemMode: true }))).toThrow(
      /mayhem mode/,
    );
  });

  it("refuses a cycle whose two legs are the same pool", () => {
    const pool = raydiumPool(key());
    expect(() =>
      buildArbitrageCycle({
        sized: cycle(pool.poolId, pool.poolId, "raydium-cpmm", "raydium-cpmm"),
        buyPool: pool,
        sellPool: pool,
        mints: MINTS,
        payer: PAYER,
        baseTokenAccount: new PublicKey(key()),
        intermediateTokenAccount: new PublicKey(key()),
        minProfitLamports: 1n,
        computeUnitLimit: 200_000,
        computeUnitPriceMicroLamports: 0n,
        createIntermediateAta: false,
        recentBlockhash: BLOCKHASH,
      }),
    ).toThrow(/same pool/);
  });

  it("refuses a pump pool that does not pair the mints the cycle needs", () => {
    const wrong = pumpPool(key(), { baseMint: key(), quoteMint: key() });
    expect(() => build(raydiumPool(key()), wrong)).toThrow(CycleBuildError);
  });
});
