"""6-max Crazy Pineapple: discard timing/sequencing, showdown on kept cards, invariants.

Independent oracles (no external CP implementation is available offline):
* a sequencing oracle over the recorded event log (discards strictly after all
  flop betting, before any turn action, by exactly the live seats in order);
* a showdown oracle recomputing winners from the kept cards with our evaluator.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fhr3.agents import AgentSpec, build_agent
from fhr3.agents.simple import RandomLegalAgent
from fhr3.estimators.allin_ev import expected_payoff
from fhr3.games import make_adapter
from fhr3.games.base import STANDARD_DECK, Action, ActionKind, GameConfig, IllegalActionError, LegalDiscards
from fhr3.games.evaluator import rank_holdem
from fhr3.rng import DecisionRNG, KeyedStream
from variant_invariants import check_core_invariants, check_serial_parallel_parquet, load


def cp(k: int = 6):
    return make_adapter(GameConfig("crazy_pineapple", k, 100))


def deal_for(ad, holes, board, burns=("2d", "3d", "4d")):
    hole = [h[i:i + 2] for h in holes for i in range(0, 6, 2)]
    b = [board[i:i + 2] for i in range(0, 10, 2)]
    runout = [burns[0], *b[:3], burns[1], b[3], burns[2], b[4]]
    rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
    return ad.deal_from_deck(hole + runout + rest)


def test_three_hole_cards_and_layout():
    ad = cp()
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    assert all(len(h.observation(s).hole_cards) == 3 for s in range(6))
    assert ad.deal_layout == "board-h3-k6" and h.trace_format == "json"


def test_discard_after_flop_betting_before_turn_in_seat_order():
    ad = cp(3)
    h = ad.new_hand(deal_for(ad, ["AsAh2c", "KsKh3d", "QsQh4h"], "7c8d9hTsJc", burns=("5c", "5d", "5h")))
    for _ in range(3):  # preflop: BTN call, SB complete, BB check
        h.apply(Action.check_call())
    assert len(h.observation(0).board) == 3 and not isinstance(h.legal_actions(), LegalDiscards)
    h.apply(Action.raise_to(300))  # flop: SB bets
    h.apply(Action.fold())  # BB folds
    assert not isinstance(h.legal_actions(), LegalDiscards)  # flop betting still open
    h.apply(Action.check_call())  # BTN calls -> flop round over
    la = h.legal_actions()
    assert isinstance(la, LegalDiscards) and h.actor() == 0  # SB first; BB folded -> skipped
    obs = h.observation(0)
    assert len(obs.hole_cards) == 3 and len(obs.board) == 3 and obs.street == 1
    h.apply(Action.discard("2c"))
    assert h.actor() == 2 and isinstance(h.legal_actions(), LegalDiscards)
    h.apply(Action.discard("4h"))
    assert not isinstance(h.legal_actions(), LegalDiscards)
    assert len(h.observation(2).board) == 4 and h.observation(2).street == 2
    assert h.observation(0).hole_cards == ("As", "Ah") and h.observation(2).hole_cards == ("Qs", "Qh")
    discards = [r for r in h._history if r.kind is ActionKind.DISCARD]
    assert [(r.seat, r.cards) for r in discards] == [(0, ("2c",)), (2, ("4h",))]


def test_no_discard_when_hand_ends_before_discard_point():
    ad = cp(3)
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    h.apply(Action.fold())
    h.apply(Action.fold())
    assert h.is_terminal() and not any(r.kind is ActionKind.DISCARD for r in h.outcome().history)


def test_all_in_preflop_still_discards_at_flop():
    ad = cp(2)
    h = ad.new_hand(deal_for(ad, ["AsAh2c", "KsKh3d"], "7c8d9hTsJc", burns=("5c", "5d", "5h")))
    h.apply(Action.raise_to(10000))
    h.apply(Action.check_call())
    assert isinstance(h.legal_actions(), LegalDiscards) and len(h.observation(0).board) == 3
    h.apply(Action.discard("2c"))
    h.apply(Action.discard("3d"))
    assert h.is_terminal() and len(h.outcome().board) == 5


@pytest.mark.parametrize("discard,winner", [("2c", 0), ("Ah", 1)])
def test_showdown_uses_kept_cards(discard, winner):
    ad = cp(2)
    h = ad.new_hand(deal_for(ad, ["AsAh2c", "KsKh3d"], "4c6d8hTsQc", burns=("5c", "5d", "5h")))
    for a in [Action.check_call(), Action.check_call(), Action.check_call(), Action.check_call()]:
        h.apply(a)
    h.apply(Action.discard(discard))
    h.apply(Action.discard("3d"))
    while not h.is_terminal():
        h.apply(Action.check_call())
    assert h.outcome().payoffs_chips[winner] > 0


def test_illegal_discards_rejected():
    ad = cp(2)
    h = ad.new_hand(deal_for(ad, ["AsAh2c", "KsKh3d"], "4c6d8hTsQc", burns=("5c", "5d", "5h")))
    with pytest.raises(IllegalActionError):
        h.apply(Action.discard("As"))  # discard during preflop betting
    for _ in range(4):
        h.apply(Action.check_call())
    for bad in (Action.discard("Ks"), Action.discard("As", "Ah"), Action.check_call(), Action.discard()):
        with pytest.raises(IllegalActionError):
            h.apply(bad)


@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 2**32), k=st.integers(2, 6))
def test_fuzz_sequencing_and_showdown_oracles(seed, k):
    ad = cp(k)
    deal = ad.deal_from_deck(KeyedStream("cp-fuzz", seed).shuffle(STANDARD_DECK))
    h = ad.new_hand(deal)
    agent, n, log = RandomLegalAgent("r"), 0, []
    while not h.is_terminal():
        seat, la = h.actor(), h.legal_actions()
        obs = h.observation(seat)
        a = agent.act(obs, la, DecisionRNG("cf", seed, n))
        assert la.contains(a)
        log.append((seat, a.kind, len(obs.board), tuple(obs.active)))
        h.apply(a)
        n += 1
    o = h.outcome()
    assert sum(o.payoffs_chips) == 0
    disc = [i for i, e in enumerate(log) if e[1] is ActionKind.DISCARD]
    if disc:
        assert all(log[i][2] == 3 for i in disc)
        assert disc == list(range(disc[0], disc[0] + len(disc)))  # contiguous block
        live = [s for s, alive in enumerate(log[disc[0]][3]) if alive]
        assert [log[i][0] for i in disc] == live  # exactly the live seats, ascending
        assert all(e[2] == 3 for e in log[: disc[0]] if e[2] >= 3)  # no turn action before discards
        assert all(e[2] >= 4 for e in log[disc[-1] + 1 :])  # all later actions after the turn
        kept = {s: h.observation(s).hole_cards for s in live}
        assert all(len(v) == 2 for v in kept.values())
        folded = {e[0] for e in log if e[1] is ActionKind.FOLD}
        contenders = [s for s in live if s not in folded]
        if len(contenders) > 1 and len(o.board) == 5:
            best = max(rank_holdem(kept[s], o.board) for s in contenders)
            winners = {s for s in contenders if rank_holdem(kept[s], o.board) == best}
            top = max(o.payoffs_chips[s] for s in contenders)
            # split pots: PokerKit gives odd chips to the first winner, so tied
            # winners may differ by up to (n - 1) chips
            tol = len(contenders) - 1
            assert winners == {s for s in contenders if o.payoffs_chips[s] >= top - tol}


def test_allin_ev_uses_kept_cards_and_matches_pokerkit():
    ad = cp(2)
    holes, flop, turn, burns = ["AsAh2c", "KsKh3d"], ("4c", "6d", "8h"), "Ts", ("5c", "5d")

    def play(river, burn3):
        hole = [h[i:i + 2] for h in holes for i in range(0, 6, 2)]
        runout = [burns[0], *flop, burns[1], turn, burn3, river]
        rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
        h = ad.new_hand(ad.deal_from_deck(hole + runout + rest))
        for a in [Action.check_call()] * 4:
            h.apply(a)
        h.apply(Action.discard("2c"))
        h.apply(Action.discard("3d"))
        h.apply(Action.raise_to(9900))
        h.apply(Action.check_call())
        return h.outcome()

    snap = play("Qc", "5h").allin_snapshot
    assert snap.hole == (("As", "Ah"), ("Ks", "Kh")) and {"2c", "3d"} <= snap.dead
    pool = [c for c in STANDARD_DECK if c not in snap.dead]
    ev, method = expected_payoff(snap, 1, "holdem", 10_000, 1, None)
    total = sum(play(r, next(c for c in pool if c != r)).payoffs_chips[1] for r in pool)
    assert method == "exact" and abs(ev * len(pool) - total) < 1e-6


@pytest.mark.parametrize("style", ["neutral", "aggressive"])
def test_cp_agent_distributions_legal(style):
    ad = cp()
    agents = [build_agent(AgentSpec(f"a{i}", "cp_heuristic", {"style": style})) for i in range(6)]
    for b in range(25):
        h = ad.new_hand(ad.deal_from_deck(KeyedStream("cp-ag", b).shuffle(STANDARD_DECK)))
        n = 0
        while not h.is_terminal():
            seat = h.actor()
            obs, la = h.observation(seat), h.legal_actions()
            dist = agents[seat].action_distribution(obs, la)
            assert abs(sum(p for _, p in dist) - 1) < 1e-9 and all(la.contains(a) for a, _ in dist)
            h.apply(agents[seat].act(obs, la, DecisionRNG("c", b, n)))
            n += 1


def test_cp_matched_invariants():
    check_core_invariants(load("cp_6max_100bb.yaml"), range(12))


def test_cp_serial_parallel_and_parquet(tmp_path):
    check_serial_parallel_parquet(load("cp_6max_100bb.yaml"), tmp_path)


def test_other_players_discards_are_private():
    ad = cp(3)
    h = ad.new_hand(deal_for(ad, ["AsAh2c", "KsKh3d", "QsQh4h"], "7c8d9hTsJc", burns=("5c", "5d", "5h")))
    for _ in range(6):  # preflop call/complete/check, flop checked around
        h.apply(Action.check_call())
    h.apply(Action.discard("2c"))  # seat 0
    seen_by_1 = [r for r in h.observation(1).history if r.kind is ActionKind.DISCARD]
    assert seen_by_1 and seen_by_1[0].seat == 0 and seen_by_1[0].cards == ()  # seat 1 cannot see the card
    own = [r for r in h.observation(0).history if r.kind is ActionKind.DISCARD]
    assert own[0].cards == ("2c",)  # a player sees its own discard
    assert h.outcome is not None and any(r.cards == ("2c",) for r in h._history)  # full record kept for traces


def test_preflop_all_in_still_discards_and_showdown_uses_kept_cards():
    """Regression for the FHR3 rule where go_trumpcards diverges (docs/variants.md).

    Everyone is all-in preflop (no further betting possible); the flop is still
    dealt, every live player - all of them all-in - discards 3 -> 2, the turn and
    river run out, and showdown uses only the kept two cards (Hold'em rules).
    Seat 0 is dealt AA2 and keeps A2: with all three hole cards AA would win
    both pots; with the kept cards KK wins the main pot and QQ the side pot.
    """
    ad = cp(3)
    deal = deal_for(ad, ["AsAh2c", "KsKh3d", "QsQh4h"], "5c6d9hJs2d", burns=("3s", "4s", "8s"))
    h = ad.new_hand(deal, starting_stacks=(10000, 3000, 10000))
    h.apply(Action.raise_to(10000))  # BTN (seat 2) jams
    h.apply(Action.check_call())  # SB calls all-in
    h.apply(Action.check_call())  # BB (short) calls all-in
    for seat, card in ((0, "Ah"), (1, "3d"), (2, "4h")):
        assert h.actor() == seat and isinstance(h.legal_actions(), LegalDiscards)
        obs = h.observation(seat)
        assert obs.street == 1 and obs.board == ("5c", "6d", "9h") and len(obs.hole_cards) == 3
        assert obs.stacks[seat] == 0  # the discarder is all-in
        h.apply(Action.discard(card))
    assert h.is_terminal()
    o = h.outcome()
    assert o.board == ("5c", "6d", "9h", "Js", "2d")  # turn and river ran out after the discards
    kept = {0: ("As", "2c"), 1: ("Ks", "Kh"), 2: ("Qs", "Qh")}
    assert rank_holdem(kept[1], o.board) > rank_holdem(kept[2], o.board) > rank_holdem(kept[0], o.board)
    # main pot 9000 -> seat 1 (KK); side pot 14000 (seats 0, 2) -> seat 2 (QQ)
    assert o.payoffs_chips == (-10000, 6000, 4000)
    # with all three hole cards seat 0 (AA) would have won everything
    assert rank_holdem(("As", "Ah", "2c"), o.board) > rank_holdem(kept[1], o.board)
