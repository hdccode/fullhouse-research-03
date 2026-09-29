# Figure QA

Every figure was inspected at its final 183 mm width: on screen at print scale, in the
600-dpi PNG, and in the QA sheets under `qa/`. Each figure was revised until labels were
collision-free, no text was clipped, and the takeaway was readable without the caption.

## Sources and data integrity

`sources.py` loads the frozen CSVs in `paper/figures/data/`. It then asserts that they
agree with the canonical reports, using a relative tolerance of 1e-6 because hand counts are
stored rounded. The build aborts on any failure.

All **271 checks pass** (148 for F1–F6, 123 for F7); they are listed in `final/build_manifest.json` together with the
sha256 of every source file.

| figure | checks | against |
|---|---|---|
| F1 | 9 | `reports/final-analysis/ranking.json`, `core/pilot_table.csv`. Medians at 1 BB/100; the 61× and 4.8× ratios are recomputed, not typed. |
| F2 | 42 | `ranking.json`: blocks, hands and wall-clock per pairing and median; 41×, 61×, 475× |
| F3 | 28 | `core/pilot_table.csv` `conc_top0.01`. The labels show the exact core values, not interpolated curve values. |
| F4a | 24 | `reports/final-analysis/allin.csv` (exact match by format and pairing) |
| F4b | 6 | `reports/final-analysis/stack.json` σ ratios and CIs |
| F5 | 17 | `reports/rq6/rq6_summary.csv`, `reports/rq6/deep/rq6_deep.json`. The ≈511k raw-equivalent is derived. |
| F6a | 18 | `reports/rq7/coverage.csv`, `real_permutations.csv` |
| F6b | 4 | `reports/rq7/real_orderings.csv`, `deep/real_orderings_sign.csv`. The trajectory ends at 250k and equals the full-corpus mean; the peek stop is at block 204. |
| F7 | 123 | FHR3A table-size suite. Checks: `reports/table-size` output sha256s = its MANIFEST, and `deep.json` is derived from that MANIFEST. F7a (16 rows): all 4 sizes × p1/p2/p3/median, no NaN or duplicates, 6-max ratios exactly 1; hands ratios and CIs = `figure_data.csv`; median hands/blocks ratios and CIs = `summary.json`; pairing blocks ratios = `summary.csv`; hands ratio = blocks ratio × k/6; 2k hands per block; elasticity = `summary.json` = `claims.json` TS1. F7b: values = `deep.json` = `mechanism.csv`, 3-max indices exactly 1, median 8/3 indices = `mechanism_scaling.csv`. |

Numbers printed inside the figures are formatted from the loaded data, never typed. These
include:
* the 61× and 4.8× ratios;
* the top-1% labels;
* the variance ratios and gains;
* the CIs;
* the block-204 values.

The captions (`final/captions.md`) were cross-checked against `paper/NUMBERS.md`.

## Determinism

`make_all.py --check` rebuilds all 18 files and compares their sha256s with the manifest.
The result is **identical**; two consecutive clean builds also gave byte-identical outputs.

The builds are made deterministic by:
* `svg.hashsalt`;
* removing the SVG and PDF creation dates;
* fixed PNG metadata;
* a deterministic label spacer, with no random placement.

## Export checks

| figure | size (mm) | PNG px | SVG text | PDF fonts |
|---|---|---|---|---|
| F1 sample complexity | 183 × 78.0 | 4320 wide, RGB, 600 dpi | `<text>`, 0 glyph paths | TrueType (Type 42), no Type 3 |
| F2 cost metrics | 183 × 62.0 | 〃 | 〃 | 〃 |
| F3 variance concentration | 183 × 91.9 | 〃 | 〃 | 〃 |
| F4 big pots / stack depth | 183 × 73.9 | 〃 | 〃 | 〃 |
| F5 variance reduction | 183 × 63.8 | 〃 | 〃 | 〃 |
| F6 sequential | 183 × 81.8 | 〃 | 〃 | 〃 |
| F7 table size | 183 × 67.8 | 〃 | 〃 (56 text elements) | 〃 |

