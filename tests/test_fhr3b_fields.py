"""FHR3B fields: deterministic pools, frozen manifests, selection rules, seed namespaces, calibration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from fhr3.tournament.calibration import (
    CalibrationSpec,
    analyse_calibration,
    hodge,
    load_calibration,
    run_calibration,
    subset_hodge,
)
from fhr3.tournament.fields import (
    FHR3B_CONFIGS,
    all_modes,
    field_from_dict,
    load_field,
    load_mode,
    pool_manifest,
    select_crowded,
    select_spread,
    smoke_field,
    write_field_immutable,
)
from fhr3.tournament.manifests import NAMESPACES, replay_seeds, tournament_seeds

FROZEN = FHR3B_CONFIGS / "fields"


@pytest.mark.parametrize("mode", all_modes())
def test_pool_regenerates_to_the_frozen_manifest(mode):
    fresh = pool_manifest(load_mode(mode))
    frozen = load_field(FROZEN / mode / "pool.json")
    assert fresh.field_hash == frozen.field_hash
    ids = fresh.bot_ids
    assert len(ids) == len(set(ids)) == 96
    for b in fresh.bots:
        assert {"archetype", "scale_index", "epsilon", "agent_seed"} <= set(b["meta"])
    frozen.validate()  # every bot rebuilds to its recorded version


@pytest.mark.parametrize("mode", all_modes())
def test_frozen_subfields_are_consistent(mode):
    pool = load_field(FROZEN / mode / "pool.json")
    for name in ("smoke12", "provisional60"):
        fm = load_field(FROZEN / mode / f"{name}.json")
        assert set(fm.bot_ids) <= set(pool.bot_ids)
        assert fm.construction["pool_hash"] == pool.field_hash
    assert smoke_field(pool).field_hash == load_field(FROZEN / mode / "smoke12.json").field_hash


def test_field_manifest_is_immutable_and_tamper_evident(tmp_path):
    pool = pool_manifest(load_mode("nlhe6"))
    p = write_field_immutable(smoke_field(pool), tmp_path / "f.json")
    write_field_immutable(smoke_field(pool), p)  # identical rewrite is a no-op
    other = smoke_field(pool, 6)
    with pytest.raises(ValueError):
        write_field_immutable(other, p)
    d = json.loads(p.read_text())
    d["bots"][0]["params"] = {"style": "loose"}
    with pytest.raises(ValueError):
        field_from_dict(d)


def test_selection_rules_are_deterministic():
    ids = [f"b{i:02d}" for i in range(30)]
    # steep everywhere except a flat region at pool ranks 9-14
    mu = {b: -i**1.5 if not 8 <= i < 14 else -8**1.5 - (i - 8) * 0.01 for i, b in enumerate(ids)}
    ranked = sorted(ids, key=lambda b: (-mu[b], b))
    sp = select_spread(ranked, 10)
    assert sp == select_spread(ranked, 10) and sp[0] == ranked[0] and sp[-1] == ranked[-1] and len(set(sp)) == 10
    sel, info = select_crowded(ranked, mu, 16, 4, n_top=2, crowd=5)
    assert len(sel) == len(set(sel)) == 16
    assert sel[:2] == ranked[:2]
    assert set(info["crowd_ids"]) <= {f"b{i:02d}" for i in range(8, 14)}  # the flat region is chosen
    with pytest.raises(ValueError):
        select_crowded(ranked, mu, 16, 8, n_top=2, crowd=5)  # crowd must straddle the cut


def test_seed_namespaces_are_disjoint():
    seeds = {ns: tournament_seeds("fam", ns, 0).tournament_seed for ns in NAMESPACES}
    assert len(set(seeds.values())) == len(NAMESPACES)
    s = tournament_seeds("fam", "publication", 3)
    r = replay_seeds("fam", "publication", 3, 0, s)
    assert r.order_seed == s.order_seed and r.chance_seed != s.chance_seed
    with pytest.raises(ValueError):
        tournament_seeds("fam", "not-a-namespace", 0)


def test_calibration_seed_separation():
    mode = load_mode("nlhe6")
    fm = smoke_field(pool_manifest(mode))
    a = CalibrationSpec(mode, fm, 10, "persistent_no_rebuy", "fam", "pool-calibration")
    b = CalibrationSpec(mode, fm, 10, "persistent_no_rebuy", "fam", "field-reference")
    assert a.seed != b.seed and a.calib_id != b.calib_id
    assert a.partition(0) != b.partition(0)
    for r in range(5):  # each round: every bot at most once, full tables only
        seated = [x for t in a.partition(r) for x in t]
        assert len(seated) == len(set(seated)) == 12 and all(len(t) == 6 for t in a.partition(r))


def _synthetic_spec(edge=None, strength=None):
    mode = load_mode("nlhe6")
    fm = smoke_field(pool_manifest(mode))
    strength = strength or {b: 0.0 for b in fm.bot_ids}
    return CalibrationSpec(mode, fm, 100, "persistent_no_rebuy", "fam", "test", chunk_rounds=20,
                           synthetic={"strength": strength, "noise_sd": 50.0, "edge": edge or {}})


def test_calibration_recovers_strength_order(tmp_path):
    mode = load_mode("nlhe6")
    ids = sorted(smoke_field(pool_manifest(mode)).bot_ids)
    strength = {b: (i - 6) * 5.0 for i, b in enumerate(ids)}  # neighbour gap ~8 SE
    spec = _synthetic_spec(strength=strength)
    run_calibration(spec, tmp_path, 200, progress=False)
    res = analyse_calibration(load_calibration(tmp_path, spec), ids, n_boot=20)
    assert list(np.argsort(res["mu"])) == list(range(12))
    assert subset_hodge(res, ids)["cyclic_share_debiased"] < 0.2  # transitive by construction


def test_calibration_detects_cyclic_matchups(tmp_path):
    mode = load_mode("nlhe6")
    ids = sorted(smoke_field(pool_manifest(mode)).bot_ids)
    groups = [ids[0::3], ids[1::3], ids[2::3]]  # rock / paper / scissors styles
    edge = {}
    for g in range(3):
        for a in groups[g]:
            edge[a] = {b: 3.0 for b in groups[(g + 1) % 3]} | {b: -3.0 for b in groups[(g + 2) % 3]}
    spec = _synthetic_spec(edge=edge)
    run_calibration(spec, tmp_path, 200, progress=False)
    res = analyse_calibration(load_calibration(tmp_path, spec), ids, n_boot=20)
    assert subset_hodge(res, ids)["cyclic_share_debiased"] > 0.8


def test_hodge_pure_gradient_and_pure_cycle():
    r = np.array([3.0, 1.0, 0.0, -4.0])
    grad = r[:, None] - r[None, :]
    z = np.zeros_like(grad)
    assert hodge(grad, z)["cyclic_share_raw"] == pytest.approx(0.0, abs=1e-12)
    cyc = np.array([[0, 1, -1], [-1, 0, 1], [1, -1, 0]], dtype=float)
    assert hodge(cyc, np.zeros((3, 3)))["cyclic_share_raw"] == pytest.approx(1.0)
