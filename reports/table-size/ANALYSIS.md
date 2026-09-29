# FHR3A controlled table-size suite: scientific analysis

This is the internal analysis note, not manuscript prose. It covers NLHE 100BB at 3, 4, 6 and
8 seats under one scheduled reference population: 40% neutral, 20% tight, 20% loose and
20% aggressive in every relative opponent slot.

**Corpora.** There are four new corpora, `fhr3a-nlhe{3,4,6,8}-100bb-tablesize-v1`:
* p1/p2/p3: 30,000 matched blocks each;
* self-play control: 10,000 blocks.

**Target.** 1 BB/100 of candidate hands, two-sided α = .05, 80% power ("N80").

## Sources

* **Primary.** `summary.csv`, `summary.json`, `figure_data.csv` and `historical.csv`, frozen by
  `MANIFEST.json`. `--verify` passes, with 360 invariant checks.
* **Derived.** `deep/` (`scripts/table_size_deep.py`) reads only the stored corpora and the
  primary outputs. It asserts that it reproduces all 12 σ_D values, all 12 required-hand counts
  and the median elasticity CI exactly, using the primary bootstrap draws (1,000 reps).
* **Validation.** Exact replay passed for 40 blocks per pairing (10 per control). All controls
  are exactly D = 0. Every relative slot has the exact 40/20/20/20 mixture, checked from the
  lineups stored per block.
* **Integrity gap, now closed.** `integrity_check.py` originally globbed only `results/fhr3-*`,
  so it silently skipped the four `fhr3a-*` corpora. The glob now also covers `fhr3a-*`.
  Re-run: 69/69 corpus rows OK, including all 16 `fhr3a` rows. Each has 0 invalid rows, 0 NaN,
  one agent version per role, controls exactly 0, and all runs from the clean commit c5538317.
  The frozen `reports/final-analysis/integrity.json` was not touched.

## Headline

**In this controlled benchmark, the per-played-hand evaluation burden rises modestly and
consistently with table size.**

| | 3-max | 4-max | 6-max | 8-max |
|---|---|---|---|---|
| required played hands (median over p1–p3) | 3.71M | 4.11M | 4.55M | 5.47M |

* **8-max vs 3-max:** required hands ×1.47 [1.29, 1.69].
* **Descriptive elasticity:** +0.37 [0.25, 0.50] (0 = per-hand invariance).
* **All three pairings** show the same direction with indistinguishable slopes.
* **Required matched blocks move the other way:** ×0.55 [0.48, 0.63] from 3 to 8 seats.

The increase is **associated with more frequent stack-sized pots per played hand**. Candidate
A/B divergences at a seat become rarer but much larger. The squared deviation per big-pot block
does not grow.

---

## A. Pairing-level results

σ_D and hands are shown with their 95% block-bootstrap CI; the hands ratio is relative to
controlled 6-max with the same pairing (independent corpora).

| k | pairing | σ_D | σ² | N80 blocks | N80 hands (M) | hands / 6-max |
|---|---|---|---|---|---|---|
| 3 | p1 | 4.97 [4.44, 5.45] | 24.7 | 215,363 | 1.29 [1.03, 1.56] | 0.88 [0.66, 1.12] |
| 3 | p2 | 8.43 [7.89, 8.94] | 71.0 | 619,126 | 3.71 [3.26, 4.18] | 0.82 [0.69, 0.94] |
| 3 | p3 | 8.71 [8.15, 9.27] | 75.9 | 662,313 | 3.97 [3.47, 4.50] | 0.86 [0.73, 1.00] |
| 4 | p1 | 5.74 [5.20, 6.25] | 32.9 | 161,555 | 1.29 [1.06, 1.53] | 0.88 [0.67, 1.11] |
| 4 | p2 | 10.47 [9.87, 11.03] | 109.6 | 537,525 | 4.30 [3.82, 4.77] | 0.94 [0.81, 1.08] |
| 4 | p3 | 10.23 [9.69, 10.79] | 104.7 | 513,807 | 4.11 [3.69, 4.57] | 0.89 [0.77, 1.03] |
| 6 | p1 | 7.48 [6.88, 8.11] | 55.9 | 121,871 | 1.46 [1.24, 1.72] | 1 |
| 6 | p2 | 13.19 [12.54, 13.83] | 174.0 | 379,286 | 4.55 [4.12, 5.01] | 1 |
| 6 | p3 | 13.28 [12.66, 13.85] | 176.3 | 384,345 | 4.61 [4.20, 5.02] | 1 |
| 8 | p1 | 9.29 [8.64, 9.89] | 86.3 | 105,884 | 1.69 [1.47, 1.92] | 1.16 [0.94, 1.41] |
| 8 | p2 | 16.70 [15.90, 17.47] | 278.9 | 341,989 | 5.47 [4.96, 5.99] | 1.20 [1.04, 1.38] |
| 8 | p3 | 16.98 [16.28, 17.68] | 288.4 | 353,743 | 5.66 [5.20, 6.14] | 1.23 [1.08, 1.40] |

