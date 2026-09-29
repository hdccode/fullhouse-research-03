# FHR3A table-size figure plan and paper integration

This is a plan only. No final figure has been rendered, and F1–F6 are unchanged. Claims are in
`claims.json`; the evidence is in `ANALYSIS.md`.

## 1. One new main figure: "Table size" (two panels, 183 mm × ~70 mm)

The figure uses the existing design system (`paper/figures/style.py`):
* Arial 6–7 pt, sentence case, bold lowercase panel letters;
* pairing markers p1 ○, p2 □, p3 △ with matched areas;
* the median drawn in ink (`INK`) with a heavier line;
* direct labels and no legend boxes where avoidable.

All data are NLHE, so the format palette is not used for identity. Pairings are marker shapes in
mid-grey, and the mechanism quantities in panel b take palette slots 1–4 with direct labels and
distinct line styles. Colour is never the only encoding.

### Panel a: required played hands vs table size

**Establishes:** TS1, TS2, TS3.

* **x axis:** seats (3, 4, 6, 8) on a log axis. Tick labels read "3 / 6 hands per block" and so
  on, so block size is visible without a second axis.
* **y axis:** ratio to controlled 6-max on a log axis (0.5–1.5). Every quantity plotted is a
  unitless ratio, so there is one axis and never a dual axis.
* **Marks:**
  * p1/p2/p3: markers, slightly dodged in x, with bootstrap 95% CIs
    (`figure_data.csv`: `hands_rel_6max`, `_lo`, `_hi`).
  * Median: a heavy ink line through the median ratios, with its CI band
    (`series = median`).
  * Median required-blocks ratio: a thin grey dashed line, directly labelled "matched blocks".
    It shows blocks falling (1.63 → 0.90) while hands rise.
  * Reference: a horizontal line at 1, labelled "per-hand invariance (β = 0)".
* **Direct annotations:**
  * the absolute median at each k: 3.7M, 4.1M, 4.6M, 5.5M hands;
  * "hands ∝ k^0.37 [0.25, 0.50]; blocks ∝ k^−0.63".
* **Why ratios, not absolute hands:** p1 sits about 3× below p2/p3 at every k, so on an
  absolute axis the shared slope is harder to see. The absolute medians are printed, and the
  full absolute table goes to the appendix.

### Panel b: what changes per candidate seat

**Establishes:** TS4, and explains panel a directly.

Cross-seat covariance is negligible, so required hands ∝ σ_D²/k ≈ per-seat variance. Per-seat
variance factors exactly into P(D_s ≠ 0) × E[D_s² given D_s ≠ 0] (the mean is negligible).
Panel b plots these factors.

* **x axis:** seats (log), shared with panel a.
* **y axis:** index relative to 3-max, log axis (about 0.6–2.4).
* **Lines:** medians over p1–p3, each with a thin pairing-range band.
  1. per-seat variance: the quantity behind panel a, ×1.41;
  2. P(A and B outcomes differ at a seat): ×0.69, falling;
  3. mean squared difference when they differ: ×2.16;
  4. stack-sized pots per played hand, as grey dashed context: ×2.18.
* **Source:** `deep/mechanism.csv`, columns `seat_var_mean`, `p_seat_diverges`,
  `seat_dev2_given_diverge`, `big_blocks_per_played_hand`.
* **One-line takeaway in the panel title:** "rarer but larger divergences".

### Rejected alternatives

* **σ_D vs k:** it duplicates panel a (β_σ = β_hands/2 + 1/2), so it adds no information.
* **Tail-concentration panel** (top-1% share 0.88 → 0.57): a real result, but secondary. It goes
  in one sentence plus the F3 caption.
* **Big-pot frequency × magnitude scatter in the F4a style:** it would echo the stack-depth
  figure, but the seat decomposition explains panel a exactly, while the scatter only
  correlates.
* **A historical 4/6 overlay:** it would mix the controlled and historical designs. The
  reconciliation stays in text and an appendix table.

### Figure-data export (to add when rendering)

Add `F7a_table_size_hands.csv` (from `reports/table-size/figure_data.csv`) and
`F7b_table_size_mechanism.csv` (from `reports/table-size/deep/mechanism.csv`) through
`scripts/paper_figure_data.py`, with sha256 sums. Then add a `fig7.py` to `make_all.py` with the
same invariant-check pattern: the ratios, elasticity and absolute medians are asserted against
`summary.json`.

## 2. Existing figures

| figure | decision | reason |
|---|---|---|
| F1 sample complexity by format | **retain unchanged** | Its format comparison uses the frozen core corpora. At matched blocks the controlled 4/6 medians differ from the historical ones by ≤1% (TS5; the largest single-pairing difference is 4-max p3, about 10%), so nothing in F1 is contradicted. |
| F2 cost metrics (blocks / hands / wall-clock) | **move to appendix** | Useful, but the blocks-vs-hands point is now made more sharply by the table-size panel a. Frees main-text space. |
| F3 variance concentration | **retain; revise caption only** | Add: "concentration is configuration-dependent; in the controlled table-size suite the top-1% share falls from 0.88 (3-max) to 0.57 (8-max)". |
| F4 big pots / stack depth | **retain unchanged** | Parallel lens to table size; cross-reference it from the new section. |
| F5 variance reduction | **retain unchanged** | Unaffected. |
| F6 sequential monitoring | **retain unchanged** | Unaffected. |
| **new** table-size figure | **add** | Becomes Figure 4 in the order below. |

## 3. Revised FHR3A structure

Here "controlled" means the fixed benchmark populations throughout.

1. **Controlled evaluation framework.** Matched blocks, the estimand, agents as experimental
   instruments, the definitions of blocks and played hands, and the 1 BB/100 at 80% power
   target. No figure; the table-size design is described in §4.
2. **Where the variance lives.** Cross-format burden (Fig 1 = F1) and concentration in rare
   big-pot blocks (Fig 2 = F3).
3. **Stack depth.** Fig 3 = F4: frequency up and magnitude down faster as stacks shorten.
4. **Table size** (new; about 0.75–1 page, Fig 4). One paragraph each:
   * *design:* why a common marginal population was used, and that the historical 4/6 corpora
     are kept separate;
   * *result:* TS1–TS3;
   * *mechanism:* TS4 and TS6;
   * *reconciliation:* TS5, in one or two sentences.

   Table size deserves its own short section, not a subsection of formats. It is the second
   controlled environment axis next to stack depth, and it produces the paper's clearest
   blocks-vs-hands lesson. It should not exceed stack depth in length.
5. **Removable vs persistent variance.** Fig 5 = F5.
6. **Fixed-N and monitoring implications.** Fig 6 = F6.
7. **Limitations.** Add:
   * four table sizes, one agent family, 100BB only;
   * the per-slot (not per-block) population control;
   * no re-tuning per table size.

**Appendix additions:**
* the full per-pairing table-size table (12 rows);
* segment elasticities and curvature;
* prefix and window stability;
* seat-position decomposition;
* the controlled-vs-historical paired table;
* compute cost;
* F2.

## 4. Language for the new section (publication-safe)

* "In this controlled NLHE 100BB benchmark, the played-hand burden rises modestly with table
  size", not "larger tables are harder".
* "Descriptive power-law fit over four table sizes (β = 0.37 [0.25, 0.50])", not "scaling law".
* "Accompanied by / associated with more frequent stack-sized pots per played hand", not
  "caused by".
* "Candidate outcomes diverge less often per seat but by more", never "multiway play increases
  divergence".
* Historical C10 always appears in its own sentence, labelled as a different design with
  table-size-dependent populations.
