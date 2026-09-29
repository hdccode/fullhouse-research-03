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

## 4. Next

* RQ6: `scripts/run_rq6_final.sh`. NLHE6 100BB (raw, all-in EV, fitted MIVAT/AIVAT)
  at 25k per pairing; 20BB all-in EV at 10k; AoF all-in EV at 50k.
* RQ7: `scripts/run_rq7_final.sh`.
* An optional Bomb multiway-aware robustness agent. It is not part of the core
  campaign.

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
