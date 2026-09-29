"""Verify the frozen value function of an evaluation config before simulating with it.

Usage: .venv/bin/python scripts/verify_value_function.py configs/rq6/nlhe_6max_100bb_fitted.yaml

Builds the configured estimators exactly as the simulator does, which refuses a
value-function file whose sha256 differs from the pinned value or that was trained on the
evaluation root seed; then prints the artifact's provenance. Exit 1 on any problem.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from fhr3.configs.experiment import load_config
from fhr3.estimators import build_estimators
from fhr3.games import make_adapter


def main() -> None:
    cfg = load_config(sys.argv[1])
    try:
        build_estimators(cfg.estimators, make_adapter(cfg.game), cfg.root_seed)
    except ValueError as e:
        raise SystemExit(f"REFUSED: {e}") from None
    seen = False
    for name, opts in cfg.estimators.items():
        vf = (opts or {}).get("value_function")
        if not vf or vf == "prior":
            continue
        seen = True
        raw = Path(vf).read_bytes()
        meta = json.loads(raw)
        print(f"{name}: {vf} sha256 {hashlib.sha256(raw).hexdigest()} (pinned {opts['value_function_sha256']})")
        print(f"  training root seed {meta['training_root_seed']} != evaluation root seed {cfg.root_seed}; "
              f"training blocks {meta['blocks']} of {meta['pairings']}; {meta['n_hand_histories']} hand histories")
        print(f"  features {meta['feature_version']}, method {meta.get('method_version')}, PVAT {meta.get('pvat_version')}, "
              f"in-sample per-hand variance {meta['in_sample_per_hand_variance']}")
    if not seen:
        raise SystemExit("no fitted value function in this config")
    print(f"OK: experiment {cfg.experiment_id}, estimator_config_hash {cfg.estimator_config_hash}")


if __name__ == "__main__":
    main()
