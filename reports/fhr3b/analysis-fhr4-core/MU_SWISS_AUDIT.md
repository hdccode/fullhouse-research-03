# FHR #4 `mu_swiss` audit: 200 tournaments per field (final)

Written for: the FHR #4 researchers closing the simulation programme.

* **Definition.** `mu_swiss` is the expected outcome under the specified adaptive Swiss mechanism
  (40 × 400): mean final score over complete tournaments in the `swiss-reference` namespace.
* **What it is not.** It is not universal skill, and not normative fairness.
* **Analysis.** `fhr3b analyse` (this directory); the 100-rep version is in git at `9f72e79`.
* **No new data were simulated for this audit.** The only re-simulation was an exact replay of 6
  stored tournaments, to verify them.

## 1. Integrity: clean

| | separated_control | crowded_cutoff | style_diverse |
|---|---|---|---|
| cell | `…swiss.swiss-reference.9972cfaa` | `…bc25b57b` | `…77d62182` |
| tournaments | t000000–t000199, 200 unique | 200 | 200 |
| digests verified / validated | 200 / 200 | 200 / 200 | 200 / 200 |
| engine hash in lock | `4647ee69857e7c9b` | same | same |
| reps 0–99 unchanged | last write 2026-10-04 14:14; the committed 100-rep report reproduces exactly | 15:21; exact | 16:37; exact |
| run records (requested, ran, skipped) | [0,100] 100/0 · [100,200] 100/0 | [0,100] 100/0 · [100,200] **28/72** | [0,100] 100/0 · [100,200] 100/0 |
| exact replay | reps 100, 199 | reps 100, 199 | reps 100, 199 |

All tables are zero-sum, every bot is seated exactly once per round, and there are no temp or partial files.

**crowded_cutoff restart.** The interrupted invocation completed 72 tournaments and wrote no run record.
The resume verified and skipped those 72 and ran exactly the remaining 28. Nothing was overwritten or
duplicated.

## 2. Final estimates (200 tournaments, 95% bootstrap / Wilson intervals)

| | separated_control | crowded_cutoff | style_diverse |
|---|---|---|---|
| rerun changed qualifiers | 3.82 [3.69, 3.94] | 4.19 [4.07, 4.31] | 4.43 [4.34, 4.52] |
| rerun top-6 overlap | 2.18 [2.06, 2.31] | 1.81 [1.69, 1.93] | 1.57 [1.48, 1.66] |
| rerun Spearman / Kendall | 0.44 / 0.31 | 0.41 / 0.29 | 0.44 / 0.31 |
| ambiguous bots (P(qualify) in [0.1, 0.9]) | 15 | 22 | 23 |
| wrong vs `mu_field` | 2.79 [2.66, 2.92] | 3.46 [3.33, 3.59] | 3.79 [3.65, 3.92] |
| qualification regret vs `mu_field` (BB; tournament CI / reference-propagated CI) | 122.3 [115.5, 128.7] / [108.4, 137.2] | 83.7 [77.7, 89.9] / [76.8, 97.3] | 93.4 [88.4, 98.3] / [84.3, 106.9] |
| boundary strength loss (BB) | 58.3 [55.8, 60.7] | 51.0 [48.0, 53.9] | 47.0 [44.9, 49.0] |
| clear misqualifications / clear omissions | 2.79 / 2.79 | 2.78 / 1.09 | 2.99 / 2.96 |
| `mu_swiss` P(same top 6) / P(6/7 reversal) | 1.000 / 0.000 | 0.212 / 0.513 | 0.232 / 0.489 |

**Boundary bots** (P(qualify) with Wilson 95% interval):

* **separated_control.**
  * The six leaders: maniac-e2-s2 0.76 [0.70, 0.81], station-e2-s2 0.65 [0.58, 0.71], nit-e3-s1 0.59
    [0.52, 0.65], trapper-e3-s3 0.52 [0.45, 0.59], neutral-e1-s0 0.39 [0.32, 0.45], station-e2-s3 0.31
    [0.25, 0.38].
  * Best non-leaders: loose-e2-s1 0.21 [0.15, 0.27], loose-e2-s3 0.20 [0.15, 0.26].
