/**
 * Raydium CP-Swap quoter tests.
 *
 * There is no published TypeScript reference implementation to fuzz against the
 * way there is for PumpSwap, so exactness is pinned three ways:
 *  1. hand-computed values derived step by step from the Rust source, with the
 *     arithmetic written out in the comments so a reviewer can re-check it;
 *  2. structural properties the program guarantees (the constant-product
 *     invariant never decreases, output is monotone in input, fees round
 *     against the trader);
 *  3. an opt-in integration test (test/integration/) that compares the quoter
 *     against `simulateTransaction` on live mainnet pools.
 */
import { describe, expect, it } from "vitest";
import {
  CREATOR_FEE_ON_BOTH,
  CREATOR_FEE_ON_TOKEN_1,
  RaydiumCpmmQuoter,
  raydiumEffectiveReserves,
  raydiumIsCreatorFeeOnInput,
  raydiumSwapBaseInput,
  type RaydiumCpmmPoolData,
} from "../../src/quoters/cpmm/raydiumCpmm.js";
import { UnquotableError, type QuoteContext } from "../../src/quoters/Quoter.js";
import type { MintState, PoolSnapshot } from "../../src/types.js";
import { emptyExtensions, TOKEN_PROGRAM_ID } from "../../src/feed/decoder/token2022.js";

const MINT_A = "So11111111111111111111111111111111111111112";
const MINT_B = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

function mint(address: string, decimals: number, supply = 1_000_000_000_000_000n): MintState {
  return {
    address,
    decimals,
    supply,
    programId: TOKEN_PROGRAM_ID,
    mintAuthority: null,
    freezeAuthority: null,
    extensions: emptyExtensions(),
    slot: 100,
    receivedAt: 1_000,
    source: "replay",
  };
}

function ctx(currentSlot = 100, blockTimeSeconds = 1_700_000_000): QuoteContext {
  return {
    mints: new Map([
      [MINT_A, mint(MINT_A, 9)],
      [MINT_B, mint(MINT_B, 6)],
    ]),
    currentSlot,
    blockTimeSeconds,
  };
}

function poolData(over: Partial<RaydiumCpmmPoolData> = {}): RaydiumCpmmPoolData {
  return {
    ammConfig: {
      address: "cfg",
      tradeFeeRate: 2_500n, // 0.25%
      protocolFeeRate: 120_000n,
      fundFeeRate: 40_000n,
      creatorFeeRate: 0n,
    },
    token0Mint: MINT_A,
    token1Mint: MINT_B,
    token0Vault: "vault0",
    token1Vault: "vault1",
    token0Program: TOKEN_PROGRAM_ID,
    token1Program: TOKEN_PROGRAM_ID,
    observationKey: "obs",
    status: 0,
    openTime: 0n,
    creatorFeeOn: CREATOR_FEE_ON_BOTH,
    enableCreatorFee: false,
    vault0Amount: 1_000_000_000n,
    vault1Amount: 2_000_000_000_000n,
    protocolFeesToken0: 0n,
    protocolFeesToken1: 0n,
    fundFeesToken0: 0n,
    fundFeesToken1: 0n,
    creatorFeesToken0: 0n,
    creatorFeesToken1: 0n,
    ...over,
  };
}

function snapshot(data: RaydiumCpmmPoolData, slot = 100): PoolSnapshot {
  return {
    family: "raydium-cpmm",
    poolId: "pool1",
    mintA: data.token0Mint,
    mintB: data.token1Mint,
    slot,
    receivedAt: 1_000,
    source: "replay",
    accounts: ["pool1", data.token0Vault, data.token1Vault],
    data,
  };
}

const q = new RaydiumCpmmQuoter();
const DIR_A_TO_B = { inputMint: MINT_A, outputMint: MINT_B };
const DIR_B_TO_A = { inputMint: MINT_B, outputMint: MINT_A };

describe("effective reserves exclude accrued fees", () => {
  it("subtracts protocol, fund and creator fee counters from the vault balance", () => {
    const d = poolData({
      protocolFeesToken0: 1_000n,
      fundFeesToken0: 500n,
      creatorFeesToken0: 250n,
      protocolFeesToken1: 7n,
      fundFeesToken1: 0n,
      creatorFeesToken1: 3n,
    });
    const r = raydiumEffectiveReserves(d);
    expect(r.reserve0).toBe(1_000_000_000n - 1_750n);
    expect(r.reserve1).toBe(2_000_000_000_000n - 10n);
  });

  it("refuses to quote when the counters exceed the vault balance", () => {
    const d = poolData({ protocolFeesToken0: 2_000_000_000n });
    expect(() => raydiumEffectiveReserves(d)).toThrow(UnquotableError);
  });

  it("materially changes the quote — this is the bug a naive x*y=k has", () => {
    const clean = q.quote(snapshot(poolData()), 1_000_000n, DIR_A_TO_B, ctx());
    const withFees = q.quote(
      snapshot(poolData({ protocolFeesToken1: 100_000_000_000n })),
      1_000_000n,
      DIR_A_TO_B,
      ctx(),
    );
    expect(withFees.amountOut).toBeLessThan(clean.amountOut);
  });
});

