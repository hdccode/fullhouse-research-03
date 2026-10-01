# FullHouse Research #4: core launch plan (NLHE6 only; NOT run)

Approved pre-compute scope, 2026-10-01. The initial programme is:

| stage | scheduled hands |
|---|---|
| `mu_field` | 18.0M |
| 50-rep matrix | 145.32M |
| `mu_swiss` at 100 per field | 48.0M |
| **total** | **211.32M** |

Scope and literature: `paper/FHR3B_SCOPE.md`. Configuration: `configs/fhr3b/matrix.yaml`, block
`core_fhr4`. The core commands read nothing else. Code: `src/fhr3/tournament/core.py` and the
`fhr3b core` command in `cli.py`. Tests: `tests/test_fhr4_core.py`.

The public 2026 engine semantics used here are a research reference. They are not a declaration
of the 2027 competition format.

* **Engine source hash:** `4647ee69857e7c9b`, unchanged by the rescoping. All scope code lives
  outside the result-relevant sources, and a test pins this.
* **Status:** nothing in this plan has been simulated. Only pool calibrations exist on disk.
  The plan snapshot is `reports/fhr3b/fhr4-core-plan.json`.

## 0. Look before launching (no simulation)

```bash
.venv/bin/fhr3b core plan --json reports/fhr3b/fhr4-core-plan.json      # or: scripts/run_fhr4_core.sh plan
.venv/bin/fhr3b core plan --rate 1289                                    # pessimistic throughput
.venv/bin/fhr3b core plan --range 50:100 --cells baseline --fields crowded_cutoff --rounds 500   # an extension
scripts/run_fhr4_core.sh smoke                                           # correctness at smoke scale (seconds)
```

`core plan` lists, for every unique cell and every field reference:

* the cell id and its output path;
* R, H, lanes, replicate range, completed tournaments and tournaments still to run;
* whether the work is the initial stage or an extension;
* scheduled hands and expected played hands;
* the work ratio against the baseline;
* wall time, both ideal and wave-quantised.

It also lists the three `mu_swiss` cells and the totals at both throughput rates. It reads only
configs and what is already on disk.

## 1. Launch sequence (after review)

```bash
scripts/run_fhr4_core.sh plan              # 0. re-check: no simulation
scripts/run_fhr4_core.sh field-reference   # 1. = fhr3b core field-reference --workers 8   (mu_field, 250 rounds x 3 fields)
#    review reports/fhr3b/field-calibration/nlhe6/*/reference.json
scripts/run_fhr4_core.sh matrix            # 2. = fhr3b core matrix --replicates 50 --workers 8  (18 cells x 50)
scripts/run_fhr4_core.sh swiss-reference   # 3. = fhr3b core swiss-reference --replicates 100 --workers 8  (mu_swiss)
scripts/run_fhr4_core.sh validate          # 4. invariants, exact replay of 2 tournaments per cell, A-prefix identity
scripts/run_fhr4_core.sh analyse           # 5. reports/fhr3b/analysis-fhr4-core/
```

The simulation steps are independent, so any order is valid; `mu_field` goes first so that its
reference quality can be reviewed. Every step is resumable: an interrupted run continues from
verified tournaments and chunks.

## 2. Unique cells (18)

| cell | experiments | R × H × lanes | scheduled hands / tournament | work vs baseline |
|---|---|---|---|---|
| baseline | A (5/10/20/30/40 prefixes), B, C (adaptive arm), D (ordinary arm) | 40 × 400 × 1 | 160,000 | 1.000 |
| budget_half_rounds | B | 20 × 800 × 1 | 160,000 | 1.000 |
| budget_quarter_rounds | B | 10 × 1600 × 1 | 160,000 | 1.000 |
| frozen_schedule | C | 40 × 400 × 1 (replays baseline r) | 160,000 | 1.000 |
| dup_fewer_rounds | D | 7 × 400 × 6 | 168,000 | **1.050** (not exact) |
| dup_shorter_matches | D | 40 × 67 × 6 | 160,800 | **1.005** (not exact) |

The duplicate variants are integer-constrained: 40/6 and 400/6 are not integers, so their work is
only approximately equal.

