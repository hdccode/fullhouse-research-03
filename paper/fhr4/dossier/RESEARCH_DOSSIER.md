# FHR #4 research dossier (frozen evidence)

**Status.** Analysis, verification and packaging only. This is not manuscript text: no title, abstract, introduction or results prose. Simulation frozen at `db45b56`; publication package `e222c9a`; engine source hash `4647ee69857e7c9b`. No simulation was run to produce this dossier, and no figure, field, threshold, reference or experimental definition was changed.

**Generation.** `scripts/fhr4_dossier.py` reads every number from the stored outputs listed in `MANIFEST.json` (SHA-256 of each input). Machine-readable copies are in `data/` and `tables/`. `tests/test_fhr4_dossier.py` checks the numbers against the analysis outputs and the wording rules.

**Reading conventions.**

* NLHE 6-max, N = 60 bots per field, top K = 6 qualify, Swiss rounds of persistent-stack matches.
* Intervals are 95%: tournament bootstrap for levels; paired bootstrap on shared replicate ids for contrasts (paired by source tournament in C); Wilson for P(qualify); `ref_propagated` intervals add the joint mu_field reference bootstrap. `reference_self_regret` is reported as the bootstrap median with its 2.5/97.5 percentile interval (see Section 6).
* Regret and boundary strength loss are in BB per ordinary-equivalent 400-hand match against the mu_field reference point estimate unless labelled mu_swiss.
* "Rerun" metrics compare independent tournaments of the same cell. "Wrong vs mu_field" counts selected bots outside the mu_field reference point top 6.
* Contrasts are first condition minus second. For error metrics, positive means the first is worse.
* Required terms: mu_field reference, mu_swiss reference, in these controlled fields, within the preregistered 40-round horizon, equal scheduled hand budget, source-schedule counterfactual, operational package comparison, engineered separated control.

**Map to the request.** Sections 1 to 8 follow the requested order. Section 9 is the prioritised limitation set (request item 11). Section 10 is the closing pack: executive, methods and results summaries, figure/table index, claims ledger (request item 10) and provenance timeline (request item 9).

## Contents

1. Research question and experimental plan
2. Canonical results sheet
3. Evidence cards
4. Results that need nuanced interpretation
5. Field profiles
6. Reference analysis
7. Figures
8. Tables
9. Remaining limitations (prioritised)
10. Closing pack: summaries, index, claims ledger, provenance timeline

## 1. Research question and experimental plan

### 1.1 Central research question

How should a finite poker-bot simulation budget be allocated so that a Swiss tournament reliably identifies the strongest agents? Operationally: how often do independent runs of the same tournament, and the tournament against independent reference strengths, agree on the qualifying top 6 of 60, and how does that change with rounds, match length, adaptive pairing and duplicate play?

### 1.2 Tournament setting

| Item | Value |
|---|---|
| Game | No-limit hold'em, 6-max tables (NLHE6) |
| Field size / qualifiers | N = 60 synthetic bots; top K = 6 qualify |
| Baseline format | 40 adaptive Swiss rounds (R0 = 40) of 400-hand persistent-stack matches (H0 = 400) |
| Scoring | raw chip delta per match, summed over rounds; public tiebreaks |
| Semantics | public-2026-style research semantics; research choices, not historical production settings |
| Agents | synthetic, stateless rule-based policy families (8 archetypes) |
| Engine | source hash `4647ee69857e7c9b` for every stored tournament and reference |

### 1.3 Final controlled fields (one frozen field per scenario)

| Field | Hash | Role | mu_field matched rounds | Rank-6/7 gap (BB) | P(same top 6) | P(6/7 reversal) |
|---|---|---|---|---|---|---|
| Separated control | `0b30004f650324e5` | Engineered separated control: six independently validated leaders, large rank-6/7 gap | 250 | 23.83 | 0.999 | 0.000 |
| Crowded cutoff | `afbffedfc3706d84` | Qualification-boundary stress test: designed near-equal crowd at the cutoff | 500 | 0.61 | 0.205 | 0.439 |
| Style diverse | `ad7d6596ef1c8c3e` | Strategically heterogeneous field: style x strength balanced, no near-duplicate bots | 500 | 2.02 | 0.366 | 0.353 |

Retired and not used: `spread` (`ff0f2b07fc210f62`, retired for selection bias) and the `spread_v2` candidate (failed held-out validation). See Section 10.6.

### 1.4 Reference estimands

* **mu_field reference.** Long-run expected performance against random partitions of the controlled field under the match semantics. Estimated by matched 6-lane whole-match duplicate play (cyclic seats, common chance streams, independent seed family), scaled to one ordinary 400-hand match. Primary SE analytic; uncertainty by joint bootstrap with one complete matched round as the unit.
* **mu_swiss reference.** Long-run expected outcome under the specified adaptive Swiss mechanism (40 x 400): mean final score over 200 complete tournaments per field in the `swiss-reference` namespace.
* Both are finite-sample estimates of mechanism-specific estimands. Neither is a context-free ranking; they can disagree in multiplayer, non-transitive games. Accuracy against mu_swiss measures convergence to the Swiss mechanism, not normative fairness.

### 1.5 Experiments

| Exp. | Question | Cells (per field, 50 tournaments each) | Comparison | Interpretation scope |
|---|---|---|---|---|
| Baseline | How reliable is 40 x 400 selection? | R40H400 adaptive | rerun and vs references | - |
| A | How does reliability change with rounds? | exact prefixes R5/R10/R20/R30/R40 of the baseline (no extra simulation) | level by prefix | within the preregistered 40-round horizon |
| B | Rounds or match length? | R10H1600, R20H800, R40H400 | paired contrasts | equal scheduled hand budget (16,000 hands per bot); played hands differ |
| C | Does adaptive pairing matter? | R40H400 frozen replay (J = 1) of each baseline schedule, fresh poker randomness | adaptive minus frozen, paired by source | source-schedule counterfactual |
| D | Do duplicate packages help? | R7H400x6 and R40H67x6 six-lane whole-match duplicate | paired contrasts vs ordinary R40H400 | operational package comparison |

### 1.6 Metrics

* **Primary identity metric:** rerun changed qualifiers (expected qualifiers that differ between two independent tournaments; 6 minus top-6 overlap). Governs the matrix extension rule.
* **Primary reference metrics:** wrong qualifiers vs the mu_field reference point top 6; qualification regret (summed mu_field of the reference-optimal six minus that of the selected six).
* **Supporting:** top-6 overlap, Jaccard, rerun Spearman and Kendall, mean absolute rank difference, number of ambiguous bots (P(qualify) in [0.1, 0.9]), P(same winner), boundary strength loss, the same metrics against the mu_swiss reference, `*_ref_propagated` intervals, `reference_self_regret` (regret floor from reference uncertainty alone), clear misqualifications / clear omissions (ignoring swaps inside the reference-ambiguous set), per-bot P(qualify).

### 1.7 Preregistered extension rules and outcomes

| Component | Rule (preregistered) | Outcome |
|---|---|---|
| mu_field, separated_control | extend 250 to 500 if P(same top 6) < 0.95 or P(6/7 reversal) > 0.05 | P(same) 0.999, P(rev) 0.000: locked at 250 |
| mu_field, crowded_cutoff | extend if a designed leader has P(top 6) < 0.95, or a bot outside leaders and crowd has P(top 6) > 0.10; ceiling 500 | fired at 250; extended to 500; still fires at 500 (loose-e2-s1, 0.208); ceiling reached, carried as reference uncertainty |
| mu_field, style_diverse | extend if a point rank 1 to 4 bot has P(top 6) < 0.90, or a rank >= 10 bot has P(top 6) > 0.10; ceiling 500 | fired at 250 (rank 10, 0.106); extended to 500; does not fire at 500: locked |
| Matrix (18 cells) | extend 50 to 100 if CI half-width of changed qualifiers or overlap > 0.3, or a pair-specific rerun changed-qualifier contrast CI spans +/-0.25; regret report-only | 18 / 18 LOCK_AT_50. Under the broad reading (wrong-vs-reference contrasts also trigger), 4 cells would have extended (sensitivity only; see 10.6) |
| mu_swiss | extend 100 to 200 if any decision-relevant bot with P(qualify) in [0.10, 0.90] has Wilson half-width > 0.08 (crowded designed crowd excluded); ceiling 200 | fired in all three fields at 100 (half-widths 0.080 to 0.096); ran to 200; at 200 max possible half-width 0.069 < 0.08, cannot fire |

### 1.8 Final simulation inventory

| Component | Units | Work | Integrity |
|---|---|---|---|
| Matrix (6 cells x 3 fields) | 18 cells x 50 = 900 tournaments | 145.32M scheduled / 126.19M played hands | all digests verified; zero-sum; seating; exact replays |
| mu_field reference, separated_control | 250 matched rounds | 6M scheduled hands | `5be0e1c0`, 25 lane chunks verified |
| mu_field reference, crowded_cutoff | 500 matched rounds | 12M scheduled hands | `7d2640ae`, 50 lane chunks verified |
| mu_field reference, style_diverse | 500 matched rounds | 12M scheduled hands | `0caf92cc`, 50 lane chunks verified |
| mu_swiss reference | 3 fields x 200 tournaments | 96M scheduled hands | 200/200 digests per field; exact replays |
| separated_control validation | 4,000 fresh pool-style rounds | pool context (96-bot pool) | seed family `fhr3b-2026-separated-control-validation`, one shot |

### 1.9 Deliberately not run

* 60/80/120-round horizons (Experiment A horizon is 5 to 40 rounds; longer horizons are future work).
* Matrix 50 to 100 extensions (rule did not fire).
* mu_field beyond 250 (separated_control) or 500 (crowded_cutoff, style_diverse); mu_swiss beyond 200.
* Any second spread_v2 attempt; any re-selection of separated_control.
* Other table sizes, game modes or fields; any statement about future competition formats.

## 2. Canonical results sheet

Full long-format sheet: `data/results_sheet.csv` (and `.json`), one row per field x condition x metric with value, interval, SE, n and source file.

### 2.1 Baseline R40H400 (50 tournaments per field)

| Metric | Separated control | Crowded cutoff | Style diverse |
|---|---|---|---|
| Rerun changed qualifiers | 3.83 [3.59, 4.07] | 4.32 [4.12, 4.50] | 4.38 [4.18, 4.56] |
| Rerun top-6 overlap | 2.17 [1.93, 2.41] | 1.68 [1.50, 1.88] | 1.62 [1.44, 1.82] |
| Rerun Spearman | 0.43 [0.40, 0.46] | 0.37 [0.34, 0.40] | 0.43 [0.41, 0.45] |
| Rerun Kendall | 0.31 [0.28, 0.33] | 0.26 [0.24, 0.28] | 0.30 [0.28, 0.32] |
| Ambiguous bots (P(qualify) in [0.1, 0.9]) | 19 [16, 22] | 25 [20, 27] | 24 [20, 26] |
| Wrong vs mu_field | 2.74 [2.50, 3.00] | 3.52 [3.26, 3.80] | 3.80 [3.58, 4.08] |
| Wrong vs mu_swiss | 2.74 [2.50, 3.00] | 3.52 [3.26, 3.80] | 3.74 [3.48, 4.02] |
| Clear misqualifications / clear omissions | 2.74 / 2.74 | 2.82 / 1.22 | 3.06 / 3.02 |
| Qualification regret (BB) | 122.9 [110.3, 137.9] | 93.7 [81.2, 105.3] | 94.3 [85.5, 103.7] |
|   with reference uncertainty propagated | 122.9 [105.7, 142.1] | 93.7 [82.5, 112.3] | 94.3 [82.7, 112.3] |
| Reference self-regret (BB; bootstrap median [2.5, 97.5 percentile]) | 0.0 [0.0, 0.0] | 2.7 [0.0, 10.7] | 1.5 [0.0, 9.8] |
| Boundary strength loss (BB) | 60.0 [55.7, 64.6] | 58.5 [53.0, 63.8] | 46.3 [42.6, 49.8] |

### 2.2 Experiment A: round prefixes

**Wrong vs mu_field**

| Field | R5 | R10 | R20 | R30 | R40 |
|---|---|---|---|---|---|
| Separated control | 4.18 [3.94, 4.40] | 3.68 [3.44, 3.94] | 3.22 [2.94, 3.52] | 2.98 [2.70, 3.26] | 2.74 [2.50, 3.00] |
| Crowded cutoff | 4.58 [4.36, 4.80] | 4.38 [4.10, 4.64] | 4.00 [3.74, 4.24] | 3.76 [3.50, 4.00] | 3.52 [3.26, 3.80] |
| Style diverse | 4.56 [4.26, 4.82] | 4.24 [3.94, 4.54] | 4.18 [3.94, 4.44] | 4.02 [3.76, 4.28] | 3.80 [3.58, 4.08] |

**Qualification regret (BB)**

| Field | R5 | R10 | R20 | R30 | R40 |
|---|---|---|---|---|---|
| Separated control | 224.8 [210.3, 238.1] | 191.4 [175.7, 208.9] | 154.8 [138.8, 172.6] | 136.0 [122.4, 151.4] | 122.9 [110.3, 137.9] |
| Crowded cutoff | 168.6 [153.7, 183.3] | 146.6 [130.1, 163.7] | 116.5 [104.5, 129.0] | 101.6 [89.5, 113.4] | 93.7 [81.2, 105.3] |
| Style diverse | 161.0 [145.0, 176.4] | 136.5 [123.0, 148.8] | 120.3 [108.8, 131.1] | 110.6 [100.0, 122.2] | 94.3 [85.5, 103.7] |

**Rerun Spearman**