| median | 3-max | 4-max | 6-max | 8-max |
|---|---|---|---|---|
| hands / 6-max | 0.82 [0.71, 0.93] | 0.90 [0.79, 1.02] | 1 | 1.20 [1.07, 1.36] |

**Direction by pairing.**

| pairing | hands elasticity | P(β > 0) | 8-max / 3-max | shape |
|---|---|---|---|---|
| p1 | +0.28 [0.05, 0.53] | 0.997 | 1.31 [1.04, 1.70] | flat 3→4 (1.292M vs 1.292M), then rising |
| p2 | +0.36 [0.22, 0.50] | 1.000 | 1.47 [1.27, 1.72] | strictly increasing |
| p3 | +0.35 [0.22, 0.50] | 1.000 | 1.42 [1.24, 1.66] | strictly increasing |

**Heterogeneity.** Pairwise slope differences:
* p1 − p2: −0.07 [−0.34, 0.20]
* p1 − p3: −0.06 [−0.33, 0.21]
* p2 − p3: +0.00 [−0.20, 0.20]

The median elasticity (+0.37) is therefore **shared**. It is not driven by one pairing and does
not hide opposite-signed slopes.

**p1 is the least precise and least stable pairing.**
* It has the highest kurtosis: 349 at 3-max, 137 at 8-max.
* No single-k ratio for p1 excludes 1.
* Its disjoint-window slopes range from +0.01 to +0.55.
* Its 3–8 slope and its 8/3 ratio do exclude zero and 1 respectively.

Absolute burdens differ about 3× between p1 and p2/p3 at every k. The relative trend is common;
the level depends on the pairing, as in the core results.

## B. Scaling with table size

Descriptive power laws y ∝ k^β come from log-log OLS over four points, with bootstrap CIs.
They are not structural laws.

| quantity | β (median series) | p1 | p2 | p3 |
|---|---|---|---|---|
| σ_D | +0.69 [0.62, 0.75] | +0.64 | +0.68 | +0.67 |
| σ_D² | +1.37 [1.25, 1.50] | +1.28 | +1.36 | +1.35 |
| hands per block (2k) | +1 (by construction) | | | |
| N80 blocks | −0.63 [−0.75, −0.50] | −0.72 | −0.64 | −0.65 |
| N80 played hands | +0.37 [0.25, 0.50] | +0.28 | +0.36 | +0.35 |

The quadratic term in log k has a CI including 0 for every series; for the median it is
+0.21 [−0.27, 0.69]. Segment elasticities for the median are:
* 3→4: +0.35 [−0.19, 0.84]
* 4→6: +0.25 [−0.06, 0.57]
* 6→8: +0.64 [0.24, 1.06]

The 6→8 segment looks steeper, but **no curvature is detectable**. Do not claim acceleration.

**Why required blocks fall while required played hands rise.** A matched block contains k
candidate hands per side, so the signal per block is Δ_block = k·Δ/100. It grows linearly in k,
while the noise per block is σ_D. Therefore:

    N_blocks = ((z.975 + z.8) σ_D / (kΔ/100))²   ∝ σ_D² / k²  ∝ k^(β_var − 2)
    N_hands  = 2k · N_blocks                      ∝ σ_D² / k   ∝ k^(β_var − 1)

Three regimes follow:
* β_var = 1: block variance grows exactly like the number of hands. Per-hand burden is
  invariant, and blocks fall as 1/k.
* β_var = 2: σ_D grows as fast as the per-block signal. The block count is flat, and hands
  grow ∝ k.
* Observed: β_var = 1.37 [1.25, 1.50], strictly between the two.

**Adding seats raises the per-block signal (∝ k) faster than the per-block noise
(∝ k^0.69).** Fewer blocks are needed. But the noise grows faster than √k, the benchmark if
each added seat contributed the same independent noise as before. Each block also costs 2k
played hands, so the played-hand total rises. The effect is sublinear: going from 3 to 8 seats
(×2.67) multiplies required hands by ×1.47.

