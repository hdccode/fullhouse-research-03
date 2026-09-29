"""Structural integrity of every block corpus under results/ (reads Parquet + locks + manifests).

Usage: .venv/bin/python scripts/integrity_check.py [--out reports/final-analysis/integrity.json]

Per (experiment, pairing): row count, contiguous block ids from 0 without
duplicates, invalid rows, NaN D, config hash == experiment lock, pairing hash ==
pairing lock, experiment_id, schema, one agent version per role, a manifest for
every run id (with its git SHA), and exact D == 0 for self-play controls.
Also checks that a re-run experiment reproduces D of its predecessor exactly on
the common block ids (REPRODUCTIONS). Exits non-zero on any failure.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.compute as pc

from fhr3.io.store import read_blocks

# (re-run experiment, original experiment): D must agree exactly on common block ids
REPRODUCTIONS = [("fhr3-nlhe4-100bb-v2", "fhr3-nlhe4-100bb-pilot-v1")]
COLS = ["config_hash", "pairing_id", "pairing_hash", "block_id", "valid", "run_id", "schema_version", "experiment_id",
        "candidate_a_version", "candidate_b_version", "reference_version", "D"]


def check_experiment(exp: Path) -> list[dict]:
    t = read_blocks(exp, columns=COLS)  # raises on duplicate (config_hash, pairing_id, block_id)
    runs = {}
    for f in glob.glob(f"{exp}/runs/*.json"):
        m = json.load(open(f))
        runs[m["run_id"]] = m["git"]["sha"][:8] + ("-dirty" if m["git"]["dirty"] else "")
    locks = {p.parent.name: json.load(open(p))["pairing_hash"] for p in exp.glob("*/pairing.lock.json")}
    elock = json.load(open(exp / "experiment.lock.json"))["config_hash"]
    rows = []
    for pid in sorted(set(t.column("pairing_id").to_pylist())):
        tp = t.filter(pc.equal(t.column("pairing_id"), pid))
        b = np.sort(tp.column("block_id").to_numpy())
        uniq = lambda c: sorted(set(tp.column(c).to_pylist()))  # noqa: E731
        D = tp.column("D").to_numpy(zero_copy_only=False).astype(float)
        r = {"experiment_id": exp.name, "pairing_id": pid, "rows": int(b.size), "first": int(b[0]), "last": int(b[-1]),
             "contiguous_from_0": bool(b[0] == 0 and b[-1] + 1 == b.size and np.unique(b).size == b.size),
             "invalid": int((~tp.column("valid").to_numpy(zero_copy_only=False)).sum()),
             "nan_D": int(np.isnan(D).sum()), "config_hash": uniq("config_hash"),
             "config_hash_matches_lock": uniq("config_hash") == [elock],
             "pairing_hash_matches_lock": uniq("pairing_hash") == [locks.get(pid)],
             "experiment_id_matches_dir": uniq("experiment_id") == [exp.name], "schema": uniq("schema_version"),
             "one_version_per_role": all(len(uniq(c)) == 1 for c in ("candidate_a_version", "candidate_b_version", "reference_version")),
             "runs": {rid: {"git": runs.get(rid, "MISSING"), "rows": int(pc.sum(pc.equal(tp.column("run_id"), rid)).as_py())}
                      for rid in uniq("run_id")}}
        r["all_runs_have_manifest"] = all(v["git"] != "MISSING" for v in r["runs"].values())
        if pid.startswith("c0-"):
            r["control_exact_zero"] = bool(np.all(D == 0))
        r["ok"] = all(r[k] for k in ("contiguous_from_0", "config_hash_matches_lock", "pairing_hash_matches_lock",
                                     "experiment_id_matches_dir", "one_version_per_role", "all_runs_have_manifest")) \
            and r["invalid"] == 0 and r["nan_D"] == 0 and r.get("control_exact_zero", True)
        rows.append(r)
    return rows


def check_reproduction(new: str, old: str) -> list[dict]:
    cols = ["config_hash", "pairing_id", "block_id", "D"]
    tn, to = read_blocks(Path("results") / new, columns=cols), read_blocks(Path("results") / old, columns=cols)
    out = []
    for pid in sorted(set(to.column("pairing_id").to_pylist())):
        get = lambda t: dict(zip(t.filter(pc.equal(t.column("pairing_id"), pid)).column("block_id").to_pylist(),  # noqa: E731
                                 t.filter(pc.equal(t.column("pairing_id"), pid)).column("D").to_pylist(), strict=True))
        a, b = get(tn), get(to)
        common = sorted(set(a) & set(b))
        mism = sum(a[i] != b[i] for i in common)
        out.append({"new": new, "old": old, "pairing_id": pid, "common_blocks": len(common), "mismatches": mism,
                    "max_abs_diff": max((abs(a[i] - b[i]) for i in common), default=0.0), "ok": bool(common) and mism == 0})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/final-analysis/integrity.json")
    a = ap.parse_args()
    corpora = [r for e in sorted(Path("results").glob("fhr3-*")) for r in check_experiment(e)]
    repro = [r for n, o in REPRODUCTIONS if (Path("results") / n).is_dir() for r in check_reproduction(n, o)]
    for r in corpora:
        print(f"[{'OK' if r['ok'] else 'FAIL'}] {r['experiment_id']:<28} {r['pairing_id']:<26} {r['rows']:>7} rows "
              f"schema {','.join(r['schema'])} runs {[v['git'] for v in r['runs'].values()]}")
    for r in repro:
        print(f"[{'OK' if r['ok'] else 'FAIL'}] reproduce {r['old']} -> {r['new']} {r['pairing_id']}: "
              f"{r['common_blocks']} common blocks, {r['mismatches']} D mismatches")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"corpora": corpora, "reproductions": repro}, indent=1))
    sys.exit(0 if all(r["ok"] for r in corpora + repro) else 1)


if __name__ == "__main__":
    main()
