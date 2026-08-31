/**
 * SPL Token / Token-2022 account decoding.
 *
 * Written by hand rather than delegating to @solana/spl-token so that decoding
 * is a pure function over a Buffer: it can run in tests against committed
 * fixtures with no RPC, and it never allocates a Connection.
 *
 * REFERENCES (see ASSUMPTIONS.md #T22-1..#T22-3):
 *  - Base Mint / Account layouts: SPL Token program state (82 and 165 bytes).
 *  - Extension framing: Token-2022 stores `AccountType` at offset 165 and a
 *    TLV list from offset 166; each entry is u16 type, u16 length, value.
 *  - `TransferFee::calculate_fee` = min(ceil(amount * bps / 10_000), maximum_fee)
 *    and `calculate_epoch_fee` picks `newer` when epoch >= newer.epoch.
 *  - Extension type ids cross-checked against @solana/spl-token 0.4.15's
 *    `ExtensionType` enum.
 */
import type { MintExtensionSummary, MintState } from "../../types.js";
import { ceilDiv } from "../../util/bigintMath.js";

export const TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA";
export const TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb";

const BASE_MINT_LEN = 82;
const BASE_ACCOUNT_LEN = 165;
const ACCOUNT_TYPE_OFFSET = 165;
const TLV_START = 166;
const ACCOUNT_TYPE_MINT = 1;

export const ExtensionId = {
  TransferFeeConfig: 1,
  MintCloseAuthority: 3,
  ConfidentialTransferMint: 4,
  DefaultAccountState: 6,
  NonTransferable: 9,
  InterestBearingConfig: 10,
  PermanentDelegate: 12,
  TransferHook: 14,
  ConfidentialTransferFeeConfig: 16,
  MetadataPointer: 18,
  TokenMetadata: 19,
  GroupPointer: 20,
  TokenGroup: 21,
  GroupMemberPointer: 22,
  TokenGroupMember: 23,
  ScaledUiAmountConfig: 25,
  PausableConfig: 26,
  PermissionedBurn: 28,
} as const;

/**
 * Extensions that provably cannot change how many base units move during a
 * transfer, cannot freeze or seize our balance, and cannot make a transfer
 * fail for reasons outside our control. Everything else is rejected by the
 * risk filter — fail-closed, including unknown ids (§29).
 */
export const BENIGN_MINT_EXTENSIONS: ReadonlySet<number> = new Set<number>([
  ExtensionId.MintCloseAuthority,
  ExtensionId.MetadataPointer,
  ExtensionId.TokenMetadata,
  ExtensionId.GroupPointer,
  ExtensionId.TokenGroup,
  ExtensionId.GroupMemberPointer,
  ExtensionId.TokenGroupMember,
]);

export interface TlvEntry {
  type: number;
  offset: number;
  length: number;
}

/** Walk the Token-2022 TLV list. Returns [] for a classic SPL account. */
export function parseTlv(data: Buffer): TlvEntry[] {
  if (data.length <= BASE_ACCOUNT_LEN) return [];
  if (data.readUInt8(ACCOUNT_TYPE_OFFSET) === 0) return [];
  const out: TlvEntry[] = [];
  let o = TLV_START;
  while (o + 4 <= data.length) {
    const type = data.readUInt16LE(o);
    const length = data.readUInt16LE(o + 2);
    if (type === 0 && length === 0) break; // Uninitialized padding
    const valueOffset = o + 4;
    if (valueOffset + length > data.length) break; // truncated: stop, do not guess
    out.push({ type, offset: valueOffset, length });
    o = valueOffset + length;
  }
  return out;
}

interface TransferFeeEpochEntry {
  epoch: bigint;
  maximumFee: bigint;
  basisPoints: number;
}

export interface TransferFeeConfigParsed {
  older: TransferFeeEpochEntry;
  newer: TransferFeeEpochEntry;
}

/**
 * TransferFeeConfig value layout:
 *   transfer_fee_config_authority: 32
 *   withdraw_withheld_authority:   32
 *   withheld_amount:                8
 *   older_transfer_fee:            18  (epoch u64, maximum_fee u64, bps u16)
 *   newer_transfer_fee:            18
 */
export function parseTransferFeeConfig(data: Buffer, offset: number): TransferFeeConfigParsed {
  const base = offset + 32 + 32 + 8;
  const read = (o: number): TransferFeeEpochEntry => ({
    epoch: data.readBigUInt64LE(o),
    maximumFee: data.readBigUInt64LE(o + 8),
    basisPoints: data.readUInt16LE(o + 16),
  });
  return { older: read(base), newer: read(base + 18) };
}

/** `TransferFee::calculate_fee` — ceiling, then capped at maximum_fee. */
export function calculateTransferFee(entry: TransferFeeEpochEntry, amount: bigint): bigint {
  if (entry.basisPoints === 0 || amount === 0n) return 0n;
  const raw = ceilDiv(amount * BigInt(entry.basisPoints), 10_000n);
  return raw < entry.maximumFee ? raw : entry.maximumFee;
}

/**
 * Fee the token program will withhold when `amount` of `mint` is transferred.
 *
 * Returns 0 for classic SPL mints and for Token-2022 mints without the
 * extension, exactly like `raydium-cp-swap::utils::token::get_transfer_fee`.
 */
export function transferFeeOn(mint: MintState, amount: bigint): bigint {
  const tf = mint.extensions.transferFee;
  if (!tf) return 0n;
  if (tf.basisPoints === 0 || amount === 0n) return 0n;
  const raw = ceilDiv(amount * BigInt(tf.basisPoints), 10_000n);
  return raw < tf.maximumFee ? raw : tf.maximumFee;
}

