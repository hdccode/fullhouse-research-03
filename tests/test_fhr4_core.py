"""FullHouse Research #4 core scope (NLHE6 only): cells, budgets, append-only extensions, guards.

Everything here is cheap: publication cells are only constructed and planned, never run; the
runs use the smoke profile (12 bots, 4 rounds, 10-hand matches) in a temporary root.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml

from fhr3.tournament import core
from fhr3.tournament.batch import run_cell
from fhr3.tournament.cli import main
from fhr3.tournament.experiments import load_matrix, load_profile
from fhr3.tournament.fields import FHR3B_CONFIGS
from fhr3.tournament.manifests import RESULT_SOURCES, engine_source_hash
from fhr3.tournament.replay import check_replay, validate_cell
from fhr3.tournament.store import completed_replicates, load_cell_arrays, tournament_dir

CORE_FIELDS = {"spread": "ff0f2b07fc210f62", "crowded_cutoff": "afbffedfc3706d84",
               "style_diverse": "ad7d6596ef1c8c3e"}
SWISS_IDS = {"spread": "nlhe6.nlhe6-spread.fhr3b_baseline.R40H400K6.swiss.swiss-reference.2d98a8cd",
             "crowded_cutoff": "nlhe6.nlhe6-crowded_cutoff.fhr3b_baseline.R40H400K6.swiss.swiss-reference.bc25b57b",
             "style_diverse": "nlhe6.nlhe6-style_diverse.fhr3b_baseline.R40H400K6.swiss.swiss-reference.77d62182"}
CORE_CALIB_IDS = {"spread": "nlhe6.nlhe6-spread.H400.dup.field-reference.3cea71b5",
                  "crowded_cutoff": "nlhe6.nlhe6-crowded_cutoff.H400.dup.field-reference.7d2640ae",
                  "style_diverse": "nlhe6.nlhe6-style_diverse.H400.dup.field-reference.0caf92cc"}


@pytest.fixture(scope="module")
def pub():
    return load_profile("publication")


@pytest.fixture(scope="module")
def cells(pub):
    return core.core_cells(pub)


# ------------------------------------------------------------------ scope
def test_core_scope_is_nlhe6_with_three_frozen_fields(pub):
    cfg = core.core_config(pub)
    core.check_scope(pub, cfg)
    assert cfg["modes"] == ["nlhe6"]
    assert cfg["fields"] == CORE_FIELDS
    frozen = yaml.safe_load((FHR3B_CONFIGS / "fields/FROZEN.yaml").read_text())
    assert {f: frozen["fields"]["nlhe6"][f] for f in CORE_FIELDS} == CORE_FIELDS
    assert load_matrix()["primary_modes"] == ["nlhe6"]


def test_exactly_six_unique_cells_per_field(cells):
    assert len(cells) == 18
    assert len({c.cell.identity_hash for c in cells}) == 18 and len({c.cell.cell_id for c in cells}) == 18
    for field in CORE_FIELDS:
        mine = [c for c in cells if c.field == field]
        assert tuple(sorted(c.key for c in mine)) == tuple(sorted(core.CORE_CELL_KEYS))
    assert {c.mode for c in cells} == {"nlhe6"}
    assert {c.cell.field.field_hash for c in cells} == set(CORE_FIELDS.values())
    shape = {c.key: (c.cell.kind, c.cell.protocol.match_format, c.cell.protocol.rounds,
                     c.cell.protocol.hands_per_match, core.lanes(c.cell)) for c in cells if c.field == "spread"}
    assert shape == {
        "baseline": ("adaptive", "ordinary", 40, 400, 1),
        "budget_half_rounds": ("adaptive", "ordinary", 20, 800, 1),
        "budget_quarter_rounds": ("adaptive", "ordinary", 10, 1600, 1),
        "frozen_schedule": ("frozen_replay", "ordinary", 40, 400, 1),
        "dup_fewer_rounds": ("adaptive", "duplicate", 7, 400, 6),
        "dup_shorter_matches": ("adaptive", "duplicate", 40, 67, 6),
    }


def test_shared_cells_are_deduplicated(pub, cells):
    """B's 40x400, C's adaptive arm and D's ordinary arm ARE the baseline cell (same identity)."""
    for field in CORE_FIELDS:
        base = pub.cell("nlhe6", field, "baseline")
        b40 = [c for a, c in pub.budget_cells("nlhe6", field) if a.label == "baseline"]
        src, frozen, _, _ = pub.schedule_cells("nlhe6", field, 1)
        d_ord = [c for lab, c in pub.duplicate_cells("nlhe6", field) if lab == "ordinary"]
        assert {base.identity_hash, b40[0].identity_hash, src.identity_hash, d_ord[0].identity_hash} == {
            base.identity_hash}
        assert frozen.source.identity_hash == base.identity_hash and frozen.replays_per_source == 1
        baseline = [c for c in cells if c.field == field and c.key == "baseline"]
        assert len(baseline) == 1 and baseline[0].experiments == ("A", "B", "C", "D")
    assert core.core_cells(pub, keys=list(core.CORE_CELL_KEYS))[0].key == "baseline"  # baselines run first


