#!/usr/bin/env bash
# Run a format pilot end to end: simulate -> validate -> analyze (-> power-sim).
# Usage: scripts/run_pilot.sh <config.yaml> [blocks=10000] [workers=8]
set -euo pipefail
CFG=${1:?config}; BLOCKS=${2:-10000}; WORKERS=${3:-8}
FHR3=${FHR3:-.venv/bin/fhr3}
EXP=$(python3 -c "import yaml,sys;print(yaml.safe_load(open('$CFG'))['experiment_id'])" 2>/dev/null || .venv/bin/python -c "import yaml;print(yaml.safe_load(open('$CFG'))['experiment_id'])")
mkdir -p reports
echo "== $EXP: simulate 0:$BLOCKS with $WORKERS workers"
$FHR3 simulate --config "$CFG" --blocks 0:"$BLOCKS" --workers "$WORKERS"
echo "== validate"
$FHR3 validate --config "$CFG" --blocks 0:"$BLOCKS" --replay 20 --json "reports/$EXP-validate.json"
echo "== analyze"
$FHR3 analyze "results/$EXP" --bootstrap 2000 --json "reports/$EXP.json" --ecdf-dir "reports/ecdf-$EXP" | tee "reports/$EXP.txt"
