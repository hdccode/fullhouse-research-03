#!/usr/bin/env bash
# RQ7 final (USER-RUN): fixed-N single look vs naive peeking vs asymptotic CS, all on the
# SAME block streams (fhr3 rq7-cell). Horizon 250,000 blocks, t* = 100,000, alpha 0.05.
#   distributions  heavy    = IID bootstrap of NLHE 6-max 100BB p1 blocks (exkurt ~186)
#                  moderate = Crazy Pineapple p2 (~38)      mild = PLO p3 (~20)
#                  normal, t3 (unit SD)
#   null           5 distributions x min_n 200, 2,000 reps       (MC SE ~0.005 at 5%)
#   min-N          heavy / mild / t3 x min_n 50, 1,000, 5,000, 2,000 reps
#   non-null       5 distributions x d = 0.017719 (fixed-N 80% power at 25k blocks; fixed look
#                  at 25k) and d = 0.008859 (100k; fixed look at 100k), 1,000 reps
#   real orderings 1,000 random permutations of the full NLHE 6-max p1 corpus (true mean =
#                  corpus mean), then fhr3 sequential on every frozen corpus (in analyze_rq7.sh)
# One seed (20261007) for every cell: identical streams across methods and across min_n.
# Resumable: finished cells (same design) are skipped. ~25-40 min at 8 workers.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
FHR3=.venv/bin/fhr3
PY=.venv/bin/python
W=${WORKERS:-8}
O=reports/rq7/cells
HEAVY=bootstrap:results/fhr3-nlhe6-100bb-pilot-v1/p1-neutral-vs-loose10
MOD=bootstrap:results/fhr3-cp6-100bb-pilot-v1/p2-neutral-vs-tight
MILD=bootstrap:results/fhr3-plo6-100bb-pilot-v1/p3-aggressive-vs-neutral
C=(--n-max 250000 --t-star 100000 --seed 20261007 --workers "$W" --out-dir "$O")

echo "== 0. preflight"
if [ -n "$(git status --porcelain -- src pyproject.toml uv.lock)" ]; then
  echo "refusing: uncommitted changes in src/, pyproject.toml or uv.lock"; exit 1
fi
$PY -m pytest -q -p no:cacheprovider tests/test_rq7.py tests/test_sequential.py
mkdir -p "$O"

echo "== 1. null coverage (min_n 200)"
$FHR3 rq7-cell --name null-heavy-min200    --sampler "$HEAVY" --reps 2000 --min-n 200 "${C[@]}"
$FHR3 rq7-cell --name null-moderate-min200 --sampler "$MOD"   --reps 2000 --min-n 200 "${C[@]}"
$FHR3 rq7-cell --name null-mild-min200     --sampler "$MILD"  --reps 2000 --min-n 200 "${C[@]}"
$FHR3 rq7-cell --name null-normal-min200   --sampler normal   --reps 2000 --min-n 200 "${C[@]}"
$FHR3 rq7-cell --name null-t3-min200       --sampler t3       --reps 2000 --min-n 200 "${C[@]}"

echo "== 2. min-N sensitivity"
for m in 50 1000 5000; do
  $FHR3 rq7-cell --name "null-heavy-min$m" --sampler "$HEAVY" --reps 2000 --min-n "$m" "${C[@]}"
  $FHR3 rq7-cell --name "null-mild-min$m"  --sampler "$MILD"  --reps 2000 --min-n "$m" "${C[@]}"
  $FHR3 rq7-cell --name "null-t3-min$m"    --sampler t3       --reps 2000 --min-n "$m" "${C[@]}"
done

echo "== 3. non-null stopping (fixed look at the 80%-power N)"
for spec in "heavy:$HEAVY" "moderate:$MOD" "mild:$MILD" "normal:normal" "t3:t3"; do
  n=${spec%%:*}; s=${spec#*:}
  $FHR3 rq7-cell --name "alt-$n-n25k"  --sampler "$s" --effect-d 0.017719 --fixed-n 25000  --reps 1000 --min-n 200 "${C[@]}"
  $FHR3 rq7-cell --name "alt-$n-n100k" --sampler "$s" --effect-d 0.008859 --fixed-n 100000 --reps 1000 --min-n 200 "${C[@]}"
done

echo "== 4. real orderings: permutations of the NLHE 6-max p1 corpus"
$FHR3 rq7-cell --name perm-nlhe6p1 --sampler permutation:results/fhr3-nlhe6-100bb-pilot-v1/p1-neutral-vs-loose10 \
    --reps 1000 --min-n 200 "${C[@]}"

echo "== 5. analysis + freeze"
scripts/analyze_rq7.sh
