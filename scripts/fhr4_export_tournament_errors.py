"""FHR4 read-only exports for the publication package (NO simulation; reads stored tournaments only).

    .venv/bin/python scripts/fhr4_export_tournament_errors.py

Writes reports/fhr3b/analysis-fhr4-core/exports/:

* tournament_errors.csv: one row per stored tournament for every core matrix cell (18 x 50) and
  every mu_swiss tournament (3 x 200). Columns: wrong qualifiers against the mu_field reference
  point top 6, qualification regret and boundary strength loss (BB per ordinary-equivalent
  400-hand match, mu_field point estimate), and how many wrong qualifiers are inside the
  mu_field reference-ambiguous set (5% < P(reference top 6) < 95%) vs clearly outside it.
* qualification_probabilities_all_cells.csv: per-bot P(qualify) with Wilson 95% intervals for
  every core matrix cell and the 200-tournament mu_swiss reference, with the mu_field rank.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from fhr3.tournament import core  # noqa: E402
from fhr3.tournament import experiments as ex  # noqa: E402
from fhr3.tournament import metrics as mt  # noqa: E402
from fhr3.tournament.analysis import field_reference  # noqa: E402
from fhr3.tournament.store import completed_replicates, load_cell_arrays  # noqa: E402

ROOT = REPO / "results/fhr3b"
OUT = REPO / "reports/fhr3b/analysis-fhr4-core/exports"
K = 6
CELL_LABEL = {"baseline": "R40H400 adaptive", "budget_half_rounds": "R20H800", "budget_quarter_rounds": "R10H1600",
              "frozen_schedule": "R40H400 frozen schedule", "dup_fewer_rounds": "R7H400 x6 duplicate",
              "dup_shorter_matches": "R40H67 x6 duplicate", "mu_swiss": "R40H400 adaptive (mu_swiss reference)"}


def main() -> None:
    prof = ex.load_profile("publication")
    OUT.mkdir(parents=True, exist_ok=True)
    err_rows, pq_rows = [], []
    for field in core.core_config(prof)["fields"]:
        fr = field_reference(ROOT, prof, "nlhe6", field, n_boot=1000)
        bots = fr["bots"]
        mu = np.asarray(fr["mu"]) / 100.0
        p_ref = np.asarray(fr["p_top_k"])
        rank = (-mu).argsort(kind="stable").argsort() + 1
        top = rank <= K
        amb = (p_ref > 0.05) & (p_ref < 0.95)
        cells = [(cc.key, cc.cell) for cc in core.core_cells(prof, [field])]
        cells.append(("mu_swiss", prof.swiss_reference_cell("nlhe6", field)))
        for key, cell in cells:
            reps = completed_replicates(ROOT, cell, verify=False)
            a = load_cell_arrays(ROOT, cell, reps)
            assert list(a["bots"]) == list(bots)
            q = a["qualified"]
            wrong = q & ~top[None, :]
            regret = mt.qualification_regret(q, mu, K)
            loss = mt.boundary_strength_loss(q, mu)
            for i, rep in enumerate(reps):
                err_rows.append({"field": field, "cell": key, "cell_label": CELL_LABEL[key], "cell_id": cell.cell_id,
                                 "replicate": rep, "wrong_vs_mu_field": int(wrong[i].sum()),
                                 "wrong_in_reference_ambiguous_set": int((wrong[i] & amb).sum()),
                                 "wrong_clearly_outside": int((wrong[i] & ~amb).sum()),
                                 "qualification_regret_bb": round(float(regret[i]), 4),
                                 "boundary_strength_loss_bb": round(float(loss[i]), 4)})
            n = q.shape[0]
            k = q.sum(0)
            lo, hi = mt.wilson_interval(k, n)
            for j, b in enumerate(bots):
                pq_rows.append({"field": field, "cell": key, "cell_label": CELL_LABEL[key], "bot_id": b,
                                "mu_field_bb": round(float(mu[j]), 4), "mu_field_rank": int(rank[j]),
                                "p_reference_top6": round(float(p_ref[j]), 4), "n_tournaments": n,
                                "p_qualify": round(float(k[j] / n), 4), "wilson_lo": round(float(lo[j]), 4),
                                "wilson_hi": round(float(hi[j]), 4)})
    for name, rows in (("tournament_errors.csv", err_rows), ("qualification_probabilities_all_cells.csv", pq_rows)):
        with (OUT / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"{OUT / name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
