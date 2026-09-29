#!/usr/bin/env bash
# FHR3B convenience wrapper. Every simulation step is resumable: re-running skips
# digest-verified tournaments and finished calibration chunks.
#
#   scripts/run_fhr3b.sh <step> [preset]
#
# steps: audit | smoke | calibrate-fields | field-reference | pilot | baseline |
#        round-sweep | budget-sweep | schedule-diagnostic | swiss-reference |
#        operational-2026 | validate | analyse | status | all-publication
# preset (baseline/budget/schedule/swiss-reference): pilot | broad | flagship (default broad)
#
# Environment: WORKERS (default 8), ROOT (default results/fhr3b), MODES (default "aof4 nlhe6 plo6"),
#              REPORTS (default reports/fhr3b), PY (default .venv/bin), SCHEDULE_MODES (default: matrix).
set -euo pipefail
cd "$(dirname "$0")/.."

STEP="${1:-}"
PRESET="${2:-broad}"
WORKERS="${WORKERS:-8}"
ROOT="${ROOT:-results/fhr3b}"
REPORTS="${REPORTS:-reports/fhr3b}"
MODES="${MODES:-aof4 nlhe6 plo6}"
BIN="${PY:-.venv/bin}"
F="$BIN/fhr3b"

run() { echo "+ $*" >&2; "$@"; }

case "$STEP" in
  audit)
    run "$F" audit ;;
  smoke)   # correctness only: 12-bot fields, 4 rounds, 10-hand matches, every mode; plus full pipeline
    S="${ROOT}-smoke"
    run "$F" run --experiment smoke --root "$S" --workers "$WORKERS" --quiet
    run "$F" validate --experiment smoke --root "$S" --replay 3 --prefix 2 > "$S/validate-smoke.json"
    SM=(--root "$S" --profile smoke --modes $MODES)
    run "$F" calibrate --stage pool "${SM[@]}" --workers "$WORKERS"
    run "$F" select-fields "${SM[@]}" --boot 50
    run "$F" calibrate --stage field "${SM[@]}" --fields spread crowded_cutoff matchup --workers "$WORKERS"
    run "$F" field-reference "${SM[@]}" --boot 30
    for E in baseline budget-sweep schedule-diagnostic swiss-reference; do
      run "$F" run --experiment "$E" "${SM[@]}" --replicates 6 --workers "$WORKERS" --quiet
    done
    run "$F" validate --experiment baseline "${SM[@]}" --replay 2 --prefix 2 > "$S/validate-pipeline.json"
    run "$F" validate --experiment schedule-diagnostic "${SM[@]}" --replay 1 >> "$S/validate-pipeline.json"
    run "$F" analyse --root "$S" --profile smoke --modes $MODES --boot 200 ;;
  calibrate-fields)   # pool calibration (namespace pool-calibration) -> deterministic field selection
    run "$F" calibrate --stage pool --root "$ROOT" --profile publication --modes $MODES --workers "$WORKERS"
    run "$F" select-fields --root "$ROOT" --profile publication --modes $MODES --reports "$REPORTS" ;;
  field-reference)    # mu_field inside each frozen field (namespace field-reference)
    run "$F" calibrate --stage field --root "$ROOT" --profile publication --modes $MODES \
        --fields spread crowded_cutoff matchup --workers "$WORKERS"
    run "$F" field-reference --root "$ROOT" --profile publication --modes $MODES --reports "$REPORTS" ;;
  pilot)              # runtime + MC calibration: 8 fhr3b_baseline tournaments per primary mode (provisional60)
    run "$F" run --experiment pilot --root "$ROOT" --modes $MODES --preset pilot --workers "$WORKERS"
    run "$F" validate --experiment pilot --root "$ROOT" --modes $MODES --replay 1 --prefix 1
    run "$F" analyse --root "$ROOT" --profile pilot --modes $MODES --out "$REPORTS/analysis-pilot" ;;
  baseline|budget-sweep|swiss-reference)
    run "$F" run --experiment "$STEP" --root "$ROOT" --modes $MODES --preset "$PRESET" --workers "$WORKERS" ;;
  schedule-diagnostic)   # modes from configs/fhr3b/matrix.yaml (nlhe6) unless SCHEDULE_MODES is set
    run "$F" run --experiment schedule-diagnostic --root "$ROOT" ${SCHEDULE_MODES:+--modes $SCHEDULE_MODES} \
        --preset "$PRESET" --workers "$WORKERS" ;;
  round-sweep)        # derived from baseline R-prefixes: verify the identity, then analyse
    run "$F" validate --experiment baseline --root "$ROOT" --modes $MODES --prefix 3
    run "$F" analyse --root "$ROOT" --profile publication --modes $MODES --out "$REPORTS/analysis" ;;
  operational-2026)   # historical validation: BLOCKED until required historical values are supplied
    run "$F" run --experiment operational-2026 --root "$ROOT" --replicates 1 ;;
  validate)
    for E in baseline budget-sweep schedule-diagnostic swiss-reference; do
      run "$F" validate --experiment "$E" --root "$ROOT" --modes $MODES --replay 2 || true
    done ;;
  analyse)
    run "$F" analyse --root "$ROOT" --profile publication --modes $MODES --out "$REPORTS/analysis" ;;
  status)
    for E in baseline budget-sweep schedule-diagnostic swiss-reference; do
      run "$F" status --experiment "$E" --root "$ROOT" --modes $MODES || true
    done ;;
  all-publication)    # EXPENSIVE (days of CPU at flagship). Resumable; run steps separately if unsure.
    echo "all-publication with preset=$PRESET: this is the full publication workload." >&2
    "$0" calibrate-fields
    "$0" field-reference
    "$0" baseline "$PRESET"
    "$0" budget-sweep "$PRESET"
    "$0" schedule-diagnostic "$PRESET"
    "$0" swiss-reference "$PRESET"
    "$0" round-sweep
    "$0" validate
    "$0" analyse ;;
  *)
    sed -n '2,15p' "$0"; exit 2 ;;
esac
