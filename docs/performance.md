# Performance

Measured single-process on the development laptop (Apple M-series, 4P+4E cores),
`fhr3 bench --blocks 60` and smoke runs. Aggregate throughput with
`--workers 8` is roughly 3.5–4.5× the single-process figure (efficiency cores,
thermal limits); the 250k NLHE extension sustained ≈ 350 blocks/s.

| config | blocks/s/core | hands/s/core | agent share | notes |
|---|---|---|---|---|
| NLHE 6-max 100BB | ~120 | ~1,440 | 0.25 | engine ~0.75 |
| NLHE 6-max 100BB + all estimators | ~40 | ~470 | 0.10 | estimators 0.57 |
| PLO 6-max 100BB | ~40 | ~480 | 0.24 | ~48% in PokerKit Omaha showdown evaluation |
| Crazy Pineapple 6-max | ~60–80 | ~750–950 | 0.45–0.5 | |
| Bomb pot 6-max | ~17 | ~200 | 0.33 | 71% showdowns, 180 decisions/block |
| Nit Game 6-max | ~10 | ~900 | 0.25 | ~95 hands/block |
| AoF 4-max 8BB | ~180 | ~1,400 | 0.03 | |

Storage: ≈ 100 B/block at 250-block chunks (small smoke chunks show higher
per-file overhead). Serialization ≈ 1–2% of worker time. Peak RSS ≈ 75 MB/process.

Instrumentation: per block `runtime_ms`, `agent_ms`, `estimator_ms`; per run
(manifest `summary.timing_shares_of_worker_time`): agents, estimators,
engine+block bookkeeping, runner overhead, serialization; `fhr3 bench --profile`
for function-level profiles.

## Optimisation decisions
* No compiled code and no PH Evaluator so far: every headline pilot (10k blocks ×
  4–5 pairings) takes minutes, and 250k-block corpora take ≲ 1–2 h on 8 workers,
  except bomb pot and Nit Game (see workflow.md estimates).
* PLO is the only format where hand evaluation is demonstrably material (~48%,
  inside PokerKit's showdown). If PLO corpora must scale to millions of blocks,
  the clean route is a faster PokerKit `hand_types` class (the same mechanism the
  Crazy Pineapple adapter uses), e.g. backed by PH Evaluator — no change to the
  scientific interface. Estimator-side evaluation already uses the fast
  pure-Python evaluator in `games/evaluator.py`.