describe("creator fee routing", () => {
  it("follows CreatorFeeOn semantics", () => {
    expect(raydiumIsCreatorFeeOnInput(CREATOR_FEE_ON_BOTH, true)).toBe(true);
    expect(raydiumIsCreatorFeeOnInput(CREATOR_FEE_ON_BOTH, false)).toBe(true);
    expect(raydiumIsCreatorFeeOnInput(CREATOR_FEE_ON_TOKEN_1, true)).toBe(false);
    expect(raydiumIsCreatorFeeOnInput(CREATOR_FEE_ON_TOKEN_1, false)).toBe(true);
  });

  it("ignores the config rate when the pool disables the creator fee", () => {
    const disabled = q.quote(
      snapshot(poolData({ enableCreatorFee: false, ammConfig: { ...poolData().ammConfig, creatorFeeRate: 1_000n } })),
      1_000_000n,
      DIR_A_TO_B,
      ctx(),
    );
    const noRate = q.quote(snapshot(poolData()), 1_000_000n, DIR_A_TO_B, ctx());
    expect(disabled.amountOut).toBe(noRate.amountOut);
  });
});

describe("swap_base_input reproduces the on-chain arithmetic", () => {
  // Reserves 1e9 / 2e12, trade_fee_rate 2500 (0.25%), amount_in 1e6.
  //   total_fee = ceil(1e6 * 2500 / 1e6)            = 2500
  //   in_less   = 1e6 - 2500                        = 997500
  //   out       = floor(997500 * 2e12 / (1e9+997500)) = 1993011970
  it("case 1: fee on input, creator fee disabled", () => {
    const r = raydiumSwapBaseInput({
      inputAmount: 1_000_000n,
      inputVaultAmount: 1_000_000_000n,
      outputVaultAmount: 2_000_000_000_000n,
      tradeFeeRate: 2_500n,
      creatorFeeRate: 0n,
      protocolFeeRate: 120_000n,
      fundFeeRate: 40_000n,
      isCreatorFeeOnInput: true,
    });
    expect(r.tradeFee).toBe(2_500n);
    expect(r.inputAmountLessFees).toBe(997_500n);
    expect(r.outputAmount).toBe(1_993_011_970n);
    // protocol/fund fees are floor shares OF THE TRADE FEE, not of the input.
    expect(r.protocolFee).toBe(300n);
    expect(r.fundFee).toBe(100n);
    expect(r.creatorFee).toBe(0n);
  });

  // creator_fee_rate 1000 charged on the OUTPUT side:
  //   out_swapped = 1993011970
  //   creator_fee = ceil(1993011970 * 1000 / 1e6) = 1993012
  //   output      = 1993011970 - 1993012          = 1991018958
  it("case 2: creator fee charged on the output, with a ceiling", () => {
    const r = raydiumSwapBaseInput({
      inputAmount: 1_000_000n,
      inputVaultAmount: 1_000_000_000n,
      outputVaultAmount: 2_000_000_000_000n,
      tradeFeeRate: 2_500n,
      creatorFeeRate: 1_000n,
      protocolFeeRate: 120_000n,
      fundFeeRate: 40_000n,
      isCreatorFeeOnInput: false,
    });
    expect(r.tradeFee).toBe(2_500n);
    expect(r.creatorFee).toBe(1_993_012n);
    expect(r.outputAmount).toBe(1_991_018_958n);
  });

  // creator fee on the INPUT side is taken from a combined ceiling, then split
  // off with a floor:
  //   total   = ceil(1e6 * 3500 / 1e6)      = 3500
  //   creator = floor(3500 * 1000 / 3500)   = 1000
  //   trade   = 3500 - 1000                 = 2500
  //   out     = floor(996500 * 2e12 / (1e9+996500)) = 1991015952
  it("case 3: creator fee charged on the input, split with a floor", () => {
    const r = raydiumSwapBaseInput({
      inputAmount: 1_000_000n,
      inputVaultAmount: 1_000_000_000n,
      outputVaultAmount: 2_000_000_000_000n,
      tradeFeeRate: 2_500n,
      creatorFeeRate: 1_000n,
      protocolFeeRate: 120_000n,
      fundFeeRate: 40_000n,
      isCreatorFeeOnInput: true,
    });
    expect(r.creatorFee).toBe(1_000n);
    expect(r.tradeFee).toBe(2_500n);
    expect(r.outputAmount).toBe(1_991_015_952n);
  });

  it("rounds the trade fee UP, never down", () => {
    // 1 base unit at 2500/1e6 is a fee of 0.0025 -> must round to 1, not 0.
    const r = raydiumSwapBaseInput({
      inputAmount: 1n,
      inputVaultAmount: 1_000_000_000n,
      outputVaultAmount: 2_000_000_000_000n,
      tradeFeeRate: 2_500n,
      creatorFeeRate: 0n,
      protocolFeeRate: 0n,
      fundFeeRate: 0n,
      isCreatorFeeOnInput: false,
    });
    expect(r.tradeFee).toBe(1n);
    expect(r.inputAmountLessFees).toBe(0n);
    expect(r.outputAmount).toBe(0n);
  });
});

