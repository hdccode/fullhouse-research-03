"""How typical is the naive-peeking failure? Permutation study on a block corpus.

Each random permutation of a pairing's blocks is an exchangeable stream whose
true mean is exactly the corpus mean mu. For each stream we apply the stopping
rule "stop at the first n >= min_n where the interval excludes 0" with
  * peek:  the fixed-N t-interval recomputed after every block (invalid)
  * asymp: the asymptotic confidence sequence (analysis.sequential)
and record whether it stopped, when, the sign of the decision, and whether the
interval at stopping excludes mu (an error for a confidence procedure).
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np
import pyarrow.compute as pc
from scipy import stats as sps

from fhr3.analysis.sequential import asymp_radius, running_mean_sd
from fhr3.io.store import read_blocks

EXP = sys.argv[1] if len(sys.argv) > 1 else "results/fhr3-nlhe6-100bb-pilot-v1"
R, MIN_N, BATCH = int(sys.argv[2]) if len(sys.argv) > 2 else 100, 200, 5


def main() -> None:
    t = read_blocks(EXP, columns=["config_hash", "pairing_id", "block_id", "valid", "D"])
    out = {}
    for pid in sorted(set(t.column("pairing_id").to_pylist())):
        if pid.startswith("c0-"):
            continue
        D = np.asarray(t.filter(pc.and_(pc.equal(t.column("pairing_id"), pid), t.column("valid"))).column("D")
                       .to_numpy(zero_copy_only=False), dtype=float)
        n, mu = D.size, float(D.mean())
        rng = np.random.default_rng(11)
        res = {m: {"stopped": 0, "err_at_stop": 0, "wrong_sign": 0, "stops": []} for m in ("peek", "asymp")}
        for start in range(0, R, BATCH):
            m_ = min(BATCH, R - start)
            X = np.stack([D[rng.permutation(n)] for _ in range(m_)])
            tt, mean, sd = running_mean_sd(X)
            rad = {"peek": sps.t.ppf(0.975, np.maximum(tt - 1, 1)) * sd / np.sqrt(tt),
                   "asymp": asymp_radius(tt, sd, 0.05, n)}
            for meth, r_ in rad.items():
                lo, hi = (mean - r_)[:, MIN_N - 1:], (mean + r_)[:, MIN_N - 1:]
                ex = (lo > 0) | (hi < 0)
                for j in range(m_):
                    if ex[j].any():
                        i = int(ex[j].argmax())
                        res[meth]["stopped"] += 1
                        res[meth]["stops"].append(i + MIN_N)
                        res[meth]["err_at_stop"] += int(lo[j, i] > mu or hi[j, i] < mu)
                        res[meth]["wrong_sign"] += int(np.sign(mean[j, i + MIN_N - 1]) != np.sign(mu))
        summ = {}
        for meth, v in res.items():
            s = np.array(v["stops"]) if v["stops"] else np.array([np.nan])
            summ[meth] = {"stop_rate": v["stopped"] / R, "interval_excludes_true_mean_at_stop": v["err_at_stop"] / R,
                          "wrong_sign_rate": v["wrong_sign"] / R, "median_stop": float(np.nanmedian(s)),
                          "q10_stop": float(np.nanquantile(s, 0.1))}
        full_z = mu / (D.std(ddof=1) / math.sqrt(n))
        out[pid] = {"n": n, "true_mean_block": mu, "full_sample_z": full_z, "reps": R, **summ}
        print(pid, json.dumps(out[pid]))
    json.dump(out, open("reports/pilot-analysis/peeking_permutation.json", "w"), indent=1)


if __name__ == "__main__":
    main()
