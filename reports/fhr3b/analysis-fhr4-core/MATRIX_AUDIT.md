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

## 2. Decision table (pre-registered 50 → 100 rule, applied mechanically)

| Field | Cell | Changed qualifiers (rerun) | Top-6 overlap | Regret (BB, vs mu_field) | CI HW changed | CI HW overlap | Contrast trigger? | Decision |
|---|---|---:|---:|---:|---:|---:|---|---|
| separated_control | baseline | 3.83 | 2.17 | 122.9 | 0.239 | 0.239 | no | **LOCK_AT_50** |
| separated_control | R20H800 | 4.00 | 2.00 | 131.8 | 0.254 | 0.254 | no | **LOCK_AT_50** |
| separated_control | R10H1600 | 4.70 | 1.30 | 188.6 | 0.158 | 0.158 | no | **LOCK_AT_50** |
| separated_control | frozen R40H400 | 4.63 | 1.37 | 177.1 | 0.180 | 0.180 | no | **LOCK_AT_50** |
| separated_control | R7H400x6 dup | 3.71 | 2.29 | 114.6 | 0.256 | 0.256 | no | **LOCK_AT_50** |
| separated_control | R40H67x6 dup | 3.38 | 2.62 | 105.6 | 0.256 | 0.256 | no | **LOCK_AT_50** |
| crowded_cutoff | baseline | 4.32 | 1.68 | 93.7 | 0.192 | 0.192 | B mu_field_reference_changed CI [-0.40, 0.42]; B mu_swiss_reference_changed CI [-0.50, 0.26] | **EXTEND_TO_100** |
| crowded_cutoff | R20H800 | 4.26 | 1.74 | 89.7 | 0.217 | 0.217 | B mu_field_reference_changed CI [-0.40, 0.42]; B mu_swiss_reference_changed CI [-0.50, 0.26] | **EXTEND_TO_100** |
| crowded_cutoff | R10H1600 | 4.74 | 1.26 | 123.3 | 0.186 | 0.186 | no | **LOCK_AT_50** |
| crowded_cutoff | frozen R40H400 | 4.70 | 1.30 | 114.9 | 0.188 | 0.188 | no | **LOCK_AT_50** |
| crowded_cutoff | R7H400x6 dup | 3.84 | 2.16 | 70.0 | 0.256 | 0.256 | no | **LOCK_AT_50** |
| crowded_cutoff | R40H67x6 dup | 4.01 | 1.99 | 77.1 | 0.194 | 0.194 | no | **LOCK_AT_50** |
| style_diverse | baseline | 4.38 | 1.62 | 94.3 | 0.191 | 0.191 | D mu_field_reference_changed CI [-0.44, 0.28]; D mu_swiss_reference_changed CI [-0.26, 0.46] | **EXTEND_TO_100** |
| style_diverse | R20H800 | 4.72 | 1.28 | 107.8 | 0.172 | 0.172 | no | **LOCK_AT_50** |
| style_diverse | R10H1600 | 4.90 | 1.10 | 136.0 | 0.177 | 0.177 | no | **LOCK_AT_50** |
| style_diverse | frozen R40H400 | 4.71 | 1.29 | 105.9 | 0.168 | 0.168 | no | **LOCK_AT_50** |
| style_diverse | R7H400x6 dup | 4.51 | 1.49 | 98.6 | 0.166 | 0.166 | D mu_field_reference_changed CI [-0.44, 0.28]; D mu_swiss_reference_changed CI [-0.26, 0.46] | **EXTEND_TO_100** |
| style_diverse | R40H67x6 dup | 4.20 | 1.80 | 86.1 | 0.224 | 0.224 | no | **LOCK_AT_50** |

No cell fires the half-width clause (the maximum is 0.256). Four cells fire the paired-contrast clause, through
reference-changed-qualifier contrasts.

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

1. **Extension pairing.** The B and D contrasts are computed over replicates common to ALL three cells of
   the experiment. Extending only the two flagged cells would not change the contrasts that triggered the
   flags. Contrasts must be paired per contrast before extending, or the extension is wasted.
2. **Reading of clause 2.** The committed rule applies it to every qualifier-unit contrast, including
   reference-changed qualifiers. Read narrowly as rerun changed qualifiers only, no cell would extend.
3. **Horizon.** The A curves have not stabilised at 40 rounds. No numeric stabilisation threshold was
   pre-registered for 60/80/120, so this is a decision for review.
4. **`mu_swiss` 100 → 200.** The pre-registered rule fires in all three fields, with Wilson half-widths
   0.080–0.096. This is a decision for review; it is not executed.
