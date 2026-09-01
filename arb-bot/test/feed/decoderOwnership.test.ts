/**
 * Account decoders must verify the OWNING PROGRAM, not just the discriminator.
 *
 * An Anchor account discriminator is `sha256("account:<TypeName>")[0..8]`. It
 * is derived from the type's NAME and nothing else, so every program that
 * defines an account called `PoolState` emits byte-for-byte identical leading
 * bytes. Two unrelated programs colliding is not bad luck, it is the default.
 *
 * This is not hypothetical. While verifying quoters against live mainnet
 * traffic, account `HrWp3QR3hNeVy6tEZtcpsjwEiGgKJuL1NDP84EaaU2Nh` — 1544 bytes,
 * owned by program `REALQqNEomY6cQGZJUGwywTBD2UmDT32rZcNnfxQ5N2`, nothing to do
 * with Raydium — opened with Raydium's exact PoolState discriminator and
 * decoded cleanly into fabricated reserves, mints and vault addresses. The
 * symptom that exposed it was an `amm_config` pointer at an address that does
 * not exist on chain.
 *
 * Left unfixed, a foreign account can be registered as a pool, quoted against,
 * and paired into a cycle that looks profitable because its reserves are
 * invented. These tests make sure that fails at the decoder.
 */
import { describe, expect, it } from "vitest";
import {
  DecodeError,
  RAYDIUM_AMM_CONFIG_DISCRIMINATOR,
  RAYDIUM_CPMM_PROGRAM_ID,
  RAYDIUM_POOL_STATE_DISCRIMINATOR,
  RAYDIUM_POOL_STATE_LEN,
  decodeRaydiumAmmConfig,
  decodeRaydiumPoolState,
} from "../../src/feed/decoder/raydiumCpmm.js";
import {
  PUMP_FEE_CONFIG_DISCRIMINATOR,
  PUMP_FEE_PROGRAM_ID,
  PUMP_GLOBAL_CONFIG_DISCRIMINATOR,
  PUMP_POOL_DISCRIMINATOR,
  PUMP_SWAP_PROGRAM_ID,
  decodePumpFeeConfig,
  decodePumpGlobalConfig,
  decodePumpPool,
} from "../../src/feed/decoder/pumpSwap.js";
import {
  TOKEN_2022_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  decodeTokenAccount,
} from "../../src/feed/decoder/token2022.js";
import { eventPayloadsFromLogs } from "../../src/feed/decoder/events.js";

/** The program that actually owns the colliding mainnet account. */
const FOREIGN_PROGRAM = "REALQqNEomY6cQGZJUGwywTBD2UmDT32rZcNnfxQ5N2";

function accountWith(discriminator: Buffer, length: number): Buffer {
  const data = Buffer.alloc(length);
  discriminator.copy(data, 0);
  return data;
}

describe("a discriminator match from a foreign program is refused", () => {
  it("Raydium PoolState: the exact mainnet collision that was found", () => {
    // Same discriminator, same shape as the real offender (1544 bytes).
    const impostor = accountWith(RAYDIUM_POOL_STATE_DISCRIMINATOR, 1544);
    expect(() => decodeRaydiumPoolState(impostor, FOREIGN_PROGRAM)).toThrow(DecodeError);
    expect(() => decodeRaydiumPoolState(impostor, FOREIGN_PROGRAM)).toThrow(/owned by/);
  });

  it("Raydium PoolState: the same bytes decode when the owner is right", () => {
    const genuine = accountWith(RAYDIUM_POOL_STATE_DISCRIMINATOR, RAYDIUM_POOL_STATE_LEN);
    expect(() => decodeRaydiumPoolState(genuine, RAYDIUM_CPMM_PROGRAM_ID)).not.toThrow();
  });

  it("Raydium AmmConfig", () => {
    const impostor = accountWith(RAYDIUM_AMM_CONFIG_DISCRIMINATOR, 236);
    expect(() => decodeRaydiumAmmConfig("addr", impostor, FOREIGN_PROGRAM)).toThrow(/owned by/);
    expect(() => decodeRaydiumAmmConfig("addr", impostor, RAYDIUM_CPMM_PROGRAM_ID)).not.toThrow();
  });

  it("PumpSwap Pool — `Pool` is about as generic a type name as exists", () => {
    const impostor = accountWith(PUMP_POOL_DISCRIMINATOR, 301);
    expect(() => decodePumpPool(impostor, FOREIGN_PROGRAM)).toThrow(/owned by/);
    expect(() => decodePumpPool(impostor, PUMP_SWAP_PROGRAM_ID)).not.toThrow();
  });

  it("PumpSwap GlobalConfig", () => {
    const impostor = accountWith(PUMP_GLOBAL_CONFIG_DISCRIMINATOR, 940);
    expect(() => decodePumpGlobalConfig("addr", impostor, FOREIGN_PROGRAM)).toThrow(/owned by/);
    expect(() => decodePumpGlobalConfig("addr", impostor, PUMP_SWAP_PROGRAM_ID)).not.toThrow();
  });

  it("pump FeeConfig must be owned by the FEE program, not the AMM", () => {
    // The fee config lives under a different program than the pool it prices;
    // accepting the AMM as its owner would be a subtler version of the same bug.
    const data = Buffer.alloc(4073);
    PUMP_FEE_CONFIG_DISCRIMINATOR.copy(data, 0);
    expect(() => decodePumpFeeConfig("addr", data, PUMP_SWAP_PROGRAM_ID)).toThrow(/owned by/);
    expect(() => decodePumpFeeConfig("addr", data, PUMP_FEE_PROGRAM_ID)).not.toThrow();
  });
});

