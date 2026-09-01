# Assumptions

Everything this bot relies on that could be wrong, where it came from, and how
to re-check it. An assumption that is not on this list and not verified in code
is a bug.

**Verification dates are 2026-08-31 unless stated otherwise.** Anything about a
third-party program can change without notice; the two automated checks below
are what keep this file honest:

- `npm test` — fuzzes the PumpSwap quoter against pump.fun's own SDK, so a math
  change on their side breaks the build on the next `npm update`.
- `npm run verify:quoters` — replays real recent mainnet swaps through our
  quoters and requires an exact match against the programs' own emitted events.
  Run it before every live session. It exits non-zero on any mismatch.

Confidence levels: **verified** (checked against the program, its source, or its
own emitted output), **documented** (stated by the project's official docs but
not independently reproduced here), **assumed** (believed, not proven — every
one of these is a live risk).

---

## Raydium CP-Swap

| # | Assumption | Confidence | Source and how to re-check |
|---|---|---|---|
| RAY-1 | Program id is `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C` | verified | `declare_id!` in `programs/cp-swap/src/lib.rs` (non-devnet branch), and the IDL published at the program's own on-chain IDL account. Devnet is a different id, `DRaycpLY18LhpbydsBWbVJtxpNv9oXPgjRSfpF2bWpYb`. |
| RAY-2 | Swap math is exactly `CurveCalculator::swap_base_input` / `swap_base_output`: trade fee by CEILING division, creator fee split off by FLOOR, curve output by FLOOR (input-exact) or CEILING (output-exact) | verified | Transcribed from `curve/calculator.rs`, `curve/constant_product.rs`, `curve/fees.rs`. Reproduced exactly against real swaps by `verify:quoters`. |
| RAY-3 | Effective reserves are the vault balances MINUS accrued protocol, fund and creator fees held in the same vaults | verified | `PoolState::vault_amount_without_fee`. This is the single biggest difference from a naive `x*y=k` and is worth re-reading if quotes start drifting. |
| RAY-4 | `PoolState` is `#[repr(C, packed)]` zero-copy, so field offsets are sequential with no alignment padding | verified | The attribute in `states/pool.rs`, plus `PoolState::LEN == 637` which our offsets reproduce. |
| RAY-5 | The deployed program matches the open-source `master` we transcribed | verified | The on-chain IDL is v0.2.0 and its `AmmConfig` and `PoolState` field lists match the source field-for-field, including `creator_fee_rate`, `creator_fee_on` and `enable_creator_fee`. Re-check with `npm run verify:quoters`. |
| RAY-5b | An Anchor discriminator does NOT identify the program that owns an account | verified by counterexample | `sha256("account:<TypeName>")[0..8]` depends only on the type name, so any program with a `PoolState` collides. Mainnet account `HrWp3QR3hNeVy6tEZtcpsjwEiGgKJuL1NDP84EaaU2Nh` (owned by `REALQqNEomY6cQGZJUGwywTBD2UmDT32rZcNnfxQ5N2`) carries Raydium's PoolState discriminator. Every decoder therefore verifies the owner first; see `test/feed/decoderOwnership.test.ts`. |
| RAY-6 | Pool, vault, observation and config addresses are PDAs with the seeds in `src/screener/pdas.ts` | verified | `instructions/initialize.rs` and `admin/create_config.rs`. NOTE: the source explicitly allows a pool at a plain keypair address instead of the PDA, so PDA-based discovery finds most pools but not all — `deepScanPoolsForMint` covers the rest. |

## PumpSwap and the pump fee program

