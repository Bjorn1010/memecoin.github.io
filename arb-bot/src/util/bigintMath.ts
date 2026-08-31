/**
 * Integer math helpers.
 *
 * Every economic quantity in this bot is a bigint of base units (lamports, or
 * raw token units). No floating point is allowed anywhere on a path that
 * decides whether to trade: a 1e-16 relative error on a 30 bps margin is a
 * silent losing trade.
 *
 * The rounding direction of each helper matters and is dictated by the on-chain
 * programs we replicate — see quoters/ for the per-protocol references.
 */

/** floor(a / b) for non-negative a, positive b. */
export function floorDiv(a: bigint, b: bigint): bigint {
  if (b <= 0n) throw new RangeError("floorDiv: divisor must be > 0");
  if (a < 0n) throw new RangeError("floorDiv: dividend must be >= 0");
  return a / b;
}

/**
 * ceil(a / b) for non-negative a, positive b.
 *
 * Implemented as `(a + b - 1) / b`, which is the exact form used by both
 * `raydium-cp-swap::curve::fees::ceil_div` and `@pump-fun/pump-swap-sdk`'s
 * `ceilDiv`. Keeping the same expression (rather than a mathematically
 * equivalent one) keeps overflow/edge behaviour identical to the programs.
 */
export function ceilDiv(a: bigint, b: bigint): bigint {
  if (b <= 0n) throw new RangeError("ceilDiv: divisor must be > 0");
  if (a < 0n) throw new RangeError("ceilDiv: dividend must be >= 0");
  return (a + b - 1n) / b;
}

/** floor(a * b / c). bigint is arbitrary precision so there is no overflow. */
export function mulDivFloor(a: bigint, b: bigint, c: bigint): bigint {
  return floorDiv(a * b, c);
}

/** ceil(a * b / c). */
export function mulDivCeil(a: bigint, b: bigint, c: bigint): bigint {
  return ceilDiv(a * b, c);
}

export function bigintMin(...values: bigint[]): bigint {
  if (values.length === 0) throw new RangeError("bigintMin: no values");
  let m = values[0]!;
  for (const v of values) if (v < m) m = v;
  return m;
}

export function bigintMax(...values: bigint[]): bigint {
  if (values.length === 0) throw new RangeError("bigintMax: no values");
  let m = values[0]!;
  for (const v of values) if (v > m) m = v;
  return m;
}

export function clampBigint(v: bigint, lo: bigint, hi: bigint): bigint {
  if (lo > hi) throw new RangeError("clampBigint: lo > hi");
  return v < lo ? lo : v > hi ? hi : v;
}

/** Integer square root (Newton). Used by the closed-form CPMM sizing. */
export function isqrt(n: bigint): bigint {
  if (n < 0n) throw new RangeError("isqrt: negative");
  if (n < 2n) return n;
  let x = n;
  let y = (x + 1n) / 2n;
  while (y < x) {
    x = y;
    y = (x + n / x) / 2n;
  }
  return x;
}

/**
 * Format a lamport amount as SOL for human-readable output only.
 * Never feed the result back into a decision path.
 */
export function lamportsToSolString(lamports: bigint, decimals = 6): string {
  const neg = lamports < 0n;
  const abs = neg ? -lamports : lamports;
  const whole = abs / 1_000_000_000n;
  const frac = (abs % 1_000_000_000n).toString().padStart(9, "0").slice(0, decimals);
  return `${neg ? "-" : ""}${whole}${decimals > 0 ? "." + frac : ""}`;
}

/** Parse a decimal SOL string ("0.05") into lamports without float rounding. */
export function solStringToLamports(value: string): bigint {
  const trimmed = value.trim();
  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
    throw new RangeError(`solStringToLamports: not a decimal number: ${value}`);
  }
  const neg = trimmed.startsWith("-");
  const body = neg ? trimmed.slice(1) : trimmed;
  const [whole = "0", frac = ""] = body.split(".");
  const fracPadded = (frac + "000000000").slice(0, 9);
  const total = BigInt(whole) * 1_000_000_000n + BigInt(fracPadded || "0");
  return neg ? -total : total;
}

/** Basis points of `part` relative to `whole`, as a float, for reporting only. */
export function bpsOf(part: bigint, whole: bigint): number {
  if (whole === 0n) return 0;
  return Number((part * 1_000_000n) / whole) / 100;
}
