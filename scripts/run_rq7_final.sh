#!/usr/bin/env bash
# RQ7 final: coverage and stopping behaviour of the asymptotic confidence sequence
# vs naive peeking vs a single pre-registered look (researcher-run; ~40-50 min total,
# single process, ~1.1 GB peak RSS). Every run evaluates asymp, peek and fixed on the
# same streams (same seed). Streams are IID draws; "bootstrap:" resamples the
# centred block residuals of ONE pairing directory (never an experiment dir).
#
# Distributions (representative, not every pairing):
#   heavy  NLHE 6-max 100BB p1   exkurt 186, top-1% share 0.94, 250k source blocks
#   mod    CP 6-max 100BB p2     exkurt  38, top-1% share 0.44, 100k source blocks
#   mild   PLO 6-max 100BB p3    exkurt  20, top-1% share 0.33,  50k source blocks
#   normal / t3 (sd 1)           Gaussian reference / infinite fourth moment
# Horizon n_max = 250k blocks (largest real budget), t* = 100k.
# MC error: null miscoverage at 2000 reps has SE ~0.005 near 0.05 (0.011 near 0.5);
# non-null (1000 reps) stop-rate SE <= 0.016; zero wrong-sign events bound the rate
# below 0.3% (95%).
set -euo pipefail
FHR3=${FHR3:-.venv/bin/fhr3}
O=reports/rq7
mkdir -p "$O"
HEAVY=bootstrap:results/fhr3-nlhe6-100bb-pilot-v1/p1-neutral-vs-loose10
MOD=bootstrap:results/fhr3-cp6-100bb-pilot-v1/p2-neutral-vs-tight
MILD=bootstrap:results/fhr3-plo6-100bb-pilot-v1/p3-aggressive-vs-neutral
COMMON=(--n-max 250000 --t-star 100000 --seed 7)

# 1. null coverage, min_n = 200 (5 runs x 2000 reps)
for spec in "heavy:$HEAVY" "mod:$MOD" "mild:$MILD" "normal:normal" "t3:t3"; do
  name=${spec%%:*}; s=${spec#*:}
  $FHR3 cs-coverage --sampler "$s" --true-mean 0 --scale 1 --reps 2000 --min-n 200 "${COMMON[@]}" \
      --json "$O/null-$name-min200.json"
done

# 2. min-N sensitivity under the null (heavy, mild, t3 x min_n 50/1000/5000; 9 runs x 2000 reps)
for spec in "heavy:$HEAVY" "mild:$MILD" "t3:t3"; do
  name=${spec%%:*}; s=${spec#*:}
  for m in 50 1000 5000; do
    $FHR3 cs-coverage --sampler "$s" --true-mean 0 --scale 1 --reps 2000 --min-n "$m" "${COMMON[@]}" \
        --json "$O/null-$name-min$m.json"
  done
done

# 3. non-null stopping at fixed standardized d (true mean = d * sigma_D), min_n = 200,
#    d = 0.017719 (fixed-N 80% power at 25k blocks) and 0.008859 (at 100k blocks); 1000 reps
nonnull() {  # name sampler mean_d25k mean_d100k
  $FHR3 cs-coverage --sampler "$2" --true-mean "$3" --scale 1 --reps 1000 --min-n 200 "${COMMON[@]}" --json "$O/alt-$1-n25k.json"
  $FHR3 cs-coverage --sampler "$2" --true-mean "$4" --scale 1 --reps 1000 --min-n 200 "${COMMON[@]}" --json "$O/alt-$1-n100k.json"
}
nonnull heavy  "$HEAVY"  0.13643 0.06822    # 2.27 / 1.14 BB/100
nonnull mod    "$MOD"    0.32329 0.16164    # 5.39 / 2.69 BB/100
nonnull mild   "$MILD"   0.48174 0.24087    # 8.03 / 4.02 BB/100
nonnull normal normal    0.017719 0.008859
nonnull t3     t3        0.017719 0.008859

# 4. real-order streams: permutations of the full 250k NLHE corpus (true mean = corpus
#    mean exactly; p3 is a natural near-null), 1000 permutations per pairing
.venv/bin/python scripts/peeking_permutation.py results/fhr3-nlhe6-100bb-pilot-v1 1000 "$O/permutation-nlhe6-250k.json"
# 5. the block-order anecdote on every final corpus
for e in fhr3-nlhe6-100bb-pilot-v1 fhr3-cp6-100bb-pilot-v1 fhr3-plo6-100bb-pilot-v1 fhr3-bomb6-100bb-pilot-v1; do
  $FHR3 sequential "results/$e" --t-star 100000 --json "$O/sequential-$e.json"
done
