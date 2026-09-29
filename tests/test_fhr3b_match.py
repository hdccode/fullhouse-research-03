"""FHR3B table matches: 2026 dealer/bust mechanics on FHR3 adapters, keyed randomness."""

from __future__ import annotations

import pytest

from fhr3.agents import AgentSpec, build_agent
from fhr3.games.base import GameConfig
from fhr3.tournament.match import (
    MatchKey,
    PokerMatchPlayer,
    SyntheticMatchPlayer,
    dealer_positions,
    zero_sum_integers,
)

STYLES = ["neutral", "tight", "loose", "aggressive", "neutral", "tight"]


def _agents(n, kind="heuristic"):
    return {f"b{i}": build_agent(AgentSpec(f"b{i}", kind, {"style": STYLES[i % 4]})) for i in range(n)}


def test_dealer_positions_follow_2026_counter():
    alive = ["a", "b", "c", "d"]
    # hand 0: dealer = a -> SB b, BB c, then d, button a
    assert dealer_positions(alive, 0) == ["b", "c", "d", "a"]
    assert dealer_positions(alive, 1) == ["c", "d", "a", "b"]
    assert dealer_positions(alive, 5) == dealer_positions(alive, 1)
    # heads-up: FHR3/PokerKit position 1 = button = SB = 2026 dealer; position 0 = BB
    assert dealer_positions(["x", "y"], 0) == ["y", "x"]
    assert dealer_positions(["x", "y"], 1) == ["x", "y"]


def test_heads_up_button_posts_small_blind_and_acts_first():
    from fhr3.games import make_adapter
    from fhr3.games.base import STANDARD_DECK
    from fhr3.rng import KeyedStream

    a = make_adapter(GameConfig("nlhe", 2, 100.0))
    h = a.new_hand(a.deal_from_deck(KeyedStream("t", 1).shuffle(STANDARD_DECK)))
    obs = h.observation(h.actor())
    assert h.actor() == 1 and obs.bets == (100, 50)


def test_persistent_match_conserves_chips_and_scores_are_stack_deltas():
    mp = PokerMatchPlayer(GameConfig("nlhe", 6, 100.0), "persistent_no_rebuy", _agents(6))
    res = mp.play(MatchKey(1, 2, 1, 0), [f"b{i}" for i in range(6)], 150)
    assert sum(res.deltas.values()) == 0
    assert all(d >= -10000 for d in res.deltas.values())
    for b, h in res.bust_hand.items():
        if h >= 0:
            assert res.deltas[b] == -10000


def test_persistent_match_ends_early_when_one_bot_has_all_chips():
    agents = {"a": build_agent(AgentSpec("a", "random", {})), "b": build_agent(AgentSpec("b", "random", {}))}
    mp = PokerMatchPlayer(GameConfig("nlhe", 2, 2.0), "persistent_no_rebuy", agents)
    res = mp.play(MatchKey(3, 4, 1, 0), ["a", "b"], 500)
    assert res.hands_played < 500
    assert sorted(res.deltas.values()) == [-200, 200]


def test_match_hand_prefix_does_not_depend_on_match_length():
    mp = PokerMatchPlayer(GameConfig("nlhe", 6, 100.0), "persistent_no_rebuy", _agents(6))
    short, long_ = [], []
    mp.play(MatchKey(5, 6, 2, 3), [f"b{i}" for i in range(6)], 20, hand_log=short)
    mp.play(MatchKey(5, 6, 2, 3), [f"b{i}" for i in range(6)], 40, hand_log=long_)
    assert long_[:20] == short


def test_match_is_deterministic_and_keyed():
    mp = PokerMatchPlayer(GameConfig("nlhe", 6, 100.0), "persistent_no_rebuy", _agents(6))
    seats = [f"b{i}" for i in range(6)]
    a = mp.play(MatchKey(7, 8, 1, 0), seats, 30).deltas
    assert a == mp.play(MatchKey(7, 8, 1, 0), seats, 30).deltas
    assert a != mp.play(MatchKey(7, 8, 1, 1), seats, 30).deltas


@pytest.mark.parametrize("variant,n,stack_bb,kind,policy,options", [
    ("nlhe", 4, 100, "heuristic", "persistent_no_rebuy", {}),
    ("plo", 6, 100, "plo_heuristic", "persistent_no_rebuy", {}),
    ("crazy_pineapple", 6, 100, "cp_heuristic", "persistent_no_rebuy", {}),
    ("aof", 4, 8, "aof_heuristic", "reset_each_hand", {}),
    ("bomb_pot", 6, 100, "heuristic", "reset_each_hand", {"ante_bb": 2}),
    ("nit_game", 6, 100, "nit_heuristic", "reset_each_hand", {"nit_penalty_bb": 5, "max_hands": 60}),
])
def test_every_mode_plays_a_zero_sum_match(variant, n, stack_bb, kind, policy, options):
    game = GameConfig(variant, n, float(stack_bb), options=options)
    mp = PokerMatchPlayer(game, policy, _agents(n, kind))
    res = mp.play(MatchKey(11, 12, 1, 0), [f"b{i}" for i in range(n)], 30)
    assert sum(res.deltas.values()) == 0 and res.hands_played == 30
    if variant == "nit_game":
        assert res.info["nit_rounds"] >= 1


def test_persistent_rejected_for_nit_game():
    with pytest.raises(ValueError):
        PokerMatchPlayer(GameConfig("nit_game", 6, 100.0), "persistent_no_rebuy", _agents(6))


def test_zero_sum_integers_and_synthetic_player():
    vals = zero_sum_integers([0.4, 0.4, 0.4, -1.2, 3.3])
    assert sum(vals) == 0
    sp = SyntheticMatchPlayer({"a": 1.0, "b": 0.0, "c": -1.0}, noise_sd=0.0)
    res = sp.play(MatchKey(1, 1, 1, 0), ["a", "b", "c"], 100)
    assert res.deltas == {"a": 100, "b": 0, "c": -100}
