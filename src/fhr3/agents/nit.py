"""Nit Game heuristic family: NLHE heuristic + nit-button awareness.

A player without a nit button is at risk of paying the nit penalty, so it plays
"hungrier": ranges widened by ``nit_looseness`` and calls loosened by
``nit_call_shift`` (subtracted from ``call_margin``). With a button it plays its
ordinary style. The button state is public (``Observation.extra["nit_buttons"]``).
Setting nit_looseness=1 and nit_call_shift=0 gives a nit-unaware agent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from fhr3.agents.base import DistributionAgent, params_hash
from fhr3.agents.heuristic import HeuristicAgent
from fhr3.games.base import Action, LegalActions, Observation

NIT_IMPL_VERSION = "nit-heuristic-1.0.0"


class NitHeuristicAgent(DistributionAgent):
    def __init__(
        self,
        agent_id: str,
        style: str = "neutral",
        nit_looseness: float = 1.3,
        nit_call_shift: float = 0.04,
        **overrides: Any,
    ) -> None:
        self.agent_id = agent_id
        self.base = HeuristicAgent(agent_id, style, **overrides)
        hungry = replace(
            self.base.p,
            looseness=self.base.p.looseness * nit_looseness,
            call_margin=self.base.p.call_margin - nit_call_shift,
        )
        self.hungry = HeuristicAgent(agent_id, style)
        self.hungry.p = hungry
        self.nit_looseness, self.nit_call_shift = nit_looseness, nit_call_shift
        self.version = f"{NIT_IMPL_VERSION}+{params_hash({'base': self.base.version, 'hungry': repr(hungry)})}"

    def action_distribution(
        self, observation: Observation, legal_actions: LegalActions
    ) -> Sequence[tuple[Action, float]]:
        buttons = observation.extra.get("nit_buttons")
        at_risk = buttons is not None and not buttons[observation.seat]
        agent = self.hungry if at_risk else self.base
        return agent.action_distribution(observation, legal_actions)
