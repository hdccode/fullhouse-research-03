"""PokerKit adapter: rules delegation, legality, pots, conservation."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fhr3.agents.simple import RandomLegalAgent
from fhr3.games.base import STANDARD_DECK, Action, ActionKind, IllegalActionError
from fhr3.rng import DecisionRNG, KeyedStream

from conftest import adapter, scripted_deal


def play_script(hand, script):
    for a in script:
        hand.apply(a)
    return hand


def check_down(hand):
    while not hand.is_terminal():
        hand.apply(Action.check_call())
    return hand.outcome()


def test_initial_legal_actions_6max():
    ad = adapter()
    deal = ad.deal_from_deck(STANDARD_DECK)
    h = ad.new_hand(deal)
    assert h.actor() == 2  # UTG acts first preflop; seat 0 SB, seat 1 BB
    la = h.legal_actions()
    assert la.can_fold and la.can_check_call and la.call_amount == 100
    assert la.raise_min == 200 and la.raise_max == 10000
    obs = h.observation(2)
    assert obs.hole_cards == deal.hole[2]
    assert obs.bets == (50, 100, 0, 0, 0, 0) and obs.pot == 150 and obs.board == ()


def test_fold_is_illegal_when_check_is_free():
    ad = adapter(3)
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    h.apply(Action.check_call())  # button limps
    h.apply(Action.check_call())  # SB completes
    assert h.actor() == 1
    la = h.legal_actions()
    assert not la.can_fold and la.call_amount == 0
    with pytest.raises(IllegalActionError):
        h.apply(Action.fold())


def test_illegal_raise_size_rejected():
    ad = adapter()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    with pytest.raises(IllegalActionError):
        h.apply(Action.raise_to(150))  # below min raise
    with pytest.raises(IllegalActionError):
        h.apply(Action.raise_to(10001))  # above stack


def test_side_pot_resolution():
    ad = adapter(3)
    deal = scripted_deal(ad, ["AsAh", "KsKh", "QsQh"], "2c3d7h9cJd")
    h = ad.new_hand(deal, starting_stacks=(10000, 3000, 10000))
    # seat 2 (button) jams, SB and BB call
    play_script(h, [Action.raise_to(10000), Action.check_call(), Action.check_call()])
    o = h.outcome()
    assert o.payoffs_chips == (13000, -3000, -10000)
    assert o.had_all_in and o.went_to_showdown and o.total_pot == 23000


def test_split_pot_when_board_plays():
    ad = adapter(3)
    deal = scripted_deal(ad, ["2s3s", "2h3h", "2d3d"], "AhKhQhJhTh")
    o = check_down(ad.new_hand(deal))
    assert o.payoffs_chips == (0, 0, 0)
    assert o.board == ("Ah", "Kh", "Qh", "Jh", "Th")


def test_multiway_showdown_winner_and_conservation():
    ad = adapter(6)
    deal = scripted_deal(ad, ["2s7d", "3c8d", "AsAh", "4c9h", "5dTc", "6h2c"], "AdKc8s3h2h")
    o = check_down(ad.new_hand(deal))
    assert o.payoffs_chips[2] == 500  # wins 5 x 1bb
    assert sum(o.payoffs_chips) == 0
    assert o.went_to_showdown and o.decision_count > 6


def test_board_uses_scripted_runout_order():
    ad = adapter(2)
    deal = scripted_deal(ad, ["AsAh", "KsKh"], "2c3d7h9cJd")
    o = check_down(ad.new_hand(deal))
    assert o.board == ("2c", "3d", "7h", "9c", "Jd")


@settings(max_examples=60, deadline=None)
@given(
    seed=st.integers(0, 2**32),
    k=st.integers(2, 6),
    stacks=st.lists(st.integers(150, 30000), min_size=6, max_size=6),
)
def test_fuzz_random_agents_conserve_chips_and_stay_legal(seed, k, stacks):
    ad = adapter(k)
    deck = KeyedStream("fuzz", seed).shuffle(STANDARD_DECK)
    h = ad.new_hand(ad.deal_from_deck(deck), starting_stacks=stacks[:k])
    agent = RandomLegalAgent("r")
    n = 0
    while not h.is_terminal():
        seat = h.actor()
        la = h.legal_actions()
        a = agent.act(h.observation(seat), la, DecisionRNG("fuzz", seed, n))
        assert la.contains(a)
        h.apply(a)
        n += 1
        assert n < 500
    o = h.outcome()
    assert sum(o.payoffs_chips) == 0
    assert sum(o.final_stacks) == sum(stacks[:k])
    assert all(p >= -s for p, s in zip(o.payoffs_chips, stacks[:k]))
    assert o.decision_count == n
    assert all(r.kind in ActionKind for r in o.history)


def test_phh_export_roundtrip_fields():
    ad = adapter(3)
    h = ad.new_hand(scripted_deal(ad, ["AsAh", "KsKh", "QsQh"], "2c3d7h9cJd"))
    check_down(h)
    text = h.to_phh(["x", "y", "z"], {"fhr3_block_id": 5})
    assert "variant = 'NT'" in text and "_fhr3_block_id = 5" in text
    assert "d dh p1 AsAh" in text
