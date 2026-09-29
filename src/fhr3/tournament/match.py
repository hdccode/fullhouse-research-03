"""One table match inside a tournament (or a calibration round).

``persistent_no_rebuy`` reproduces the 2026 match loop (``sandbox/match.py`` at
fullhouse-engine a80b269) on top of the FHR3 GameAdapters:

* every bot starts the match with the configured stack; stacks carry over between
  hands; there are no rebuys;
* before each hand the bots with chips are listed in seat order (``alive``); the match
  ends early when fewer than two remain;
* the dealer counter increases by one per hand played, so in hand ``h`` the dealer is
  ``alive[h mod len(alive)]``; SB/BB follow (heads-up: dealer = SB);
* a bot's match score is ``final stack - starting stack`` (floor ``-stack``).

FHR3 adapters use fixed positions (position 0 = SB, position m-1 = button, PokerKit
heads-up: position 1 = button = SB). Position ``p`` is therefore occupied by
``alive[(d + 1 + p) mod m]``, which gives the same SB/BB/button as the 2026 engine for
every m >= 2.

``reset_each_hand`` is the FHR3 cash-game rule (every hand from full stacks, all
seats play every hand, the same dealer rotation); the match score is the sum of hand
payoffs. Nit Game keeps its nit-button state across the hands of a match and settles
a nit round when at most one player lacks a button; an unfinished round at the end of
the match is dropped (no transfer).

Randomness is keyed, never sequential:

    deal     KeyedStream("fhr3b-chance", chance_seed, round, table, hand)
    decision DecisionRNG("fhr3b-decision", decision_seed, round, table, hand, bot_id, ordinal)

so hand ``h`` of a match does not depend on the match length (length-nested matches
share their chance prefix) and nothing depends on process placement.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from fhr3.agents import Agent
from fhr3.eval.matched import _Timer, nit_resolution, nit_update_buttons, play_hand
from fhr3.games import make_adapter
from fhr3.games.base import STANDARD_DECK, GameAdapter, GameConfig
from fhr3.rng import DecisionRNG, KeyedStream, derive_seed

MATCH_ENGINE_VERSION = "fhr3b-match-v1"


@dataclass(frozen=True)
class MatchKey:
    chance_seed: int
    decision_seed: int
    round: int
    table: int

    @property
    def match_seed(self) -> int:
        """Compact identifier of the match's randomness (logged, not used for draws)."""
        return derive_seed("fhr3b-match", self.chance_seed, self.decision_seed, self.round, self.table)


@dataclass
class MatchResult:
    deltas: dict[str, int]  # bot_id -> chip delta
    hands_played: int
    bust_hand: dict[str, int] = field(default_factory=dict)  # -1 = never busted
    info: dict[str, Any] = field(default_factory=dict)


class MatchPlayer(Protocol):
    zero_sum: bool

    def play(self, key: MatchKey, seat_order: Sequence[str], hands: int) -> MatchResult: ...


class ChipConservationError(AssertionError):
    pass


def dealer_positions(alive: Sequence[str], hand_index: int) -> list[str]:
    """Bots in FHR3 position order (0 = SB ... m-1 = button) for this hand."""
    m = len(alive)
    d = hand_index % m
    return [alive[(d + 1 + p) % m] for p in range(m)]