describe("quoter guards", () => {
  it("rejects a pool with the swap status bit set", () => {
    expect(() => q.quote(snapshot(poolData({ status: 4 })), 1_000n, DIR_A_TO_B, ctx())).toThrow(
      /swap disabled/,
    );
  });

  it("rejects a pool that has not opened yet", () => {
    expect(() =>
      q.quote(snapshot(poolData({ openTime: 9_999_999_999n })), 1_000n, DIR_A_TO_B, ctx()),
    ).toThrow(/not reached/);
  });

  it("rejects a mint that is not in the pool", () => {
    expect(() =>
      q.quote(snapshot(poolData()), 1_000n, { inputMint: "other", outputMint: MINT_B }, ctx()),
    ).toThrow(/not in pool/);
  });

  it("rejects a non-positive amount", () => {
    expect(() => q.quote(snapshot(poolData()), 0n, DIR_A_TO_B, ctx())).toThrow(/must be > 0/);
  });

  it("accepts a pool whose swap bit is clear but other bits are set", () => {
    // status 3 = deposit+withdraw disabled, swap still enabled.
    expect(() => q.quote(snapshot(poolData({ status: 3 })), 1_000n, DIR_A_TO_B, ctx())).not.toThrow();
  });
});

describe("structural properties the program guarantees", () => {
  it("output is non-decreasing in input", () => {
    const s = snapshot(poolData());
    let previous = 0n;
    for (let a = 1_000n; a <= 100_000_000n; a *= 3n) {
      const out = q.quote(s, a, DIR_A_TO_B, ctx()).amountOut;
      expect(out).toBeGreaterThanOrEqual(previous);
      previous = out;
    }
  });

  it("never lets the constant product decrease (the program asserts this)", () => {
    const d = poolData();
    const { reserve0, reserve1 } = raydiumEffectiveReserves(d);
    for (let a = 1n; a <= 10_000_000n; a *= 7n) {
      const r = raydiumSwapBaseInput({
        inputAmount: a,
        inputVaultAmount: reserve0,
        outputVaultAmount: reserve1,
        tradeFeeRate: d.ammConfig.tradeFeeRate,
        creatorFeeRate: 0n,
        protocolFeeRate: d.ammConfig.protocolFeeRate,
        fundFeeRate: d.ammConfig.fundFeeRate,
        isCreatorFeeOnInput: true,
      });
      const before = reserve0 * reserve1;
      const after = (reserve0 + r.inputAmountLessFees) * (reserve1 - r.outputAmount);
      expect(after).toBeGreaterThanOrEqual(before);
    }
  });

  it("is symmetric in direction: both sides quote and both charge a fee", () => {
    const s = snapshot(poolData());
    const ab = q.quote(s, 1_000_000n, DIR_A_TO_B, ctx());
    const ba = q.quote(s, 1_000_000_000n, DIR_B_TO_A, ctx());
    expect(ab.amountOut).toBeGreaterThan(0n);
    expect(ba.amountOut).toBeGreaterThan(0n);
    expect(ab.fees.inInputToken).toBeGreaterThan(0n);
    expect(ba.fees.inInputToken).toBeGreaterThan(0n);
    expect(ab.reserveIn).toBe(1_000_000_000n);
    expect(ba.reserveIn).toBe(2_000_000_000_000n);
  });

  it("reports the accounts that must stay subscribed", () => {
    expect(q.requiredAccounts(snapshot(poolData()))).toEqual(["pool1", "vault0", "vault1"]);
  });
});

describe("Token-2022 transfer fees are applied on both sides", () => {
  function ctxWithTransferFee(bps: number): QuoteContext {
    const b = mint(MINT_B, 6);
    b.extensions = { ...b.extensions, transferFee: { basisPoints: bps, maximumFee: 10n ** 18n } };
    return {
      mints: new Map([
        [MINT_A, mint(MINT_A, 9)],
        [MINT_B, b],
      ]),
      currentSlot: 100,
      blockTimeSeconds: 1_700_000_000,
    };
  }

  it("reduces the credited output when the OUTPUT mint charges a fee", () => {
    const s = snapshot(poolData());
    const clean = q.quote(s, 1_000_000n, DIR_A_TO_B, ctx());
    const taxed = q.quote(s, 1_000_000n, DIR_A_TO_B, ctxWithTransferFee(100));
    // 1% of 1993011970 = 19930120, rounded up.
    expect(clean.amountOut - taxed.amountOut).toBe(19_930_120n);
    expect(taxed.fees.breakdown.outputTransferFee).toBe(19_930_120n);
  });

  it("reduces the amount that reaches the curve when the INPUT mint charges a fee", () => {
    const s = snapshot(poolData());
    const taxed = q.quote(s, 1_000_000_000n, DIR_B_TO_A, ctxWithTransferFee(100));
    expect(taxed.fees.breakdown.inputTransferFee).toBe(10_000_000n);
  });
});
