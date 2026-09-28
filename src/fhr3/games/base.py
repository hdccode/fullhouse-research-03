"""Variant-independent game interface.

Nothing outside ``fhr3.games`` may import PokerKit. Agents, the matched-block
engine and analysis see only the types defined here. Cards are two-character
strings (rank in ``23456789TJQKA``, suit in ``cdhs``), e.g. ``"As"``.

Seat convention (all variants): seats are ``0..k-1`` in dealing order; seat 0
is the small blind, seat 1 the big blind and seat ``k-1`` the button. This is a
fixed-button table: seat indices *are* positions.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

RANKS = "23456789TJQKA"
SUITS = "cdhs"
STANDARD_DECK: tuple[str, ...] = tuple(r + s for r in RANKS for s in SUITS)


@dataclass(frozen=True)
class GameConfig:
    """Scientific game definition. Hashed into ``config_hash``."""

    variant: str
    player_count: int
    stack_bb: float
    bb_chips: int = 100
    sb_chips: int = 50
    ante_chips: int = 0
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 2 <= self.player_count <= 10:
            raise ValueError("player_count must be in [2, 10]")
        if self.bb_chips <= 0 or self.sb_chips <= 0:
            raise ValueError("blinds must be positive")
        stack = self.stack_bb * self.bb_chips
        if abs(stack - round(stack)) > 1e-9:
            raise ValueError("stack_bb * bb_chips must be an integer chip count")

    @property
    def starting_stack_chips(self) -> int:
        return int(round(self.stack_bb * self.bb_chips))

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "player_count": self.player_count,
            "stack_bb": self.stack_bb,
            "bb_chips": self.bb_chips,
            "sb_chips": self.sb_chips,
            "ante_chips": self.ante_chips,
            "options": dict(self.options),
        }


class ActionKind(enum.Enum):
    FOLD = "f"
    CHECK_CALL = "cc"
    BET_RAISE = "br"  # amount = total bet this street after the action ("raise to")
    # Reserved for later variants (e.g. Crazy Pineapple): amount unused, cards set.
    DISCARD = "sd"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    amount: int | None = None
    cards: tuple[str, ...] = ()

    @staticmethod
    def fold() -> Action:
        return Action(ActionKind.FOLD)

    @staticmethod
    def check_call() -> Action:
        return Action(ActionKind.CHECK_CALL)

    @staticmethod
    def raise_to(amount: int) -> Action:
        return Action(ActionKind.BET_RAISE, int(amount))


@dataclass(frozen=True)
class LegalActions:
    """Legal action set at a decision point (amounts in chips).

    ``fold`` is illegal when checking is free (PokerKit rule, kept here).
    ``raise_min``/``raise_max`` are "raise to" totals for the current street;
    both are ``None`` when raising is illegal. ``raise_max`` is all-in.
    """

    can_fold: bool
    can_check_call: bool
    call_amount: int
    raise_min: int | None
    raise_max: int | None

    @property
    def can_raise(self) -> bool:
        return self.raise_min is not None

    def contains(self, action: Action) -> bool:
        if action.kind is ActionKind.FOLD:
            return self.can_fold
        if action.kind is ActionKind.CHECK_CALL:
            return self.can_check_call
        if action.kind is ActionKind.BET_RAISE:
            return (
                self.raise_min is not None
                and self.raise_max is not None
                and action.amount is not None
                and self.raise_min <= action.amount <= self.raise_max
            )
        return False


@dataclass(frozen=True)
class ActionRecord:
    seat: int
    street: int
    kind: ActionKind
    amount: int | None  # raise-to total for BET_RAISE, chips added for CHECK_CALL


@dataclass(frozen=True)
class Observation:
    """What the acting player may legitimately see. No opponent hole cards."""

    variant: str
    seat: int
    player_count: int
    street: int  # 0 preflop, 1 flop, 2 turn, 3 river
    hole_cards: tuple[str, ...]
    board: tuple[str, ...]
    stacks: tuple[int, ...]  # behind, current
    bets: tuple[int, ...]  # this street, uncollected
    pot: int  # collected pots + uncollected bets
    active: tuple[bool, ...]  # not folded
    starting_stacks: tuple[int, ...]
    bb_chips: int
    history: tuple[ActionRecord, ...]

    @property
    def button(self) -> int:
        return self.player_count - 1

    @property
    def to_call(self) -> int:
        return max(self.bets) - self.bets[self.seat]

    @property
    def n_active(self) -> int:
        return sum(self.active)


@dataclass(frozen=True)
class Deal:
    """A complete chance realization for one table deal.

    ``hole[p]`` belongs to *seat/position* ``p``, not to an agent: in a matched
    block the same Deal is replayed with different agents in the seats.
    ``runout`` is the ordered sequence of burn/board cards consumed after the
    hole cards; the adapter takes from it in dealing order.
    """

    hole: tuple[tuple[str, ...], ...]
    runout: tuple[str, ...]
    deck_order: tuple[str, ...]


@dataclass
class HandOutcome:
    payoffs_chips: tuple[int, ...]
    starting_stacks: tuple[int, ...]
    final_stacks: tuple[int, ...]
    board: tuple[str, ...]
    total_pot: int
    went_to_showdown: bool
    had_all_in: bool
    decision_count: int
    history: tuple[ActionRecord, ...]


class IllegalActionError(Exception):
    def __init__(self, seat: int, action: Action, legal: LegalActions) -> None:
        super().__init__(f"seat {seat} illegal action {action} given {legal}")
        self.seat, self.action, self.legal = seat, action, legal


class Hand(Protocol):
    """One hand in progress. Created by ``GameAdapter.new_hand``."""

    def is_terminal(self) -> bool: ...
    def actor(self) -> int: ...
    def observation(self, seat: int) -> Observation: ...
    def legal_actions(self) -> LegalActions: ...
    def apply(self, action: Action) -> None: ...
    def outcome(self) -> HandOutcome: ...
    def to_phh(self, players: Sequence[str], extra: Mapping[str, Any]) -> str: ...


class GameAdapter(Protocol):
    config: GameConfig

    def cards_per_deal(self) -> int: ...
    def deal_from_deck(self, deck: Sequence[str]) -> Deal: ...
    def new_hand(
        self, deal: Deal, starting_stacks: Sequence[int] | None = None
    ) -> Hand: ...
