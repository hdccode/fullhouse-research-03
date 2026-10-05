# FHR #4 core matrix audit: NLHE6, 3 fields × 6 cells × 50 tournaments

Written for: the FHR #4 researchers reviewing the completed matrix before any extension.

* **Protocol.** Commits `c488026` / `28c4207` / `64a90e6` govern; the pre-registered thresholds are
  unchanged.
* **Data.** `results/fhr3b`, run 2026-10-04.
* **Analysis.** `fhr3b analyse` (this directory), plus read-only computations in `audit_extra.json` and
  `audit_integrity.json`. No simulation was run for this audit.
* **Uncertainty.** All intervals are 95% tournament-level bootstraps, paired by replicate index (B, D) or
  by source tournament (C).
* **Scope.** One frozen field per scenario: statements are conditional on these three controlled fields.

## 1. Integrity: clean

**All 18 cells:**

* tournaments t000000–t000049 exactly, with no extra or partial directories;
* expected files present (`lanes.parquet` in all 6 duplicate cells);
* 900 of 900 digests verified, and the engine hash `4647ee69857e7c9b` in every lock;
* every table and every duplicate lane zero-sum;
* each bot seated exactly once per round;
* `fhr3b validate`: 50 of 50 validated per cell, 2 of 2 exact replays per cell, and the round-prefix
  identity exact at R = 5, 10, 20 and 30.

**Hands:** 145.32M scheduled, 126.19M played.

**Runs:**

* All cells completed in one invocation except `dup_shorter_matches`/style_diverse. Its first invocation
  (32 tournaments) was interrupted and therefore wrote no run record. Those 32 tournaments are
  digest-verified and validated, and the remaining 18 ran on resume.
* `mu_swiss` (100 per field) is also complete and validated. It ran in the same overnight chain.

**Caveat:** per-tournament runtime is distorted by machine throttling and sleep. Played hands are the work
measure, and CPU ratios are indicative only.

## 2. Decision table: CORRECTED 2026-10-05 (pair-specific contrasts; clause-2 clarification)

**Protocol clarification.** The wording was ambiguous; this was decided before any extension ran.

* In clause 2, "changed qualifiers" is the pre-registered rerun metric: expected changed qualifiers between
  independent tournaments.
* Every contrast is paired on the replicates shared by that pair of cells only. This fixes the earlier
  pairing over the intersection of all three cells.
* Wrong-vs-reference contrasts do not trigger an extension. Their verdict is reported below as a
  sensitivity.

