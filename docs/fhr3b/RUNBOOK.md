# FHR3B runbook (publicly FullHouse Research #4)

Branch `research/fhr3b-swiss-baseline`, worktree `~/fullhouse-research-03b`.

> **Core publication study (2026-10-01 rescoping): NLHE6 only.** It covers the three frozen
> fields and six unique cells per field, with 50 tournaments per cell, 250 `mu_field` rounds per
> field and 100 `mu_swiss` tournaments per field initially. That is 211.32M scheduled hands in
> total. Its launch plan, exact commands and cost are in
> **`docs/fhr3b/FHR4_CORE.md`**, and the launcher is `scripts/run_fhr4_core.sh`. Run
> `fhr3b core plan` before anything expensive. Two things below are now history or general
> capability and are not part of the core:
>
> * AoF4 and NLHE4, which stay frozen for provenance;
> * the 200/1000 replication presets, which are retired.

All experiments use the controlled research protocol `fhr3b_baseline`:

* N = 60, K = 6, H0 = 400;
* R0 = 40 as the *initial* horizon;
* core publication mode NLHE6 (AoF4/NLHE4 frozen, not in the core matrix).

These are research design choices, not 2026 settings (`paper/FHR3B_SCOPE.md`). Only
`operational-2026` (historical validation H) depends on historical facts, and it is blocked.

