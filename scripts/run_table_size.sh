#!/usr/bin/env bash
# FHR3A table-size sweep: the two new publication corpora (researcher-run) + validation + analysis.
#   NLHE 3-max 100BB  fhr3-nlhe3-100bb-v1   p1-p3 at 30,000 blocks, c0 control at 10,000
#   NLHE 8-max 100BB  fhr3-nlhe8-100bb-v1   p1-p3 at 30,000 blocks, c0 control at 10,000
# 4-max (fhr3-nlhe4-100bb-v2) and 6-max (fhr3-nlhe6-100bb-pilot-v1) are the frozen core corpora
# and are only read. Every simulate step is resumable: re-running skips finished 250-block
# chunks, so an interrupted run can simply be restarted with the same command.
# Usage: scripts/run_table_size.sh [sim3|sim8|validate|analyse|all]   (default: all)
set -euo pipefail
FHR3=${FHR3:-.venv/bin/fhr3}
PY=${PY:-.venv/bin/python}
W=${WORKERS:-8}
P3=(--pairing p1-neutral-vs-loose10 --pairing p2-neutral-vs-tight --pairing p3-aggressive-vs-neutral)
C0=(--pairing c0-selfplay-control)
V=reports/table-size/validate
step=${1:-all}

sim() {  # $1 = 3 | 8
  local cfg=configs/nlhe_$1max_100bb.yaml
  $FHR3 simulate --config "$cfg" --blocks 0:10000 "${C0[@]}" --workers "$W"
  $FHR3 simulate --config "$cfg" --blocks 0:30000 "${P3[@]}" --workers "$W"
}

validate() {
  mkdir -p "$V"
  for k in 3 8; do
    local cfg=configs/nlhe_${k}max_100bb.yaml
    $FHR3 validate --config "$cfg" --blocks 0:30000 "${P3[@]}" --replay 40 --json "$V/nlhe$k-30k.json"
    $FHR3 validate --config "$cfg" --blocks 0:10000 "${C0[@]}" --replay 10 --json "$V/nlhe$k-control-10k.json"
  done
  # structural integrity of every corpus (writes to reports/table-size, NOT the frozen final-analysis copy)
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
  sim8) sim 8 ;;
  validate) validate ;;
  analyse) analyse ;;
  all) sim 3; sim 8; validate; analyse ;;
  *) echo "usage: $0 [sim3|sim8|validate|analyse|all]" >&2; exit 2 ;;
esac