* **Fewer-rounds arm.** It is deliberately **7 × 400 × 6**, not 7 × 381. It isolates fewer Swiss
  rounds plus duplicate play while keeping the standard 400-hand match object, so the +5%
  scheduled-work mismatch (ratio 1.05) is accepted and flagged.
* **Work accounting.** `duplicate_play.csv` records scheduled and actually played hands per
  tournament, with both ratios against ordinary play. Any per-compute comparison must use these
  columns explicitly.

Cell ids (`results/fhr3b/<cell_id>/`):

| cell | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| baseline | `…spread.fhr3b_baseline.R40H400K6.swiss.publication.b5f3d314` | `…crowded_cutoff….R40H400K6.swiss.publication.7f40559c` | `…style_diverse….R40H400K6.swiss.publication.4cb85cc5` |
| budget_half_rounds | `….R20H800K6.swiss.publication.06c3c2d5` | `….R20H800K6.swiss.publication.ed78ee35` | `….R20H800K6.swiss.publication.36235c3a` |
| budget_quarter_rounds | `….R10H1600K6.swiss.publication.42ee3c9c` | `….R10H1600K6.swiss.publication.614bb63e` | `….R10H1600K6.swiss.publication.f4bb4d9f` |
| frozen_schedule | `….R40H400K6.frozen.publication.04eefd47` | `….R40H400K6.frozen.publication.85cba4b8` | `….R40H400K6.frozen.publication.c99bd91a` |
| dup_fewer_rounds | `….R7H400K6dup.swiss.publication.2b40b831` | `….R7H400K6dup.swiss.publication.30e72800` | `….R7H400K6dup.swiss.publication.137478d3` |
| dup_shorter_matches | `….R40H67K6dup.swiss.publication.bdd7506c` | `….R40H67K6dup.swiss.publication.6f076fbf` | `….R40H67K6dup.swiss.publication.f222bed2` |

Each `…` stands for `nlhe6.nlhe6-<field>.fhr3b_baseline`. The full ids are printed by
`fhr3b core plan`.

### How sharing works

* **One cell, many experiments.** Deduplication is by identity hash. Experiment B's 40 × 400
  cell, C's adaptive arm and D's ordinary arm all resolve to the baseline cell's identity, so it
  runs once.
* **A uses the baseline trajectories.** The 5/10/20/30/40 checkpoints are read from the stored
  post-round standings of the 40-round tournaments, and `validate --prefix` checks that identity.
* **C is a source-schedule counterfactual, paired by source.**
  * Baseline (source) tournament r generates a realised Swiss schedule.
  * Frozen replicate r plays that realised schedule with fresh poker randomness (new cards and
    decisions). Its own results cannot change its future pairings.
  * This removes within-run result → future-pairing feedback while preserving realistic Swiss
    schedule structure. It is not an identical-randomness causal pair.
  * The initial core uses J = 1. Baselines run first, and a frozen replicate whose source is
    missing is refused.
  * J > 1 is a later precision extension: a new cell, created by raising
    `experiments.frozen_schedule.replays_per_source` in `matrix.yaml`. J is part of the cell
    identity, so the J = 1 results are untouched, and frozen replicate r then means source r // J.
    `frozen_schedule.csv` always bootstraps over source tournaments, so several replays of one
    source are one cluster, never independent observations.
* **The supplementary within-source diagnostic** (`schedule-diagnostic`, J = 4, adaptive-replay
  cells) is not part of the core.

## 3. `mu_field` (matched field reference), initial stage

**The 250-round budget is core-scoped.** It lives only in `core_fhr4.field_reference` and is
requested by `fhr3b core field-reference` (and by `fhr3b calibrate --stage field` for the core
mode NLHE6). There is no global default:

* a non-core (AoF4/NLHE4) field reference needs `--allow-noncore` **and** an explicit
  `--rounds`;
* it never inherits 250.

Those budgets belong to the later, separately designed operational studies.

* **Design:** six whole-match duplicate lanes, 400 hands per lane, cyclic seats, common chance
  streams, random field partitions independent of Swiss standings.
