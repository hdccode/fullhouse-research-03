"""FHR3B-local agent families and builder (FHR3A agent code is untouched).

``fhr3b_heuristic`` (``FHR3BHeuristicAgent``) is the FHR3A ``heuristic`` policy with the
same parameters and the same decision logic. It corrects one thing only: how game state
maps to blind roles at a **heads-up** table.

FHR3A's ``HeuristicAgent._preflop`` assumes seat 0 = SB and seat 1 = BB. That holds for 3+
players. In FHR3/PokerKit heads-up, seat 1 is the button = small blind and acts first
preflop, and seat 0 is the big blind. FHR3A never played heads-up (minimum 3 seats). FHR3B's
persistent-stack matches reach heads-up whenever bots bust, and the inverted roles made the
button take the "BB vs limps" branch (raise ~12%, fold ~88%) and the BB use the non-BB calling
range (fold ~87% facing a raise). Seen in the NLHE4/NLHE6 pool calibrations; see
reports/fhr3b/field-calibration/retired_hu_role_bug/.

Corrected roles:

| table | SB (``sb_open_pct`` when first in) | BB (iso vs limps; ``bb_defend_pct`` vs a raise) |
|---|---|---|
| 3+ players | seat 0 (unchanged) | seat 1 (unchanged) |
| heads-up | seat 1 = button = SB, acts first | seat 0 |

The heads-up button uses the small-blind open range because that is its exact situation:
first to act with only the big blind behind. Everything else (preflop strength, sizing,
3-/4-bet logic, all postflop play, whose order the engine sets) is inherited unchanged. With 3
or more players the decision distribution is identical to FHR3A's (tested).
"""

from __future__ import annotations

from collections.abc import Sequence

from fhr3.agents import Agent, AgentSpec
from fhr3.agents import build_agent as _fhr3_build_agent
from fhr3.agents.heuristic import HeuristicAgent
from fhr3.games.base import Action, ActionKind, LegalActions, Observation

FHR3B_HEURISTIC_IMPL = "fhr3b-heuristic-1.0.0"
FHR3B_KINDS = ("fhr3b_heuristic",)


def blind_roles(seat: int, player_count: int) -> tuple[bool, bool]:
    """(is small blind, is big blind) for the FHR3/PokerKit seat convention."""
    if player_count == 2:
        return seat == 1, seat == 0
    return seat == 0, seat == 1


class FHR3BHeuristicAgent(HeuristicAgent):
    IMPL = FHR3B_HEURISTIC_IMPL

    def _preflop(self, obs: Observation, legal: LegalActions) -> list[tuple[Action, float]]:
        k = obs.player_count
        if k > 2:  # 3+ handed: exactly the FHR3A logic
            return super()._preflop(obs, legal)
        p, seat, bb = self.p, obs.seat, obs.bb_chips
        is_sb, is_bb = blind_roles(seat, k)
        s = self.preflop_strength(obs)
        pre = [r for r in obs.history if r.street == 0]
        raises = [r for r in pre if r.kind is ActionKind.BET_RAISE]
        limpers = sum(1 for r in pre if r.kind is ActionKind.CHECK_CALL and not raises)
        t, L = p.preflop_temperature, p.looseness
        max_bet = max(obs.bets)

        if not raises:
            pct = p.sb_open_pct if is_sb else p.threebet_pct * 2  # BB: iso-raise vs a limp
            p_raise = self._in_range(s, pct * L, t)
            target = (p.open_size_bb + limpers) * bb
            return self._finalize(legal, p_raise, 0.0, self._raise_action(obs, legal, target))

        n = len(raises)
        if n == 1:
            call_pct = p.bb_defend_pct if is_bb else p.call_open_pct
            raise_pct, mult = p.threebet_pct * p.aggression, p.threebet_mult
        elif n == 2:
            call_pct, raise_pct, mult = p.call_3bet_pct, p.fourbet_pct * p.aggression, p.fourbet_mult
        else:
            call_pct, raise_pct, mult = p.call_4bet_pct, p.fourbet_pct * 0.6, 100.0
        p_raise = self._in_range(s, raise_pct * L, t)
        p_cont = self._in_range(s, max(call_pct, raise_pct) * L, t)
        return self._finalize(legal, p_raise, p_cont - p_raise, self._raise_action(obs, legal, mult * max_bet))


def build_agent(spec: AgentSpec) -> Agent:
    """FHR3B agent registry: FHR3B-local kinds here, everything else delegated to FHR3A."""
    if spec.kind == "fhr3b_heuristic":
        params = dict(spec.params)
        style = params.pop("style", "neutral")
        return FHR3BHeuristicAgent(spec.agent_id, style=style, **params.pop("overrides", {}), **params)
    return _fhr3_build_agent(spec)


def is_fhr3b_kind(kind: str) -> bool:
    return kind in FHR3B_KINDS


__all__: Sequence[str] = ("FHR3BHeuristicAgent", "build_agent", "blind_roles", "FHR3B_HEURISTIC_IMPL")
