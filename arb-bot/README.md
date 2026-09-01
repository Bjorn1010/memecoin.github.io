# Solana atomic arbitrage bot

A two-leg atomic arbitrage bot for Solana, built for exactly one measure of
success: **realised net profit**. Not opportunities detected, not transactions
sent, not venues integrated. A bot that finds ten thousand opportunities and
loses money is a failure; one that takes five trades and ends the week up is not.

Everything below is written so you can decide whether to run it, and — more
importantly — when to stop.

---

## Read this first

Three things were measured during development. They matter more than any feature
list:

1. **PumpSwap canonical pools charge up to 125 bps per leg.** The fee is a
   market-cap tier ladder, read live from the fee program's config account: 125
   bps below a 420 SOL market cap, decaying to 30 bps above ~98 000 SOL. Raydium
   CP-Swap is typically 25 bps. So a round trip costs roughly **55 to 150 basis
   points in DEX fees alone**, before a single Solana fee. The low-cap long tail
   is the *most* expensive segment to trade, not the cheapest.

2. **A cross-venue cycle does not fit in a transaction without help.** A
   PumpSwap+Raydium cycle serialises to 1281 bytes against Solana's 1232-byte
   limit. An address lookup table is a requirement, not an optimisation, and
   `npm run setup` creates it.

3. **Cycleable tokens are rare.** In a discovery run over the ten most active
   mints, exactly one had the two or more quotable pools a cycle needs.

None of that means the strategy cannot work. It means the burden of proof is on
the data, which is what `--observe` exists to collect.

---

## What it does

Watches a small set of WSOL pools across two venues, looks for a price gap it can
close in a single atomic transaction, sizes the trade, prices every cost, and
either takes it or records why it did not.

```
feed ──▶ decode ──▶ cycles ──▶ sizing ──▶ costs ──▶ risk ──▶ build ──▶ simulate ──▶ decision
                                                                                       │
                                        observe: stop and record ◀────────────────────┤
                                        paper:   stop after simulating ◀──────────────┤
                                        live:    send ◀───────────────────────────────┘
```

All three modes run the same code with the last step switched off. That is the
only honest way for `--paper` to predict `--live`.

### Venues

| Venue | Program | Status |
|---|---|---|
| Raydium CP-Swap | `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C` | exact, verified against on-chain execution |
| PumpSwap | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | exact, verified against on-chain execution |