| Field | R5 | R10 | R20 | R30 | R40 |
|---|---|---|---|---|---|
| Separated control | 0.11 [0.09, 0.14] | 0.20 [0.17, 0.23] | 0.32 [0.28, 0.35] | 0.38 [0.34, 0.41] | 0.43 [0.40, 0.46] |
| Crowded cutoff | 0.08 [0.06, 0.10] | 0.14 [0.11, 0.18] | 0.24 [0.21, 0.27] | 0.32 [0.29, 0.35] | 0.37 [0.34, 0.40] |
| Style diverse | 0.08 [0.06, 0.10] | 0.16 [0.13, 0.18] | 0.28 [0.25, 0.31] | 0.37 [0.34, 0.40] | 0.43 [0.41, 0.45] |

**Rerun changed qualifiers**

| Field | R5 | R10 | R20 | R30 | R40 |
|---|---|---|---|---|---|
| Separated control | 5.04 [4.90, 5.16] | 4.72 [4.55, 4.89] | 4.23 [3.99, 4.46] | 4.01 [3.79, 4.23] | 3.83 [3.59, 4.07] |
| Crowded cutoff | 5.13 [5.00, 5.25] | 4.94 [4.76, 5.10] | 4.69 [4.51, 4.87] | 4.50 [4.29, 4.69] | 4.32 [4.12, 4.50] |
| Style diverse | 5.12 [4.97, 5.24] | 4.95 [4.78, 5.10] | 4.78 [4.61, 4.93] | 4.63 [4.43, 4.79] | 4.38 [4.18, 4.56] |

Every metric improves at every step from 5 to 40 rounds in every field (checked by the generator).

### 2.3 Experiment B: equal scheduled hand budget (16,000 hands per bot)

**Levels**

| Field | Allocation | Scheduled hands / tournament | Played hands / tournament | Played / scheduled | Rerun changed qualifiers | Rerun Spearman | Wrong vs mu_field | Regret (BB) |
|---|---|---|---|---|---|---|---|---|
| Separated control | R10H1600 | 160,000 | 93,940 | 0.587 | 4.70 [4.54, 4.86] | 0.27 [0.24, 0.29] | 3.86 [3.58, 4.14] | 188.6 [173.1, 203.3] |
| Separated control | R20H800 | 160,000 | 129,307 | 0.808 | 4.00 [3.74, 4.25] | 0.36 [0.34, 0.39] | 2.90 [2.66, 3.12] | 131.8 [118.2, 144.9] |
| Separated control | R40H400 | 160,000 | 150,966 | 0.944 | 3.83 [3.59, 4.07] | 0.43 [0.40, 0.46] | 2.74 [2.50, 3.00] | 122.9 [109.9, 138.1] |
| Crowded cutoff | R10H1600 | 160,000 | 94,394 | 0.590 | 4.74 [4.53, 4.91] | 0.24 [0.21, 0.26] | 3.92 [3.64, 4.16] | 123.3 [111.4, 135.3] |
| Crowded cutoff | R20H800 | 160,000 | 129,953 | 0.812 | 4.26 [4.03, 4.47] | 0.32 [0.30, 0.35] | 3.54 [3.30, 3.78] | 89.7 [78.4, 101.1] |
| Crowded cutoff | R40H400 | 160,000 | 151,345 | 0.946 | 4.32 [4.12, 4.52] | 0.37 [0.34, 0.40] | 3.52 [3.24, 3.82] | 93.7 [82.1, 105.7] |
| Style diverse | R10H1600 | 160,000 | 86,748 | 0.542 | 4.90 [4.71, 5.06] | 0.27 [0.25, 0.30] | 4.56 [4.30, 4.82] | 136.0 [124.3, 148.4] |
| Style diverse | R20H800 | 160,000 | 125,355 | 0.783 | 4.72 [4.53, 4.87] | 0.34 [0.32, 0.36] | 4.08 [3.82, 4.32] | 107.8 [96.2, 119.5] |
| Style diverse | R40H400 | 160,000 | 150,493 | 0.941 | 4.38 [4.15, 4.57] | 0.43 [0.40, 0.45] | 3.80 [3.56, 4.06] | 94.3 [85.0, 103.7] |

**Paired contrasts (first minus second; positive = first worse)**

| Contrast | Field | Rerun changed qualifiers | Wrong vs mu_field | Regret (BB) |
|---|---|---|---|---|
| R10H1600 vs R40H400 | Separated control | 0.87 [0.60, 1.14] | 1.12 [0.74, 1.50] | 65.7 [47.2, 84.9] |
| R10H1600 vs R40H400 | Crowded cutoff | 0.42 [0.12, 0.69] | 0.40 [0.02, 0.76] | 29.6 [12.8, 46.2] |
| R10H1600 vs R40H400 | Style diverse | 0.52 [0.25, 0.79] | 0.76 [0.44, 1.14] | 41.7 [27.0, 57.1] |
| R20H800 vs R40H400 | Separated control | 0.17 [−0.18, 0.51] | 0.16 [−0.20, 0.50] | 8.9 [−10.2, 26.5] |
| R20H800 vs R40H400 | Crowded cutoff | −0.07 [−0.39, 0.24] | 0.02 [−0.40, 0.42] | −4.0 [−21.9, 12.4] |
| R20H800 vs R40H400 | Style diverse | 0.34 [0.05, 0.62] | 0.28 [−0.06, 0.62] | 13.5 [−1.7, 29.4] |
| R10H1600 vs R20H800 | Separated control | 0.69 [0.43, 0.98] | 0.96 [0.64, 1.30] | 56.7 [38.7, 76.8] |
| R10H1600 vs R20H800 | Crowded cutoff | 0.48 [0.24, 0.74] | 0.38 [0.02, 0.68] | 33.6 [17.6, 49.7] |
| R10H1600 vs R20H800 | Style diverse | 0.18 [−0.08, 0.42] | 0.48 [0.18, 0.84] | 28.2 [11.0, 44.4] |

**Matched played hands (descriptive, post hoc).** Each B allocation compared with the R40H400 prefix that played about the same number of hands.

| Comparison | Field | Played hands (arm / prefix) | Rerun changed qualifiers | Wrong vs mu_field | Regret (BB) |
|---|---|---|---|---|---|
| R10H1600 vs R40 prefix R25 | Separated control | 93,940 / 94,203 | 0.68 [0.41, 0.93] | 0.90 [0.48, 1.30] | 51.5 [27.8, 72.5] |
| R10H1600 vs R40 prefix R25 | Crowded cutoff | 94,393 / 94,488 | 0.10 [−0.15, 0.37] | 0.04 [−0.28, 0.38] | 10.5 [−5.9, 28.3] |
| R10H1600 vs R40 prefix R23 | Style diverse | 86,748 / 86,375 | 0.21 [−0.01, 0.48] | 0.48 [0.18, 0.82] | 23.6 [9.2, 39.2] |
| R20H800 vs R40 prefix R34 | Separated control | 129,307 / 128,122 | 0.07 [−0.28, 0.39] | −0.04 [−0.36, 0.30] | 0.5 [−17.3, 16.8] |
| R20H800 vs R40 prefix R34 | Crowded cutoff | 129,953 / 128,684 | −0.14 [−0.46, 0.21] | −0.02 [−0.36, 0.36] | −7.0 [−22.4, 9.0] |
| R20H800 vs R40 prefix R33 | Style diverse | 125,355 / 124,095 | 0.21 [−0.04, 0.49] | 0.24 [−0.14, 0.60] | 5.9 [−11.0, 21.3] |

### 2.4 Experiment C: adaptive minus frozen (source-schedule counterfactual)

| Field | Rerun changed qualifiers | Rerun Spearman | Rerun Kendall | Wrong vs mu_field | Regret vs mu_field (BB) | Regret vs mu_swiss (BB) |
|---|---|---|---|---|---|---|
| Separated control | −0.80 [−1.06, −0.56] | 0.15 [0.11, 0.21] | 0.11 [0.08, 0.15] | −0.90 [−1.26, −0.54] | −54.2 [−74.3, −36.5] | −32.9 [−45.8, −21.8] |
| Crowded cutoff | −0.38 [−0.65, −0.11] | 0.10 [0.06, 0.14] | 0.07 [0.05, 0.10] | −0.62 [−1.04, −0.18] | −21.2 [−40.4, −1.6] | −15.6 [−29.4, −1.5] |
| Style diverse | −0.33 [−0.59, −0.09] | 0.12 [0.08, 0.16] | 0.09 [0.06, 0.11] | −0.12 [−0.48, 0.24] | −11.6 [−24.7, 1.1] | −13.1 [−23.3, −3.0] |

Negative error contrasts and positive rank-correlation contrasts favour adaptive pairing. 50 source tournaments per field, one frozen replay each.

### 2.5 Experiment D: duplicate packages (operational package comparison)

| Field | Package | Scheduled work ratio | Played hands ratio | Rerun changed qualifiers | Rerun Spearman | Wrong vs mu_field | Regret (BB) |
|---|---|---|---|---|---|---|---|
| Separated control | R40H400 | 1.000 | 1.000 | 3.83 [3.61, 4.06] | 0.43 [0.40, 0.46] | 2.74 [2.50, 2.98] | 122.9 [110.8, 136.3] |
| Separated control | R7H400x6 | 1.050 | 1.051 | 3.71 [3.45, 3.96] | 0.44 [0.41, 0.47] | 2.56 [2.30, 2.82] | 114.6 [101.7, 128.0] |
| Separated control | R40H67x6 | 1.005 | 1.065 | 3.38 [3.11, 3.62] | 0.54 [0.52, 0.56] | 2.48 [2.24, 2.72] | 105.6 [94.4, 116.9] |
| Crowded cutoff | R40H400 | 1.000 | 1.000 | 4.32 [4.11, 4.52] | 0.37 [0.34, 0.40] | 3.52 [3.26, 3.82] | 93.7 [82.9, 105.1] |
| Crowded cutoff | R7H400x6 | 1.050 | 1.055 | 3.84 [3.58, 4.09] | 0.41 [0.39, 0.44] | 3.28 [3.04, 3.52] | 70.0 [58.6, 82.5] |
| Crowded cutoff | R40H67x6 | 1.005 | 1.062 | 4.01 [3.81, 4.20] | 0.51 [0.48, 0.54] | 3.18 [2.94, 3.42] | 77.1 [67.0, 87.3] |
| Style diverse | R40H400 | 1.000 | 1.000 | 4.38 [4.17, 4.58] | 0.43 [0.41, 0.45] | 3.80 [3.58, 4.06] | 94.3 [85.6, 104.3] |
| Style diverse | R7H400x6 | 1.050 | 1.050 | 4.51 [4.35, 4.68] | 0.43 [0.41, 0.46] | 3.74 [3.50, 3.96] | 98.6 [89.5, 107.4] |
| Style diverse | R40H67x6 | 1.005 | 1.068 | 4.20 [3.96, 4.41] | 0.49 [0.47, 0.52] | 3.38 [3.12, 3.64] | 86.1 [76.1, 95.9] |

| Contrast | Field | Rerun changed qualifiers | Wrong vs mu_field | Regret (BB) |
|---|---|---|---|---|
| R40H67x6 vs R40H400 | Separated control | −0.45 [−0.79, −0.13] | −0.26 [−0.56, 0.02] | −17.3 [−33.0, −3.6] |
| R40H67x6 vs R40H400 | Crowded cutoff | −0.31 [−0.62, 0.00] | −0.34 [−0.76, 0.02] | −16.6 [−33.8, 1.3] |
| R40H67x6 vs R40H400 | Style diverse | −0.17 [−0.46, 0.09] | −0.42 [−0.72, −0.16] | −8.2 [−20.1, 2.6] |
| R7H400x6 vs R40H400 | Separated control | −0.12 [−0.46, 0.21] | −0.18 [−0.54, 0.16] | −8.3 [−26.3, 8.8] |
| R7H400x6 vs R40H400 | Crowded cutoff | −0.49 [−0.78, −0.20] | −0.24 [−0.60, 0.12] | −23.7 [−36.5, −11.1] |
| R7H400x6 vs R40H400 | Style diverse | 0.14 [−0.15, 0.42] | −0.06 [−0.44, 0.28] | 4.4 [−10.3, 18.4] |
| R40H67x6 vs R7H400x6 | Separated control | −0.33 [−0.68, −0.01] | −0.08 [−0.42, 0.22] | −9.0 [−26.2, 6.1] |
| R40H67x6 vs R7H400x6 | Crowded cutoff | 0.18 [−0.17, 0.53] | −0.10 [−0.44, 0.24] | 7.1 [−10.1, 23.6] |
| R40H67x6 vs R7H400x6 | Style diverse | −0.31 [−0.61, −0.03] | −0.36 [−0.76, 0.04] | −12.5 [−25.9, 0.9] |

Runtime ratios are stored in the sheet but are indicative only (machine throttling and sleep).

### 2.6 mu_swiss reference (200 tournaments per field)

