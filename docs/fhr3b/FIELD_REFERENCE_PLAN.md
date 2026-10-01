# Matched mu_field reference: pre-launch plan (NOT run)

> **FHR #4 rescoping (2026-10-01).** The core publication study runs `mu_field` for **NLHE6
> only**: the three frozen fields at **250 matched rounds per field** initially. That is
> 250 × 10 tables × 6 lanes × 400 = 6M scheduled hands per field, 18M in total.
>
> * **Budget scope:** the 250 rounds are core-scoped (`core_fhr4.field_reference`). There is no
>   global default; a non-core AoF4/NLHE4 reference needs `--allow-noncore` and an explicit
>   `--rounds`.
> * **Extension:** to 500 rounds, appending rounds 250–499 to the same calibration ids.
> * **Unchanged:** the design, estimator, uncertainty, lane validation and CRN coupling below.
> * **Superseded:** the AoF4/NLHE4 rows and the 3,000-ordinary-equivalent budget.
>
> Command, cost and ids: `docs/fhr3b/FHR4_CORE.md`.

Status: review decisions 2–5 have been implemented. Decision 1 keeps the shared seed. The
stage has **not** been run.

* Engine source hash: `4647ee69857e7c9b` (previously `5f5019c69316d098`).
* Fields: the 9 frozen fields in `configs/fhr3b/fields/FROZEN.yaml`, unchanged.

```bash
scripts/run_fhr4_core.sh field-reference    # NOT YET RUN; awaiting the launch instruction
# = fhr3b core field-reference --workers 8   (NLHE6 x 3 frozen fields, 250 matched rounds, then reports)
```

## 1. Design

| | AoF4 | NLHE4 | NLHE6 |
|---|---|---|---|
| match format | duplicate | duplicate | duplicate |
| lanes per match (k) | 4 | 4 | 6 |
| hands per lane | 400 | 400 | 400 |
| stack rule inside a lane | reset each hand (8 BB) | persistent, no rebuy (100 BB) | persistent, no rebuy (100 BB) |
| matched rounds per field | **750** | **750** | **500** |
| tables per round (60 bots) | 15 | 15 | 10 |
| work per bot | 1.2M hand-seats | 1.2M | 1.2M |
| scheduled hands per field | 18.0M | 18.0M | 12.0M |
| expected played (measured ratio) | 18.0M (1.00) | ≈ 15.1M (0.84) | ≈ 11.2M (0.93) |
| bootstrap groups (10 rounds each) | 75 | 75 | 50 |

Every bot gets the same simulator work as 3,000 ordinary 400-hand matches.

### Table composition and seating

* **Tables:** each round is a uniformly random partition of the field
  (`KeyedStream("fhr3b-calibration-partition", seed, round)`). No standings are used.
* **Seat rotation:** lane ℓ seats `base[(i + ℓ) mod k]` in seat i, so each bot starts in every
  seat exactly once per duplicate match.
* **Base seating:** a fresh keyed shuffle per (round, table),
  `KeyedStream("fhr3b-duplicate-base", chance_seed, decision_seed, round, table)`. It is
  independent of the partition shuffle.

### Lanes

Each lane is a complete, independent match:

* it has its own agent instances, stacks, busts and rolling history;
* decisions come from `("fhr3b-dup-decision", decision_seed, round, table, lane, hand, bot, ordinal)`;
* every lane uses the same deck for hand h, `("fhr3b-chance", chance_seed, round, table, h)`;
* lane identity is never visible to the bots.

Lanes are aggregated only after all of them have finished.

## 2. Estimator (decision 2)

* **Stored row:** one per (round, table, bot). `chip_delta` is the k-lane sum and
  `hands_played` covers all lanes.
* **Reported reference:**

      mu_field          = mean over rounds(lane_sum) / k    (chips per ordinary-equivalent 400-hand match)
      mu_field_lane_sum = mean over rounds(lane_sum)        (raw; provenance and debugging)

  `sd` and the matchup matrix are scaled the same way. The raw `sd_lane_sum` is kept as well.
