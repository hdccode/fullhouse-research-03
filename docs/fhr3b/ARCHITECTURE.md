# FHR3B architecture

FHR3B simulates **whole Swiss tournaments**. One statistical unit is one complete
tournament replication:

```text
field manifest -> round-1 order -> [Swiss tables -> table matches -> chip deltas -> standings] x R
               -> final leaderboard -> top-K qualification
```

## Protocols: historical provenance vs research baseline

| object | file | runnable | meaning |
|---|---|---|---|
| `fhr3b_baseline` | `configs/fhr3b/protocols/fhr3b_baseline.yaml` | yes; every primary experiment | predeclared research design: R0 = 40, H0 = 400, K = 6 (with N = 60 from `lab/lab60_top6.yaml`), seeded round-1 shuffle, raw chip delta, public-engine Swiss rule and tiebreaks |
| `historical_2026_reconstruction` | `configs/fhr3b/protocols/historical_2026_reconstruction.yaml` | no (a record); loaded by `historical.py` | the audited 2026 facts; unknown historical values are `null`; only Experiment D reads it and it refuses while any is null |
| `smoke` | `configs/fhr3b/protocols/smoke.yaml` | yes | correctness only |

Per mode, `fhr3b_baseline` takes the mode's natural table size and stack rule, so its per-mode
protocol hash differs by table size and stack rule. The public 2026 engine is the
*architectural provenance* of the Swiss rule, the scoring and the match mechanics. It is not
the source of R0, N, K or the round-1 order. See `docs/fhr3b/2026_protocol_audit.md`,
section "Historical provenance vs research baseline".

The tournament layer sits on top of FHR3's `GameAdapter`s (PokerKit rules for every mode)
and `Agent`s. It adds no poker rules and copies no agent logic.

## Package `src/fhr3/tournament/`

| module | role |
|---|---|
| `agents.py` | FHR3B-local agent registry; `fhr3b_heuristic` = FHR3A heuristic with correct heads-up blind roles (FHR3A agent code untouched) |
| `historical.py` | loads the historical provenance record; builds a protocol only when every required historical value is supplied |
| `swiss.py` | line-for-line port of the public 2026 engine's pairing, standings, tiebreaks and cut (golden-tested against the vendored reference) |
| `protocol.py` | `TournamentProtocol` (table size, H, R, K, stack rule, pairing, stragglers, round-1 order, scoring, tiebreaks, source pin), `protocol_hash`, R-sweep and fixed-budget generators |
| `match.py` | one table match: `PokerMatchPlayer` (2026 persistent-stack loop or reset-each-hand cash rule, Nit Game rounds), `SyntheticMatchPlayer` (tests), keyed randomness, optional hand logs |
| `schedule.py` | adaptive Swiss schedule vs research-only frozen schedule; assignment validator |
| `runner.py` | `run_tournament` with hard invariant gates; row schemas; analytical digest |
| `fields.py` | modes (`configs/fhr3b/modes`), candidate pools, immutable field manifests, spread and crowded selection rules |
| `calibration.py` | balanced field EV (mu_field), presence-effect matchup matrix (the greedy matchup selection it still contains is retired and unused) |
| `behaviour.py` | behaviour audit: exact replay of calibration rounds with logging proxies; style classes (analysis only) |
| `diagnostics.py` | resolved-parameter vectors and near-duplicate distances; split-half matchup measurement (analysis only) |
| `selection.py` | selection v2: spread (gap constraint + diverse stratified fill), crowded_cutoff (+ diversity audit), style_diverse (style × strength integer allocation); field-reference reports |
| `manifests.py` | seed namespaces, cell identity, engine source hash, analysis version |
| `cells.py` | `Cell` = one experimental condition (adaptive / frozen_replay / adaptive_replay) |
| `store.py` | on-disk layout, locks, atomic per-tournament Parquet, verified-completion checks, array loading |
| `batch.py` | resumable multiprocess execution of a cell |
| `replay.py` | independent re-validation from stored rows, exact replay, hand-log regeneration, R-prefix verification |
| `experiments.py` | matrix and profiles (publication / pilot / smoke) resolved to cells |
| `metrics.py` | repeatability metrics, bootstrap, Wilson intervals, inversions, cutoff curves |
| `analysis.py` | stored results to the report tree (CSV/JSON + MANIFEST) |
| `cli.py` | `fhr3b` entry point |

## Engine inputs

