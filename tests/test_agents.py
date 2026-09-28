"""Agent features, action distributions and legality."""

from itertools import combinations

import pokerkit as pk
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fhr3.agents import AgentSpec, build_agent
from fhr3.agents.base import sample_inverse_cdf
from fhr3.agents.features import made_category, preflop_percentile
from fhr3.agents.heuristic import STYLES, HeuristicAgent
from fhr3.games.base import STANDARD_DECK, Action
from fhr3.rng import DecisionRNG, KeyedStream

from conftest import adapter

LABELS = list(pk.Label)


@settings(max_examples=300, deadline=None)
@given(seed=st.integers(0, 2**32), n=st.sampled_from([5, 6, 7]))
def test_made_category_matches_pokerkit(seed, n):
    cards = KeyedStream("cat", seed).shuffle(STANDARD_DECK)[:n]
    hand = pk.StandardHighHand.from_game("".join(cards[:2]), "".join(cards[2:]))
    assert made_category(cards) == LABELS.index(hand.entry.label)


def test_preflop_percentile_ordering():
    assert preflop_percentile(("As", "Ah")) > 0.99
    assert preflop_percentile(("7c", "2d")) < 0.05
    assert preflop_percentile(("As", "Ks")) > preflop_percentile(("As", "Kd")) > preflop_percentile(("Ts", "9s")) - 0.2
    vals = [preflop_percentile(c) for c in combinations(STANDARD_DECK, 2)]
    assert abs(sum(vals) / len(vals) - 0.5) < 1e-9  # mid-rank CDF has mean 1/2


def test_inverse_cdf_sampling():
    dist = [(Action.fold(), 0.25), (Action.check_call(), 0.5), (Action.raise_to(300), 0.25)]
    assert sample_inverse_cdf(dist, 0.1) == Action.fold()
    assert sample_inverse_cdf(dist, 0.5) == Action.check_call()
    assert sample_inverse_cdf(dist, 0.99) == Action.raise_to(300)


def test_unknown_style_param_rejected():
    with pytest.raises(ValueError):
        HeuristicAgent("x", "neutral", not_a_param=1)
    with pytest.raises(ValueError):
        HeuristicAgent("x", "nope")


def test_version_reflects_parameters():
    a = build_agent(AgentSpec("a", "heuristic", {"style": "neutral"}))
    b = build_agent(AgentSpec("b", "heuristic", {"style": "neutral"}))
    c = build_agent(AgentSpec("c", "heuristic", {"style": "neutral", "overrides": {"looseness": 1.1}}))
    assert a.version == b.version != c.version


@pytest.mark.parametrize("style", sorted(STYLES))
def test_heuristic_distributions_valid_and_actions_legal(style):
    ad = adapter(6)
    agents = [HeuristicAgent(f"a{i}", style) for i in range(6)]
    for b in range(60):
        h = ad.new_hand(ad.deal_from_deck(KeyedStream("agents", b).shuffle(STANDARD_DECK)))
        n = 0
        while not h.is_terminal():
            seat = h.actor()
            obs, la = h.observation(seat), h.legal_actions()
            dist = agents[seat].action_distribution(obs, la)
            assert abs(sum(p for _, p in dist) - 1.0) < 1e-9
            assert all(p >= 0 and la.contains(a) for a, p in dist)
            h.apply(agents[seat].act(obs, la, DecisionRNG("t", b, n)))
            n += 1
        assert sum(h.outcome().payoffs_chips) == 0


def test_act_is_deterministic_given_rng_key():
    ad = adapter(6)
    h = ad.new_hand(ad.deal_from_deck(STANDARD_DECK))
    a = HeuristicAgent("a", "aggressive")
    obs, la = h.observation(h.actor()), h.legal_actions()
    assert a.act(obs, la, DecisionRNG("k", 1)) == a.act(obs, la, DecisionRNG("k", 1))
