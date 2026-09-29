#!/usr/bin/env bash
# RQ6 analysis (read-only on Parquet; minutes). Exits non-zero on any correctness blocker:
# raw D not reproducing the frozen reference, nonzero self-play, |z(estimator - raw)| > 3.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
FHR3=.venv/bin/fhr3
PY=.venv/bin/python
mkdir -p reports/rq6
for e in fhr3-nlhe6-100bb-rq6-v1-fittedvf fhr3-nlhe6-20bb-rq6-allin-v1 fhr3-aof4-8bb-rq6-allin-v1; do
  $FHR3 analyze "results/$e" --bootstrap 1000 --json "reports/rq6/analyze-$e.json" | tee "reports/rq6/analyze-$e.txt"
done
# raw-D regression: every raw row must read "paired; corr(D) +1.000" against its reference
$FHR3 compare results/fhr3-nlhe6-100bb-pilot-v1 results/fhr3-nlhe6-100bb-rq6-v1-fittedvf \
    results/fhr3-nlhe6-20bb-v1 results/fhr3-nlhe6-20bb-rq6-allin-v1 \
    results/fhr3-aof4-8bb-pilot-v1 results/fhr3-aof4-8bb-rq6-allin-v1 \
    --json reports/rq6/compare.json | tee reports/rq6/compare.txt
$PY scripts/analyze_rq6.py --out reports/rq6 --boot 2000
$PY scripts/freeze_rq_manifest.py rq6