* **crowded_cutoff.**
  * The three leaders: maniac-e2-s2 0.73, station-e2-s2 0.68, trapper-e3-s3 0.50.
  * Then a flat cluster at 0.17–0.26: aggressive-e2-s0, aggressive-e1-s0, station-e1-s0, tight-e2-s3,
    loose-e2-s1, maniac-e2-s3, neutral-e1-s1.
* **style_diverse.**
  * Top three: maniac-e2-s2 0.70, station-e2-s2 0.49, nit-e3-s1 0.43.
  * Then a flat cluster at 0.21–0.23: trapper-e3-s3, tight-e2-s1, neutral-e2-s1, station-e2-s1,
    trapper-e2-s2, loose-e0, aggressive-e3-s3.

## 3. 100 vs 200

| | separated_control | crowded_cutoff | style_diverse |
|---|---|---|---|
| P(qualify) correlation, 100 vs 200 | 0.994 | 0.992 | 0.990 |
| max / mean abs change in P(qualify) | 0.065 / 0.011 | 0.070 / 0.014 | 0.060 / 0.013 |
| `mu_swiss` rank Spearman, 100 vs 200 | 0.996 | 0.991 | 0.993 |
| median Wilson half-width, 100 → 200 | 0.041 → 0.026 | 0.043 → 0.030 | 0.043 → 0.033 |

**Verdict: precision improved and the picture did not change.** All rerun, regret and `mu_field`-agreement
metrics moved within Monte Carlo error.

* The largest shift is crowded_cutoff regret (78.0 → 83.7 BB), and its intervals overlap.
* `mu_swiss` top-6 membership moved only inside the boundary clusters, where those clusters are flat:
  crowded_cutoff 4/6 shared, style_diverse 6th slot.

## 4. `mu_swiss` vs `mu_field`

| | separated_control | crowded_cutoff | style_diverse |
|---|---|---|---|
| Spearman / Kendall | 0.978 / 0.885 | 0.970 / 0.869 | 0.980 / 0.890 |
| top-6 overlap | 6/6 | 6/6 | 5/6 (`mu_swiss` 5th: tight-e2-s1, `mu_field` rank 9) |
| significantly discordant pairs (both \|z\| > 2) | 0 | 0 | 0 |

Disagreements stay inside the reference-ambiguous boundary sets and are within reference uncertainty.

**`mu_swiss` compresses strength differences.** For example, the separated_control leaders are at 24–55
BB/match under `mu_swiss`, against 48–74 BB under `mu_field`. Adaptive pairing puts strong bots against
each other, so their Swiss outcomes are compressed. This is expected for different estimands and is not a
disagreement in ordering.

**Conclusion holds.** The two reference notions agree strongly. Tournament noise dominates
reference-definition uncertainty.

## 5. Replication of the 50-rep baseline matrix

* Baseline P(qualify), from 50 tournaments, against `mu_swiss` P(qualify), from 200 independent
  tournaments: correlation 0.955 / 0.952 / 0.963, mean abs difference 0.029 / 0.030 / 0.023.
* `mu_swiss` reproduces the baseline's rerun instability and error against `mu_field` within intervals.
* Re-running the analysis with the 200-rep `mu_swiss` changed only `mu_swiss`-based columns.
* The matrix extension verdict is unchanged: primary 18/18 LOCK_AT_50, and the broad sensitivity flags the
  same 4 cells.

## 6. Pre-registered 100 → 200 rule at 200

The rule cannot trigger at n = 200 (the maximum possible Wilson half-width is 0.069, below 0.08), and 200 is
the pre-registered ceiling. **No further extension.** The remaining boundary ambiguity is reported, not
simulated away.

## 7. Simulation freeze

**The FHR4 simulation programme is COMPLETE** (2026-10-05); see `configs/fhr3b/matrix.yaml:
core_fhr4.simulation_freeze`. Publication-profile simulation commands now refuse to run.
