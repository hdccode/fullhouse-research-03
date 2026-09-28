"""End-to-end CLI smoke test on a tiny config (few blocks)."""

import json

import yaml

from fhr3.cli.main import main

from conftest import TINY


def test_cli_simulate_validate_analyze_replay(tmp_path, capsys):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(TINY))
    out, tr = tmp_path / "results", tmp_path / "traces"
    common = ["--config", str(cfg)]
    assert main(["simulate", *common, "--blocks", "0:8", "--out", str(out), "--traces", str(tr), "--dry-run"]) == 0
    assert not out.exists()
    assert main(["simulate", *common, "--blocks", "0:4", "--out", str(out), "--traces", str(tr)]) == 0
    # resume: second invocation extends the range and skips existing chunks
    assert main(["simulate", *common, "--blocks", "0:8", "--out", str(out), "--traces", str(tr), "--workers", "2"]) == 0
    manifests = sorted((out / "test-exp" / "runs").glob("*.json"))
    assert len(manifests) == 2
    m = json.loads(manifests[-1].read_text())
    assert m["work"]["units_already_done"] == 2 and m["summary"]["invalid"] == 0
    assert main(["validate", *common, "--out", str(out), "--blocks", "0:8", "--replay", "4"]) == 0
    capsys.readouterr()
    assert main(["analyze", str(out / "test-exp"), "--bootstrap", "100", "--json", str(tmp_path / "rep.json")]) == 0
    text = capsys.readouterr().out
    assert "sigma_D = 0: A and B played identically" in text  # self-play control
    rep = json.loads((tmp_path / "rep.json").read_text())
    assert {e["pairing_id"] for e in rep["pairings"].values()} == {"ab", "self"}
    assert main(["replay", *common, "--pairing", "ab", "--block", "5", "--compare", str(out)]) == 0
    assert "replay matches stored row exactly" in capsys.readouterr().out
    assert main(["power-sim", str(out / "test-exp" / "ab"), "--n", "10,20", "--deltas", "1", "--reps", "50"]) == 0


def test_cli_compare(tmp_path, capsys):
    import copy

    out = tmp_path / "results"
    for stack, exp in ((100, "cmp-100"), (20, "cmp-20")):
        raw = copy.deepcopy(TINY)
        raw["experiment_id"], raw["game"]["stack_bb"] = exp, stack
        cfg = tmp_path / f"{exp}.yaml"
        cfg.write_text(yaml.safe_dump(raw))
        assert main(["simulate", "--config", str(cfg), "--blocks", "0:8", "--out", str(out), "--no-traces"]) == 0
    capsys.readouterr()
    assert main(["compare", str(out / "cmp-100"), str(out / "cmp-20"), "--json", str(tmp_path / "c.json")]) == 0
    text = capsys.readouterr().out
    assert "6max/20bb" in text and "(same deals)" in text
    rep = json.loads((tmp_path / "c.json").read_text())
    assert [c["stack_bb"] for c in rep["pairings"]["ab"]["configs"]] == [20, 100]