Two venues, priced exactly, rather than five priced approximately. Both quoters
reproduce real mainnet swaps to the lamport — see [Verifying the
quoters](#verifying-the-quoters).

---

## Install

Node 20 or newer.

```bash
cd arb-bot
npm install
cp .env.example .env     # then edit it
npm test                 # 143 tests, no network required
```

---

## The atomicity guarantee

This is the load-bearing claim, so here it is in full.

**Leg 1** asks for an *exact* amount of the intermediate token while capping the
base spent — `swap_base_output` on Raydium, `buy` on PumpSwap. After it we hold
exactly `intermediateAmount` and have spent **at most** `amountIn`.

**Leg 2** sells precisely that amount, with a minimum output of
`amountIn + costs + MIN_PROFIT` — `swap_base_input`'s `minimum_amount_out`,
`sell`'s `min_quote_amount_out`.

Both programs enforce their bound with a `require`, so if either fails the whole
transaction reverts. On success the WSOL balance is up by at least
`costs + MIN_PROFIT` while `costs` came out of native SOL, leaving a genuine net
profit of `MIN_PROFIT`. The intermediate balance returns to where it started,
because leg 2 sells precisely what leg 1 produced.

**No custom on-chain program is needed, and none is included.** The two venues
already expose the exact bounds the assertion requires. Writing an Anchor
program here would add deployment risk and audit surface to buy nothing.

The one thing the on-chain assertion cannot see is that fees are paid in native
SOL rather than in the asset being asserted on — which is why the costs are
folded into the bound rather than left to `MIN_PROFIT` alone.

---

## Running it

### 1. Observe (start here, and stay here for a while)

```bash
npm run observe
```

No wallet is loaded and no sender is constructed, so there is no code path that
could transmit. It records, for every opportunity, whether it still existed
200ms, 500ms, 1s and 5s later — the measurement that decides whether this
strategy is viable from your machine at all.

Raw account state is captured to `data/<run>/state.jsonl` so the same period can
be replayed against different settings later.

```bash
npm run report -- --dir data/<run>
```

The report answers: how many opportunities existed, how many survived your
latency, what they were worth, which pools produced them, and what your
practical latency ceiling is. If it says *"under 200ms — this segment is a speed
game we cannot win"*, believe it.

### 2. Paper

```bash
npm run paper
```

The full pipeline including transaction construction and on-chain simulation,
stopping immediately before sending. Set `WALLET_PUBLIC_KEY` (a public key, no
secret) so simulations run against real balances — otherwise they fail for lack
of funds and measure nothing, and the engine will tell you so at startup.

Paper mode **cannot** tell you your land rate. Nothing is sent, so nothing
lands. Treat its expected PnL as an upper bound that assumes perfect inclusion.

### 3. Live

```bash
npm run setup    # once: WSOL account, pump volume accumulator, lookup table
npm run live
```

Refuses to start unless all of: `LIVE_TRADING=true`,
`LIVE_CONFIRMATION=I_UNDERSTAND_THIS_SPENDS_REAL_SOL`, a `WALLET_KEYPAIR_PATH`,
`MAX_TRADE_SIZE`, `MAX_DAILY_LOSS` and `MIN_PROFIT` all set, and an untripped
kill switch.

### 4. Replay

```bash
npm run replay -- --state data/<run>/state.jsonl --speed 10
```

Feeds captured state back through the identical pipeline with no sender and no
network feed. Change a threshold, re-run against the same capture, compare the
reports. This is how you tune `MIN_PROFIT` without paying tuition.

---

## Verifying the quoters

```bash
npm run verify:quoters
```

Both programs emit an event on every swap carrying the pre-trade reserves, the
input amount, and the output the program actually computed. This command replays
recent real mainnet swaps through our quoters and requires an **exact base-unit
match**, exiting non-zero otherwise. Run it before every live session.

`npm test` additionally fuzzes the PumpSwap quoter against pump.fun's own SDK
over 12 000 randomised states, so a math change on their side breaks the build.

One subtlety worth knowing, because it bit this codebase: Anchor derives both
account and event discriminators from the TYPE NAME alone, so unrelated programs
collide by construction. Raydium's CP-Swap and its CLMM both define `PoolState`
and both emit `SwapEvent` with identical leading bytes. Every decoder here
therefore verifies the owning program, and event parsing is attributed via the
log's `invoke`/`success` framing. See `ADVERSARIAL_REVIEW.md` §4b and §4c.

---

## How the money is counted

Four figures, never conflated:

| Term | Meaning |
|---|---|
| **Expected PnL** | What we predicted before sending. An estimate. |
| **Realised PnL** | WSOL balance delta minus base fee, priority fee and tip. What actually happened. |
| **Failed attempt cost** | What a failed attempt actually cost. Zero if it never landed; base + priority if it landed and reverted; **zero for a Jito bundle**, which is never included when it fails. |
| **Strategy PnL** | Cumulative realised PnL net of every failed attempt. The only number that matters. |

And five outcomes, never merged into a "success rate":

`not-sent` · `simulated-abandoned` · `sent-not-landed` · `landed-profitable` ·
`landed-unprofitable`

### Expected value, and why a profitable trade gets rejected

```
EV = P(success) × (gross − baseFee − priorityFee − tip)
   − P(reverted) × (baseFee + priorityFee)
   − P(notIncluded) × 0
```

At a 10% land rate one success pays for nine failures. An opportunity with a
healthy gross profit and a negative EV is rejected automatically. That is the
whole point of the cost model.

### Land rate

Never configured. Estimated from the bot's own ledger with a hierarchical
Dirichlet posterior, segmented by pool pair, venue pair, profit bucket, latency
bucket and hour. A segment with two observations backs off to its parent rather
than producing a confident wrong number, and the prior assumes 5% success until
evidence says otherwise.

---

## Configuration

Every economically significant number lives in `.env` — see `.env.example`, which
documents each one. Nothing that decides whether to trade is hardcoded.

**None of the defaults are tuned.** They are conservative starting points chosen
before any data existed. `MIN_PROFIT` in particular is a guess; the report prints
the realised distribution against it.

---

## The RPC is a budget, not an API

Every call passes through a priority token bucket:

| Priority | Used for |
|---|---|
| P0 | Safety and critical state: balances, blockhash, sends |
| P1 | Simulating a live opportunity |
| P2 | State needed to trade |
| P3 | Screener sweeps |
| P4 | Statistics and maintenance |

A 429 backs off the entire client, not just the request that tripped it. A
screener sweep can never delay simulating a live opportunity.

Pool discovery derives addresses locally and reads them in one batched call,
because `getProgramAccounts` does not complete at all against a public endpoint.
The scan survives as an opt-in deep scan for pools at non-canonical addresses.

Subscriptions are counted exactly: each watched pool costs three, and the config
refuses to start if `MAX_WATCHED_POOLS × 3 + 2` exceeds `MAX_SUBSCRIPTIONS`.

---

## The screener

Runs off the critical path and decides which pools hold the scarce
subscriptions. It scores on measurements, not on which DEX is fashionable:

```
score = w1·persistence + w2·netProfit + w3·frequency + w4·liquidity
      − w5·competition − w6·failureRate
```

Every component is returned normalised alongside its weighted contribution, so a
ranking can be explained rather than trusted. The weights are configurable and
**uncalibrated**: compare realised PnL per pool against the score that pool had,
and adjust.

The watchlist has hysteresis (a challenger must beat the weakest incumbent by a
margin), a grace period, and a cooldown after eviction. Unproven pools get a
time-boxed trial in free slots — without that the watchlist can never bootstrap,
since a pool that is never watched is never observed and therefore always scores
zero.

---

## Adding things

**A pool** — discovery finds pools automatically. To force one, add its mint to
`WHITELIST_MINTS`.

**A quoter** — implement `Quoter` in `src/quoters/`, transcribing the program's
own math rather than a general formula. Add it to the map in `src/engine.ts` and
the decoder in `src/feed/decoder/`. It is not finished until `verify:quoters`
reproduces real swaps exactly.

**A venue** — a quoter, a decoder, PDA derivations, instruction encoders, and a
branch in the transaction builder. Budget for the transaction size: the limit is
already tight.

---

## Safety

- A **dedicated wallet**. Fund it with what you can afford to lose.
- The private key is never logged, never written to the ledger, never in an error
  message. The ledger writer actively refuses any value shaped like a key.
- `.gitignore` covers `.env`, `*.keypair`, `wallet.json`, `id.json` and
  `keypair*.json`, while explicitly re-including test fixtures so a blanket
  `*.json` rule cannot swallow legitimate committed data.
- Hard limits: `MAX_TRADE_SIZE`, `MAX_TOKEN_EXPOSURE`, `MAX_IN_FLIGHT_TX`,
  `MAX_DAILY_LOSS`, `MIN_PROFIT`, plus a native-SOL reserve never traded.
- The **kill switch** trips on daily loss, recurring residual balances, repeated
  quote-versus-simulation divergence, or consecutive failures — and **stays
  tripped** across restarts until a human clears `data/kill-switch.json`. There
  is no code path that clears it automatically.
- Token admission fails **closed**: transfer fee, transfer hook, non-transferable,
  permanent delegate, default-frozen, confidential transfers, or any Token-2022
  extension not on a small benign allowlist is a rejection.

---

## Known limits

- Two venues only. Everything else is invisible.
- Two-leg cycles only. No triangular routes.
- WSOL is the only base asset.
- Pools at non-canonical addresses are missed by default discovery.
- PumpSwap pools in mayhem mode are refused: their fee recipients are not modelled.
- Latency is whatever your machine and RPC give you; nothing here makes it faster.
- Jito's free-failure property is taken from their documentation, not measured here.

See `ADVERSARIAL_REVIEW.md` for the full list, including the bugs that were found
and fixed, and `ASSUMPTIONS.md` for everything that could be wrong and how to
re-check it.

---

## Devnet and mainnet

Raydium CP-Swap has a devnet deployment (`DRaycpLY18LhpbydsBWbVJtxpNv9oXPgjRSfpF2bWpYb`).
**PumpSwap does not**, so a devnet run cannot exercise the cross-venue path that
is most of the point. A devnet run therefore tests plumbing, not economics.

The honest alternative is a local validator with mainnet accounts cloned
(`solana-test-validator --clone`), which reproduces real pool state. Neither
substitutes for a small-capital mainnet run, which is why `MAX_TRADE_SIZE` starts
at 0.25 SOL.

No code change is needed between clusters: the cluster is entirely determined by
`RPC_HTTP_URL` and `RPC_WS_URL`.

---

## Going from phase 1 to phase 2

Phase 1 is a free RPC and WebSocket subscriptions. Phase 2 is paid
infrastructure — Geyser/gRPC, a dedicated endpoint. The migration is a
substitution behind two interfaces, `MarketDataFeed` and `TxSender`, not a
rewrite.

**Do not migrate on a hunch.** The decision is arithmetic:

```
monthly gain = current monthly realised PnL
             × (expected land rate with better infra / current land rate − 1)

migrate when   monthly gain > monthly infrastructure cost × 2
```

The safety factor of two exists because the land-rate improvement is an estimate
and the cost is not.

You need three numbers from the ledger, and the report prints all three:

1. **Current monthly realised PnL.** If it is not positive, better infrastructure
   makes you lose money faster. Stop here.
2. **Current land rate**, and specifically the share of failures whose cause is
   latency — `sent-not-landed` and `simulation-unprofitable`, not
   `not-profitable-net`.
3. **The distribution of opportunity lifetimes** from `--observe`. If most
   opportunities live 2 seconds, cutting 200ms of latency buys little. If most
   die in 300ms, it buys everything.

Saying "it will be profitable with a better RPC" without those three numbers is
how people fund an expensive endpoint to lose money at a higher rate.

---

## Moving between modes

### Observe → Paper

- at least 72 continuous hours of observation, including a weekend and a US session;
- at least 100 recorded opportunities (fewer means no distribution to reason about);
- `verify:quoters` passing with zero mismatches;
- a measured opportunity-lifetime distribution whose median exceeds your measured
  end-to-end latency;
- no unexplained decode or quote errors.

### Paper → Live

- simulations succeeding consistently, with `WALLET_PUBLIC_KEY` set so they mean
  something;
- quote-versus-simulation divergence below 25 bps at p95;
- replay over the observed period producing no unexpected losses under the
  configuration you intend to run;
- sizing validated against replay: the chosen size beats the alternatives;
- the kill switch deliberately tripped and cleared at least once, so you know
  what that looks like;
- `npm run setup` completed, and a built transaction inspected by hand;
- every limit set to a number you would be comfortable losing today.

**Passing tests is not readiness.** These are necessary, not sufficient.

---

## When to stop

Written down in advance, because the moment to decide is not the moment you find
out.

- **Realised PnL after 30 days of live running is negative** and the losses are
  `landed-unprofitable` rather than `sent-not-landed`. The strategy is wrong, not
  the infrastructure.
- **Cumulative realised loss reaches your `MAX_DAILY_LOSS` × 5.** Stop and
  re-derive from the ledger rather than adjusting thresholds.
- **`--observe` shows a median opportunity lifetime under your measured latency.**
  Better thresholds cannot fix being late.
- **The kill switch trips on residual balances or quote divergence more than
  once.** The model is wrong somewhere; find it before trading again.
- **Fees exceed the median gross opportunity.** Already close to true on low-cap
  PumpSwap pools. If the report confirms it, the segment is not tradable and no
  amount of tuning changes that.

---

## What to expect

Honestly, and without invented numbers.

**Competition.** Solana MEV is contested by teams with co-located infrastructure,
Geyser feeds and custom senders. On liquid pairs you will not win. This bot is
deliberately aimed at inefficiencies that *persist* rather than ones that appear
instantaneously — but whether such inefficiencies exist in a tradable size is
exactly what has not been established.

**Returns.** *Impossible to estimate seriously before collecting data.* Anyone
quoting a figure without your latency, your capital and your pool set is guessing.
What determines it: the frequency of gaps exceeding roughly 55–150 bps of DEX
fees plus Solana costs, the share surviving your latency, your land rate, and
your capital. `--observe` measures the first two directly, `--paper` bounds the
third, and only live trading resolves it.

**Variance.** Expect long stretches with nothing. A strategy taking a handful of
trades a day has a PnL dominated by a few outcomes; a losing week says almost
nothing, and so does a winning one.

**Capital.** Profit scales with size, but usable size is capped by pool depth on
exactly the low-liquidity pools this targets. Below roughly 1 SOL of working
capital the profit on a viable trade struggles to clear the transaction's fixed
cost. That is arithmetic, not pessimism.

**Costs.** A free RPC is enough to observe and probably not enough to compete.
A paid endpoint costs real money every month whether or not the bot earns
anything.

**When it is probably not profitable.** If your latency exceeds the median
opportunity lifetime; if your capital is small enough that fixed costs dominate;
if the pools you can watch are the ones everyone watches; or if — as the fee
measurement suggests may often be the case — the fees simply exceed the gaps.

**The most likely outcome** is that observation shows the opportunities are
either too rare, too small, or too fast, and that the correct decision is not to
trade. That is a successful use of this bot. The failure mode is trading anyway.
