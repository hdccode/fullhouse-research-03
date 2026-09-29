# FIGURES and TABLES: final specifications

Figure data is in `paper/figures/data/`, generated from frozen outputs by
`scripts/paper_figure_data.py`; checksums are in `paper/figures/data/SHA256SUMS`. Each CSV
starts with a `# source:` line. Images have not been rendered: matplotlib is not in the
project environment, and adding it would change `uv.lock`. Render in any plotting
environment from these CSVs.

**Shared encoding:**
* one colour per format, fixed across F1–F4, colour-blind safe;
* pairing role by marker shape (p1 ○, p2 △, p3 □);
* methods in F6 by colour (fixed-N grey, naive peeking red/orange, confidence sequence
  blue);
* log axes are labelled with real values (100k, 1M, 10M), not exponents.

Main text: 6 figures.

---

## F1: Played hands needed vs the true edge
* **Data:** `F1_hands_vs_effect.csv`, one row per format × Δ, with columns
  `median_played_hands`, `min_played_hands` and `max_played_hands` over p1–p3.
* **Axes:** x = true edge Δ (BB/100), log, 0.1–20. y = played hands for 80% power, log.
* **Marks:** a median line per format plus a p1–p3 min–max ribbon (alpha ≈ 0.2). Add a
  vertical guide at 1 BB/100.
* **Order:** legend by median at 1 BB/100: AoF, NLHE 4-max, NLHE 6-max, Crazy Pineapple,
  Nit, PLO, Bomb.
* **Caption facts:**
  * matched blocks, two-sided α = 0.05, 80% power;
  * medians at 1 BB/100 range from 0.34M (AoF) to 20.5M (Bomb): 61× overall, 4.8× among
    100BB formats;
  * ribbons show the spread over three candidate pairings.
* **Takeaway:** equal hand budgets buy very different amounts of evidence, and the curves'
  slope of −2 means halving the edge quadruples the hands.
* **Caveats:** agent- and reference-dependent. A 1 BB/100 edge is not equally meaningful
  across formats. Nit uses variable-length rounds (hands counted as played).

## F2: The same evaluations measured in three units
* **Data:** `F2_cost_by_metric.csv`, keyed by format × role × metric
  (independent blocks / played hands / wall-clock hours), plus a `role = median` row per
  format.
* **Layout:** three side-by-side panels sharing the y axis (formats, ordered by median
  played hands). x = requirement at 1 BB/100 and 80% power, log scale, independent per
  panel.
* **Marks:** p1/p2/p3 as shaped dots; the median as a short vertical tick.
* **Caption facts:**
  * ratios: blocks 41×, hands 61×, wall-clock 475×;
  * within-format pairing spread 2.8–8.5× among 100BB formats, vs 4.8× between them;
  * wall-clock is measured at 8 workers and is implementation-specific.
* **Takeaway:** the ordering depends on the unit, and pairing choice moves requirements
  about as much as format choice.
* **Caveat:** pairings are not identical perturbations across formats.

## F3: Where the squared deviation lives
* **Data:** `F3_variance_concentration.csv`, keyed by format × role, with `top_fraction`
  and `cumulative_share_sq_dev`, plus a `Gaussian reference` series.
* **Layout:** a 7-panel small-multiple grid (one per format) with the same axes.
* **Axes:** x = top fraction of blocks ranked by |D − mean|, log, 1e-5 to 1.
  y = cumulative share of squared deviation, linear, 0–1.
* **Marks:** three pairing curves per panel; the Gaussian reference as a dashed curve in
  every panel.
* **Caption facts:**
  * in 100BB formats the top 1% of blocks carry 33–95% of the squared deviation, vs ≈ 8.5%
    for Gaussian data;
  * p1 curves reach 1.0 by the top ~10% because 83–95% of their blocks have D = 0 (all formats except Nit, 31%).
* **Takeaway:** a sliver of blocks carries most of the evaluation uncertainty.
* **Caveat:** per pairing, the 0.1% level rests on 10–250 blocks and the 0.01% level on
  1–25.

