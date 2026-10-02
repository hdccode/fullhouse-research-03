# FHR #4 `mu_field` reference audit: NLHE6, 250 matched rounds

Written for: the FHR #4 researchers deciding whether to launch the matrix.

* **Protocol.** Commit `28c4207` governs. Thresholds were applied exactly as pre-registered.
* **Data.** `results/fhr3b/calibration/nlhe6.nlhe6-*.H400.dup.field-reference.*`, run
  2026-10-02.
* **Estimand.** `mu_field` is long-run expected performance against random partitions of each
  controlled field under the specified match semantics. It is reported in BB per
  ordinary-equivalent 400-hand match. It is an estimate, not universal poker skill.

## 1. Integrity: clean

| | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| calibration id | `nlhe6.nlhe6-spread.H400.dup.field-reference.3cea71b5` | `nlhe6.nlhe6-crowded_cutoff.H400.dup.field-reference.7d2640ae` | `nlhe6.nlhe6-style_diverse.H400.dup.field-reference.0caf92cc` |
| matched rounds | 250 (0–249, contiguous) | 250 | 250 |
| chunks / lane files (expected 25) | 25 / 25 | 25 / 25 | 25 / 25 |
| rows / lane rows | 15,000 / 90,000 | 15,000 / 90,000 | 15,000 / 90,000 |
| scheduled hands | 6,000,000 | 6,000,000 | 6,000,000 |
| played hands (ratio) | 5,669,268 (0.945) | 5,715,865 (0.953) | 5,650,196 (0.942) |
| wall-clock | 21.5 min (~4,400 h/s) | 22.3 min (~4,280 h/s) | 2 h 31 min, including one 2.2 h stall (~18 min active) |
| calibration digest | `98d90ea417bfa92d01fe415cd99624ff` | `10745eba8842cca4feba0e4076120130` | `f1dc65156dc12aa36aa3eacb1ea631f1` |
| lock engine hash / identity | `4647ee69857e7c9b` / matches | same | same |

**Checks, all passing for every field:**

* **Lane validation.** The built-in `verify_calibration_lanes` passes on 25/25 chunks.
* **Independent recheck** on all 15,000 lanes per field:
  * every lane is zero-sum;
  * every bot started in all six seats in every matched match;
  * lane deltas reconstruct the stored matched result exactly;
  * lane hands sum to the stored hands.
* **Exact replay.** Rounds 0 and 249 of each field were recomputed from scratch, and both the
  rows and the lane rows are identical.
* **Common deck.** In 4 replayed matched tables, 1,071 of 1,071 lane pairs with equal player
  counts show identical boards.
* **No failures.** There are no temp files, failed chunks or retries.

The only anomaly is the style_diverse wall-clock stall (a machine sleep or pause between
chunks). It did not affect the data.

## 2. Reference strengths

| | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| `mu_field` range (BB) | −48.9 … 65.4 | −43.5 … 66.4 | −49.1 … 60.8 |
| analytic SE min / median / max (BB) | 2.66 / 4.18 / 5.61 | 2.15 / 4.11 / 6.07 | 2.20 / 4.10 / 6.06 |
| median bootstrap SE (check; unit = one round) | 4.15 | 4.13 | 4.12 |
| split-half (even/odd rounds) Pearson / Spearman | 0.947 / 0.937 | 0.953 / 0.922 | 0.919 / 0.918 |
| split-half top-6 overlap | 4/6 | 5/6 | 3/6 |

The analytic and round-bootstrap SEs agree, which is consistent with independent rounds.

**Top 10 bots.** P(top 6) and the 95% rank interval come from the joint round bootstrap
(1,000 resamples).

**spread**