| input | where it comes from |
|---|---|
| game config | `configs/fhr3b/modes/<mode>.yaml` |
| field manifest | `configs/fhr3b/fields/<mode>/<field>.json` |
| protocol | `configs/fhr3b/protocols/*.yaml` plus the lab environment |
| N | the field |
| K, R, H | the protocol |
| tournament seed | seed family + namespace + replicate |
| output location | `--root` |

## Match semantics

Publication modes are **AoF4, NLHE4 and NLHE6**. The other modes remain generic engine support;
PLO is not part of FHR3B.

**NLHE (locked research baseline, public 2026 match semantics).**

* Every Swiss match starts every bot at 100 BB.
* Stacks persist between hands, with no rebuys. A bot at zero is out for the rest of the match.
* Survivors play on with their actual stacks, including short, deep and asymmetric effective
  stacks.
* The next Swiss round is a new match, again from 100 BB.
* The standing is the cumulative chip delta. Match length is 400 hands.

**Within-match history (exposed; public 2026 engine semantics).** Every decision's
`Observation.extra` carries the following keys:

| key | contents |
|---|---|
| `match_history` | rolling tuple of the last 200 actions of *previous* hands of this match, as `(hand, bot_id, street, action, amount)`; the 2026 engine's `MATCH_LOG_MAX_ENTRIES = 200` |
| `seat_bot_ids` | the bot at each position |
| `match_hand_index` | the hand number within the match |

Duplicate-lane identity is **never** bot-visible, in either the action request or the history, because lanes are isolated counterfactual matches. The lane appears only in evaluator metadata (match info, replay hand logs, `lanes.parquet`); a regression test checks corresponding lane states are identical.

The current hand's actions are in `Observation.history`. The shipped FHR3 agents are stateless
and ignore these keys (D5: within-match opponent modelling is under-represented, a stated
limitation), but history-aware agents can use them.

Exposure is **result-neutral**, verified two ways:

* golden ordinary matches from the pre-change engine (`tests/data/fhr3b/golden_ordinary_matches.json`);
* an exact replay of 3,840 completed AoF4/NLHE6 calibration match results.

It changed the engine source hash from `389451b27c2264d2` to `5f5019c69316d098`. The frozen
AoF4/NLHE6 pool calibrations keep the old hash in their locks; NLHE4 calibrates under the new
one.