## C. Mechanism

These are descriptive associations from stored metrics (`deep/mechanism.csv`,
`deep/mechanism_scaling.csv`). The medians over p1–p3 are:

| metric | 3 | 4 | 6 | 8 | 8/3 |
|---|---|---|---|---|---|
| σ_D² / k (per candidate hand) | 23.7 | 26.2 | 29.0 | 34.9 | 1.47 |
| mean per-seat variance var(D_s) | 24.7 | 25.9 | 30.0 | 34.8 | 1.41 |
| cross-seat covariance share of σ_D² | −0.9% | −2.4% | −2.2% | +0.1% | ≈ 0 |
| P(D_s ≠ 0) per candidate seat (A vs B outcome differs) | 6.65% | 6.19% | 5.16% | 4.59% | 0.69 |
| E[D_s² given D_s ≠ 0] (BB²) | 307 | 382 | 499 | 663 | 2.16 |
| P(D = 0), per block | 0.82 | 0.78 | 0.73 | 0.69 | 0.84 |
| blocks with a pot ≥ 1 stack | 1.9% | 3.2% | 6.5% | 11.2% | 5.8 |
| … per played hand | 0.32% | 0.40% | 0.55% | 0.70% | 2.18 |
| all-in hands per played hand | 1.08% | 1.50% | 2.50% | 3.79% | 3.53 |
| share of σ_D² in big-pot blocks | 0.80 | 0.81 | 0.84 | 0.88 | 1.10 |
| share of σ_D² in all-in blocks | 0.82 | 0.82 | 0.85 | 0.88 | 1.08 |
| mean squared deviation per big-pot block | 2,892 | 2,411 | 2,110 | 2,163 | 0.75 |
| variance contribution of big-pot blocks | 56.5 | 83.0 | 145 | 249 | 4.4 |
| variance contribution of other blocks | 14.5 | 18.6 | 26.4 | 29.9 | 2.1 |
| excess kurtosis | 134 | 96 | 71 | 68 | 0.50 |
| top-1% share of squared deviation | 0.88 | 0.83 | 0.71 | 0.57 | 0.65 |

**Assessment of the candidate mechanisms.**

1. **Big decisive pots become more frequent: supported.** The rate of stack-sized pots rises
   per block (×5.8) and per played hand (×2.2). All-in hands per played hand rise ×3.5.
   Big-pot blocks carry 80–88% of σ_D² at every table size, and their variance contribution
   grows faster (k^1.49) than that of other blocks (k^0.76).
2. **Decisive pots become larger: not supported at the block level.** The mean squared
   deviation per big-pot block falls from 2,892 to 2,163.
   * The per-seat squared difference given divergence does rise ×2.2. That reflects the
     changing *mix* of divergences: a larger share are big-pot events.
   * No stored metric shows that an individual big pot moves D by more.
3. **Multiway interaction increases divergence probability: contradicted.** Per candidate
   seat-hand, A and B outcomes differ *less* often at larger tables (6.6% → 4.6%).
   * Block-level P(D = 0) falls only because a block contains more seats.
   * What rises is the size of the divergences that do occur.
   * We did not measure why divergence per seat falls. With more players acting first,
     plausibly both candidates fold the same hands more often, but this is not tested.
4. **Tail concentration changes: yes, but downward.** Larger tables are harder per hand while
   *less* dominated by rare extreme blocks. The top-1% share falls from 0.88 to 0.57 and
   kurtosis from 134 to 68.
   * p1 barely changes (0.975 → 0.897).
   * Big-pot blocks remain the variance carriers. At 8-max they are common (11% of blocks),
     not rare (2% at 3-max).
5. **Combination.** The supported description is:
   * cross-seat covariance is negligible, so block variance ≈ k × per-seat variance;
   * per-seat variance rises 41% from 3 to 8 seats;
   * the rise comes with more frequent stack-sized and all-in pots per played hand, so
     divergences are rarer per seat but larger on average;
   * variance is spread over more big-pot blocks rather than concentrated in a few.

   **This is an association under these agents, not an identified causal mechanism.**

**Position (appendix, `deep/seat_position.csv`).** The blinds carry the largest share of
per-seat variance at every size. At p2, SB + BB account for 69% of per-seat variance at 3-max
and 33% at 8-max, and early positions carry the least.

