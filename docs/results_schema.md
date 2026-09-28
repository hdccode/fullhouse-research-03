# Results: layout, schema, manifests, traces

## Layout

```text
results/<experiment_id>/
  experiment.lock.json              environment + config_hash (immutable)
  runs/<run_id>.json                RunManifest per `simulate` invocation
  <pairing_id>/pairing.lock.json    resolved pairing + agent versions (immutable)
  <pairing_id>/blocks/blocks_<start:09d>_<end:09d>.parquet   rows for [start, end)
traces/<experiment_id>/<pairing_id>/block_<id:09d>/s<seat><A|B>.phh
```

Chunks follow the `chunk_size` grid and are written atomically. A lock mismatch
aborts with `IncompatibleResultsError`; duplicated `(config_hash, pairing_id,
block_id)` rows abort any read.

## Block schema `fhr3-block-v2` (one row per matched block, payoffs in BB)

v2 = v1 + `hands_a`, `hands_b`, `deal_layout`, `estimator_config_hash`,
`estimator_ms`, `allin_ev_hands`, `variant_json`. v1 files are read with those
columns null; `fhr3 validate` replays v1 rows against current code on the shared
columns (cross-schema replay). v2 code refuses to *extend* a v1 experiment.

| column | meaning |
|---|---|
| experiment_id, run_id | ids (run_id = invocation that wrote the row; non-deterministic) |
| block_id, seed | block index; derived 63-bit block seed |
| variant, stack_bb, player_count | game |
| config_hash | hash of environment (experiment id, root seed, game, rng, seed version) |
| pairing_id, pairing_hash | pairing and hash of its resolved agent specs/versions |
| candidate_a[_version], candidate_b[_version] | agent id and `impl+paramhash` |
| reference_population, reference_version | population id and hash of its seats |
| candidate_coupling, reference_coupling | RNG coupling modes |
| block_payoff_a, block_payoff_b | Σ_s X_A,s and Σ_s X_B,s |
| **D** | block_payoff_a − block_payoff_b (null if invalid) |
| played_hands | 2k (Nit Game: total hands of all rounds) |
| candidate_hands_per_side | k (BB/100 = 100·D/k) |
| decision_count | all decisions in the block (incl. discards) |
| runtime_ms, agent_ms | wall time for the block; share spent in agents (non-deterministic) |
| valid, error_code, error_detail | `ILLEGAL_ACTION`, `CHIP_CONSERVATION`, `EXCEPTION:<type>` |
| raw_estimator_D | = D (RawMatchedEstimator) |
| allin_ev_D, mivat_D, aivat_D | estimator D (same estimand); null when not enabled (docs/estimators.md) |
| seat_payoff_a, seat_payoff_b, seat_D | length-k lists, index = candidate seat (0 = SB) |
| showdown_hands, allin_hands | counts over the 2k hands |
| pot_bb_sum, pot_bb_max | pot diagnostics over the 2k hands |
| traced | whether PHH traces were written (non-deterministic across trace policies) |
| hands_a, hands_b | candidate hands played per side (k, except Nit Game rounds) |
| deal_layout | `board-h{hole}-k{players}`; same layout + seeds + protocol => same cards |
| estimator_config_hash, estimator_ms | estimator settings hash; time spent in estimators (non-deterministic) |
| allin_ev_hands | hands with an all-in runout (their payoff was replaced by EV) |
| variant_json | variant diagnostics, e.g. Nit rounds: lengths, truncations, transfers |
| matched_protocol_version | `fhr3-matched-v1` or `fhr3-nit-round-v1` |
| seed_derivation_version, schema_version | versions |

Non-deterministic columns (excluded from replay equality): `run_id`,
`runtime_ms`, `agent_ms`, `estimator_ms`, `traced`.

## Manifest (`runs/<run_id>.json`)

git SHA and dirty flag, Python version, all installed package versions,
`uv.lock` SHA-256, PokerKit version, machine/CPU, full config contents,
config/pairing hashes, argv, start/finish timestamps, seed-derivation / schema /
protocol versions, the work plan, and a summary (blocks, invalid, traced,
aggregate blocks/s).

## Traces

Sparse traces, one file per hand: PHH (PokerKit `HandHistory`) where PokerKit has
a variant (NLHE, PLO, AoF, Nit hands), otherwise FHR3 JSON (`fhr3-trace-v1`:
Crazy Pineapple discards, bomb pots). Selected when
`KeyedStream("trace-selection", seed).random() < trace.rate`, when the block id
is listed in `trace.block_ids`, or when the block is invalid (deterministic
re-run with tracing; failing hands get a `-partial` trace). Any other block can
be traced later with `fhr3 replay --trace-dir`.
