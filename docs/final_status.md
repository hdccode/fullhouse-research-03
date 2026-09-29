# Final core corpus: status and frozen conclusions (internal analysis note)

Frozen 2026-09-29. Every number below comes from `reports/final-analysis/`, whose
exact inputs and outputs are pinned by `reports/final-analysis/MANIFEST.json`
(`scripts/freeze_manifest.py --verify` checks for drift). Not paper text.

## 1. Corpus (final; core raw simulation complete)

| format | experiment_id | blocks/pairing p1-p3 | control | schema |
|---|---|---|---|---|
| NLHE 6-max 100BB | fhr3-nlhe6-100bb-pilot-v1 | 250,000 | 10,000 | v1 |
| NLHE 4-max 100BB | fhr3-nlhe4-100bb-v2 | 100,000 | 10,000 | v2 |
| Crazy Pineapple 6-max | fhr3-cp6-100bb-pilot-v1 | 100,000 | 10,000 | v2 |
| PLO 6-max | fhr3-plo6-100bb-pilot-v1 | 50,000 | 10,000 | v2 |
| Bomb Pot 6-max | fhr3-bomb6-100bb-pilot-v1 | 50,000 | 10,000 | v2 |
| AoF 4-max 8BB | fhr3-aof4-8bb-pilot-v1 | 50,000 | 10,000 | v2 |
| Nit Game 6-max | fhr3-nit6-100bb-pilot-v1 | 10,000 (+p4) | 10,000 | v2 |
| NLHE 6-max 20BB / 50BB | fhr3-nlhe6-{20,50}bb-v1 | 10,000 | 10,000 | v1 |

`fhr3-nlhe4-100bb-pilot-v1` (v1, 10k) is superseded. Blocks 0..9,999 of the v2
re-run reproduce all of its D values exactly (40,000 rows, 0 mismatches).

`scripts/integrity_check.py` checks every pairing for the following, and all pass:
contiguous ids from 0; no duplicates; 0 invalid rows; no NaN D; one config hash
equal to the lock; pairing hash equal to the lock; one agent version per role; a
manifest for every run id (all git-clean); and controls exactly 0. `fhr3 validate`
replayed 20-40 blocks per pairing exactly at the current code, including pilot-range
blocks of every mixed-SHA extension. `src/` is unchanged since a86909d.

## 2. Frozen conclusions

* **Burden (1 BB/100, 80% power, median p1-p3).** Played hands:
  * AoF 0.34M, NLHE4 4.26M, NLHE6 4.43M, CP 8.71M, Nit 9.49M, PLO 16.4M, Bomb 20.5M.
  * Full-set ratio 61x; 100BB formats 4.8x (NLHE4 to Bomb).
  * Blocks: 41x full set, 4.6x among 100BB excluding Nit.
  * Measured wall-clock at 8 workers: 475x (0.016 h to 7.7 h). This is
    implementation- and run-specific; AoF's measured aggregate throughput differs
    by ~20% between its two runs.
* **4-max vs 6-max NLHE.** Similar cost per played hand. Per role, 4-max needs
  0.85 / 0.96 / 0.91 of the 6-max hands. The median ratio 6-max/4-max is 1.04
  [0.98, 1.11]. In blocks, 4-max needs 1.27-1.44x more (8 vs 12 hands per block).
* **Pairing sensitivity (max/min hands p1-p3).**
  * Values: AoF 10.0x, Bomb 8.5x, NLHE4 3.4x, PLO 3.4x, NLHE6 3.2x, CP 2.8x, Nit 2.7x.
  * Among the five 100BB non-Nit formats, the within-format spread (2.8-8.5x) is
    comparable to the between-format spread of medians (4.8x).
  * This does not hold for the full set, where AoF adds 13x.
* **Robust orderings (hands).**
  * AoF below all others, with disjoint pairing ranges.
  * NLHE6 < CP (2.0x) and Nit < PLO (1.7x) in 3/3 roles, but p1-p3 ranges overlap.
  * Not robust: NLHE4 vs NLHE6 (1.04x), CP vs Nit (1.09x; different block
    construction) and PLO vs Bomb (1.25x; 2/3 roles).
* **Variance mechanism.**
  * Big-pot blocks: blocks containing a pot of at least one starting stack carry
    79-97% of squared deviation in every 100BB format: NLHE4 79-81%, NLHE6 83-85%,
    CP 88-89%, PLO 93-94%, Bomb 96-97%. That variance sits in the 0.6-22% of blocks
    that are big-pot and decisive (D != 0).
  * All-in blocks: they carry 80-97%. "All-in" is a proxy that slightly overcounts in
    NL (uncontested shoves, 1.8-2.8% of the share) and undercounts in PLO, where 6.4%
    of blocks have >=100 BB pots without an all-in and carry 12-13%.
  * Within a format, big-pot/all-in frequency is fixed by format and reference
    population; pairings differ in the squared deviation per such block.
  * Across 100BB formats, log-variance spread is ~65-75% frequency and ~30-40% magnitude
    (exploratory decomposition, 15 pairings; big-pot vs all-in definition). Across stack depths, frequency rises
    while magnitude falls faster.