## F4: The mechanism: big pots, and what stack depth does to them
* **Panel A, frequency vs magnitude.**
  * Data: `F4a_bigpot_frequency_magnitude.csv`.
  * Axes: x = fraction of blocks with a pot of at least one starting stack
    (`frac_blocks_big_pot`, log). y = mean squared deviation per big-pot block
    (`mean_sq_dev_per_big_pot_block`, log).
  * Marks: dashed iso-variance guide lines (x·y = const). Points coloured by format and
    shaped by role. Connect the NLHE 6-max stack series 20 → 50 → 100BB (`stack_series`)
    with a thin line per role. Nit is excluded; AoF is included, with big pot = 8BB.
  * Caption fact: big-pot blocks carry 79–97% of squared deviation in 100BB formats.
* **Panel B, stack depth.**
  * Data: `F4b_stack_depth.csv`.
  * Axes: x = stack (20, 50, 100 BB). y = blocks needed relative to 100BB
    (`blocks_needed_vs_100`, log), or σ ratio with its CI (`sd_ratio_vs_100`, `ci_lo`,
    `ci_hi`).
  * Marks: three pairings.
  * Caption fact: 100BB needs 6.8–7.2× the blocks of 20BB and 2.0–2.1× those of 50BB; all-in
    frequency rises as stacks shrink, but squared deviation per all-in falls faster.
* **Takeaway:** uncertainty is a frequency × magnitude of decisive big pots. Stack depth
  trades one against the other.
* **Caveats:** exploratory, not causal. Agents are not stack-aware.

## F5: How much variance can estimators remove? (RQ6)
* **Data:** `F5_variance_reduction.csv` (rows ordered by `order`), with inset data in
  `F5_inset_aof_p1.csv`.
* **Axes:** y = five rows, top to bottom: AoF 8BB all-in EV; NLHE 20BB all-in EV; NLHE
  100BB all-in EV; NLHE 100BB MIVAT; NLHE 100BB AIVAT. x = variance ratio
  Var(estimator D) / Var(raw D), linear, 0–1.05, with a secondary top axis for sample
  efficiency 1/x (1×, 1.5×, 2×, 5×, 10×).
* **Marks:** p1/p2/p3 points with paired-bootstrap 95% CI bars. Solid reference line at 1
  (raw); dotted line at 0.5.
* **Inset:** AoF p1, production v2 vs 10% blend on the same 50k blocks. Show the mean with
  95% CI (BB/100) for raw and for all-in EV, with a zero line.
* **Caption facts:**
  * variance ratios: AoF 0.098 (≈ 10× efficiency); 20BB 0.716; 100BB all-in EV 0.878,
    MIVAT 0.616, AIVAT 0.580 (medians);
  * inset: raw +0.27 [−0.07, +0.62] vs all-in EV +0.41 [+0.30, +0.52];
  * all estimators target the same estimand (max |z| of estimator − raw is 1.29).
* **Takeaway:** removable chance falls steeply with stack depth, and at 100BB most of the
  variance survives even the best estimator.
* **Caveat:** MIVAT and AIVAT use a fitted linear value function. The inset's point
  estimates differ within sampling noise (z = 0.79).

## F6: How should evaluation stop? (RQ7)
* **Panel A, false conclusions under the null.**
  * Data: `F6a_false_exclusion.csv`.
  * Axes: x = six groups: NLHE 6-max p1 (heavy), Crazy Pineapple p2, PLO p3, Normal,
    Student t3, then (separated) real orderings of NLHE 6-max p1. y = probability the
    interval ever excludes the true mean, 0–0.7.
  * Marks: three methods side by side, with Wilson 95% CIs and a 5% reference line.
  * Caption facts: fixed-N single look 4.45–4.95%; naive peeking 58.0–63.9% (real
    orderings 44.8%); confidence sequence 2.4–3.4% (real orderings 0.9%); 2,000 null
    streams per group (1,000 orderings); horizon 250k blocks.
