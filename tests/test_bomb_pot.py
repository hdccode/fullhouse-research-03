"""6-max NLHE Bomb Pot: forced antes, flop-first action, side pots, invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fhr3.agents.simple import RandomLegalAgent
from fhr3.estimators.allin_ev import expected_payoff
from fhr3.games import make_adapter
from fhr3.games.base import STANDARD_DECK, Action, GameConfig
from fhr3.rng import DecisionRNG, KeyedStream
from variant_invariants import check_core_invariants, check_serial_parallel_parquet, load


def bomb(k: int = 6, ante_bb: float = 2.0, stack_bb: float = 100):
    return make_adapter(GameConfig("bomb_pot", k, stack_bb, options={"ante_bb": ante_bb}))


def test_forced_antes_starting_pot_and_first_decision_on_flop():
    ad = bomb()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    obs = h.observation(h.actor())
    assert h.actor() == 0
    assert obs.street == 1 and len(obs.board) == 3 and obs.history == ()
    assert obs.stacks == (9800,) * 6 and obs.bets == (0,) * 6 and obs.pot == 1200
    la = h.legal_actions()
    assert not la.can_fold and la.call_amount == 0 and la.raise_min == 100 and la.raise_max == 9800
    assert h.trace_format == "json"


def test_board_order_and_split_when_board_plays():
    ad = bomb()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    while not h.is_terminal():
        h.apply(Action.check_call())
    o = h.outcome()
    # deck order: holes 2c..4s, burn 5c, flop 5d5h5s, burn 6c, turn 6d, burn 6h, river 6s
    assert o.board == ("5d", "5h", "5s", "6d", "6s") and o.payoffs_chips == (0,) * 6
    assert o.total_pot == 1200


def test_action_order_on_later_streets():
    ad = bomb(3)
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    seen = []
    while not h.is_terminal():
        seen.append((h.observation(h.actor()).street, h.actor()))
        h.apply(Action.check_call())
    assert seen == [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2), (3, 0), (3, 1), (3, 2)]


def test_options_validated():
    with pytest.raises(ValueError):
        bomb(ante_bb=100)  # ante must be below the stack
    with pytest.raises(ValueError):
        make_adapter(GameConfig("bomb_pot", 6, 100, ante_chips=100))
    with pytest.raises(ValueError):
        make_adapter(GameConfig("bomb_pot", 6, 100, options={"double_board": True}))


@settings(max_examples=50, deadline=None)
@given(seed=st.integers(0, 2**32), k=st.integers(2, 6), stacks=st.lists(st.integers(250, 30000), min_size=6, max_size=6))
def test_fuzz_side_pots_conservation_legality(seed, k, stacks):
    ad = bomb(k)
    h = ad.new_hand(ad.deal_from_deck(KeyedStream("bomb-fuzz", seed).shuffle(STANDARD_DECK)), starting_stacks=stacks[:k])
    assert h.observation(h.actor()).pot == 200 * k
    agent, n = RandomLegalAgent("r"), 0
    while not h.is_terminal():
        la = h.legal_actions()
        a = agent.act(h.observation(h.actor()), la, DecisionRNG("bf", seed, n))
        assert la.contains(a)
        h.apply(a)
        n += 1
    o = h.outcome()
    assert sum(o.payoffs_chips) == 0 and sum(o.final_stacks) == sum(stacks[:k])
    assert all(p <= s * (k - 1) and p >= -s for p, s in zip(o.payoffs_chips, stacks[:k]))


def test_allin_ev_exact_in_bomb_pot():
    ad = bomb(3)
    holes = ["AsKd", "QcQh", "7s8s"]
    flop, turn, burns = ("2s", "9s", "Jh"), "3c", ("4d", "5d")

    def play(river, burn3):
        hole = [h[i:i + 2] for h in holes for i in (0, 2)]
        runout = [burns[0], *flop, burns[1], turn, burn3, river]
        rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
        h = ad.new_hand(ad.deal_from_deck(hole + runout + rest), starting_stacks=(10000, 3000, 6000))
        for _ in range(3):  # flop checked around
            h.apply(Action.check_call())
        h.apply(Action.raise_to(h.legal_actions().raise_max))  # turn: seat 0 jams
        h.apply(Action.check_call())
        h.apply(Action.check_call())
        return h.outcome()

    snap = play("Kh", "6d").allin_snapshot
    assert snap is not None and len(snap.board) == 4
    pool = [c for c in STANDARD_DECK if c not in snap.dead]
    for seat in range(3):
        ev, _ = expected_payoff(snap, seat, "holdem", 10_000, 1, None)
        total = sum(play(r, next(c for c in pool if c != r)).payoffs_chips[seat] for r in pool)
        assert abs(ev * len(pool) - total) < 1e-6


def test_bomb_matched_invariants():
    check_core_invariants(load("bomb_6max_100bb.yaml"), range(10))


def test_bomb_serial_parallel_and_parquet(tmp_path):
    check_serial_parallel_parquet(load("bomb_6max_100bb.yaml"), tmp_path)
