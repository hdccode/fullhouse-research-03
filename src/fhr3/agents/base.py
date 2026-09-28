"""Agent interface.

Agents are *stateless across hands*: ``act`` must be a pure function of
``(observation, legal_actions, rng draws)``. The matched-block engine relies on
this so hand order within a block (and process placement) cannot matter.
Agents never see PokerKit objects.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from fhr3.games.base import Action, LegalActions, Observation
from fhr3.rng import DecisionRNG


@runtime_checkable
class Agent(Protocol):
    agent_id: str
    version: str

    def act(
        self, observation: Observation, legal_actions: LegalActions, rng: DecisionRNG
    ) -> Action: ...


class DistributionAgent:
    """Base for agents defined by an explicit action distribution.

    ``act`` consumes exactly one uniform (inverse-CDF selection), which is what
    makes A/B common random numbers well-defined. ``action_distribution`` is
    also what later AIVAT-style estimators need.
    """

    agent_id: str
    version: str

    def action_distribution(
        self, observation: Observation, legal_actions: LegalActions
    ) -> Sequence[tuple[Action, float]]:
        raise NotImplementedError

    def act(
        self, observation: Observation, legal_actions: LegalActions, rng: DecisionRNG
    ) -> Action:
        dist = self.action_distribution(observation, legal_actions)
        return sample_inverse_cdf(dist, rng.random())


def sample_inverse_cdf(dist: Sequence[tuple[Action, float]], u: float) -> Action:
    total = sum(p for _, p in dist)
    if total <= 0:
        raise ValueError("empty action distribution")
    acc = 0.0
    for action, p in dist:
        acc += p / total
        if u < acc:
            return action
    return dist[-1][0]


def params_hash(params: Mapping[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


@dataclass(frozen=True)
class AgentSpec:
    """Serializable agent definition (lives in experiment configs)."""

    agent_id: str
    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "kind": self.kind, "params": dict(self.params)}
