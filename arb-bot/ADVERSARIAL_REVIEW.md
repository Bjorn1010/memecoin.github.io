# Adversarial review

A pass over the code asking one question throughout: *how would I make this bot
lose money?* Each finding gives the mechanism, its economic impact, how likely
it is, how it would be detected, and what was done about it.

Findings marked **FIXED** were corrected before this document was written; the
commit history shows each change. Findings marked **ACCEPTED** are real and
unmitigated, and are risks you are taking if you run this.

---

## Found by running it, not by reading it

These four were invisible in review and obvious within two minutes of a live
`--observe` run. They are listed first because they are the honest answer to
"what did testing actually catch?".

### 1. Freshness rejected almost everything — **FIXED**

**Mechanism.** Three separate errors stacked. `slotSubscribe` reports slots as
they are *processed*, several ahead of *confirmed* account data, so measuring a
confirmed account against it added a constant bias. Rarely-changing config
accounts were folded into each snapshot's slot, pinning every snapshot to
startup. And most fundamentally, `accountSubscribe` only fires on **change**:
ageing out a pool that has not traded confuses "no news" with "stale news".

**Impact.** Total. 384 of 386 cycles rejected as stale while the data's
wall-clock age was zero. The bot would have traded nothing, forever, and the
metrics would have blamed the market.

**Probability.** Certain — it happened on the first run.

**Detection.** The `stale-state` reject counter next to a state-age p50 of 0ms.

**Mitigation.** Freshness is now a property of the feed and of subscription
coverage rather than of an account's age: subscribed data is current while the
socket is healthy; a disconnect or a stall invalidates everything at once;
RPC-primed but unsubscribed data still expires. The guard against state that
changed a moment ago is the mandatory pre-send simulation, which is what
actually protects the money.

### 2. The watchlist could never bootstrap — **FIXED**

**Mechanism.** An unwatched pool has no observations, so it scores zero, so the
minimum-score gate on entry kept it out permanently. No pool could ever be
observed, so no pool could ever score.

**Impact.** Total: the watchlist stayed empty and the bot idled.

**Detection.** `watching 0 pools` in the screener log.

**Mitigation.** Free slots admit unproven pools on a time-boxed trial; the score
floor applies only at eviction.

### 3. Eviction immediately re-admitted the same pool — **FIXED**

**Mechanism.** Eviction freed a slot, and the evicted pool was instantly the
best candidate for its own slot in the same pass.

**Impact.** Endless resubscribe churn, burning RPC budget while the watchlist
never actually changed.

**Mitigation.** Evicted pools serve a cooldown before they can return.

### 4. Cross-venue cycles do not fit in a transaction — **FIXED**

**Mechanism.** A PumpSwap+Raydium cycle touches ~30 accounts. Measured, it
serialises to **1281 bytes** against Solana's **1232-byte** limit.

**Impact.** Severe but silent: every cross-venue opportunity — the majority of
the reason this bot exists — would fail at build or send time, leaving only
same-venue arbitrage.

**Detection.** `test/exec/transactionBuilder.test.ts` measures both shapes and
asserts the sizes, so this is now a build failure rather than a discovery.

**Mitigation.** An address lookup table is created by `npm run setup` and loaded
at startup; the same test proves the mixed cycle fits with one. The builder
refuses an oversized transaction with an error naming the remedy, and the engine
warns loudly at startup when no table is configured.

---

## Money-losing bugs found by review

### 5. The on-chain assertion did not cover the SOL-side costs — **FIXED**

**Mechanism.** The profit assertion is denominated in WSOL, but the base fee,
priority fee and tip are paid in native SOL, which the assertion cannot see. The
bound was `amountIn + MIN_PROFIT`. With `MIN_PROFIT` set below the cost of a
transaction, the chain would happily confirm a trade that lost money overall.

**Impact.** A slow bleed that looks like success. Every trade "lands
profitably" while the wallet shrinks.

**Probability.** Certain for anyone who lowers `MIN_PROFIT` to chase volume —
which is exactly what an operator does when the bot is not trading enough.

**Mitigation.** The bound is now `amountIn + costs.onSuccess + MIN_PROFIT`, so
landing guarantees a genuine net profit of at least `MIN_PROFIT`.

### 6. Realised PnL overstated itself by the fees — **FIXED**

**Mechanism.** Realised profit subtracted only the tip from the WSOL balance
delta, not the base and priority fees.

**Impact.** Reported PnL drifts above reality by the fee on every trade. The
kill switch, which watches realised PnL, would trip late or not at all.

**Mitigation.** Subtracts `costs.onSuccess` in full.

### 7. Residual balances compared token units to lamports — **FIXED**

**Mechanism.** The residual-balance alarm compared a raw token amount against a
lamport threshold. A six-decimal token trips it on dust worth nothing; an
eighteen-decimal one never trips it at all.

**Impact.** Either constant false alarms that get ignored, or a genuinely
broken cycle silently accumulating exposure. The second is worse: §30 exists
precisely so a residue is never explained away.

**Mitigation.** The residue is priced through the sell pool into base lamports
before comparison. If it cannot be priced, it is treated as material rather than
as zero.

### 8. The screener scored pools on gross profit — **FIXED**

**Mechanism.** Pool activity recorded gross profit in the field the scorer reads
as net.

**Impact.** Systematically over-ranks expensive pools. Given that PumpSwap's
low-cap tier charges 125 bps a leg, this would have steered the watchlist toward
exactly the pools least likely to pay.

**Mitigation.** Net profit is recorded after the cost model runs.

