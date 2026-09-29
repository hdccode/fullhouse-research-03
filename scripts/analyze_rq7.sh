#!/usr/bin/env bash
# RQ7 analysis (read-only; ~1 min): sequential analysis of every frozen corpus in block-id
# order, the canonical tables / figure data from the cells, and the freeze manifest.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
FHR3=.venv/bin/fhr3
PY=.venv/bin/python
mkdir -p reports/rq7
for e in fhr3-nlhe6-100bb-pilot-v1 fhr3-nlhe4-100bb-v2 fhr3-cp6-100bb-pilot-v1 fhr3-plo6-100bb-pilot-v1 \
         fhr3-bomb6-100bb-pilot-v1 fhr3-aof4-8bb-pilot-v1 fhr3-nit6-100bb-pilot-v1 fhr3-nlhe6-20bb-v1 fhr3-nlhe6-50bb-v1; do
  $FHR3 sequential "results/$e" --t-star 100000 --json "reports/rq7/sequential-$e.json" > /dev/null
done
$PY scripts/analyze_rq7.py --cells reports/rq7/cells --out reports/rq7
$PY scripts/freeze_rq_manifest.py rq7