| Field | Cell | Changed qualifiers (rerun) | Top-6 overlap | Regret (BB) | CI HW changed | CI HW overlap | Pair-specific rerun contrasts (none spans ±0.25) | Decision |
|---|---|---:|---:|---:|---:|---:|---|---|
| separated_control | baseline | 3.83 | 2.17 | 122.9 | 0.239 | 0.239 | B R20H800−baseline [-0.18,+0.51]; B R10H1600−baseline [+0.60,+1.14]; D R7H400x6 dup−baseline [-0.46,+0.21]; D R40H67x6 dup−baseline [-0.79,-0.13]; C frozen R40H400−baseline [+0.56,+1.06] | **LOCK_AT_50** |
| separated_control | R20H800 | 4.00 | 2.00 | 131.8 | 0.254 | 0.254 | B R20H800−baseline [-0.18,+0.51]; B R10H1600−R20H800 [+0.43,+0.98] | **LOCK_AT_50** |
| separated_control | R10H1600 | 4.70 | 1.30 | 188.6 | 0.158 | 0.158 | B R10H1600−baseline [+0.60,+1.14]; B R10H1600−R20H800 [+0.43,+0.98] | **LOCK_AT_50** |
| separated_control | frozen R40H400 | 4.63 | 1.37 | 177.1 | 0.180 | 0.180 | C frozen R40H400−baseline [+0.56,+1.06] | **LOCK_AT_50** |
| separated_control | R7H400x6 dup | 3.71 | 2.29 | 114.6 | 0.256 | 0.256 | D R7H400x6 dup−baseline [-0.46,+0.21]; D R40H67x6 dup−R7H400x6 dup [-0.68,-0.01] | **LOCK_AT_50** |
| separated_control | R40H67x6 dup | 3.38 | 2.62 | 105.6 | 0.256 | 0.256 | D R40H67x6 dup−baseline [-0.79,-0.13]; D R40H67x6 dup−R7H400x6 dup [-0.68,-0.01] | **LOCK_AT_50** |
| crowded_cutoff | baseline | 4.32 | 1.68 | 93.7 | 0.192 | 0.192 | B R20H800−baseline [-0.39,+0.24]; B R10H1600−baseline [+0.12,+0.69]; D R7H400x6 dup−baseline [-0.78,-0.20]; D R40H67x6 dup−baseline [-0.62,+0.00]; C frozen R40H400−baseline [+0.11,+0.65] | **LOCK_AT_50** |
| crowded_cutoff | R20H800 | 4.26 | 1.74 | 89.7 | 0.217 | 0.217 | B R20H800−baseline [-0.39,+0.24]; B R10H1600−R20H800 [+0.24,+0.74] | **LOCK_AT_50** |
| crowded_cutoff | R10H1600 | 4.74 | 1.26 | 123.3 | 0.186 | 0.186 | B R10H1600−baseline [+0.12,+0.69]; B R10H1600−R20H800 [+0.24,+0.74] | **LOCK_AT_50** |
| crowded_cutoff | frozen R40H400 | 4.70 | 1.30 | 114.9 | 0.188 | 0.188 | C frozen R40H400−baseline [+0.11,+0.65] | **LOCK_AT_50** |
| crowded_cutoff | R7H400x6 dup | 3.84 | 2.16 | 70.0 | 0.256 | 0.256 | D R7H400x6 dup−baseline [-0.78,-0.20]; D R40H67x6 dup−R7H400x6 dup [-0.17,+0.53] | **LOCK_AT_50** |
| crowded_cutoff | R40H67x6 dup | 4.01 | 1.99 | 77.1 | 0.194 | 0.194 | D R40H67x6 dup−baseline [-0.62,+0.00]; D R40H67x6 dup−R7H400x6 dup [-0.17,+0.53] | **LOCK_AT_50** |
| style_diverse | baseline | 4.38 | 1.62 | 94.3 | 0.191 | 0.191 | B R20H800−baseline [+0.05,+0.62]; B R10H1600−baseline [+0.25,+0.79]; D R7H400x6 dup−baseline [-0.15,+0.42]; D R40H67x6 dup−baseline [-0.46,+0.09]; C frozen R40H400−baseline [+0.09,+0.59] | **LOCK_AT_50** |
| style_diverse | R20H800 | 4.72 | 1.28 | 107.8 | 0.172 | 0.172 | B R20H800−baseline [+0.05,+0.62]; B R10H1600−R20H800 [-0.08,+0.42] | **LOCK_AT_50** |
| style_diverse | R10H1600 | 4.90 | 1.10 | 136.0 | 0.177 | 0.177 | B R10H1600−baseline [+0.25,+0.79]; B R10H1600−R20H800 [-0.08,+0.42] | **LOCK_AT_50** |
| style_diverse | frozen R40H400 | 4.71 | 1.29 | 105.9 | 0.168 | 0.168 | C frozen R40H400−baseline [+0.09,+0.59] | **LOCK_AT_50** |
| style_diverse | R7H400x6 dup | 4.51 | 1.49 | 98.6 | 0.166 | 0.166 | D R7H400x6 dup−baseline [-0.15,+0.42]; D R40H67x6 dup−R7H400x6 dup [-0.61,-0.03] | **LOCK_AT_50** |
| style_diverse | R40H67x6 dup | 4.20 | 1.80 | 86.1 | 0.224 | 0.224 | D R40H67x6 dup−baseline [-0.46,+0.09]; D R40H67x6 dup−R7H400x6 dup [-0.61,-0.03] | **LOCK_AT_50** |

**Primary verdict: 18 / 18 LOCK_AT_50.** No half-width exceeds 0.30 (the maximum is 0.256), and no pair-specific
rerun changed-qualifier contrast spans both −0.25 and +0.25.

### Sensitivity: broad reading (also counting wrong-vs-`mu_field` / `mu_swiss` contrasts). Reported only.

