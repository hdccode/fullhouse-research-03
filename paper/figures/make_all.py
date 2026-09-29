"""Build all six paper figures from frozen sources.

Usage (from the repo root):
    .venv-figures/bin/python paper/figures/make_all.py [--check]

Writes paper/figures/final/figure{1..6}_*.{svg,pdf,png} and final/build_manifest.json
(output sha256s, invariant checks, package versions, source-file sha256s). With --check, rebuilds
into memory-equivalent files and fails if any output hash differs from the committed manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fig1, fig2, fig3, fig4, fig5, fig6  # noqa: E401,E402
import sources  # noqa: E402
import style  # noqa: E402

FIGS = [("figure1_sample_complexity", fig1), ("figure2_cost_metrics", fig2), ("figure3_variance_concentration", fig3),
        ("figure4_big_pots_stack_depth", fig4), ("figure5_variance_reduction", fig5), ("figure6_sequential", fig6)]
SOURCE_FILES = sorted([*(sources.DATA.glob("F*.csv")),
                       sources.FA / "ranking.json", sources.FA / "core" / "pilot_table.csv", sources.FA / "allin.csv",
                       sources.FA / "stack.json", sources.R6 / "rq6_summary.csv", sources.R6 / "deep" / "rq6_deep.json",
                       sources.R7 / "coverage.csv", sources.R7 / "real_permutations.csv", sources.R7 / "real_orderings.csv",
                       sources.R7 / "deep" / "real_orderings_sign.csv"])


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if outputs differ from final/build_manifest.json")
    a = ap.parse_args()
    style.setup()
    hashes = {}
    for stem, mod in FIGS:
        hashes[stem] = mod.draw()
        print(f"{stem}: " + ", ".join(f"{k} {v[:12]}" for k, v in hashes[stem].items()))
    manifest = {
        "outputs": hashes,
        "invariant_checks_passed": sources.CHECKS,
        "n_checks": len(sources.CHECKS),
        "sources": {str(p.relative_to(sources.ROOT)): sha(p) for p in SOURCE_FILES},
        "packages": {p: md.version(p) for p in ("matplotlib", "numpy", "pandas", "scipy")},
        "python": sys.version.split()[0],
        "font": style.FONT,
        "width_mm": 183,
    }
    path = style.OUT / "build_manifest.json"
    if a.check:
        old = json.loads(path.read_text())
        bad = [f"{s}.{e}" for s in hashes for e in hashes[s] if old["outputs"].get(s, {}).get(e) != hashes[s][e]]
        print("outputs identical to manifest" if not bad else f"DIFFERENT: {bad}")
        sys.exit(1 if bad else 0)
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(sources.CHECKS)} invariant checks passed; wrote {path}")


if __name__ == "__main__":
    main()