Type is Arial throughout:
* 6.5 pt body;
* 6.0 pt labels;
* 5.5 pt minimum, for tick notes and inset titles;
* 8 pt bold lowercase panel letters.

## Colour, grayscale and colour-vision deficiency

**Palette validation.** The palette is 7 format slots from the dataviz reference palette,
validated with `validate_palette.js` in light mode:
* lightness band and chroma floor: PASS;
* worst adjacent CVD ΔE: 9.1 (target ≥ 8);
* worst normal-vision ΔE: 19.6 (floor 15);
* three slots below 3:1 contrast on white: WARN.

The contrast warning is relieved because every series is direct-labelled or marker-coded.

**Rejected palettes.** Okabe-Ito and Tol muted/bright were rejected: several slots fall
outside the lightness band for thin marks on white.

**Simulations.** `qa.py` renders each figure in colour, grayscale, protanopia and
deuteranopia (Machado 2009, severity 1).

| figure | where hues converge | what keeps them identifiable |
|---|---|---|
| F1 | NLHE 4-max/6-max and CP/Nit converge in grayscale and deuteranopia | direct labels at line ends, in the same vertical order |
| F2 | rows | rows are labelled on the y axis, so colour is redundant |
| F3 | none | one format per panel, titled |
| F4a | NLHE 4-max and PLO lie close together | text labels next to each cluster; pairing shapes |
| F5 | none that matter | rows labelled; AoF and NLHE groups also separated by stripes |
| F6 | none | methods differ by marker (◆ fixed-N, ✕ peeking, ⬢ CS) and by position; the ribbons differ in lightness as well as hue |
| F7 | (a) none: all ink/grey, by weight and dash; (b) in grayscale the orange magnitude line and the grey dashed big-pot line are similar greys | (b) solid+◆ vs dashed without markers; every line directly labelled with its value; blue ▼ vs orange ◆ stay distinct under protanopia and deuteranopia |

Colour is never the only encoding:
* Pairings are always p1 circle, p2 square, p3 triangle, with the marker areas matched.
* RQ7 methods have their own markers.

## Deliberate deviations from `paper/FIGURES.md`

1. **F1 has no pairing ribbons.**
   * Required hands scale as Δ⁻², so every curve is exactly parallel. Seven overlapping
     ribbons produced an unreadable wash.
   * F1 therefore shows medians only and points to F2 for per-pairing values. F2 shows every
     pairing at 1 BB/100, and the ratios are unchanged at other edges.
2. **Pairing markers.** The brief says p2 is a square and p3 a triangle; `FIGURES.md` had them
   the other way round. The brief was followed and `FIGURES.md` updated.
3. **F3 top-1% labels** use the exact core `conc_top0.01` medians rather than values read off
   the interpolated curve.
4. **F6a** adds a 0–7% zoom strip below a linear 0–72% panel, rather than using a broken or
   log axis. This keeps the valid methods legible without distorting the scale.
5. **F6b**:
   * the y axis is clipped at ±60 BB/100, which is noted in the panel;
   * an inset zooms on the final 220k blocks;
   * the x axis starts at 175 blocks so the block-204 bar clears the axis.
6. **F4a** encodes the frequency × magnitude decomposition as a log–log scatter with
   iso-product lines, not stacked bars. The product (squared deviation from big-pot blocks)
   is then readable directly.
7. **Labels.** Label placement uses a deterministic 1-D spacer, not textalloc/adjustText,
   to keep builds reproducible.

## Caveats carried into captions

* Requirements depend on the benchmark agents and reference population.
* 1 BB/100 is not equally meaningful across formats.
* Wall-clock times are specific to this implementation and machine.
* The F4 decomposition is descriptive, not causal.
* The CS coverage is asymptotic and empirical.
* The real-ordering permutations are conservative, because they sample without replacement.
