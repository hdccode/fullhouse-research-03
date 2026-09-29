#!/usr/bin/env bash
# RQ6 final (USER-RUN): raw vs all-in EV vs fitted MIVAT / AIVAT on the SAME matched blocks.
#   A. NLHE 6-max 100BB  fhr3-nlhe6-100bb-rq6-v1-fittedvf  raw, all-in EV, fitted MIVAT, fitted AIVAT
#                        25,000 blocks/pairing (+ 2,000 control)       reference fhr3-nlhe6-100bb-pilot-v1
#   B. NLHE 6-max 20BB   fhr3-nlhe6-20bb-rq6-allin-v1      raw, all-in EV   10,000/pairing (+ control)
#                                                                       reference fhr3-nlhe6-20bb-v1
#   C. AoF 4-max 8BB     fhr3-aof4-8bb-rq6-allin-v1        raw, all-in EV   50,000/pairing (+ 10,000 control)
#                                                                       reference fhr3-aof4-8bb-pilot-v1
# Every setting uses the reference corpus' root seed, so raw D must reproduce it block for block.
# Resumable: finished chunks are skipped; the value function is fitted once and then reused
# (its sha256 is pinned in the derived config); locks refuse incompatible results.
# Conservative duration at 8 workers: ~25-40 min total (see docs/workflow.md).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
FHR3=.venv/bin/fhr3
PY=.venv/bin/python
W=${WORKERS:-8}
P3=(--pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral)
P3AOF=(--pairing p1-prodv2-vs-blend10 --pairing p2-prodv2-vs-heuristic --pairing p3-aggressive-vs-neutral)
VF=configs/rq6/vf/nlhe6-100bb-vf.json
FIT=configs/rq6/nlhe_6max_100bb_fitted.yaml

echo "== 0. preflight: committed code, RQ6 correctness gates"
if [ -n "$(git status --porcelain -- src pyproject.toml uv.lock)" ]; then
  echo "refusing: uncommitted changes in src/, pyproject.toml or uv.lock (run manifests must record a clean SHA)"; exit 1
fi
$PY -m pytest -q -p no:cacheprovider tests/test_rq6.py tests/test_allin_ev.py tests/test_vat.py

echo "== 1. value function: fit once on separate training blocks (seed 90210), then verify"
if [ ! -f "$FIT" ]; then
  mkdir -p "$(dirname "$VF")"
  $FHR3 vat-fit --config configs/nlhe_6max_100bb_rq6.yaml "${P3[@]}" --blocks 0:1000 \
      --training-root-seed 90210 --flop-samples 16 --kind aivat --out "$VF" --write-config "$FIT"
fi
$PY scripts/verify_value_function.py "$FIT"

echo "== 2. A: NLHE 6-max 100BB (fitted)"
$FHR3 simulate --config "$FIT" --blocks 0:2000 --pairing c0-selfplay-control --workers "$W"
$FHR3 simulate --config "$FIT" --blocks 0:25000 "${P3[@]}" --workers "$W"

echo "== 3. B: NLHE 6-max 20BB all-in EV"
$FHR3 simulate --config configs/rq6/nlhe_6max_20bb_allin.yaml --blocks 0:10000 --workers "$W"

echo "== 4. C: AoF 4-max 8BB all-in EV"
$FHR3 simulate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:10000 --pairing c0-selfplay-control --workers "$W"
$FHR3 simulate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:50000 "${P3AOF[@]}" --workers "$W"

echo "== 5. validate (structure + exact replay incl. estimator columns)"
mkdir -p reports/rq6
$FHR3 validate --config "$FIT" --blocks 0:25000 "${P3[@]}" --replay 20 --json reports/rq6/validate-nlhe6-100bb.json
$FHR3 validate --config "$FIT" --blocks 0:2000 --pairing c0-selfplay-control --replay 10 --json reports/rq6/validate-nlhe6-100bb-control.json
$FHR3 validate --config configs/rq6/nlhe_6max_20bb_allin.yaml --blocks 0:10000 --replay 20 --json reports/rq6/validate-nlhe6-20bb.json
$FHR3 validate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:50000 "${P3AOF[@]}" --replay 20 --json reports/rq6/validate-aof4.json
$FHR3 validate --config configs/rq6/aof_4max_8bb_allin.yaml --blocks 0:10000 --pairing c0-selfplay-control --replay 10 --json reports/rq6/validate-aof4-control.json

echo "== 6. analysis + freeze"
scripts/analyze_rq6.sh
