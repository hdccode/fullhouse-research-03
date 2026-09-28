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

## Block schema `fhr3-block-v1` (one row per matched block, payoffs in BB)

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
| played_hands | 2k |
| candidate_hands_per_side | k (BB/100 = 100·D/k) |
| decision_count | all decisions in the 2k hands |
| runtime_ms, agent_ms | wall time for the block; share spent in agents (non-deterministic) |
| valid, error_code, error_detail | `ILLEGAL_ACTION`, `CHIP_CONSERVATION`, `EXCEPTION:<type>` |
| raw_estimator_D | = D (RawMatchedEstimator) |
| allin_ev_D, mivat_D, aivat_D | null until those estimators exist (RQ6) |
| seat_payoff_a, seat_payoff_b, seat_D | length-k lists, index = candidate seat (0 = SB) |
| showdown_hands, allin_hands | counts over the 2k hands |
| pot_bb_sum, pot_bb_max | pot diagnostics over the 2k hands |
| traced | whether PHH traces were written (non-deterministic across trace policies) |
| matched_protocol_version, seed_derivation_version, schema_version | versions |

Non-deterministic columns (excluded from replay equality): `run_id`,
`runtime_ms`, `agent_ms`, `traced`.

## Manifest (`runs/<run_id>.json`)

git SHA and dirty flag, Python version, all installed package versions,
`uv.lock` SHA-256, PokerKit version, machine/CPU, full config contents,
config/pairing hashes, argv, start/finish timestamps, seed-derivation / schema /
protocol versions, the work plan, and a summary (blocks, invalid, traced,
aggregate blocks/s).

## Traces

Sparse PHH (PokerKit `HandHistory`), one file per hand. Selected when
`KeyedStream("trace-selection", seed).random() < trace.rate`, when the block id
is listed in `trace.block_ids`, or when the block is invalid (deterministic
re-run with tracing; failing hands get a `-partial` trace). Any other block can
be traced later with `fhr3 replay --trace-dir`.
