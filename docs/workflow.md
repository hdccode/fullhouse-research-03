# Workflow: pilots, validation, analysis (researcher-run commands)

Heavy jobs are run from a terminal by the researcher; the coding agent runs only
tests and tiny smoke samples. Commands assume the repo root. Runtime estimates are
for `--workers 8` on the development laptop (see performance.md) and are order of
magnitude only.

## 0. Before any large run

```bash
.venv/bin/python -m pytest          # all invariants (~2 min)
git status && git log -1            # commit first: manifests record git SHA + dirty flag
.venv/bin/fhr3 simulate --config <config> --dry-run
```

Re-running a `simulate` command is always safe (finished chunks are skipped).
Existing v1 corpora (schema `fhr3-block-v1`) remain readable, analysable and
replay-validatable, but cannot be *extended* by v2 code (the lock refuses); new
blocks go under a new experiment_id.

## Status: final core corpus (frozen)

The core raw simulation campaign is complete. Corpus sizes, integrity checks and
frozen conclusions are in `final_status.md`. The authoritative analysis products
are in `reports/final-analysis/`, pinned by `MANIFEST.json`; verify them with
`scripts/freeze_manifest.py --verify`. Pre-extension snapshots are in
`reports/obsolete-pre-extension/`; do not cite them. The remaining researcher-run jobs
are:

```bash
scripts/run_rq6_final.sh         # RQ6 estimator experiment (~25-40 min at 8 workers); section 3
scripts/run_rq7_final.sh         # RQ7 coverage / stopping study (~25-40 min at 8 workers); section 4
```

## 1. Headline format pilots (10,000 blocks per pairing, incl. control)

One command per format (simulate → validate → analyze):

```bash
scripts/run_pilot.sh configs/aof_4max_8bb.yaml       # 4 pairings, ~1-2 min
scripts/run_pilot.sh configs/plo_6max_100bb.yaml     # 4 pairings, ~5 min
scripts/run_pilot.sh configs/cp_6max_100bb.yaml      # 4 pairings, ~3 min
scripts/run_pilot.sh configs/bomb_6max_100bb.yaml    # 4 pairings, ~10-15 min
scripts/run_pilot.sh configs/nit_6max_100bb.yaml     # 5 pairings, ~20-30 min
```

(4-max NLHE and 6-max NLHE 20/50/100BB are already complete.)

Outputs: `results/<experiment_id>/...`, `traces/<experiment_id>/...` (~0.1% of
blocks; PHH for NLHE/PLO/AoF/Nit, JSON traces for Crazy Pineapple and bomb pots),
`reports/<experiment_id>{-validate.json,.json,.txt}`, `reports/ecdf-<experiment_id>/`.

Validation conditions (all formats):
* `simulate` exits 0; manifest summary `invalid: 0`
* `validate`: every pairing `[OK]`, 20 blocks replayed exactly
* `c0-selfplay-control`: sigma_D = 0 (every D exactly 0)
* no non-control pairing with sigma_D = 0 (degenerate pairing)
* Nit Game: `variant_json` truncated counts small (rounds cap at 60 hands)

## 2. Cross-format comparison and figure data

```bash
.venv/bin/fhr3 compare results/fhr3-aof4-8bb-pilot-v1 results/fhr3-nlhe4-100bb-pilot-v1 \
    results/fhr3-nlhe6-20bb-v1 results/fhr3-nlhe6-50bb-v1 results/fhr3-nlhe6-100bb-pilot-v1 \
    results/fhr3-cp6-100bb-pilot-v1 results/fhr3-plo6-100bb-pilot-v1 \
    results/fhr3-bomb6-100bb-pilot-v1 results/fhr3-nit6-100bb-pilot-v1 \
    --json reports/cross-format-compare.json | tee reports/cross-format-compare.txt
.venv/bin/fhr3 figures <same directories> --powersim reports/nlhe6-100bb-ref250k-powersim.json \
    --out reports/figures --workers 8
```

`compare` labels relations strictly: `paired` only for same variant + deal layout
+ protocol + seeds (the stack series); everything else is `shared cards,
different game`, `shared seed material only` or `independent`, with the observed
corr(D). Empirical power per format (optional, minutes each):

