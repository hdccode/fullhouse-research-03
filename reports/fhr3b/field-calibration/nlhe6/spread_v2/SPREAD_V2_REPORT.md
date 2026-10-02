# Corrected NLHE6 spread selection (spread_v2): result

Written for: the FHR #4 researchers deciding how to replace the retired spread field.

**The pre-registered split-sample attempt FAILED held-out validation.** No candidate is frozen.

* **Protocol:** `core_fhr4.spread_v2`, hash `b01323bccc932cf2`, committed in `c425a5f` before any
  held-out data were read.
* **Selection:** committed in `d01d551` before validation.
* **Validation:** run once (`attempts: 1`).

## Data and split

* **Data.** The existing NLHE6 pool calibration `nlhe6.nlhe6-pool.H400.pool-calibration.aadd073b`:
  2,000 independent rounds, 96 bots, 16 tables per round. Every bot plays one ordinary
  400-hand match per round.
* **Selection half:** even rounds, 1,000 rounds (16,000 matches; 1,000 per bot; median per-bot
  SE 5.1 BB).
* **Validation half:** odd rounds, 1,000 rounds (16,000 matches; 1,000 per bot).
* The halves are disjoint and complete (tested). Rounds are independent: lag-1 autocorrelation
  0.004, block variance ratio 1.00.

## Selection (even rounds only)

**Leaders** (selection-half mu; 6 archetypes, no near-duplicates):

| bot | mu (BB) |
|---|---|
| station-e2-s2 | 57.9 |
| maniac-e2-s2 | 56.3 |
| neutral-e1-s0 | 41.6 |
| nit-e3-s1 | 36.4 |
| trapper-e3-s3 | 35.4 |
| aggressive-e2-s3 | 32.4 |

**Separation.** A 3.0 SE separation was infeasible (53 eligible). The single logged relaxation
step to 2.75 SE gave 58 eligible.

* 32 non-leaders were excluded above the band.
* 4 were thinned by redundancy: nit-e0, maniac-e0, nit-e1-s0, tight-e0.

**Non-leaders (54):**

* all 8 archetypes and all 4 styles (LA 16, LP 10, TA 11, TP 17);
* 7 near-duplicate pairs, allowed among non-leaders;
* selection-half mu −56.4 … 8.6 BB.

**Selection gap:** 23.75 BB. **Candidate:** `nlhe6-spread_v2`, hash `82cefd0b3814ea03`, not frozen.

## Validation (odd rounds only, once)

| criterion | required | observed | |
|---|---|---|---|
| point top 6 = leaders | yes | no (G = −2.13 BB) | FAIL |
| P(leaders are the top 6), joint round bootstrap (2,000) | ≥ 0.95 | 0.208 (one-sided 95% LCB of G = −18.0 BB) | FAIL |
| max non-leader P(top 6) | ≤ 0.05 | 0.418 (trapper-e3-s2) | FAIL |

**Held-out top 10** (BB; P(top 6)):

| rank | bot | leader? | mu (BB) | P(top 6) |
|---|---|---|---|---|
| 1 | maniac-e2-s2 | L | 52.1 | 1.000 |
| 2 | station-e2-s2 | L | 47.6 | 1.000 |
| 3 | trapper-e3-s3 | L | 41.5 | 0.999 |
| 4 | nit-e3-s1 | L | 37.5 | 0.990 |
| 5 | neutral-e1-s0 | L | 29.8 | 0.869 |
| 6 | trapper-e3-s2 | | 22.5 | 0.418 |
| 7 | aggressive-e2-s3 | L | 20.4 | 0.275 |
| 8 | aggressive-e3-s2 | | 19.6 | 0.202 |
| 9 | maniac-e2-s3 | | 18.9 | 0.160 |
| 10 | tight-e2-s3 | | 14.3 | 0.028 |

**Diagnosis.** Regression to the mean ran in both directions:

* the sixth leader fell from 32.4 to 20.4 BB;
* three non-leaders, each at or below 8.6 BB on the selection half, scored 18.9–22.5 BB.

With about 5–6 BB per-bot SE per half, the sixth slot is noise-dominated.

## Is a clean spread field constructible from the existing 96 bots without new calibration?

**No, not demonstrably.** The full 2,000-round pool ranking shows five clearly strong bots:

| bot | mu (BB) |
|---|---|
| maniac-e2-s2 | 54.2 |
| station-e2-s2 | 52.7 |
| trapper-e3-s3 | 38.5 |
| nit-e3-s1 | 37.0 |
| neutral-e1-s0 | 35.7 |

After them comes a dense continuum (31.8, 29.1, 26.4, 26.3, 24.8, 24.1 … BB, each ±4 BB). The
pool has no naturally separated sixth agent. A clean 6/7 boundary therefore needs a wide excluded
band, plus independent data to certify it. The existing calibration cannot both select and
validate it; this attempt shows that.

Under the protocol the attempt stops here: there is no re-selection or re-validation on this
split.

## Cheapest valid alternatives (for decision; nothing run)

Planning estimates of pass probability come from a normal shrinkage model on the full-data
estimates. They are optimistic: global shrinkage understates top-tail regression.

| option | new data | design | P(pool-context validation pass) | extra compute |
|---|---|---|---|---|
| A. fresh independent pool data, 4,000 rounds | new pool calibration of the same 96-bot pool with a scoped new seed family (config-only, no engine change) | spread_v3, pre-registered before the data exist: select on all 2,000 existing rounds, widest band (6 leaders + 54 weakest; 23.3 BB gap; 8 archetypes, 4 styles, 15 near-duplicate pairs, strength −57 … 8 BB); validate once on the new rounds | about 0.91 | 25.6M scheduled hands (about 1.6 h at 4,260 h/s; 5.5 h at 1,289) |
| A′. same, 2,000 rounds | as A | as A | about 0.68 | 12.8M (about 0.8 h) |
| A″. 3-SE band instead of widest | as A | 18.0 BB gap, keeps more mid-strength bots | about 0.65 (4,000) / 0.28 (2,000) | as A / A′ |
| B. no new spread field | none | report the retired field only descriptively, as "clear top 5, open 6th"; the core matrix keeps crowded_cutoff and style_diverse | n/a | 0 |

**Further cost for any passing candidate.** It still needs a fresh field-relative `mu_field`
reference under its own seed family: 6M scheduled hands (about 0.47 h), plus up to 6M more if the
pre-registered spread rule fires at 250. The field-context shift seen in the audit (about noise
level) means pool-context validation is necessary but not sufficient.

**Trade-off.** The widest band gives the cleanest boundary, but the 54 non-leaders then span only
the lower part of the strength range (no mid-upper bots). The field becomes "six clear leaders
plus a broad weaker field". That still fits the spread scenario's purpose as a clean-selection
control.
