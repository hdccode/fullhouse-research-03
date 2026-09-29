"""FHR3B end to end at smoke scale: every experiment kind -> every report file."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil

from fhr3.tournament.cli import main
from fhr3.tournament.fields import FHR3B_CONFIGS


def test_pipeline_end_to_end(tmp_path, capsys):
    root = tmp_path / "res"
    # use the frozen smoke12 field for every smoke-profile field slot (skips calibration here)
    for name in ("spread", "crowded_cutoff", "style_diverse"):
        dst = root / "smoke-fields" / "nlhe6" / f"{name}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FHR3B_CONFIGS / "fields/nlhe6/smoke12.json", dst)
    common = ["--root", str(root), "--profile", "smoke", "--modes", "nlhe6"]
    for exp in ("baseline", "budget-sweep", "schedule-diagnostic", "swiss-reference"):
        assert main(["run", "--experiment", exp, *common, "--replicates", "4", "--quiet"]) == 0
    assert main(["validate", "--experiment", "baseline", *common, "--replay", "1", "--prefix", "1"]) == 0
    out = tmp_path / "rep"
    assert main(["analyse", "--root", str(root), "--profile", "smoke", "--modes", "nlhe6", "--out", str(out),
                 "--boot", "50"]) == 0
    summary = json.loads((out / "summary.json").read_text())
    status = summary["sections"]["status"]
    for f in ("baseline_reliability.csv", "qualification_probabilities.csv", "rank_stability.csv",
              "round_sweep.csv", "budget_allocation.csv", "schedule_diagnostic.csv", "pairwise_inversions.csv"):
        assert status[f] == "ok", f
    sweep = list(csv.DictReader((out / "round_sweep.csv").open()))
    assert {int(r["R_prefix"]) for r in sweep} == {1, 2, 3, 4}
    budget = list(csv.DictReader((out / "budget_allocation.csv").open()))
    assert {(r["R"], r["H"]) for r in budget} == {("1", "40"), ("2", "20"), ("4", "10")}
    assert all(r["budget_hands_per_bot"] == "40" for r in budget)
    man = json.loads((out / "MANIFEST.json").read_text())
    for rel, h in man["outputs_sha256"].items():
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == h
    assert all(i["engine_source_hash"] for i in man["inputs"])


def test_pending_operational_protocol_is_refused(capsys):
    import pytest

    with pytest.raises(SystemExit) as e:
        main(["run", "--experiment", "operational-2026", "--replicates", "1"])
    assert "PENDING" in str(e.value) and "field size" in str(e.value)


def test_publication_run_requires_explicit_count():
    import pytest

    with pytest.raises(SystemExit):
        main(["run", "--experiment", "baseline", "--root", "/nonexistent"])