def test_a_prefixes_are_read_from_the_baseline(pub, cells):
    cfg = core.core_config(pub)
    assert cfg["round_prefixes"] == [5, 10, 20, 30, 40] == pub.checkpoints_for(40)
    # no separate 5/10/20/30-round cells: A only ever reads the 40-round baseline trajectories
    assert {c.cell.protocol.rounds for c in cells if "A" in c.experiments} == {40}
    assert not [c for c in cells if c.cell.protocol.rounds in (5, 30)]


def test_horizon_extensions_disabled_by_default(pub, cells):
    hz = core.core_config(pub)["horizon_extensions"]
    assert hz == {"enabled": False, "horizons": [60, 80, 120]}
    assert max(c.cell.protocol.rounds for c in cells) == 40


def test_initial_budgets(pub):
    cfg = core.core_config(pub)
    assert cfg["replicates_initial"] == 50
    assert load_matrix()["presets"] == {"pilot": 8, "core": 50, "swiss_reference": 100}
    assert cfg["field_reference"]["matched_rounds_initial"] == 250 == core.core_field_rounds(pub)
    sw = cfg["swiss_reference"]
    assert (sw["enabled"], sw["replicates_initial"], sw["replicates_extension"]) == (True, 100, 200)
    assert load_matrix()["experiments"]["frozen_schedule"]["replays_per_source"] == 1  # J = 1 in the core
    assert {f: pub.swiss_reference_cell("nlhe6", f).cell_id for f in CORE_FIELDS} == SWISS_IDS


def test_mu_field_budget_is_core_scoped(pub, tmp_path):
    """Non-core field references never inherit the FHR #4 250 rounds: they must pass --rounds."""
    assert "matched_rounds" not in pub.calibration["field_reference"]
    assert "rounds" not in pub.calibration["field_reference"]
    for mode in ("aof4", "nlhe4"):
        with pytest.raises(ValueError):
            pub.calibration_rounds("field", mode)
        with pytest.raises(SystemExit, match="explicitly with --rounds"):
            main(["calibrate", "--stage", "field", "--modes", mode, "--fields", "spread", "--allow-noncore",
                  "--root", str(tmp_path)])
    assert not any(tmp_path.iterdir())


def test_calibration_ids_unchanged_by_the_250_round_scope(pub):
    # rounds are not part of the calibration identity: 250 and the 500 extension share these ids
    assert {f: pub.calibration_spec("nlhe6", "field", f).calib_id for f in CORE_FIELDS} == CORE_CALIB_IDS


