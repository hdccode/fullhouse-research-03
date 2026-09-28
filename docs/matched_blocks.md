# Matched blocks, randomness and seeds

Protocol id: `fhr3-matched-v1` (column `matched_protocol_version`).
Seed derivation id: `fhr3-seed-v1` (column `seed_derivation_version`).

## Estimand

For candidates A, B, a fixed reference population R, and a game configuration G:

    Δ = E[D] / k      BB per candidate hand      (×100 → BB/100)

where D is the block difference below and k the player count. All estimators
(raw, and later all-in-EV / MIVAT / AIVAT) must target this same quantity.

## One block (k-player table, seats 0..k−1, seat 0 = SB, seat k−1 = button)

1. `block_seed = derive_seed("fhr3-block", root_seed, block_id)`.
2. One deck is shuffled from `KeyedStream("chance", block_seed, salt_chance)`.
   It becomes a `Deal`: hole cards bound to **seats** (`deck[2p:2p+2]` → seat p),
   then a fixed runout (burn, flop, burn, turn, burn, river).
3. For every candidate seat `s = 0..k−1` and side `X ∈ {A, B}` one hand is played
   on that same Deal:
   * candidate X sits in seat s (gets seat s's cards and position);
   * reference agent `j` sits in seat `(s + 1 + j) mod k`, so the reference
     line-up *relative to the candidate* is the same in every hand;
   * every seat starts with the configured stack (cash-game reset; no carry-over).
4. `X_{X,s}` = candidate X's net chips / big blind in seat s.
   `D_s = X_{A,s} − X_{B,s}`,  `D = Σ_s D_s`.

→ 2k played hands per block (12 at 6-max, 8 at 4-max), k candidate hands per side.

The A-hand and B-hand for seat s differ **only** in which candidate occupies seat
s. Any difference in outcome is caused by A and B acting differently (and the
downstream reactions of the reference agents).

Seat components `D_s` are stored (`seat_D`) for diagnostics, but they are *not*
independent (they share one deck and are positively/negatively correlated), so
all inference uses `D`.

## Nit Game protocol (`fhr3-nit-round-v1`)

Each seat/side plays one complete nit round (see variants.md) from the empty
button state. Hand h uses `KeyedStream("chance", seed, salt_chance, "hand", h)`
and the dealer rotates one seat per hand; decision keys append `("hand", h)` and
use table seats. The block is still one independent observation; hands and
rounds inside it are not.

## Decision randomness

Agents receive a `DecisionRNG`, a keyed counter-based stream:

| actor | key |
|---|---|
| candidate | `("decision", seed, "candidate", salt_candidate, s, ordinal)` |
| reference | `("decision", seed, "reference", salt_reference, s, acting_seat, ordinal)` |

`ordinal` is the acting seat's decision index within that hand.

* **`candidate_coupling: shared`** (default) — A and B read identical uniforms at
  their n-th decision in the matched hands (common random numbers). Each policy's
  marginal distribution is unchanged because each still receives Uniform(0,1)
  draws; only the *joint* distribution of (A-hand, B-hand) is coupled. Under
  `independent` the label becomes `candidate:A` / `candidate:B`.
* **`reference_coupling: shared`** (default) — a reference seat reads the same
  uniforms in the A-hand and the B-hand, so references react identically as long
  as the action sequence is identical. `independent` adds `:A`/`:B`.

Consequences, all covered by tests:

* A vs an identical copy of A gives **D = 0 exactly** under shared coupling.
* Swapping A and B negates D (and each `D_s`) exactly under shared coupling.
  Under independent candidate coupling it negates only in distribution.
* Changing `salts.reference` changes only reference draws; `salts.candidate`
  only candidate draws; `salts.chance` only the deck.

Policies following `DistributionAgent` consume exactly one uniform per decision
(inverse-CDF selection), which maximises A/B coupling.

Estimator streams (all-in EV Monte Carlo, AIVAT flop samples) are keyed by
`("hand", seed, s[, h])` without the side, so they are shared between the A- and
B-hand of a seat (exact self-play zero and swap negation for every estimator).

## Seeds and hashing

* All randomness derives from BLAKE2b over a type-tagged, length-prefixed key
  encoding (`fhr3/rng.py`). No Python `hash()`, no global RNG, no dependency on
  numpy/stdlib stream stability. Golden values are pinned in `tests/test_rng.py`.
* The deck depends only on `(root_seed, block_id, salt_chance)` — **not** on the
  pairing, agents or stack depth. Blocks with the same id are chance-matched
  across pairings and across stack configurations sharing a root seed (useful
  for the stack-sensitivity study; note the induced cross-pairing correlation).
* Decision streams depend on `block_seed` but not on pairing id.

## Reproducing any block

A row's `(config file, pairing_id, block_id)` fully determines it:

```bash
fhr3 replay --config configs/nlhe_6max_100bb.yaml --pairing p2-neutral-vs-tight \
    --block 4711 --trace-dir traces/replay-4711 --compare results
```

This recomputes the block, writes 2k PHH files and checks every deterministic
column against the stored row.
