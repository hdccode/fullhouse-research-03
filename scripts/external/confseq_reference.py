"""Generate tests/data/confseq_normal_mixture_reference.json with the external confseq oracle.

Runs OUTSIDE the project environment, in an isolated Python 3.10 venv that has the
prebuilt confseq 0.0.9 wheel (confseq has no wheels for Python >= 3.11 and its
source build needs Boost + CMake):

    uv venv --python 3.10 /tmp/cs310
    VIRTUAL_ENV=/tmp/cs310 uv pip install "confseq==0.0.9" "numpy<2"
    /tmp/cs310/bin/python scripts/external/confseq_reference.py > tests/data/confseq_normal_mixture_reference.json

Only numpy + confseq are imported. The FHR3 test suite compares
fhr3.analysis.sequential.asymp_radius against these values (tests/test_rq7.py).
"""

import importlib.metadata
import json
import sys

import numpy as np
from confseq import boundaries

cases = []
for alpha in (0.05, 0.01):
    for t_star in (1_000.0, 100_000.0):
        for v in (50.0, 200.0, 1_000.0, 10_000.0, 100_000.0, 250_000.0, 1_000_000.0):
            # two-sided normal mixture bound on S_t at intrinsic time V_t = v (unit variance),
            # optimised at v_opt = t_star with alpha_opt = alpha
            b = float(boundaries.normal_mixture_bound(v, alpha, t_star, alpha, False))
            cases.append({"v": v, "alpha": alpha, "v_opt": t_star, "alpha_opt": alpha, "two_sided": True, "bound": b})
json.dump({
    "source": "gostevehoward/confseq, PyPI wheel confseq==" + importlib.metadata.version("confseq"),
    "function": "confseq.boundaries.normal_mixture_bound(v, alpha, v_opt, alpha_opt, is_one_sided=False)",
    "python": sys.version.split()[0],
    "cases": cases,
}, sys.stdout, indent=1)
print()