* **Pilot sizing.**
  * A 10k prefix estimated sigma_D within -7.3% to +13.3% of final across 18 extended
    pairings, giving required hands 0.86-1.28x final. The worst were 4-max p3 (+13%)
    and p1 (+8%).
  * 97% of disjoint 10k windows land within ±20% of final required hands.
  * Window scatter matches the delta-method relative SE sqrt((kappa+2)/(4n)): the
    observed/predicted median is 1.00.
  * Rule: n ≈ 384(kappa+2) blocks for sigma within ±5% with 95% confidence
    (≈ 100(kappa+2) for ±5% at one SE).
* **Standardized d.** At the analytic 80%-power N (n = 500, 2k, 10k), resampled power
  is 0.779-0.815 across all 27 pairings (MC SE 0.006), and null rejection is
  0.028-0.057. The worst case is 4-max p1 (kappa 305) at n = 2,000 with power 0.779.
  There is no systematic heavy-tail penalty; the test is slightly conservative at
  n = 500 for the heaviest tails. Appendix only.
* **Stack depth.** Paired over common blocks 0-9,999:
  * sigma(20BB)/sigma(100BB) = 0.38 / 0.37 / 0.38, with CIs within 0.34-0.42.
  * 100BB needs 7.1x / 7.2x / 6.8x the blocks of 20BB (CIs 5.6-8.6x) and 2.1x / 2.1x /
    2.0x those of 50BB (CIs 1.7-2.4x).
  * Measured against the full 250k 100BB sigma instead: 6.2-6.5x and 1.8-2.0x.
  * corr(D) is 0.69-0.74 between 20BB and 100BB, and 0.85-0.90 between 50BB and 100BB.
  * The fraction of blocks with an all-in rises 0.08 -> 0.16 -> 0.29 as stacks
    shrink, while the squared deviation per all-in block falls (p2: 1,870 -> 535 -> 87).
  * Agents are not stack-aware.
* **Nit.**
  * The total gaps (p1 -10.1, p2 +30.3, p3 +17.3, p4 +25.8 BB/100) are almost
    entirely penalty transfer.
  * The chip-play components are -1.5, -1.0 (CI includes 0), -0.2 (CI includes 0) and
    -2.1 BB/100.
  * The chip component carries 67-82% of the variance; transfers carry 8-19%.
  * Block kurtosis of 4-12 reflects ~95 hands per block; all-in blocks still carry
    85-90% of squared deviation.

## 3. Format verdicts

* **AoF (50k).**
  * Sigma is stable: window CV 0.7-3.7%, and the 10k pilot was within 1.3%.
  * Production v2 beats the heuristic by +4.5 [+3.4, +5.6] BB/100 (z 8.0).
  * The production vs 10%-blend gap is unresolved: +0.27 [-0.07, +0.62] BB/100
    (z 1.55). It is bounded below ~0.6 BB/100 and is the RQ6 target.
  * Role: bounded-payoff, low-variance contrast (max pot 32 BB).
* **NLHE 4-max (100k).**
  * p1 remains the heaviest-tailed pairing in the suite: kappa 305, top-0.1% share
    0.39, 10k-window sigma CV 9.2%. Its 10k pilot was high by 8%.
  * At 100k its sigma CI is ±5%, which is adequate.
* **NLHE 6-max (250k).** The baseline; no open question.
* **Crazy Pineapple (100k).**
  * Stable.
  * Preflop all-in hands are 0.29% of traced hands, so the canonical-rule edge case
    is immaterial.
  * Burden: 8.7M hands (median).
* **PLO (50k).**
  * Sigma CI ±2-3.5%; no further corpus is needed.
  * Burden is 3.7x NLHE6 in hands and 9.9x in wall-clock.
* **Bomb Pot (50k).**
  * Statistically stable.
  * The agent family is not credible as competent multiway play: 70% showdown,
    28% of hands contain an all-in, ~18% of traced hands are six-way check-downs, and
    standardized style gaps are 0.067 / 0.040 per block versus <= 0.016 elsewhere.
  * Treat it as a stress case. No core claim depends on its absolute rank.
* **Nit.** A block-construction and mechanism case study (see above).

## 4. RQ6 results (complete, 2026-09-29) and RQ7 status

