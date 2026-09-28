"""Mandatory matched-block invariants (blocking if any fails)."""

from __future__ import annotations

import pytest

from fhr3.agents.heuristic import HeuristicAgent
from fhr3.agents.simple import CheckCallAgent, RandomLegalAgent
from fhr3.configs.experiment import RNGConfig
from fhr3.eval.matched import (
    MatchedBlockSpec,
    make_deal,
    reference_seats,
    run_matched_block,
)
from fhr3.eval.runner import BlockSimulator
from fhr3.games.base import Action
from fhr3.validation.corpus import rows_equal

from conftest import adapter, make_cfg

BLOCKS = range(12)


def spec(block_id: int, rng: RNGConfig | None = None, root_seed: int = 99) -> MatchedBlockSpec:
    return MatchedBlockSpec("e", "c", "p", "ph", root_seed, block_id, rng or RNGConfig())


def refs(style_list=("tight", "neutral", "loose", "aggressive", "neutral")):
    return [HeuristicAgent(f"r{i}", s) for i, s in enumerate(style_list)]


class Recorder:
    """Wraps an agent and records (seat, hole cards) of each decision."""

    def __init__(self, inner, log, tag):
        self.inner, self.log, self.tag = inner, log, tag
        self.agent_id, self.version = inner.agent_id, inner.version

    def act(self, obs, legal, rng):
        self.log.append((self.tag, obs.seat, obs.hole_cards))
        return self.inner.act(obs, legal, rng)


# ---------------------------------------------------------------- replay
def test_exact_replay_with_fresh_objects(tiny_cfg):
    r1 = [BlockSimulator(tiny_cfg, tiny_cfg.pairing("ab")) for _ in range(2)]
    for b in BLOCKS:
        rows = [s.row(s.run(b), "run", False) for s in r1]
        assert rows_equal(rows[0], rows[1]) == []


# ---------------------------------------------------------------- self-play
@pytest.mark.parametrize("kind", ["heuristic", "random"])
def test_selfplay_gives_exact_zero(kind):
    ad = adapter()
    mk = (lambda n: HeuristicAgent(n, "aggressive")) if kind == "heuristic" else RandomLegalAgent
    nonzero_payoffs = 0
    for b in BLOCKS:
        r = run_matched_block(spec(b), ad, mk("A"), mk("A2"), refs())
        assert r.valid, r.error_detail
        assert r.D == 0.0 and all(d == 0.0 for d in r.seat_D)
        nonzero_payoffs += any(r.seat_payoff_a)
    assert nonzero_payoffs > 0  # the zero is from cancellation, not from nothing happening


def test_independent_candidate_coupling_breaks_exact_cancellation():
    ad = adapter()
    rng = RNGConfig(candidate_coupling="independent")
    Ds = [run_matched_block(spec(b, rng), ad, RandomLegalAgent("A"), RandomLegalAgent("A2"), refs()).D for b in BLOCKS]
    assert any(d != 0 for d in Ds)


# ---------------------------------------------------------------- A/B swap
def test_swap_negates_block_and_seat_results():
    ad = adapter()
    A, B = HeuristicAgent("A", "neutral"), HeuristicAgent("B", "aggressive")
    seen_nonzero = False
    for b in BLOCKS:
        ab = run_matched_block(spec(b), ad, A, B, refs())
        ba = run_matched_block(spec(b), ad, B, A, refs())
        assert ab.D == -ba.D
        assert ab.seat_D == [-x for x in ba.seat_D]
        assert ab.seat_payoff_a == ba.seat_payoff_b
        seen_nonzero |= ab.D != 0
    assert seen_nonzero


# ---------------------------------------------------------------- conservation / legality
def test_chip_conservation_and_validity_under_random_play():
    ad = adapter()
    for b in range(20):
        r = run_matched_block(spec(b), ad, RandomLegalAgent("A"), RandomLegalAgent("B"), [RandomLegalAgent(f"r{i}") for i in range(5)])
        assert r.valid, r.error_detail
        assert r.played_hands == 12


class IllegalAgent:
    agent_id, version = "bad", "bad"

    def act(self, obs, legal, rng):
        return Action.raise_to(1)


def test_illegal_action_invalidates_block_with_code():
    r = run_matched_block(spec(0), adapter(), IllegalAgent(), HeuristicAgent("B"), refs())
    assert not r.valid and r.error_code == "ILLEGAL_ACTION" and r.D is None


