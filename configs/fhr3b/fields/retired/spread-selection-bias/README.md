# Retired: NLHE6 `spread` field (selection bias), 2026-10-02

Status: `retired_spread_selection_bias`. The field is on **HOLD** at 250 matched rounds. It is
kept for provenance only and must never be used as the FHR #4 publication `spread` reference.

| mode | field | hash | frozen | reference at retirement |
|---|---|---|---|---|
| nlhe6 | spread | `ff0f2b07fc210f62` | 2026-10-01 | `nlhe6.nlhe6-spread.H400.dup.field-reference.3cea71b5`, 250 matched rounds, digest `98d90ea417bfa92d01fe415cd99624ff` |

## Why

The field was built as a clean-selection control with a separated rank-6/7 boundary.

* The boundary was 16.8 BB (2.89 SE) in the 96-bot pool calibration that selected it.
* The independent field-relative `mu_field` reference measured it at **0.71 BB**:
  * P(rank-6/7 reversal) = 0.475;
  * P(same top 6) = 0.342.

The audit (`reports/fhr3b/field-calibration/nlhe6/MU_FIELD_AUDIT.md`) traces this mainly to
**regression to the mean**. The leaders were chosen, and the band near the cut excluded, using
the same noisy pool estimates that then measured the gap. Field-minus-pool shifts are at noise
level (centred z sd 1.13), so this is not a reference-estimator failure.

More rounds would only measure the small gap more precisely; they would not repair the field.
The pre-registered rule said EXTEND_TO_500. That extension is deliberately **not** run.

## What is preserved

* `nlhe6/spread.json` here: a byte-identical copy of the frozen manifest. The original
  `configs/fhr3b/fields/nlhe6/spread.json` stays in place until a corrected field is frozen.
* `results/fhr3b/calibration/nlhe6.nlhe6-spread.H400.dup.field-reference.3cea71b5/`: 250 matched
  rounds, untouched, with a `RETIRED.txt` marker.
* `reports/fhr3b/field-calibration/nlhe6/nlhe6-spread/`: the reference reports as generated.

## Replacement

A corrected spread selector separates selection from validation (split-sample;
`core_fhr4.spread_v2` in `configs/fhr3b/matrix.yaml`, `src/fhr3/tournament/spread_v2.py`). Any
replacement gets a new field hash and a fresh, independent `mu_field` reference. Freezing it is
a human decision.
