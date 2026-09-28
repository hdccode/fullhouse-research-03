"""4-max All-in-or-Fold agents.

* ``AoFPolicyAgent`` – the FullHouse 4-max 8BB production policy v2 (vendored
  from aof-ml, see ``data/aof_4max_8bb_production_v2.json`` provenance), looked
  up per (decision node, hand class). Optional ``blend`` mixes in an AoF
  heuristic: p = (1 - blend) * p_policy + blend * p_heuristic (used for small,
  controlled perturbations of the production policy).
* ``AoFHeuristicAgent`` – transparent percentile-threshold shove/call ranges.

Seat mapping (FHR3 seats are positions): 0 = SB, 1 = BB, 2 = CO, 3 = BTN.
The only non-fold action is all-in: ``raise_to(raise_max)`` when unopened,
otherwise the (all-in) call.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields, replace
from functools import lru_cache
from importlib import resources
from typing import Any

from fhr3.agents.base import DistributionAgent, params_hash
from fhr3.agents.features import RANK_VALUE, preflop_percentile
from fhr3.games.base import Action, ActionKind, LegalActions, Observation

AOF_POLICY_IMPL = "aof-policy-1.0.0"
AOF_HEUR_IMPL = "aof-heuristic-1.0.0"
POSITIONS_4MAX = {2: "CO", 3: "BTN", 0: "SB", 1: "BB"}
RANKS_DESC = "AKQJT98765432"
POLICIES = {"production-v2": "aof_4max_8bb_production_v2.json"}


def hand_class(hole: Sequence[str]) -> str:
    a, b = sorted(hole, key=lambda c: RANK_VALUE[c[0]], reverse=True)
    if a[0] == b[0]:
        return a[0] + b[0]
    return a[0] + b[0] + ("s" if a[1] == b[1] else "o")


def prior_actions(obs: Observation) -> tuple[str, ...]:
    return tuple("F" if r.kind is ActionKind.FOLD else "A" for r in obs.history if r.street == 0)


def allin_action(legal: LegalActions) -> Action:
    if legal.raise_max is not None:
        return Action.raise_to(legal.raise_max)
    return Action.check_call()


@lru_cache(maxsize=None)
def load_policy(name: str) -> dict[str, Any]:
    text = resources.files("fhr3.agents.data").joinpath(POLICIES[name]).read_text()
    d = json.loads(text)
    d["by_key"] = {(n["acting_position"], tuple(n["prior_actions"])): n for n in d["nodes"].values()}
    return d


def _check_game(obs: Observation) -> None:
    if obs.player_count != 4 or obs.starting_stacks[obs.seat] != 8 * obs.bb_chips:
        raise ValueError("AoF policies are defined for 4-max, 8BB equal stacks")


def _dist(p: float, legal: LegalActions) -> list[tuple[Action, float]]:
    p = min(1.0, max(0.0, p))
    if not legal.can_fold:
        p = 1.0
    out = []
    if p < 1.0:
        out.append((Action.fold(), 1.0 - p))
    if p > 0.0:
        out.append((allin_action(legal), p))
    return out


@dataclass(frozen=True)
class AoFStyle:
    shove_pct: tuple[float, float, float] = (0.28, 0.40, 0.55)  # CO, BTN, SB unopened
    call_pct: tuple[float, float, float] = (0.16, 0.18, 0.28)  # BTN, SB, BB vs one shove
    multi_call_pct: float = 0.07  # vs two or more shoves
    shove_scale: float = 1.0
    call_scale: float = 1.0
    temperature: float = 0.015


AOF_STYLES = {
    "neutral": AoFStyle(),
    "tight": AoFStyle(shove_scale=0.75, call_scale=0.75),
    "loose": AoFStyle(shove_scale=1.2, call_scale=1.3),
    "aggressive": AoFStyle(shove_scale=1.25, call_scale=0.95),
}


class AoFHeuristicAgent(DistributionAgent):
    def __init__(self, agent_id: str, style: str = "neutral", **overrides: Any) -> None:
        known = {f.name for f in fields(AoFStyle)}
        if style not in AOF_STYLES or set(overrides) - known:
            raise ValueError(f"bad AoF style/overrides: {style!r} {sorted(set(overrides) - known)}")
        self.s = replace(AOF_STYLES[style], **{k: tuple(v) if isinstance(v, list) else v for k, v in overrides.items()})
        self.agent_id = agent_id
        self.version = f"{AOF_HEUR_IMPL}+{params_hash(asdict(self.s))}"

    def p_allin(self, obs: Observation) -> float:
        _check_game(obs)
        st = self.s
        pos = POSITIONS_4MAX[obs.seat]
        n_shoves = sum(1 for a in prior_actions(obs) if a == "A")
        if n_shoves == 0:
            pct = st.shove_pct[("CO", "BTN", "SB").index(pos)] * st.shove_scale
        elif n_shoves == 1:
            pct = st.call_pct[("BTN", "SB", "BB").index(pos)] * st.call_scale
        else:
            pct = st.multi_call_pct * st.call_scale
        pct = min(1.0, max(0.0, pct))
        x = (preflop_percentile(obs.hole_cards) - (1.0 - pct)) / st.temperature
        return 1.0 / (1.0 + math.exp(-x)) if x > -700 else 0.0

    def action_distribution(self, observation: Observation, legal_actions: LegalActions) -> Sequence[tuple[Action, float]]:
        return _dist(self.p_allin(observation), legal_actions)


class AoFPolicyAgent(DistributionAgent):
    def __init__(self, agent_id: str, policy: str = "production-v2", blend: float = 0.0, blend_style: str = "neutral") -> None:
        if policy not in POLICIES or not 0.0 <= blend <= 1.0:
            raise ValueError(f"unknown AoF policy {policy!r} or blend outside [0, 1]")
        self.policy = load_policy(policy)
        self.blend = float(blend)
        self.heur = AoFHeuristicAgent(agent_id, blend_style) if blend > 0 else None
        self.agent_id = agent_id
        tag = {"policy": self.policy["provenance"]["source_content_hash"], "blend": blend,
               "blend_with": self.heur.version if self.heur else None}
        self.version = f"{AOF_POLICY_IMPL}+{params_hash(tag)}"

    def p_allin(self, obs: Observation) -> float:
        _check_game(obs)
        node = self.policy["by_key"][(POSITIONS_4MAX[obs.seat], prior_actions(obs))]
        p = node["p"][hand_class(obs.hole_cards)]
        if self.heur is not None:
            p = (1.0 - self.blend) * p + self.blend * self.heur.p_allin(obs)
        return p

    def action_distribution(self, observation: Observation, legal_actions: LegalActions) -> Sequence[tuple[Action, float]]:
        return _dist(self.p_allin(observation), legal_actions)