| Metric | Separated control | Crowded cutoff | Style diverse |
|---|---|---|---|
| Rerun changed qualifiers | 3.82 [3.69, 3.94] | 4.19 [4.07, 4.31] | 4.43 [4.34, 4.52] |
| Rerun top-6 overlap | 2.18 [2.06, 2.31] | 1.81 [1.69, 1.93] | 1.57 [1.48, 1.66] |
| Rerun Spearman | 0.44 [0.43, 0.46] | 0.41 [0.40, 0.43] | 0.44 [0.43, 0.45] |
| Rerun Kendall | 0.31 [0.30, 0.32] | 0.29 [0.28, 0.30] | 0.31 [0.30, 0.32] |
| Ambiguous bots | 15 | 22 | 23 |
| Wrong vs mu_field | 2.79 [2.66, 2.92] | 3.46 [3.33, 3.59] | 3.79 [3.65, 3.92] |
| Regret vs mu_field (BB) | 122.2 [115.5, 128.7] | 83.7 [77.7, 89.9] | 93.4 [88.4, 98.3] |
|   with reference uncertainty propagated | 122.2 [108.4, 137.2] | 83.7 [76.8, 97.3] | 93.4 [84.3, 106.9] |
| Boundary strength loss (BB) | 58.2 [55.8, 60.7] | 51.0 [48.0, 53.9] | 47.0 [44.9, 49.0] |
| P(same top 6) / P(6/7 reversal) of mu_swiss | 1.000 / 0.000 | 0.212 / 0.513 | 0.232 / 0.489 |

**P(qualify) near the cutoff** (mu_swiss 200 with Wilson 95%; baseline 50 for comparison; mu_field ranks 1 to 10). Full 180-bot table: Table A1.

*Separated control*

| mu_field rank | Bot | mu_field (BB) | P(reference top 6) | P(qualify), mu_swiss 200 | P(qualify), baseline 50 |
|---|---|---|---|---|---|
| 1 | station-e2-s2 | 73.7 | 1.000 | 0.65 [0.58, 0.71] | 0.74 |
| 2 | maniac-e2-s2 | 60.8 | 1.000 | 0.76 [0.70, 0.81] | 0.64 |
| 3 | nit-e3-s1 | 51.3 | 1.000 | 0.58 [0.52, 0.65] | 0.38 |
| 4 | station-e2-s3 | 50.6 | 1.000 | 0.31 [0.25, 0.38] | 0.32 |
| 5 | trapper-e3-s3 | 50.0 | 1.000 | 0.52 [0.45, 0.59] | 0.62 |
| 6 | neutral-e1-s0 | 47.9 | 0.999 | 0.39 [0.32, 0.45] | 0.56 |
| 7 | loose-e2-s3 | 24.0 | 0.000 | 0.20 [0.15, 0.26] | 0.20 |
| 8 | station-e3-s0 | 22.6 | 0.001 | 0.17 [0.13, 0.23] | 0.16 |
| 9 | loose-e2-s1 | 19.7 | 0.000 | 0.20 [0.15, 0.27] | 0.16 |
| 10 | neutral-e2-s0 | 18.9 | 0.000 | 0.13 [0.09, 0.18] | 0.08 |

*Crowded cutoff*

| mu_field rank | Bot | mu_field (BB) | P(reference top 6) | P(qualify), mu_swiss 200 | P(qualify), baseline 50 |
|---|---|---|---|---|---|
| 1 | station-e2-s2 | 66.5 | 1.000 | 0.68 [0.61, 0.74] | 0.60 |
| 2 | maniac-e2-s2 | 58.4 | 1.000 | 0.73 [0.66, 0.79] | 0.74 |
| 3 | trapper-e3-s3 | 54.9 | 1.000 | 0.49 [0.43, 0.56] | 0.44 |
| 4 | aggressive-e2-s0 | 25.2 | 0.871 | 0.26 [0.20, 0.32] | 0.26 |
| 5 | aggressive-e1-s0 | 21.8 | 0.593 | 0.21 [0.16, 0.28] | 0.22 |
| 6 | neutral-e1-s1 | 21.8 | 0.568 | 0.17 [0.12, 0.22] | 0.22 |
| 7 | maniac-e2-s3 | 21.2 | 0.468 | 0.17 [0.12, 0.23] | 0.16 |
| 8 | loose-e2-s1 | 18.7 | 0.208 | 0.18 [0.14, 0.24] | 0.22 |
| 9 | tight-e2-s3 | 16.9 | 0.069 | 0.19 [0.14, 0.25] | 0.14 |
| 10 | loose-e2-s0 | 16.8 | 0.073 | 0.14 [0.09, 0.19] | 0.18 |

*Style diverse*

| mu_field rank | Bot | mu_field (BB) | P(reference top 6) | P(qualify), mu_swiss 200 | P(qualify), baseline 50 |
|---|---|---|---|---|---|
| 1 | maniac-e2-s2 | 58.8 | 1.000 | 0.69 [0.63, 0.75] | 0.76 |
| 2 | station-e2-s2 | 51.3 | 1.000 | 0.48 [0.42, 0.55] | 0.50 |
| 3 | trapper-e3-s3 | 36.5 | 1.000 | 0.22 [0.17, 0.28] | 0.16 |
| 4 | nit-e3-s1 | 34.4 | 0.992 | 0.42 [0.36, 0.49] | 0.40 |
| 5 | neutral-e2-s1 | 32.3 | 0.973 | 0.22 [0.17, 0.28] | 0.16 |
| 6 | tight-e3-s2 | 24.8 | 0.393 | 0.17 [0.12, 0.23] | 0.22 |
| 7 | loose-e0 | 22.8 | 0.195 | 0.21 [0.16, 0.27] | 0.22 |
| 8 | neutral-e1-s2 | 22.6 | 0.176 | 0.14 [0.09, 0.19] | 0.14 |
| 9 | tight-e2-s1 | 22.5 | 0.145 | 0.23 [0.18, 0.29] | 0.28 |
| 10 | aggressive-e3-s3 | 20.6 | 0.067 | 0.22 [0.17, 0.28] | 0.10 |

## 3. Evidence cards

Format per card: support, uncertainty, fields, identity vs strength agreement, consistency, defensible wording, overclaim (avoid). Machine-readable: `data/evidence_cards.json`.

### Card 1. Baseline tournament reliability (R40H400)

* **Support:**
  * Rerun changed qualifiers: Separated control 3.83 [3.59, 4.07], Crowded cutoff 4.32 [4.12, 4.50], Style diverse 4.38 [4.18, 4.56] of 6.
  * Wrong vs mu_field: Separated control 2.74 [2.50, 3.00], Crowded cutoff 3.52 [3.26, 3.80], Style diverse 3.80 [3.58, 4.08].
  * Rerun Spearman over all 60 bots: 0.37 to 0.43.
  * Replicated in the independent 200-tournament mu_swiss reference: rerun changed qualifiers 3.82 [3.69, 3.94], 4.19 [4.07, 4.31], 4.43 [4.34, 4.52]; wrong vs mu_field 2.79 [2.66, 2.92], 3.46 [3.33, 3.59], 3.79 [3.65, 3.92].
  * Engineered separated control: the six validated leaders qualify with P = 0.31 to 0.76 (mu_swiss 200); the exact mu_field top 6 was selected in 2 of 250 tournaments.
* **Uncertainty:** Tournament bootstrap half-widths about 0.2 qualifiers at n = 50 and about 0.1 at n = 200; conditional on one frozen field per scenario.
* **Fields:** All three.
* **Identity vs strength:** Agree: high rerun disagreement, many wrong qualifiers, and large regret (122.9 [110.3, 137.9], 93.7 [81.2, 105.3], 94.3 [85.5, 103.7] BB).
* **Consistency:** Consistent across all three fields and across both references; the two independent tournament samples (50 matrix, 200 mu_swiss) agree within intervals.
* **Defensible wording:** In these controlled fields, 40 rounds of 400-hand matches selected the top 6 with substantial poker-variance error: independent reruns disagreed on 3.83 to 4.38 of 6 qualifiers, and 2.74 to 3.80 selected bots were outside the mu_field reference top 6.
* **Overclaim (avoid):**
  * Avoid: "Swiss is unreliable in general" or "40 rounds are insufficient in general".
  * Avoid: "the tournament fails to find the true skill ranking" (references are estimands, not a true skill ranking).

### Card 2. Improvement with rounds (Experiment A)

* **Support:**
  * Separated control: wrong vs mu_field 4.18 [3.94, 4.40] at R5 to 2.74 [2.50, 3.00] at R40; regret 224.8 [210.3, 238.1] to 122.9 [110.3, 137.9] BB; rerun Spearman 0.11 [0.09, 0.14] to 0.43 [0.40, 0.46].
  * Crowded cutoff: wrong vs mu_field 4.58 [4.36, 4.80] at R5 to 3.52 [3.26, 3.80] at R40; regret 168.6 [153.7, 183.3] to 93.7 [81.2, 105.3] BB; rerun Spearman 0.08 [0.06, 0.10] to 0.37 [0.34, 0.40].
  * Style diverse: wrong vs mu_field 4.56 [4.26, 4.82] at R5 to 3.80 [3.58, 4.08] at R40; regret 161.0 [145.0, 176.4] to 94.3 [85.5, 103.7] BB; rerun Spearman 0.08 [0.06, 0.10] to 0.43 [0.41, 0.45].
  * Every metric improves at every step 5, 10, 20, 30, 40 in every field (generator check).
  * Last step R30 to R40 regret: Separated control 136.0 to 122.9, Crowded cutoff 101.6 to 93.7, Style diverse 110.6 to 94.3 BB.
* **Uncertainty:** Prefixes are nested in the same 50 tournaments, so successive points are strongly correlated; adjacent-step differences are not separately tested. Endpoints (R5 vs R40) are far outside each other's intervals.
* **Fields:** All three.
* **Identity vs strength:** Agree (wrong qualifiers, regret, boundary loss, rerun rank correlation all improve).
* **Consistency:** Consistent across all three fields.
* **Defensible wording:** Reliability improved continuously with rounds in all three controlled fields, with no evidence of a plateau within the preregistered 40-round horizon.
* **Overclaim (avoid):**
  * Avoid: any rounds-needed extrapolation beyond 40 rounds, or "reliability plateaus at N rounds".
  * Avoid: "40 rounds are insufficient in general".

### Card 3. Rounds versus match length at an equal scheduled hand budget (Experiment B)

* **Support:**
  * R10H1600 minus R40H400, rerun changed qualifiers: Separated control 0.87 [0.60, 1.14], Crowded cutoff 0.42 [0.12, 0.69], Style diverse 0.52 [0.25, 0.79].
  * Same, regret (BB): Separated control 65.7 [47.2, 84.9], Crowded cutoff 29.6 [12.8, 46.2], Style diverse 41.7 [27.0, 57.1].
  * R20H800 minus R40H400, rerun changed qualifiers: Separated control 0.17 [−0.18, 0.51], Crowded cutoff −0.07 [−0.39, 0.24], Style diverse 0.34 [0.05, 0.62]; regret: Separated control 8.9 [−10.2, 26.5], Crowded cutoff −4.0 [−21.9, 12.4], Style diverse 13.5 [−1.7, 29.4].
  * Played / scheduled hands (mean over fields): R10H1600 0.57, R20H800 0.80, R40H400 0.94.
  * R10H1600 vs the R40 prefix with matched played hands, regret (BB): Separated control 51.5 [27.8, 72.5], Crowded cutoff 10.5 [−5.9, 28.3], Style diverse 23.6 [9.2, 39.2]; rerun changed qualifiers: Separated control 0.68 [0.41, 0.93], Crowded cutoff 0.10 [−0.15, 0.37], Style diverse 0.21 [−0.01, 0.48].
* **Uncertainty:** Paired bootstrap on 50 shared replicate ids. The matched-played-hands comparison is post hoc and descriptive, and uses prefixes of the baseline tournaments.
* **Fields:** R10 worse: all three on both metrics. R20 vs R40: no clear difference except style_diverse changed qualifiers. Matched played hands: separated_control (both metrics), style_diverse (regret and wrong vs mu_field), not crowded_cutoff.
* **Identity vs strength:** Agree for R10 vs R40 in all fields. For R20 vs R40 in style_diverse the identity contrast excludes zero while regret does not.
* **Consistency:** R10 disadvantage consistent across fields; the size of R20 vs R40 and the matched-played result vary by field.
* **Defensible wording:** At an equal scheduled hand budget, ten 1,600-hand rounds selected less reliably than forty 400-hand rounds in all three controlled fields; twenty 800-hand rounds were close to forty 400-hand rounds. Part of the R10 deficit remained at matched played hands in two of the three fields.
* **Overclaim (avoid):**
  * Avoid: "compute was held fixed" (scheduled hands were fixed; played hands and runtime were not).
  * Avoid: "R10 is worse at equal played hands everywhere" or "R20 is equivalent to R40".
  * Avoid: "longer matches are always worse".

### Card 4. Adaptive versus frozen schedule (Experiment C)

* **Support:**
  * Adaptive minus frozen, rerun changed qualifiers: Separated control −0.80 [−1.06, −0.56], Crowded cutoff −0.38 [−0.65, −0.11], Style diverse −0.33 [−0.59, −0.09].
  * Rerun Spearman: Separated control 0.15 [0.11, 0.21], Crowded cutoff 0.10 [0.06, 0.14], Style diverse 0.12 [0.08, 0.16].
  * Regret vs mu_field (BB): Separated control −54.2 [−74.3, −36.5], Crowded cutoff −21.2 [−40.4, −1.6], Style diverse −11.6 [−24.7, 1.1].
  * Wrong vs mu_field: Separated control −0.90 [−1.26, −0.54], Crowded cutoff −0.62 [−1.04, −0.18], Style diverse −0.12 [−0.48, 0.24].
* **Uncertainty:** Bootstrap paired by source tournament (50 sources, J = 1 replay each). The frozen arm adds fresh poker randomness, so the contrast includes that noise.
* **Fields:** Identity and rank-correlation contrasts favour adaptive in all three. Regret clear in separated_control and crowded_cutoff; style_diverse regret and wrong-vs-mu_field intervals include zero.
* **Identity vs strength:** Rerun identity metrics agree in all fields; reference-based metrics agree in two of three.
* **Consistency:** Direction consistent in all three fields on every metric; strength of evidence varies by field.
* **Defensible wording:** In a source-schedule counterfactual, adaptive Swiss selected more consistently than a frozen replay of its own realised schedule in all three controlled fields.
* **Overclaim (avoid):**
  * Avoid: "adaptive Swiss causally improves selection" or a clean causal estimate of adaptation.
  * Avoid: "adaptive pairing reduces regret in every field".