# ------------------------------------------------------------------ accounting / plan
def test_plan_accounting(pub, tmp_path):
    plan = core.build_plan(pub, tmp_path)
    assert plan["simulates"] is False and not any(tmp_path.iterdir())  # planning writes nothing
    fr = plan["field_reference"]
    assert [r["calib_id"] for r in fr] == list(CORE_CALIB_IDS.values())
    for r in fr:  # 250 rounds x 10 tables x 6 lanes x 400 hands
        assert (r["matched_rounds_to_run"], r["lanes"], r["tables_per_round"]) == (250, 6, 10)
        assert r["scheduled_hands_to_run"] == 6_000_000 and r["stage"] == "initial"
    rows = plan["matrix"]
    assert len(rows) == 18 and all(r["to_run"] == 50 and r["replicates"] == [0, 50] for r in rows)
    per = {r["cell"]: r["scheduled_hands_per_tournament"] for r in rows if r["field"] == "spread"}
    assert per == {"baseline": 160_000, "budget_half_rounds": 160_000, "budget_quarter_rounds": 160_000,
                   "frozen_schedule": 160_000, "dup_fewer_rounds": 168_000, "dup_shorter_matches": 160_800}
    work = {r["cell"]: (r["scheduled_work_ratio_vs_baseline"], r["exact_equal_work"]) for r in rows
            if r["field"] == "spread"}
    assert work["dup_fewer_rounds"] == (1.05, False) and work["dup_shorter_matches"] == (1.005, False)
    t = plan["totals"]
    assert t["mu_field"]["scheduled_hands"] == 18_000_000
    assert t["matrix"]["scheduled_hands"] == 145_320_000 and t["matrix"]["tournaments"] == 900
    assert t["mu_field_plus_matrix"]["scheduled_hands"] == 163_320_000
    assert t["mu_swiss"]["scheduled_hands"] == 48_000_000 and t["mu_swiss"]["tournaments"] == 300
    assert t["programme"]["scheduled_hands"] == 211_320_000
    assert t["programme"]["slow_rate_wall_h_ideal"] == pytest.approx(t["programme"]["wall_h_ideal"] * 4260 / 1289)
    sw = plan["swiss_reference"]
    assert sw["enabled"] is True and {r["field"]: r["cell_id"] for r in sw["rows"]} == SWISS_IDS
    assert all(r["replicates"] == [0, 100] and r["stage"] == "initial" for r in sw["rows"])
    frozen = [r for r in rows if r["cell"] == "frozen_schedule"]
    assert all(r["replays_per_source"] == 1 and r["replicates"] == [0, 50] for r in frozen)
    assert {n: o["scheduled_hands"] for n, o in plan["swiss_reference"]["options"].items()} == {
        "50": 24_000_000, "100": 48_000_000, "200": 96_000_000}


def test_plan_reports_extensions(pub, tmp_path):
    plan = core.build_plan(pub, tmp_path, replicates=range(50, 100), mu_field_rounds=500,
                           fields=["crowded_cutoff"], keys=["baseline"], swiss_replicates=range(100, 200))
    assert [r["stage"] for r in plan["matrix"]] == ["extension"]
    assert plan["field_reference"][0]["stage"] == "extension"
    assert [(r["stage"], r["to_run"]) for r in plan["swiss_reference"]["rows"]] == [("extension", 100)]


def test_cli_plan_runs_no_simulation(tmp_path, capsys):
    out = tmp_path / "plan.json"
    assert main(["core", "plan", "--root", str(tmp_path / "r"), "--json", str(out)]) == 0
    assert "NO simulation" in capsys.readouterr().out
    plan = json.loads(out.read_text())
    assert plan["totals"]["programme"]["scheduled_hands"] == 211_320_000
    assert not (tmp_path / "r").exists()


# ------------------------------------------------------------------ guards (refuse before any simulation)
@pytest.mark.parametrize("argv, match", [
    (["core", "matrix", "--range", "50:100"], "--extend"),
    (["core", "matrix", "--replicates", "100"], "--extend"),
    (["core", "field-reference", "--rounds", "500"], "--extend"),
    (["core", "field-reference", "--rounds", "255", "--extend"], "multiple of chunk_rounds"),
    (["core", "swiss-reference", "--range", "100:200"], "--extend"),
    (["core", "swiss-reference", "--replicates", "200"], "--extend"),
    (["run", "--experiment", "swiss-reference", "--replicates", "150"], "--extend"),
    (["run", "--experiment", "baseline", "--modes", "aof4", "--replicates", "1"], "outside the FHR #4 core"),
    (["run", "--experiment", "budget-sweep", "--modes", "nlhe4", "--replicates", "1"], "outside the FHR #4 core"),
    (["run", "--experiment", "core", "--modes", "aof4", "--replicates", "1"], "nlhe6"),
    (["calibrate", "--stage", "field", "--modes", "aof4", "--fields", "spread"], "outside the FHR #4 core"),
    (["run", "--experiment", "baseline", "--replicates", "60"], "--extend"),
    (["run", "--experiment", "baseline", "--horizon", "80", "--replicates", "1"], "disabled by default"),
])
def test_publication_guards(tmp_path, argv, match):
    with pytest.raises(SystemExit, match=match):
        main(argv + ["--root", str(tmp_path)])
    assert not any(tmp_path.iterdir())


