"""FHR3A table-size sweep (NLHE 100BB at 3 / 4 / 6 / 8 seats): configs, block construction,
invariants and the guard that the frozen 4-/6-max corpora and manifests are untouched.

Design and population rule: docs/table_size.md.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from fhr3.agents.heuristic import HeuristicAgent
from fhr3.cli.main import main
from fhr3.configs.experiment import load_config
from fhr3.eval.matched import make_deal, reference_seats
from fhr3.eval.runner import BlockSimulator
from fhr3.games import make_adapter
from fhr3.games.base import Action
from fhr3.io.store import read_blocks
from fhr3.validation.corpus import rows_equal, validate_pairing

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"
SWEEP = {3: "nlhe_3max_100bb.yaml", 4: "nlhe_4max_100bb_v2.yaml", 6: "nlhe_6max_100bb.yaml", 8: "nlhe_8max_100bb.yaml"}
NEW = (3, 8)
PAIRINGS = ("p1-neutral-vs-loose10", "p2-neutral-vs-tight", "p3-aggressive-vs-neutral", "c0-selfplay-control")
DIVERGENT = PAIRINGS[:3]

# Pinned hashes. 4 and 6 are the frozen corpora's lock values: a change here means the
# reused corpora would no longer match their configs. 3 and 8 pin the new experiments.
PINNED = {
    3: ("fhr3-nlhe3-100bb-v1", "579e143783d086c7", {
        "p1-neutral-vs-loose10": "977da395648b8e30", "p2-neutral-vs-tight": "c02f9e38f144a4f6",
        "p3-aggressive-vs-neutral": "8ecc36ca1bbd9992", "c0-selfplay-control": "81adff0361fb903b"}),
    4: ("fhr3-nlhe4-100bb-v2", "ab7e279f1720c074", {
        "p1-neutral-vs-loose10": "c9611883f0df92dd", "p2-neutral-vs-tight": "2fab1924aa240919",
        "p3-aggressive-vs-neutral": "288544a16a8fd536", "c0-selfplay-control": "87ef4dd3c9d23cbe"}),
    6: ("fhr3-nlhe6-100bb-pilot-v1", "5f8886e193bc5489", {
        "p1-neutral-vs-loose10": "8271526be0009827", "p2-neutral-vs-tight": "7ccf8986402ec53f",
        "p3-aggressive-vs-neutral": "87abe185aa06c57a", "c0-selfplay-control": "a8faf06a963035ba"}),
    8: ("fhr3-nlhe8-100bb-v1", "389507f11e1692ab", {
        "p1-neutral-vs-loose10": "84167055446c4ef7", "p2-neutral-vs-tight": "dd624a8e514a67f0",
        "p3-aggressive-vs-neutral": "4d3c9a4892e0fa58", "c0-selfplay-control": "aafedcc07d3b7d4d"}),
}
# Frozen research outputs that the table-size work must never modify.
FROZEN_FILES = {
    "reports/final-analysis/MANIFEST.json": "2724469c22276f4d2406e69f0a1d8b2a01e34ad0a50338a2d853a91ca2877ddb",
    "reports/rq6/MANIFEST.json": "aee2b8477ab82270166b3bf8d636103e8145ecc43b3d6829ed9a6a4274653e93",
    "reports/rq7/MANIFEST.json": "3564b2e1bd1f1a10c294496d322d65af3cdce601aaa752ec507d93f86a231d0a",
    "paper/figures/final/build_manifest.json": "07388a0054b94c6add0760ae8eb0e7b86ece212dc95a3eddf96c0d7f21a221ed",
}
# D of p2 on blocks 0..7 (deterministic replay from the root seed, any process/machine)
GOLDEN_P2 = {3: [0.0, 1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5], 8: [0.0, -16.74, 0.0, 0.0, 0.0, 0.0, 0.0, 61.67]}


def cfg(k):
    return load_config(CONFIGS / SWEEP[k])


def styles(pairing):
    return [s.params["style"] for s in pairing.reference_seats]


# ---------------------------------------------------------------- configs and hashes
@pytest.mark.parametrize("k", sorted(SWEEP))
def test_config_and_pairing_hashes_pinned(k):
    c = cfg(k)
    eid, chash, phashes = PINNED[k]
    assert c.experiment_id == eid and c.game.player_count == k
    assert c.config_hash == chash
    assert {p.pairing_id: p.pairing_hash for p in c.pairings} == phashes


def test_sweep_differs_only_in_table_size_and_population():
    cs = {k: cfg(k) for k in SWEEP}
    base = cs[6]
    for k, c in cs.items():
        assert c.environment()["game"] | {"player_count": 0} == base.environment()["game"] | {"player_count": 0}
        assert c.root_seed == base.root_seed and c.rng.to_dict() == base.rng.to_dict()
        assert [p.pairing_id for p in c.pairings] == list(PAIRINGS)
        for p, b in zip(c.pairings, base.pairings, strict=True):
            # identical candidate specs and implementation versions at every table size
            assert p.resolved()["candidate_a"] == b.resolved()["candidate_a"]
            assert p.resolved()["candidate_b"] == b.resolved()["candidate_b"]
            assert len(p.reference_seats) == k - 1
        assert len({p.reference_population for p in c.pairings}) == 1  # one population per table size


def test_reference_population_rule():
    pops = {k: styles(cfg(k).pairings[0]) for k in SWEEP}
    assert pops[3] == ["tight", "loose"]
    assert pops[4] == ["tight", "loose", "aggressive"]
    assert pops[6] == ["tight", "neutral", "loose", "aggressive", "neutral"]
    assert pops[8] == ["tight", "neutral", "loose", "aggressive", "neutral", "neutral", "neutral"]
    for k in (4, 6, 8):  # each non-neutral style exactly once, neutral filler
        non_neutral = sorted(s for s in pops[k] if s != "neutral")
        assert non_neutral == ["aggressive", "loose", "tight"]
    assert pops[3] == pops[4][:2]  # 3-max: prefix of the 4-max population
    assert pops[8][:5] == pops[6]  # 8-max: 6-max population + appended neutral seats
    for k in SWEEP:  # reference seats carry no overrides (pure styles)
        assert all(set(s.params) == {"style"} for s in cfg(k).pairings[0].reference_seats)


# ---------------------------------------------------------------- game instantiation
@pytest.mark.parametrize("k", NEW)
def test_game_instantiation_and_deal(k):
    ad = make_adapter(cfg(k).game)
    assert ad.cards_per_deal() == 2 * k + 8 and ad.deal_layout == f"board-h2-k{k}"
    deal = make_deal(ad, 12345)
    cards = [c for h in deal.hole for c in h] + list(deal.runout)
    assert len(deal.hole) == k and len(cards) == len(set(cards)) == 2 * k + 8
    h = ad.new_hand(deal)
    obs = h.observation(h.actor())
    assert obs.player_count == k
    assert obs.bets == (50, 100) + (0,) * (k - 2)
    assert obs.stacks == (10000 - 50, 10000 - 100) + (10000,) * (k - 2)


@pytest.mark.parametrize("k", NEW)
def test_blind_and_action_order(k):
    """Seat 0 = SB, 1 = BB, k-1 = button. Preflop starts at seat 2 (the button at 3-max, UTG at
    8-max); folding round leaves the BB winning the SB; postflop starts at the SB."""
    ad = make_adapter(cfg(k).game)
    deal = make_deal(ad, 7)
    h = ad.new_hand(deal)
    order = []
    while not h.is_terminal():
        order.append(h.actor())
        h.apply(Action.fold())
    assert order == list(range(2, k)) + [0]
    assert h.outcome().payoffs_chips == (-50, 50) + (0,) * (k - 2)
    # limp around: flop is opened by the small blind
    h = ad.new_hand(deal)
    pre = []
    while h.observation(h.actor()).street == 0:
        pre.append(h.actor())
        h.apply(Action.check_call())
    assert pre == list(range(2, k)) + [0, 1]
    assert h.actor() == 0


@pytest.mark.parametrize("k", NEW)
def test_heuristic_positional_mapping_generalises(k):
    """The agent opens by 'seats behind' (button = 0). Its table must cover every
    non-blind seat without clipping, and the unopened-pot raise probability at every
    seat must follow that rule (SB uses sb_open_pct). No agent code is seat-count specific."""
    ag = HeuristicAgent("n", "neutral")
    table = ag.p.open_pct_by_seats_behind
    assert k - 1 - 2 < len(table)  # UTG has k-3 seats behind: no clipping up to 10-max
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


# ---------------------------------------------------------------- matched blocks
class Recorder:
    def __init__(self, inner, log, tag):
        self.inner, self.log, self.tag = inner, log, tag
        self.agent_id, self.version = inner.agent_id, inner.version

    def act(self, obs, legal, rng):
        self.log.append((self.tag, obs.seat, obs.hole_cards))
        return self.inner.act(obs, legal, rng)


@pytest.mark.parametrize("k", NEW)
def test_candidate_seat_rotation_and_reference_fill(k):
    c = cfg(k)
    sim = BlockSimulator(c, c.pairing("p2-neutral-vs-tight"))
    log: list = []
    sim.a, sim.b = Recorder(sim.a, log, "A"), Recorder(sim.b, log, "B")
    sim.refs = [Recorder(r, log, f"r{j}") for j, r in enumerate(sim.refs)]
    for b in range(6):
        log.clear()
        r = sim.run(b)
        assert r.valid and r.played_hands == 2 * k and len(r.seat_D) == k
        assert [h.candidate_seat for h in r.hands] == [s for s in range(k) for _ in "AB"]
        assert [h.side for h in r.hands] == ["A", "B"] * k
        deal = make_deal(sim.adapter, sim.spec(b).seed)
        assert all(hole == deal.hole[seat] for _, seat, hole in log)
        for side in "AB":
            assert {seat for tag, seat, _ in log if tag == side} <= set(range(k))
        for j in range(k - 1):
            assert {seat for tag, seat, _ in log if tag == f"r{j}"} <= {reference_seats(k, s)[j] for s in range(k)}
    assert reference_seats(k, 0) == list(range(1, k))
    assert reference_seats(k, k - 1) == list(range(0, k - 1))


@pytest.mark.parametrize("k", NEW)
def test_matched_block_reproducible_and_golden(k):
    c = cfg(k)
    p = c.pairing("p2-neutral-vs-tight")
    s1, s2 = BlockSimulator(c, p), BlockSimulator(c, p)
    for b in range(8):
        assert rows_equal(s1.row(s1.run(b), "r", False), s2.row(s2.run(b), "r", False)) == []
    assert [round(s1.run(b).D, 6) for b in range(8)] == GOLDEN_P2[k]


@pytest.mark.parametrize("k", NEW)
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
    assert moved > 0  # the zero is cancellation, not inactivity


@pytest.mark.parametrize("k", NEW)
@pytest.mark.parametrize("pid", DIVERGENT)
def test_every_non_control_pairing_diverges(k, pid):
    """Divergence guard (cf. the Bomb Pot audit): each non-control pairing must produce
    D != 0 in a non-trivial share of blocks, otherwise its sigma_D is not measuring anything."""
    c = cfg(k)
    sim = BlockSimulator(c, c.pairing(pid))
    D = np.array([sim.run(b).D for b in range(100)])
    assert np.isfinite(D).all()
    assert (D != 0).sum() >= 5, f"{pid} at {k}-max diverged in only {(D != 0).sum()}/100 blocks"


# ---------------------------------------------------------------- smoke via the CLI
@pytest.mark.parametrize("k", NEW)
def test_cli_smoke_corpus_valid(k, tmp_path):
    c = cfg(k)
    out = tmp_path / "results"
    args = ["simulate", "--config", str(CONFIGS / SWEEP[k]), "--blocks", "0:12", "--chunk-size", "6",
            "--out", str(out), "--no-traces"]
    assert main(args) == 0
    assert main(args) == 0  # resume: nothing left to do, no duplicates
    for pid in PAIRINGS:
        rep = validate_pairing(c, out, pid, expected=(0, 12), replay=3)
        assert rep["ok"], rep["problems"]
    t = read_blocks(out / c.experiment_id)
    assert t.num_rows == 12 * len(PAIRINGS)
    D = t.column("D").to_numpy(zero_copy_only=False).astype(float)
    assert np.isfinite(D).all() and all(t.column("valid").to_pylist())
    assert set(t.column("played_hands").to_pylist()) == {2 * k}
    assert set(t.column("config_hash").to_pylist()) == {PINNED[k][1]}


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
    """Synthetic sweep with var(D) proportional to k: required played hands must be flat in
    table size (ratio to 6-max ~ 1, elasticity ~ 0); blocks must scale as 1/k."""
    ta = _analysis_module()
    rng = np.random.default_rng(0)
    data = {}
    for k in (3, 4, 6, 8):
        for i, role in enumerate(ta.ROLES):
            n = 200_000
            D = rng.standard_normal(n) * math.sqrt(40.0 * (i + 1) * k)
            data[(k, role)] = {"exp": f"syn{k}", "pairing_id": f"{role}-x", "D": D, "played": np.full(n, 2.0 * k),
                               "k": float(k), "allin": np.zeros(n, int), "potmax": np.ones(n), "stack": 100.0,
                               "bps": 100.0}
    res = ta.analyse(data, reps=40)
    for k in (3, 4, 8):
        m = res["medians"][k]
        assert abs(m["hands_required_1bb100_rel_6max"] - 1) < 0.02
        assert abs(m["blocks_required_1bb100_rel_6max"] - 6 / k) < 0.02 * 6 / k
        for role in ta.ROLES:
            assert abs(res["rows"][(k, role)]["hands_required_1bb100_rel_6max"] - 1) < 0.02
    assert abs(res["elasticity_hands_vs_seats"]["median"]["overall"]) < 0.02
    assert res["rows"][(6, "p1")]["hands_per_block"] == 12


def test_partial_analysis_cannot_write_frozen_location(monkeypatch):
    ta = _analysis_module()
    monkeypatch.setattr("sys.argv", ["x", "--allow-partial"])
    with pytest.raises(SystemExit, match="provisional"):
        ta.main()