### Card 5. Duplicate packages (Experiment D)

* **Support:**
  * Rerun Spearman, ordinary vs R40H67x6: Separated control 0.43 [0.40, 0.46] vs 0.54 [0.52, 0.56], Crowded cutoff 0.37 [0.34, 0.40] vs 0.51 [0.48, 0.54], Style diverse 0.43 [0.41, 0.45] vs 0.49 [0.47, 0.52] (intervals do not overlap in any field).
  * R40H67x6 minus ordinary, rerun changed qualifiers: Separated control −0.45 [−0.79, −0.13], Crowded cutoff −0.31 [−0.62, 0.00], Style diverse −0.17 [−0.46, 0.09]; regret (BB): Separated control −17.3 [−33.0, −3.6], Crowded cutoff −16.6 [−33.8, 1.3], Style diverse −8.2 [−20.1, 2.6].
  * R7H400x6 minus ordinary, rerun changed qualifiers: Separated control −0.12 [−0.46, 0.21], Crowded cutoff −0.49 [−0.78, −0.20], Style diverse 0.14 [−0.15, 0.42]; regret (BB): Separated control −8.3 [−26.3, 8.8], Crowded cutoff −23.7 [−36.5, −11.1], Style diverse 4.4 [−10.3, 18.4].
  * Scheduled work 1.050 (R7H400x6) and 1.005 (R40H67x6) of ordinary; played hands about 1.05 and 1.06 to 1.07.
* **Uncertainty:** Paired bootstrap on 50 shared replicate ids. Spearman is compared on levels (no paired Spearman contrast stored for D).
* **Fields:** R40H67x6: Spearman higher in all three; changed qualifiers clear only in separated_control (crowded_cutoff upper bound +0.0009, includes zero). R7H400x6: clear improvement only in crowded_cutoff.
* **Identity vs strength:** R40H67x6: identity and regret both negative in all fields, regret clear only in separated_control. R7H400x6: agree in crowded_cutoff; mixed elsewhere.
* **Consistency:** Directionally consistent for R40H67x6; not consistent for R7H400x6.
* **Defensible wording:** In an operational package comparison, the short-match six-lane duplicate package gave higher rerun rank correlation than ordinary play in all three controlled fields, with consistently negative but mostly inconclusive qualifier and regret contrasts; the fewer-rounds duplicate package helped only in the crowded-cutoff field.
* **Overclaim (avoid):**
  * Avoid: "duplication causally reduces variance" (both packages also change rounds or match length).
  * Avoid: "short duplication significantly improves selection in every field".

### Card 6. Error severity: wrong qualifiers are mostly clearly weaker entrants

* **Support:**
  * Share of wrong qualifiers outside the mu_field reference-ambiguous set (baseline + mu_swiss, 250 tournaments): Separated control 1.00, Crowded cutoff 0.80, Style diverse 0.79.
  * Mean regret per wrong qualifier (BB per match): Separated control 44.0, Crowded cutoff 24.7, Style diverse 24.7.
  * Correlation of wrong-qualifier count with regret across tournaments: Separated control 0.90, Crowded cutoff 0.79, Style diverse 0.79.
  * Baseline clear misqualifications vs wrong qualifiers: Separated control 2.74 of 2.74, Crowded cutoff 2.82 of 3.52, Style diverse 3.06 of 3.80.
* **Uncertainty:** Pooled descriptive shares (no interval computed). The ambiguous set uses 5% < P(reference top 6) < 95%; a different band would move borderline bots.
* **Fields:** All three; strongest in separated_control (no ambiguous bots).
* **Identity vs strength:** This card is the bridge: identity errors carry large strength costs.
* **Consistency:** Consistent: roughly four in five wrong qualifiers are clearly weaker in the two fields with reference ambiguity.
* **Defensible wording:** Most selection errors in these controlled fields admitted bots the mu_field reference clearly places outside the top 6, rather than swaps among near-equals.
* **Overclaim (avoid):**
  * Avoid: "errors are only near-equal swaps" (opposite of the data) and "every error is costly" (some are ambiguous swaps).

### Card 7. Reference uncertainty is small relative to tournament noise; references agree

* **Support:**
  * Reference self-regret (BB; bootstrap median [2.5, 97.5 percentile]): Separated control 0.0 [0.0, 0.0], Crowded cutoff 2.7 [0.0, 10.7], Style diverse 1.5 [0.0, 9.8] vs tournament regret 122.9 [110.3, 137.9], 93.7 [81.2, 105.3], 94.3 [85.5, 103.7].
  * Regret interval with reference uncertainty propagated: Separated control 122.9 [105.7, 142.1], Crowded cutoff 93.7 [82.5, 112.3], Style diverse 94.3 [82.7, 112.3].
  * mu_field vs mu_swiss ordering: Spearman 0.978, 0.970, 0.980; Kendall 0.885, 0.869, 0.890; no significant discordant pairs.
  * Wrong vs mu_field and wrong vs mu_swiss baseline counts are equal or nearly equal: Separated control 2.74 / 2.74, Crowded cutoff 3.52 / 3.52, Style diverse 3.80 / 3.74.
* **Uncertainty:** crowded_cutoff mu_field reference still fires its rule at the 500-round ceiling (one bot outside the designed sets, P(top 6) 0.208); reference P(same top 6) 0.205 (crowded) and 0.366 (style).
* **Fields:** All three; least reference uncertainty in separated_control.
* **Identity vs strength:** Agree: wrong-qualifier counts barely change between references; regret intervals widen modestly.
* **Consistency:** Consistent.
* **Defensible wording:** Finite reference uncertainty was small relative to tournament noise, and the mu_field and mu_swiss references ordered the bots almost identically in all three controlled fields.
* **Overclaim (avoid):**
  * Avoid: "the references are the true skill ranking" or "the crowded-cutoff reference top 6 is settled".

## 4. Results that need nuanced interpretation

### 4.1 Separated control: highest regret despite the fewest misses

* Wrong vs mu_field: Separated control 2.74 [2.50, 3.00] (fewest) but regret 122.9 [110.3, 137.9] BB (highest).
* Each miss costs about 44 BB per match there vs about 25 BB in the other two fields, because a miss replaces a leader 23.8 BB above the next bot.
* Read counts (wrong qualifiers, changed qualifiers) for frequency and regret for cost; do not rank fields by regret alone.

### 4.2 R20 vs R40 is much closer than R10 vs R40

* R10H1600 minus R40H400 regret (BB): Separated control 65.7 [47.2, 84.9], Crowded cutoff 29.6 [12.8, 46.2], Style diverse 41.7 [27.0, 57.1].
* R20H800 minus R40H400 regret (BB): Separated control 8.9 [−10.2, 26.5], Crowded cutoff −4.0 [−21.9, 12.4], Style diverse 13.5 [−1.7, 29.4].
* Only style_diverse R20 changed qualifiers excludes zero (0.34 [0.05, 0.62]).
* Do not read an absent R20 difference as equivalence; intervals are about +/-0.3 qualifiers and +/-17 BB.

### 4.3 Matched-played-hands result is not uniform across fields

* R10H1600 vs the R40 prefix with matched played hands:
* Separated control: changed qualifiers 0.68 [0.41, 0.93], wrong vs mu_field 0.90 [0.48, 1.30], regret 51.5 [27.8, 72.5] BB.
* Crowded cutoff: changed qualifiers 0.10 [−0.15, 0.37], wrong vs mu_field 0.04 [−0.28, 0.38], regret 10.5 [−5.9, 28.3] BB.
* Style diverse: changed qualifiers 0.21 [−0.01, 0.48], wrong vs mu_field 0.48 [0.18, 0.82], regret 23.6 [9.2, 39.2] BB.
* Clear on both metrics in separated_control; regret and wrong-vs-mu_field (not changed qualifiers) in style_diverse; inconclusive in crowded_cutoff.
* Post hoc and descriptive; prefixes of baseline tournaments are not independent tournaments with fewer rounds scheduled.

### 4.4 Short duplication: directionally consistent, not individually significant everywhere

* R40H67x6 minus ordinary, rerun changed qualifiers: Separated control −0.45 [−0.79, −0.13], Crowded cutoff −0.31 [−0.62, 0.00], Style diverse −0.17 [−0.46, 0.09].
* Regret (BB): Separated control −17.3 [−33.0, −3.6], Crowded cutoff −16.6 [−33.8, 1.3], Style diverse −8.2 [−20.1, 2.6].
* The consistent evidence is direction in all three fields plus higher rerun Spearman in all three. Only separated_control excludes zero on changed qualifiers and regret. Figure 4 panel b (Spearman) was chosen after the results were seen; report the changed-qualifier contrasts alongside it.
* In crowded_cutoff the R7H400x6 package has the largest single improvement (−0.49 [−0.78, −0.20] qualifiers).

### 4.5 Crowded cutoff is not dominated by cheap near-equal swaps

* Share of wrong qualifiers clearly outside the reference-ambiguous set: 0.80; mean cost 24.7 BB per wrong qualifier.
* Baseline clear misqualifications 2.82 of 3.52 wrong; clear omissions only 1.22, because several reference top-6 members are themselves ambiguous.
* The designed crowd makes the reference boundary uncertain, but the tournament mostly errs by admitting clearly weaker bots, not by swapping crowd members.

### 4.6 Regret is not directly comparable across fields

* Regret is BB per match summed over six qualifiers; its scale depends on each field's strength spread (mu_field SD across bots: Separated control 25.4, Crowded cutoff 22.8, Style diverse 22.7 BB; rank-6/7 gap Separated control 23.8, Crowded cutoff 0.6, Style diverse 2.0 BB).
* Compare regret within a field across conditions; compare fields with identity metrics.
* mu_swiss regret is on a compressed scale (adaptive pairing): baseline regret vs mu_swiss Separated control 75.1 [66.7, 83.9], Crowded cutoff 64.9 [56.7, 72.8], Style diverse 58.6 [51.8, 66.3] BB; do not mix with mu_field regret.

### 4.7 Experiment C is not a clean causal estimate

* The frozen schedules were produced by adaptive trajectories, so the frozen arm inherits pairings informed by the source tournament's poker outcomes.
* Fresh poker randomness in the replay adds variance to the paired contrast; J = 1 replay per source.
* style_diverse regret −11.6 [−24.7, 1.1] BB and wrong vs mu_field −0.12 [−0.48, 0.24] include zero.
* Use "source-schedule counterfactual"; do not decompose into an effect of adaptation.

### 4.8 Experiment D is an operational package comparison

* R7H400x6 changes rounds (40 to 7) and R40H67x6 changes match length (400 to 67) as well as adding duplication.
* Scheduled work is 1.050 and 1.005 of ordinary; played hands are about 5 to 7% higher.
* Mechanism (descriptive diagnostic, not tested): in 400-hand persistent matches about 60% of bot-lanes bust and duplicate trajectories diverge early, so little card luck cancels; in 67-hand lanes busts are rare and lanes stay coupled.

### 4.9 Baseline vs mu_swiss per-bot differences are within noise

* Baseline P(qualify) uses 50 tournaments (Wilson half-widths up to about 0.14); mu_swiss uses 200 (up to about 0.07).
* Example: nit-e3-s1 in separated_control, mu_swiss 0.58 [0.52, 0.65] vs baseline 0.38 [0.26, 0.52].

### 4.10 P(qualify) is not monotone in mu_field below the cutoff

* Bots outside the reference top 6 that qualify more often than the weakest reference top-6 bot (mu_swiss 200): Separated control (weakest top-6 P = 0.310): none; Crowded cutoff (weakest top-6 P = 0.165): maniac-e2-s3 (rank 7) 0.170, loose-e2-s1 (rank 8) 0.185, tight-e2-s3 (rank 9) 0.190, station-e1-s0 (rank 13) 0.205, loose-e3-s1 (rank 20) 0.185, maniac-e3-s2 (rank 26) 0.170, maniac-e1-s0 (rank 28) 0.210; Style diverse (weakest top-6 P = 0.170): loose-e0 (rank 7) 0.210, tight-e2-s1 (rank 9) 0.230, aggressive-e3-s3 (rank 10) 0.220, station-e2-s1 (rank 12) 0.220, trapper-e2-s2 (rank 13) 0.210, aggressive-e2-s0 (rank 17) 0.200, aggressive-e0 (rank 19) 0.200.
* In the flat 0.15 to 0.25 band, mu_field rank predicts P(qualify) weakly; differences of a few points are within Wilson intervals (about +/-0.06).
* Archetype residuals (ranks 7 to 30, vs a linear fit on mu_field) are small and inconsistent: maniac +0.071, +0.047, −0.018 across the three fields. No claim that high-variance styles systematically over-qualify.

### 4.11 Noise vs spread consistency check (descriptive)

* Median per-bot tournament-to-tournament SD of the mean per-match score (mu_swiss 200): Separated control 17.6, Crowded cutoff 18.5, Style diverse 19.1 BB.
* SD of mu_swiss per-match score across bots: Separated control 17.7, Crowded cutoff 17.0, Style diverse 17.8 BB.
* Noise is about as large as the between-bot spread inside the Swiss mechanism; the implied signal share 0.50, 0.46, 0.47 is in line with rerun Spearman 0.43, 0.37, 0.43.
* Approximate (score correlation vs rank correlation; Swiss pairing compresses spread). Supporting context, not a result.