| # | Assumption | Confidence | Source and how to re-check |
|---|---|---|---|
| PS-1 | Program ids `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` (AMM) and `pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ` (fees) | verified | Both publish an Anchor IDL at their own on-chain IDL account; `scripts/fetch-idl.mjs` re-fetches them. |
| PS-2 | Swap math matches `@pump-fun/pump-swap-sdk` `buy.ts` / `sell.ts`, including the `-1` base-unit adjustment inside the buy path and the CEILING rounding in `fee()` | verified | Fuzzed against the SDK over 12 000 randomised states in `test/quoters/pumpSwap.reference.test.ts`, and reproduced against real swaps by `verify:quoters`. Note the comment in the SDK's `buy.ts` says "floor" while the code calls `ceilDiv`; the code is what the chain does. |
| PS-3 | Fees for canonical pump pools come from a market-cap tier ladder, selected by the algorithm in pump's `FEE_PROGRAM_README.md`; non-canonical pools pay `flat_fees` | documented + verified | The algorithm is published by pump.fun; the tiers are read live from the fee config account rather than hardcoded. `verify:quoters` cross-checks the tier we picked against the bps in the program's own event. |
| PS-4 | A pool is canonical iff `pool.creator == PDA(["pool-authority", base_mint], PUMP_PROGRAM)` | documented | pump's `isPumpPool`, quoted verbatim in their docs. |
| PS-5 | `Pool.virtual_quote_reserves` is an `i128` at offset 245 | assumed, guarded | Present in the SDK's IDL but NOT in the IDL the program publishes on-chain. Live pool accounts are 301 bytes, past the 245 the older layout needs, and Anchor zero-initialises reserve space, so reading it yields the real value if the field exists and 0 if it does not — 0 being the SDK's own default. The decoder additionally rejects an implausible magnitude rather than trusting reserve bytes. **Re-check if pump ships a layout change.** |
| PS-6 | The `cashback` and `buyback` fee legs in the sell event do NOT reduce what the trader receives | verified by measurement | These appear in the deployed program's event but not in pump's published quote helpers, which looked like it could make every quote wrong. Measured against real transactions, the buyback leg is consistently exactly half the protocol fee and our quote still matched `user_quote_amount_out` to the lamport. Recorded as a measurement, not a belief: `verify:quoters` prints these legs whenever they are non-zero. |
| PS-7 | Pools in "mayhem mode" pay their protocol fee to a reserved recipient set we do not model | verified | The field is in the IDL and the SDK selects a different recipient list for it. The transaction builder REFUSES such pools rather than guessing. |

## Token-2022

| # | Assumption | Confidence | Source |
|---|---|---|---|
| T22-1 | Extension TLV starts at offset 166, after the account-type byte at 165 | documented | Token-2022 account layout. Our parser stops rather than guessing on a truncated entry. |
| T22-2 | `TransferFee::calculate_fee` = `min(ceil(amount * bps / 10_000), maximum_fee)`, and `calculate_epoch_fee` picks the newer schedule when `epoch >= newer.epoch` | documented | Token-2022 source. In practice the risk filter rejects any mint charging a transfer fee, so this path is defence in depth. |
| T22-3 | Extension type ids match `@solana/spl-token` 0.4.15's `ExtensionType` | verified | Enumerated from the installed library. The risk filter fails CLOSED on any id not on a small benign allowlist, so an extension invented after this was written is a rejection rather than a surprise. |

## Solana fees and transactions

| # | Assumption | Confidence | Source |
|---|---|---|---|
| SOL-1 | Priority fee = `ceil(compute_unit_limit * compute_unit_price / 1e6)` | assumed, checked at runtime | Not hardcoded from memory: `verifyPriorityFeeModel` compares this formula against `getFeeForMessage` for the exact message being sent. |
| SOL-2 | The base fee per signature is whatever the cluster says | verified by construction | Read at startup by pricing a minimal one-signature message with `getFeeForMessage`. Nothing hardcodes 5000 lamports. |
| SOL-3 | Fees are charged only for transactions that are INCLUDED in a block | documented | Drives the cost model's distinction between "reverted" (pays fees) and "not included" (pays nothing). Getting this backwards makes every expected value pessimistic. |
| SOL-4 | A serialized transaction must be at most 1232 bytes | documented | The builder measures the real serialized size plus the signature and refuses to send an oversized transaction rather than discovering it at send time. A Raydium+PumpSwap cycle lands close to the limit; an address lookup table is the remedy. |
| SOL-5 | Token account rent exemption is whatever `getMinimumBalanceForRentExemption(165)` returns | verified by construction | Queried, never assumed. Treated as locked capital, not as a cost, because it is refundable. |

