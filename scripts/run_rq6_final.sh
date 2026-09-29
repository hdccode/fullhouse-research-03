#!/usr/bin/env bash
# RQ6 final: the minimum estimator set (researcher-run; ~15-20 min total at 8 workers).
#   1. 6-max NLHE 100BB: raw vs all-in EV vs fitted MIVAT vs fitted AIVAT, 25k blocks
#      per pairing (same root seed as the 250k reference: raw D must equal stored D).
#   2. 6-max NLHE 20BB: raw vs all-in EV, 10k/pairing (same seed as the 20BB corpus).
#   3. AoF 4-max 8BB: raw vs all-in EV, 50k/pairing (every contested hand is a
#      preflop all-in: the all-in EV limit case). 50k matches the raw corpus: the
#      production-vs-blend gap (+0.27 [-0.07, +0.62] BB/100 raw) is the test case.
# The prior-value-function 100BB run and the Bomb Pot all-in EV run are not part
# of the minimum set (see docs/final_status.md).
set -euo pipefail
FHR3=${FHR3:-.venv/bin/fhr3}
W=${WORKERS:-8}
P3=(--pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral)
mkdir -p reports/vat reports/rq6

# 1a. frozen value function on separate training blocks (training seed != 20260928)
$FHR3 vat-fit --config configs/nlhe_6max_100bb_rq6.yaml "${P3[@]}" --blocks 0:1000 \
    --training-root-seed 90210 --flop-samples 16 --kind aivat \
    --out reports/vat/nlhe6-100bb-vf.json --write-config configs/nlhe_6max_100bb_rq6_fitted.yaml
# 1b. evaluate (experiment fhr3-nlhe6-100bb-rq6-v1-fittedvf); control only needs 2k blocks
$FHR3 simulate --config configs/nlhe_6max_100bb_rq6_fitted.yaml --blocks 0:2000 --pairing c0-selfplay-control --workers "$W"
$FHR3 simulate --config configs/nlhe_6max_100bb_rq6_fitted.yaml --blocks 0:25000 "${P3[@]}" --workers "$W"
$FHR3 validate --config configs/nlhe_6max_100bb_rq6_fitted.yaml --blocks 0:25000 "${P3[@]}" --replay 20 \
    --json reports/rq6/nlhe6-100bb-fitted-validate.json
$FHR3 analyze results/fhr3-nlhe6-100bb-rq6-v1-fittedvf --bootstrap 2000 --json reports/rq6/nlhe6-100bb-fitted.json \
    | tee reports/rq6/nlhe6-100bb-fitted.txt

# 2. 20BB all-in EV (experiment fhr3-nlhe6-20bb-rq6-allin-v1)
scripts/run_pilot.sh configs/rq6/nlhe_6max_20bb_allin.yaml 10000 "$W"
# 3. AoF all-in EV (experiment fhr3-aof4-8bb-rq6-allin-v1): control 10k, p1-p3 50k
P3AOF=(--pairing p1-prodv2-vs-blend10 --pairing p2-prodv2-vs-heuristic --pairing p3-aggressive-vs-neutral)
$FHR3 simulate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:10000 --workers "$W"
$FHR3 simulate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:50000 "${P3AOF[@]}" --workers "$W"
$FHR3 validate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:50000 "${P3AOF[@]}" --replay 20 \
    --json reports/rq6/aof4-allin-validate.json
$FHR3 analyze results/fhr3-aof4-8bb-rq6-allin-v1 --bootstrap 2000 --json reports/rq6/aof4-allin.json \
    | tee reports/rq6/aof4-allin.txt

# raw-D regression (expect "paired; corr(D) +1.000" for every raw row) + variance-reduction table
$FHR3 compare results/fhr3-nlhe6-100bb-pilot-v1 results/fhr3-nlhe6-100bb-rq6-v1-fittedvf \
    results/fhr3-nlhe6-20bb-v1 results/fhr3-nlhe6-20bb-rq6-allin-v1 \
    results/fhr3-aof4-8bb-pilot-v1 results/fhr3-aof4-8bb-rq6-allin-v1 \
    --json reports/rq6/rq6-compare.json | tee reports/rq6/rq6-compare.txt
$FHR3 figures results/fhr3-nlhe6-100bb-rq6-v1-fittedvf results/fhr3-nlhe6-20bb-rq6-allin-v1 \
    results/fhr3-aof4-8bb-rq6-allin-v1 --out reports/rq6/figures --workers "$W"