## 5. Field profiles

One frozen field per scenario: each profile describes that field only. No regime-level claims.

### 5.1 Separated control (`0b30004f650324e5`)

* **Purpose:** Engineered easy-selection control: if selection fails here, the cause is tournament noise, not reference ambiguity at the cutoff.
* **Reference gap:** mu_field rank-6/7 gap 23.8 BB; P(same top 6) 0.999; P(6/7 reversal) 0.000; no reference-ambiguous bots.
* **Validation evidence:** Built once from the 2,000 existing pool rounds (construction gap 23.3 BB) and bound before validation; one-shot validation on 4,000 fresh pool-style rounds (seed family `fhr3b-2026-separated-control-validation`): P(leaders are the top 6) 0.998 (required >= 0.95), max non-leader P(top 6) 0.0015, gap 12.36 BB (one-sided 95% LCB 4.38). Field-relative mu_field reference generated independently afterwards.
* **Baseline selection reliability:** rerun changed qualifiers 3.83 [3.59, 4.07]; wrong vs mu_field 2.74 [2.50, 3.00]; regret 122.9 [110.3, 137.9] BB; rerun Spearman 0.43 [0.40, 0.46]; mu_swiss 200: changed 3.82 [3.69, 3.94], wrong 2.79 [2.66, 2.92].
* **Important P(qualify) values:** Leaders (mu_swiss 200): station-e2-s2 0.65, maniac-e2-s2 0.76, nit-e3-s1 0.58, station-e2-s3 0.31, trapper-e3-s3 0.52, neutral-e1-s0 0.39. Best non-leaders: maniac-e1-s0 (rank 17) 0.24, loose-e2-s1 (rank 9) 0.20 (P(qualify) is not monotone in mu_field below the gap). Exact reference top 6 selected in 2 of 250 tournaments.
* **What it shows:** Even with six independently validated leaders far above the rest, 40 x 400 adaptive Swiss misses about half of them per tournament; every wrong qualifier is clearly weaker.
* **What it does not show:** It is engineered (strongest defensible six plus the 54 weakest pool bots); it is not representative of any natural field. Its validation ran in pool context; the field-relative reference confirmed the separation.

### 5.2 Crowded cutoff (`afbffedfc3706d84`)

* **Purpose:** Qualification-boundary stress test: three designed leaders and a designed near-equal crowd at ranks 4 to about 15.
* **Reference gap:** mu_field rank-6/7 gap 0.61 BB at 500 matched rounds; P(same top 6) 0.205; P(6/7 reversal) 0.439; 7 reference-ambiguous bots.
* **Validation evidence:** Pre-registered mu_field rule fired at 250 and again at the 500-round ceiling (loose-e2-s1, outside the designed sets, P(top 6) 0.208). Carried as residual reference uncertainty. Designed leaders all have P(top 6) >= 0.95.
* **Baseline selection reliability:** rerun changed qualifiers 4.32 [4.12, 4.50]; wrong vs mu_field 3.52 [3.26, 3.80]; regret 93.7 [81.2, 105.3] BB; rerun Spearman 0.37 [0.34, 0.40]; mu_swiss 200: changed 4.19 [4.07, 4.31], wrong 3.46 [3.33, 3.59].
* **Important P(qualify) values:** Top mu_field ranks (mu_swiss 200): station-e2-s2 0.68, maniac-e2-s2 0.73, trapper-e3-s3 0.49, aggressive-e2-s0 0.26, aggressive-e1-s0 0.21, neutral-e1-s1 0.17, maniac-e2-s3 0.17, loose-e2-s1 0.18. Only 3 bots qualify with P >= 0.35 (station-e2-s2 (rank 1), maniac-e2-s2 (rank 2), trapper-e3-s3 (rank 3)); every other bot is at or below 0.26, on both sides of the reference boundary. Best bots outside the reference top 6: maniac-e1-s0 (rank 28) 0.21, station-e1-s0 (rank 13) 0.20, tight-e2-s3 (rank 9) 0.19.
* **What it shows:** Selection noise dominates even where the reference boundary is uncertain: 80% of wrong qualifiers are clearly outside the ambiguous set.
* **What it does not show:** Nothing about crowded fields as a class (one field). The reference top 6 below the three leaders is not settled.

### 5.3 Style diverse (`ad7d6596ef1c8c3e`)

* **Purpose:** Strategically heterogeneous field (style x strength balanced; no near-duplicate parameter vectors).
* **Reference gap:** mu_field rank-6/7 gap 2.02 BB at 500 matched rounds; P(same top 6) 0.366; P(6/7 reversal) 0.353; 5 reference-ambiguous bots; rule does not fire at 500 (locked).
* **Validation evidence:** Diversity audit: 8 archetypes, 60/60 distinct parameter vectors, 0 near-duplicate pairs (styles LA:17 LP:13 TA:13 TP:17).
* **Baseline selection reliability:** rerun changed qualifiers 4.38 [4.18, 4.56]; wrong vs mu_field 3.80 [3.58, 4.08]; regret 94.3 [85.5, 103.7] BB; rerun Spearman 0.43 [0.41, 0.45]; mu_swiss 200: changed 4.43 [4.34, 4.52], wrong 3.79 [3.65, 3.92].
* **Important P(qualify) values:** Top mu_field ranks (mu_swiss 200): maniac-e2-s2 0.69, station-e2-s2 0.48, trapper-e3-s3 0.22, nit-e3-s1 0.42, neutral-e2-s1 0.22, tight-e3-s2 0.17, loose-e0 0.21, neutral-e1-s2 0.14. Only 3 bots qualify with P >= 0.35 (maniac-e2-s2 (rank 1), station-e2-s2 (rank 2), nit-e3-s1 (rank 4)); every other bot is at or below 0.23, on both sides of the reference boundary. Best bots outside the reference top 6: tight-e2-s1 (rank 9) 0.23, aggressive-e3-s3 (rank 10) 0.22, station-e2-s1 (rank 12) 0.22.
* **What it shows:** Results from the other two fields are not an artefact of near-duplicate agents: reliability is similar with strategically distinct bots.
* **What it does not show:** Nothing about style mixes in general; one field, synthetic stateless agents.

## 6. Reference analysis

| Field | Spearman | Kendall | Significant discordant pairs | Point top-6 overlap | Largest rank displacements in mu_field top 12 (mu_field vs mu_swiss rank) |
|---|---|---|---|---|---|
| Separated control | 0.978 | 0.885 | 0 | 6 / 6 | station-e3-s0 (8 vs 15), trapper-e1-s2 (11 vs 17), loose-e2-s0 (12 vs 8) |
| Crowded cutoff | 0.970 | 0.869 | 0 | 6 / 6 | trapper-e0 (11 vs 19), loose-e2-s0 (10 vs 15), aggressive-e1-s1 (12 vs 16) |
| Style diverse | 0.980 | 0.890 | 0 | 5 / 6 | neutral-e1-s2 (8 vs 15), tight-e3-s2 (6 vs 12), station-e2-s1 (12 vs 7) |

| Field | mu_field rounds | Median SE (BB) | Split-half r | mu_field P(same top 6) | mu_swiss P(same top 6) | Reference-ambiguous bots | Reference self-regret (BB; median [2.5, 97.5]) | Baseline regret: tournament CI / propagated CI |
|---|---|---|---|---|---|---|---|---|
| Separated control | 250 | 4.04 | 0.957 | 0.999 | 1.000 | 0 | 0.0 [0.0, 0.0] | 122.9 [110.3, 137.9] / 122.9 [105.7, 142.1] |
| Crowded cutoff | 500 | 2.88 | 0.966 | 0.205 | 0.212 | 7 | 2.7 [0.0, 10.7] | 93.7 [81.2, 105.3] / 93.7 [82.5, 112.3] |
| Style diverse | 500 | 2.92 | 0.970 | 0.366 | 0.232 | 5 | 1.5 [0.0, 9.8] | 94.3 [85.5, 103.7] / 94.3 [82.7, 112.3] |

