# FullHouse Research #3 — How many hands does it take to know which bot is better?

Simulation and analysis framework for **matched (duplicate-style) evaluation** of
poker agents. The statistical unit is a **matched block**: one chance realization,
candidates A and B each rotated through every seat against a fixed reference
population, reduced to one paired difference `D = Σ_s (X_A,s − X_B,s)`. All
inference (CIs, power, bootstrap, later sequential inference) runs on the
independent sequence `D_1, D_2, …`.

Status: **milestone 1 — 6-max NLHE vertical slice** (PokerKit engine, heuristic
agent family, matched blocks, invariant tests, Parquet + manifests, sparse PHH
traces, resumable/shardable runner, analysis CLI). Other formats are not yet
implemented; see `docs/extending.md` for the order and the recipe.

## Install

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"   # or: uv sync --extra dev
.venv/bin/python -m pytest                              # ~10 s, all cheap
```

## CLI in one screen

```bash
fhr3 simulate --config configs/nlhe_6max_100bb.yaml --dry-run          # inspect plan + hashes
fhr3 simulate --config configs/nlhe_6max_100bb.yaml --blocks 0:10000 --workers 8
fhr3 simulate --config ... --blocks 0:10000 --shard 3/16                # zero-based shard i/n
fhr3 validate --config ... --blocks 0:10000 --replay 20                 # structure + exact replay
fhr3 analyze results/fhr3-nlhe6-100bb-pilot-v1 --json reports/pilot.json
fhr3 power-sim results/fhr3-nlhe6-100bb-pilot-v1/p2-neutral-vs-tight
fhr3 replay --config ... --pairing p2-neutral-vs-tight --block 1234 --trace-dir /tmp/b1234
fhr3 bench --config ... --blocks 100 --profile
```

Re-running `simulate` is always safe: finished chunks are skipped, and a run
whose configuration disagrees with existing results is refused.

## Documentation

| doc | contents |
|---|---|
| `docs/matched_blocks.md` | estimand, matched-block protocol, seat rotation, RNG streams and coupling, seed derivation |
| `docs/architecture.md` | package layout and interfaces |
| `docs/results_schema.md` | Parquet columns, layout on disk, manifests, traces |
| `docs/workflow.md` | pilot launch, validation, analysis, reproducing a block |
| `docs/agents.md` | agent definitions and versioning |
| `docs/extending.md` | adding variants, agents, estimators |
| `docs/assumptions.md` | assumptions that could affect the paper |

## Guardrails

* The simulator knows nothing about confidence sequences or estimators beyond
  the raw difference; analysis never re-runs poker.
* Hands within a block are never treated as independent samples.
* Measured variance is conditional on game config, stacks, agents and reference
  population — not an intrinsic property of a variant.
* This is pairwise comparison against a controlled reference environment; field
  ranking is FHR4. Nothing here describes FullHouse 2027 competition modes.
