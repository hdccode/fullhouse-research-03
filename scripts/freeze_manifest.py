"""Freeze manifest for the final core analysis: which corpora and which outputs the
paper's numbers come from, with checksums.

Usage:
  .venv/bin/python scripts/freeze_manifest.py            # write reports/final-analysis/MANIFEST.json
  .venv/bin/python scripts/freeze_manifest.py --verify   # recompute and compare; exit 1 on any drift

Corpus fingerprint per (experiment, pairing): row count, block-id range, config /
pairing hash, and sha256 over the sorted (file name, file sha256) list of its
Parquet chunks. Output checksums cover FROZEN_OUTPUTS under reports/final-analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path("reports/final-analysis")
MANIFEST = ROOT / "MANIFEST.json"
# the experiments behind the final analysis (largest valid corpus per format)
CORE_EXPERIMENTS = [
    "fhr3-aof4-8bb-pilot-v1", "fhr3-nlhe4-100bb-v2", "fhr3-nlhe6-20bb-v1", "fhr3-nlhe6-50bb-v1",
    "fhr3-nlhe6-100bb-pilot-v1", "fhr3-cp6-100bb-pilot-v1", "fhr3-plo6-100bb-pilot-v1",
    "fhr3-bomb6-100bb-pilot-v1", "fhr3-nit6-100bb-pilot-v1",
]
FROZEN_OUTPUTS = [
    "core/pilot_table.csv", "core/pilot_analysis.json", "final_tables.md", "convergence.csv", "ranking.json",
    "allin.csv", "allin_regression.json", "stack.json", "nit.json", "windows.csv", "d_collapse.csv",
    "integrity.json", "cross-format-compare.json", "cross-format-compare.txt",
    "figures/sigma_by_format_pairing.csv", "figures/hands_vs_effect.csv", "figures/blocks_vs_d.csv",
    "figures/empirical_power.csv", "figures/stack_sensitivity.csv", "figures/variance_concentration.csv",
    "figures/variance_reduction.csv", "figures/cost_translation.csv", "figures/relations.csv",
]
COMMANDS = [
    ".venv/bin/python scripts/integrity_check.py",
    ".venv/bin/python scripts/analyze_pilots.py --out reports/final-analysis/core --boot 1000",
    ".venv/bin/python scripts/final_analysis.py --boot 1000",
    ".venv/bin/python scripts/d_collapse_check.py --out reports/final-analysis/d_collapse.csv --reps 4000",
    ".venv/bin/python scripts/final_tables.py",
    ".venv/bin/fhr3 compare <CORE_EXPERIMENTS as results/...> --json reports/final-analysis/cross-format-compare.json",
    ".venv/bin/fhr3 figures <CORE_EXPERIMENTS as results/...> --powersim reports/nlhe6-100bb-ref250k-powersim.json "
    "--out reports/final-analysis/figures --workers 8",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_fingerprints() -> dict:
    out = {}
    for exp in CORE_EXPERIMENTS:
        d = Path("results") / exp
        lock = json.loads((d / "experiment.lock.json").read_text())
        pairings = {}
        for pdir in sorted(p for p in d.iterdir() if (p / "pairing.lock.json").exists()):
            files = sorted((pdir / "blocks").glob("blocks_*.parquet"))
            h = hashlib.sha256()
            rows = 0
            for f in files:
                h.update(f"{f.name}:{sha256(f)}\n".encode())
                rows += pq.ParquetFile(f).metadata.num_rows
            pairings[pdir.name] = {
                "pairing_hash": json.loads((pdir / "pairing.lock.json").read_text())["pairing_hash"],
                "rows": rows, "chunks": len(files),
                "first_chunk": files[0].name if files else None, "last_chunk": files[-1].name if files else None,
                "parquet_sha256": h.hexdigest(),
            }
        runs = sorted(json.loads(f.read_text())["run_id"] for f in (d / "runs").glob("*.json"))
        out[exp] = {"config_hash": lock["config_hash"], "schema_version": lock["schema_version"],
                    "runs": runs, "pairings": pairings}
    return out


def outputs() -> dict:
    return {p: sha256(ROOT / p) for p in FROZEN_OUTPUTS}


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    current = {"corpora": corpus_fingerprints(), "outputs": outputs()}
    if a.verify:
        frozen = json.loads(MANIFEST.read_text())
        bad = [f"corpus {e}" for e in frozen["corpora"] if frozen["corpora"][e] != current["corpora"].get(e)]
        bad += [f"output {p}" for p in frozen["outputs"] if frozen["outputs"][p] != current["outputs"].get(p)]
        print("MANIFEST verified" if not bad else "DRIFT: " + ", ".join(bad))
        sys.exit(1 if bad else 0)
    MANIFEST.write_text(json.dumps({
        "description": "Final core raw-simulation analysis (frozen for writing). Numbers cited in the paper "
                       "must come from these outputs.",
        "analysis_code_git_sha": git_sha(), "commands": COMMANDS, "core_experiments": CORE_EXPERIMENTS,
        "superseded": {"fhr3-nlhe4-100bb-pilot-v1": "v1 10k corpus; reproduced exactly by blocks 0..9999 of "
                                                   "fhr3-nlhe4-100bb-v2 (integrity.json reproductions)"},
        **current}, indent=1) + "\n")
    print(f"wrote {MANIFEST}")


if __name__ == "__main__":
    main()