* **Scale:** reported as normalised ordinary-match-equivalent `mu_field`.
* **Uncertainty:** analytic SE is primary; a 10-round grouped joint bootstrap feeds the ranking
  and gap diagnostics.
* **Validation:** per-lane persistence and validation. Common-random-number coupling across
  fields is documented in every `reference.json`. Design details: `FIELD_REFERENCE_PLAN.md`.

| field | calibration id |
|---|---|
| spread | `nlhe6.nlhe6-spread.H400.dup.field-reference.3cea71b5` |
| crowded_cutoff | `nlhe6.nlhe6-crowded_cutoff.H400.dup.field-reference.7d2640ae` |
| style_diverse | `nlhe6.nlhe6-style_diverse.H400.dup.field-reference.0caf92cc` |

The match count is not part of a calibration's identity, so these ids are the same as under the
earlier 500-round plan. Extending to 500 rounds adds chunk files 250–499 to the same calibration
directory. Extensions must be multiples of the 10-round chunk.

**Accounting:** 250 rounds × 10 tables × 6 lanes × 400 scheduled hands = **6.0M scheduled
table-hands per field**, **18.0M across the three fields**. Early match ends reduce this to
≈ 17.0M played (measured ratio 0.943).

## 4. Hands and wall time

| stage | scheduled hands | expected played | wall at 4,260 h/s (healthy, measured) | wall at 1,289 h/s (slow, observed end to end) |
|---|---|---|---|---|
| `mu_field`, initial (3 × 250 rounds) | 18.00M | 16.98M | ≈ 1.4 h (ideal 1.1 h) | ≈ 4.7 h (ideal 3.7 h) |
| main matrix (18 cells × 50) | 145.32M | 127.56M | ≈ 9.3 h (ideal 8.3 h) | ≈ 30.8 h (ideal 27.5 h) |
| `mu_swiss`, initial (3 × 100) | 48.00M | 45.28M | ≈ 3.1 h (ideal 3.0 h) | ≈ 10.2 h (ideal 9.8 h) |
| **initial paper programme** | **211.32M** | **189.81M** | **≈ 13.8 h** (ideal 12.4 h) | **≈ 45.6 h** (ideal 40.9 h) |

Per field and replicate, the six matrix cells schedule 968,800 table-hands:
4 × 160,000 + 168,000 + 160,800.

**Storage:** about 54 MB for the matrix, about 18 MB for `mu_swiss` and about 4 MB for
`mu_field`.

**Throughput basis.** The 8-worker rate is the steady state of the corrected NLHE6 pool
calibration on this machine:

* the run had 8 workers on 2026-10-01 and finished a batch of 8 chunks about every 285 s;
* its 1,289 h/s end-to-end figure includes two machine stalls of 73 and 44 minutes.

**Single-core rates**, measured in this session on tiny real tournaments:

| setting | rate |
|---|---|
| H = 400 | 1,350–1,450 h/s |
| H = 800 | ≈ 1,760 h/s |
| H = 1600 | ≈ 1,970 h/s |

Long matches lose seats to busts, so each hand is cheaper. The plan applies one rate to every
cell, which overestimates time for the long-match cells.

**Played ratios** (played ÷ scheduled hands):

| H | ratio | basis |
|---|---|---|
| 400 | 0.943 | 32,000 pool matches |
| 67 | 0.9998 | exact: prefix of the same matches |
| 800 | ≈ 0.83 | 30 matches; rough |
| 1600 | ≈ 0.60 | 30 matches; rough |

**Wave-quantised wall time.** Cells run one after another, and each spreads its 50 tournaments
over 8 workers in ⌈50/8⌉ = 7 waves.

## 5. `mu_swiss`: 100 tournaments per field (enabled, NOT run)

Each tournament is an adaptive 40 × 400 Swiss event in the `swiss-reference` namespace, at
160,000 scheduled hands.

| field | cell id |
|---|---|
| spread | `nlhe6.nlhe6-spread.fhr3b_baseline.R40H400K6.swiss.swiss-reference.2d98a8cd` |
| crowded_cutoff | `nlhe6.nlhe6-crowded_cutoff.fhr3b_baseline.R40H400K6.swiss.swiss-reference.bc25b57b` |
| style_diverse | `nlhe6.nlhe6-style_diverse.fhr3b_baseline.R40H400K6.swiss.swiss-reference.77d62182` |