**Wall-clock (secondary; implementation-specific).** Median compute at 8 workers on this
machine is 0.16, 0.24, 0.32 and 0.47 hours (8/3 ×2.95). This rises faster than required hands
because decisions per played hand grow ∝ k (3.7 → 9.9) and throughput per hand falls.

## D. Controlled vs historical 4/6

The historical frozen corpora are:
* `fhr3-nlhe4-100bb-v2`: 100k blocks, population `mixed3-v1` (T, L, A);
* `fhr3-nlhe6-100bb-pilot-v1`: 250k blocks, population `mixed5-v1` (T, N, L, A, N).

The medians are 4.26M and 4.43M hands, giving 6/4 = 1.04 [0.98, 1.11].

The suite shares their root seed and deal layout, so controlled block b deals the same cards as
historical block b. The comparison below is paired on blocks 0..29,999 (`deep/historical.csv`):

| | 4-max | 6-max |
|---|---|---|
| hands ratio controlled / historical, median | 1.00 [0.87, 1.10] | 1.01 [0.93, 1.07] |
| … p1 / p2 / p3 | 0.97 / 1.04 / 0.90 [0.80, 0.99] | 0.99 / 1.01 / 0.98 |
| corr(D) controlled vs historical | 0.70–0.79 | 0.75–0.77 |

| hands 6-max / 4-max (median) | value |
|---|---|
| controlled, 30k | 1.11 [0.99, 1.25] |
| historical, first 30k (same blocks) | 1.10 [0.95, 1.25] |
| historical, full 100k / 250k (frozen C10) | 1.04 [0.98, 1.11] |
| population term (controlled 6/4 ÷ historical 6/4, same blocks) | 1.01 [0.89, 1.18] |

**Why did the historical comparison look invariant?** Two reasons:
* 4 and 6 are adjacent points on a modest gradient: the controlled 4→6 step is ×1.11.
* The frozen full-corpus estimate (1.04) happens to sit at the low end of that step's
  uncertainty. On the same 30k blocks, the historical populations give 1.10, like the
  controlled suite.

**How much came from the changing population?** Essentially none detectable. The median
population effect at fixed table size is 1.00 at 4-max and 1.01 at 6-max. The one significant
pairing-level effect is historical 4-max p3, whose all-non-neutral lineup needed about 12%
more hands (controlled/historical 0.90 [0.80, 0.99]). The difference between 1.04 and 1.11 is sampling (different blocks in heavy-tailed
data), not population.

**Does controlled 4-vs-6 alone support near-invariance?** It cannot distinguish invariance
from the trend. 6/4 = 1.11 [0.99, 1.25], and the controlled 4-max ratio 0.90 [0.79, 1.02]
includes 1. It is not decisive either way.

**Does 3–8 reveal a broader curve?** Yes. Both endpoints exclude 1 (3-max 0.82 [0.71, 0.93];
8-max 1.20 [1.07, 1.36]). The slope is positive for every pairing and in every prefix and
disjoint window. The two-point 4/6 design could not detect this, because at +0.37 elasticity
the expected 4→6 step (~×1.16) is within its resolution limit.

## E. Is 30k enough?

**Yes, for every claim proposed for the main text.**

| check | median elasticity | CI | other |
|---|---|---|---|
| prefix 0–10k | +0.37 | [0.20, 0.61] | |
| prefix 0–20k | +0.34 | [0.22, 0.51] | |
| full 30k | +0.37 | [0.25, 0.50] | |
| window 0–10k | +0.37 | CI excludes 0 | 8/6 ratio 1.22 |
| window 10–20k | +0.28 | [0.08, 0.49] | 8/6 ratio 1.14 |
| window 20–30k | +0.38 | CI excludes 0 | 8/6 ratio 1.29 |

* The 3-max ratio is ≤ 0.87 in every window, and the 8-max ratio is ≥ 1.14 in every window.
* σ_D relative SE at 30k is 2.0–5.4% (delta method), which is 4–11% on required hands.
* The mechanism metrics move monotonically in k by factors of 1.4–5.8, far larger than their
  sampling noise.

**A 60k extension (≈ 2× the blocks, CIs about 1/√2 narrower) would sharpen three things:**
* the controlled 4-vs-6 contrast, where it would likely exclude 1, but that is not a claim;
* p1's own CIs;
* segment elasticities, where no curvature claim is proposed.

It would not change any proposed conclusion. **No new simulation is scientifically necessary.**
If the paper later wants a curvature or acceleration claim at larger tables, that needs a
different design (more table sizes, e.g. 5, 7, 9), not more blocks.

