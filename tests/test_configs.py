"""Shipped experiment configs: loadability, cross-config matching, invariants per format."""

from pathlib import Path

import pytest

from fhr3.configs.experiment import load_config
from fhr3.eval.matched import make_deal
from fhr3.eval.runner import BlockSimulator
from fhr3.games import make_adapter

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
STACK_SERIES = ["nlhe_6max_20bb.yaml", "nlhe_6max_50bb.yaml", "nlhe_6max_100bb.yaml"]
ALL = sorted(p.name for p in CONFIGS.glob("*.yaml"))


def test_all_configs_load_with_distinct_ids_and_hashes():
    cfgs = [load_config(CONFIGS / n) for n in ALL]
    assert len({c.experiment_id for c in cfgs}) == len(cfgs)
    assert len({c.config_hash for c in cfgs}) == len(cfgs)


def test_stack_series_differs_only_in_stack_and_id():
    cfgs = [load_config(CONFIGS / n) for n in STACK_SERIES]
    base = cfgs[-1]
    for c in cfgs[:-1]:
        env, benv = c.environment(), base.environment()
        assert env["game"] | {"stack_bb": 0} == benv["game"] | {"stack_bb": 0}
        assert env["root_seed"] == benv["root_seed"] and env["rng"] == benv["rng"]
        assert [p.pairing_hash for p in c.pairings] == [p.pairing_hash for p in base.pairings]
    assert [c.game.stack_bb for c in cfgs] == [20, 50, 100]


def test_stack_series_shares_decks_per_block():
    cfgs = [load_config(CONFIGS / n) for n in STACK_SERIES]
    sims = [BlockSimulator(c, c.pairings[0]) for c in cfgs]
    for b in range(10):
        assert len({s.spec(b).seed for s in sims}) == 1
        assert len({make_deal(s.adapter, s.spec(b).seed) for s in sims}) == 1


def test_4max_uses_same_candidates_as_6max():
    c4 = load_config(CONFIGS / "nlhe_4max_100bb.yaml")
    c6 = load_config(CONFIGS / "nlhe_6max_100bb.yaml")
    assert c4.game.player_count == 4
    assert all(len(p.reference_seats) == 3 for p in c4.pairings)
    for p4, p6 in zip(c4.pairings, c6.pairings, strict=True):
        assert p4.pairing_id == p6.pairing_id
        assert p4.resolved()["candidate_a"] == p6.resolved()["candidate_a"]
        assert p4.resolved()["candidate_b"] == p6.resolved()["candidate_b"]


@pytest.mark.parametrize("name", ["nlhe_4max_100bb.yaml", "nlhe_6max_20bb.yaml", "nlhe_6max_50bb.yaml"])
def test_invariants_hold_for_new_formats(name):
    cfg = load_config(CONFIGS / name)
    k = cfg.game.player_count
    control = BlockSimulator(cfg, cfg.pairing("c0-selfplay-control"))
    ab = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))
    # swapped pairing built from the same objects
    ba = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))
    ba.a, ba.b = ab.b, ab.a
    nonzero = allins = 0
    for b in range(15):
        c = control.run(b)
        assert c.valid and c.D == 0.0 and c.played_hands == 2 * k
        r, s = ab.run(b), ba.run(b)
        assert r.valid and s.valid, (r.error_detail, s.error_detail)
        assert r.D == -s.D and r.seat_D == [-x for x in s.seat_D]
        nonzero += r.D != 0
        allins += sum(h.all_in for h in r.hands)
    assert nonzero > 0
    if cfg.game.stack_bb == 20:
        assert allins > 0  # short stacks must actually exercise all-in paths


def test_adapter_respects_stack_depth():
    cfg = load_config(CONFIGS / "nlhe_6max_20bb.yaml")
    ad = make_adapter(cfg.game)
    h = ad.new_hand(make_deal(ad, 1))
    assert h.legal_actions().raise_max == 2000