The RQ6 run is at `ac3cd5f` (clean). Corpora:
* `fhr3-nlhe6-100bb-rq6-v1-fittedvf`: 25k per pairing, plus a 2k control;
* `fhr3-nlhe6-20bb-rq6-allin-v1`: 10k per pairing;
* `fhr3-aof4-8bb-rq6-allin-v1`: 50k per pairing, plus a 10k control.

Every gate passes:
* 0 invalid rows, contiguous block ids, validation replays `[OK]`;
* raw D reproduces the frozen corpora block for block, and `compare` shows `paired`
  with corr 1.000;
* self-play is exactly 0 for every estimator;
* the value function verifies (sha256 `acb224b9…`, training seed 90210 ≠ evaluation seed
  20260928, 36,000 training hands);
* `reports/rq6/MANIFEST.json` verifies;
* max |z(mean(estimator − raw))| = 1.29.

Numbers come from `reports/rq6/` (summary) and `reports/rq6/deep/`
(`scripts/rq6_deep_analysis.py`). Variance ratio = Var(estimator D) / Var(raw D) on the same
blocks, with a paired bootstrap 95% CI. The effective-sample-size multiplier is 1/ratio.

| setting | estimator | variance ratio p1 / p2 / p3 | median ESS | hands saved @1 BB/100 |
|---|---|---|---|---|
| NLHE6 100BB | all-in EV | 0.878 / 0.857 / 0.924 | 1.14× | 8-14% |
| NLHE6 100BB | fitted MIVAT | 0.616 / 0.596 / 0.663 | 1.62× | 34-40% |
| NLHE6 100BB | fitted AIVAT | 0.571 / 0.580 / 0.590 | 1.72× | 41-43% |
| NLHE6 20BB | all-in EV | 0.675 / 0.716 / 0.774 | 1.40× | 23-33% |
| AoF 8BB | all-in EV | 0.098 / 0.093 / 0.131 | 10.2× | 87-91% |

* **Estimator increments (NLHE100, paired).**
  * MIVAT/all-in EV = 0.70-0.72; every CI is below 1.
  * AIVAT/MIVAT = 0.93 / 0.97 / 0.89. p1 and p2 CIs include 1; p3 is [0.83, 0.95].
  * So broader chance correction matters, while known-action correction adds little.
* **Dose-response of all-in EV** (median variance ratio): 0.88 at 100BB, 0.72 at 20BB,
  0.10 in AoF. The 100BB − 20BB difference is 0.16 [0.10, 0.23].
* **Tails persist at 100BB.**
  * Excess kurtosis (raw → all-in EV / MIVAT / AIVAT): p1 183 → 177 / 229 / 265.
  * The top-1% share stays at 0.93-0.95 (p1).
  * Blocks with a pot of at least one stack still carry 82-87% of the corrected squared
    deviation.
  * Correction removes 9-43% of the big-pot squared deviation at 100BB, but ~90% in AoF.
  * Correction is proportional, not tail-selective: at deep stacks, most of the tail is
    not runout luck the estimators can see.
* **AIVAT removes zero inflation.** D=0 goes from 87% of blocks to 0%, because action
  corrections differ between the A and B policies. It is still unbiased.
* **AoF p1 (production v2 vs 10% blend), same 50k blocks.**
  * Raw: +0.27 [−0.07, +0.62] BB/100, z = 1.55.
  * All-in EV: +0.41 [+0.30, +0.52], z = 7.38.
  * Raw would need ~511k blocks for that precision.
* **Compute** (single-process benches, estimator vs raw):
  * slowdown: NLHE100 all-in EV 1.06×, MIVAT 1.42×, AIVAT 1.86×; 20BB all-in EV 1.01×;
    AoF all-in EV 1.70×. These match the measured 8-worker aggregates (2.25× for all three
    NLHE100 estimators together, 1.74× for AoF).
  * Net wall-clock efficiency (ESS / slowdown): NLHE100 all-in EV 1.02-1.10, MIVAT
    1.07-1.18, AIVAT 0.91-0.94 (a net loss in simulation); 20BB 1.28-1.47; AoF 4.5-6.3.
* **Interpretation.**
  * Chance correction removes ~40% of NLHE100 variance at best.
  * Exact post-all-in runout luck is only 8-14% of it.
  * The share that can be removed rises steeply as stacks shrink.
  * The remaining deep-stack variance is strategic divergence, plus chance variance the
    linear value function cannot capture. The latter is an upper-bound caveat.

## 4b. RQ7 results (complete, 2026-09-29)

The run is at `ac3cd5f` (clean): 25 cells, seed 20261007, horizon 250,000 blocks,
t* = 100,000, alpha 0.05.