| rank | bot | mu (BB) | SE | P(top 6) | rank 95% |
|---|---|---|---|---|---|
| 1 | nlhe6-maniac-e2-s2 | 65.4 | 5.61 | 1.000 | 1–3 |
| 2 | nlhe6-station-e2-s2 | 64.0 | 5.46 | 1.000 | 1–3 |
| 3 | nlhe6-trapper-e3-s3 | 54.8 | 4.63 | 1.000 | 1–4 |
| 4 | nlhe6-station-e2-s3 | 41.2 | 5.27 | 0.948 | 4–7 |
| 5 | nlhe6-nit-e3-s1 | 40.0 | 5.07 | 0.923 | 4–8 |
| 6 | nlhe6-neutral-e1-s0 | 32.4 | 5.08 | 0.427 | 4–11 |
| 7 | nlhe6-aggressive-e2-s0 | 31.7 | 5.04 | 0.386 | 5–12 |
| 8 | nlhe6-aggressive-e1-s0 | 28.9 | 4.45 | 0.202 | 5–12 |
| 9 | nlhe6-maniac-e3-s2 | 24.9 | 4.68 | 0.052 | 6–15 |
| 10 | nlhe6-station-e0 | 24.6 | 4.79 | 0.036 | 6–16 |

**crowded_cutoff**

| rank | bot | mu (BB) | SE | P(top 6) | rank 95% |
|---|---|---|---|---|---|
| 1 | nlhe6-station-e2-s2 | 66.4 | 4.78 | 1.000 | 1–2 |
| 2 | nlhe6-maniac-e2-s2 | 57.0 | 6.07 | 1.000 | 1–3 |
| 3 | nlhe6-trapper-e3-s3 | 56.5 | 4.84 | 1.000 | 1–3 |
| 4 | nlhe6-aggressive-e2-s0 | 32.5 | 4.53 | 0.973 | 4–7 |
| 5 | nlhe6-maniac-e2-s3 | 23.6 | 4.24 | 0.490 | 4–16 |
| 6 | nlhe6-neutral-e1-s1 | 23.4 | 4.32 | 0.478 | 4–16 |
| 7 | nlhe6-aggressive-e1-s0 | 20.8 | 3.89 | 0.241 | 5–18 |
| 8 | nlhe6-neutral-e2-s0 | 19.1 | 4.13 | 0.145 | 5–22 |
| 9 | nlhe6-tight-e2-s3 | 18.6 | 4.43 | 0.119 | 5–23 |
| 10 | nlhe6-loose-e2-s0 | 18.0 | 4.53 | 0.134 | 5–25 |

**style_diverse**

| rank | bot | mu (BB) | SE | P(top 6) | rank 95% |
|---|---|---|---|---|---|
| 1 | nlhe6-maniac-e2-s2 | 60.8 | 6.06 | 1.000 | 1–2 |
| 2 | nlhe6-station-e2-s2 | 47.4 | 5.27 | 1.000 | 1–3 |
| 3 | nlhe6-trapper-e3-s3 | 36.4 | 4.54 | 0.973 | 2–7 |
| 4 | nlhe6-nit-e3-s1 | 35.1 | 5.23 | 0.935 | 2–8 |
| 5 | nlhe6-neutral-e2-s1 | 32.9 | 5.28 | 0.865 | 3–9 |
| 6 | nlhe6-tight-e3-s2 | 27.0 | 5.26 | 0.471 | 4–15 |
| 7 | nlhe6-station-e2-s1 | 22.8 | 5.27 | 0.194 | 5–19 |
| 8 | nlhe6-trapper-e2-s2 | 22.0 | 5.53 | 0.157 | 5–21 |
| 9 | nlhe6-loose-e0 | 21.9 | 4.92 | 0.124 | 5–20 |
| 10 | nlhe6-aggressive-e3-s3 | 21.9 | 4.82 | 0.106 | 5–19 |

### Comparison with the pool ranking the fields were built from

Within-field `mu_field` agrees closely with the pool-calibration ranking (Spearman 0.962 / 0.952 /
0.965). Field-minus-pool shifts were centred, because each field is zero-sum over its own 60 bots,
and divided by both estimates' SEs. Their standard deviation is 1.13 / 1.20 / 0.99, where 1 means
pure sampling noise; spread and crowded_cutoff each have one |z| > 3 outlier.

The spread boundary is therefore much tighter under `mu_field` than at construction:

