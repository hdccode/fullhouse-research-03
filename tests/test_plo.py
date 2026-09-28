"""6-max Pot-Limit Omaha: rules delegation, exact-card use, invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fhr3.agents import AgentSpec, build_agent
from fhr3.agents.omaha_features import omaha_preflop_percentile
from fhr3.agents.simple import RandomLegalAgent
from fhr3.estimators.allin_ev import expected_payoff
from fhr3.games import make_adapter
from fhr3.games.base import STANDARD_DECK, Action, GameConfig
from fhr3.rng import DecisionRNG, KeyedStream
from variant_invariants import check_core_invariants, check_serial_parallel_parquet, load


def plo(k: int = 6):
    return make_adapter(GameConfig("plo", k, 100))


def deal_for(ad, holes, board, burns=("2d", "3d", "4d")):
    hole = [h[i:i + 2] for h in holes for i in range(0, 8, 2)]
    b = [board[i:i + 2] for i in range(0, 10, 2)]
    runout = [burns[0], *b[:3], burns[1], b[3], burns[2], b[4]]
    rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
    return ad.deal_from_deck(hole + runout + rest)


def check_down(h):
    while not h.is_terminal():
        h.apply(Action.check_call())
    return h.outcome()


def test_four_hole_cards_and_pot_limit_bounds():
    ad = plo()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    assert all(len(h.observation(s).hole_cards) == 4 for s in range(6))
    la = h.legal_actions()
    # UTG: call 100, pot = 150 + 100 -> raise to 100 + 250 = 350 (pot limit)
    assert la.call_amount == 100 and la.raise_min == 200 and la.raise_max == 350
    h.apply(Action.raise_to(350))
    # HJ facing 350: call 350 -> pot 850 -> max raise to 350 + 850 = 1200
    assert h.legal_actions().raise_max == 1200
    assert ad.deal_layout == "board-h4-k6"


def test_omaha_exact_card_use_decides_showdown():
    ad = plo(2)
    board = "AhKhQhJh2c"
    # seat 0: a single heart (Th) -> Hold'em royal, Omaha high card
    # seat 1: two hearts (9h8h) -> Omaha flush
    o = check_down(ad.new_hand(deal_for(ad, ["Th3c4d5s", "9h8h7c6d"], board, burns=("2s", "3s", "4s"))))
    assert o.payoffs_chips[1] > 0 and o.payoffs_chips[0] < 0


def test_omaha_board_full_house_does_not_play():
    ad = plo(2)
    # board AAAKK: Hold'em would chop; Omaha seat 0 (KK in hand) makes quads-free KKK AA? -> K K + AAA = full house
    o = check_down(ad.new_hand(deal_for(ad, ["Kc2c3c4c", "5d6d7d8d"], "AsAhAdKsKh", burns=("9s", "9h", "9d"))))
    assert o.payoffs_chips[0] > 0


def test_omaha_split_pot():
    ad = plo(2)
    # both players hold A+T: Broadway (AKQJT) using exactly two hole cards each
    o = check_down(ad.new_hand(deal_for(ad, ["AsTc3c4c", "AdTd5h6h"], "KdQcJs2h7s", burns=("9s", "9h", "9d"))))
    assert o.payoffs_chips == (0, 0)


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 2**32), k=st.integers(2, 6), stacks=st.lists(st.integers(150, 30000), min_size=6, max_size=6))
def test_fuzz_conservation_side_pots_and_legality(seed, k, stacks):
    ad = plo(k)
    h = ad.new_hand(ad.deal_from_deck(KeyedStream("plo-fuzz", seed).shuffle(STANDARD_DECK)), starting_stacks=stacks[:k])
    agent, n = RandomLegalAgent("r"), 0
    while not h.is_terminal():
        la = h.legal_actions()
        a = agent.act(h.observation(h.actor()), la, DecisionRNG("f", seed, n))
        assert la.contains(a)
        h.apply(a)
        n += 1
    o = h.outcome()
    assert sum(o.payoffs_chips) == 0 and sum(o.final_stacks) == sum(stacks[:k])


def test_allin_ev_omaha_exact_matches_pokerkit_rivers():
    ad = plo(2)
    holes, flop, turn = ["AsKsQd2c", "JhTh9c8c"], "Kh9h4s", "5d"
    burns = ("2d", "3d")
    script = [Action.check_call()] * 4  # heads-up: preflop call/check, flop check/check

    def play(river, burn3):
        hole = [h[i:i + 2] for h in holes for i in range(0, 8, 2)]
        runout = [burns[0], flop[0:2], flop[2:4], flop[4:6], burns[1], turn, burn3, river]
        rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
        h = ad.new_hand(ad.deal_from_deck(hole + runout + rest), starting_stacks=(10000, 2000))
        for a in script:
            h.apply(a)
        # turn: pot-raise back and forth until the 2000-chip stack is all-in, then call
        while not h.is_terminal():
            la = h.legal_actions()
            h.apply(Action.raise_to(la.raise_max) if la.can_raise else Action.check_call())
        return h.outcome()

    snap = play("7c", "6c").allin_snapshot
    assert snap is not None and len(snap.board) == 4
    pool = [c for c in STANDARD_DECK if c not in snap.dead]
    for seat in (0, 1):
        ev, method = expected_payoff(snap, seat, "omaha", 10_000, 1, None)
        total = sum(play(r, next(c for c in pool if c != r)).payoffs_chips[seat] for r in pool)
        assert method == "exact" and abs(ev * len(pool) - total) < 1e-6


def test_preflop_percentile_orders_classic_hands():
    assert omaha_preflop_percentile(("As", "Ah", "Ks", "Kh")) > 0.97
    assert omaha_preflop_percentile(("As", "Ah", "Ks", "Kh")) > omaha_preflop_percentile(("Jc", "Th", "9s", "8d"))
    assert omaha_preflop_percentile(("2c", "7d", "9h", "Ks")) < 0.3


@pytest.mark.parametrize("style", ["neutral", "tight", "loose", "aggressive"])
def test_plo_agent_distributions_legal(style):
    ad = plo()
    agents = [build_agent(AgentSpec(f"a{i}", "plo_heuristic", {"style": style})) for i in range(6)]
    for b in range(25):
        h = ad.new_hand(ad.deal_from_deck(KeyedStream("plo-ag", b).shuffle(STANDARD_DECK)))
        n = 0
        while not h.is_terminal():
            seat = h.actor()
            obs, la = h.observation(seat), h.legal_actions()
            dist = agents[seat].action_distribution(obs, la)
            assert abs(sum(p for _, p in dist) - 1) < 1e-9 and all(la.contains(a) for a, _ in dist)
            h.apply(agents[seat].act(obs, la, DecisionRNG("p", b, n)))
            n += 1


def test_plo_matched_invariants():
    diag = check_core_invariants(load("plo_6max_100bb.yaml"), range(12))
    assert diag["hands"] == 12 * 12


def test_plo_serial_parallel_and_parquet(tmp_path):
    check_serial_parallel_parquet(load("plo_6max_100bb.yaml"), tmp_path)