**Configuration** (`core_fhr4.swiss_reference`):

* `enabled: true`, `replicates_initial: 100`, `replicates_extension: 200`;
* preset `swiss_reference: 100`.

**Per-field extension.** Extending one field from 100 to 200 appends tournaments 100–199 and never
recomputes 0–99:

```bash
.venv/bin/fhr3b core swiss-reference --fields style_diverse --range 100:200 --extend --workers 8
```

We decide field by field after the 100-tournament run.

**Reference outputs.** `fhr3b analyse` writes `swiss_reference_bots.csv` and the
`summary.json → sections.swiss_reference` block:

* per-bot P(qualify) with Wilson intervals;
* expected final score (total, and per match in BB) with SE;
* rank and top-6 uncertainty from a joint tournament bootstrap:
  * `mu_swiss` rank and 95% interval;
  * P(in the `mu_swiss` top 6);
  * P(same top-6 set);
  * the rank-6/7 gap and P(reversal);
* expected top-6 overlap against `mu_field`, and against `mu_swiss` (flagged as in-sample);
* the boundary bots whose qualification remains materially ambiguous.

In `crowded_cutoff` and `style_diverse` the rank-6/rank-7 order is not expected to become clean.
That ambiguity is part of the experimental object, not a reason to extend.

**Planning precision.** This approximation comes from the pool calibration's per-match SD (a
median of 156–161 BB). A bot's per-match SE ≈ SD / √(40 n).

| reps per field | per-bot SE (BB per match) | pair-difference SE | spread gap / pair SE | style_diverse | crowded_cutoff |
|---|---|---|---|---|---|
| 100 (initial) | ≈ 2.5 | ≈ 3.5 | 4.8 | 0.80 | 0.03 |
| 200 (extension) | ≈ 1.75 | ≈ 2.5 | 6.8 | 1.1 | 0.04 |

## 6. Extensions (explicit, append-only, per cell)

```bash
# 50 more tournaments in one cell (0..49 verified and skipped, never recomputed)
.venv/bin/fhr3b core matrix --range 50:100 --fields crowded_cutoff --cells baseline frozen_schedule --extend
# mu_field 250 -> 500 matched rounds for one field (appends chunks 250..499)
.venv/bin/fhr3b core field-reference --fields style_diverse --rounds 500 --extend
# long horizon, only if qualification metrics have not stabilised at 40 rounds (new cell; first 40 rounds identical)
.venv/bin/fhr3b run --experiment baseline --fields crowded_cutoff --horizon 80 --replicates 50 --extend --workers 8
```

**Guards under the publication profile.** Each case is refused before any simulation:

| request | refused unless |
|---|---|
| more than 50 tournaments per cell | `--extend` |
| more than 100 `mu_swiss` tournaments per field | `--extend` |
| more than 250 `mu_field` rounds | `--extend` |
| `mu_field` rounds that are not a multiple of 10 | never allowed |
| a horizon above 40 | `--extend` |
| AoF4, NLHE4 or any other non-core mode | `--allow-noncore`, plus an explicit `--rounds` for a field reference |
| a retired preset (`broad`, `flagship`) | never allowed; these presets no longer exist |

**Precision-driven policy.**

* **Tournament cells:** extend only where the primary qualification metrics (changed
  qualifiers, top-6 overlap, P(qualify) near the cut, ambiguous count) are too uncertain for the
  conclusion at hand. `summary.json → monte_carlo` gives a cell's CI half-width and the
  approximate count needed for a target.
* **Field references:** extend only where the reference cutoff ordering is too uncertain to
  judge accuracy.

## 7. Out of scope here

* AoF4 and NLHE4 full matrices. Their fields stay frozen and valid.
* The AoF4 and Crazy Pineapple operational ranking-budget studies, which come later and
  separately.
* Retired and revoked fields. Their history is preserved under `configs/fhr3b/fields/retired/`
  and `FROZEN.yaml: revoked`.
