/**
 * State freshness.
 *
 * WHAT "STALE" ACTUALLY MEANS ON A SUBSCRIPTION FEED
 *
 * The obvious rule — "reject state older than N slots" — is wrong here, and
 * measurably so: the first live run rejected 384 of 386 cycles as stale while
 * the wall-clock age of the data was zero. `accountSubscribe` only notifies on
 * CHANGE, so a pool that has not traded for a minute has data that is a minute
 * old and completely current. Ageing it out confuses "no news" with "stale
 * news" and blinds the bot to exactly the quiet pools it is supposed to be
 * hunting in.
 *
 * So freshness is a property of the FEED, not of the account:
 *
 *   - data delivered by a live subscription is current until the subscription
 *     stops being live. No news is good news, provided the socket is healthy;
 *   - data read once over RPC to prime a pool is only trusted for a bounded
 *     time, because nothing is watching it in the meantime;
 *   - if the socket is disconnected, or has gone silent for longer than a
 *     stall timeout, EVERYTHING it fed us is suspect at once.
 *
 * This deliberately trusts the subscription. The guard against acting on state
 * that changed a moment ago is not this function — it is the mandatory
 * simulation immediately before sending, which re-prices against the chain and
 * abandons if the profit is gone (§20). This function's job is to catch a dead
 * or lying feed, which simulation cannot.
 */
import type { StateMeta } from "../types.js";

export interface FreshnessPolicy {
  /** How long RPC-primed state is trusted before a subscription must confirm it. */
  maxStateAgeMs: number;
  /** How far behind the newest data a primed account may be, in slots. */
  maxStateAgeSlots: number;
  /** Silence longer than this means the feed is not delivering. */
  feedStallMs: number;
}

export interface FeedHealth {
  connected: boolean;
  /** Wall clock of the last message of any kind from the feed. */
  lastUpdateAt: number;
  /** Newest slot seen at our commitment. */
  dataSlot: number;
}

export type StalenessReason =
  | "feed-disconnected"
  | "feed-stalled"
  | "primed-state-expired"
  | "primed-state-slot-age"
  | "future-slot"
  | null;

export interface FreshnessVerdict {
  fresh: boolean;
  reason: StalenessReason;
  ageSlots: number;
  ageMs: number;
}

export interface FreshnessSubject extends Pick<StateMeta, "slot" | "receivedAt" | "source"> {
  /** Whether a live subscription covers this state. Defaults to false. */
  subscribed?: boolean;
}

export function isStateFresh(
  state: FreshnessSubject,
  feed: FeedHealth,
  nowMs: number,
  policy: FreshnessPolicy,
): FreshnessVerdict {
  const ageSlots = feed.dataSlot - state.slot;
  const ageMs = nowMs - state.receivedAt;

  // A dead feed invalidates everything it ever told us, at once.
  if (!feed.connected) {
    return { fresh: false, reason: "feed-disconnected", ageSlots, ageMs };
  }
  if (feed.lastUpdateAt > 0 && nowMs - feed.lastUpdateAt > policy.feedStallMs) {
    return { fresh: false, reason: "feed-stalled", ageSlots, ageMs };
  }

  // Replayed state is as fresh as the capture says it is.
  if (state.source === "replay") {
    return { fresh: true, reason: null, ageSlots, ageMs };
  }

  // Covered by a live subscription — whether the bytes we hold arrived over the
  // socket or were read once over RPC to prime the pool. Either way, a change
  // since then would have been delivered, so the data is current.
  if (state.source === "ws" || state.subscribed) {
    if (ageSlots < 0) return { fresh: true, reason: "future-slot", ageSlots, ageMs };
    return { fresh: true, reason: null, ageSlots, ageMs };
  }

  // Unwatched, RPC-read state: nothing would tell us it changed, so it expires.
  if (ageMs > policy.maxStateAgeMs) {
    return { fresh: false, reason: "primed-state-expired", ageSlots, ageMs };
  }
  if (ageSlots > policy.maxStateAgeSlots) {
    return { fresh: false, reason: "primed-state-slot-age", ageSlots, ageMs };
  }
  return { fresh: true, reason: null, ageSlots, ageMs };
}

/** Freshness of the worst account among several. */
export function worstFreshness(
  states: readonly FreshnessSubject[],
  feed: FeedHealth,
  nowMs: number,
  policy: FreshnessPolicy,
): FreshnessVerdict {
  let worst: FreshnessVerdict | null = null;
  for (const s of states) {
    const v = isStateFresh(s, feed, nowMs, policy);
    if (!worst || (!v.fresh && worst.fresh) || (v.fresh === worst.fresh && v.ageMs > worst.ageMs)) {
      worst = v;
    }
  }
  return worst ?? { fresh: true, reason: null, ageSlots: 0, ageMs: 0 };
}