```bash
.venv/bin/fhr3 power-sim results/<experiment_id> --n 1000,10000,50000,100000,250000 \
    --deltas 0.5,1,2,5 --reps 2000 --json reports/<experiment_id>-powersim.json
```

## 3. RQ6: estimator variance reduction (USER-RUN)

Script: `scripts/run_rq6_final.sh` (resumable; ends with `scripts/analyze_rq6.sh`). It is
equivalent to the commands below, run in order from the repo root. Durations are
conservative estimates for 8 workers, from single-process benches of the same configs:
NLHE100 fitted ~50 blocks/s/core (estimators 55% of time), 20BB ~118, AoF ~122.

```bash
git status --porcelain -- src pyproject.toml uv.lock        # must print nothing
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_rq6.py tests/test_allin_ev.py tests/test_vat.py   # ~15 s
# value function: separate training seed, frozen + pinned (skip if configs/rq6/nlhe_6max_100bb_fitted.yaml exists)  ~3-6 min
mkdir -p configs/rq6/vf
.venv/bin/fhr3 vat-fit --config configs/nlhe_6max_100bb_rq6.yaml --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --blocks 0:1000 --training-root-seed 90210 --flop-samples 16 --kind aivat --out configs/rq6/vf/nlhe6-100bb-vf.json --write-config configs/rq6/nlhe_6max_100bb_fitted.yaml
.venv/bin/python scripts/verify_value_function.py configs/rq6/nlhe_6max_100bb_fitted.yaml
# A. NLHE 6-max 100BB, fhr3-nlhe6-100bb-rq6-v1-fittedvf                                       ~5-10 min
.venv/bin/fhr3 simulate --config configs/rq6/nlhe_6max_100bb_fitted.yaml --blocks 0:2000 --pairing c0-selfplay-control --workers 8
.venv/bin/fhr3 simulate --config configs/rq6/nlhe_6max_100bb_fitted.yaml --blocks 0:25000 --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --workers 8
# B. NLHE 6-max 20BB all-in EV, fhr3-nlhe6-20bb-rq6-allin-v1                                 ~1-3 min
.venv/bin/fhr3 simulate --config configs/rq6/nlhe_6max_20bb_allin.yaml --blocks 0:10000 --workers 8
# C. AoF all-in EV, fhr3-aof4-8bb-rq6-allin-v1                                               ~4-8 min
.venv/bin/fhr3 simulate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:10000 --pairing c0-selfplay-control --workers 8
.venv/bin/fhr3 simulate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:50000 --pairing p1-prodv2-vs-blend10 --pairing p2-prodv2-vs-heuristic --pairing p3-aggressive-vs-neutral --workers 8
# validation (exact replay incl. estimator columns)                                          ~1-2 min
mkdir -p reports/rq6
.venv/bin/fhr3 validate --config configs/rq6/nlhe_6max_100bb_fitted.yaml --blocks 0:25000 --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral --replay 20 --json reports/rq6/validate-nlhe6-100bb.json
.venv/bin/fhr3 validate --config configs/rq6/nlhe_6max_100bb_fitted.yaml --blocks 0:2000 --pairing c0-selfplay-control --replay 10 --json reports/rq6/validate-nlhe6-100bb-control.json
.venv/bin/fhr3 validate --config configs/rq6/nlhe_6max_20bb_allin.yaml --blocks 0:10000 --replay 20 --json reports/rq6/validate-nlhe6-20bb.json
.venv/bin/fhr3 validate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:50000 --pairing p1-prodv2-vs-blend10 --pairing p2-prodv2-vs-heuristic --pairing p3-aggressive-vs-neutral --replay 20 --json reports/rq6/validate-aof4.json
.venv/bin/fhr3 validate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:10000 --pairing c0-selfplay-control --replay 10 --json reports/rq6/validate-aof4-control.json
# analysis + freeze (scripts/analyze_rq6.sh)                                                 ~2-5 min
for e in fhr3-nlhe6-100bb-rq6-v1-fittedvf fhr3-nlhe6-20bb-rq6-allin-v1 fhr3-aof4-8bb-rq6-allin-v1; do .venv/bin/fhr3 analyze "results/$e" --bootstrap 1000 --json "reports/rq6/analyze-$e.json" | tee "reports/rq6/analyze-$e.txt"; done
.venv/bin/fhr3 compare results/fhr3-nlhe6-100bb-pilot-v1 results/fhr3-nlhe6-100bb-rq6-v1-fittedvf results/fhr3-nlhe6-20bb-v1 results/fhr3-nlhe6-20bb-rq6-allin-v1 results/fhr3-aof4-8bb-pilot-v1 results/fhr3-aof4-8bb-rq6-allin-v1 --json reports/rq6/compare.json | tee reports/rq6/compare.txt
.venv/bin/python scripts/analyze_rq6.py --out reports/rq6 --boot 2000
.venv/bin/python scripts/freeze_rq_manifest.py rq6
# deep analysis: estimator increments, tails / big-pot decomposition, hands at 80% + 95%, efficiency (~10 s)
.venv/bin/python scripts/rq6_deep_analysis.py --out reports/rq6/deep --boot 2000
```