class PokerMatchPlayer:
    """Real poker via the FHR3 GameAdapter/Agent stack."""

    zero_sum = True

    def __init__(self, game: GameConfig, stack_policy: str, agents: Mapping[str, Agent]) -> None:
        if stack_policy not in ("persistent_no_rebuy", "reset_each_hand"):
            raise ValueError(f"unknown stack_policy {stack_policy!r}")
        self.game = game
        self.persistent = stack_policy == "persistent_no_rebuy"
        self.agents = dict(agents)
        self.nit = game.variant == "nit_game"
        if self.nit and self.persistent:
            raise ValueError("nit_game matches use reset_each_hand")
        opts = dict(game.options)
        self.nit_penalty_bb = float(opts.get("nit_penalty_bb", 5.0))
        self.nit_max_hands = int(opts.get("max_hands", 60))
        self._adapters: dict[int, GameAdapter] = {}
        self.timer = _Timer()

    def adapter(self, m: int) -> GameAdapter:
        a = self._adapters.get(m)
        if a is None:
            a = make_adapter(replace(self.game, player_count=m))
            self._adapters[m] = a
        return a

    def play(self, key: MatchKey, seat_order: Sequence[str], hands: int,
             hand_log: list[dict[str, Any]] | None = None) -> MatchResult:
        """``hand_log`` (replay/inspection only) receives one record per hand played."""
        seat_order = list(seat_order)
        if len(set(seat_order)) != len(seat_order):
            raise ValueError("a bot cannot sit twice at one table")
        k = len(seat_order)
        if k < 2:
            raise ValueError("a match needs at least two bots")
        s0 = self.game.starting_stack_chips
        bb = self.game.bb_chips
        stacks = {b: s0 for b in seat_order}
        score = {b: 0 for b in seat_order}
        bust = {b: -1 for b in seat_order}
        buttons = {b: False for b in seat_order}
        nit_round_hands, nit_rounds, nit_truncated = 0, 0, 0
        played = 0
        for h in range(hands):
            alive = [b for b in seat_order if stacks[b] > 0] if self.persistent else seat_order
            m = len(alive)
            if m < 2:
                break
            pos = dealer_positions(alive, h)
            adapter = self.adapter(m)
            deck = KeyedStream("fhr3b-chance", key.chance_seed, key.round, key.table, h).shuffle(STANDARD_DECK)
            deal = adapter.deal_from_deck(deck)
            agents = [self.agents[b] for b in pos]

            def rng_for(acting: int, ordinal: int, _h: int = h, _pos: list[str] = pos) -> DecisionRNG:
                return DecisionRNG("fhr3b-decision", key.decision_seed, key.round, key.table, _h, _pos[acting], ordinal)

            public = None
            if self.nit:
                public = {
                    "nit_buttons": tuple(buttons[b] for b in pos),
                    "nit_hand_index": nit_round_hands,
                    "nit_penalty_bb": self.nit_penalty_bb,
                }
            if self.persistent:
                hand = adapter.new_hand(deal, starting_stacks=[stacks[b] for b in pos])
                outcome, _ = _play_prepared(hand, agents, rng_for, self.timer)
            else:
                outcome, _ = play_hand(adapter, deal, agents, rng_for, self.timer, public_info=public)
            pay = outcome.payoffs_chips
            if sum(pay) != 0 or sum(outcome.final_stacks) != sum(outcome.starting_stacks):
                raise ChipConservationError(f"match {key} hand {h}: payoffs {pay}")
            if hand_log is not None:
                hand_log.append({"hand": h, "positions": list(pos), "payoffs": list(pay),
                                 "starting_stacks": list(outcome.starting_stacks), "board": list(outcome.board),
                                 "pot": outcome.total_pot, "showdown": outcome.went_to_showdown,
                                 "decisions": outcome.decision_count})
            for p, b in enumerate(pos):
                score[b] += pay[p]
                if self.persistent:
                    stacks[b] += pay[p]
                    if stacks[b] < 0:
                        raise ChipConservationError(f"negative stack for {b} in {key} hand {h}")
                    if stacks[b] == 0:
                        bust[b] = h
            if self.nit:
                by_bot = {b: pay[p] for p, b in enumerate(pos)}
                upd = nit_update_buttons([buttons[b] for b in seat_order], [by_bot[b] for b in seat_order])
                buttons = dict(zip(seat_order, upd, strict=True))
                nit_round_hands += 1
                over, _nit, transfers = nit_resolution(upd, self.nit_penalty_bb)
                if over:
                    for b, t in zip(seat_order, transfers, strict=True):
                        score[b] += int(round(t * bb))
                    nit_rounds += 1
                    buttons = {b: False for b in seat_order}
                    nit_round_hands = 0
                elif nit_round_hands >= self.nit_max_hands:
                    nit_truncated += 1
                    buttons = {b: False for b in seat_order}
                    nit_round_hands = 0
            played += 1
        if sum(score.values()) != 0:
            raise ChipConservationError(f"match {key}: scores do not sum to zero")
        if self.persistent and any(score[b] != stacks[b] - s0 for b in seat_order):
            raise ChipConservationError(f"match {key}: score != final stack - starting stack")
        info: dict[str, Any] = {}
        if self.nit:
            info = {"nit_rounds": nit_rounds, "nit_truncated": nit_truncated}
        return MatchResult(score, played, bust, info)


def _play_prepared(hand: Any, agents: Sequence[Agent], rng_for: Callable[[int, int], DecisionRNG], timer: _Timer):
    """``play_hand`` for a hand created with explicit (carried-over) stacks."""

    class _Pre:
        """Adapter shim: ``play_hand`` only calls ``new_hand``."""

        def __init__(self, h: Any) -> None:
            self._h = h

        def new_hand(self, deal: Any, public_info: Any = None) -> Any:
            return self._h

    return play_hand(_Pre(hand), None, agents, rng_for, timer)  # type: ignore[arg-type]


# ------------------------------------------------------------------ synthetic model
def _normal(stream: KeyedStream) -> float:
    u1 = max(stream.random(), 1e-300)
    u2 = stream.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def zero_sum_integers(values: Sequence[float]) -> list[int]:
    """Centre to mean zero and round to integers that still sum to zero (deterministic)."""
    mean = sum(values) / len(values)
    centred = [v - mean for v in values]
    floors = [math.floor(v) for v in centred]
    short = -sum(floors)
    order = sorted(range(len(values)), key=lambda i: (-(centred[i] - floors[i]), i))
    out = list(floors)
    for i in order[:short]:
        out[i] += 1
    return out


class SyntheticMatchPlayer:
    """Fast stochastic stand-in for poker (tests, fixtures, analysis smoke).

    Bot i's match result is ``H * (strength_i + sum_j edge[i][j] over opponents j)
    + noise_sd * sqrt(H) * Z_i``, centred to zero-sum and rounded to chips. Keyed
    by the same MatchKey as poker, so tournaments stay replayable.
    """

    zero_sum = True

    def __init__(
        self,
        strength: Mapping[str, float],
        noise_sd: float = 100.0,
        edge: Mapping[str, Mapping[str, float]] | None = None,
    ) -> None:
        self.strength = dict(strength)
        self.noise_sd = float(noise_sd)
        self.edge = {k: dict(v) for k, v in (edge or {}).items()}

    def play(self, key: MatchKey, seat_order: Sequence[str], hands: int) -> MatchResult:
        raw = []
        for b in seat_order:
            s = self.strength[b] + sum(self.edge.get(b, {}).get(o, 0.0) for o in seat_order if o != b)
            z = _normal(KeyedStream("fhr3b-synthetic", key.chance_seed, key.decision_seed, key.round, key.table, b))
            raw.append(hands * s + self.noise_sd * math.sqrt(hands) * z)
        deltas = dict(zip(seat_order, zero_sum_integers(raw), strict=True))
        return MatchResult(deltas, hands, {b: -1 for b in seat_order})