* **Panel B, the flagship comparison in real order.**
  * Data: `F6b_trajectory_nlhe6_p2.csv` plus `F6b_markers.csv`.
  * Axes: x = blocks, log, 200–250,000. y = BB/100.
  * Marks: running mean line; t-interval ribbon (light); CS ribbon (darker outline); zero
    line; a marker at block 204 (naive stop: −27.9 [−54.0, −1.8]); endpoint bars at 250k
    for the fixed-N interval [+0.43, +2.13] and the CS [−0.06, +2.61]. Clip y to about ±60
    and note that early CS widths exceed the axis.
  * Caption facts: naive peeking declares the tight agent better after 204 blocks, while
    the full corpus shows +1.28 BB/100 for the neutral agent (z = 2.94). The confidence
    sequence never excludes zero.
* **Takeaway:** repeated looks at an ordinary interval produce confident false conclusions
  early. The confidence sequence stays valid at a cost of about 1.6–1.7× the fixed-N sample
  for equal power.

---

## Tables

### Main text
**Table 1: Benchmark design** (the only main-text table).

| format | players | stack | block (hands/side × sides) | pairings | blocks per pairing |
|---|---|---|---|---|---|
| NLHE | 6 | 100BB | 6 × 2 | p1–p3 | 250,000 |
| NLHE | 4 | 100BB | 4 × 2 | p1–p3 | 100,000 |
| NLHE (stack series) | 6 | 20 / 50BB | 6 × 2 | p1–p3 | 10,000 |
| Crazy Pineapple | 6 | 100BB | 6 × 2 | p1–p3 | 100,000 |
| PLO | 6 | 100BB | 6 × 2 | p1–p3 | 50,000 |
| Bomb Pot | 6 | 100BB (2BB ante) | 6 × 2 | p1–p3 | 50,000 |
| All-in-or-Fold | 4 | 8BB | 4 × 2 | p1–p3 | 50,000 |
| Nit Game | 6 | 100BB | nit round (~47.5 × 2) | p1–p4 | 10,000 |

Every format also has a self-play control (10,000 blocks; D exactly 0). RQ6 and RQ7 runs
are summarized in their own sections.

Source: `docs/final_status.md` §1 and `reports/final-analysis/MANIFEST.json` (row counts).

### Appendix tables
* **A1:** full per-format × pairing table: σ_D [bootstrap CI], D = 0 rate, skew, kurtosis,
  quantiles, all seven concentration levels, all-in/showdown/pot, blocks/hands at
  0.25–5 BB/100 (80% and 95% power), throughput, storage.
  Source: `reports/final-analysis/final_tables.md` sections A–C.
* **A2:** medians with CIs, pairing ranges, neighbour ratios (blocks/hands/wall-clock).
  Source: `final_tables.md` §D and `ranking.json`.
* **A3:** pilot convergence and the pilot-size rule. Source: `final_tables.md` §E and
  `convergence.csv`.
* **A4:** standardized-d / empirical power. Source: `d_collapse.csv`.
* **A5:** stack series. Source: `stack.json`.
* **A6:** Nit decomposition. Source: `nit.json`.
* **A7:** RQ6 full estimator table (80% and 95% hands, CIs, correlation, bias z).
  Source: `reports/rq6/rq6_summary.csv` and `reports/rq6/deep/rq6_hands.csv`.
* **A8:** RQ6 tails and the big-pot decomposition after correction.
  Source: `reports/rq6/deep/rq6_tails.csv`.
* **A9:** RQ6 compute and net wall-clock. Source: `reports/rq6/deep/rq6_efficiency.csv`.
* **A10:** RQ7 min-N sensitivity. Source: `reports/rq7/min_n_sensitivity.csv`.
* **A11:** RQ7 stopping distributions and power-matched cost.
  Source: `reports/rq7/stopping.csv` and `reports/rq7/deep/stopping_cost.csv`.
* **A12:** RQ7 width inflation. Source: `reports/rq7/deep/width_inflation.csv`.
* **A13:** RQ7 real orderings, all 28 streams. Source: `reports/rq7/real_orderings.csv`
  and `deep/real_orderings_sign.csv`.
* **A14:** integrity and reproducibility: manifests, validation, git SHAs.
