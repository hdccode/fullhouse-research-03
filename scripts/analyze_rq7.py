"""RQ7 analysis: collect rq7-cell outputs into the canonical tables and figure data.

Usage: .venv/bin/python scripts/analyze_rq7.py [--cells reports/rq7/cells] [--out reports/rq7]

Cell naming convention (scripts/run_rq7_final.sh): ``null-<dist>-min<k>``,
``alt-<dist>-n<N80>``, ``perm-<dist>``; <dist> in heavy / moderate / mild / normal / t3 /
nlhe6p1. Classification uses the stored design (true mean, sampler), not the name.

Outputs (reports/rq7/):
  coverage.csv             null cells at min_n = 200: miscoverage + Wilson 95% CI + MC SE
  min_n_sensitivity.csv    null cells at every min_n
  stopping.csv             non-null cells: decision / censoring / wrong-sign rates, decision-time
                           quantiles, median decision time relative to the fixed-N 80% requirement
  real_permutations.csv    permutation cells (real corpus orderings; true mean = corpus mean)
  real_orderings.csv       fhr3 sequential on each frozen corpus in block-id order
  figures/miscoverage.csv, figures/stopping_times.csv, figures/stopping_cost.csv
  summary.json             designs, seeds, versions, source-corpus fingerprints, git SHA
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path

import numpy as np
from scipy import stats as sps

from fhr3.analysis.rq7 import ENGINE_VERSION, METHODS
from fhr3.analysis.sequential import METHOD_VERSION
from fhr3.io.manifest import git_info

Z80 = sps.norm.ppf(0.975) + sps.norm.ppf(0.8)


def _w(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        if not rows:
            fh.write("")
            return
        fields = list(dict.fromkeys(k for r in rows for k in r))  # union: methods report different widths
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def dist_of(name: str) -> str:
    parts = name.split("-")
    return parts[1] if len(parts) > 1 else name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="reports/rq7/cells")
    ap.add_argument("--out", default="reports/rq7")
    ap.add_argument("--core-manifest", default="reports/final-analysis/MANIFEST.json")
    a = ap.parse_args()
    out = Path(a.out)
    cells = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(f"{a.cells}/*.json"))]
    if not cells:
        raise SystemExit(f"no cells under {a.cells}")
    cov, minn, stop, perm, figmis, figstop, figcost = [], [], [], [], [], [], []
    for c in cells:
        d, s, name = c["design"], c["summary"], c["name"]
        dist = dist_of(name)
        is_perm = d["sampler"].startswith("permutation:")
        null = d["true_mean"] == 0 and not is_perm
        for m in METHODS:
            v = s[m]
            base = {"cell": name, "distribution": dist, "sampler": d["sampler"], "method": m, "reps": v["reps"],
                    "n_max": d["n_max"], "t_star": d["t_star"], "min_n": d["min_n"], "fixed_n": d["fixed_n"],
                    "seed": d["seed"]}
            ci = v["miscoverage_wilson95"]
            cv_row = {**base, "miscoverage": v["miscoverage"], "wilson_lo": ci[0], "wilson_hi": ci[1],
                      "mc_se": v["miscoverage_mc_se"], "final_n_miscoverage": v["final_n_miscoverage"],
                      "decision_rate": v["decision_rate"]}
            if null:
                minn.append(cv_row)
                if d["min_n"] == 200:
                    cov.append(cv_row)
                figmis.append({k: cv_row[k] for k in ("distribution", "min_n", "method", "miscoverage", "wilson_lo", "wilson_hi")})
            elif is_perm:
                perm.append({**cv_row, "true_mean_block": d["true_mean"], "wrong_decision_rate": v["wrong_decision_rate"],
                             "median_decision_time": v["decision_time_quantiles"].get("0.5")})
            else:
                n80 = (Z80 / d["effect_d"]) ** 2 if d.get("effect_d") else (Z80 * d["sigma"] / d["true_mean"]) ** 2
                q = v["decision_time_quantiles"]
                row = {**base, "effect_d": d.get("effect_d"), "true_mean_block": d["true_mean"], "fixed_n_80pct": n80,
                       "decision_rate": v["decision_rate"], "censored_rate": v["censored_rate"],
                       "wrong_decision_rate": v["wrong_decision_rate"], "wrong_wilson_hi": v["wrong_decision_wilson95"][1],
                       "correct_sign_rate": v["correct_sign_rate"],
                       **{f"decision_time_q{p}": q.get(p) for p in ("0.1", "0.25", "0.5", "0.75", "0.9")},
                       "median_decision_over_fixed_n80": (q["0.5"] / n80) if q.get("0.5") else None}
                for k, val in v.items():
                    if k.startswith("median_width_at_"):
                        row[k] = val
                stop.append(row)
                figcost.append({"distribution": dist, "effect_d": d.get("effect_d"), "method": m,
                                "fixed_n_80pct": n80, "median_decision_time": q.get("0.5"),
                                "ratio": row["median_decision_over_fixed_n80"], "decision_rate": v["decision_rate"]})
                per = Path(a.cells) / c["per_replicate_csv"]
                if per.exists():
                    with per.open() as fh:
                        for r in csv.DictReader(fh):
                            if r["method"] == m:
                                figstop.append({"distribution": dist, "effect_d": d.get("effect_d"), "method": m,
                                                "rep": int(r["rep"]), "decision_time": int(r["decision_time"]),
                                                "censored": r["censored"] == "True", "fixed_n_80pct": n80})
    orderings = []
    for f in sorted(glob.glob(f"{out}/sequential-*.json")):
        for r in json.loads(Path(f).read_text()):
            orderings.append({"file": Path(f).name, **{k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
                                                       for k, v in r.items()}})
    _w(out / "coverage.csv", cov)
    _w(out / "min_n_sensitivity.csv", minn)
    _w(out / "stopping.csv", stop)
    _w(out / "real_permutations.csv", perm)
    _w(out / "real_orderings.csv", orderings)
    _w(out / "figures" / "miscoverage.csv", figmis)
    _w(out / "figures" / "stopping_times.csv", figstop)
    _w(out / "figures" / "stopping_cost.csv", figcost)
    core = json.loads(Path(a.core_manifest).read_text()) if Path(a.core_manifest).exists() else {}
    sources = {}
    for c in cells:
        smp = c["design"]["sampler"]
        if ":" in smp:
            pdir = Path(smp.split(":", 1)[1])
            fp = core.get("corpora", {}).get(pdir.parent.name, {}).get("pairings", {}).get(pdir.name)
            sources[smp] = fp or "not in core manifest"
    blockers = [f"{r['cell']} asymp miscoverage {r['miscoverage']:.3f} (Wilson lo {r['wilson_lo']:.3f} > 0.05)"
                for r in minn if r["method"] == "asymp" and r["wilson_lo"] > 0.05]
    summary = {
        "engine_version": ENGINE_VERSION, "asymp_method_version": METHOD_VERSION,
        "unit": "matched block; streams are IID block draws (bootstrap/synthetic) or corpus permutations",
        "asymptotic_note": "asymp coverage is asymptotic (finite variance), not a finite-sample guarantee",
        "git": git_info(), "cells": {c["name"]: {"design": c["design"], "design_hash": c["design_hash"],
                                                 "wall_s": c["wall_s"], "git": c["git"]} for c in cells},
        "source_corpus_fingerprints": sources,
        "flags_asymp_miscoverage_above_alpha": blockers,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n")
    print(f"{len(cells)} cells -> coverage {len(cov)}, min_n {len(minn)}, stopping {len(stop)}, "
          f"permutations {len(perm)}, orderings {len(orderings)} rows")
    for r in cov:
        print(f"  null {r['distribution']:<9} {r['method']:<5} miscoverage {r['miscoverage']:.4f} "
              f"[{r['wilson_lo']:.4f}, {r['wilson_hi']:.4f}]")
    for r in stop:
        med = r["decision_time_q0.5"]
        print(f"  alt  {r['distribution']:<9} d={r['effect_d']} {r['method']:<5} decide {r['decision_rate']:.3f} "
              f"wrong {r['wrong_decision_rate']:.4f} median n {med if med is None else f'{med:,.0f}'} "
              f"(x{r['median_decision_over_fixed_n80'] or float('nan'):.2f} of fixed N80 {r['fixed_n_80pct']:,.0f})")
    if blockers:
        print("FLAGS: " + "; ".join(blockers))


if __name__ == "__main__":
    main()
