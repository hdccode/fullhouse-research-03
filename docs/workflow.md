# Workflow: pilots, validation, analysis

Heavy jobs are run by the researcher from a terminal; the coding agent only runs
tests and tiny smoke samples. All commands assume the repo root and the venv
(`source .venv/bin/activate`, or prefix with `.venv/bin/`).

## 1. Before any large run

```bash
python -m pytest                                               # all invariants, ~10 s
fhr3 simulate --config configs/nlhe_6max_100bb.yaml --dry-run   # hashes, plan, output dirs
git status                                                      # manifests record the SHA and dirty flag
```

Commit before running, so the manifest's `git.sha` identifies the code exactly.

## 2. 6-max NLHE 100BB pilot (10,000 blocks × 3 pairings + self-play control)

```bash
fhr3 simulate --config configs/nlhe_6max_100bb.yaml --blocks 0:10000 --workers 8
```

* Output: `results/fhr3-nlhe6-100bb-pilot-v1/<pairing>/blocks/*.parquet` (40 chunks
  per pairing), manifest in `results/fhr3-nlhe6-100bb-pilot-v1/runs/`, about 40 traced
  blocks (≈480 PHH files) under `traces/fhr3-nlhe6-100bb-pilot-v1/`.
* Size: 40,000 blocks = 480,000 played hands, a few MB of Parquet.
* Interrupted? Re-run the identical command; finished chunks are skipped.
* Split across machines/sessions: add `--shard i/n` (zero-based); shards partition
  the chunk list exactly.

Then validate and analyse:

```bash
fhr3 validate --config configs/nlhe_6max_100bb.yaml --blocks 0:10000 --replay 20 \
    --json reports/nlhe6-100bb-pilot-validate.json
fhr3 analyze results/fhr3-nlhe6-100bb-pilot-v1 --bootstrap 2000 \
    --json reports/nlhe6-100bb-pilot.json --ecdf-dir reports/ecdf-nlhe6-100bb
fhr3 power-sim results/fhr3-nlhe6-100bb-pilot-v1/p1-neutral-vs-loose10 \
    results/fhr3-nlhe6-100bb-pilot-v1/p2-neutral-vs-tight \
    results/fhr3-nlhe6-100bb-pilot-v1/p3-aggressive-vs-neutral \
    --n 1000,10000,50000,100000,300000 --deltas 0.5,1,2,5 --reps 2000 \
    --json reports/nlhe6-100bb-pilot-powersim.json
```

The analysis report gives, per pairing: mean D with t- and bootstrap CIs, σ_D,
tail quantiles, skew/kurtosis, the share of variance from the top 1%/0.1% of
blocks, per-hand showdown/all-in/pot diagnostics, per-core throughput, storage per
block, and required blocks/hands for Δ ∈ {0.25, 0.5, 1, 2, 5} BB/100 at 80%/95%
power. `power-sim` output is labelled `synthetic_location_shift`: it resamples
centred block residuals, so it describes the *statistics*, not a real matchup.

### Sanity checks for the pilot

* `invalid` = 0 everywhere (the exit code of `simulate` is 1 otherwise).
* `c0-selfplay-control`: every D exactly 0, σ_D = 0.
* `validate`: all OK, replayed blocks match exactly.
* p1–p3: a large share of blocks with D = 0 (~70–90%); very heavy tails (excess
  kurtosis ≫ 3; most variance from a few % of blocks). A 200-block smoke sample
  gave σ_D ≈ 10–12 BB/block; the pilot is what actually estimates it.
* Per hand: showdown ≈ 0.13, all-in ≈ 0.03, mean pot ≈ 10–11 BB.
* Throughput ≈ 90–120 blocks/s per core.

## 3. Reproducing / tracing one block

```bash
fhr3 replay --config configs/nlhe_6max_100bb.yaml --pairing p2-neutral-vs-tight \
    --block 4711 --trace-dir traces/replay-4711 --compare results
```

## 4. Throughput / profiling

```bash
fhr3 bench --config configs/nlhe_6max_100bb.yaml --blocks 200 --profile
```

Profile before optimizing: at milestone 1, ~45% of the time is PokerKit state
transitions (about half of which is its showdown hand evaluation), ~25% is agents.
