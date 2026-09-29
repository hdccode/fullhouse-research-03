"""FHR3A controlled table-size suite (NLHE 100BB at 3 / 4 / 6 / 8 seats, one scheduled reference
population): configs, the reference-mixture schedule, block construction, invariants, and the
guard that the frozen corpora and manifests are untouched. Design: docs/table_size.md.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from fhr3.agents.heuristic import HeuristicAgent
from fhr3.cli.main import main
from fhr3.configs.experiment import config_from_dict, load_config
from fhr3.eval.matched import make_deal, reference_seats
from fhr3.eval.runner import BlockSimulator
from fhr3.games import make_adapter
from fhr3.games.base import Action
from fhr3.io.store import read_blocks
from fhr3.validation.corpus import rows_equal, validate_pairing

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"
SEATS = (3, 4, 6, 8)
PAIRINGS = ("p1-neutral-vs-loose10", "p2-neutral-vs-tight", "p3-aggressive-vs-neutral", "c0-selfplay-control")
DIVERGENT = PAIRINGS[:3]
CYCLE_STYLES = ["neutral", "neutral", "tight", "loose", "aggressive"]
MIXTURE = {"neutral": 2, "tight": 1, "loose": 1, "aggressive": 1}  # per 5 blocks, per slot

# Pinned hashes of the controlled suite. Pairing hashes are identical at every table size: the
# pairing (candidates + reference schedule) is the same object; table size lives in config_hash.
SUITE_CONFIG_HASH = {3: "c9937b916d1bb80f", 4: "56dcbd13a8614cbb", 6: "e02ffdc936b79e3f", 8: "1bbb0bcb3b465ed8"}
SUITE_PAIRING_HASH = {"p1-neutral-vs-loose10": "673af4685c2af5bd", "p2-neutral-vs-tight": "ae7864c08a103e25",
                      "p3-aggressive-vs-neutral": "23aee34fa30d77a6", "c0-selfplay-control": "6b579ec93d864457"}
SUITE_REFERENCE_VERSION = "e945702f6e"
# Frozen corpora (historical 4/6-max comparison only): lock values that must never change.
FROZEN_LOCKS = {
    "nlhe_4max_100bb_v2.yaml": ("ab7e279f1720c074", {
        "p1-neutral-vs-loose10": "c9611883f0df92dd", "p2-neutral-vs-tight": "2fab1924aa240919",
        "p3-aggressive-vs-neutral": "288544a16a8fd536", "c0-selfplay-control": "87ef4dd3c9d23cbe"}),
    "nlhe_6max_100bb.yaml": ("5f8886e193bc5489", {
        "p1-neutral-vs-loose10": "8271526be0009827", "p2-neutral-vs-tight": "7ccf8986402ec53f",
        "p3-aggressive-vs-neutral": "87abe185aa06c57a", "c0-selfplay-control": "a8faf06a963035ba"}),
}
FROZEN_FILES = {
    "reports/final-analysis/MANIFEST.json": "2724469c22276f4d2406e69f0a1d8b2a01e34ad0a50338a2d853a91ca2877ddb",
    "reports/rq6/MANIFEST.json": "aee2b8477ab82270166b3bf8d636103e8145ecc43b3d6829ed9a6a4274653e93",
    "reports/rq7/MANIFEST.json": "3564b2e1bd1f1a10c294496d322d65af3cdce601aaa752ec507d93f86a231d0a",
    "paper/figures/final/build_manifest.json": "07388a0054b94c6add0760ae8eb0e7b86ece212dc95a3eddf96c0d7f21a221ed",
}


def cfg(k):
    return load_config(CONFIGS / "tablesize" / f"nlhe_{k}max_100bb.yaml")


def lineup_styles(p, b, k):
    return [s.params["style"] for s in p.reference_specs(b, k)]


# ---------------------------------------------------------------- configs and hashes
@pytest.mark.parametrize("k", SEATS)
def test_suite_hashes_pinned(k):
    c = cfg(k)
    assert c.experiment_id == f"fhr3a-nlhe{k}-100bb-tablesize-v1" and c.game.player_count == k
    assert c.config_hash == SUITE_CONFIG_HASH[k]
    assert {p.pairing_id: p.pairing_hash for p in c.pairings} == SUITE_PAIRING_HASH
    assert {p.reference_version for p in c.pairings} == {SUITE_REFERENCE_VERSION}


def test_suite_differs_only_in_table_size():
    cs = {k: cfg(k) for k in SEATS}
    base = cs[6]
    for c in cs.values():
        assert c.environment()["game"] | {"player_count": 0} == base.environment()["game"] | {"player_count": 0}
        assert c.root_seed == base.root_seed and c.rng.to_dict() == base.rng.to_dict()
        assert [p.resolved() for p in c.pairings] == [p.resolved() for p in base.pairings]
        assert all(p.scheduled and not p.reference_seats for p in c.pairings)
    # candidates identical to the frozen NLHE configs; experiment ids new and unambiguous
    frozen = load_config(CONFIGS / "nlhe_6max_100bb.yaml")
    for p, f in zip(base.pairings, frozen.pairings, strict=True):
        assert p.pairing_id == f.pairing_id
        assert p.resolved()["candidate_a"] == f.resolved()["candidate_a"]
        assert p.resolved()["candidate_b"] == f.resolved()["candidate_b"]
    old_ids = {load_config(p).experiment_id for p in CONFIGS.glob("*.yaml")}
    assert not {c.experiment_id for c in cs.values()} & old_ids
    assert len({c.config_hash for c in cs.values()}) == 4


@pytest.mark.parametrize("name", sorted(FROZEN_LOCKS))
def test_fixed_population_configs_hash_as_before(name):
    c = load_config(CONFIGS / name)
    chash, phashes = FROZEN_LOCKS[name]
    assert c.config_hash == chash
    assert {p.pairing_id: p.pairing_hash for p in c.pairings} == phashes
    assert all(not p.scheduled and "reference_schedule" not in p.resolved() for p in c.pairings)


def test_schedule_config_validation():
    raw = {"experiment_id": "x", "root_seed": 1, "game": {"variant": "nlhe", "player_count": 3, "stack_bb": 100},
           "agents": {"a": {"kind": "heuristic", "style": "neutral"}},
           "reference_populations": {"pop": {"cycle": []}},
           "pairings": [{"pairing_id": "p", "candidate_a": "a", "candidate_b": "a", "reference_population": "pop"}]}
    with pytest.raises(ValueError, match="cycle"):
        config_from_dict(raw)
    raw["reference_populations"]["pop"] = {"cycle": ["a"], "extra": 1}
    with pytest.raises(ValueError, match="cycle"):
        config_from_dict(raw)


# ---------------------------------------------------------------- the reference-mixture schedule
@pytest.mark.parametrize("k", SEATS)
def test_schedule_is_deterministic_and_follows_the_rule(k):
    p1, p2 = cfg(k).pairing("p2-neutral-vs-tight"), cfg(k).pairing("p2-neutral-vs-tight")
    for b in range(200):
        assert p1.reference_specs(b, k) == p2.reference_specs(b, k)
        assert lineup_styles(p1, b, k) == [CYCLE_STYLES[(b + j) % 5] for j in range(k - 1)]
    # every pairing (including the control) uses the same schedule
    assert len({tuple(lineup_styles(p, 7, k)) for p in cfg(k).pairings}) == 1


@pytest.mark.parametrize("k", SEATS)
def test_every_slot_has_exact_mixture_over_every_5_block_window(k):
    p = cfg(k).pairing("p1-neutral-vs-loose10")
    for start in range(0, 40):  # aligned and unaligned windows
        for j in range(k - 1):
            assert Counter(lineup_styles(p, b, k)[j] for b in range(start, start + 5)) == MIXTURE
    # and exactly 40/20/20/20 over the publication ranges (30k p1-p3, 10k control)
    for n in (30000, 10000):
        for j in range(k - 1):
            counts = Counter(CYCLE_STYLES[(b + j) % 5] for b in range(n))
            assert counts == {"neutral": 0.4 * n, "tight": 0.2 * n, "loose": 0.2 * n, "aggressive": 0.2 * n}


def _players(trace: str) -> list[str]:
    line = next(x for x in trace.splitlines() if x.startswith("players"))
    return ast.literal_eval(line.split("=", 1)[1].strip())


@pytest.mark.parametrize("k", SEATS)
def test_A_and_B_face_identical_lineup_and_rotation_is_complete(k):
    c = cfg(k)
    sim = BlockSimulator(c, c.pairing("p2-neutral-vs-tight"))
    for b in range(10):
        r = sim.run(b, trace=True)
        assert r.valid and r.played_hands == 2 * k and len(r.seat_D) == k
        assert [h.candidate_seat for h in r.hands] == [s for s in range(k) for _ in "AB"]
        assert [h.side for h in r.hands] == ["A", "B"] * k
        lineup = r.variant_info["reference_lineup"]["agents"]
        assert lineup == [s.agent_id for s in c.pairing("p2-neutral-vs-tight").reference_specs(b, k)]
        for s in range(k):
            pa, pb = _players(r.traces[f"s{s}A.phh"]), _players(r.traces[f"s{s}B.phh"])
            assert pa[s] == "neutral" and pb[s] == "tight"  # candidate in seat s
            assert [x for i, x in enumerate(pa) if i != s] == [x for i, x in enumerate(pb) if i != s]
            for j, seat in enumerate(reference_seats(k, s)):  # lineup relative to the candidate
                assert pa[seat] == lineup[j]


@pytest.mark.parametrize("k", SEATS)
def test_lineup_recorded_in_row_and_replayed(k):
    c = cfg(k)
    p = c.pairing("p3-aggressive-vs-neutral")
    s1, s2 = BlockSimulator(c, p), BlockSimulator(c, p)
    for b in range(6):
        r1, r2 = s1.row(s1.run(b), "r", False), s2.row(s2.run(b), "r", False)
        assert rows_equal(r1, r2) == []
        assert json.loads(r1["variant_json"])["reference_lineup"]["styles"] == lineup_styles(p, b, k)


# ---------------------------------------------------------------- game and agent at new sizes
@pytest.mark.parametrize("k", (3, 8))
def test_blind_and_action_order(k):
    """Seat 0 = SB, 1 = BB, k-1 = button. Preflop starts at seat 2; folding round leaves the BB
    winning the SB; postflop is opened by the SB."""
    ad = make_adapter(cfg(k).game)
    assert ad.cards_per_deal() == 2 * k + 8
    deal = make_deal(ad, 7)
    h = ad.new_hand(deal)
    assert h.observation(h.actor()).bets == (50, 100) + (0,) * (k - 2)
    order = []
    while not h.is_terminal():
        order.append(h.actor())
        h.apply(Action.fold())
    assert order == list(range(2, k)) + [0]
    assert h.outcome().payoffs_chips == (-50, 50) + (0,) * (k - 2)
    h = ad.new_hand(deal)
    pre = []
    while h.observation(h.actor()).street == 0:
        pre.append(h.actor())
        h.apply(Action.check_call())
    assert pre == list(range(2, k)) + [0, 1] and h.actor() == 0


@pytest.mark.parametrize("k", SEATS)
def test_heuristic_positional_mapping_generalises(k):
    """Unopened-pot raise probability follows 'seats behind the button' at every seat, with no
    clipping of the open table (SB uses sb_open_pct). No agent code is seat-count specific."""
    ag = HeuristicAgent("n", "neutral")
    table = ag.p.open_pct_by_seats_behind
    assert k - 3 < len(table)
    ad = make_adapter(cfg(k).game)
    for seat in [s for s in range(k) if s != 1]:
        h = ad.new_hand(make_deal(ad, 99))
        while h.actor() != seat:
            h.apply(Action.fold())
        obs, legal = h.observation(seat), h.legal_actions()
        pct = ag.p.sb_open_pct if seat == 0 else table[k - 1 - seat]
        want = ag._in_range(ag.preflop_strength(obs), pct * ag.p.looseness, ag.p.preflop_temperature)
        got = sum(p for a, p in ag.action_distribution(obs, legal) if a.kind.value == "br")
        assert math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-15)


# ---------------------------------------------------------------- matched-block invariants
@pytest.mark.parametrize("k", SEATS)
def test_selfplay_exact_zero_and_swap_negation(k):
    c = cfg(k)
    ctl = BlockSimulator(c, c.pairing("c0-selfplay-control"))
    ab = BlockSimulator(c, c.pairing("p3-aggressive-vs-neutral"))
    ba = BlockSimulator(c, c.pairing("p3-aggressive-vs-neutral"))
    ba.a, ba.b = ab.b, ab.a
    moved = 0
    for b in range(25):
        r = ctl.run(b)
        assert r.valid and r.D == 0.0 and all(d == 0.0 for d in r.seat_D) and r.played_hands == 2 * k
        moved += any(r.seat_payoff_a)
        x, y = ab.run(b), ba.run(b)
        assert x.valid and y.valid and x.D == -y.D and x.seat_D == [-v for v in y.seat_D]
    assert moved > 0


@pytest.mark.parametrize("k", SEATS)
@pytest.mark.parametrize("pid", DIVERGENT)
def test_every_non_control_pairing_diverges(k, pid):
    """Divergence guard (cf. the Bomb Pot audit): D != 0 in a non-trivial share of blocks."""
    c = cfg(k)
    sim = BlockSimulator(c, c.pairing(pid))
    D = np.array([sim.run(b).D for b in range(100)])
    assert np.isfinite(D).all()
    assert (D != 0).sum() >= 5, f"{pid} at {k}-max diverged in only {(D != 0).sum()}/100 blocks"


GOLDEN_P2 = {
    3: [0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5],
    4: [0.0, 1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    6: [0.0, 0.0, 0.0, 30.02, 0.0, 0.0, 0.0, 0.0],
    8: [0.0, 1.5, 52.41, 0.0, 0.0, 0.0, 0.0, -39.83],
}


@pytest.mark.parametrize("k", SEATS)
def test_replay_golden(k):
    c = cfg(k)
    s = BlockSimulator(c, c.pairing("p2-neutral-vs-tight"))
    assert [round(s.run(b).D, 6) for b in range(8)] == GOLDEN_P2[k]


# ---------------------------------------------------------------- smoke via the CLI
@pytest.mark.parametrize("k", SEATS)
def test_cli_smoke_corpus_valid(k, tmp_path):
    c = cfg(k)
    out = tmp_path / "results"
    args = ["simulate", "--config", str(CONFIGS / "tablesize" / f"nlhe_{k}max_100bb.yaml"), "--blocks", "0:10",
            "--chunk-size", "5", "--out", str(out), "--no-traces"]
    assert main(args) == 0
    assert main(args) == 0  # resume: nothing left to do, no duplicates
    for pid in PAIRINGS:
        rep = validate_pairing(c, out, pid, expected=(0, 10), replay=3)
        assert rep["ok"], rep["problems"]
    t = read_blocks(out / c.experiment_id)
    assert t.num_rows == 10 * len(PAIRINGS)
    D = t.column("D").to_numpy(zero_copy_only=False).astype(float)
    assert np.isfinite(D).all() and all(t.column("valid").to_pylist())
    assert set(t.column("played_hands").to_pylist()) == {2 * k}
    for row in t.to_pylist():
        styles = json.loads(row["variant_json"])["reference_lineup"]["styles"]
        assert styles == [CYCLE_STYLES[(row["block_id"] + j) % 5] for j in range(k - 1)]


# ---------------------------------------------------------------- frozen research untouched
@pytest.mark.parametrize("rel", sorted(FROZEN_FILES))
def test_frozen_manifests_unchanged(rel):
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == FROZEN_FILES[rel]


# ---------------------------------------------------------------- analysis semantics
def _analysis_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("table_size_analysis", ROOT / "scripts" / "table_size_analysis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_analysis_detects_per_hand_invariance():
    """Synthetic suite with var(D) proportional to k: required played hands must be flat in
    table size (ratio to 6-max ~ 1, elasticity ~ 0) and required blocks must scale as 1/k."""
    ta = _analysis_module()
    rng = np.random.default_rng(0)
    data = {}
    for k in SEATS:
        for i, role in enumerate(ta.ROLES):
            n = 200_000
            D = rng.standard_normal(n) * math.sqrt(40.0 * (i + 1) * k)
            data[(k, role)] = {"exp": f"syn{k}", "pairing_id": f"{role}-x", "D": D, "played": np.full(n, 2.0 * k),
                               "k": float(k), "allin": np.zeros(n, int), "potmax": np.ones(n), "stack": 100.0,
                               "bps": 100.0}
    res = ta.analyse(data, reps=40)
    for k in (3, 4, 8):
        m = res["medians"][k]
        assert abs(m["hands_required_1bb100_rel_base"] - 1) < 0.02
        assert abs(m["blocks_required_1bb100_rel_base"] - 6 / k) < 0.02 * 6 / k
        for role in ta.ROLES:
            assert abs(res["rows"][(k, role)]["hands_required_1bb100_rel_base"] - 1) < 0.02
    assert abs(res["elasticity_hands_vs_seats"]["median"]["overall"]) < 0.02
    assert res["rows"][(6, "p1")]["hands_per_block"] == 12


def test_primary_curve_uses_only_controlled_corpora():
    ta = _analysis_module()
    assert {exp for _, exp in ta.SUITE.values()} == {f"fhr3a-nlhe{k}-100bb-tablesize-v1" for k in SEATS}
    assert not {exp for _, exp, _ in ta.HISTORICAL.values()} & {exp for _, exp in ta.SUITE.values()}
    assert all(p.startswith("configs/tablesize/") for p, _ in ta.SUITE.values())


def test_partial_analysis_cannot_write_frozen_location(monkeypatch):
    ta = _analysis_module()
    monkeypatch.setattr("sys.argv", ["x", "--allow-partial"])
    with pytest.raises(SystemExit, match="provisional"):
        ta.main()
