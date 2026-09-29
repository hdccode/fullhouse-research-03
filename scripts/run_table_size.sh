#!/usr/bin/env bash
# FHR3A controlled table-size suite: four new publication corpora (researcher-run), validation
# and the combined analysis.
#   fhr3a-nlhe{3,4,6,8}-100bb-tablesize-v1  (configs/tablesize/nlhe_{k}max_100bb.yaml)
#   p1-p3 at 30,000 blocks each, c0 self-play control at 10,000, for EVERY table size.
# The frozen core corpora (fhr3-nlhe4-100bb-v2, fhr3-nlhe6-100bb-pilot-v1) are only read, as a
# separate historical comparison. Every simulate step is resumable: re-running skips finished
# 250-block chunks, so an interrupted run is restarted with the same command.
# Usage: scripts/run_table_size.sh [sim3|sim4|sim6|sim8|controls|validate|analyse|all]   (default: all)
set -euo pipefail
FHR3=${FHR3:-.venv/bin/fhr3}
PY=${PY:-.venv/bin/python}
W=${WORKERS:-8}
P3=(--pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral)
C0=(--pairing c0-selfplay-control)
V=reports/table-size/validate
step=${1:-all}
cfg() { echo "configs/tablesize/nlhe_$1max_100bb.yaml"; }

sim() {  # $1 = 3 | 4 | 6 | 8 : p1-p3 publication corpus
  $FHR3 simulate --config "$(cfg "$1")" --blocks 0:30000 "${P3[@]}" --workers "$W"
}

controls() {
  for k in 3 4 6 8; do
    $FHR3 simulate --config "$(cfg "$k")" --blocks 0:10000 "${C0[@]}" --workers "$W"
  done
}

validate() {
  mkdir -p "$V"
  for k in 3 4 6 8; do
    $FHR3 validate --config "$(cfg "$k")" --blocks 0:30000 "${P3[@]}" --replay 40 --json "$V/nlhe$k-30k.json"
    $FHR3 validate --config "$(cfg "$k")" --blocks 0:10000 "${C0[@]}" --replay 10 --json "$V/nlhe$k-control-10k.json"
  done
  # structural integrity of every corpus (written to reports/table-size, NOT the frozen final-analysis copy)
  $PY scripts/integrity_check.py --out "$V/integrity.json"
  # the frozen research must be byte-identical
  $PY scripts/freeze_manifest.py --verify
  $PY scripts/freeze_rq_manifest.py rq6 --verify
  $PY scripts/freeze_rq_manifest.py rq7 --verify
}

analyse() {
  $PY scripts/table_size_analysis.py --boot 1000 --freeze
  $PY scripts/table_size_analysis.py --boot 1000 --verify
}

case "$step" in
  sim3) sim 3 ;;
  sim4) sim 4 ;;
  sim6) sim 6 ;;
  sim8) sim 8 ;;
  controls) controls ;;
  validate) validate ;;
  analyse) analyse ;;
  all) sim 3; sim 4; sim 6; sim 8; controls; validate; analyse ;;
  *) echo "usage: $0 [sim3|sim4|sim6|sim8|controls|validate|analyse|all]" >&2; exit 2 ;;
esac