| mode | table | stack rule | why |
|---|---|---|---|
| nlhe6 (the public engine's game) | 6 | `persistent_no_rebuy` | the public engine's match rule (locked) |
| nlhe4 | 4 | `persistent_no_rebuy` | the same rule at 4-max (locked) |
| plo6 (not in FHR3B) | 6 | `persistent_no_rebuy` | generic support only |
| cp6 | 6 | `persistent_no_rebuy` | generic support |
| aof4 | 4 | `reset_each_hand` | the FHR3 AoF game is 8 BB every hand; carrying 8 BB stacks through 400 hands would make each match a short sit-and-go (a different estimand) |
| bomb6 | 6 | `reset_each_hand` | carried stacks below the 2 BB ante are undefined in the adapter |
| nit6 | 6 | `reset_each_hand` + nit rounds across hands | nit-button state persists within the match; an unfinished round at match end is dropped |

The outer Swiss logic is identical in every mode. **Caveat:** the stack rule differs between
the mode groups, so a cross-mode comparison compares whole formats (game + natural match
rule), not the game alone.

Position mapping: FHR3 fixed positions (0 = SB, m−1 = button). In hand h the bots with
chips, listed in seat order, are `alive`. Position p is `alive[((h mod m) + 1 + p) mod m]`.
That reproduces the 2026 SB/BB/button for every m ≥ 2. For heads-up, PokerKit's button
posts the SB, as in the 2026 engine (tested).

## Duplicate play (Experiment D and matched mu_field): IMPLEMENTED

For a k-player table (k = 4 for AoF4/NLHE4, 6 for NLHE6), one duplicate match is k parallel lanes:

* **Same start, same cards.** Every lane starts from the same initial stacks and reads the same
  keyed chance stream (hand h of every lane gets the same deck).
* **Seat rotation.** Lane ℓ seats the bots in the base order rotated by ℓ, so every bot occupies
  every starting seat exactly once. The base order varies from match to match, using a keyed
  shuffle of the Swiss table, so rotation does not freeze neighbour relationships.
* **Lane isolation.** Each lane's stack trajectory, busts, early ending and bot state evolve
  independently. A bot can bust in one lane and survive in another. Nothing leaks between
  lanes, and stacks are never averaged or merged during play.
* **Aggregation.** A bot's match result is the sum (or mean) of its final chip deltas across the
  k lanes, computed after all lanes finish.
* **Cost accounting.** A duplicate match costs about k ordinary matches. Experiment D compares
  duplicate and ordinary play at **equal played work** (hands simulated / simulator time), for
  example k-lane duplicates at H hands against ordinary matches at k·H hands or k× the rounds.

Implementation:

* **Player.** `match.DuplicateMatchPlayer` runs k lanes, each a full
  `PokerMatchPlayer.play(..., lane=ℓ)`.
* **Seating.** `match.lane_orders` rotates a keyed base seating
  (`KeyedStream("fhr3b-duplicate-base", chance, decision, round, table)`).
* **Isolation.** Each lane has its own agent instances (built by a factory), stacks, busts and
  history. Decision streams are lane-keyed (`"fhr3b-dup-decision", …, lane, hand, bot, ordinal`);
  the deck of hand h is shared.
* **Results.** The match result (the scoring quantity) is the sum of the final lane deltas;
  `hands_played` counts every lane, and `bust_hand` holds the earliest bust over lanes.
* **Per-lane persistence.** Duplicate tournaments also write a compact `lanes.parquet`, one row per
  (round, table, lane, bot): `lane, bot_id, start_seat, chip_delta, hands_played, bust_hand, busted`.
  It has no hand histories. It is covered by the digest, and validation checks that lanes are
  zero-sum, that every bot starts in every seat once, and that lane deltas sum to the table delta.
* **Protocol switch.** `TournamentProtocol.match_format = "duplicate"` turns it on. The field is
  absent from the hash when ordinary, so existing identities are unchanged.
* **Matched calibration.** `CalibrationSpec.match_format` does the same for calibration; matched
  field-reference uses `rounds // k` at equal simulator work.
* **Experiment D cells.** `Profile.duplicate_cells` pairs the ordinary (R0, H0) cell with two
  duplicate variants at equal work:

| variant | AoF4 / NLHE4 (4 lanes) | NLHE6 (6 lanes) |
|---|---|---|
| fewer rounds | 10 rounds × 400 hands | 7 rounds × 400 hands (+5% work, flagged) |
| shorter matches | 40 rounds × 100 hands | 40 rounds × 67 hands (+0.5% work, flagged) |

  Seeds are shared. The analysis reports actual simulated hands per tournament and the work
  ratio (`duplicate_play.csv`).

## Reference rankings

* **`mu_field`**: long-run balanced performance against the controlled field, from **matched**
  evaluation. `field-reference` plays k-lane duplicate matches at random tables
  (`matrix.yaml: calibration.field_reference.match_format: duplicate`) inside frozen fields only.
  Reported on the ordinary-match scale, `mu_field = mean(lane_sum) / k`; every ranking,
  comparison and accuracy metric uses this normalised value. Per-lane outcomes are stored under
  `calibration/<id>/lanes/` and re-validated before use. The nine field references share one
  seed (common random numbers), so they are coupled, not independent replications.
* **`mu_swiss`**: expected Swiss performance, from many complete tournaments (`swiss-reference`
  namespace).

The analysis reports, for both, accuracy (`reference_accuracy.csv`: overlap with the reference
top 6, Kendall tau) and the repeatability metrics.

## Rounds horizon

R0 = 40 is the initial horizon. `fhr3b run --horizon R` creates the R-round cell. Seeds do not
depend on R, so its first 40 rounds reproduce the 40-round cell exactly, and checkpoints are
read from prefixes (`round_checkpoints` in `matrix.yaml`: 5 … 40, 60, 80, 120).

## Randomness and common random numbers

| stream | key |
|---|---|
| tournament seed | `derive_seed("fhr3b-tournament", seed_family, namespace, replicate)` |
| round-1 order | `KeyedStream("fhr3b-initial-order", order_seed)` shuffle |
| cards | `KeyedStream("fhr3b-chance", chance_seed, round, table, hand)` |
| decisions | `DecisionRNG("fhr3b-decision", decision_seed, round, table, hand, bot_id, ordinal)` |
| frozen/adaptive replays | new chance/decision seeds from `("fhr3b-replay", family, ns, source, j)`; the round-1 order is the source's |
| calibration | `derive_seed("fhr3b-calibration", family, namespace)`; partitions keyed by round |

Seeds do not depend on R, H or K. Consequences:

* **R sweep (paired, exact nesting).** The R-round tournament with replicate i equals the
  first R rounds of the R0 tournament with replicate i, because Swiss pairing after round r
  depends only on rounds ≤ r. The R sweep is therefore read from the stored post-round
  standings of the R0 runs at no extra simulation cost. `validate --prefix` re-runs shorter
  cells and checks the identity. It also holds exactly in tests on real poker.
* **Fixed budget (paired by replicate).** All allocations share tournament seeds, so round 1
  has identical tables, and hand h of a round-1 match is identical across H while stacks
  agree. From round 2 on the tables diverge, so the coupling is partial. No coupling is
  forced beyond what the keys give.
* **Frozen vs adaptive (paired by source and replay).** Frozen replay j and adaptive replay j
  of source s share cards, decision seeds and round-1 tables. They differ only in whether
  later tables react to results.
* **Independent:** different fields, different modes, and every reference namespace.

## Invariants (hard gates)

Checked while running (`runner.py`) and again independently from stored rows
(`replay.validate_tournament_rows`):

* every bot sits exactly once per round;
* nobody sits twice at one table;
* table sizes are exactly what the Swiss rule produces (≤ 10 seats, ≥ 2);
* no table is duplicated;
* one score update per bot per round;
* zero-sum tables, and no rake;
* tournament-wide chip conservation after every round;
* pre-round and post-round standings recomputed with the reference rule;
* the adaptive assignment equals `swiss_pairing(pre-round standings)`, with round 1 from the
  seeded order;
* final score = sum of round deltas;
* the final ranking is reproducible;
* the top-K flags match the recomputed cut;
* the digest matches;
* frozen replays use exactly the source schedule;
* every hand conserves chips; persistent scores equal stack deltas.

## Output schema (per tournament, `results/fhr3b/<cell_id>/tournaments/tNNNNNN/`)

`tables.parquet`, one row per (round, table, seat):

* `tournament_id, replicate, round, table_index, seat, table_size, bot_id`
* `pre_score, pre_rank` (before round 1, `pre_rank` is the seeded order)
* `match_seed, chip_delta, hands_played, bust_hand`
* `post_score, post_rank, post_best_match_delta`

These rows give the full schedule, the pre- and post-round standings for every round, and
the R-prefix leaderboards.

`lanes.parquet` (duplicate matches only): one row per (round, table, lane, bot), as described
under "Duplicate play".

`final.parquet`, one row per bot:

* `bot_id, final_score, final_rank, qualified`
* `matches_played, best_match_delta` (tiebreak values), `dense_rank`

`manifest.json` is the commit marker, written last and atomically:

* ids: `tournament_id, cell_id, replicate, schedule_kind`
* `seeds` (tournament, order, chance, decision), `protocol_hash`, `identity_hash`
* `R, H, N, K`
* `final_ranking, qualified`
* `digest` (sha256 of the row values), `schedule_digest`
* `hands_played, runtime_s`

`cell.lock.json` holds the full identity, the cell definition (protocol, field manifest,
mode), and `engine_source_hash`.

Hand-level logs are not stored. `fhr3b replay-hands` regenerates any table match exactly
and checks it against the stored deltas.

## Identity and hashes

| hash | covers |
|---|---|
| `protocol_hash` | every result-relevant protocol field (notes excluded) |
| `field_hash` | every bot's `bot_id, kind, params`, resolved agent version (implementation + params hash), and the mode |
| `game_hash` | the `GameConfig` |
| `identity_hash` (cell) | engine versions, seed-derivation version, kind, mode, protocol, field hash, seed family, namespace, and for replays the source cell and J |
| `engine_source_hash` | result-relevant modules (rng, eval/matched, games, agents, tournament engine modules). Recorded in the lock; a mismatch refuses to extend a cell unless `--allow-source-change` is given, and `validate --replay` must then confirm old tournaments still replay exactly |
| `ANALYSIS_VERSION` | recorded in every report MANIFEST |
| architectural provenance | `protocol.source` pins the public 2026 engine repository, commit and file hash (`role: architectural provenance only`) |
| historical record | `historical_2026_reconstruction` record hash (`fhr3b audit`); not part of any research identity |

Replication counts are not part of any identity. Extending broad → flagship reuses the same
cells, and verified tournaments are skipped.

## Resumability

* The unit of work is one tournament (calibration: a chunk of rounds).
* A tournament counts as done only if its manifest exists and the digest recomputed from its
  Parquet rows matches.
* Any worker count, order or interruption gives byte-identical Parquet files (tested).
