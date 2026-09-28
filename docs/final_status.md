# Final core corpus: status and conclusions (internal analysis note)

State as of 2026-09-28, `main` @ a86909d plus the final-analysis commits. Numbers come
from `reports/final-analysis/` (regenerate with the commands at the end). Not paper text.

## 1. Corpus status

| format | experiment_id | blocks/pairing (p1-p3) | control | schema | status |
|---|---|---|---|---|---|
| NLHE 6-max 100BB | fhr3-nlhe6-100bb-pilot-v1 | 250,000 | 10,000 | v1 | final |
| NLHE 4-max 100BB | fhr3-nlhe4-100bb-pilot-v1 | **10,000** | 10,000 | v1 | **extension to 100k missing** |
| Crazy Pineapple 6-max | fhr3-cp6-100bb-pilot-v1 | 100,000 | 10,000 | v2 | final |
| PLO 6-max | fhr3-plo6-100bb-pilot-v1 | 50,000 | 10,000 | v2 | final |
| Bomb Pot 6-max | fhr3-bomb6-100bb-pilot-v1 | 50,000 | 10,000 | v2 | final (stress case) |
| AoF 4-max 8BB | fhr3-aof4-8bb-pilot-v1 | **10,000** | 10,000 | v2 | **extension to 50k missing** (optional) |
| Nit Game 6-max | fhr3-nit6-100bb-pilot-v1 | 10,000 (+p4) | 10,000 | v2 | final |
| NLHE 6-max 20BB / 50BB | fhr3-nlhe6-{20,50}bb-v1 | 10,000 | 10,000 | v1 | final |

Integrity (`reports/final-analysis/integrity.json`, `validate/`): every pairing has
contiguous block ids from 0, no duplicates, 0 invalid rows, one config hash equal to
the experiment lock, pairing hashes equal to the pairing locks, one agent version per
role, a manifest for every run id; every control has sigma_D = 0; exact replay of
20-40 sampled blocks per pairing at the current code passes for all corpora,
including pilot-range blocks of the mixed-SHA extensions (CP/PLO/Bomb pilots at
d3b8ded, extensions at a86909d; the only simulation change between them, 7eecaf7,
does not alter outcomes).

The 4-max extension cannot be done by re-running the v1 config (the schema lock
refuses v2 writes); `configs/nlhe_4max_100bb_v2.yaml` is a v2 re-run under a new
experiment_id with the same seed (`scripts/run_core_extensions.sh`, ~10 min with
AoF). `scripts/analyze_pilots.py` switches to it automatically once it exists.

## 2. Conclusions that survive the final corpora

* **Pilot sizing.** A 10k-block pilot put sigma_D within ±7.3% of the final value
  for all 12 extended pairings (required hands 0.86-1.15x final). Disjoint 10k
  windows range 0.79-1.32x (worst: NLHE6 p1, exkurt 186); 2.5k windows 0.42-2.12x.
  The spread of window sigmas matches the delta-method relative SE
  sqrt((kappa+2)/(4n)) closely. PLO is the only format where 10k underestimated sigma
  in all three pairings (-3 to -7%).
* **Burden spread.** Median p1-p3 played hands at 1 BB/100, 80% power: AoF 0.34M,
  NLHE4 4.1M, NLHE6 4.4M, CP 8.7M, Nit 9.5M, PLO 16.4M, Bomb 20.5M. Largest /
  smallest = 60x (AoF to Bomb); among 100BB formats 5.0x. In blocks 40x; in
  measured wall-clock 570x (0.013 h to 7.7 h at 8 workers).
* **Pairing sensitivity.** Within-format max/min required hands: AoF 10.4x, Bomb
  8.5x, NLHE4 3.8x, PLO 3.4x, NLHE6 3.2x, CP 2.8x, Nit 2.7x. Among 100BB formats
  this is the same order as the between-format spread (5x). Across the full set
  including AoF the format dominates.
* **Robust vs non-robust orderings** (hands): AoF < everything (ranges disjoint,
  12x). NLHE4 vs NLHE6 (1.08x), CP vs Nit (1.09x) and PLO vs Bomb (1.25x, 2/3
  roles) are not robust. NLHE6 < CP < PLO hold in 3/3 roles, but p1-p3 ranges
  overlap.
* **Concentration.** Blocks containing an all-in hand carry 82-97% of the
  squared deviation in every 100BB format (NLHE6 85-86%, NLHE4 84-87%, CP 89-90%,
  PLO 82-83%, Bomb 97%). The 20/50BB range is 92-94%, Nit 85-90%, AoF ~100%
  (trivially). That share sits in the 0.7-24% of blocks that are both all-in and
  decisive (D≠0). The top 1% of blocks carry 33-96%. PLO is the one case where
  the all-in share understates big pots: blocks with a >=100 BB pot carry 93-94%
  (pot-limit builds large pots without all-ins).
