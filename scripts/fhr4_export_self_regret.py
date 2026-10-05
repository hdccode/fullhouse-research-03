"""FHR4 read-only export: reference_self_regret bootstrap summaries (NO simulation; stored references only).

    .venv/bin/python scripts/fhr4_export_self_regret.py

``reference_self_regret`` depends only on the reference's own joint bootstrap resamples (not on any
tournament). The frozen analysis stores its bootstrap MEAN with a PERCENTILE interval; when almost every
resample gives zero (separated_control) the mean lies outside that interval. This script rebuilds the same
resamples (same seeds, same code path as `fhr3b analyse`), asserts that the mean reproduces the stored
value, and writes the median, mean, percentile interval and zero share for reporting.

Writes reports/fhr3b/analysis-fhr4-core/exports/reference_self_regret.csv.
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
from fhr3.tournament.analysis import field_reference, reference_set, swiss_reference  # noqa: E402

ROOT = REPO / "results/fhr3b"
A = REPO / "reports/fhr3b/analysis-fhr4-core"
OUT = A / "exports/reference_self_regret.csv"
K = 6


def r6(x) -> float:
    return round(float(x), 6) + 0.0  # + 0.0 normalises -0.0 from float rounding in np.quantile


def main() -> None:
    prof = ex.load_profile("publication")
    base = {r["field_id"].replace("nlhe6-", ""): r for r in csv.DictReader((A / "baseline_reliability.csv").open())}
    rows = []
    for field in core.core_config(prof)["fields"]:
        fr = field_reference(ROOT, prof, "nlhe6", field, n_boot=1000)
        sr = swiss_reference(ROOT, prof, "nlhe6", field, n_boot=1000)
        for ref in reference_set(fr, sr, fr["bots"]):
            mu, br = ref["mu"], ref["boot"]
            top = (-mu).argsort(kind="stable").argsort() < K
            s = np.array([np.sort(r)[::-1][:K].sum() - r[top].sum() for r in br])
            stored = float(base[field][f"{ref['name']}_reference_self_regret_value"])
            assert np.isclose(s.mean(), stored, rtol=1e-4, atol=1e-6), (field, ref["name"], s.mean(), stored)
            rows.append({"field": field, "reference": ref["name"], "n_resamples": len(s),
                         "median_bb": r6(np.median(s)), "ci_lo_bb": r6(np.quantile(s, 0.025)),
                         "ci_hi_bb": r6(np.quantile(s, 0.975)), "mean_bb": r6(s.mean()),
                         "stored_mean_bb": stored, "share_zero": round(float((s <= 1e-9).mean()), 4),
                         "max_bb": r6(s.max())})
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{OUT}: {len(rows)} rows")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
