# FHR3A table-size figure plan and paper integration

**Status: built and frozen.** The figure is `paper/figures/final/figure7_table_size.{svg,pdf,png}`
(183 × 67.8 mm, 600 dpi). It was built by `paper/figures/fig7.py` through `make_all.py`, from
`paper/figures/data/F7a_table_size_burden.csv` and `F7b_table_size_mechanism.csv`, with 123
invariant checks (`sources.f7`). Claims are in `claims.json`; the evidence is in `ANALYSIS.md`;
the caption is in `paper/figures/final/captions.md`. F1–F6 are byte-identical to the committed
package.

## 1. Final design: "Table size changes the cost and character of evaluation"

The figure uses the existing design system (`paper/figures/style.py`):
* Arial, 6.5 pt body, 6 pt labels, 5.5 pt notes, 8 pt bold panel letters;
* sentence-case titles set with `panel_title`;
* pairing markers p1 ○, p2 □, p3 △ with matched areas;
* direct labels.

All data are NLHE and no format is encoded, so the format palette plays no identity role.

### Panel a: "larger tables need fewer matched blocks but more played hands"

**Establishes:** TS1–TS3.

* **x axis:** seats 3, 4, 6, 8 on a **linear** axis. Log was not needed for readability.
  Played hands per block (6, 8, 12, 16) are printed as a second tick row, labelled
  "hands/block".
* **y axis:** one dimensionless axis, "required at 1 BB/100, 80% power (ratio to 6-max)",
  **linear** from 0.55 to 1.95. There is no second y-axis: both series are ratios, and a thin
  rule marks 1.0.
* **Required played hands (the result):**
  * the median over p1–p3 is a heavy solid ink line (1.8 pt) with a light 95% CI band;
  * p1/p2/p3 are mid-grey role markers (dodged ±0.16), each with a bootstrap 95% CI bar and a
    thin connecting trace.
* **Required matched blocks (the contrast):** the median is a dashed dark-grey line with open
  markers.
* **Direct labels:**
  * "played hands" (bold) and "matched blocks" at the right end, with their 8-max values
    1.20 and 0.90;
  * the 3-max values 0.82 and 1.63 at the left end.
* **Annotation:** "elasticity of played hands in seats +0.37 [0.25, 0.50]", from
  `summary.json`.
* **Legend:** pairing markers and "median, 95% CI band" under the heading "played hands (bars:
  95% CI)". The blocks line is directly labelled instead.

### Panel b: "rarer differences, larger when they occur"

**Establishes:** TS4.

* **x axis:** seats, linear, matching panel a.
* **y axis:** "index (3-max = 1)" on a **log** axis (0.55–2.6). Here log is justified: halving
  and doubling look symmetric, and on this axis the variance line is approximately the sum of
  the other two.
* **Lines:** medians over p1–p3, each with a light band for the p1–p3 range and a
  directly labelled right-end value.
  * per-seat variance: heavy ink with ● markers, ×1.41, bold label;
  * "size of the difference when A and B differ": orange with ◆, ×2.16;
  * "chance that A and B differ at a seat": blue with ▼, ×0.69;
  * "big-pot blocks per played hand": grey, dashed, no markers, no band (context), ×2.18.
* **Key:** a small note in the empty corner reads "lines: median over p1–p3 / bands: range over
  p1–p3".
* **Language:** no causal wording anywhere in the figure.

### Deviations from the requested design, and why

* **Panel a uses linear axes.** Log axes were optional, and the linear version reads more
  directly. The elasticity annotation carries the log-log summary.
* **Median hands line has no node markers.** At 3 and 8 seats the median equals p2 (and p3 at
  4), and a median dot would hide that pairing's marker. The pairing markers are drawn above the
  line, and dominance comes from line weight.
* **No CI band on the blocks line.** It overlapped the hands band at 3–4 seats and muddied the
  contrast. The blocks CIs are in `F7a` and the caption covers the definitions.
* **Wording.** "∝ seats^0.37" was replaced with "elasticity of played hands in seats", because
  Arial lacks the ∝ glyph and the phrase is plainer.
* **No "6-max = 1" label.** It collided with the convergence point; the y-axis label states the
  normalisation.
* **Big-pot series in panel b.** It is drawn as context only (dashed grey, no band), and
  all-in incidence and tail concentration are left out, as requested.

### Rejected alternatives (unchanged from the plan)

* **σ_D vs k:** it duplicates panel a.
* **Tail-concentration panel:** secondary; it goes in one sentence plus a note in the F3
  caption.
* **F4a-style frequency × magnitude scatter:** the seat decomposition explains panel a more
  directly.
* **A historical 4/6 overlay:** it would mix the controlled and historical designs.

## 2. Existing figures

| figure | decision | reason |
|---|---|---|
| F1 sample complexity by format | **retain unchanged** | Its format comparison uses the frozen core corpora. At matched blocks the controlled 4/6 medians differ from the historical ones by ≤1% (TS5; the largest single-pairing difference is 4-max p3, about 10%), so nothing in F1 is contradicted. |
| F2 cost metrics (blocks / hands / wall-clock) | **move to appendix** | Useful, but the blocks-vs-hands point is now made more sharply by the table-size panel a. Frees main-text space. |
| F3 variance concentration | **retain; revise caption only** | Add: "concentration is configuration-dependent; in the controlled table-size suite the top-1% share falls from 0.88 (3-max) to 0.57 (8-max)". |
| F4 big pots / stack depth | **retain unchanged** | Parallel lens to table size; cross-reference it from the new section. |
| F5 variance reduction | **retain unchanged** | Unaffected. |
| F6 sequential monitoring | **retain unchanged** | Unaffected. |
| F1 (position) | **keep in main text** | It is the only figure spanning all seven formats, and it anchors §2. The pairing-level detail it lacks lives in F2 (appendix). |
| **new** table-size figure (`figure7_table_size`) | **add as manuscript Figure 4** | Place it after stack depth (Fig 3 = F4). The package keeps the file name `figure7_*` so that no existing artefact, hash or reference is renumbered; mapping package files to manuscript numbers is a manuscript-assembly step. |

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