* **Mechanism (exploratory).** Within a format, the fraction of blocks with an
  all-in is fixed by the format and reference population (NLHE6 0.078/0.078/0.083).
  Pairings differ only in the squared deviation per all-in block. Across 100BB
  formats the log-variance spread is ~2/3 all-in frequency and ~1/3 magnitude.
  Across stack depths the two trade off (frequency up, magnitude down faster).
  Frequency alone explains 7% of cross-pairing log variance over all 24 non-Nit
  pairings.
* **Standardized d.** At the analytic N for 80% power (n = 500/2k/10k),
  resampled power is 0.778-0.815 for all 21 headline pairings (MC SE 0.006) and
  null rejection 0.028-0.057. The only tail effect is a slightly conservative t-test at
  n = 500 for the heaviest pairing. There is no systematic heavy-tail penalty at
  these n. BB/100 at d = 0.01 spans 0.39 (AoF p1) to 6.2 (Bomb p3).
* **Stack depth (paired, common 10k blocks, bootstrap CIs).** sigma(20BB)/sigma(100BB) =
  0.38/0.37/0.38 (CIs within 0.34-0.42), and sigma(50BB)/sigma(100BB) = 0.70/0.69/0.70. So 100BB needs
  ~7x the blocks of 20BB (per-pairing CIs 5.6-8.5x) and ~2x those of 50BB
  (1.7-2.4x), for all three pairings. Using the full 250k 100BB sigma instead: 6.2-6.5x
  and 1.8-2.0x. corr(D) 20-vs-100 0.69-0.74, 50-vs-100 0.85-0.90. Agents are not
  stack-aware.
* **Nit.** Total gaps (p1 -10.1, p2 +30.3, p3 +17.3, p4 +25.8 BB/100) are almost
  entirely penalty transfer. The chip-play components are -1.5, -1.0 (CI incl. 0),
  -0.2 (CI incl. 0) and -2.1 BB/100. The chip component carries 67-82% of the
  variance, the transfer component 8-19%. Block excess kurtosis 4-12 reflects ~95
  hands per block, not lighter per-hand tails (all-in blocks still carry 85-90%).
  No truncated rounds.

## 3. Format notes

* **Bomb Pot**: statistically stable (10k-window sigma CV 1.6-4.7%, 10k pilot
  within 4%, exact replay, control 0), but the agent family is not credible as
  competent multiway play. 70% showdown per hand; 28% of hands contain an all-in;
  mean pot 80 BB on a 12 BB ante pot; ~18% of traced hands are six-way check-downs.
  Style gaps of -31 (p2) and -24 (p3) BB/100 (z -15, -9). As a standardized per-block
  gap |mean D|/sigma_D that is 0.067 and 0.040, against <= 0.016 for every other
  100BB-format pairing (NLHE6 p2 0.006). p1 perturbs aggression, not looseness. Keep it
  as a stress case with a caveat. Do not claim "Bomb is hardest": Bomb p1 (4.2M
  hands) is easier than PLO p1 (5.7M), and Bomb vs PLO medians differ by only 1.25x.
* **Crazy Pineapple**: 100k stable (window CV 3-5%). Preflop-all-in hands (the
  go_trumpcards divergence is a subset) are 0.29% of traced hands (11/3,852; 3 of
  321 traced blocks), consistent with the documented ~0.25%. Too rare to matter.
* **PLO**: 50k sufficient (bootstrap sigma CI ±2-3.5%, window CV 2-4%). 3.7x NLHE6
  in hands and 9.9x in wall-clock (2.7x slower per block). No further corpus.
* **AoF**: low-variance, bounded-payoff contrast (max pot 32 BB; top-1% share
  0.18-0.46). Production v2 beats the heuristic by +5.1 [+2.6, +7.6] BB/100. The
  prod-vs-blend10 gap (-0.2 ± 0.8) is not resolved at 10k.

## 4. Remaining work

* Run `scripts/run_core_extensions.sh` (4-max v2 100k; AoF 50k), then rerun the analysis.
* RQ6: `scripts/run_rq6_final.sh`. NLHE6 100BB covers raw, all-in EV and fitted
  MIVAT/AIVAT at 25k/pairing; 20BB and AoF cover all-in EV at 10k. Dropped: the
  prior-VF 100BB run (not interpretable) and Bomb all-in EV (caveated agents).
* RQ7: `scripts/run_rq7_final.sh`. Null coverage covers 5 distributions at 2,000
  reps; min-N sensitivity covers 3 distributions × 3 values; non-null covers
  5 distributions × 2 effects at 1,000 reps; plus 1,000-permutation real-order streams.
* Optional Bomb robustness agent (only if Bomb's absolute position is claimed): see
  the final report for its specification.

## 5. Regenerating the analysis

```bash
mkdir -p reports/final-analysis
.venv/bin/python scripts/analyze_pilots.py --out reports/final-analysis/core --boot 1000
.venv/bin/python scripts/final_analysis.py --boot 400
.venv/bin/python scripts/d_collapse_check.py --out reports/final-analysis/d_collapse.csv --reps 4000
.venv/bin/python scripts/final_tables.py
# plus fhr3 compare / figures over the nine experiment directories (see run_core_extensions.sh)
```
