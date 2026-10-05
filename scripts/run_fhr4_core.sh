#!/usr/bin/env bash
# FullHouse Research #4 core publication study (NLHE6 only; configs/fhr3b/matrix.yaml: core_fhr4).
# FROZEN 2026-10-05: the FHR4 simulation programme is COMPLETE. The simulation steps below are historical
# and now refused by the CLI (core_fhr4.simulation_freeze); plan / analyse / validate still work.
# Every simulation step is resumable and append-only; nothing outside the core scope runs from here.
#
#   scripts/run_fhr4_core.sh <step>
#
# steps:
#   plan             NO simulation: exact cells, counts, hands, ids/paths, wall estimate -> $REPORTS/fhr4-core-plan.json
#   field-diversity  NO simulation: strategic-diversity table of the 3 frozen fields (existing audit outputs)
#   smoke            correctness only: the core matrix + mu_field at smoke scale in ${ROOT}-core-smoke
#   field-reference  EXPENSIVE: mu_field, 250 matched rounds x 3 NLHE6 fields (18M scheduled hands)   [launch 1st]
#   matrix           EXPENSIVE: 6 unique cells x 3 fields x 50 tournaments (145.32M scheduled hands)   [2nd]
#   swiss-reference  EXPENSIVE: mu_swiss, 100 tournaments x 3 fields (48M scheduled hands)            [3rd]
#   validate         invariants + exact replay of 2 tournaments per cell + A-prefix identity
#   analyse          reports -> $REPORTS/analysis-fhr4-core
#
# Initial programme total: 211.32M scheduled hands. Not here on purpose: 60/80/120-round horizons,
# >50 tournaments per cell, >250 mu_field rounds, >100 mu_swiss tournaments per field,
# AoF4/NLHE4/Crazy Pineapple. Extensions are explicit per-cell / per-field
# `fhr3b core ... --extend` commands (docs/fhr3b/FHR4_CORE.md).
#
# Environment: WORKERS (default 8), ROOT (default results/fhr3b), REPORTS (default reports/fhr3b),
#              PY (default .venv/bin).
set -euo pipefail
cd "$(dirname "$0")/.."

STEP="${1:-}"
WORKERS="${WORKERS:-8}"
ROOT="${ROOT:-results/fhr3b}"
REPORTS="${REPORTS:-reports/fhr3b}"
BIN="${PY:-.venv/bin}"
F="$BIN/fhr3b"

run() { echo "+ $*" >&2; "$@"; }

case "$STEP" in
  plan)
    run "$F" core plan --root "$ROOT" --workers "$WORKERS" --json "$REPORTS/fhr4-core-plan.json" ;;
  field-diversity)
    run "$F" core field-diversity --reports "$REPORTS" ;;
  smoke)
    S="${ROOT}-core-smoke"
    run "$F" core matrix --profile smoke --fields smoke12 --root "$S" --replicates 3 --workers "$WORKERS" --quiet
    run "$F" core matrix --profile smoke --fields smoke12 --root "$S" --replicates 3 --workers "$WORKERS" --quiet
    run "$F" validate --experiment core --profile smoke --fields smoke12 --root "$S" --replay 1 --prefix 2 \
        > "$S/validate-core.json"
    run "$F" core field-reference --profile smoke --fields smoke12 --root "$S" --workers "$WORKERS" --boot 30 --quiet \
        > "$S/field-reference.json"
    run "$F" core swiss-reference --profile smoke --fields smoke12 --root "$S" --replicates 4 --workers "$WORKERS" \
        --quiet ;;
  field-reference)
    run "$F" core field-reference --root "$ROOT" --reports "$REPORTS" --workers "$WORKERS" ;;
  matrix)
    run "$F" core matrix --root "$ROOT" --replicates 50 --workers "$WORKERS" ;;
  swiss-reference)
    run "$F" core swiss-reference --root "$ROOT" --replicates 100 --workers "$WORKERS" ;;
  validate)
    run "$F" validate --experiment core --root "$ROOT" --replay 2 --prefix 2 ;;
  analyse)
    run "$F" analyse --root "$ROOT" --profile publication --modes nlhe6 --out "$REPORTS/analysis-fhr4-core" ;;
  *)
    sed -n '2,23p' "$0"; exit 2 ;;
esac
