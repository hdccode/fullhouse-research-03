#!/usr/bin/env bash
# The two reference extensions that are missing from the final core corpus
# (researcher-run; ~10 min total at --workers 8).
#   * 4-max NLHE 100BB -> 100k blocks/pairing. The v1 corpus cannot be extended by
#     v2 code (schema lock), so this is a v2 re-run under a new experiment_id with
#     the same root seed: blocks 0..9999 must reproduce the v1 D exactly.
#   * AoF 4-max 8BB -> 50k blocks/pairing (extends the existing v2 corpus).
# Then re-run the final analysis (analyze_pilots.py picks up the v2 4-max corpus).
set -euo pipefail
FHR3=${FHR3:-.venv/bin/fhr3}
W=${WORKERS:-8}
P3NLHE=(--pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral)
P3AOF=(--pairing p1-prodv2-vs-blend10 --pairing p2-prodv2-vs-heuristic --pairing p3-aggressive-vs-neutral)

# 4-max NLHE v2: control at 10k, p1-p3 at 100k (~310k blocks, ~7-8 min)
$FHR3 simulate --config configs/nlhe_4max_100bb_v2.yaml --blocks 0:10000 --workers "$W"
$FHR3 simulate --config configs/nlhe_4max_100bb_v2.yaml --blocks 0:100000 "${P3NLHE[@]}" --workers "$W"
$FHR3 validate --config configs/nlhe_4max_100bb_v2.yaml --blocks 0:100000 "${P3NLHE[@]}" --replay 40 \
    --json reports/final-analysis/validate/nlhe4-v2-100k.json
$FHR3 compare results/fhr3-nlhe4-100bb-pilot-v1 results/fhr3-nlhe4-100bb-v2 \
    --json reports/final-analysis/nlhe4-v1-vs-v2.json   # expect: paired, corr(D) +1.000 on 10k common blocks

# AoF: p1-p3 to 50k (~120k new blocks, ~2-3 min)
$FHR3 simulate --config configs/aof_4max_8bb.yaml --blocks 0:50000 "${P3AOF[@]}" --workers "$W"
$FHR3 validate --config configs/aof_4max_8bb.yaml --blocks 0:50000 "${P3AOF[@]}" --replay 40 \
    --json reports/final-analysis/validate/aof4-50k.json

# refresh every analysis product
.venv/bin/python scripts/analyze_pilots.py --out reports/final-analysis/core --boot 1000
.venv/bin/python scripts/final_analysis.py --boot 400
.venv/bin/python scripts/d_collapse_check.py --out reports/final-analysis/d_collapse.csv --reps 4000
.venv/bin/python scripts/final_tables.py
R=(results/fhr3-aof4-8bb-pilot-v1 results/fhr3-nlhe4-100bb-v2 results/fhr3-nlhe6-20bb-v1 results/fhr3-nlhe6-50bb-v1
   results/fhr3-nlhe6-100bb-pilot-v1 results/fhr3-cp6-100bb-pilot-v1 results/fhr3-plo6-100bb-pilot-v1
   results/fhr3-bomb6-100bb-pilot-v1 results/fhr3-nit6-100bb-pilot-v1)
$FHR3 compare "${R[@]}" --json reports/final-analysis/cross-format-compare.json | tee reports/final-analysis/cross-format-compare.txt
$FHR3 figures "${R[@]}" --powersim reports/nlhe6-100bb-ref250k-powersim.json --out reports/final-analysis/figures --workers "$W"
