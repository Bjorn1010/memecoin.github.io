/**
 * State freshness.
 *
 * Every quote is computed from account data we received some time ago. On a
 * free RPC that lag is the single biggest reason a profitable-looking cycle is
 * already gone. Freshness is therefore checked twice: once when a candidate is
 * found, and again immediately before sending (§20).
 *
 * Both a slot bound and a wall-clock bound are enforced, because they fail in
 * different ways: a stalled WebSocket keeps reporting an old slot (caught by
 * the slot bound), while a stalled *local* process has fresh slots but stale
 * wall time (caught by the ms bound).
 */

export interface FreshnessPolicy {
  maxStateAgeSlots: number;
  maxStateAgeMs: number;
}

export type StalenessReason = "slot-age" | "wall-age" | "future-slot" | null;

export interface FreshnessVerdict {
  fresh: boolean;
  reason: StalenessReason;
  ageSlots: number;
  ageMs: number;
}

export function isStateFresh(
  state: { slot: number; receivedAt: number },
  currentSlot: number,
  nowMs: number,
  policy: FreshnessPolicy,
): FreshnessVerdict {
  const ageSlots = currentSlot - state.slot;
  const ageMs = nowMs - state.receivedAt;

  // A state ahead of our notion of the current slot means our slot tracker is
  // behind, not that the state is fresh. Treat it as age 0 but flag it so the
  // caller can see the feed is inconsistent.
  if (ageSlots < 0) {
    return { fresh: true, reason: "future-slot", ageSlots, ageMs };
  }
  if (ageSlots > policy.maxStateAgeSlots) {
    return { fresh: false, reason: "slot-age", ageSlots, ageMs };
  }
  if (ageMs > policy.maxStateAgeMs) {
    return { fresh: false, reason: "wall-age", ageSlots, ageMs };
  }
  return { fresh: true, reason: null, ageSlots, ageMs };
}

/** Freshness of the worst account among several. */
export function worstFreshness(
  states: readonly { slot: number; receivedAt: number }[],
  currentSlot: number,
  nowMs: number,
  policy: FreshnessPolicy,
): FreshnessVerdict {
  let worst: FreshnessVerdict | null = null;
  for (const s of states) {
    const v = isStateFresh(s, currentSlot, nowMs, policy);
    if (!worst || (!v.fresh && worst.fresh) || v.ageSlots > worst.ageSlots) {
      worst = v;
    }
  }
  return worst ?? { fresh: true, reason: null, ageSlots: 0, ageMs: 0 };
}
