"""Empirical check that sample requirements collapse in standardized d.

For each non-control pairing, choose Delta so that the analytic two-sided z-test
has exactly 80% power at n blocks (Delta = (z_.975 + z_.8) sigma_D / sqrt(n)),
impose it as a synthetic location shift on the centred block residuals, and
measure empirical power by block resampling. Deviations from 0.80 are the
finite-sample / tail effects that normalization by sigma_D does not remove.
Resampling uses each pilot's own empirical distribution (unseen tails cannot
appear), so this is a check of the normal approximation, not new poker data.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
from scipy import stats as sps

from fhr3.analysis.stats import location_shift_power
from fhr3.io.store import read_blocks

sys.path.insert(0, str(Path(__file__).parent))
from analyze_pilots import EXPERIMENTS  # noqa: E402

NS = (500, 2000, 10000)
REPS = 1000
Z = sps.norm.ppf(0.975) + sps.norm.ppf(0.8)


def main() -> None:
    out = Path("reports/pilot-analysis/d_collapse.csv")
    rows = []
    for label, exp in EXPERIMENTS:
        t = read_blocks(Path("results") / exp, columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
        for pid in sorted(set(t.column("pairing_id").to_pylist())):
            if pid.startswith("c0-"):
                continue
            D = np.asarray(t.filter(pc.and_(pc.equal(t.column("pairing_id"), pid), t.column("valid"))).column("D")
                           .to_numpy(zero_copy_only=False), dtype=float)
            sd = D.std(ddof=1)
            for n in NS:
                delta = Z * sd / math.sqrt(n)
                res = location_shift_power(D, [delta], [n], reps=REPS, seed=7)[0]
                rows.append({"format": label, "pairing_id": pid, "n_blocks": n, "d": delta / sd,
                             "empirical_power": res["power_two_sided"], "p_select_stronger": res["p_select_stronger"],
                             "analytic_power": 0.8})
                print(f"{label:<16}{pid[:24]:<25} n={n:>6} d={delta / sd:.4f} empirical power {res['power_two_sided']:.3f}  P(correct sign) {res['p_select_stronger']:.3f}")
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
