# FullHouse Research #4: publication package

Everything here is built from stored, frozen results (simulation freeze at `db45b56`). No simulation was
run to produce it.

| item | path | produced by |
|---|---|---|
| per-tournament errors, per-cell P(qualify) | `reports/fhr3b/analysis-fhr4-core/exports/` | `.venv/bin/python scripts/fhr4_export_tournament_errors.py` (reads stored tournaments only) |
| Figures 1 to 5, S1 (PDF, SVG, 600-dpi PNG) | `figures/` | `.venv-figures/bin/python scripts/fhr4_publication.py` |
| exact plotted values | `figures/data/*.csv` | same |
| checksums | `figures/SHA256SUMS.json` | same |
| draft captions | `figures/CAPTIONS.md` | hand-written from the plotted values |
| Tables 1 to 3 | `TABLES.md`, `tables/*.csv` | `scripts/fhr4_publication.py` |
| manuscript skeleton | `OUTLINE.md` | hand-written |

Analysis inputs: `reports/fhr3b/analysis-fhr4-core/` (MATRIX_AUDIT.md, MU_SWISS_AUDIT.md) and
`reports/fhr3b/field-calibration/nlhe6/`.
