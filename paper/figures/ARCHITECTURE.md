# Figure architecture: spike and decision

**Decision: bespoke Matplotlib**, with one shared design module (`style.py`) and one
frozen-source layer (`sources.py`). It was chosen on the evidence of two rendered prototypes,
not by default.

## Deliverable the choice was judged against
The deliverable is six static scientific figures at 183 mm width. They need:
* multi-panel layouts and small multiples;
* confidence intervals, ribbons and forest plots;
* log scales and reference lines;
* direct labels with collision control;
* editable-text SVG, PDF and 600-dpi PNG (for Google Docs);
* 6–7 pt type at final size;
* byte-deterministic rebuilds;
* long-term maintainability in a Python research repo.

## Options considered

| option | what it is | verdict |
|---|---|---|
| **Matplotlib** (bespoke) | the Python plotting core; full control of every artist | **chosen**, see below |
| **Observable Plot** (browser/SVG) | concise grammar with excellent defaults; JS; SVG output | **prototyped**; strong look, weak static/print pipeline |
| **Altair / Vega-Lite** | declarative JSON grammar; `vl-convert` gives SVG/PDF/PNG without a browser | not prototyped: annotation, inset and small-multiple control is weaker than Plot's, and its strengths (interactivity, declarative specs) are not needed |
| D3 | low-level SVG toolkit | every axis, legend and layout hand-built; highest cost for no gain over Plot |
| Recharts / Nivo | React chart components | dashboard components rendered in a browser; no print pipeline, no log-scale forest plots out of the box |
| Tremor / shadcn/ui charts | React component systems around Recharts | presentation layers for data products, not statistical rendering engines; wrong genre for print figures |
| plotnine / SciencePlots / UltraPlot | ggplot grammar / Matplotlib style sheets / Matplotlib convenience layer | all end in Matplotlib; a style sheet adds nothing the shared design module does not |

## Prototypes: F5 at final size in both finalists

The prototype files are in `prototypes/`:
* `proto_f5_matplotlib.py` → `proto_f5_matplotlib.{png,svg,pdf}`;
* `observable/proto_f5_plot.mjs` → `proto_f5_observable.{png,svg}` (Plot 0.6.17 + jsdom 30.1.1 + resvg-js 2.6.2).

### Observable Plot

**Strengths:** attractive defaults, a concise grammar, and SVG text. Small multiples via
`fx`/`fy` are good.

**Weaknesses found in the render:**
* Headless jsdom has no text measurement, so Plot cannot size margins or avoid label
  collisions. Every margin and label offset is a manual guess.
* Numeric y domains were inferred as ordinal. An `axisY` mark silently replaced the
  scale's `tickFormat`, so the row labels rendered as 0–4. A `tickX` mark forced a band
  scale.
* Symbol sizes are not area-matched: the triangle rendered visibly larger than the circle.
* Multi-panel figures require hand-composing SVG strings.
* There is no PDF path without adding a headless browser. resvg gives PNG only.
* Sizes are in CSS px, so point-accurate print typography needs manual conversion.

### Matplotlib

**Strengths:**
* Exact physical sizing in inches and points.
* Measurable text extents, which enable deterministic label placement.
* Native SVG (text kept as `<text>`), PDF (TrueType Type 42) and 600-dpi PNG from one
  figure object.
* Insets, gridspecs and shared axes.
* Metadata control makes byte-identical rebuilds possible.
* One stack reads the same frozen CSVs as the analysis.

**Weaknesses:** the defaults are generic and need a design layer. That is what
`style.py` provides.

## Decision details
* **Label placement.** `textalloc`/`adjustText` were evaluated. The final figures instead use
  a deterministic 1-D label spacer (`style.spread_labels`, order-preserving least
  displacement) plus explicit anchors checked visually. This avoids stochastic placement
  and keeps rebuilds byte-identical, so neither library is a dependency.
* **Palette.** The dataviz-skill reference palette, 7 slots, validated with its
  `validate_palette.js` in light mode:
  * lightness band pass;
  * chroma floor pass;
  * adjacent CVD ΔE ≥ 8 (worst 9.1);
  * normal-vision ≥ 15 (worst 19.6);
  * three slots below 3:1 contrast, which is relieved by direct labels and marker shapes.

  Okabe-Ito and Paul Tol muted and bright failed the lightness band on white for thin marks.
* **Environment.** A separate `.venv-figures` (`requirements.txt`); the research `uv.lock`
  is untouched.
