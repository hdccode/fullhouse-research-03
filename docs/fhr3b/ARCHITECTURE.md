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
| `historical.py` | loads the historical provenance record; builds a protocol only when every required historical value is supplied |
| `swiss.py` | line-for-line port of the public 2026 engine's pairing, standings, tiebreaks and cut (golden-tested against the vendored reference) |
| `protocol.py` | `TournamentProtocol` (table size, H, R, K, stack rule, pairing, stragglers, round-1 order, scoring, tiebreaks, source pin), `protocol_hash`, R-sweep and fixed-budget generators |
| `match.py` | one table match: `PokerMatchPlayer` (2026 persistent-stack loop or reset-each-hand cash rule, Nit Game rounds), `SyntheticMatchPlayer` (tests), keyed randomness, optional hand logs |
| `schedule.py` | adaptive Swiss schedule vs research-only frozen schedule; assignment validator |
| `runner.py` | `run_tournament` with hard invariant gates; row schemas; analytical digest |
| `fields.py` | modes (`configs/fhr3b/modes`), candidate pools, immutable field manifests, spread and crowded selection rules |
| `calibration.py` | balanced field EV (mu_field), presence-effect matchup matrix, Hodge transitive/cyclic split, matchup selection |
| `selection.py` | deterministic field selection from a frozen pool calibration; field-reference reports |
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

| mode | table | stack rule | why |
|---|---|---|---|
| nlhe6 (the public engine's game) | 6 | `persistent_no_rebuy` | the public engine's match rule |
| nlhe4 | 4 | `persistent_no_rebuy` | the same rule at 4-max |
| plo6 | 6 | `persistent_no_rebuy` | same outer and inner rule as NLHE |
| cp6 | 6 | `persistent_no_rebuy` | same |
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
