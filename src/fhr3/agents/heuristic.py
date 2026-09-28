"""Parameterized stochastic heuristic policy family (FHR3 baseline agents).

Design goals: competent-looking, transparent, cheap, smoothly stochastic.
Every decision produces an explicit distribution over a small set of actions
(fold / check-call / one raise size); mixing comes from logistic "soft
thresholds" so small parameter perturbations produce small behavioural changes
(useful for realistic small A/B gaps).

Bump ``IMPL_VERSION`` whenever decision logic changes. Parameter values are
hashed separately into the agent version string.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from fhr3.agents.base import DistributionAgent, params_hash
from fhr3.agents.features import (
    FLUSH,
    FULL_HOUSE,
    HIGH_CARD,
    ONE_PAIR,
    STRAIGHT,
    TRIPS,
    TWO_PAIR,
    postflop_features,
    preflop_percentile,
)
from fhr3.games.base import Action, ActionKind, LegalActions, Observation

IMPL_VERSION = "heuristic-1.0.0"


@dataclass(frozen=True)
class StyleParams:
    # Preflop ranges, as fractions of all starting hands (before looseness).
    open_pct_by_seats_behind: tuple[float, ...] = (0.45, 0.28, 0.20, 0.16, 0.14, 0.12, 0.11, 0.10)
    sb_open_pct: float = 0.36
    call_open_pct: float = 0.11
    bb_defend_pct: float = 0.30
    threebet_pct: float = 0.05
    call_3bet_pct: float = 0.05
    fourbet_pct: float = 0.022
    call_4bet_pct: float = 0.03
    looseness: float = 1.0
    preflop_temperature: float = 0.015
    open_size_bb: float = 2.5
    threebet_mult: float = 3.2
    fourbet_mult: float = 2.3
    # Postflop.
    aggression: float = 1.0
    value_threshold: float = 0.60
    raise_threshold: float = 0.84
    call_margin: float = 0.0
    postflop_temperature: float = 0.04
    bet_fraction: float = 0.66
    raise_pot_fraction: float = 0.9
    semibluff_freq: float = 0.45
    bluff_freq: float = 0.10
    multiway_exponent: float = 0.5
    allin_commit_fraction: float = 0.45

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> StyleParams:
        known = {f.name for f in fields(cls)}
        unknown = set(m) - known
        if unknown:
            raise ValueError(f"unknown StyleParams: {sorted(unknown)}")
        kw = {k: tuple(v) if isinstance(v, list) else v for k, v in m.items()}
        return cls(**kw)


STYLES: dict[str, StyleParams] = {
    "neutral": StyleParams(),
    "tight": StyleParams(looseness=0.75, aggression=0.9, call_margin=0.03),
    "loose": StyleParams(looseness=1.35, call_margin=-0.03, bluff_freq=0.08),
    "aggressive": StyleParams(
        looseness=1.15, aggression=1.4, bluff_freq=0.16, semibluff_freq=0.6
    ),
}


def _sig(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _clip01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


class HeuristicAgent(DistributionAgent):
    IMPL = IMPL_VERSION
    STYLE_TABLE: dict[str, StyleParams] = STYLES

    def __init__(self, agent_id: str, style: str = "neutral", **overrides: Any) -> None:
        if style not in self.STYLE_TABLE:
            raise ValueError(f"unknown style {style!r}; choose from {sorted(self.STYLE_TABLE)}")
        self.p = _merge(self.STYLE_TABLE[style], overrides)
        self.agent_id = agent_id
        self.version = f"{self.IMPL}+{params_hash(asdict(self.p))}"

    def preflop_strength(self, obs: Observation) -> float:
        """Percentile of the starting hand among all starting hands (0..1)."""
        return preflop_percentile(obs.hole_cards)

    # ------------------------------------------------------------------ helpers
    def _in_range(self, strength: float, pct: float, temperature: float) -> float:
        """Soft membership of a hand of percentile ``strength`` in the top ``pct``."""
        pct = _clip01(pct)
        if pct <= 0:
            return 0.0
        if pct >= 1:
            return 1.0
        return _sig((strength - (1.0 - pct)) / temperature)

    def _raise_action(self, obs: Observation, legal: LegalActions, target: float) -> Action | None:
        if not legal.can_raise:
            return None
        assert legal.raise_min is not None and legal.raise_max is not None
        amount = int(round(target))
        committed = obs.stacks[obs.seat] + obs.bets[obs.seat]
        if amount >= self.p.allin_commit_fraction * committed:
            amount = legal.raise_max
        amount = max(legal.raise_min, min(legal.raise_max, amount))
        return Action.raise_to(amount)

    def _finalize(
        self, legal: LegalActions, p_raise: float, p_call: float, raise_action: Action | None
    ) -> list[tuple[Action, float]]:
        p_raise = _clip01(p_raise)
        p_call = _clip01(p_call)
        if raise_action is None:
            p_call, p_raise = _clip01(p_call + p_raise), 0.0
        if p_raise + p_call > 1:
            p_call = 1 - p_raise
        p_fold = 1.0 - p_raise - p_call
        if not legal.can_fold:  # checking is free: never fold
            p_call, p_fold = p_call + p_fold, 0.0
        out: list[tuple[Action, float]] = []
        if p_fold > 0:
            out.append((Action.fold(), p_fold))
        if p_call > 0:
            out.append((Action.check_call(), p_call))
        if p_raise > 0 and raise_action is not None:
            out.append((raise_action, p_raise))
        return out

    # ------------------------------------------------------------------ preflop
    def _preflop(self, obs: Observation, legal: LegalActions) -> list[tuple[Action, float]]:
        p, k, seat, bb = self.p, obs.player_count, obs.seat, obs.bb_chips
        s = self.preflop_strength(obs)
        pre = [r for r in obs.history if r.street == 0]
        raises = [r for r in pre if r.kind is ActionKind.BET_RAISE]
        limpers = sum(1 for r in pre if r.kind is ActionKind.CHECK_CALL and not raises)
        t, L = p.preflop_temperature, p.looseness
        max_bet = max(obs.bets)

        if not raises:
            if seat == 0 and k > 2:
                pct = p.sb_open_pct
            elif seat == 1:
                pct = p.threebet_pct * 2  # BB iso-raise vs limps
            else:
                behind = k - 1 - seat
                table = p.open_pct_by_seats_behind
                pct = table[min(behind, len(table) - 1)]
            p_raise = self._in_range(s, pct * L, t)
            target = (p.open_size_bb + limpers) * bb
            return self._finalize(legal, p_raise, 0.0, self._raise_action(obs, legal, target))

        n = len(raises)
        if n == 1:
            call_pct = p.bb_defend_pct if seat == 1 else p.call_open_pct
            raise_pct, mult = p.threebet_pct * p.aggression, p.threebet_mult
        elif n == 2:
            call_pct, raise_pct, mult = p.call_3bet_pct, p.fourbet_pct * p.aggression, p.fourbet_mult
        else:
            call_pct, raise_pct, mult = p.call_4bet_pct, p.fourbet_pct * 0.6, 100.0
        p_raise = self._in_range(s, raise_pct * L, t)
        p_cont = self._in_range(s, max(call_pct, raise_pct) * L, t)
        return self._finalize(
            legal, p_raise, p_cont - p_raise, self._raise_action(obs, legal, mult * max_bet)
        )

    # ------------------------------------------------------------------ postflop
    def strength(self, obs: Observation) -> tuple[float, float]:
        """(made-hand strength vs one random hand, draw equity) — heuristic."""
        f = postflop_features(obs.hole_cards, obs.board)
        cat = int(f["category"])
        improves = f["hole_improves"] > 0
        board_ranks: tuple[int, ...] = f["board_ranks"]  # type: ignore[assignment]
        hi, lo = f["hole_high"], f["hole_low"]
        if not improves or cat == HIGH_CARD:
            s = 0.10 + 0.14 * (hi / 12.0)
        elif cat == ONE_PAIR:
            if f["pocket_pair"] and hi > f["board_high"]:
                s = 0.70 + 0.10 * (hi / 12.0)
            elif hi == f["board_high"] or lo == f["board_high"]:
                kicker = lo if hi == f["board_high"] else hi
                s = 0.56 + 0.12 * (kicker / 12.0)
            elif len(board_ranks) > 1 and (hi == board_ranks[1] or lo == board_ranks[1]):
                s = 0.44
            else:
                s = 0.34
        elif cat == TWO_PAIR:
            both = not f["pocket_pair"] and hi in board_ranks and lo in board_ranks
            s = 0.84 if both else 0.60
        elif cat == TRIPS:
            s = 0.90 if f["pocket_pair"] else 0.82
        elif cat == STRAIGHT:
            s = 0.91
        elif cat == FLUSH:
            s = 0.94
        elif cat == FULL_HOUSE:
            s = 0.97
        else:
            s = 0.99
        if cat <= TRIPS:
            s -= 0.10 * f["board_flushy"] + 0.05 * f["board_straighty"]
            if cat <= ONE_PAIR:
                s -= 0.04 * f["board_paired"]
        outs = 9.0 * f["flush_draw"] + min(f["straight_outs"], 2.0) * 4.0
        to_come = 5 - len(obs.board)
        draw_eq = _clip01(outs * (0.04 if to_come == 2 else 0.02 if to_come == 1 else 0.0))
        return _clip01(s), draw_eq

    def _postflop(self, obs: Observation, legal: LegalActions) -> list[tuple[Action, float]]:
        p = self.p
        s, draw_eq = self.strength(obs)
        n_opp = max(1, obs.n_active - 1)
        eq = s ** (1.0 + p.multiway_exponent * (n_opp - 1))
        eq = eq + (1 - eq) * draw_eq
        pot, to_call, t = obs.pot, legal.call_amount, p.postflop_temperature
        has_draw = draw_eq > 0.1

        if to_call == 0:
            p_value = _sig((eq - p.value_threshold) / t)
            p_other = 0.0
            if has_draw:
                p_other = p.semibluff_freq * p.aggression
            elif n_opp == 1 and eq < 0.3:
                p_other = p.bluff_freq * p.aggression
            p_bet = p_value + (1 - p_value) * _clip01(p_other)
            target = max(obs.bets) + p.bet_fraction * pot
            return self._finalize(legal, p_bet, 1 - p_bet, self._raise_action(obs, legal, target))

        pot_odds = to_call / (pot + to_call)
        p_raise = _sig((eq - p.raise_threshold) / t)
        if has_draw:
            p_raise = p_raise + (1 - p_raise) * _clip01(0.25 * p.semibluff_freq * p.aggression)
        p_cont = _sig((eq - pot_odds - p.call_margin) / t)
        p_cont = max(p_cont, p_raise)
        target = max(obs.bets) + p.raise_pot_fraction * (pot + to_call)
        return self._finalize(
            legal, p_raise, p_cont - p_raise, self._raise_action(obs, legal, target)
        )

    def action_distribution(
        self, observation: Observation, legal_actions: LegalActions
    ) -> Sequence[tuple[Action, float]]:
        if observation.street == 0:
            return self._preflop(observation, legal_actions)
        return self._postflop(observation, legal_actions)


def _merge(base: StyleParams, overrides: Mapping[str, Any]) -> StyleParams:
    StyleParams.from_mapping(overrides)  # validates names
    kw = {k: tuple(v) if isinstance(v, list) else v for k, v in overrides.items()}
    return replace(base, **kw)
