# paper/: research handoff for completing the FHR3 manuscript

EMPIRICAL RESEARCH COMPLETE (2026-09-29). These files organize the frozen evidence. None of
them is manuscript prose.

**Framing and scope (FHR3A): read `FHR3A_SCOPE.md` first.** FHR3A is a controlled
empirical study of how poker format, table size, stack depth and betting structure affect the
concentration, magnitude and removability of evaluation variance. It is not the FullHouse
Swiss ranking experiment. One targeted extension, the NLHE 100BB table-size sweep
(3/4/6/8 seats), is set up but its two new runs are pending (`../docs/table_size.md`). The
frozen evidence below is unchanged.

| file | what it is |
|---|---|
| `FHR3A_SCOPE.md` | framing: controlled populations, conditional numbers, the table-size extension, not Swiss ranking |
| `CLAIMS.md` | the frozen claim set (C1–C14): wording, values, source field, uncertainty, caveat, figure, status |
| `NUMBERS.md` / `numbers.json` | every number with its frozen source (generated: `scripts/paper_numbers.py`) |
| `EVIDENCE_MAP.md` | synthesis, section-by-section map, transitions, tension reconciliations, contributions, recommendations, terminology, appendix package, reproducibility |
| `FIGURES.md` | six main figures and the table specifications |
| `figures/data/` | figure-ready CSVs + SHA256SUMS (generated: `scripts/paper_figure_data.py`) |
| `LIMITATIONS.md` | limitations, with what each affects and what survives |
| `REFERENCES.md` | citation handoff with verification status |
| `DRAFT_REVISION_NOTES.md` | search-and-fix checklist (the draft is not in the repo) |

Regenerate and check:

    .venv/bin/python scripts/freeze_manifest.py --verify
    .venv/bin/python scripts/freeze_rq_manifest.py rq6 --verify
    .venv/bin/python scripts/freeze_rq_manifest.py rq7 --verify
    .venv/bin/python scripts/paper_numbers.py
    .venv/bin/python scripts/paper_figure_data.py
