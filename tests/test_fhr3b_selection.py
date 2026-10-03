"""FHR3B locked design: selection v2, behaviour styles, NLHE4 readiness, matrix, horizon."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from fhr3.tournament import metrics as mt
from fhr3.tournament import selection as S
from fhr3.tournament.behaviour import style_classes
from fhr3.tournament.diagnostics import param_distance, param_vectors
from fhr3.tournament.experiments import load_matrix, load_profile
from fhr3.tournament.fields import FHR3B_CONFIGS, load_field, load_mode

REPO = Path(__file__).resolve().parents[1]


class FakeInputs:
    """Minimal stand-in for selection.Inputs with synthetic strengths and styles."""

    def __init__(self, mode: str = "nlhe6", gap_after: int = 6, seed: int = 0) -> None:
        pool = load_field(FHR3B_CONFIGS / f"fields/{mode}/pool.json")
        rng = np.random.default_rng(seed)
        self.bots = sorted(pool.bot_ids)
        order = rng.permutation(len(self.bots))
        self.mu = {b: float(1000 - 30 * r - (3000 if r >= gap_after else 0)) for b, r in zip(self.bots, order)}
        self.se = {b: 100.0 for b in self.bots}
        self.ranked = sorted(self.bots, key=lambda b: (-self.mu[b], b))
        meta = {b["bot_id"]: b["meta"] for b in pool.bots}
        self.arch = {b: meta[b]["archetype"] for b in self.bots}
        self.style = {b: "TA LA TP LP".split()[i % 4] for i, b in enumerate(self.bots)}
        self.vecs = param_vectors(pool.bots)
        self.family = "nlhe"

    near_dup = S.Inputs.near_dup
    min_dist = S.Inputs.min_dist


SPREAD = {"gap_se": 3.0, "strata": 6, "leader_archetype_cap": 3, "archetype_cap": 10, "near_dup": 0.15}
STYLE = {"strata": 5, "archetype_cap": 10, "near_dup": 0.15}


def _near_dup_pairs(inp, ids):
    return sum(inp.near_dup(a, b, 0.15) for i, a in enumerate(ids) for b in ids[i + 1:])


def test_spread_selector_meets_gap_and_diversity_constraints():
    inp = FakeInputs()
    ids, info = S.select_spread(inp, 60, 6, SPREAD)
    assert len(ids) == len(set(ids)) == 60
    assert ids == S.select_spread(inp, 60, 6, SPREAD)[0]  # deterministic
    assert info["gap_se_constraint"] == 3.0 and info["achieved_gap_se"] >= 3.0
    assert _near_dup_pairs(inp, ids) == 0
    assert max(sum(inp.arch[b] == a for b in ids) for a in set(inp.arch.values())) <= 10
    leaders = sorted(ids, key=lambda b: -inp.mu[b])[:6]
    assert leaders == info["leaders"]


def test_spread_selector_records_relaxation_when_gap_infeasible():
    inp = FakeInputs()
    inp.mu = {b: float(-10 * i) for i, b in enumerate(inp.ranked)}  # smooth, gapless strengths
    inp.se = {b: 150.0 for b in inp.bots}  # 3 SE of a difference (636) excludes too many bots
    ids, info = S.select_spread(inp, 60, 6, SPREAD)
    assert len(ids) == 60
    assert info["gap_se_target"] == 3.0 and info["gap_se_constraint"] < 3.0


def test_style_diverse_balances_style_and_strength_strata():
    inp = FakeInputs()
    ids, info = S.select_style_diverse(inp, 60, STYLE)
    assert len(ids) == len(set(ids)) == 60
    assert ids == S.select_style_diverse(inp, 60, STYLE)[0]
    alloc = np.array(list(info["allocation"].values()))
    assert (alloc.sum(axis=0) == 12).all()  # every strength quintile gets 12
    assert all(abs(t - 15) <= info["style_slack"] for t in alloc.sum(axis=1))
    assert _near_dup_pairs(inp, ids) == 0


def test_style_classes_are_median_split_quadrants():
    rows = [{"bot_id": f"b{i}", "vpip": str(v), "pfr": str(p)} for i, (v, p) in
            enumerate([(0.1, 0.09), (0.1, 0.03), (0.5, 0.45), (0.5, 0.1)])]
    assert style_classes(rows, "heuristic") == {"b0": "TA", "b1": "TP", "b2": "LA", "b3": "LP"}


def test_param_distance_zero_for_self_inf_across_kinds():
    pool = load_field(FHR3B_CONFIGS / "fields/aof4/pool.json")
    v = param_vectors(pool.bots)
    assert param_distance(v, "aof4-neutral-e0", "aof4-neutral-e0") == 0
    assert math.isinf(param_distance(v, "aof4-neutral-e0", "aof4-policy-e0"))
    assert 0 < param_distance(v, "aof4-neutral-e0", "aof4-neutral-e1-s0") < 0.2


@pytest.mark.parametrize("mode", ["aof4", "nlhe4", "nlhe6"])
def test_candidate_fields_reproduce_from_frozen_calibration(mode, tmp_path):
    """Selection v2 is a pure function of the calibration chunks + behaviour audit."""
    from fhr3.tournament.calibration import calib_dir

    prof = load_profile("publication")
    if not (calib_dir(REPO / "results/fhr3b", prof.calibration_spec(mode, "pool")) / "chunks").exists():
        pytest.skip(f"{mode}: current pool calibration not run")
    inp = S.Inputs(REPO / "results/fhr3b", prof, mode, REPO / "reports/fhr3b", n_boot=20)
    sel = prof.selection
    spread, _ = S.select_spread(inp, 60, 6, sel["spread"] | {"near_dup": sel["near_dup"]})
    style, _ = S.select_style_diverse(inp, 60, sel["style_diverse"] | {"near_dup": sel["near_dup"]})
    for name, ids in (("spread", spread), ("style_diverse", style)):
        path = FHR3B_CONFIGS / f"fields/{mode}/{name}.json"
        if path.exists():
            assert sorted(ids) == sorted(load_field(path).bot_ids), name


# ------------------------------------------------------------------ locked design
def test_matrix_locks_modes_fields_and_retires_matchup():
    mx = load_matrix()
    assert mx["primary_modes"] == ["nlhe6"]  # FHR #4 core scope
    assert mx["provenance_modes"] == ["aof4", "nlhe4"]  # frozen, provenance only
    for name, ex in mx["experiments"].items():
        if name not in ("smoke",):
            assert "plo6" not in ex.get("modes", []), name
    assert mx["experiments"]["baseline"]["fields"] == ["separated_control", "crowded_cutoff", "style_diverse"]
    assert mx["experiments"]["duplicate_play"]["status"] == "implemented"
    assert mx["calibration"]["field_reference"]["match_format"] == "duplicate"
    text = (FHR3B_CONFIGS / "matrix.yaml").read_text()
    assert "matchup_gate" not in text and "matchup_sensitive" not in text
    assert "select_matchup" not in (REPO / "src/fhr3/tournament/selection.py").read_text().split('"""', 2)[2]
    for mode in ("aof4", "nlhe4", "nlhe6"):
        assert not (FHR3B_CONFIGS / f"fields/{mode}/matchup_sensitive.json").exists()


