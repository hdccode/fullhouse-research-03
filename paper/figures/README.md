# Paper figures

This directory holds the publication figures (F1–F6 from the frozen core, RQ6 and RQ7 results; F7 from the
FHR3A controlled table-size suite in `reports/table-size/`), built with Matplotlib from frozen
sources. `ARCHITECTURE.md` explains why Matplotlib was chosen, and `QA.md` records the
verification results.

## Build

Run these from the repository root. The figures use their own environment, separate from
the research `uv.lock`.

```bash
python3.12 -m venv .venv-figures
.venv-figures/bin/pip install -r paper/figures/requirements.txt
.venv-figures/bin/python paper/figures/make_all.py           # build all seven and write final/build_manifest.json
.venv-figures/bin/python paper/figures/make_all.py --check   # rebuild and fail if any output hash differs
.venv-figures/bin/python paper/figures/qa.py                 # grayscale and CVD sheets plus contact sheet in qa/
```

The build needs Arial installed; it ships with macOS. No simulation is run, and every value
is read from `paper/figures/data/` and the canonical `reports/` directories.

## Layout

| path | contents |
|---|---|
| `style.py` | the design system: sizes, fonts, palette, markers, helpers, and deterministic `save()` |
| `sources.py` | frozen-source loaders plus invariant checks; the build aborts if any check fails |
| `fig1.py` … `fig6.py` | one script per figure; each exposes `draw()` |
| `make_all.py` | builds all seven and writes `final/build_manifest.json` |
| `qa.py` | visual QA sheets |
| `final/` | `figureN_*.{svg,pdf,png}`, `captions.md`, `build_manifest.json` |
| `qa/` | per-figure colour / grayscale / protanopia / deuteranopia grids and the contact sheet |
| `prototypes/` | architecture spike: F5 in Matplotlib and in Observable Plot |

## Outputs

All outputs are 183 mm (7.20 in) wide:
* SVG with editable `<text>`, in Arial;
* PDF with embedded TrueType fonts;
* 600-dpi RGB PNG, for Google Docs.

In Google Docs, insert the PNG at full text width.