export function summarizeExtensions(
  data: Buffer,
  currentEpoch: bigint,
): MintExtensionSummary {
  const tlv = parseTlv(data);
  const present = tlv.map((e) => e.type);
  let transferFee: MintExtensionSummary["transferFee"] = null;

  for (const e of tlv) {
    if (e.type === ExtensionId.TransferFeeConfig) {
      const cfg = parseTransferFeeConfig(data, e.offset);
      const active = currentEpoch >= cfg.newer.epoch ? cfg.newer : cfg.older;
      transferFee = { basisPoints: active.basisPoints, maximumFee: active.maximumFee };
    }
  }

  return {
    present,
    transferFee,
    hasTransferHook: present.includes(ExtensionId.TransferHook),
    nonTransferable: present.includes(ExtensionId.NonTransferable),
    hasPermanentDelegate: present.includes(ExtensionId.PermanentDelegate),
    defaultAccountStateFrozen: hasFrozenDefaultState(data, tlv),
    hasConfidentialTransfers:
      present.includes(ExtensionId.ConfidentialTransferMint) ||
      present.includes(ExtensionId.ConfidentialTransferFeeConfig),
  };
}

/** DefaultAccountState value is a single byte: 1 = Initialized, 2 = Frozen. */
function hasFrozenDefaultState(data: Buffer, tlv: TlvEntry[]): boolean {
  const e = tlv.find((x) => x.type === ExtensionId.DefaultAccountState);
  if (!e || e.length < 1) return false;
  return data.readUInt8(e.offset) === 2;
}

export interface DecodeMintArgs {
  address: string;
  data: Buffer;
  programId: string;
  slot: number;
  receivedAt: number;
  source: MintState["source"];
  currentEpoch: bigint;
}

export function decodeMint(args: DecodeMintArgs): MintState {
  const { data } = args;
  if (data.length < BASE_MINT_LEN) {
    throw new Error(`decodeMint: account too small (${data.length} bytes)`);
  }
  const mintAuthoritySet = data.readUInt32LE(0) === 1;
  const mintAuthority = mintAuthoritySet ? bs58Encode(data.subarray(4, 36)) : null;
  const supply = data.readBigUInt64LE(36);
  const decimals = data.readUInt8(44);
  const freezeAuthoritySet = data.readUInt32LE(46) === 1;
  const freezeAuthority = freezeAuthoritySet ? bs58Encode(data.subarray(50, 82)) : null;

  const extensions =
    args.programId === TOKEN_2022_PROGRAM_ID
      ? summarizeExtensions(data, args.currentEpoch)
      : emptyExtensions();

  return {
    address: args.address,
    decimals,
    supply,
    programId: args.programId,
    mintAuthority,
    freezeAuthority,
    extensions,
    slot: args.slot,
    receivedAt: args.receivedAt,
    source: args.source,
  };
}

export function emptyExtensions(): MintExtensionSummary {
  return {
    present: [],
    transferFee: null,
    hasTransferHook: false,
    nonTransferable: false,
    hasPermanentDelegate: false,
    defaultAccountStateFrozen: false,
    hasConfidentialTransfers: false,
  };
}

export interface DecodedTokenAccount {
  mint: string;
  owner: string;
  amount: bigint;
  /** 0 = Uninitialized, 1 = Initialized, 2 = Frozen. */
  state: number;
  isNative: boolean;
}

export function decodeTokenAccount(data: Buffer): DecodedTokenAccount {
  if (data.length < BASE_ACCOUNT_LEN) {
    throw new Error(`decodeTokenAccount: account too small (${data.length} bytes)`);
  }
  return {
    mint: bs58Encode(data.subarray(0, 32)),
    owner: bs58Encode(data.subarray(32, 64)),
    amount: data.readBigUInt64LE(64),
    state: data.readUInt8(108),
    isNative: data.readUInt32LE(109) === 1,
  };
}

// --- base58 -----------------------------------------------------------------
// Kept local so decoding stays dependency-free and synchronous.

const B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

export function bs58Encode(bytes: Uint8Array): string {
  if (bytes.length === 0) return "";
  let zeros = 0;
  while (zeros < bytes.length && bytes[zeros] === 0) zeros++;
  const digits: number[] = [];
  for (let i = zeros; i < bytes.length; i++) {
    let carry = bytes[i]!;
    for (let j = 0; j < digits.length; j++) {
      carry += digits[j]! << 8;
      digits[j] = carry % 58;
      carry = (carry / 58) | 0;
    }
    while (carry > 0) {
      digits.push(carry % 58);
      carry = (carry / 58) | 0;
    }
  }
  let out = "1".repeat(zeros);
  for (let i = digits.length - 1; i >= 0; i--) out += B58_ALPHABET[digits[i]!];
  return out;
}

export function bs58Decode(str: string): Uint8Array {
  if (str.length === 0) return new Uint8Array(0);
  let zeros = 0;
  while (zeros < str.length && str[zeros] === "1") zeros++;
  const bytes: number[] = [];
  for (let i = zeros; i < str.length; i++) {
    const value = B58_ALPHABET.indexOf(str[i]!);
    if (value < 0) throw new Error(`bs58Decode: invalid character '${str[i]}'`);
    let carry = value;
    for (let j = 0; j < bytes.length; j++) {
      carry += bytes[j]! * 58;
      bytes[j] = carry & 0xff;
      carry >>= 8;
    }
    while (carry > 0) {
      bytes.push(carry & 0xff);
      carry >>= 8;
    }
  }
  const out = new Uint8Array(zeros + bytes.length);
  for (let i = 0; i < bytes.length; i++) out[zeros + i] = bytes[bytes.length - 1 - i]!;
  return out;
}
