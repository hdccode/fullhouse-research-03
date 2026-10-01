# FHR3B runbook

Branch `research/fhr3b-swiss-baseline`, worktree `~/fullhouse-research-03b`.

All experiments use the controlled research protocol `fhr3b_baseline`:

* N = 60, K = 6, H0 = 400;
* R0 = 40 as the *initial* horizon;
* publication modes AoF4, NLHE4, NLHE6.

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
| `MODES` | `aof4 nlhe4 nlhe6` |
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
| 7 | Matched field-reference (duplicate lanes) for 3 modes × 3 frozen fields | expensive |
| 8 | Inspect reference quality before any Swiss tournament pilot | human |

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
scripts/run_fhr3b.sh field-reference   # k-lane duplicate matches inside each FROZEN field
```

* **Rounds:** 3,000 ordinary-equivalent, run as 750 × 4 lanes (AoF4, NLHE4) or 500 × 6 lanes
  (NLHE6).
* **Cost:** ≈ 30–35 core-hours (≈ 8 h wall).
* **Guard:** refuses unfrozen or revoked fields.

## 3. Runtime pilot (≈ 15–30 min)

```bash
scripts/run_fhr3b.sh pilot     # 8 full tournaments per mode on provisional60 fields
```

## 4. Publication experiments (after review)

Presets are `pilot` (8), `broad` (200) and `flagship` (1000) tournaments per cell. Extend only the
cells whose Monte Carlo intervals miss their targets.

```bash
scripts/run_fhr3b.sh baseline broad             # A: 40-round cells; 5/10/20/30/40 read from prefixes
scripts/run_fhr3b.sh round-sweep                # A: verify prefix identity + analyse (no new simulation)
.venv/bin/fhr3b run --experiment baseline --horizon 80 --preset broad --workers 8   # A: only if still improving at 40
scripts/run_fhr3b.sh budget-sweep broad         # B: 10x1600, 20x800 (40x400 = baseline, reused)
scripts/run_fhr3b.sh schedule-diagnostic broad  # C: nlhe6 crowded_cutoff; 50 sources x 4 replays
scripts/run_fhr3b.sh duplicate-play broad       # D: ordinary vs 2 duplicate variants at equal work (paired seeds)
scripts/run_fhr3b.sh swiss-reference broad      # mu_swiss
scripts/run_fhr3b.sh operational-2026           # H (historical): blocked, lists the missing facts
scripts/run_fhr3b.sh validate
scripts/run_fhr3b.sh analyse                    # reports/fhr3b/analysis/ (incl. reference_accuracy.csv)
```

## Runtime estimates

Estimates are from measured single-process throughput on this machine, with 8 workers assumed to
give about 4×.

| mode | hands/s/core | one 40-round tournament (N = 60) |
|---|---|---|
| AoF4 | ~1,410 | 240k hands, ~2.8 core-min |
| NLHE4 | ~1,470 | ≤ 240k hands, ~2.7 core-min |
| NLHE6 | ~940–1,375 | ≤ 160k hands, ~2–3 core-min |

Planning numbers, for 3 modes × 3 fields:

| workload | core-hours | wall at 8 workers |
|---|---|---|
| baseline broad (200 tournaments per cell) | ~75 | ~19 h |
| baseline flagship (1000 per cell) | — | ~95 h |
| swiss-reference broad | ~75 | ~19 h |
| budget sweep (2 extra cells per mode) | ~50 | ~12 h |
| field reference (3,000 rounds) | ~30–35 | ~8 h |

## Failure handling

* **Interrupted run.** Re-run the same command.
* **`result-relevant source changed`.** Code under the engine source hash changed (current hash
  `389451b27c2264d2`, which matches every pool-calibration lock). Use `--allow-source-change`
  only for provably result-neutral changes, then run `validate --replay`.
* **`field ... not frozen yet`.** Run the field steps first.