## Jito

| # | Assumption | Confidence | Source |
|---|---|---|---|
| JITO-1 | Endpoints are `/api/v1/bundles` (`sendBundle`), `/api/v1/getTipAccounts`, `/api/v1/getBundleStatuses`, `/api/v1/getInflightBundleStatuses` on `https://<region>.mainnet.block-engine.jito.wtf` | documented | docs.jito.wtf, read 2026-08-31. The URL is NOT defaulted in code: it must be configured explicitly. |
| JITO-2 | A bundle whose transactions do not all succeed is rejected and never included, so a failed attempt costs nothing | documented | This is the single most economically significant assumption in the file. It is what makes a low land rate survivable, so it is exposed as `revertCostsFees` on the sender rather than buried in a constant. **If it is wrong, every expected value computed with Jito enabled is too optimistic.** Verify it empirically before trusting it: run live with Jito on, and check that failed attempts show no fee in the wallet's transaction history. |
| JITO-3 | No auth keypair is required for default sends | documented | docs.jito.wtf. |
| JITO-4 | Rate limit is 1 request per second per IP per region; minimum tip 1000 lamports | documented | docs.jito.wtf. The sender self-throttles to respect it. |
| JITO-5 | Tip accounts are those returned by `getTipAccounts` | verified by construction | Fetched at startup from the block engine itself; the sender refuses to operate if the call fails, rather than falling back to a hardcoded address. |

## Economic assumptions — the ones most likely to be wrong

| # | Assumption | Confidence | How to check |
|---|---|---|---|
| ECON-1 | Two-leg WSOL cycles between PumpSwap and Raydium CP-Swap are the right hunting ground | **assumed** | This is the strategy bet, and it is unproven. `--observe` is the experiment that tests it. A first discovery run found exactly ONE of the ten most active mints had the two or more quotable pools a cycle needs. |
| ECON-2 | Fees leave room for a profit | **measured, and discouraging** | PumpSwap canonical pools charge 125 bps per leg below a 420 SOL market cap, decaying to 30 bps at the top of the ladder; Raydium CP-Swap is typically 25 bps. A round trip therefore costs roughly 55–150 bps in DEX fees alone, before any Solana cost. **The low-cap long tail the brief targets is the most expensive segment to trade, not the cheapest.** The gap has to exceed that before anything else matters. |
| ECON-3 | Opportunities survive long enough for us to act | **unknown** | Precisely what `--observe` measures, and the reason the survival probes exist. If the median opportunity is gone in under 200ms, this is a speed game and this bot loses it. |
| ECON-4 | The starting `MIN_PROFIT` of 0.0008 SOL is roughly right | **assumed, not tuned** | Chosen before any data existed. Compare against the realised distribution in `npm run report` and move it deliberately. |
| ECON-5 | The screener's weights rank pools usefully | **assumed, not calibrated** | The weights are a starting point. Calibrate by comparing realised PnL per pool against the score that pool had at the time. Any claim that they are tuned is false until that comparison has been run. |
| ECON-6 | The land-rate prior (5% success) is conservative enough | **assumed** | Deliberately pessimistic so a new segment must earn its optimism. If real land rates come out far higher, the prior is costing opportunities; if far lower, it was not pessimistic enough. |

## Environment

| # | Assumption | Confidence | Notes |
|---|---|---|---|
| ENV-1 | Latency from the machine running the bot is 150–500ms | **assumed** | Taken from the brief, never measured. The observation report's "practical latency ceiling" line is what turns this into a number. Latency measured in a cloud container is NOT the operator's latency. |
| ENV-2 | The configured RPC allows enough `accountSubscribe` for `MAX_WATCHED_POOLS * 3 + 2` | assumed | The config refuses to start if the arithmetic does not fit the configured cap, but the cap itself is whatever you tell it. Check your provider's actual limit. |
| ENV-3 | `getProgramAccounts` is unusable on a free public endpoint | **verified by failure** | A single scan of either program failed to complete against the public endpoint. This is why discovery derives addresses locally instead. |