## F. Claim hierarchy (details in `claims.json`)

**Main text**
* **TS1.** Per-hand evaluation burden rises modestly and consistently with table size in the
  controlled 100BB NLHE benchmark.
  * Required hands 3.71M → 5.47M (median), ×1.47 [1.29, 1.69] from 3 to 8 seats.
  * Descriptive elasticity +0.37 [0.25, 0.50].
* **TS2.** The direction is common to all three pairings (+0.28, +0.36, +0.35), with
  indistinguishable slopes. The absolute level depends on the pairing (~3×).
* **TS3.** Required independent blocks fall (8/3 ×0.55 [0.48, 0.63]) while required played
  hands rise. Block variance grows as k^1.37 [1.25, 1.50]: faster than per-hand invariance
  (k^1), slower than a flat block count (k^2).
* **TS4 (descriptive mechanism).** Cross-seat covariance is negligible, so the rise is in
  per-seat variance.
  * At larger tables, A and B diverge less often per seat but by more.
  * This comes with more stack-sized pots per played hand (×2.2) and more all-in hands
    (×3.5).
  * Big-pot blocks carry 80–88% of σ_D² at every table size; the squared deviation per
    big-pot block does not rise.
* **TS5.** Standardizing the opponent population left block variance at fixed table size
  unchanged (controlled/historical 1.00 at 4-max, 1.01 at 6-max, paired on deals).
  * The earlier 4-vs-6 near-invariance was correct for those two sizes but underpowered as a
    general claim.
  * The 3–8 sweep reveals the gradient.

**Main text, one sentence (qualifies the "where variance lives" section)**
* **TS6.** Tail concentration depends on table size: the top-1% share is 0.88 at 3-max and
  0.57 at 8-max (median). Larger tables are harder per hand but less dominated by rare extreme
  blocks.

**Appendix only**
* Segment elasticities and the absence of detectable curvature.
* Per-pairing tables.
* p1 window instability.
* Seat-position decomposition.
* Wall-clock and throughput.
* Decisions and showdowns per hand.
* Prefix and window stability.
* Pairing-level population effects (4-max p3).
* The integrity-check glob fix.
* Historical C10 as context.

## G. Figure

One new main figure with two panels (`figure_plan.md`):
* **(a)** Required played hands relative to controlled 6-max vs seats (log-log). It shows
  p1/p2/p3 with CIs and the emphasized median, with the median required-blocks ratio on the
  same ratio axis and a flat per-hand-invariance reference.
* **(b)** The per-seat mechanism, as indices on a log axis: divergence probability falls,
  conditional magnitude rises, per-seat variance rises modestly, and big pots per played hand
  rise.

Existing figures stay unchanged. F2 (cost metrics) moves to the appendix, and the F3 caption
gains a one-clause caveat that concentration depends on table size.

## H. Paper integration

See `figure_plan.md` §3. Table size becomes its own short section after stack depth, about
0.75–1 page with one figure. It is framed as the second environment axis alongside stack depth,
with the same frequency-vs-magnitude lens.

## I. Publication-safe language

* Say "in this controlled benchmark" or "under these agent populations". Never say that
  variance or sample requirements are intrinsic to a table size or game.
* Absolute hands (3.7–5.5M) are conditional on the agents and pairings. The transferable
  results are the direction, the common slope across pairings and the blocks-vs-hands logic.
* Call β values "descriptive power-law fits over four table sizes", never scaling laws.
* The mechanism is "associated with" or "accompanied by". The seat decomposition is an
  identity; the link to big pots is correlational across four table sizes.
* Do not say "multiway play makes agents diverge more": the data show the opposite per seat.
* Keep the historical 4/6 (C10) and the controlled suite in separate sentences and tables.
  Report the population comparison as paired on deals.
* The synthetic agents are experimental instruments, not representations of FullHouse
  entrants. The agents are not re-tuned per table size.
* Residual variance after AIVAT (RQ6) is "not removed by this value function", not "purely
  strategic". This is unaffected here, but keep it consistent.

## J. Caveats specific to this analysis

* Four table sizes, three pairings, one agent family, 100BB only.
* Per-slot mixture is exact, but per-block composition varies at 3/4/8-max, and larger tables
  have more opponents of every style.
* The 1 BB/100 target is held fixed across k.
* CIs are sampling-only with pairings held fixed. Across-table-size CIs are independent-sample.