* rank-6/7 gap 0.71 BB here, against 16.8 BB in the pool.
* This is mainly **regression to the mean**. The pool gap was measured on the same noisy
  estimates that selected the leaders and excluded the band near the cut (a winner's curse).
* A small context (composition) effect may add to it. It is not an estimator fault.

## 3. Qualification-boundary uncertainty

| | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| point rank 6 | nlhe6-neutral-e1-s0, 32.37 | nlhe6-neutral-e1-s1, 23.38 | nlhe6-tight-e3-s2, 27.04 |
| point rank 7 | nlhe6-aggressive-e2-s0, 31.67 | nlhe6-aggressive-e1-s0, 20.77 | nlhe6-station-e2-s1, 22.80 |
| gap (BB/match) | 0.71 | 2.62 | 4.24 |
| gap 95% CI, this pair | [−12.65, 14.00] | [−8.94, 13.90] | [−10.05, 19.29] |
| gap 95% CI, order statistic | [0.10, 9.03] | [0.05, 5.48] | [0.08, 7.73] |
| P(rank-6/7 reversal) | 0.475 | 0.345 | 0.290 |
| P(same top-6 set) | 0.342 | 0.169 | 0.324 |
| clear top 6 (P ≥ 0.95) | ranks 1–3 | ranks 1–4 | ranks 1–3 |
| `reference_self_regret` (BB): mean, median, 95% | 3.57, 2.16, [0, 14.35] | 5.13, 4.13, [0, 16.45] | 3.82, 2.31, [0, 14.40] |
| reference self-changed qualifiers (mean) | 0.70 | 1.06 | 0.76 |
| bootstrap Spearman vs point ranking (median) | 0.983 | 0.974 | 0.979 |

**Unsettled reference top-6 membership** (5% < P < 95%), as bot (rank, P):

* **spread (6):** station-e2-s3 (4, 0.948), nit-e3-s1 (5, 0.923), neutral-e1-s0 (6, 0.427),
  aggressive-e2-s0 (7, 0.386), aggressive-e1-s0 (8, 0.202), maniac-e3-s2 (9, 0.052).
* **crowded_cutoff (9):** maniac-e2-s3 (5, 0.490), neutral-e1-s1 (6, 0.478), aggressive-e1-s0
  (7, 0.241), neutral-e2-s0 (8, 0.145), tight-e2-s3 (9, 0.119), loose-e2-s0 (10, 0.134),
  aggressive-e1-s1 (11, 0.064), loose-e3-s1 (12, 0.118), loose-e2-s1 (14, 0.058).
* **style_diverse (8):** nit-e3-s1 (4, 0.935), neutral-e2-s1 (5, 0.865), tight-e3-s2 (6, 0.471),
  station-e2-s1 (7, 0.194), trapper-e2-s2 (8, 0.157), loose-e0 (9, 0.124), aggressive-e3-s3
  (10, 0.106), tight-e2-s1 (11, 0.082).

### crowded_cutoff structure (manifest sets)

Instability inside the designed crowd is the intended object, not a defect.

* **Designed leaders**, as (rank, P(top 6)): station-e2-s2 (1, 1.000), maniac-e2-s2 (2, 1.000),
  trapper-e3-s3 (3, 1.000).
* **Designed crowd (12)**, as (rank, P(top 6)):

  | bot | rank | P(top 6) |
  |---|---|---|
  | aggressive-e2-s0 | 4 | 0.973 |
  | maniac-e2-s3 | 5 | 0.490 |
  | neutral-e1-s1 | 6 | 0.478 |
  | aggressive-e1-s0 | 7 | 0.241 |
  | tight-e2-s3 | 9 | 0.119 |
  | aggressive-e1-s1 | 11 | 0.064 |
  | loose-e3-s1 | 12 | 0.118 |
  | loose-e3-s2 | 15 | 0.040 |
  | station-e1-s2 | 17 | 0.028 |
  | trapper-e0 | 18 | 0.017 |
  | tight-e1-s2 | 19 | 0.011 |
  | maniac-e3-s2 | 28 | 0.000 |

  Total P(top 6) in the crowd: 2.58.
* **Outside both sets (45 bots) with P(top 6) > 0.10:** neutral-e2-s0 (rank 8, 0.145) and
  loose-e2-s0 (rank 10, 0.134). These had within-field pool ranks of 24 and 22.
  * Others with P > 0 are all ≤ 0.058.
  * About 0.42 of the top-6 probability mass lies outside the designed leaders and crowd.
* The crowd spans 17.3 BB in `mu_field`.

### style_diverse

* **Point ranks 1–4**, as P(top 6): maniac-e2-s2 1.000, station-e2-s2 1.000, trapper-e3-s3
  0.973, nit-e3-s1 0.935.
* **Rank ≥ 10 with P(top 6) > 0.10:** aggressive-e3-s3 (rank 10, 0.106). The next is
  tight-e2-s1 (rank 11, 0.082).

## 4. Pre-registered 250 → 500 rules, applied exactly

| field | clause 1 | clause 2 | decision |
|---|---|---|---|
| spread | P(same top 6) = 0.342 < 0.95: **fires** | P(reversal) = 0.475 > 0.05: **fires** | **EXTEND_TO_500** |
| crowded_cutoff | leaders' P(top 6) = 1.000, 1.000, 1.000 (all ≥ 0.95): no | outside-both bots neutral-e2-s0 0.145 and loose-e2-s0 0.134 > 0.10: **fires** | **EXTEND_TO_500** |
| style_diverse | ranks 1–4 P(top 6) ≥ 0.935 (all ≥ 0.90): no | rank 10 aggressive-e3-s3 0.106 > 0.10: **fires** | **EXTEND_TO_500** |

The verdicts match `reference.json → extension_rule` for every field.

**What 500 rounds can plausibly change.** This is context only and changes no decision. It
shrinks each bootstrap deviation by 1/√2 and keeps the point estimates.

* **spread:** P(same top 6) about 0.45, P(reversal) about 0.46. The rule would still fire,
  because a 0.71 BB gap cannot be resolved at any affordable precision.
* **crowded_cutoff:** the outside-bot clause would probably still fire.
* **style_diverse:** it would probably lock.

500 rounds is the pre-registered ceiling; the protocol allows no further `mu_field` extension.

## 5. Duplicate and lane diagnostics (not Experiment D)

| | spread | crowded_cutoff | style_diverse |
|---|---|---|---|
| sd of a single lane delta (BB/match) | 161.2 | 157.7 | 163.0 |
| sd of the six-lane normalised matched result | 66.5 | 65.2 | 67.3 |
| sd if the 6 lanes were independent | 65.8 | 64.4 | 66.6 |
| variance-reduction factor vs 6 independent ordinary matches | **0.979** | **0.976** | **0.978** |
| a bot's cross-lane correlation (same match) | +0.004 | +0.005 | +0.005 |
| CRN signal: same start seat, different bot, across lanes | +0.044 | +0.053 | +0.049 |
| control: different seat and different bot | −0.007 | −0.010 | −0.009 |
| bust rate (bot × lane) | 0.607 | 0.590 | 0.614 |
| bust rate by lane index (χ² p) | flat (0.91) | flat (0.98) | flat (0.51) |
| bust rate by start seat (χ² p) | 0.21 | 0.08 | 0.43 |
| pooled start-seat means (BB; SE about 1.3) | −1.6 … +2.1 | −2.6 … +3.5 | −2.7 … +1.5 |
| bots with a seat effect at p < 0.05 / Bonferroni (of 60) | 4 / 0 | 5 / 0 | 4 / 0 |

**What this means:**

* **Common random numbers work.** Boards are identical across lanes, and same-seat cards
  correlate across lanes.
* **But duplication gives essentially no variance reduction for `mu_field`.** The factor is
  about 0.98, and lanes are almost uncorrelated. Under persistent-stack 400-hand matches about
  60% of bot-lanes bust and lanes diverge within the first hands, so little card luck cancels.
  The matched estimate is about as precise as 1,500 independent ordinary matches per bot.
* **No seat or lane problems.** There is no notable systematic seat effect, and cyclic rotation
  cancels any that exists anyway. Lanes behave interchangeably. There is no sign of abnormal lane
  dependence or broken CRN.

The estimator is unbiased and behaving as specified. Only its expected precision gain is absent.
This is a finding relevant to how Experiment D should be read, not a defect.

## 6. Reference uncertainty and regret

* **Gaps vs uncertainty.** The per-bot SE is about 4.1–4.2 BB, so a pair difference has SE ≈ 6 BB.
  The boundary gaps (0.7 / 2.6 / 4.2 BB) are all well inside reference noise.
  * Only the top 3 (spread, style_diverse) or top 4 (crowded_cutoff) are settled.
* **Self-regret is modest, not negligible.** Its mean is 3.6–5.1 BB per match summed over the
  six qualifiers, i.e. under 1 BB per qualifier, below one bot-level SE. It is under 2% of the
  top-6 total strength.
* **Misqualification by reference noise.** A tournament that recovered the true reference
  ordering would still appear to "misqualify" about 0.70 / 1.06 / 0.76 agents on average against
  the point top 6, purely because the reference ordering is uncertain. Identity errors against the
  reference point estimate must be read against this floor, using `*_ref_propagated` intervals
  and the `clear_*` counts.
* **crowded_cutoff regret stays small.** Top-6 identity is unstable (P(same set) 0.17), but
  regret stays small. Swapping rank 6 for rank 7 costs 2.6 BB, and for rank 10 costs 5.4 BB,
  while admitting a rank-30 bot would cost 19.7 BB and a rank-45 bot 40.8 BB. Regret separates harmless crowd swaps from
  material mistakes, as intended.
* **No unique true top 6** is claimed for any field. Beyond the settled leaders, the reference
  supports only the unsettled sets listed in section 3.

## 7. Field comparison (descriptive; three controlled fields)

* **spread** is **not** a clean-selection control under `mu_field`. Ranks 1–3 are clear and
  ranks 4–5 nearly so, but the 6/7 boundary is a near-tie (0.71 BB, P(reversal) 0.48).
  It is now a "clear top 5, tied 6th" scenario rather than a separated boundary.
* **crowded_cutoff** remains the near-tie stress test:
  * the leaders are completely clear;
  * 9 bots are unsettled;
  * the top-6 identity is the least stable of the three (0.17);
  * the ambiguity extends beyond the designed crowd: two outside bots rose into it and one crowd
    bot fell to rank 28.
* **style_diverse** has the most localised ambiguity: a clear top 3, a strong 4–5, and an
  open 6th seat contested by about 5 bots at ranks 6–10.

## 8. Decision table

| Field | Rounds | P(same top 6) | P(6/7 reversal) | Unsettled bots | Rule fired? | Decision |
|---|---:|---:|---:|---|---|---|
| spread | 250 | 0.342 | 0.475 | 6 (ranks 4–9) | yes: both clauses | EXTEND_TO_500 |
| crowded_cutoff | 250 | 0.169 | 0.345 | 9 (ranks 5–14) | yes: outside-both > 0.10 (2 bots) | EXTEND_TO_500 |
| style_diverse | 250 | 0.324 | 0.290 | 8 (ranks 4–11) | yes: rank ≥ 10 > 0.10 (1 bot, 0.106) | EXTEND_TO_500 |

**Extension commands (not run):**

```bash
.venv/bin/fhr3b core field-reference --rounds 500 --extend --workers 8                 # all three fields
# or per field:
.venv/bin/fhr3b core field-reference --fields spread --rounds 500 --extend --workers 8
.venv/bin/fhr3b core field-reference --fields crowded_cutoff --rounds 500 --extend --workers 8
.venv/bin/fhr3b core field-reference --fields style_diverse --rounds 500 --extend --workers 8
```

Each command appends rounds 250–499 to the same calibration ids: 6M scheduled hands per field,
about 0.47 h per field at 8 workers.
