# FHR3B runbook

All commands run from `~/fullhouse-research-03b` on branch `research/fhr3b-swiss-baseline`.
Every simulation step is **resumable**:

* re-running skips digest-verified tournaments and finished calibration chunks;
* results from a different configuration are refused;
* changing only the replication count or preset extends the same cells.

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest              # FHR3A + FHR3B tests
```

Environment knobs for `scripts/run_fhr3b.sh`:

| variable | default |
|---|---|
| `WORKERS` | 8 |
| `ROOT` | `results/fhr3b` |
| `REPORTS` | `reports/fhr3b` |
| `MODES` | `aof4 nlhe6 plo6` |
| `SCHEDULE_MODES` | from `matrix.yaml`: nlhe6 |

## 0. Audit and smoke (cheap)

```bash
scripts/run_fhr3b.sh audit     # vendored 2026 reference hash + protocol summary
scripts/run_fhr3b.sh smoke     # every mode + the whole pipeline at 10 hands/match, into results/fhr3b-smoke
```

Smoke numbers are never interpreted.

## 1. Field calibration (cost: hours)

```bash
scripts/run_fhr3b.sh calibrate-fields   # pool calibration, then select spread / crowded_cutoff / matchup
# writes configs/fhr3b/fields/<mode>/{spread,crowded_cutoff,matchup_sensitive|style_diverse}.json (immutable)
#        reports/fhr3b/field-calibration/<mode>/{pool_bots.csv,pool_matchup_matrix.csv,selection.json}
git add configs/fhr3b/fields reports/fhr3b/field-calibration && git commit -m "FHR3B: freeze fields"
scripts/run_fhr3b.sh field-reference    # mu_field inside each frozen field
```

Review `selection.json` before step 3. Check the matchup gate result and whether the crowd is
really crowded in `reference.json`.

## 2. Runtime pilot (cost: about 15–30 min wall at 8 workers)

```bash
scripts/run_fhr3b.sh pilot     # 8 full tournaments (N=60, R0, H0) per primary mode, provisional60 fields
```

The pilot runs before or after field calibration. It gives:

* the measured wall time per tournament, in `results/fhr3b/<cell>/runs/*.json`;
* Monte Carlo spread, in `reports/fhr3b/analysis-pilot/summary.json` under
  `monte_carlo.approx_tournaments_for_target`.

Use both to fix the publication presets before step 3.

## 3. Publication experiments (cost: see estimates)

The preset is `pilot` (8), `broad` (200) or `flagship` (1000) tournaments per cell. Start with
`broad`, analyse, then extend the same cells with `flagship` if the MC intervals are too wide.

```bash
scripts/run_fhr3b.sh baseline broad             # A: R0 cells, 3 modes x 3 fields
scripts/run_fhr3b.sh round-sweep                # A: derived from baseline prefixes; verifies identity, analyses
scripts/run_fhr3b.sh budget-sweep broad         # B: crowded_cutoff, (R0/4 x 4H0), (R0/2 x 2H0); baseline reused
scripts/run_fhr3b.sh schedule-diagnostic broad  # C: nlhe6 crowded_cutoff; 50 sources x 4 replays (frozen + adaptive)
scripts/run_fhr3b.sh swiss-reference broad      # mu_swiss, namespace swiss-reference
scripts/run_fhr3b.sh operational-2026           # D: prints the unresolved facts and exits (PENDING)
scripts/run_fhr3b.sh validate                   # independent invariant checks + exact replays
scripts/run_fhr3b.sh analyse                    # reports/fhr3b/analysis/
```

Equivalent direct CLI:

```bash
.venv/bin/fhr3b plan   --experiment baseline --modes aof4 nlhe6 plo6            # cells, hashes, completion
.venv/bin/fhr3b run    --experiment baseline --modes nlhe6 --fields crowded_cutoff --preset broad --workers 8
.venv/bin/fhr3b run    --experiment baseline --modes nlhe6 --range 200:400 --workers 8   # explicit extension
.venv/bin/fhr3b validate --experiment baseline --modes nlhe6 --replay 5 --prefix 3
.venv/bin/fhr3b replay-hands --experiment baseline --mode nlhe6 --field crowded_cutoff --replicate 0 --round 7 --table 2
.venv/bin/fhr3b analyse --modes aof4 nlhe6 plo6 --out reports/fhr3b/analysis
```

Several machines can run disjoint `--range` slices into separate roots. Merge by copying the
`tournaments/tNNNNNN` directories: the cell ids and locks are identical.

## Expected outputs

| path | contents |
|---|---|
| `results/fhr3b/<cell_id>/` | `cell.lock.json`, `runs/`, `tournaments/tNNNNNN/{tables,final}.parquet + manifest.json` |
| `results/fhr3b/calibration/<calib_id>/` | `calibration.lock.json`, `chunks/c_*.parquet` |
| `reports/fhr3b/field-calibration/<mode>/` | pool calibration + `selection.json`; `<field_id>/reference.json` |
| `reports/fhr3b/analysis/` | the CSV/JSON files below |

Files in `reports/fhr3b/analysis/`:

* `baseline_reliability.csv`, `qualification_probabilities.csv`, `rank_stability.csv`
* `round_sweep.csv`, `budget_allocation.csv`, `schedule_diagnostic.csv`
* `pairwise_inversions.csv`, `pairwise_inversions_binned.csv`, `field_references.csv`
* `figure_data/fig1..fig5*.csv`
* `summary.json`, `MANIFEST.json`

## Runtime estimates

These are **estimates**, from 2-round, H=400, N=60 runs on this machine (single process,
2026-09-29), scaled linearly. FHR3 throughput notes say 8 workers give about 3.5–4.5× on the
4P+4E laptop; 4× is assumed below.

| mode | measured hands/s/core | one full lab tournament (R0=40, H0=400, N=60) |
|---|---|---|
| nlhe6 | ~1,375 | ≤ 160k hands, ~1.9 core-min |
| plo6 | ~1,090 | ≤ 160k hands, ~2.5 core-min |
| aof4 | ~1,410 | 240k hands, ~2.8 core-min |

Busts shorten persistent-stack matches, by about 3% for NLHE and 9% for PLO.

| workload | core-hours | wall at 8 workers (~4×) |
|---|---|---|
| pool calibration, 3 modes × 2000 rounds | ~10 | ~2.5 h |
| field reference, 3 modes × 3 fields × 3000 rounds | ~27 | ~7 h |
| pilot, 8 tournaments × 3 modes | ~1 | ~15 min |
| baseline broad (200 × 9 cells) | ~72 | ~18 h |
| baseline flagship (1000 × 9 cells) | ~360 | ~90 h |
| budget sweep broad (2 extra cells × 3 modes × 200) | ~48 | ~12 h |
| schedule diagnostic broad (2 × 200, nlhe6) | ~13 | ~3 h |
| swiss reference (200 × 9 cells) | ~72 | ~18 h |

The R sweep costs nothing: it reuses the baseline prefixes.

Given these costs, flagship for every cell is probably unnecessary. Extend only the cells
whose MC intervals miss the targets in `summary.json`.

## Failure handling

* **Interrupted run.** Re-run the same command. Incomplete tournaments have no manifest and
  are recomputed.
* **`result-relevant source changed`.** Code under the engine source hash changed. Do not use
  `--allow-source-change` unless the change cannot affect results. Afterwards run
  `validate --replay N` to prove that old tournaments still replay exactly.
* **`field ... not frozen yet`.** Run `calibrate-fields` first. Before that, only
  smoke/provisional fields exist.