* mu_field and mu_swiss are different estimands (random-partition play vs the adaptive Swiss mechanism); their near-identical orderings are evidence that the conclusions do not depend on the choice of reference, not that either is a context-free ranking.
* Discordance is confined to near-equal bots: no pair is significantly discordant in any field, and the largest top-12 rank displacements are listed above.
* Reference self-regret (regret of the reference's own point top 6 under its bootstrap; median [2.5, 97.5 percentile]) is Separated control 0.0 [0.0, 0.0], Crowded cutoff 2.7 [0.0, 10.7], Style diverse 1.5 [0.0, 9.8] BB, against tournament regret of 122.9 [110.3, 137.9], 93.7 [81.2, 105.3], 94.3 [85.5, 103.7] BB.
* Propagating reference uncertainty widens regret intervals modestly and leaves wrong-qualifier intervals nearly unchanged (Section 2.1).
* Why tournament noise dominates: per-bot SE of mu_field is about 3 to 4 BB per match after 250 to 500 matched duplicate rounds, while one tournament gives each bot 40 single-lane matches whose mean varies by about 18 BB between tournaments (Section 4.11).
* mu_swiss vs mu_field selection metrics differ in scale (Swiss pairing compresses spread), so compare regret only within one reference.
* **Reporting change (dossier cleanup).** The frozen analysis stores `reference_self_regret` as the bootstrap MEAN paired with a 2.5/97.5 PERCENTILE interval. In the separated control 999 of 1,000 resamples give zero, so the mean (0.000297 BB) lies above a [0, 0] interval. The dossier now reports the bootstrap MEDIAN with the same percentile interval in every field and table, recomputed read-only by `scripts/fhr4_export_self_regret.py` from the same resamples (the recomputed means reproduce the stored values; `exports/reference_self_regret.csv`). Stored analysis outputs are unchanged; the means remain in the results sheet as `*_reference_self_regret_mean` rows without an interval.

## 7. Figures

No figure was redesigned. The plotted values in each figure data CSV were re-checked against the analysis outputs (`tests/test_fhr4_dossier.py`) and the caption numbers against this dossier; no error was found.

### Figure 1. Reliability vs rounds (main text)

* **Question:** How do wrong qualifiers and regret change as Swiss rounds accumulate (5 to 40)?
* **Source CSV:** `paper/fhr4/figures/data/fig1_reliability_vs_rounds.csv` (built from round_sweep.csv)
* **Plotted metrics:** (a) wrong vs mu_field; (b) qualification regret (BB); by prefix and field, 95% bootstrap.
* **Principal takeaway:** Separated control wrong 4.18 to 2.74; Crowded cutoff wrong 4.58 to 3.52; Style diverse wrong 4.56 to 3.80; monotone, no plateau within 40 rounds.
* **Caption caveat:** Prefixes of the same tournaments (correlated points); separated control has the highest regret because each miss is costlier, not because it has more misses; nothing implied beyond 40 rounds.

### Figure 2. Rounds vs match length (main text)

* **Question:** At an equal scheduled hand budget, is it better to play more rounds or longer matches?
* **Source CSV:** `paper/fhr4/figures/data/fig2_allocation_equal_scheduled_budget.csv` (built from budget_allocation.csv, contrasts.csv, audit_extra.json)
* **Plotted metrics:** (a) rerun changed qualifiers; (b) regret; (c, d) paired contrasts incl. the matched-played-hands row.
* **Principal takeaway:** R10H1600 worse than R40H400 in all fields (changed qualifiers 0.87 [0.60, 1.14], 0.42 [0.12, 0.69], 0.52 [0.25, 0.79]); R20H800 close to R40H400.
* **Caption caveat:** Only scheduled hands are equal (played 57%, 80%, 94%); matched-played row differs by field and metric.

### Figure 3. Adaptive vs frozen schedule (main text)

* **Question:** Does adaptive Swiss select more reliably than a frozen replay of its own realised schedule?
* **Source CSV:** `paper/fhr4/figures/data/fig3_adaptive_vs_frozen.csv` (built from frozen_schedule.csv)
* **Plotted metrics:** Adaptive minus frozen: (a) rerun changed qualifiers; (b) regret; paired by source.
* **Principal takeaway:** Changed qualifiers Separated control −0.80 [−1.06, −0.56], Crowded cutoff −0.38 [−0.65, −0.11], Style diverse −0.33 [−0.59, −0.09].
* **Caption caveat:** Source-schedule counterfactual, not a causal estimate; style_diverse regret interval includes zero.

### Figure 4. Duplicate packages (main text)

* **Question:** Do six-lane duplicate packages of about equal scheduled work select more consistently than ordinary play?
* **Source CSV:** `paper/fhr4/figures/data/fig4_duplicate_packages.csv` (built from duplicate_play.csv, contrasts.csv)
* **Plotted metrics:** (a) rerun changed qualifiers; (b) rerun Spearman; (c, d) paired contrasts for changed qualifiers and regret.
* **Principal takeaway:** R40H67x6 Spearman 0.54 vs 0.43, 0.51 vs 0.37, 0.49 vs 0.43 (dup vs ordinary).
* **Caption caveat:** Operational package comparison; changed-qualifier contrasts individually clear only in separated control; panel b metric chosen after results were seen.

### Figure 5. Qualification probability at the cutoff (main text)

* **Question:** How likely is each bot near the reference boundary to qualify under 40 x 400 adaptive Swiss?
* **Source CSV:** `paper/fhr4/figures/data/fig5_qualification_probability_at_cutoff.csv` (built from exports/qualification_probabilities_all_cells.csv)
* **Plotted metrics:** P(qualify) from mu_swiss 200 (Wilson 95%) with baseline-50 diamonds, ordered by mu_field rank.
* **Principal takeaway:** Separated control leaders 0.31 to 0.76; exact top 6 in 2 of 250; flat 0.15 to 0.25 band after the top two or three bots in the other fields.
* **Caption caveat:** Baseline diamonds have intervals about twice as wide; individual baseline deviations are within noise.

### Figure S1. Identity vs strength errors (supplement)

* **Question:** Are wrong qualifiers near-equal swaps or clearly weaker bots, and how does regret scale with wrong count?
* **Source CSV:** `paper/fhr4/figures/data/figS1_identity_vs_strength_error.csv` (built from exports/tournament_errors.csv)
* **Plotted metrics:** (a to c) regret vs wrong count per tournament; (d) share of wrong qualifiers clearly outside the reference-ambiguous set.
* **Principal takeaway:** Clearly-outside share Separated control 1.00, Crowded cutoff 0.80, Style diverse 0.79; correlation 0.90, 0.79, 0.79.
* **Caption caveat:** Pooled descriptive (baseline 50 + mu_swiss 200); ambiguous band 5% to 95%.

## 8. Tables

Tables 1 to 3 are the frozen publication tables (`paper/fhr4/tables/`, `paper/fhr4/TABLES.md`), reproduced unchanged. Table 4 and Table A1 are new and generated here.

### Table 1. Final experimental design

| Field | Role | mu_field matched rounds | Matrix tournaments per cell | mu_swiss tournaments | Reference rank-6/7 gap (BB) | Reference P(same top 6) |
|---|---|---|---|---|---|---|
| Separated control | Engineered easy-selection control (six independently validated leaders) | 250 | 50 | 200 | 23.8 | 0.999 |
| Crowded cutoff | Qualification-boundary stress test (designed near-equal crowd) | 500 | 50 | 200 | 0.6 | 0.205 |
| Style diverse | Strategically heterogeneous field (style x strength balanced) | 500 | 50 | 200 | 2.0 | 0.366 |

### Table 2. Baseline reliability (R40H400, 50 tournaments per field)

| Field | Rerun changed qualifiers | Rerun top-6 overlap | Rerun Spearman | Wrong vs mu_field | Qualification regret (BB) | Boundary strength loss (BB) |
|---|---|---|---|---|---|---|
| Separated control | 3.83 [3.59, 4.07] | 2.17 [1.93, 2.41] | 0.43 [0.40, 0.46] | 2.74 [2.50, 3.00] | 122.9 [110.3, 137.9] | 60.0 [55.7, 64.6] |
| Crowded cutoff | 4.32 [4.12, 4.50] | 1.68 [1.50, 1.88] | 0.37 [0.34, 0.40] | 3.52 [3.26, 3.80] | 93.7 [81.2, 105.3] | 58.5 [53.0, 63.8] |
| Style diverse | 4.38 [4.18, 4.56] | 1.62 [1.44, 1.82] | 0.43 [0.41, 0.45] | 3.80 [3.58, 4.08] | 94.3 [85.5, 103.7] | 46.3 [42.6, 49.8] |

### Table 3. Primary paired contrasts (first minus second; positive = first worse)

| Contrast | Field | Rerun changed qualifiers | Qualification regret (BB) |
|---|---|---|---|
| R10 x H1600 vs R40 x H400 | Separated control | 0.87 [0.60, 1.14] | 65.7 [47.2, 84.9] |
| R10 x H1600 vs R40 x H400 | Crowded cutoff | 0.42 [0.12, 0.69] | 29.6 [12.8, 46.2] |
| R10 x H1600 vs R40 x H400 | Style diverse | 0.52 [0.25, 0.79] | 41.7 [27.0, 57.1] |
| R20 x H800 vs R40 x H400 | Separated control | 0.17 [−0.18, 0.51] | 8.9 [−10.2, 26.5] |
| R20 x H800 vs R40 x H400 | Crowded cutoff | −0.07 [−0.39, 0.24] | −4.0 [−21.9, 12.4] |
| R20 x H800 vs R40 x H400 | Style diverse | 0.34 [0.05, 0.62] | 13.5 [−1.7, 29.4] |
| Adaptive vs frozen schedule (R40 x H400) | Separated control | −0.80 [−1.06, −0.56] | −54.2 [−74.3, −36.5] |
| Adaptive vs frozen schedule (R40 x H400) | Crowded cutoff | −0.38 [−0.65, −0.11] | −21.2 [−40.4, −1.6] |
| Adaptive vs frozen schedule (R40 x H400) | Style diverse | −0.33 [−0.59, −0.09] | −11.6 [−24.7, 1.1] |
| Duplicate R40 x H67 x6 vs ordinary | Separated control | −0.45 [−0.79, −0.13] | −17.3 [−33.0, −3.6] |
| Duplicate R40 x H67 x6 vs ordinary | Crowded cutoff | −0.31 [−0.62, 0.00] | −16.6 [−33.8, 1.3] |
| Duplicate R40 x H67 x6 vs ordinary | Style diverse | −0.17 [−0.46, 0.09] | −8.2 [−20.1, 2.6] |
| Duplicate R7 x H400 x6 vs ordinary | Separated control | −0.12 [−0.46, 0.21] | −8.3 [−26.3, 8.8] |
| Duplicate R7 x H400 x6 vs ordinary | Crowded cutoff | −0.49 [−0.78, −0.20] | −23.7 [−36.5, −11.1] |
| Duplicate R7 x H400 x6 vs ordinary | Style diverse | 0.14 [−0.15, 0.42] | 4.4 [−10.3, 18.4] |

### Table 4. Final references

| Field | mu_field matched rounds | mu_field calibration | mu_field digest | Median SE (BB) | Split-half r | Rank-6/7 gap (BB) | mu_field P(same top 6) | mu_field P(6/7 reversal) | Reference-ambiguous bots | mu_field rule at final rounds | mu_swiss tournaments | mu_swiss P(same top 6) | mu_swiss max Wilson half-width | Spearman mu_field vs mu_swiss | Kendall mu_field vs mu_swiss | Point top-6 overlap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Separated control | 250 | 5be0e1c0 | 90ae3326 | 4.04 | 0.957 | 23.83 | 0.999 | 0.000 | 0 | does not fire (locked) | 200 | 1.000 | 0.069 | 0.978 | 0.885 | 6 |
| Crowded cutoff | 500 | 7d2640ae | f717e385 | 2.88 | 0.966 | 0.61 | 0.205 | 0.439 | 7 | fires (ceiling; carried as uncertainty) | 200 | 0.212 | 0.069 | 0.970 | 0.869 | 6 |
| Style diverse | 500 | 0caf92cc | f88129a4 | 2.92 | 0.970 | 2.02 | 0.366 | 0.353 | 5 | does not fire (locked) | 200 | 0.232 | 0.069 | 0.980 | 0.890 | 5 |

Note: mu_field reference ranks are the operational point ranking; membership inside the reference-ambiguous set is not resolved. The crowded-cutoff rule still fires at its 500-round ceiling.

### Table A1. Per-bot qualification probability (appendix; excerpt: mu_field ranks 1 to 12)

Full 180 rows: `tables/tableA1_per_bot_qualification.csv`.

| Field | mu_field rank | Bot | mu_field (BB) [SE] | P(ref top 6) | mu_swiss rank | P(qualify) mu_swiss 200 [Wilson] | P(qualify) baseline 50 [Wilson] |
|---|---|---|---|---|---|---|---|
| Separated control | 1 | station-e2-s2 | 73.7 [5.6] | 1.000 | 2 | 0.65 [0.58, 0.71] | 0.74 [0.60, 0.84] |
| Separated control | 2 | maniac-e2-s2 | 60.8 [5.6] | 1.000 | 1 | 0.76 [0.70, 0.81] | 0.64 [0.50, 0.76] |
| Separated control | 3 | nit-e3-s1 | 51.3 [5.4] | 1.000 | 3 | 0.58 [0.52, 0.65] | 0.38 [0.26, 0.52] |
| Separated control | 4 | station-e2-s3 | 50.6 [5.6] | 1.000 | 6 | 0.31 [0.25, 0.38] | 0.32 [0.21, 0.46] |
| Separated control | 5 | trapper-e3-s3 | 50.0 [4.7] | 1.000 | 4 | 0.52 [0.45, 0.59] | 0.62 [0.48, 0.74] |
| Separated control | 6 | neutral-e1-s0 | 47.9 [4.9] | 0.999 | 5 | 0.39 [0.32, 0.45] | 0.56 [0.42, 0.69] |
| Separated control | 7 | loose-e2-s3 | 24.0 [5.0] | 0.000 | 9 | 0.20 [0.15, 0.26] | 0.20 [0.11, 0.33] |
| Separated control | 8 | station-e3-s0 | 22.6 [5.2] | 0.001 | 15 | 0.17 [0.13, 0.23] | 0.16 [0.08, 0.29] |
| Separated control | 9 | loose-e2-s1 | 19.7 [5.0] | 0.000 | 7 | 0.20 [0.15, 0.27] | 0.16 [0.08, 0.29] |
| Separated control | 10 | neutral-e2-s0 | 18.9 [4.2] | 0.000 | 11 | 0.13 [0.09, 0.18] | 0.08 [0.03, 0.19] |
| Separated control | 11 | trapper-e1-s2 | 18.8 [4.1] | 0.000 | 17 | 0.09 [0.06, 0.14] | 0.08 [0.03, 0.19] |
| Separated control | 12 | loose-e2-s0 | 15.6 [4.5] | 0.000 | 8 | 0.16 [0.12, 0.22] | 0.16 [0.08, 0.29] |
| Crowded cutoff | 1 | station-e2-s2 | 66.5 [3.5] | 1.000 | 2 | 0.68 [0.61, 0.74] | 0.60 [0.46, 0.72] |
| Crowded cutoff | 2 | maniac-e2-s2 | 58.4 [4.2] | 1.000 | 1 | 0.73 [0.66, 0.79] | 0.74 [0.60, 0.84] |
| Crowded cutoff | 3 | trapper-e3-s3 | 54.9 [3.4] | 1.000 | 3 | 0.49 [0.43, 0.56] | 0.44 [0.31, 0.58] |
| Crowded cutoff | 4 | aggressive-e2-s0 | 25.2 [3.1] | 0.871 | 4 | 0.26 [0.20, 0.32] | 0.26 [0.16, 0.40] |
| Crowded cutoff | 5 | aggressive-e1-s0 | 21.8 [2.7] | 0.593 | 5 | 0.21 [0.16, 0.28] | 0.22 [0.13, 0.35] |
| Crowded cutoff | 6 | neutral-e1-s1 | 21.8 [3.0] | 0.568 | 6 | 0.17 [0.12, 0.22] | 0.22 [0.13, 0.35] |
| Crowded cutoff | 7 | maniac-e2-s3 | 21.2 [2.9] | 0.468 | 9 | 0.17 [0.12, 0.23] | 0.16 [0.08, 0.29] |
| Crowded cutoff | 8 | loose-e2-s1 | 18.7 [3.6] | 0.208 | 10 | 0.18 [0.14, 0.24] | 0.22 [0.13, 0.35] |
| Crowded cutoff | 9 | tight-e2-s3 | 16.9 [3.0] | 0.069 | 8 | 0.19 [0.14, 0.25] | 0.14 [0.07, 0.26] |
| Crowded cutoff | 10 | loose-e2-s0 | 16.8 [3.2] | 0.073 | 15 | 0.14 [0.09, 0.19] | 0.18 [0.10, 0.31] |
| Crowded cutoff | 11 | trapper-e0 | 15.9 [2.8] | 0.027 | 19 | 0.10 [0.06, 0.14] | 0.08 [0.03, 0.19] |
| Crowded cutoff | 12 | aggressive-e1-s1 | 15.1 [3.3] | 0.033 | 16 | 0.14 [0.10, 0.20] | 0.30 [0.19, 0.44] |
| Style diverse | 1 | maniac-e2-s2 | 58.8 [4.2] | 1.000 | 1 | 0.69 [0.63, 0.75] | 0.76 [0.63, 0.86] |
| Style diverse | 2 | station-e2-s2 | 51.3 [3.6] | 1.000 | 2 | 0.48 [0.42, 0.55] | 0.50 [0.37, 0.63] |
| Style diverse | 3 | trapper-e3-s3 | 36.5 [3.2] | 1.000 | 4 | 0.22 [0.17, 0.28] | 0.16 [0.08, 0.29] |
| Style diverse | 4 | nit-e3-s1 | 34.4 [3.7] | 0.992 | 3 | 0.42 [0.36, 0.49] | 0.40 [0.28, 0.54] |
| Style diverse | 5 | neutral-e2-s1 | 32.3 [3.6] | 0.973 | 6 | 0.22 [0.17, 0.28] | 0.16 [0.08, 0.29] |
| Style diverse | 6 | tight-e3-s2 | 24.8 [3.6] | 0.393 | 12 | 0.17 [0.12, 0.23] | 0.22 [0.13, 0.35] |
| Style diverse | 7 | loose-e0 | 22.8 [3.4] | 0.195 | 9 | 0.21 [0.16, 0.27] | 0.22 [0.13, 0.35] |
| Style diverse | 8 | neutral-e1-s2 | 22.6 [3.1] | 0.176 | 15 | 0.14 [0.09, 0.19] | 0.14 [0.07, 0.26] |
| Style diverse | 9 | tight-e2-s1 | 22.5 [3.2] | 0.145 | 5 | 0.23 [0.18, 0.29] | 0.28 [0.17, 0.42] |
| Style diverse | 10 | aggressive-e3-s3 | 20.6 [3.5] | 0.067 | 10 | 0.22 [0.17, 0.28] | 0.10 [0.04, 0.21] |
| Style diverse | 11 | station-e2-s3 | 18.6 [3.4] | 0.021 | 11 | 0.17 [0.12, 0.22] | 0.14 [0.07, 0.26] |
| Style diverse | 12 | station-e2-s1 | 17.8 [3.5] | 0.013 | 7 | 0.22 [0.17, 0.28] | 0.20 [0.11, 0.33] |

## 9. Remaining limitations (prioritised)

| # | Limitation | Why it matters | What the study did | How to state it |
|---|---|---|---|---|
| 1 | One field per scenario | Tournament reruns are conditional on one frozen field per scenario; no regime-level inference. | Three deliberately different fields; results stated per field. | Results hold in these controlled fields; no claim about classes of fields. |
| 2 | Synthetic, stateless agents | Rule-based policy families without within-match opponent modelling may under- or over-state luck vs skill in real bot fields. | Diversity audit (8 archetypes; style_diverse has no near-duplicates). | Agents are synthetic stateless policies; transfer to adaptive agents is untested. |
| 3 | Engineered separated control | Built from the strongest defensible six plus the 54 weakest pool bots; not a natural field. | One-shot independent validation (P = 0.998) and an independent field-relative reference. | Use "engineered separated control"; never call it representative. |
| 4 | 40-round horizon only | Reliability had not plateaued at 40 rounds; how much more rounds would help is unknown. | Horizon fixed at 5 to 40 by preregistration; 60/80/120 explicitly not run. | "within the preregistered 40-round horizon"; no extrapolation. |
| 5 | Experiment C interpretation | Frozen schedules come from adaptive trajectories; replay adds fresh randomness; J = 1. | Paired by source tournament; termed a counterfactual from the start. | "source-schedule counterfactual"; not a causal effect of adaptation. |
| 6 | Experiment D interpretation | Duplicate packages also change rounds or match length; work ratios not exactly 1. | Reported scheduled and played work ratios; mechanism given only as a diagnostic. | "operational package comparison"; no isolated duplication effect. |
| 7 | Residual crowded-cutoff reference ambiguity | Reference top 6 below the three leaders is unsettled; a bot outside the designed sets has P(reference top 6) 0.208 at the 500-round ceiling. | Propagated reference uncertainty, clear-error counts, and agreement with mu_swiss. | Treat the crowded-cutoff reference boundary as uncertain; rely on rerun metrics and clear errors there. |
| 8 | Post-hoc clarification of matrix clause 2 | Decided after matrix data were seen; under the broad reading 4 of 18 cells would have extended 50 to 100. | Decision recorded before any extension ran; broad-reading verdicts reported as a sensitivity. | Disclose in methods with the sensitivity verdict. |
| 9 | Research semantics | Public-2026-style research semantics are not exact historical production settings, nor any future FullHouse rules. | Semantics fixed and documented; historical provenance separated from the research baseline. | No statement about historical results or future competition formats. |
| 10 | Runtime measurement | Wall-clock and CPU ratios are distorted by machine throttling and sleep. | Work measured in scheduled and played hands. | Report hands; CPU ratios indicative only. |

## 10. Closing pack

### 10.1 Executive research summary (one page)

* **Question.** How should a finite simulation budget be allocated so that a Swiss tournament reliably identifies the strongest poker bots (top 6 of 60, NLHE6)?
* **Design.** Three controlled fields (engineered separated control, crowded cutoff, style diverse); two independent references (mu_field reference from matched duplicate random partitions; mu_swiss reference from 200 adaptive tournaments); four experiments (A rounds, B equal scheduled hand budget, C source-schedule counterfactual, D operational package comparison); 900 matrix tournaments; preregistered extension rules applied, with one post-hoc clarification disclosed (matrix clause 2); simulation frozen.
* **Baseline.** At 40 x 400, independent reruns disagreed on 3.83 to 4.38 of 6 qualifiers and 2.74 to 3.80 selected bots were outside the mu_field reference top 6. In the engineered separated control, validated leaders qualified with probability 0.31 to 0.76; the exact top 6 was selected in 2 of 250 tournaments.
* **Rounds.** Every reliability metric improved at every step from 5 to 40 rounds in all three fields, with no evidence of a plateau within the preregistered 40-round horizon.
* **Rounds vs match length.** At an equal scheduled hand budget, ten 1,600-hand rounds were worse than forty 400-hand rounds in all three fields (changed qualifiers 0.87 [0.60, 1.14], 0.42 [0.12, 0.69], 0.52 [0.25, 0.79]); twenty 800-hand rounds were close to forty.
* **Adaptive pairing.** Adaptive Swiss beat a frozen replay of its own schedule on rerun changed qualifiers in all three fields (−0.80 [−1.06, −0.56], −0.38 [−0.65, −0.11], −0.33 [−0.59, −0.09]).
* **Duplicate packages.** The short-match duplicate package raised rerun rank correlation in all three fields; qualifier contrasts were consistently negative but individually clear only in the separated control. The fewer-rounds package helped only in the crowded cutoff.
* **Errors and references.** Most wrong qualifiers were clearly weaker bots (100%, 80%, 79%). Reference uncertainty was small next to tournament noise, and the two references agreed (Spearman 0.97 to 0.98).
* **Scope.** One frozen field per scenario, synthetic stateless agents, research semantics, 40-round horizon; no regime-level or future-format claims.

### 10.2 Methods summary (one page)

* **Mechanism.** NLHE6, N = 60, K = 6, adaptive Swiss, persistent-stack matches scored by raw chip delta, public tiebreaks; public-2026-style research semantics; engine `4647ee69857e7c9b`.
* **Fields.** separated_control `0b30004f650324e5` (engineered; one-shot validation on 4,000 fresh pool rounds), crowded_cutoff `afbffedfc3706d84`, style_diverse `ad7d6596ef1c8c3e`; one frozen field per scenario.
* **mu_field reference.** Matched 6-lane whole-match duplicate random partitions, cyclic seats, common chance streams, independent seed family; 250 / 500 / 500 matched rounds; analytic SE; joint round bootstrap (unit = one matched round).
* **mu_swiss reference.** 200 complete 40 x 400 adaptive tournaments per field in a separate namespace.
* **Matrix.** Six unique cells per field x 50 tournaments: R40H400 adaptive (baseline; A prefixes 5/10/20/30/40), R20H800 and R10H1600 (B), frozen replay J = 1 (C), R7H400x6 and R40H67x6 duplicate (D).
* **Metrics.** Primary: rerun changed qualifiers; wrong qualifiers and qualification regret vs the mu_field reference. Supporting: overlap, rank correlations, boundary strength loss, mu_swiss-based metrics, reference-propagated intervals, self-regret, clear errors, per-bot P(qualify).
* **Inference.** Tournament bootstrap for levels; paired bootstrap on shared replicate ids for contrasts (by source tournament in C); Wilson for proportions; 95% throughout.
* **Extension rules (preregistered).** mu_field per field kind (250 to 500 ceiling); matrix half-width > 0.30 or pair-specific rerun changed-qualifier contrast spanning +/-0.25 (regret report-only); mu_swiss Wilson half-width > 0.08 in [0.10, 0.90] (100 to 200 ceiling; at 200 max possible 0.069).
* **Integrity.** Identity hashes, append-only resumable runs, digest verification, zero-sum and seating checks, exact replays, HOLD and simulation-freeze guards.
* **Not run.** Horizons beyond 40 rounds; matrix 50 to 100; references beyond their ceilings; second field-construction attempts.

### 10.3 Results summary (one page)

* **Baseline (rerun changed / wrong vs mu_field / regret BB):** Separated control 3.83 [3.59, 4.07] / 2.74 [2.50, 3.00] / 122.9 [110.3, 137.9]; Crowded cutoff 4.32 [4.12, 4.50] / 3.52 [3.26, 3.80] / 93.7 [81.2, 105.3]; Style diverse 4.38 [4.18, 4.56] / 3.80 [3.58, 4.08] / 94.3 [85.5, 103.7].
* **mu_swiss 200 replication (changed / wrong):** Separated control 3.82 [3.69, 3.94] / 2.79 [2.66, 2.92]; Crowded cutoff 4.19 [4.07, 4.31] / 3.46 [3.33, 3.59]; Style diverse 4.43 [4.34, 4.52] / 3.79 [3.65, 3.92].
* **Separated control leaders:** P(qualify) 0.31 to 0.76; exact top 6 in 2/250.
* **A (wrong vs mu_field, R5 to R40):** Separated control 4.18 to 2.74; Crowded cutoff 4.58 to 3.52; Style diverse 4.56 to 3.80; monotone in every metric.
* **B R10H1600 minus R40H400 (changed / regret):** Separated control 0.87 [0.60, 1.14] / 65.7 [47.2, 84.9]; Crowded cutoff 0.42 [0.12, 0.69] / 29.6 [12.8, 46.2]; Style diverse 0.52 [0.25, 0.79] / 41.7 [27.0, 57.1].
* **B R20H800 minus R40H400 (changed / regret):** Separated control 0.17 [−0.18, 0.51] / 8.9 [−10.2, 26.5]; Crowded cutoff −0.07 [−0.39, 0.24] / −4.0 [−21.9, 12.4]; Style diverse 0.34 [0.05, 0.62] / 13.5 [−1.7, 29.4].
* **B matched played hands, R10 regret:** Separated control 51.5 [27.8, 72.5]; Crowded cutoff 10.5 [−5.9, 28.3]; Style diverse 23.6 [9.2, 39.2] (post hoc).
* **C adaptive minus frozen (changed / regret):** Separated control −0.80 [−1.06, −0.56] / −54.2 [−74.3, −36.5]; Crowded cutoff −0.38 [−0.65, −0.11] / −21.2 [−40.4, −1.6]; Style diverse −0.33 [−0.59, −0.09] / −11.6 [−24.7, 1.1].
* **D R40H67x6 minus ordinary (changed / regret):** Separated control −0.45 [−0.79, −0.13] / −17.3 [−33.0, −3.6]; Crowded cutoff −0.31 [−0.62, 0.00] / −16.6 [−33.8, 1.3]; Style diverse −0.17 [−0.46, 0.09] / −8.2 [−20.1, 2.6].
* **D R7H400x6 minus ordinary (changed):** Separated control −0.12 [−0.46, 0.21]; Crowded cutoff −0.49 [−0.78, −0.20]; Style diverse 0.14 [−0.15, 0.42].
* **Error severity:** clearly-outside share 1.00, 0.80, 0.79; cost per wrong qualifier 44.0, 24.7, 24.7 BB.
* **References:** Spearman mu_field vs mu_swiss 0.978, 0.970, 0.980; self-regret (median [2.5, 97.5]) 0.0 [0.0, 0.0], 2.7 [0.0, 10.7], 1.5 [0.0, 9.8] BB.

### 10.4 Figure and table index

| Item | Placement | File(s) | Source data | Evidence card(s) |
|---|---|---|---|---|
| Figure 1 | main | figures/fig1_reliability_vs_rounds.{pdf,svg,png} | figures/data/fig1_reliability_vs_rounds.csv | F2 |
| Figure 2 | main | figures/fig2_allocation_equal_scheduled_budget.{pdf,svg,png} | figures/data/fig2_allocation_equal_scheduled_budget.csv | F3 |
| Figure 3 | main | figures/fig3_adaptive_vs_frozen.{pdf,svg,png} | figures/data/fig3_adaptive_vs_frozen.csv | F4 |
| Figure 4 | main | figures/fig4_duplicate_packages.{pdf,svg,png} | figures/data/fig4_duplicate_packages.csv | F5 |
| Figure 5 | main | figures/fig5_qualification_probability_at_cutoff.{pdf,svg,png} | figures/data/fig5_qualification_probability_at_cutoff.csv | F1, F6 |
| Figure S1 | supplement | figures/figS1_identity_vs_strength_error.{pdf,svg,png} | figures/data/figS1_identity_vs_strength_error.csv | F6 |
| Table 1 | main | tables/table1_design.csv | field references, config | - |
| Table 2 | main | tables/table2_baseline_reliability.csv | baseline_reliability.csv | F1 |
| Table 3 | main | tables/table3_primary_contrasts.csv | contrasts.csv, frozen_schedule.csv | F3, F4, F5 |
| Table 4 | main or methods | dossier/tables/table4_final_references.csv | reference.json, summary.json | F7 |
| Table A1 | appendix | dossier/tables/tableA1_per_bot_qualification.csv | exports/qualification_probabilities_all_cells.csv, field_references.csv | F1, F6 |

### 10.5 Claims ledger

**Strongly supported (can be stated in Results)**

| ID | Tier | Claim | Reason | Evidence |
|---|---|---|---|---|
| S1 | strong | At R40H400, independent reruns disagree on 3.83 to 4.38 of 6 qualifiers in these controlled fields. | Tight intervals in all three fields; replicated by the independent 200-tournament mu_swiss sample. | Table 2; 2.1; 2.6; Card F1 |
| S2 | strong | 2.74 to 3.80 of the selected six are outside the mu_field reference top 6 at R40H400. | All fields; consistent against mu_swiss reference; robust to reference propagation. | Table 2; Card F1, F7 |
| S3 | strong | In the engineered separated control, each validated leader qualifies with probability 0.31 to 0.76, and the exact top 6 was selected in 2 of 250 tournaments. | Wilson intervals from 200 tournaments; leaders independently validated. | Figure 5a; Table A1; Card F1 |
| S4 | strong | Reliability improves continuously with rounds, with no evidence of a plateau within the preregistered 40-round horizon. | Monotone at every step on every metric in every field. | Figure 1; 2.2; Card F2 |
| S5 | strong | At an equal scheduled hand budget, ten 1,600-hand rounds select less reliably than forty 400-hand rounds in all three controlled fields. | Paired contrasts exclude zero on rerun changed qualifiers and regret in every field. | Figure 2; Table 3; Card F3 |
| S6 | strong | In the source-schedule counterfactual, adaptive Swiss is more consistent than a frozen replay of its own schedule in all three controlled fields. | Changed-qualifier and rerun rank-correlation contrasts exclude zero in every field. | Figure 3; Table 3; Card F4 |
| S7 | strong | Most wrong qualifiers are bots the mu_field reference clearly places outside the top 6. | Shares 1.00, 0.80, 0.79; regret tracks wrong count (r 0.90, 0.79, 0.79). | Figure S1; Card F6 |
| S8 | strong | Reference uncertainty is small relative to tournament noise, and the mu_field and mu_swiss references order the bots almost identically. | Self-regret median <= 2.7 BB (97.5 percentile <= 10.7) vs tournament regret >= 94 BB; Spearman >= 0.97; no significant discordant pairs. | Section 6; Table 4; Card F7 |

**Supported with qualification (needs scope or wording)**

| ID | Tier | Claim | Reason | Evidence |
|---|---|---|---|---|
| Q1 | qualified | Twenty 800-hand rounds perform close to forty 400-hand rounds. | Intervals include zero except style_diverse changed qualifiers (0.34 [0.05, 0.62]); absence of difference is not equivalence. | Table 3; 4.2 |
| Q2 | qualified | Part of the R10H1600 deficit persists at matched played hands. | Holds in separated_control (both metrics) and style_diverse (regret, wrong vs mu_field); inconclusive in crowded_cutoff; post hoc descriptive. | 2.3; 4.3; Figure 2 last rows |
| Q3 | qualified | Adaptive pairing reduces regret relative to the frozen replay. | Clear in separated_control and crowded_cutoff; style_diverse regret −11.6 [−24.7, 1.1] includes zero. | Figure 3b; 4.7 |
| Q4 | qualified | The short-match six-lane duplicate package is more consistent than ordinary play. | Rerun Spearman higher in all three fields; changed-qualifier and regret contrasts negative everywhere but individually clear only in separated_control; package comparison. | Figure 4; 4.4 |
| Q5 | qualified | The fewer-rounds six-lane duplicate package helps in the crowded-cutoff field. | Only that field (−0.49 [−0.78, −0.20]); not in the other two. | Table 3; Figure 4 |
| Q6 | qualified | Duplication helps only when lanes stay coupled (short matches). | Mechanistic reading consistent with bust rates and played-hand ratios; not tested directly. | 4.8; Figure 4 caption |
| Q7 | qualified | Tournament noise per bot is about as large as the between-bot strength spread inside Swiss. | Descriptive approximation in this dossier (Section 4.11); not a preregistered analysis. | derived_checks.json |
| Q8 | qualified | The separated control has the costliest errors. | True for regret per wrong qualifier, but driven by its engineered gap; regret is not comparable across fields. | 4.1; 4.6 |

**Unsupported / avoid**

| ID | Tier | Claim | Reason | Evidence |
|---|---|---|---|---|
| A1 | avoid | Swiss is unreliable in general. | One frozen field per scenario; synthetic agents; research semantics. | Limitations 1, 2, 9 |
| A2 | avoid | 40 rounds are insufficient in general. | Only these fields; no external target reliability; no horizon beyond 40. | Limitations 1, 4 |
| A3 | avoid | The tournament fails to recover true skill. | References are mechanism-specific estimands; no true skill ranking exists in the design. | 1.4; Section 6 |
| A4 | avoid | Compute was held fixed in Experiment B. | Only scheduled hands were equal; played fractions 0.57 / 0.80 / 0.94; runtime throttled. | 2.3; Limitation 10 |
| A5 | avoid | Adaptive Swiss causally improves selection. | Experiment C is a source-schedule counterfactual with inherited adaptive schedules and fresh randomness. | 4.7; Limitation 5 |
| A6 | avoid | Duplication causally reduces variance. | Experiment D packages also change rounds or match length. | 4.8; Limitation 6 |
| A7 | avoid | The separated control is representative. | Engineered from the strongest six plus the 54 weakest pool bots. | 5.1; Limitation 3 |
| A8 | avoid | R10 is worse at equal played hands everywhere. | Inconclusive in crowded_cutoff; identity metric inconclusive in style_diverse. | 4.3 |
| A9 | avoid | Reliability plateaus at some number of rounds, or N more rounds would reach a target. | No plateau observed and no data beyond 40 rounds. | Figure 1; Limitation 4 |
| A10 | avoid | Selection errors are mainly near-equal swaps at the cutoff. | About four in five (all, in the separated control) are clearly weaker bots. | Figure S1; 4.5 |
| A11 | avoid | Crowded fields (or diverse fields) require X rounds. | No regime-level inference from one field per scenario. | Limitation 1 |
| A12 | avoid | Results describe historical FullHouse events or any future competition format. | Research semantics only; no future-format statements. | Limitation 9 |
| A13 | avoid | High-variance styles systematically over-qualify relative to their strength. | Archetype residuals are small and change sign across fields; not analysed as a hypothesis. | 4.10; derived_checks.json |
| A14 | avoid | Short duplication significantly improves selection in every field. | Individually clear only in separated_control on qualifier and regret contrasts. | 4.4 |

### 10.6 Provenance timeline

Classification per change: bug fix; protocol clarification; descriptive analysis; genuinely pre-registered decision. Two field-replacement decisions fit none of these honestly and are labelled **post-hoc design decision** (each was pre-registered before its own new data). `Data seen` records whether outcome data relevant to the decision existed when it was made.

| Date | Commit | Event | Classification | Data seen | Effect on results | Record |
|---|---|---|---|---|---|---|
| 2026-09-30 | `75408be` | Fields and duplicate evaluation protocol frozen; original `spread` field selected from the 96-bot pool calibration for a large rank-6/7 gap (16.8 BB, 2.89 SE). | genuinely pre-registered decision | pool calibration only | Defined the original third field. | configs/fhr3b/fields/retired/spread-selection-bias/README.md |
| 2026-10-01 | `fec0aed` | Heads-up heuristic role bug fixed; affected NLHE fields revoked and re-frozen (2291f5c). | bug fix | no core data | Fields used in FHR4 are the corrected ones. | git history |
| 2026-10-01 | `1e35878` | mu_field estimator fixed before launch: normalised scale, analytic SE, joint round bootstrap, per-lane persistence. | genuinely pre-registered decision | no reference data | Defines the mu_field reference. | docs/fhr3b/FIELD_REFERENCE_PLAN.md |
| 2026-10-01 | `3226137` | Scope fixed to NLHE6 core: 3 fields, 6 unique cells, 50 tournaments per cell, mu_field 250. | genuinely pre-registered decision | no core data | Defines the study. | paper/FHR3B_SCOPE.md |
| 2026-10-01 | `c488026` | Methodology hardening: analysis plan, metrics (incl. regret), reference uncertainty, B/C/D wording, extension rules. | genuinely pre-registered decision | no core data | Defines metrics and rules. | docs/fhr3b/FHR4_CORE.md |
| 2026-10-01 | `28c4207` | Pre-launch rule correction: mu_swiss threshold 0.08; regret never triggers an extension; crowded "outside" = outside both designed sets. | protocol clarification | no core data | Rules as applied. | configs/fhr3b/matrix.yaml |
| 2026-10-02 | `b872c16` | mu_field references at 250 rounds; the preregistered rule fires in spread, crowded_cutoff and style_diverse (EXTEND_TO_500). | genuinely pre-registered decision | yes (reference data) | Crowded and style extended to 500. | reports/fhr3b/field-calibration/nlhe6/MU_FIELD_AUDIT.md |
| 2026-10-02 | `b872c16` | Selection bias discovered: spread's 16.8 BB pool gap measured 0.71 BB by the field-relative mu_field reference (regression to the mean from selecting on noisy estimates). | descriptive analysis | yes | Spread placed on HOLD. | MU_FIELD_AUDIT.md; retired README |
| 2026-10-02 | `c425a5f` | spread retired (held, provenance kept); spread_v2 split-sample protocol pre-registered (select on even pool rounds, validate once on odd rounds, no second attempt). | post-hoc design decision | yes (spread reference) | Replaced the third field. | configs/fhr3b/fields/retired/; SPREAD_V2_REPORT.md |
| 2026-10-02 | `d01d551` | spread_v2 candidate selected on the selection half only (not frozen). | genuinely pre-registered decision | selection half only | - | spread_v2/selection.json |
| 2026-10-02 | `9e321ca` | spread_v2 held-out validation FAILED (P(leaders are top 6) 0.208 vs 0.95 required); stopped, no re-selection. | genuinely pre-registered decision | held-out half | No spread-type field from this split. | spread_v2/validation.json |
| 2026-10-02 | `64a90e6` | separated_control construction and one-shot validation protocol pre-registered. | post-hoc design decision | yes (2,000 pool rounds used for construction) | Defined the replacement field. | docs/fhr3b/FHR4_CORE.md |
| 2026-10-02 | `d7568e8` | separated_control candidate `0b30004f650324e5` built once and bound to the validation protocol before any validation round. | genuinely pre-registered decision | construction data only | - | separated_control/construction.json, binding.json |
| 2026-10-03 | `bd732e3` | One-shot validation on 4,000 fresh pool-style rounds PASSED (P(leaders are top 6) 0.998). | genuinely pre-registered decision | fresh data | Field frozen. | separated_control/validation.json |
| 2026-10-03 | `9171b2c` | separated_control frozen into the core; crowded_cutoff and style_diverse mu_field references extended to 500; crowded still fires at the ceiling (carried as uncertainty), style locks. | genuinely pre-registered decision | yes | Final references for two fields. | FHR4_CORE.md section 6c |
| 2026-10-04 | `d7db218` | Independent separated_control mu_field reference (250 matched rounds; seed family `fhr3b-2026-spread-v2`, prepared for a spread_v2 reference that was never run, assigned in the protocol before validation); rule does not fire; locked. | genuinely pre-registered decision | yes | Final reference for separated control. | nlhe6-separated_control/reference.json |
| 2026-10-05 | `dce170d` | Matrix complete: 18 cells x 50 = 900 tournaments verified; audit, including matched-played-hands comparison (descriptive). | genuinely pre-registered decision | yes | All A to D results. | MATRIX_AUDIT.md; audit_extra.json |
| 2026-10-05 | `931d942` | Extension contrasts paired per pair of cells (previously over the intersection of all three cells); all three pairs within B and D now reported. | bug fix | yes | Changed some contrast intervals; definitions unchanged. | MATRIX_AUDIT.md |
| 2026-10-05 | `931d942` | Clause 2 clarified: rerun changed qualifiers govern the matrix rule; wrong-vs-reference contrasts become a sensitivity. Under the broad reading 4 cells would have extended 50 to 100. | protocol clarification | yes (matrix results) | Original audit (dce170d) said EXTEND_TO_100 for these 4 cells; final verdict 18/18 LOCK_AT_50. | MATRIX_AUDIT.md; summary.json extension_rules |
| 2026-10-05 | `931d942` | Horizon confirmed: Experiment A stays at 5 to 40 rounds; 60/80/120 dropped from FHR4 (future, separately preregistered). | protocol clarification | yes | No horizon extension. | configs/fhr3b/matrix.yaml |
| 2026-10-05 | `9f72e79` | mu_swiss 100-tournament report; preregistered rule fires in all three fields (half-widths 0.080 to 0.096). | genuinely pre-registered decision | yes | mu_swiss extended to 200. | git 9f72e79 |
| 2026-10-05 | `db45b56` | mu_swiss complete at 200 per field (ceiling); audited; SIMULATION FREEZE (publication commands refuse to run). | genuinely pre-registered decision | yes | Final inventory. | MU_SWISS_AUDIT.md; matrix.yaml simulation_freeze |
| 2026-10-05 | `e222c9a` | Publication package: per-tournament error export (clear-outside shares, cost per wrong qualifier); Figure 2 played-hand labels corrected; Figure 4 panel b set to rerun Spearman after results were seen. | descriptive analysis | yes | Presentation and descriptive analyses only. | paper/fhr4/ |
| 2026-10-05 | - | This dossier: noise-vs-spread consistency check, rank displacement between references, Table 4 and Table A1. | descriptive analysis | yes | Descriptive only. | paper/fhr4/dossier/ |
| 2026-10-05 | - | Dossier cleanup: reference_self_regret reported as bootstrap median with its percentile interval (was bootstrap mean with a percentile interval, incoherent in separated_control); recomputed read-only from the same resamples. | bug fix | yes | Reporting only; stored analysis outputs and all other numbers unchanged. | scripts/fhr4_export_self_regret.py; exports/reference_self_regret.csv |

**Researcher degrees of freedom, in one place.**

* Field replacement (spread to separated_control) was decided after reference data showed selection bias; the replacement was constructed once and validated once on fresh data under a never-used seed family before inclusion.
* The spread_v2 attempt failed and was not retried; no further field searches were made.
* Clause 2 was clarified after matrix data were seen; the broad reading would have extended 4 cells (sensitivity verdict reported).
* The pair-specific pairing change is a correctness fix; it changed some contrast intervals, not metric definitions.
* Figure 4 panel b (Spearman) and the matched-played-hands comparison were chosen or added after results were seen; both are presented as descriptive with the primary contrasts alongside.
* All extension rules for references were applied mechanically; ceilings (500 rounds, 200 tournaments) were preregistered and respected.
* No simulation outcome was discarded: every stored tournament in the 18 matrix cells and 3 mu_swiss cells is analysed; the retired spread reference is kept unchanged for provenance.