def test_swiss_reference_can_be_switched_off(tmp_path):
    cfg_root = tmp_path / "configs"
    shutil.copytree(FHR3B_CONFIGS, cfg_root)
    mx = (cfg_root / "matrix.yaml").read_text()
    (cfg_root / "matrix.yaml").write_text(mx.replace("    enabled: true                    # approved",
                                                     "    enabled: false                   # approved"))
    from fhr3.tournament import cli

    prof = load_profile("publication", config_root=cfg_root)
    orig = cli._core_cfg
    cli._core_cfg = lambda: load_matrix(cfg_root)["core_fhr4"]
    try:
        with pytest.raises(SystemExit, match="DISABLED"):
            cli._guard_swiss_reference(prof)
    finally:
        cli._core_cfg = orig


def test_retired_presets_are_gone():
    with pytest.raises(SystemExit):
        main(["run", "--experiment", "baseline", "--preset", "flagship", "--root", "/nonexistent"])


def test_core_refuses_a_revoked_or_unpinned_field(tmp_path):
    cfg_root = tmp_path / "configs"
    shutil.copytree(FHR3B_CONFIGS, cfg_root)
    mx = (cfg_root / "matrix.yaml").read_text()
    (cfg_root / "matrix.yaml").write_text(mx.replace("spread: ff0f2b07fc210f62", "spread: 16df070db91a53bd"))
    prof = load_profile("publication", config_root=cfg_root)
    with pytest.raises(core.CoreScopeError, match="16df070db91a53bd"):
        core.check_scope(prof)
    revoked = set(prof.revoked_hashes())
    assert "16df070db91a53bd" in revoked and not revoked & set(CORE_FIELDS.values())


def test_all_nine_frozen_fields_stay_valid(pub):
    frozen = yaml.safe_load((FHR3B_CONFIGS / "fields/FROZEN.yaml").read_text())["fields"]
    assert sorted(frozen) == ["aof4", "nlhe4", "nlhe6"]
    for mode, fields in frozen.items():
        for field, h in fields.items():
            assert pub.field(mode, field).field_hash == h


def test_core_modules_cannot_change_results():
    """The FHR #4 scope code is outside the engine source hash: results and replay are untouched."""
    for mod in ("core.py", "cli.py", "analysis.py", "experiments.py", "batch.py"):
        assert f"tournament/{mod}" not in RESULT_SOURCES
    assert engine_source_hash() == "4647ee69857e7c9b", "result-relevant source changed: re-verify replay"


# ------------------------------------------------------------------ smoke-scale runs
@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("core-smoke")
    assert main(["core", "matrix", "--profile", "smoke", "--fields", "smoke12", "--root", str(root),
                 "--replicates", "2", "--workers", "1", "--quiet"]) == 0
    prof = load_profile("smoke", root)
    return root, prof, core.core_cells(prof, ["smoke12"])


def test_smoke_core_matrix_replays_and_validates(smoke_run):
    root, _, cells = smoke_run
    assert len(cells) == 6 and len(list(root.iterdir())) == 6  # six unique cells on disk, nothing else
    for cc in cells:
        assert completed_replicates(root, cc.cell) == [0, 1]
        assert validate_cell(root, cc.cell, [0, 1])["validated"] == 2  # incl. lane invariants for duplicate
        assert check_replay(root, cc.cell, [0])["replayed_exactly"] == 1
    dup = [cc for cc in cells if cc.cell.protocol.match_format == "duplicate"]
    assert all((tournament_dir(root, cc.cell, 0) / "lanes.parquet").exists() for cc in dup)