def test_invalid_block_keeps_partial_trace():
    r = run_matched_block(spec(0), adapter(), IllegalAgent(), HeuristicAgent("B"), refs(), trace=True)
    assert any("-partial." in k for k in r.traces)


# ---------------------------------------------------------------- seat rotation
@pytest.mark.parametrize("k", [2, 4, 6])
def test_seat_rotation_protocol(k):
    ad = adapter(k)
    log: list = []
    A = Recorder(CheckCallAgent("A"), log, "A")
    B = Recorder(CheckCallAgent("B"), log, "B")
    R = [Recorder(CheckCallAgent(f"r{j}"), log, f"r{j}") for j in range(k - 1)]
    s0 = spec(3)
    deal = make_deal(ad, s0.seed)
    r = run_matched_block(s0, ad, A, B, R)
    assert r.valid and r.played_hands == 2 * k
    assert [h.candidate_seat for h in r.hands] == [s for s in range(k) for _ in "AB"]
    assert [h.side for h in r.hands] == ["A", "B"] * k
    # every agent always sees the Deal's cards for the seat it occupies
    for _tag, seat, hole in log:
        assert hole == deal.hole[seat]
    # candidate occupies each seat exactly in its own hands; references follow the rule
    for side in "AB":
        seats = {seat for tag, seat, _ in log if tag == side}
        assert seats == set(range(k))
    for j in range(k - 1):
        seats = {seat for tag, seat, _ in log if tag == f"r{j}"}
        assert seats == {reference_seats(k, s)[j] for s in range(k)}
    assert reference_seats(6, 0) == [1, 2, 3, 4, 5]
    assert reference_seats(6, 4) == [5, 0, 1, 2, 3]


# ---------------------------------------------------------------- stream isolation
def _run(rng, a, b, rs, blocks=BLOCKS):
    ad = adapter()
    return [run_matched_block(spec(x, rng), ad, a, b, rs) for x in blocks]


def _payoffs(results):
    return [(r.seat_payoff_a, r.seat_payoff_b) for r in results]


def test_reference_salt_only_affects_reference_draws():
    base = RNGConfig()
    salted = RNGConfig(salts={"chance": 0, "candidate": 0, "reference": 7})
    # deterministic references -> reference salt must be a no-op
    det_refs = [CheckCallAgent(f"r{i}") for i in range(5)]
    A, B = RandomLegalAgent("A"), RandomLegalAgent("B")
    assert _payoffs(_run(base, A, B, det_refs)) == _payoffs(_run(salted, A, B, det_refs))
    # stochastic references -> salt is live
    assert _payoffs(_run(base, A, B, refs())) != _payoffs(_run(salted, A, B, refs()))


def test_candidate_salt_only_affects_candidate_draws():
    base = RNGConfig()
    salted = RNGConfig(salts={"chance": 0, "candidate": 7, "reference": 0})
    A, B = CheckCallAgent("A"), CheckCallAgent("B")
    assert _payoffs(_run(base, A, B, refs())) == _payoffs(_run(salted, A, B, refs()))
    A2, B2 = RandomLegalAgent("A"), RandomLegalAgent("B")
    assert _payoffs(_run(base, A2, B2, refs())) != _payoffs(_run(salted, A2, B2, refs()))


def test_chance_salt_changes_deals_only_via_chance_stream():
    ad = adapter()
    d0 = [make_deal(ad, spec(b).seed, 0) for b in BLOCKS]
    d1 = [make_deal(ad, spec(b).seed, 1) for b in BLOCKS]
    assert all(x != y for x, y in zip(d0, d1))
    assert d0 == [make_deal(ad, spec(b).seed, 0) for b in BLOCKS]


def test_deals_are_shared_across_pairings_and_stack_depths():
    a100, a20 = adapter(6, 100), adapter(6, 20)
    for b in BLOCKS:
        assert make_deal(a100, spec(b).seed) == make_deal(a20, spec(b).seed)
    c1 = make_cfg()
    s_ab = BlockSimulator(c1, c1.pairing("ab")).spec(0)
    s_self = BlockSimulator(c1, c1.pairing("self")).spec(0)
    assert s_ab.seed == s_self.seed


def test_different_blocks_get_different_deals():
    ad = adapter()
    deals = {make_deal(ad, spec(b).seed).deck_order for b in range(50)}
    assert len(deals) == 50