def test_horizon_checkpoints():
    prof = load_profile("publication")
    assert prof.rounds_sweep() == [5, 10, 20, 30, 40]
    assert prof.checkpoints_for(40) == [5, 10, 20, 30, 40]
    assert prof.checkpoints_for(80) == [5, 10, 20, 30, 40, 60, 80]
    assert prof.checkpoints_for(100) == [5, 10, 20, 30, 40, 60, 80, 100]
    assert prof.cell("nlhe6", "provisional60", "baseline", 80).protocol.rounds == 80


def test_nlhe4_calibration_is_prepared():
    prof = load_profile("publication")
    spec = prof.calibration_spec("nlhe4", "pool")
    six = prof.calibration_spec("nlhe6", "pool")
    mode = load_mode("nlhe4")
    assert (mode.table_size, mode.stack_policy, mode.game.stack_bb) == (4, "persistent_no_rebuy", 100.0)
    assert spec.hands_per_match == 400 and spec.namespace == "pool-calibration"
    assert spec.field.n == 96 and spec.field.field_hash != six.field.field_hash
    assert spec.calib_id != six.calib_id and spec.calib_id.startswith("nlhe4.nlhe4-pool.H400.pool-calibration.")
    spec.field.validate()
    assert all(len(t) == 4 for t in spec.partition(0)) and len(spec.partition(0)) == 24


def test_duplicate_play_publication_run_needs_explicit_count():
    from fhr3.tournament.cli import main

    with pytest.raises(SystemExit, match="explicit"):
        main(["run", "--experiment", "duplicate-play", "--root", "/nonexistent"])


def test_accuracy_vs_reference_exact():
    ref = np.array([6.0, 5, 4, 3, 2, 1, 0, -1])
    perfect = np.tile(np.arange(1, 9), (3, 1))
    est = mt.accuracy_vs_reference(perfect, ref, 3, b=20)
    assert est["reference_topk_overlap"].value == 3 and est["reference_kendall_tau"].value == pytest.approx(1)
    swapped = np.array([[1, 2, 4, 3, 5, 6, 7, 8]] * 2)  # reference #3 and #4 swap across the cut
    est = mt.accuracy_vs_reference(swapped, ref, 3, b=20)
    assert est["reference_changed"].value == 1


def test_locked_scope_language():
    scope = (REPO / "paper/FHR3B_SCOPE.md").read_text()
    assert "initial horizon" in scope and "not** an assumption that 40 rounds suffice" in scope
    assert "NLHE6 only" in scope and "PLO is removed" in scope
    lab = yaml.safe_load((FHR3B_CONFIGS / "lab/lab60_top6.yaml").read_text())
    assert lab["field_size"] == 60