def test_frozen_replays_baseline_schedule(smoke_run):
    from fhr3.tournament.schedule import schedule_from_rows
    from fhr3.tournament.store import read_tournament_rows

    root, _, cells = smoke_run
    base = next(cc.cell for cc in cells if cc.key == "baseline")
    frozen = next(cc.cell for cc in cells if cc.key == "frozen_schedule")
    for r in (0, 1):
        b_rows, _, _ = read_tournament_rows(root, base, r)
        f_rows, _, _ = read_tournament_rows(root, frozen, r)
        assert schedule_from_rows(f_rows) == schedule_from_rows(b_rows)  # J = 1: replicate r <- source r
        assert [x["chip_delta"] for x in f_rows] != [x["chip_delta"] for x in b_rows]  # fresh poker randomness


def test_extension_appends_without_recomputing(smoke_run, capsys):
    root, _, cells = smoke_run
    before = {(cc.key, r): (tournament_dir(root, cc.cell, r) / "manifest.json").read_bytes()
              for cc in cells for r in (0, 1)}
    capsys.readouterr()
    assert main(["core", "matrix", "--profile", "smoke", "--fields", "smoke12", "--root", str(root),
                 "--range", "0:3", "--workers", "1", "--quiet", "--cells", "baseline", "frozen_schedule"]) == 0
    out = capsys.readouterr().out
    assert out.count("ran 1 (skipped 2)") == 2
    for cc in cells:
        for r in (0, 1):
            assert (tournament_dir(root, cc.cell, r) / "manifest.json").read_bytes() == before[(cc.key, r)]
    base = next(cc.cell for cc in cells if cc.key == "baseline")
    assert completed_replicates(root, base) == [0, 1, 2]


def test_frozen_extension_needs_its_source(smoke_run):
    root, _, _ = smoke_run
    with pytest.raises(SystemExit, match="run the baseline cell first"):
        main(["core", "matrix", "--profile", "smoke", "--fields", "smoke12", "--root", str(root),
              "--range", "5:6", "--workers", "1", "--quiet", "--cells", "frozen_schedule"])


def test_field_reference_extension_appends_chunks(tmp_path):
    from fhr3.tournament.calibration import calib_dir

    args = ["core", "field-reference", "--profile", "smoke", "--fields", "smoke12", "--root", str(tmp_path),
            "--workers", "1", "--boot", "10", "--quiet", "--no-report"]
    assert main(args) == 0  # smoke initial stage: 12 // 6 = 2 matched rounds
    spec = load_profile("smoke", tmp_path).calibration_spec("nlhe6", "field", "smoke12")
    d = calib_dir(tmp_path, spec)
    first = {p.name: p.read_bytes() for p in sorted((d / "chunks").glob("*.parquet"))}
    assert sorted(first) == ["c_0000000_0000001.parquet", "c_0000001_0000002.parquet"]
    assert main(args + ["--rounds", "4"]) == 0
    after = {p.name: p.read_bytes() for p in sorted((d / "chunks").glob("*.parquet"))}
    assert len(after) == 4 and all(after[k] == v for k, v in first.items())
    assert core._rounds_on_disk(tmp_path, spec) == 4


def test_frozen_schedule_contrast_analysis(smoke_run):
    from fhr3.tournament.analysis import _frozen_schedule

    root, _, cells = smoke_run
    base = next(cc.cell for cc in cells if cc.key == "baseline")
    frozen = next(cc.cell for cc in cells if cc.key == "frozen_schedule")
    rows = _frozen_schedule(root, base, frozen, n_boot=20, fr=None)
    metrics = {r["metric"] for r in rows}
    assert {"changed_qualifiers", "topk_overlap", "n_ambiguous_bots", "kendall_tau"} <= metrics
    for r in rows:
        assert r["adaptive_minus_frozen_value"] == pytest.approx(r["adaptive_value"] - r["frozen_value"])
    a = load_cell_arrays(root, base, [0, 1])
    assert a["final_rank"].shape == (2, 12)


