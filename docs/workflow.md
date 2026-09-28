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

## Status: final core corpus

The pilots below have been extended. Current corpus sizes, integrity checks and
conclusions are in `final_status.md`. The canonical analysis products are in
`reports/final-analysis/` (the older `reports/pilot-analysis/` and
`reports/figures/` are pre-extension snapshots). The remaining researcher-run jobs
are:

```bash
scripts/run_core_extensions.sh   # 4-max NLHE v2 re-run to 100k + AoF to 50k, then full re-analysis (~10 min + analysis)
scripts/run_rq6_final.sh         # RQ6 minimum estimator set (~15-25 min)
scripts/run_rq7_final.sh         # RQ7 coverage / stopping study (~40-50 min, single process)
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

## 3. RQ6: raw vs all-in EV vs MIVAT vs AIVAT (6-max NLHE 100BB)

`configs/nlhe_6max_100bb_rq6.yaml` has the same root seed as the 250k reference
corpus, so raw D must equal the stored D block for block (a built-in regression
check); estimators use the prior value function.

a) Fit a frozen value function on **separate** training blocks (~1-2 min, one
process, < 1 GB RAM; ~36k hand histories):

```bash
mkdir -p reports/vat
.venv/bin/fhr3 vat-fit --config configs/nlhe_6max_100bb_rq6.yaml \
    --pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral \
    --blocks 0:1000 --training-root-seed 90210 --flop-samples 16 \
    --out reports/vat/nlhe6-100bb-vf.json --write-config configs/nlhe_6max_100bb_rq6_fitted.yaml
```

b) Evaluate (10k blocks per pairing each; ~5-8 min each):

```bash
scripts/run_pilot.sh configs/nlhe_6max_100bb_rq6.yaml
scripts/run_pilot.sh configs/nlhe_6max_100bb_rq6_fitted.yaml
.venv/bin/fhr3 compare results/fhr3-nlhe6-100bb-pilot-v1 results/fhr3-nlhe6-100bb-rq6-v1 \
    results/fhr3-nlhe6-100bb-rq6-v1-fittedvf --json reports/rq6-compare.json
```

Check: raw rows of the RQ6 experiments show `paired; corr(D) +1.000` against the
reference corpus; the analyze report's `estimator ...: mean(est-raw) z` stays
within about ±3 for every estimator and pairing; the control stays exactly 0.
Interpret `var ratio vs raw` only for the fitted value function.

## 4. RQ7: sequential inference

```bash
# on existing corpora (seconds)
.venv/bin/fhr3 sequential results/fhr3-nlhe6-100bb-pilot-v1 --t-star 250000 --json reports/rq7-nlhe6-100bb.json
# coverage on synthetic streams (minutes each; 2000 reps x 100k blocks)
.venv/bin/fhr3 cs-coverage --sampler t3 --true-mean 0 --n-max 100000 --reps 2000 --t-star 100000 --json reports/rq7-cov-t3-null.json
.venv/bin/fhr3 cs-coverage --sampler bootstrap:results/fhr3-nlhe6-100bb-pilot-v1/p2-neutral-vs-tight \
    --true-mean 0 --n-max 100000 --reps 2000 --t-star 100000 --json reports/rq7-cov-boot-null.json
.venv/bin/fhr3 cs-coverage --sampler bootstrap:results/fhr3-nlhe6-100bb-pilot-v1/p2-neutral-vs-tight \
    --true-mean 0.12 --n-max 250000 --reps 1000 --t-star 250000 --json reports/rq7-cov-boot-2bb100.json
```

Expected: `asymp` time-uniform miscoverage ≤ ~0.05 (asymptotic; heavy tails may
need a larger `--min-n`); `peek` far above 0.05; `fixed` final-n miscoverage ≈ 0.05.
(`--true-mean 0.12` BB/block = 2 BB/100 at 6 candidate hands per side.)

## 5. Reproducing / tracing one block

```bash
.venv/bin/fhr3 replay --config configs/plo_6max_100bb.yaml --pairing p2-neutral-vs-tight \
    --block 4711 --trace-dir traces/replay-4711 --compare results
```

## 6. Throughput / profiling

```bash
.venv/bin/fhr3 bench --config configs/<config>.yaml --blocks 200 [--profile]
```