### 9. Live sizing used the trade cap when the balance was unknown — **FIXED**

**Mechanism.** A zero WSOL balance was treated as "unconstrained" and sizing
used `MAX_TRADE_SIZE`.

**Impact.** Wasted work and misleading metrics — every cycle sized against money
we do not have, then rejected a stage later by the limit check.

**Mitigation.** Live mode sizes against the real balance; observe and paper,
which hold no capital, still use the cap.

### 10. A connected-but-silent feed was never detected — **FIXED**

**Mechanism.** The stall check compared `now` against `lastUpdateAt`, which was
zero until the first message, so `now - now = 0`. A socket that connected and
then delivered nothing was considered healthy forever.

**Impact.** The worst failure shape there is: the bot looks alive and quotes
increasingly stale state.

**Mitigation.** The stall clock starts at connection time.

### 11. Paper mode could not simulate anything — **FIXED**

**Mechanism.** Paper mode built transactions for a placeholder payer holding no
WSOL, so every simulation failed at leg 1.

**Impact.** Paper mode measured nothing — no compute units, no quote-versus-
simulation divergence — while appearing to run. The mode most responsible for
deciding whether to go live would have been decorative.

**Mitigation.** `WALLET_PUBLIC_KEY` (a public key only, no secret) makes paper
simulate against real balances. Without it the engine says plainly, at startup,
that its numbers will be missing.

---

## Risks reviewed and deliberately accepted

### 12. `getProgramAccounts` discovery misses non-canonical pools — **ACCEPTED**

Raydium explicitly allows a pool at a plain keypair address rather than the
canonical PDA. The default derived-address discovery misses those. The deep scan
finds them but does not complete at all on a public endpoint. **Consequence: an
unknown fraction of pools is invisible.** Run `deepScanPoolsForMint` on a paid
endpoint to quantify it.

### 13. Leg 1 reverts on any adverse move — **ACCEPTED, by design**

`LEG1_TOLERANCE_BPS` defaults to 0, so the transaction reverts if leg 1 returns
one base unit less than quoted. This will cost land rate. The alternative —
tolerance on the intermediate amount — creates systematic dust. Since leg 1 asks
for an exact output, its tolerance sits on the input side, where a favourable
move makes us pay less rather than accumulating residue. Watch the
`simulation-unprofitable` counter to see what it costs.

### 14. Mayhem-mode PumpSwap pools are refused — **ACCEPTED**

Their protocol fee goes to a reserved recipient set we do not model. Refusing
them costs opportunities; guessing a recipient risks paying the wrong account.

### 15. Land rate is estimated, and starts pessimistic — **ACCEPTED**

The Dirichlet prior assumes 5% success until evidence says otherwise, so the bot
under-trades at first by construction. The alternative — an optimistic prior —
over-trades into unknown segments, which costs real money rather than
opportunity.

### 16. The screener's weights are uncalibrated — **ACCEPTED, and stated**

Chosen before data existed. They rank pools by an opinion, not a measurement.
`npm run report` prints realised PnL per pool against the score that pool had;
until that comparison is run, any claim these weights are tuned is false.

### 17. Synchronous appends on the update path — **ACCEPTED**

Observe mode writes captured state with `appendFileSync` on every account
update. At the observed rate of a few updates per second this is invisible; at a
much higher rate it would block the event loop. The capture is also capped so a
long run cannot fill the disk.

### 18. High-priority RPC traffic can starve low-priority work — **ACCEPTED, by design**

The budget serves strictly by priority. A sustained burst of P0 work will starve
the screener indefinitely. That is the correct trade — a screener sweep must
never delay simulating a live opportunity — but it means the watchlist can go
stale under load without any single thing failing.

### 19. Jito's free-failure property is documented, not verified here — **ACCEPTED**

That a failed bundle costs nothing is the single most economically significant
assumption in the project, and it comes from Jito's documentation rather than
from our own measurement. If it is wrong, every expected value computed with
Jito enabled is too optimistic. Verify it against your own wallet history before
trusting it. Jito is off by default.

### 20. `Pool.virtual_quote_reserves` is read from a field the on-chain IDL does not list — **ACCEPTED, guarded**

Present in pump's SDK, absent from the IDL the program publishes. The reasoning
for why reading it is safe either way is in `ASSUMPTIONS.md` (#PS-5); the decoder
rejects an implausible magnitude rather than trusting reserve bytes blindly.

---

## Why this bot could still lose money

Ranked by how likely each is to be the one that actually does it.

1. **The fees are larger than the edge.** PumpSwap canonical pools charge 125 bps
   per leg below a 420 SOL market cap. A round trip through one costs more than
   most price gaps are worth. This is measured, not feared, and it is the
   strongest argument against the whole strategy.
2. **The opportunities are gone before we see them.** Unmeasured until you run
   `--observe`. If the median opportunity dies in under 200ms, this is a speed
   game and this bot loses it.
3. **There are too few cycleable tokens.** A discovery run found exactly one of
   the ten most active mints had the two or more quotable pools a cycle needs.
4. **The land rate makes every attempt negative-sum.** Modelled and guarded
   against, but the guard only works if the land-rate estimate is right, and it
   starts as a prior.
5. **Adverse selection.** The opportunities that survive long enough for us to
   take them may survive precisely because something is wrong with them.
6. **A quoter drifts from its program.** Guarded by `verify:quoters` and by the
   kill switch's divergence trigger, but a drift between runs is possible.
7. **Capital is too small for the fixed costs.** Below roughly 1 SOL of working
   capital, the profit on a viable trade struggles to clear the transaction's
   fixed cost.