Status: RQ6 has been run (2026-09-29, `ac3cd5f`), every gate passes, and results are in
`final_status.md` section 4.

Pass/fail:
* `analyze_rq6.py` exits 0. That means raw D reproduces the frozen reference block by
  block, `raw_estimator_D` = D, self-play is exactly 0, and |z(est − raw)| ≤ 3 for every
  estimator and pairing.
* `compare` shows `paired; corr(D) +1.000` for every raw row.
* Every validate step reports `[OK]`.

A variance ratio ≤ 0.5 with its CI below 1 is main-text worthy. Ratios ≥ 0.8 or above 1
are flagged in `rq6_summary.csv`.

Outputs, in `reports/rq6/`:
* `rq6_summary.csv` and `rq6_summary.json`;
* `figures/variance_reduction.csv`;
* `analyze-*.json/txt`, `compare.*`, `validate-*.json`;
* `MANIFEST.json`.

After the fit, commit `configs/rq6/nlhe_6max_100bb_fitted.yaml` and
`configs/rq6/vf/nlhe6-100bb-vf.json`: the pinned artifact is part of the experiment.

## 4. RQ7: fixed look vs naive peeking vs asymptotic CS (USER-RUN)

Script: `scripts/run_rq7_final.sh` (resumable; ends with `scripts/analyze_rq7.sh`). One
2,000-rep cell (250k horizon) takes ~70 s at 8 workers; one 1,000-rep cell takes ~35 s
(measured on a 64-rep slice). Total ~25-40 min. Every cell uses seed 20261007, n_max
250,000 and t* 100,000.