| Field | Cell | Primary (rerun changed qualifiers) | Broad reading (+ wrong-vs-reference contrasts) | Broad trigger |
|---|---|---|---|---|
| separated_control | baseline | LOCK_AT_50 | LOCK_AT_50 | — |
| separated_control | R20H800 | LOCK_AT_50 | LOCK_AT_50 | — |
| separated_control | R10H1600 | LOCK_AT_50 | LOCK_AT_50 | — |
| separated_control | frozen R40H400 | LOCK_AT_50 | LOCK_AT_50 | — |
| separated_control | R7H400x6 dup | LOCK_AT_50 | LOCK_AT_50 | — |
| separated_control | R40H67x6 dup | LOCK_AT_50 | LOCK_AT_50 | — |
| crowded_cutoff | baseline | LOCK_AT_50 | EXTEND_TO_100 | mu_field_reference_changed (B); mu_swiss_reference_changed (B) |
| crowded_cutoff | R20H800 | LOCK_AT_50 | EXTEND_TO_100 | mu_field_reference_changed (B); mu_swiss_reference_changed (B) |
| crowded_cutoff | R10H1600 | LOCK_AT_50 | LOCK_AT_50 | — |
| crowded_cutoff | frozen R40H400 | LOCK_AT_50 | LOCK_AT_50 | — |
| crowded_cutoff | R7H400x6 dup | LOCK_AT_50 | LOCK_AT_50 | — |
| crowded_cutoff | R40H67x6 dup | LOCK_AT_50 | LOCK_AT_50 | — |
| style_diverse | baseline | LOCK_AT_50 | EXTEND_TO_100 | mu_field_reference_changed (D); mu_swiss_reference_changed (D) |
| style_diverse | R20H800 | LOCK_AT_50 | LOCK_AT_50 | — |
| style_diverse | R10H1600 | LOCK_AT_50 | LOCK_AT_50 | — |
| style_diverse | frozen R40H400 | LOCK_AT_50 | LOCK_AT_50 | — |
| style_diverse | R7H400x6 dup | LOCK_AT_50 | EXTEND_TO_100 | mu_field_reference_changed (D); mu_swiss_reference_changed (D) |
| style_diverse | R40H67x6 dup | LOCK_AT_50 | LOCK_AT_50 | — |

Under the broad reading, 4 cells would extend. This does not govern the extension decision.

## Simulation freeze (2026-10-05)

`mu_swiss` was extended to 200 per field (`MU_SWISS_AUDIT.md`). With it, the matrix verdicts above are
unchanged (primary 18/18 LOCK_AT_50; broad sensitivity flags the same 4 cells). The FHR4 simulation
programme is COMPLETE (`core_fhr4.simulation_freeze`).

## 3. Key results

See the chat report of 2026-10-05; the numbers come from the CSVs in this directory. Summary:

* **Baseline 40×400 rerun agreement:**
  * changed qualifiers 3.83 / 4.32 / 4.38 (separated_control / crowded_cutoff / style_diverse);
  * Spearman 0.43 / 0.37 / 0.43;
  * against `mu_field`, wrong qualifiers 2.74 / 3.52 / 3.80 and regret 123 / 94 / 94 BB.
* **A:** monotone improvement from 5 to 40 rounds, with no plateau at 40.
* **B:** R10H1600 is worse than R40 in every field. R20H800 is about equal to R40 (both separated_control
  contrasts include 0).
* **C:** adaptive beats exogenous replay in every field (changed qualifiers −0.33 to −0.80).
* **D:** the 40×67×6 duplicate package is better than ordinary on most metrics; 7×400×6 is mixed.
* **References:** reference uncertainty is negligible against tournament noise. `mu_field` and `mu_swiss`
  agree (Spearman 0.97).

## 4. Issues found

1. **Extension pairing: FIXED (2026-10-05).** Contrasts are now paired per pair of cells
   (`_pairwise_contrasts`), and all three pairs within B and within D are reported.
2. **Reading of clause 2: RESOLVED (2026-10-05).** The rule uses rerun changed qualifiers; the broad reading
   is reported as a sensitivity.
3. **Horizon: RESOLVED (2026-10-05).** No 60/80/120 in FHR #4. The stated result: "reliability improved
   continuously through 40 rounds, with no evidence of a plateau within the pre-registered horizon".
   Longer horizons are future work, as a separately pre-registered follow-up.
4. **`mu_swiss` 100 → 200.** The pre-registered rule fires in all three fields, with Wilson half-widths
   0.080–0.096. This is a decision for review; it is not executed.
