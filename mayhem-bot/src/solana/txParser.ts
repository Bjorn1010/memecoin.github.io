import type { ParsedTransactionWithMeta } from "@solana/web3.js";
import type { MayhemEvent, MayhemEventKind } from "../types.js";

const DUST_UI_AMOUNT = 0.000001;

/**
 * Inspects a confirmed transaction that mentions `wallet` and derives, per mint touched,
 * how the wallet's token balance changed. Multiple mints can move in one tx (rare for
 * Mayhem's simple swaps, but we handle it defensively) — one MayhemEvent is returned per mint.
 */
export function parseMayhemTransaction(
  wallet: string,
  signature: string,
  tx: ParsedTransactionWithMeta,
  idPrefix: string,
): Omit<MayhemEvent, "id" | "detectedAtMs">[] {
  const meta = tx.meta;
  if (!meta || meta.err) return [];

  const pre = meta.preTokenBalances ?? [];
  const post = meta.postTokenBalances ?? [];

  const mints = new Set<string>();
  for (const b of pre) if (b.owner === wallet) mints.add(b.mint);
  for (const b of post) if (b.owner === wallet) mints.add(b.mint);

  const accountKeys = tx.transaction.message.accountKeys.map((k) => k.pubkey.toBase58());
  const walletIdx = accountKeys.indexOf(wallet);
  const isFeePayer = walletIdx === 0;
  const feeSol = isFeePayer ? (meta.fee ?? 0) / 1e9 : 0;

  let walletSolDelta = 0;
  if (walletIdx >= 0 && meta.preBalances && meta.postBalances) {
    walletSolDelta = (meta.postBalances[walletIdx] - meta.preBalances[walletIdx]) / 1e9;
  }

  const events: Omit<MayhemEvent, "id" | "detectedAtMs">[] = [];

  for (const mint of mints) {
    const preBal = pre.find((b) => b.owner === wallet && b.mint === mint);
    const postBal = post.find((b) => b.owner === wallet && b.mint === mint);
    const preUi = preBal?.uiTokenAmount.uiAmount ?? 0;
    const postUi = postBal?.uiTokenAmount.uiAmount ?? 0;
    const delta = postUi - preUi;

    if (Math.abs(delta) < DUST_UI_AMOUNT) continue;

    const kind: MayhemEventKind =
      delta > 0 ? "buy" : postUi < DUST_UI_AMOUNT ? "full_exit" : "sell";

    // Approximate SOL side of this specific mint's leg using the wallet's net SOL delta
    // corrected for the fee. Good enough for single-swap transactions (Mayhem's norm).
    const solAmount = Math.max(Math.abs(walletSolDelta) - feeSol, 0);
    const tokenAmount = Math.abs(delta);
    const priceSol = tokenAmount > 0 ? solAmount / tokenAmount : 0;

    events.push({
      wallet,
      kind,
      mint,
      signature,
      slot: tx.slot,
      blockTime: tx.blockTime ?? Math.floor(Date.now() / 1000),
      solAmount,
      tokenAmount,
      priceSol,
      walletTokenBalanceAfter: postUi,
    });
  }

  return events;
}
