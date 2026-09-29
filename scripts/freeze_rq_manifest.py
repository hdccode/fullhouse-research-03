"""Freeze manifests for the RQ6 and RQ7 results (separate from the core
reports/final-analysis/MANIFEST.json, which is never touched here).

Usage:
  .venv/bin/python scripts/freeze_rq_manifest.py rq6 [--verify]   # reports/rq6/MANIFEST.json
  .venv/bin/python scripts/freeze_rq_manifest.py rq7 [--verify]   # reports/rq7/MANIFEST.json

rq6 records, per estimator experiment and its frozen raw reference: config hash, estimator
config hash + provenance (method / PVAT versions, RNG derivation, settings) from the lock,
value-function artifact sha256 + training root seed, Parquet fingerprints, run manifests
(git SHA), and sha256 of every RQ6 output. rq7 records every cell's design (sampler, seed,
reps, horizon, t*, min_n, fixed_n) and design hash, the Parquet fingerprints of every
source pairing corpus, and sha256 of every RQ7 output.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from freeze_manifest import git_sha, sha256  # noqa: E402

import pyarrow.parquet as pq  # noqa: E402

RQ6 = [  # (estimator experiment, frozen raw reference)
    ("results/fhr3-nlhe6-100bb-rq6-v1-fittedvf", "results/fhr3-nlhe6-100bb-pilot-v1"),
    ("results/fhr3-nlhe6-20bb-rq6-allin-v1", "results/fhr3-nlhe6-20bb-v1"),
    ("results/fhr3-aof4-8bb-rq6-allin-v1", "results/fhr3-aof4-8bb-pilot-v1"),
]
RQ6_COMMANDS = ["scripts/run_rq6_final.sh (expanded in docs/workflow.md)", "scripts/analyze_rq6.sh"]
RQ7_COMMANDS = ["scripts/run_rq7_final.sh (expanded in docs/workflow.md)", "scripts/analyze_rq7.sh"]


def pairing_fingerprint(pdir: Path) -> dict:
    import hashlib

    files = sorted((pdir / "blocks").glob("blocks_*.parquet"))
    h, rows = hashlib.sha256(), 0
    for f in files:
        h.update(f"{f.name}:{sha256(f)}\n".encode())
        rows += pq.ParquetFile(f).metadata.num_rows
    lock = json.loads((pdir / "pairing.lock.json").read_text())
    return {"pairing_hash": lock["pairing_hash"], "rows": rows, "chunks": len(files), "parquet_sha256": h.hexdigest()}


def experiment_record(d: Path) -> dict:
    lock = json.loads((d / "experiment.lock.json").read_text())
    runs = {}
    for f in sorted((d / "runs").glob("*.json")):
        m = json.loads(f.read_text())
        runs[m["run_id"]] = {"git": m["git"], "command": m["command"][1:], "config_hash": m["config_hash"],
                             "estimator_config_hash": m.get("estimator_config_hash")}
    rec = {"config_hash": lock["config_hash"], "root_seed": lock["environment"]["root_seed"],
           "schema_version": lock["schema_version"], "estimators": lock.get("estimators"),
           "estimator_config_hash": lock.get("estimator_config_hash"),
           "estimator_provenance": lock.get("estimator_provenance"), "runs": runs,
           "pairings": {p.name: pairing_fingerprint(p) for p in sorted(d.iterdir()) if (p / "pairing.lock.json").exists()}}
    vfs = {}
    for name, opts in (lock.get("estimators") or {}).items():
        vf = (opts or {}).get("value_function")
        if vf and vf != "prior":
            meta = json.loads(Path(vf).read_text())
            vfs[name] = {"path": vf, "sha256": sha256(Path(vf)), "pinned_sha256": opts.get("value_function_sha256"),
                         "training_root_seed": meta.get("training_root_seed"), "blocks": meta.get("blocks"),
                         "n_hand_histories": meta.get("n_hand_histories"), "pvat_version": meta.get("pvat_version")}
    rec["value_functions"] = vfs
    return rec


def outputs(root: Path, patterns: list[str]) -> dict:
    files = sorted({f for p in patterns for f in glob.glob(str(root / p), recursive=True)})
    return {str(Path(f).relative_to(root)): sha256(Path(f)) for f in files if Path(f).is_file() and "MANIFEST" not in f}


def build(target: str, root: Path, results: Path) -> dict:
    if target == "rq6":
        return {"target": "rq6", "analysis_code_git_sha": git_sha(), "commands": RQ6_COMMANDS,
                "experiments": {Path(e).name: {"estimator_experiment": experiment_record(results / Path(e).name),
                                               "reference": Path(r).name,
                                               "reference_config_hash": json.loads((Path(r) / "experiment.lock.json").read_text())["config_hash"]}
                                for e, r in RQ6},
                "outputs": outputs(root, ["*.csv", "*.json", "*.txt", "figures/*.csv"])}
    cells = {json.loads(Path(f).read_text())["name"]: json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(root / "cells" / "*.json")))}
    sources = {}
    for c in cells.values():
        smp = c["design"]["sampler"]
        if ":" in smp and smp not in sources:
            sources[smp] = pairing_fingerprint(Path(smp.split(":", 1)[1]))
    return {"target": "rq7", "analysis_code_git_sha": git_sha(), "commands": RQ7_COMMANDS,
            "cells": {n: {"design": c["design"], "design_hash": c["design_hash"], "git": c["git"]} for n, c in cells.items()},
            "source_corpora": sources,
            "outputs": outputs(root, ["*.csv", "*.json", "figures/*.csv", "cells/*.json", "cells/*.csv"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", choices=["rq6", "rq7"])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--reports", help="reports directory (default reports/<target>)")
    ap.add_argument("--results", default="results", help="results root holding the RQ6 estimator experiments")
    a = ap.parse_args()
    root = Path(a.reports or f"reports/{a.target}")
    path = root / "MANIFEST.json"
    cur = build(a.target, root, Path(a.results))
    if a.verify:
        old = json.loads(path.read_text())
        keys = ["outputs", "experiments"] if a.target == "rq6" else ["outputs", "cells", "source_corpora"]
        bad = [k for k in keys if old.get(k) != cur.get(k)]
        print(f"{path} verified" if not bad else f"DRIFT in {bad}")
        sys.exit(1 if bad else 0)
    path.write_text(json.dumps(cur, indent=1, default=str) + "\n")
    print(f"wrote {path} ({len(cur['outputs'])} outputs)")


if __name__ == "__main__":
    main()
