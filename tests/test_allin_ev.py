"""All-in EV estimator: exactness against PokerKit, mean preservation, CRN symmetry."""

from __future__ import annotations

import math

import numpy as np

from fhr3.agents.heuristic import HeuristicAgent
from fhr3.agents.simple import RandomLegalAgent
from fhr3.configs.experiment import RNGConfig
from fhr3.estimators.allin_ev import AllInEVEstimator, expected_payoff
from fhr3.eval.matched import MatchedBlockSpec, run_matched_block
from fhr3.games.base import STANDARD_DECK, Action, Deal
from fhr3.rng import KeyedStream

from conftest import adapter

HOLES = ["AsKd", "QcQh", "7s8s"]
FLOP, TURN = ("2s", "9s", "Jh"), "3c"
BURNS = ("4d", "5d", "6d")
STACKS = (10000, 3000, 6000)
# preflop: BTN calls, SB completes, BB checks; flop checked; turn: SB jams, BB calls, BTN calls
SCRIPT = [Action.check_call(), Action.check_call(), Action.check_call(),
          Action.check_call(), Action.check_call(), Action.check_call(),
          Action.raise_to(9900), Action.check_call(), Action.check_call()]


def make_deal(river: str, burn3: str) -> Deal:
    hole = [h[i:i + 2] for h in HOLES for i in (0, 2)]
    runout = [BURNS[0], *FLOP, BURNS[1], TURN, burn3, river]
    rest = [c for c in STANDARD_DECK if c not in set(hole) | set(runout)]
    ad = adapter(3)
    return ad.deal_from_deck(hole + runout + rest)


def play(deal: Deal):
    ad = adapter(3)
    h = ad.new_hand(deal, starting_stacks=STACKS)
    for a in SCRIPT:
        h.apply(a)
    assert h.is_terminal()
    return h.outcome()


def test_snapshot_fields_on_turn_all_in():
    o = play(make_deal("Kh", BURNS[2]))
    snap = o.allin_snapshot
    assert snap is not None and snap.board == (*FLOP, TURN)
    assert snap.live == (True, True, True)
    assert sum(a for a, _ in snap.pots) == sum(snap.contributed) == 3000 + 6000 + 6000
    assert {BURNS[0], BURNS[1]} <= snap.dead and BURNS[2] not in snap.dead


def test_exact_ev_equals_pokerkit_average_over_all_rivers_including_side_pots():
    snap = play(make_deal("Kh", BURNS[2])).allin_snapshot
    pool = [c for c in STANDARD_DECK if c not in snap.dead]
    for seat in range(3):
        ev, method = expected_payoff(snap, seat, "holdem", 10_000, 1, None)
        assert method == "exact"
        total = 0
        for river in pool:
            burn3 = next(c for c in pool if c != river)
            total += play(make_deal(river, burn3)).payoffs_chips[seat]
        assert abs(ev * len(pool) - total) < 1e-6  # exact, incl. side pot and odd-chip rules
    evs = [expected_payoff(snap, s, "holdem", 10_000, 1, None)[0] for s in range(3)]
    assert abs(sum(evs)) < 1e-9  # zero-sum


def test_monte_carlo_matches_exact_and_is_deterministic():
    snap = play(make_deal("Kh", BURNS[2])).allin_snapshot
    exact, _ = expected_payoff(snap, 2, "holdem", 10_000, 1, None)
    mc1, m = expected_payoff(snap, 2, "holdem", 1, 4000, KeyedStream("t", 1))
    mc2, _ = expected_payoff(snap, 2, "holdem", 1, 4000, KeyedStream("t", 1))
    assert m == "mc" and mc1 == mc2
    assert abs(mc1 - exact) < 4 * 6000 / math.sqrt(4000)


def spec(b: int) -> MatchedBlockSpec:
    return MatchedBlockSpec("e", "c", "p", "ph", 7, b, RNGConfig())


def rand_refs(k=6):
    return [RandomLegalAgent(f"r{i}") for i in range(k - 1)]


def test_block_level_selfplay_zero_and_swap_negation():
    ad = adapter()
    est = [AllInEVEstimator("holdem", mc_samples=30)]
    seen = changed = 0
    for b in range(15):
        a1, a2, bb = RandomLegalAgent("A"), RandomLegalAgent("A2"), HeuristicAgent("B", "aggressive")
        r = run_matched_block(spec(b), ad, a1, a2, rand_refs(), estimators=est)
        assert r.valid and r.estimator_D("allin_ev") == 0.0
        ab = run_matched_block(spec(b), ad, a1, bb, rand_refs(), estimators=est)
        ba = run_matched_block(spec(b), ad, bb, a1, rand_refs(), estimators=est)
        assert ab.estimator_D("allin_ev") == -ba.estimator_D("allin_ev")
        seen += sum(h.allin_runout for h in ab.hands)
        changed += ab.estimator_D("allin_ev") != ab.D
    assert seen > 0 and changed > 0


def test_hands_without_allin_runout_are_unchanged():
    ad = adapter()
    r = run_matched_block(spec(3), ad, RandomLegalAgent("A"), RandomLegalAgent("B"), rand_refs(),
                          estimators=[AllInEVEstimator("holdem", mc_samples=20)])
    for h in r.hands:
        if not h.allin_runout:
            assert h.estimates_bb["allin_ev"] == h.payoff_bb


def test_mean_preservation_statistical():
    """E[allin_ev_D - D] = 0: paired t-statistic over random-agent blocks."""
    ad = adapter()
    est = [AllInEVEstimator("holdem", mc_samples=40)]
    diffs = []
    for b in range(120):
        r = run_matched_block(spec(1000 + b), ad, RandomLegalAgent("A"), HeuristicAgent("B", "aggressive"), rand_refs(), estimators=est)
        diffs.append(r.estimator_D("allin_ev") - r.D)
    d = np.array(diffs)
    assert d.std() > 0  # the estimator actually changes things
    t = d.mean() / (d.std(ddof=1) / math.sqrt(d.size))
    assert abs(t) < 4.0