def test_runbook_and_scope_docs_state_the_core_scope():
    repo = Path(__file__).resolve().parents[1]
    scope = (repo / "paper/FHR3B_SCOPE.md").read_text()
    assert "FullHouse Research #4" in scope and "NLHE6 only" in scope
    for ref in ("10.1016/j.cor.2022.105821", "Swiss Tournament Model", "Annual Computer Poker Competition",
                "Baseline: Practical Control Variates", "10.1609/aaai.v32i1.11481"):
        assert ref in scope, ref
    plan_doc = " ".join((repo / "docs/fhr3b/FHR4_CORE.md").read_text().split())
    assert "fhr3b core plan" in plan_doc and "not a declaration of the 2027" in plan_doc


def test_frozen_contrast_clusters_by_source_for_j_above_one(smoke_run):
    """J > 1 (a later precision extension) is a new cell; replays of one source are one bootstrap cluster."""
    from fhr3.tournament.analysis import _cluster_pair_mean, _frozen_schedule
    from fhr3.tournament.cells import Cell

    root, prof, cells = smoke_run
    base = next(cc.cell for cc in cells if cc.key == "baseline")
    j1 = next(cc.cell for cc in cells if cc.key == "frozen_schedule")
    j2 = Cell("frozen_replay", base.mode, base.protocol, base.field, base.seed_family, base.namespace, base, 2)
    assert j2.identity_hash != j1.identity_hash  # J is part of the identity: no collision with the core cell
    run_cell(j2, root, range(4), progress=False)  # sources 0, 1 x 2 replays
    rows = _frozen_schedule(root, base, j2, n_boot=20, fr=None)
    assert rows and all(r["n_sources"] == 2 and r["replays_per_source"] == 2 for r in rows)
    # same-source pairs are excluded; weights act per source
    mat = np.arange(16, dtype=float).reshape(4, 4)
    cl = np.array([0, 0, 1, 1])
    assert _cluster_pair_mean(mat, cl, None) == pytest.approx(np.mean([mat[i, j] for i in range(4) for j in range(4)
                                                                        if cl[i] != cl[j]]))
    assert np.isnan(_cluster_pair_mean(mat, cl, np.array([3.0, 0.0])))  # one source drawn: no between-source pair
    one = np.arange(3)
    m3 = np.arange(9, dtype=float).reshape(3, 3)
    from fhr3.tournament import metrics as mt

    assert _cluster_pair_mean(m3, one, None) == pytest.approx(mt.pair_mean(m3))


def test_swiss_reference_outputs(tmp_path):
    from fhr3.tournament.analysis import swiss_reference_report

    prof = load_profile("smoke", tmp_path)
    cell = prof.cell("nlhe6", "smoke12", "swiss_reference")
    run_cell(cell, tmp_path, range(4), progress=False)
    bots, summ = swiss_reference_report(tmp_path, cell, None, n_boot=30)
    assert len(bots) == 12
    need = {"p_qualify", "p_qualify_wilson_lo", "p_qualify_wilson_hi", "mu_swiss_final_score",
            "mu_swiss_final_score_se", "mu_swiss_rank_lo95", "mu_swiss_rank_hi95", "p_in_mu_swiss_top_k",
            "ambiguous_qualification"}
    assert need <= set(bots[0])
    assert sum(b["p_qualify"] for b in bots) == pytest.approx(summ["K"])
    assert {"expected_topk_overlap", "boundary_bots", "n_ambiguous_bots", "ranking_robustness"} <= set(summ)
    assert "reference_topk_overlap_value" in summ["expected_topk_overlap"]["vs_mu_swiss_in_sample"]
    # extension 4 -> 6 appends replicates 4, 5 only
    before = (tournament_dir(tmp_path, cell, 0) / "manifest.json").read_bytes()
    assert run_cell(cell, tmp_path, range(6), progress=False)["ran"] == 2
    assert (tournament_dir(tmp_path, cell, 0) / "manifest.json").read_bytes() == before
