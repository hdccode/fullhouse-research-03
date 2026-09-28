"""6-max Nit Game: persistent-state transitions, block independence, invariants."""

from __future__ import annotations

import copy

import pytest
import yaml

from fhr3.agents import AgentSpec, build_agent
from fhr3.configs.experiment import RNGConfig, config_from_dict
from fhr3.eval.matched import (
    MatchedBlockSpec,
    make_deal,
    nit_resolution,
    nit_update_buttons,
    run_matched_block,
)
from fhr3.eval.runner import BlockSimulator
from fhr3.games import make_adapter
from fhr3.games.base import GameConfig
from variant_invariants import CONFIGS, check_core_invariants, check_serial_parallel_parquet, load


# ---------------------------------------------------------------- pure transitions
def test_button_update_only_on_positive_result():
    assert nit_update_buttons([False] * 4, [0, -100, 150, -50]) == [False, False, True, False]
    assert nit_update_buttons([True, False, False, False], [-10, 0, 0, 10]) == [True, False, False, True]


def test_resolution_rules_and_zero_sum():
    assert nit_resolution([True, False, False, True], 5) == (False, None, [0.0] * 4)
    over, nit, tr = nit_resolution([True, True, False, True], 5)
    assert over and nit == 2 and tr == [5.0, 5.0, -15.0, 5.0] and sum(tr) == 0
    assert nit_resolution([True] * 4, 5) == (True, None, [0.0] * 4)  # last two won together


# ---------------------------------------------------------------- protocol semantics
class Recorder:
    def __init__(self, inner, log, tag):
        self.inner, self.log, self.tag = inner, log, tag
        self.agent_id, self.version = inner.agent_id, inner.version

    def act(self, obs, legal, rng):
        self.log.append((self.tag, obs.extra.get("nit_hand_index"), obs.seat, obs.hole_cards, obs.extra.get("nit_buttons")))
        return self.inner.act(obs, legal, rng)


def nit_adapter(k=6, **opts):
    return make_adapter(GameConfig("nit_game", k, 100, options={"nit_penalty_bb": 5, **opts}))


def agents(k):
    mk = lambda i, st="neutral": build_agent(AgentSpec(f"x{i}", "nit_heuristic", {"style": st}))  # noqa: E731
    return mk("A", "aggressive"), mk("B"), [mk(j) for j in range(k - 1)]


def test_initial_state_is_empty_and_buttons_accumulate():
    k, log = 6, []
    a, b, refs = agents(k)
    ad = nit_adapter(k)
    r = run_matched_block(MatchedBlockSpec("e", "c", "p", "ph", 1, 3, RNGConfig()), ad,
                          Recorder(a, log, "A"), Recorder(b, log, "B"), refs)
    assert r.valid and r.protocol == "fhr3-nit-round-v1"
    firsts = [e for e in log if e[1] == 0]
    assert firsts and all(e[4] == (False,) * k for e in firsts)  # every round starts empty
    assert any(h > 0 for _, h, _, _, _ in log)  # rounds last more than one hand


def test_dealer_rotation_and_candidate_position():
    k, log = 6, []
    a, b, refs = agents(k)
    ad = nit_adapter(k)
    run_matched_block(MatchedBlockSpec("e", "c", "p", "ph", 1, 5, RNGConfig()), ad,
                      Recorder(a, log, "A"), b, refs)
    # candidate A plays seat s = 0..5 in order; within each round position = (s - h) mod k
    s, prev_h = -1, None
    for _, h, pos, _, _ in log:
        if h == 0 and prev_h != 0:
            s += 1
        assert pos == (s - h) % k
        prev_h = h


def test_a_and_b_rounds_share_the_deal_of_each_hand_index():
    k, log = 6, []
    a, b, refs = agents(k)
    ad = nit_adapter(k)
    spec = MatchedBlockSpec("e", "c", "p", "ph", 1, 8, RNGConfig())
    run_matched_block(spec, ad, Recorder(a, log, "A"), Recorder(b, log, "B"), refs)
    for _tag, h, pos, hole, _ in log:
        assert hole == make_deal(ad, spec.seed, 0, hand_index=h).hole[pos]


def test_seat_payoff_equals_hand_sum_plus_transfer_and_truncation():
    cfg = load("nit_6max_100bb.yaml")
    sim = BlockSimulator(cfg, cfg.pairing("p3-aggressive-vs-neutral"))
    for b in range(6):
        r = sim.run(b)
        info = r.variant_info["nit"]
        for side, seat_pay in (("A", r.seat_payoff_a), ("B", r.seat_payoff_b)):
            for s in range(6):
                hands = [h.payoff_bb for h in r.hands if h.side == side and h.candidate_seat == s]
                assert len(hands) == info["round_hands"][side][s]
                assert abs(sum(hands) + info["candidate_transfer_bb"][side][s] - seat_pay[s]) < 1e-9
                assert info["candidate_transfer_bb"][side][s] in (0.0, 5.0, -25.0)
    # with max_hands = 1 every unresolved round is truncated without a payment
    raw = yaml.safe_load((CONFIGS / "nit_6max_100bb.yaml").read_text())
    raw2 = copy.deepcopy(raw)
    raw2["game"]["options"]["max_hands"] = 1
    cfg1 = config_from_dict(raw2)
    r = BlockSimulator(cfg1, cfg1.pairing("p3-aggressive-vs-neutral")).run(0)
    info = r.variant_info["nit"]
    assert all(n == 1 for side in "AB" for n in info["round_hands"][side])
    assert info["truncated"]["A"] == 6 and all(t == 0.0 for t in info["candidate_transfer_bb"]["A"])


def test_blocks_are_independent_of_execution_history():
    cfg = load("nit_6max_100bb.yaml")
    fresh = BlockSimulator(cfg, cfg.pairing("p2-neutral-vs-tight")).run(7)
    used = BlockSimulator(cfg, cfg.pairing("p2-neutral-vs-tight"))
    for b in range(4):
        used.run(b)
    again = used.run(7)
    assert fresh.D == again.D and fresh.seat_payoff_a == again.seat_payoff_a
    assert fresh.variant_info == again.variant_info


def test_nit_options_validated():
    with pytest.raises(ValueError):
        nit_adapter(bogus=1)
    with pytest.raises(ValueError):
        nit_adapter(max_hands=0)


def test_nit_matched_invariants():
    diag = check_core_invariants(load("nit_6max_100bb.yaml"), range(6))
    assert diag["hands"] > 12 * 6  # multi-hand rounds


def test_nit_serial_parallel_and_parquet(tmp_path):
    check_serial_parallel_parquet(load("nit_6max_100bb.yaml"), tmp_path, n=2)
