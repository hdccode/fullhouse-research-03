"""Simple agents for tests and fuzzing. Not intended as experimental candidates."""

from __future__ import annotations

from collections.abc import Sequence

from fhr3.agents.base import DistributionAgent
from fhr3.games.base import Action, LegalActions, LegalDiscards, Observation
from fhr3.rng import DecisionRNG

SIMPLE_VERSION = "simple-1.0.0"


class CheckCallAgent(DistributionAgent):
    """Deterministic calling station (never folds, never raises)."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id, self.version = agent_id, f"{SIMPLE_VERSION}/checkcall"

    def action_distribution(
        self, observation: Observation, legal_actions: LegalActions | LegalDiscards
    ) -> Sequence[tuple[Action, float]]:
        if isinstance(legal_actions, LegalDiscards):
            return [(Action.discard(*legal_actions.cards[-legal_actions.count:]), 1.0)]
        return [(Action.check_call(), 1.0)]


class RandomLegalAgent:
    """Uniform over action kinds, uniform raise size. Fuzzing only."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id, self.version = agent_id, f"{SIMPLE_VERSION}/random"

    def act(
        self, observation: Observation, legal_actions: LegalActions | LegalDiscards, rng: DecisionRNG
    ) -> Action:
        if isinstance(legal_actions, LegalDiscards):
            cards = rng.shuffle(legal_actions.cards)[: legal_actions.count]
            return Action.discard(*cards)
        options = []
        if legal_actions.can_fold:
            options.append("f")
        if legal_actions.can_check_call:
            options.append("c")
        if legal_actions.can_raise:
            options.append("r")
        choice = options[rng.randbelow(len(options))]
        if choice == "f":
            return Action.fold()
        if choice == "c":
            return Action.check_call()
        assert legal_actions.raise_min is not None and legal_actions.raise_max is not None
        lo, hi = legal_actions.raise_min, legal_actions.raise_max
        # Bias towards the extremes so all-ins/min-raises are well exercised.
        r = rng.random()
        if r < 0.25:
            return Action.raise_to(lo)
        if r < 0.5:
            return Action.raise_to(hi)
        return Action.raise_to(lo + rng.randbelow(hi - lo + 1))
