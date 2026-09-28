"""PokerKit-backed No-Limit Texas Hold'em adapter.

All chance events are driven from an explicit ``Deal`` (our own deterministic
deck): PokerKit's internal deck is overwritten with our order and every card is
dealt/burned explicitly, so PokerKit's module-level ``random.shuffle`` never
influences results. Betting, pot construction (incl. side pots), showdown and
chip pushing are PokerKit's.

Cash-game semantics: every hand starts from ``GameConfig.starting_stack_chips``
for every seat (no stack carry-over), no rake.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any

import pokerkit as pk

from fhr3.games.base import (
    STANDARD_DECK,
    Action,
    ActionKind,
    ActionRecord,
    Deal,
    GameConfig,
    HandOutcome,
    IllegalActionError,
    LegalActions,
    Observation,
)

_A = pk.Automation
_AUTOMATIONS = (
    _A.ANTE_POSTING,
    _A.BET_COLLECTION,
    _A.BLIND_OR_STRADDLE_POSTING,
    _A.RUNOUT_COUNT_SELECTION,
    _A.HOLE_CARDS_SHOWING_OR_MUCKING,
    _A.HAND_KILLING,
    _A.CHIPS_PUSHING,
    _A.CHIPS_PULLING,
)

_TO_PK: dict[str, pk.Card] = {s: next(iter(pk.Card.parse(s))) for s in STANDARD_DECK}
_FROM_PK: dict[pk.Card, str] = {c: s for s, c in _TO_PK.items()}

HOLE_CARDS = 2
RUNOUT_CARDS = 8  # burn, flop x3, burn, turn, burn, river


class PokerKitHoldemHand:
    def __init__(
        self,
        game: pk.NoLimitTexasHoldem,
        config: GameConfig,
        deal: Deal,
        starting_stacks: Sequence[int],
    ) -> None:
        self._game = game
        self._config = config
        self._deal = deal
        self._starting = tuple(int(s) for s in starting_stacks)
        k = config.player_count
        self._state = game(self._starting, k)
        # Make PokerKit's own deck agree with ours (no "not recommended" warnings,
        # and PokerKit's internal shuffle is discarded).
        self._state.deck_cards = deque(_TO_PK[c] for c in deal.deck_order)
        for seat in range(k):
            self._state.deal_hole([_TO_PK[c] for c in deal.hole[seat]])
        self._runout = iter(deal.runout)
        self._history: list[ActionRecord] = []
        self._decisions = 0
        self._had_all_in = False
        self._legal: LegalActions | None = None  # cached per decision point
        self._advance()

    def _advance(self) -> None:
        st = self._state
        while st.status and st.actor_index is None:
            if st.can_burn_card():
                st.burn_card(_TO_PK[next(self._runout)])
            elif st.can_deal_board():
                st.deal_board(
                    [_TO_PK[next(self._runout)] for _ in range(st.board_dealing_count)]
                )
            else:  # pragma: no cover - would indicate an unhandled PokerKit phase
                raise RuntimeError(f"PokerKit state stalled: {st.operations[-1:]}")

    # --- Hand protocol -------------------------------------------------------
    def is_terminal(self) -> bool:
        return not self._state.status

    def actor(self) -> int:
        idx = self._state.actor_index
        if idx is None:
            raise RuntimeError("no actor: hand is terminal")
        return int(idx)

    def legal_actions(self) -> LegalActions:
        if self._legal is None:
            self._legal = self._compute_legal_actions()
        return self._legal

    def _compute_legal_actions(self) -> LegalActions:
        st = self._state
        can_raise = st.can_complete_bet_or_raise_to()
        call_amount = int(st.checking_or_calling_amount or 0)
        return LegalActions(
            # PokerKit's cash-game mode permits (with a warning) folding when
            # checking is free; FHR3 treats that dominated action as illegal. The
            # short-circuit also avoids can_fold()'s warning in that case.
            can_fold=call_amount > 0 and st.can_fold(),
            can_check_call=st.can_check_or_call(),
            call_amount=call_amount,
            raise_min=int(st.min_completion_betting_or_raising_to_amount)
            if can_raise
            else None,
            raise_max=int(st.max_completion_betting_or_raising_to_amount)
            if can_raise
            else None,
        )

    def observation(self, seat: int) -> Observation:
        st = self._state
        board = tuple(_FROM_PK[c] for c in st.get_board_cards(0))
        return Observation(
            variant=self._config.variant,
            seat=seat,
            player_count=self._config.player_count,
            street=int(st.street_index) if st.street_index is not None else 3,
            hole_cards=tuple(_FROM_PK[c] for c in st.hole_cards[seat]),
            board=board,
            stacks=tuple(int(x) for x in st.stacks),
            bets=tuple(int(x) for x in st.bets),
            pot=int(st.total_pot_amount),
            active=tuple(bool(x) for x in st.statuses),
            starting_stacks=self._starting,
            bb_chips=self._config.bb_chips,
            history=tuple(self._history),
        )

    def apply(self, action: Action) -> None:
        st = self._state
        seat = self.actor()
        legal = self.legal_actions()
        if not legal.contains(action):
            raise IllegalActionError(seat, action, legal)
        street = int(st.street_index)
        if action.kind is ActionKind.FOLD:
            st.fold()
            rec = ActionRecord(seat, street, action.kind, None)
        elif action.kind is ActionKind.CHECK_CALL:
            rec = ActionRecord(seat, street, action.kind, legal.call_amount)
            st.check_or_call()
        else:
            assert action.amount is not None
            st.complete_bet_or_raise_to(action.amount)
            rec = ActionRecord(seat, street, action.kind, action.amount)
        if st.stacks[seat] == 0:
            self._had_all_in = True
        self._history.append(rec)
        self._decisions += 1
        self._legal = None
        self._advance()

    def outcome(self) -> HandOutcome:
        if not self.is_terminal():
            raise RuntimeError("hand not finished")
        st = self._state
        folds = sum(1 for r in self._history if r.kind is ActionKind.FOLD)
        return HandOutcome(
            payoffs_chips=tuple(int(x) for x in st.payoffs),
            starting_stacks=self._starting,
            final_stacks=tuple(int(x) for x in st.stacks),
            board=tuple(_FROM_PK[c] for c in st.get_board_cards(0)),
            total_pot=int(st.total_pushed_amount),
            went_to_showdown=(self._config.player_count - folds) > 1,
            had_all_in=self._had_all_in,
            decision_count=self._decisions,
            history=tuple(self._history),
        )

    def to_phh(self, players: Sequence[str], extra: Mapping[str, Any]) -> str:
        hh = pk.HandHistory.from_game_state(self._game, self._state)
        hh.players = list(players)
        hh.user_defined_fields = {f"_{k}": v for k, v in extra.items()}
        return hh.dumps()


class PokerKitHoldemAdapter:
    """GameAdapter for No-Limit Hold'em (variant ``nlhe``)."""

    def __init__(self, config: GameConfig) -> None:
        if config.variant != "nlhe":
            raise ValueError(f"PokerKitHoldemAdapter cannot run {config.variant!r}")
        self.config = config
        k = config.player_count
        blinds = (config.sb_chips, config.bb_chips) + (0,) * (k - 2)
        self._game = pk.NoLimitTexasHoldem(
            _AUTOMATIONS,
            True,
            config.ante_chips,
            blinds,
            config.bb_chips,
            mode=pk.Mode.CASH_GAME,
        )

    def cards_per_deal(self) -> int:
        return HOLE_CARDS * self.config.player_count + RUNOUT_CARDS

    def deal_from_deck(self, deck: Sequence[str]) -> Deal:
        k = self.config.player_count
        hole = tuple(
            tuple(deck[HOLE_CARDS * p : HOLE_CARDS * (p + 1)]) for p in range(k)
        )
        start = HOLE_CARDS * k
        return Deal(
            hole=hole,
            runout=tuple(deck[start : start + RUNOUT_CARDS]),
            deck_order=tuple(deck),
        )

    def new_hand(
        self, deal: Deal, starting_stacks: Sequence[int] | None = None
    ) -> PokerKitHoldemHand:
        stacks = (
            tuple(starting_stacks)
            if starting_stacks is not None
            else (self.config.starting_stack_chips,) * self.config.player_count
        )
        return PokerKitHoldemHand(self._game, self.config, deal, stacks)