```bash
git status --porcelain -- src pyproject.toml uv.lock        # must print nothing
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_rq7.py tests/test_sequential.py
mkdir -p reports/rq7/cells
H=bootstrap:results/fhr3-nlhe6-100bb-pilot-v1/p1-neutral-vs-loose10
M=bootstrap:results/fhr3-cp6-100bb-pilot-v1/p2-neutral-vs-tight
L=bootstrap:results/fhr3-plo6-100bb-pilot-v1/p3-aggressive-vs-neutral
C=(--n-max 250000 --t-star 100000 --seed 20261007 --workers 8 --out-dir reports/rq7/cells)   # array: works in zsh and bash
# null coverage, min_n 200 (5 x 2,000 reps)                                                ~6 min
.venv/bin/fhr3 rq7-cell --name null-heavy-min200    --sampler $H --reps 2000 --min-n 200 "${C[@]}"
.venv/bin/fhr3 rq7-cell --name null-moderate-min200 --sampler $M --reps 2000 --min-n 200 "${C[@]}"
.venv/bin/fhr3 rq7-cell --name null-mild-min200     --sampler $L --reps 2000 --min-n 200 "${C[@]}"
.venv/bin/fhr3 rq7-cell --name null-normal-min200   --sampler normal --reps 2000 --min-n 200 "${C[@]}"
.venv/bin/fhr3 rq7-cell --name null-t3-min200       --sampler t3 --reps 2000 --min-n 200 "${C[@]}"
# min-N sensitivity (9 x 2,000 reps)                                                       ~11 min
for m in 50 1000 5000; do
  .venv/bin/fhr3 rq7-cell --name null-heavy-min$m --sampler $H --reps 2000 --min-n $m "${C[@]}"
  .venv/bin/fhr3 rq7-cell --name null-mild-min$m  --sampler $L --reps 2000 --min-n $m "${C[@]}"
  .venv/bin/fhr3 rq7-cell --name null-t3-min$m    --sampler t3 --reps 2000 --min-n $m "${C[@]}"
done
# non-null stopping (10 x 1,000 reps; fixed look at the 80%-power N)                        ~6 min
for s in heavy:$H moderate:$M mild:$L normal:normal t3:t3; do
  n=${s%%:*}; smp=${s#*:}
  .venv/bin/fhr3 rq7-cell --name alt-$n-n25k  --sampler $smp --effect-d 0.017719 --fixed-n 25000  --reps 1000 --min-n 200 "${C[@]}"
  .venv/bin/fhr3 rq7-cell --name alt-$n-n100k --sampler $smp --effect-d 0.008859 --fixed-n 100000 --reps 1000 --min-n 200 "${C[@]}"
done
# real orderings: 1,000 permutations of the NLHE 6-max p1 corpus                          ~1 min
.venv/bin/fhr3 rq7-cell --name perm-nlhe6p1 --sampler permutation:results/fhr3-nlhe6-100bb-pilot-v1/p1-neutral-vs-loose10 --reps 1000 --min-n 200 "${C[@]}"
# analysis + freeze (scripts/analyze_rq7.sh)                                               ~1 min
for e in fhr3-nlhe6-100bb-pilot-v1 fhr3-nlhe4-100bb-v2 fhr3-cp6-100bb-pilot-v1 fhr3-plo6-100bb-pilot-v1 fhr3-bomb6-100bb-pilot-v1 fhr3-aof4-8bb-pilot-v1 fhr3-nit6-100bb-pilot-v1 fhr3-nlhe6-20bb-v1 fhr3-nlhe6-50bb-v1; do .venv/bin/fhr3 sequential "results/$e" --t-star 100000 --json "reports/rq7/sequential-$e.json" > /dev/null; done
.venv/bin/python scripts/analyze_rq7.py --cells reports/rq7/cells --out reports/rq7
.venv/bin/python scripts/freeze_rq_manifest.py rq7
# deep analysis: invariants + recomputation check, null timing, width inflation, power-matched cost,
# wrong-sign bounds, real-ordering signs, illustrative trajectory (~15 s)
.venv/bin/python scripts/rq7_deep_analysis.py --out reports/rq7/deep
```

Status: RQ7 has been run (2026-09-29, `ac3cd5f`), every check passes, and results are in
`final_status.md` section 4b.

Outputs, in `reports/rq7/`:
* the tables `coverage.csv`, `min_n_sensitivity.csv`, `stopping.csv`,
  `real_permutations.csv` and `real_orderings.csv`;
* `figures/{miscoverage,stopping_times,stopping_cost}.csv`;
* `summary.json`, `cells/*.json/csv` and `MANIFEST.json`.

Monte Carlo uncertainty: the null miscoverage SE is ~0.005 near 0.05 at 2,000 reps (Wilson
CIs are in the tables). At 1,000 reps the decision-rate SE is ≤ 0.016, and zero
wrong-sign events bound that rate below 0.3%.

The earlier peeking evidence (`reports/obsolete-pre-extension/pilot-analysis/peeking_permutation.json`,
100 permutations: ~47% false exclusion) is kept for provenance only. `perm-nlhe6p1`
supersedes it.

### Who ran what

Claude ran, during development:
* the unit and integration tests;
* tiny smoke runs, into a scratch directory, never `results/`: `vat-fit` on 5 training
  blocks, then 15-25 estimator blocks per pairing per setting;
* RQ7 cells of 8-64 replicates;
* single-process benches of 150 blocks;
* read-only analysis of the frozen corpora.

Every publication-scale command above is USER-RUN.

## 5. Reproducing / tracing one block

```bash
.venv/bin/fhr3 replay --config configs/plo_6max_100bb.yaml --pairing p2-neutral-vs-tight \
    --block 4711 --trace-dir traces/replay-4711 --compare results
```

## 6. Throughput / profiling

```bash
.venv/bin/fhr3 bench --config configs/<config>.yaml --blocks 200 [--profile]
```