Every simulation step is **resumable**. Re-running skips digest-verified tournaments and
finished calibration chunks, refuses results from a different configuration, and extends the
same cells when only the preset changes.

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest                     # FHR3A + FHR3B tests
```

Knobs for `scripts/run_fhr3b.sh`:

| variable | default |
|---|---|
| `WORKERS` | 8 |
| `ROOT` | `results/fhr3b` |
| `REPORTS` | `reports/fhr3b` |
| `MODES` | `nlhe6` |
| `SCHEDULE_MODES` | from the matrix: nlhe6 |

## 0. Audit and smoke (cheap)

```bash
scripts/run_fhr3b.sh audit     # historical record (unknowns, reference hash) + research baseline hash
scripts/run_fhr3b.sh smoke     # every mode + whole pipeline at 10 hands/match (results/fhr3b-smoke); never interpreted
```

## Execution order (updated 2026-10-01: heads-up-role fix)

| step | what | status |
|---|---|---|
| 1 | AoF4 fields frozen (`FROZEN.yaml`) | done; unaffected |
| 2 | Duplicate lanes + within-match history | done |
| 3 | Heads-up-role fix (`fhr3b_heuristic`); old NLHE pools, calibrations and fields retired; the NLHE6 freeze revoked | done |
| 4 | **Re-run NLHE4 and NLHE6 pool calibration** on the new pools | next (expensive) |
| 5 | Behaviour audit + selection for NLHE4 and NLHE6 | cheap |
| 6 | Review and freeze both NLHE modes (add hashes to `FROZEN.yaml`) | human |
| 7 | ~~Matched field-reference for 3 modes × 3 frozen fields~~ superseded: NLHE6 × 3 fields, 250 matched rounds (`FHR4_CORE.md`) | expensive, not yet run |
| 8 | FHR #4 core matrix: 18 unique NLHE6 cells × 50 tournaments (`FHR4_CORE.md`) | expensive, not yet run |

## 1. NLHE pool calibration (step 4; expensive)

```bash
MODES="nlhe4 nlhe6" scripts/run_fhr3b.sh calibrate-pool
# = .venv/bin/fhr3b calibrate --stage pool --profile publication --modes nlhe4 nlhe6 --workers 8
```

* **New calibration ids:** `nlhe4.nlhe4-pool.H400.pool-calibration.9880eebd` and
  `nlhe6.nlhe6-pool.H400.pool-calibration.aadd073b`. They cannot collide with the retired runs,
  which keep a `RETIRED.txt` marker.
* **NLHE4:** 19.2M hands, ≈ 1–1.5 h wall at 8 workers.
* **NLHE6:** 12.8M hands, ≈ 1–1.5 h, or up to ≈ 3.4 h on a shared machine (the earlier observed
  run).
* **Hand count:** corrected heads-up play is longer (fewer folds), so hands per match can rise
  slightly.
* **Engine hash:** `5f5019c69316d098`. The AoF4 frozen calibration is proven result-neutral under
  it by exact replay.

Then (minutes):

```bash
MODES="nlhe4 nlhe6" scripts/run_fhr3b.sh behaviour-audit
MODES="nlhe4 nlhe6" scripts/run_fhr3b.sh select-fields
.venv/bin/python scripts/fhr3b_calibration_review.py && .venv-figures/bin/python scripts/fhr3b_calibration_figures.py
# review; then add the six NLHE hashes to configs/fhr3b/fields/FROZEN.yaml
```

## 2. Matched field reference (step 7; expensive)

```bash
scripts/run_fhr4_core.sh field-reference   # = fhr3b core field-reference: NLHE6 x 3 frozen fields
```

* **Rounds:** 250 matched rounds per NLHE6 field (6 lanes × 400 hands). That is 6M scheduled
  table-hands per field and 18M in total. (Earlier plan, superseded: 3,000
  ordinary-equivalent rounds, i.e. 500 × 6 for NLHE6 and 750 × 4 for AoF4/NLHE4.)
* **Extension to 500:** `--rounds 500 --extend` appends rounds 250–499 to the same calibration
  ids.
* **Cost:** ≈ 17M played hands; ≈ 1.4 h wall at 8 workers.
* **Outputs:** `calibration/<id>/{calibration.lock.json, chunks/, lanes/}`; reports
  `field-calibration/<mode>/<field_id>/{reference_bots.csv, reference.json}`.
* **Guard:** refuses unfrozen or revoked fields.

## 3. Runtime pilot (≈ 15–30 min)

```bash
scripts/run_fhr3b.sh pilot     # 8 full tournaments per mode on provisional60 fields
```

## 4. Publication experiments (FHR #4 core; after review)

The publication matrix is `fhr3b core matrix`: 18 unique NLHE6 cells serving A–D, with 50
tournaments per cell. See `docs/fhr3b/FHR4_CORE.md`.

* **Presets:** `pilot` (8) and `core` (50). The former `broad` (200) and `flagship` (1000)
  presets are retired.
* **Extensions:** per cell, append-only (`--range 50:100 --extend`), and only where the primary
  qualification metrics are still too uncertain.

```bash
scripts/run_fhr4_core.sh plan       # no simulation: exactly what would run, and its cost
scripts/run_fhr4_core.sh matrix     # A (prefixes of the baseline) + B + C (frozen J=1) + D, deduplicated
scripts/run_fhr4_core.sh validate
scripts/run_fhr4_core.sh analyse    # reports/fhr3b/analysis-fhr4-core/
scripts/run_fhr4_core.sh swiss-reference             # mu_swiss: 100 per field (extend per field: --range 100:200 --extend)
scripts/run_fhr3b.sh operational-2026                 # H (historical): blocked, lists the missing facts
```

## Runtime estimates

Estimates are from measured single-process throughput on this machine, with 8 workers assumed to
give about 4×.

| mode | hands/s/core | one 40-round tournament (N = 60) |
|---|---|---|
| AoF4 | ~1,410 | 240k hands, ~2.8 core-min |
| NLHE4 | ~1,470 | ≤ 240k hands, ~2.7 core-min |
| NLHE6 | ~940–1,375 | ≤ 160k hands, ~2–3 core-min |

Current planning numbers come from `fhr3b core plan` (`docs/fhr3b/FHR4_CORE.md`), using the
measured 8-worker NLHE6 rate of ≈ 4,260 h/s:

| workload | wall at 8 workers |
|---|---|
| `mu_field`, 3 × 250 matched rounds | ≈ 1.4 h |
| core matrix, 18 cells × 50 | ≈ 9.3 h |
| combined | ≈ 10.7 h |
| `mu_swiss`, 3 × 100 | ≈ 3.1 h |
| initial programme (211.32M scheduled) | ≈ 13.8 h (≈ 45.6 h at the slow 1,289 h/s) |

The earlier 3-mode `broad`/`flagship` estimates are superseded.

## Failure handling

* **Interrupted run.** Re-run the same command.
* **`result-relevant source changed`.** Code under the engine source hash changed (current hash
  `389451b27c2264d2`, which matches every pool-calibration lock). Use `--allow-source-change`
  only for provably result-neutral changes, then run `validate --replay`.
* **`field ... not frozen yet`.** Run the field steps first.