* **Consumers:** every downstream use takes the normalised `mu_field`. That covers
  `reference_bots.csv`, `reference.json` (gap at the cutoff, crowd range, ranking robustness,
  archetype cycle in BB) and `fhr3b analyse`:
  * `field_references.csv` (plus `mu_field_lane_sum` and `mu_field_lanes` columns);
  * the `mu_field`/`mu_swiss` ordering agreement;
  * the Swiss accuracy metrics in `reference_accuracy.csv`.

  Verified in the smoke run: `mu_field × k = mu_field_lane_sum` for every bot.

## 3. Uncertainty (decision 3)

* **Primary per-bot SE:** analytic `sd / sqrt(matches)`. Each bot has one independent matched
  observation per round.
* **Bootstrap:** 10-round groups (75 or 50 groups), 1,000 resamples by default. Each resample
  draws **one** multinomial weight vector over round groups and applies it to the whole bot
  vector, so cross-bot covariance is preserved. A test checks this: in a zero-sum field every
  resample's bot means sum to exactly 0.
* **What the bootstrap feeds:** only the ranking, gap and robustness diagnostics
  (`reference.json → ranking_robustness`; per-bot `rank_lo95`, `rank_hi95` and `p_top_k` in
  `reference_bots.csv`):
  * P(same top-6 set);
  * the gap at the cutoff, with a 95% CI for the point-estimate 6th/7th pair and for the order
    statistic;
  * P(that pair reverses);
  * the median Spearman correlation of resampled rankings with the point ranking.
* **Bootstrap SE:** `se_bootstrap` is reported only as a check on the analytic SE.

## 4. Per-lane persistence (decision 4)

* **Files:** `calibration/<calib_id>/lanes/l_<a>_<b>.parquet`, one per chunk. Each row records
  round, table, lane, bot, start seat, final chip delta for that lane, hands played, bust hand
  and whether the bot busted. No hand histories are stored.
* **Validation** runs when each chunk is written (the lane file is written first; the chunk file
  marks completion). It runs again before every report or analysis read
  (`verify_calibration_lanes`). It checks that:
  * each lane is zero-sum;
  * each lane seats exactly the table's bots, in all k start seats;
  * every bot starts in every seat exactly once within a duplicate match;
  * the lane count equals the mode's table size;
  * a bot's per-lane deltas add up exactly to its stored lane-summed result;
  * lane hands add up to the stored `hands_played`;
  * the `busted` flag agrees with `bust_hand`.
* **Digest:** lane files are part of the calibration digest. A chunk without its lane file is
  refused when the run resumes.
* **Tests:** a regression test breaks each invariant in turn and checks that it is rejected.

## 5. Retired Hodge share (decision 5)

* `analyse_calibration` no longer computes the Hodge cyclic share, either per resample or as a
  point estimate. `hodge`/`subset_hodge` remain only for the retired-provenance tests.
* The archetype cycle test and split-half reliability are computed **once** from the completed
  reference data and labelled descriptive. Their energies are rescaled to the normalised scale.

## 6. Common random numbers (decision 1, unchanged)

All nine field references use calibration seed `838148860091781465`:

* calibration seed = `derive_seed("fhr3b-calibration", "fhr3b-2026", "field-reference")`;
* chance seed = `derive_seed("fhr3b-calibration-chance", ·)`;
* decision seed = `derive_seed("fhr3b-calibration-decision", ·)`.

The fields share decks and decision streams for a given (round, table, hand). Partitions differ
because the bot sets differ. Each field's estimate is unbiased. **Cross-field reference
estimates are coupled through common random numbers and must not be analysed as independent
replications.** This note is written into every `reference.json` and into the `references`
section of the analysis summary.

## 7. Calibration identities

`chunk_rounds` 10 and the lane store (`lane_store: fhr3b-calibration-lanes-v1`, included only
for duplicate calibrations) change every field-reference identity. Pool-calibration identities
are unchanged.

