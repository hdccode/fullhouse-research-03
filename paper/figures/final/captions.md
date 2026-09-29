# Figure captions

All results are for matched blocks against a fixed reference population: duplicate deals
with shared randomness, and the block is the unit of inference. "Required" sample sizes are
for a two-sided test at α = 0.05 with 80% power. Pairing shapes are the same in every figure
(p1 ○, p2 □, p3 △), as are the format colours.

**Figure 1 | Equal hand budgets differ by orders of magnitude in resolving power.**
Played hands needed to detect a true edge between two candidate agents, as a function of
the edge (BB/100 of candidate hands), for seven poker formats.
* Lines are medians over three candidate/reference pairings (p1–p3); dots mark 1 BB/100.
* Required hands scale as Δ⁻², so the curves are parallel and every ratio between formats
  holds at every edge. At 1 BB/100, the medians span 61× across all formats (0.34M hands for
  8BB All-in-or-Fold to 20.5M for Bomb Pot), and 4.8× among the five 100BB formats.
* Per-pairing values are in Fig. 2.
* Requirements depend on the benchmark agents and reference population. A 1 BB/100 edge is
  not equally meaningful across formats, and this is not a difficulty ranking of poker
  variants.

**Figure 2 | The practical ordering depends on whether cost is counted in blocks, hands or
compute.**
Requirement at 1 BB/100 (80% power) for each format in (a) independent matched blocks,
(b) played hands, and (c) measured wall-clock time at 8 workers.
* Markers are the three pairings; horizontal lines span them; black ticks are medians.
* Largest/smallest medians: 41× (blocks), 61× (hands), 475× (wall-clock).
* Within a 100BB format, the pairing changes the required hands 2.8–8.5×, comparable to the
  4.8× spread between 100BB formats. Perturbations are not identical across formats: AoF and
  Bomb Pot p1 are format-specific.
* Wall-clock depends on this simulator, its implementation and the hardware.

**Figure 3 | A tiny fraction of matched blocks carries most evaluation uncertainty.**
Cumulative share of the total squared deviation of the block difference D carried by the
most extreme blocks (ranked by |D − mean|), one panel per format.
* Lines are medians over pairings; bands span the pairings; the dashed curve is the Gaussian
  reference.
* Labels give the share carried by the top 1% of blocks (median over pairings): 33–95% in
  the 100BB formats, against 8.5% for Gaussian data.
* Curves that reach 100% by ~10% of blocks reflect blocks with D = 0 (identical play on both
  sides).
* At the 0.1% level, the curves rest on few blocks and are noisier.

**Figure 4 | Stack depth changes the frequency and the magnitude of decisive big pots.**
(a) For each pairing: the share of blocks containing a pot of at least one starting stack
(x), against the mean squared deviation of D per such block (y).
* Grey lines mark constant products: the squared deviation contributed by big-pot blocks,
  in BB² per block.
* Filled markers are the headline formats. Open markers are NLHE 6-max at 20BB and 50BB
  (same cards and agents), linked to 100BB by pairing.
* Big-pot blocks carry 79–97% of the squared deviation in every 100BB format. The frequency
  × magnitude split is descriptive, not causal.

(b) Block-level σ of the same NLHE 6-max pairings at 20, 50 and 100BB, relative to 100BB,
on identical blocks.
* Error bars are paired bootstrap 95% CIs.
* 100BB needs 6.8–7.2× the matched blocks of 20BB and 2.0–2.1× those of 50BB.
* As stacks shrink, all-in pots become more frequent but each moves D far less.
* The agents are not stack-aware.

**Figure 5 | Removable chance variance rises sharply as stacks become shallower.**
(a) Variance of each estimator's block difference relative to the raw outcome, on the same
matched blocks.
* All estimators target the same estimand. The largest |z| of mean(estimator − raw) is 1.29.
* Markers are pairings, with paired block-bootstrap 95% CIs; black ticks are medians.
  Columns give the median variance ratio and the implied sample-efficiency gain
  (1/ratio).
* All-in EV removes about 90% of the variance in 8BB AoF, 28% at 20BB and 12% at 100BB. At
  100BB, fitted MIVAT and AIVAT leave 62% and 58%.
* The remaining 100BB variance reflects strategic divergence plus chance variation not
  captured by the fitted linear value function.

(b) AoF production policy v2 vs a 10% blend, on the same 50,000 blocks.
* The raw outcome gives +0.27 BB/100 [−0.07, +0.62]. All-in EV gives +0.41 [+0.30, +0.52].
* Both are unbiased for the same quantity; the difference in point estimates is within
  sampling noise (z = 0.79).
* The raw outcome would need about 511,000 blocks for the all-in EV precision.

**Figure 6 | Repeatedly checking an ordinary confidence interval can confidently choose the
wrong bot.**
(a) Share of streams in which each rule ever excludes the true mean (zero) within 250,000
blocks: a fixed-N test with one precommitted look at 100,000 blocks; naive peeking (the
ordinary 95% interval re-checked after every block from block 200); and an asymptotic
confidence sequence (tuned at 100,000 blocks).
* The first five groups are 2,000 IID null streams each: resampled blocks of three real
  pairings, a Normal and a Student-t3 stream. The last group is 1,000 random orderings of the
  same 250,000 real NLHE 6-max blocks, whose true mean is the corpus mean; sampling without
  replacement makes that group conservative for every method.
* Bars are Wilson 95% intervals. The lower strip zooms on the two valid rules.
* The confidence sequence's coverage is asymptotic and empirical over these streams and
  horizons, not a finite-sample guarantee.

(b) The flagship NLHE 6-max comparison (neutral vs tight), read in its actual block order.
* Shows the running estimate, the ordinary 95% interval (valid at a single precommitted
  look) and the confidence sequence (valid at every look). The y axis is clipped at
  ±60 BB/100.
* Naive peeking stops at block 204 at −27.9 BB/100 [−54.0, −1.8], declaring the tight agent
  better. All 250,000 blocks show +1.28 [+0.43, +2.13] for the neutral agent.
* The confidence sequence never excludes zero and ends at [−0.06, +2.61]. The inset zooms on
  the final 220,000 blocks.