describe("token accounts are the same problem without a discriminator at all", () => {
  it("refuses a 165-byte account owned by anything but a token program", () => {
    // Token accounts have NO discriminator, so the owner is the only thing that
    // distinguishes a real vault from any other account of the right size.
    // Reserves are read from these, so a fake one fabricates a balance directly.
    const data = Buffer.alloc(165);
    expect(() => decodeTokenAccount(data, FOREIGN_PROGRAM)).toThrow(/not a token program/);
  });

  it("accepts both SPL Token and Token-2022", () => {
    const data = Buffer.alloc(165);
    expect(() => decodeTokenAccount(data, TOKEN_PROGRAM_ID)).not.toThrow();
    expect(() => decodeTokenAccount(data, TOKEN_2022_PROGRAM_ID)).not.toThrow();
  });

  it("still enforces the length", () => {
    expect(() => decodeTokenAccount(Buffer.alloc(64), TOKEN_PROGRAM_ID)).toThrow(/too small/);
  });
});

describe("event log lines must be attributed to the emitting program", () => {
  // Raydium's CP-Swap and its CLMM are different programs that both emit an
  // event called `SwapEvent`. Anchor derives the discriminator from the type
  // NAME, so the two are byte-identical and matching on it alone reads a CLMM
  // swap as a CP-Swap swap — a real pool id belonging to the wrong program,
  // with every other field read at the wrong offset.
  const CPMM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C";
  const CLMM = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK";
  const cpmmPayload = Buffer.from("cp-swap-event").toString("base64");
  const clmmPayload = Buffer.from("clmm-event").toString("base64");

  const logs = [
    `Program ${CLMM} invoke [1]`,
    "Program log: swapping",
    `Program data: ${clmmPayload}`,
    `Program ${CLMM} success`,
    `Program ${CPMM} invoke [1]`,
    `Program data: ${cpmmPayload}`,
    `Program ${CPMM} success`,
  ];

  it("returns only the requested program's payloads", () => {
    const cp = eventPayloadsFromLogs(logs, CPMM).map((b) => b.toString());
    expect(cp).toEqual(["cp-swap-event"]);
    const clmm = eventPayloadsFromLogs(logs, CLMM).map((b) => b.toString());
    expect(clmm).toEqual(["clmm-event"]);
  });

  it("attributes correctly through nested invocations", () => {
    // A CPI from an aggregator into CP-Swap: the inner program owns the line.
    const nested = [
      `Program ROUTER1111111111111111111111111111111111111 invoke [1]`,
      `Program ${CPMM} invoke [2]`,
      `Program data: ${cpmmPayload}`,
      `Program ${CPMM} success`,
      `Program data: ${clmmPayload}`,
      `Program ROUTER1111111111111111111111111111111111111 success`,
    ];
    expect(eventPayloadsFromLogs(nested, CPMM).map((b) => b.toString())).toEqual([
      "cp-swap-event",
    ]);
  });

  it("returns nothing for a program that did not emit", () => {
    expect(eventPayloadsFromLogs(logs, "SomeOtherProgram11111111111111111111111111")).toEqual([]);
  });

  it("survives a truncated log without throwing", () => {
    expect(() => eventPayloadsFromLogs([`Program data: ${cpmmPayload}`], CPMM)).not.toThrow();
  });
});