| field | calibration id |
|---|---|
| aof4 spread | `aof4.aof4-spread.H400.dup.field-reference.70adb060` |
| aof4 crowded_cutoff | `aof4.aof4-crowded_cutoff.H400.dup.field-reference.92afa17b` |
| aof4 style_diverse | `aof4.aof4-style_diverse.H400.dup.field-reference.fefb1197` |
| nlhe4 spread | `nlhe4.nlhe4-spread.H400.dup.field-reference.8f9817e4` |
| nlhe4 crowded_cutoff | `nlhe4.nlhe4-crowded_cutoff.H400.dup.field-reference.b4a51d13` |
| nlhe4 style_diverse | `nlhe4.nlhe4-style_diverse.H400.dup.field-reference.43a9f572` |
| nlhe6 spread | `nlhe6.nlhe6-spread.H400.dup.field-reference.3cea71b5` |
| nlhe6 crowded_cutoff | `nlhe6.nlhe6-crowded_cutoff.H400.dup.field-reference.7d2640ae` |
| nlhe6 style_diverse | `nlhe6.nlhe6-style_diverse.H400.dup.field-reference.0caf92cc` |

These ids are pinned by `test_field_reference_identity_and_new_calibration_ids`.

**Outputs:**

* `results/fhr3b/calibration/<id>/{calibration.lock.json, chunks/c_*.parquet, lanes/l_*.parquet}`;
* `reports/fhr3b/field-calibration/<mode>/<field_id>/{reference_bots.csv, reference.json}`.
  `reference.json` records the calibration digest, which covers chunks and lanes.

## 8. Runtime and storage (estimates)

**Throughput measured on 2026-10-01** (one core, one 10-round chunk at full H = 400, with lane
validation):

| mode | rate | time per 10-round chunk |
|---|---|---|
| AoF4 | ≈ 1,400 h/s | 171 s |
| NLHE6 | ≈ 1,290 h/s | 173 s |

The earlier 8-worker pool runs reached 4,666 h/s (AoF4) and 5,633 h/s (NLHE4). NLHE6 reached only
1,264 h/s, which is about one core's worth, so that NLHE6 run was probably throttled.

| mode | played hands (3 fields) | expected aggregate rate | wall at 8 workers |
|---|---|---|---|
| AoF4 | 54M | ≈ 4,700 h/s | ≈ 3.2 h |
| NLHE4 | ≈ 45M | ≈ 5,600 h/s | ≈ 2.2 h |
| NLHE6 | ≈ 34M | ≈ 4,300 h/s (worst seen ≈ 1,260) | ≈ 2.2 h (up to 7.5 h) |
| **total** | ≈ 133M | | **≈ 8 h (up to ≈ 13 h)** |

The work unit is a 10-round chunk: 75 or 50 chunks per field, about 3 minutes each on one core.
That parallelises cleanly over 8 workers, and resuming loses at most one chunk per worker.

**Storage**, measured per 10-round chunk:

| mode | rows | lanes | per field (rows + lanes) |
|---|---|---|---|
| AoF4 | 5.6 KB | 11.5 KB | ≈ 1.3 MB (75 chunks; 45k rows + 180k lane rows) |
| NLHE6 | 6.1 KB | 18.4 KB | ≈ 1.2 MB (50 chunks; 30k rows + 180k lane rows) |

The total for all 9 fields is **≈ 12 MB**, plus well under 1 MB of reports.

## 9. Independence from Swiss

Tables are random partitions, every bot plays exactly one matched match per round, no standings
are used, and the seed namespace (`field-reference`) is disjoint from every tournament
namespace. `mu_field` is therefore independent of Swiss scheduling by construction. `mu_swiss` is
the separate Swiss reference.

## 10. Verification at this commit

* **Tests:** 413 passed, 1 skipped (optional confseq).
* **Frozen fields:** all 9 accepted; every revoked hash rejected.
* **Neutrality of the engine-hash change:** the ordinary calibration path is unchanged. Round 0
  of the stored AoF4, NLHE4 and NLHE6 pool calibrations replays to identical rows, and the golden
  ordinary matches pass.
* **Smoke run end to end** (profile smoke, namespace `test`, 12-bot fields, H = 10): pool, then
  behaviour audit, select-fields, matched field calibration, field-reference, a baseline run and
  analyse.
  * 9 duplicate calibrations;
  * 24 lane files written and re-verified;
  * the normalised `mu_field` reaches `field_references.csv` and `reference_accuracy.csv`.

## Remaining differences from the locked protocol

None known. Decision 1 (common seed) is a documented design choice rather than a deviation.