Integrity:
* every cell is present with its full repetitions (2,000 null / 1,000 non-null and
  permutation) × 3 methods;
* `reports/rq7/MANIFEST.json` verifies, and there are no FLAGS;
* the same-stream invariant holds in every cell (0 violations);
* recomputing 40 replicates of two cells with a different worker count and chunking
  reproduces them exactly (`reports/rq7/deep/invariants.json`).

Numbers come from `reports/rq7/*.csv` and `reports/rq7/deep/` (`scripts/rq7_deep_analysis.py`).

| null, min_n 200 (2,000 reps) | fixed-N (one look at 100k) | naive peeking, ever | asymptotic CS, ever |
|---|---|---|---|
| heavy (NLHE6 p1, kurt 186) | 4.95% | 58.0% [55.8, 60.1] | 2.40% [1.8, 3.2] |
| moderate (CP p2) | 4.45% | 62.8% [60.7, 64.9] | 2.70% [2.1, 3.5] |
| mild (PLO p3) | 4.95% | 60.6% [58.4, 62.7] | 2.55% [1.9, 3.3] |
| normal | 4.75% | 63.9% [61.8, 66.0] | 3.40% [2.7, 4.3] |
| t3 | 4.65% | 63.4% [61.2, 65.4] | 3.20% [2.5, 4.1] |

(Wilson 95% CIs.)

* **Naive peeking.**
  * False stops start early and keep accumulating: on the heavy data, 16% of runs by
    1k blocks, 36% by 10k, 52% by 100k and 58% by 250k.
  * The median first false exclusion is at 3.9k blocks (heavy) and 2.0-2.3k for the
    other distributions.
  * A later burn-in only dampens it: at min_n 5,000 the rate is still 44-45%.
* **Asymptotic CS.**
  * It is conservative in every distribution, and the heavy poker stream is the most
    conservative.
  * No null miss occurs before 8.7k blocks, except one replicate (0.05%) at block 50
    with min_n 50 on the heavy data.
  * So miscoverage is unchanged across min_n 200 / 1,000 / 5,000. Recommendation:
    min_n ≥ 200 (1,000 costs nothing).
* **Width.** CS width / t-interval width is 4.63 at 1k blocks, 1.97 at 10k, 1.67 at 25k,
  1.55 at t* = 100k and 1.57 at 250k. The ratio is the same for every distribution,
  because both widths scale with the same running σ̂.
* **Stopping cost (non-null, 1,000 reps per cell).**
  * The fixed test decides in 80-82% of runs at N80.
  * By N80 the CS has decided in 40-58%.
  * To reach the fixed test's decision rate, the CS needs 1.60-1.73 × N80 (power-matched).
  * Median CS stop is 0.87-1.13 × N80; the 90th percentile is about 2.0-2.2 × N80.
  * By the 250k horizon the CS decides in 95-100%.
  * The cost is nearly identical across the heavy, mild, normal and t3 distributions.
* **Wrong-sign decisions (non-null, pooled).**
  * CS: 0 / 9,768 (one-sided 95% upper bound 0.031%).
  * Fixed-N: 0 / 8,096.
  * Naive peeking: 854 / 9,995 = 8.5%, and up to 12.6% at the weak effect.
* **Real orderings: 1,000 permutations of the 250k NLHE6 p1 blocks** (true mean = corpus
  mean, −0.54 BB/100).
  * Naive peeking excluded the true mean in 44.8% [41.7, 47.9] of orderings. It
    eventually "decided" in every ordering, and in 11.2% it declared the wrong direction.
  * CS: 0.9% [0.5, 1.7] miscoverage; 10.3% decisions, all correct.
  * Sampling without replacement makes permutation coverage conservative (fixed-N at
    100k is 0.8%).
* **Frozen corpora in block order (28 streams).**
  * Peeking stopped in 23, 7 of them where the full corpus is not significant. 4 of
    those stops contradict the full-corpus sign, including NLHE6 p2 at block 204
    (full corpus +1.28 BB/100, z = 2.94).
  * The CS stopped in 10, and none contradicts the full-corpus sign.
  * Illustrative trajectory: `reports/rq7/deep/trajectory_nlhe6_p2.csv`.


## 5. Regenerating and verifying

```bash
.venv/bin/python scripts/integrity_check.py
.venv/bin/python scripts/analyze_pilots.py --out reports/final-analysis/core --boot 1000
.venv/bin/python scripts/final_analysis.py --boot 1000
.venv/bin/python scripts/d_collapse_check.py --out reports/final-analysis/d_collapse.csv --reps 4000
.venv/bin/python scripts/final_tables.py
# fhr3 compare / figures over the nine core experiments (MANIFEST.json "commands")
.venv/bin/python scripts/freeze_manifest.py --verify
```
