"""PokerKit-backed community-card games (the only place PokerKit is imported).

All chance events are driven from an explicit ``Deal`` (our deterministic deck):
PokerKit's internal deck is overwritten with our order and every card is
dealt/burned explicitly, so PokerKit's module-level ``random.shuffle`` never
influences results. Betting, pots (incl. side pots), showdown and chip pushing
are PokerKit's.

Variants (see docs/variants.md for the benchmark rule definitions):

  nlhe            No-Limit Hold'em                (PokerKit NoLimitTexasHoldem)
  plo             Pot-Limit Omaha                 (PokerKit PotLimitOmahaHoldem)
  aof             NLHE restricted to fold / all-in
  bomb_pot        NLHE with uniform antes, no blinds, no preflop betting
                  (custom PokerKit streets: hole cards + flop on street 0)
  crazy_pineapple 3 hole cards, one discard after flop betting
                  (FHR3-level discard + per-hand PokerKit hand type)

Cash-game semantics: every hand starts from the configured stack for every seat
(no stack carry-over), no rake.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import replace
from collections.abc import Mapping, Sequence
from typing import Any

import pokerkit as pk

from fhr3.games.base import (
    STANDARD_DECK,
    Action,
    ActionKind,
    ActionRecord,
    AllInSnapshot,
    Deal,
    GameConfig,
    HandOutcome,
    IllegalActionError,
    LegalActions,
    LegalDiscards,
    Observation,
)

_A = pk.Automation
AUTOMATIONS = (
    _A.ANTE_POSTING,
    _A.BET_COLLECTION,
    _A.BLIND_OR_STRADDLE_POSTING,
    _A.RUNOUT_COUNT_SELECTION,
    _A.HOLE_CARDS_SHOWING_OR_MUCKING,
    _A.HAND_KILLING,
    _A.CHIPS_PUSHING,
    _A.CHIPS_PULLING,
)

TO_PK: dict[str, pk.Card] = {s: next(iter(pk.Card.parse(s))) for s in STANDARD_DECK}
FROM_PK: dict[pk.Card, str] = {c: s for s, c in TO_PK.items()}

RUNOUT_CARDS = 8  # burn, flop x3, burn, turn, burn, river


class PokerKitBoardHand:
    """One hand. The base class is exactly the validated NLHE behaviour."""

    trace_format = "phh"
    street_offset = 0  # Observation.street = PokerKit street_index + offset

    def __init__(
        self,
        adapter: PokerKitBoardAdapter,
        deal: Deal,
        starting_stacks: Sequence[int],
        public_info: Mapping[str, Any] | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = adapter.config
        self._deal = deal
        self._starting = tuple(int(s) for s in starting_stacks)
        self._public = dict(public_info or {})
        k = self._config.player_count
        self._state = self._create_state(self._starting)
        # Make PokerKit's own deck agree with ours (no "not recommended" warnings,
        # and PokerKit's internal shuffle is discarded).
        self._state.deck_cards = deque(TO_PK[c] for c in deal.deck_order)
        for seat in range(k):
            self._state.deal_hole([TO_PK[c] for c in deal.hole[seat]])
        self._runout = iter(deal.runout)
        self._burned: list[str] = []
        self._history: list[ActionRecord] = []
        self._decisions = 0
        self._had_all_in = False
        self._legal: LegalActions | LegalDiscards | None = None  # cached per decision point
        self._snapshot: AllInSnapshot | None = None
        self._advance()

    def _create_state(self, stacks: tuple[int, ...]) -> pk.State:
        return self._adapter.create_state(stacks)

    # ------------------------------------------------------------ chance
    def _pause_for_fhr3_decision(self) -> bool:
        """Hook: return True to stop before the next chance event (discards)."""
        return False

    def _advance(self) -> None:
        st = self._state
        while st.status and st.actor_index is None:
            if self._pause_for_fhr3_decision():
                return
            if self._snapshot is None:
                self._maybe_snapshot()
            if st.can_burn_card():
                card = next(self._runout)
                self._burned.append(card)
                st.burn_card(TO_PK[card])
            elif st.can_deal_board():
                st.deal_board(
                    [TO_PK[next(self._runout)] for _ in range(st.board_dealing_count)]
                )
            else:  # pragma: no cover - would indicate an unhandled PokerKit phase
                raise RuntimeError(f"PokerKit state stalled: {st.operations[-1:]}")

    def _current_hole(self, seat: int) -> tuple[str, ...]:
        return tuple(FROM_PK[c] for c in self._state.hole_cards[seat])

    def _decisions_remain(self) -> bool:
        st = self._state
        with_chips = sum(1 for i, live in enumerate(st.statuses) if live and st.stacks[i] > 0)
        return with_chips > 1

    def _maybe_snapshot(self) -> None:
        """Capture the all-in runout point (read-only on PokerKit state)."""
        st = self._state
        board = tuple(FROM_PK[c] for c in st.get_board_cards(0))
        live = tuple(bool(x) for x in st.statuses)
        if len(board) >= 5 or sum(live) < 2 or self._decisions_remain():
            return
        k = self._config.player_count
        hole = tuple(self._current_hole(i) if live[i] else () for i in range(k))
        dealt_hole = {c for h in self._deal.hole for c in h}
        self._snapshot = AllInSnapshot(
            board=board,
            hole=hole,
            live=live,
            pots=tuple((int(p.amount), tuple(p.player_indices)) for p in st.pots),
            contributed=tuple(self._starting[i] - int(st.stacks[i]) for i in range(k)),
            dead=frozenset(dealt_hole | set(board) | set(self._burned)),
        )

    # ------------------------------------------------------------ Hand protocol
    def is_terminal(self) -> bool:
        return not self._state.status

    def actor(self) -> int:
        idx = self._state.actor_index
        if idx is None:
            raise RuntimeError("no actor: hand is terminal")
        return int(idx)

    def legal_actions(self) -> LegalActions | LegalDiscards:
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

    def _street(self) -> int:
        st = self._state
        return (int(st.street_index) + self.street_offset) if st.street_index is not None else 3

    def observation(self, seat: int) -> Observation:
        st = self._state
        return Observation(
            variant=self._config.variant,
            seat=seat,
            player_count=self._config.player_count,
            street=self._street(),
            hole_cards=self._current_hole(seat),
            board=tuple(FROM_PK[c] for c in st.get_board_cards(0)),
            stacks=tuple(int(x) for x in st.stacks),
            bets=tuple(int(x) for x in st.bets),
            pot=int(st.total_pot_amount),
            active=tuple(bool(x) for x in st.statuses),
            starting_stacks=self._starting,
            bb_chips=self._config.bb_chips,
            history=tuple(self._history),
            extra=self._public,
        )

    def apply(self, action: Action) -> None:
        st = self._state
        seat = self.actor()
        legal = self.legal_actions()
        if not legal.contains(action):
            raise IllegalActionError(seat, action, legal)  # type: ignore[arg-type]
        street = self._street()
        if action.kind is ActionKind.FOLD:
            st.fold()
            rec = ActionRecord(seat, street, action.kind, None)
        elif action.kind is ActionKind.CHECK_CALL:
            assert isinstance(legal, LegalActions)
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
            board=tuple(FROM_PK[c] for c in st.get_board_cards(0)),
            total_pot=int(st.total_pushed_amount),
            went_to_showdown=(self._config.player_count - folds) > 1,
            had_all_in=self._had_all_in,
            decision_count=self._decisions,
            history=tuple(self._history),
            allin_snapshot=self._snapshot,
        )

    # ------------------------------------------------------------ traces
    def to_trace(self, players: Sequence[str], extra: Mapping[str, Any]) -> str:
        if self.trace_format == "phh":
            return self.to_phh(players, extra)
        return self.to_json_trace(players, extra)

    def to_phh(self, players: Sequence[str], extra: Mapping[str, Any]) -> str:
        hh = pk.HandHistory.from_game_state(self._adapter.phh_game, self._state)
        hh.players = list(players)
        hh.user_defined_fields = {f"_{k}": v for k, v in extra.items()}
        return hh.dumps()

    def to_json_trace(self, players: Sequence[str], extra: Mapping[str, Any]) -> str:
        """FHR3 JSON trace for variants PHH cannot express (discards, bomb pots)."""
        st = self._state
        return json.dumps(
            {
                "format": "fhr3-trace-v1",
                "variant": self._config.variant,
                "game": self._config.to_dict(),
                "players": list(players),
                "starting_stacks": list(self._starting),
                "deal": {"hole": [list(h) for h in self._deal.hole], "runout": list(self._deal.runout)},
                "public_info": {k: list(v) if isinstance(v, tuple) else v for k, v in self._public.items()},
                "actions": [
                    {"seat": r.seat, "street": r.street, "kind": r.kind.value, "amount": r.amount}
                    | ({"cards": list(r.cards)} if r.cards else {})
                    for r in self._history
                ],
                "board": [FROM_PK[c] for c in st.get_board_cards(0)],
                "payoffs": [int(x) for x in st.payoffs] if not st.status else None,
                "fhr3": dict(extra),
            },
            indent=1,
            default=str,
        )


class AoFHand(PokerKitBoardHand):
    """All-in-or-fold: the only non-fold action is all-in (shove or call all-in)."""

    def _compute_legal_actions(self) -> LegalActions:
        la = super()._compute_legal_actions()
        if la.raise_max is not None:
            return LegalActions(la.can_fold, False, la.call_amount, la.raise_max, la.raise_max)
        # Facing an all-in: calling is the (all-in) call. Limping/checking is only
        # permitted when nothing else is (not reachable with equal stacks).
        stack = int(self._state.stacks[self.actor()])
        allowed = la.call_amount >= stack or la.call_amount == 0
        return LegalActions(la.can_fold, la.can_check_call and allowed, la.call_amount, None, None)


class BombPotHand(PokerKitBoardHand):
    """Street 0 of the custom PokerKit game is the flop."""

    trace_format = "json"
    street_offset = 1


class CrazyPineappleHand(PokerKitBoardHand):
    """3 hole cards; every live player discards 1 after the flop betting round.

    The discard is an FHR3-level decision: when the flop betting round is over
    (or skipped because of all-ins) and before the turn burn, the hand pauses and
    live players discard in seat order (seat 0 = SB first). The kept two cards are
    registered with the per-hand PokerKit hand type, which evaluates only those
    at showdown. PokerKit's own draw mechanism is not used (it always deals
    replacement cards).
    """

    trace_format = "json"
    DISCARD_STREET = 1  # after the flop betting round

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._kept: dict[int, tuple[str, ...]] = {}
        self._discarded: dict[int, str] = {}
        super().__init__(*args, **kwargs)

    def _create_state(self, stacks: tuple[int, ...]) -> pk.State:
        self._hand_type = make_crazy_pineapple_hand_type()
        return self._adapter.create_state(stacks, hand_type=self._hand_type)

    def _pending_discarders(self) -> list[int]:
        st = self._state
        if len(tuple(st.get_board_cards(0))) != 3:
            return []
        return [i for i, live in enumerate(st.statuses) if live and i not in self._kept]

    def _pause_for_fhr3_decision(self) -> bool:
        return bool(self._pending_discarders())

    def _decisions_remain(self) -> bool:
        if len(tuple(self._state.get_board_cards(0))) <= 3 and any(
            live and i not in self._kept for i, live in enumerate(self._state.statuses)
        ):
            return True  # discards still to come
        return super()._decisions_remain()

    def _current_hole(self, seat: int) -> tuple[str, ...]:
        if seat in self._kept:
            return self._kept[seat]
        return super()._current_hole(seat)

    def observation(self, seat: int) -> Observation:
        """Discards are private: other players' discarded cards are censored."""
        obs = super().observation(seat)
        if not any(r.kind is ActionKind.DISCARD and r.seat != seat for r in obs.history):
            return obs
        hist = tuple(
            ActionRecord(r.seat, r.street, r.kind, r.amount, ()) if r.kind is ActionKind.DISCARD and r.seat != seat else r
            for r in obs.history
        )
        return replace(obs, history=hist)

    def is_terminal(self) -> bool:
        return not self._state.status

    def actor(self) -> int:
        pending = self._pending_discarders() if self._state.actor_index is None else []
        if pending:
            return pending[0]
        return super().actor()

    def _compute_legal_actions(self) -> LegalActions | LegalDiscards:  # type: ignore[override]
        if self._state.actor_index is None and self._pending_discarders():
            return LegalDiscards(self._current_hole(self.actor()), 1)
        return super()._compute_legal_actions()

    def _street(self) -> int:
        if self._state.actor_index is None and self._pending_discarders():
            return self.DISCARD_STREET
        return super()._street()

    def apply(self, action: Action) -> None:
        legal = self.legal_actions()
        if not isinstance(legal, LegalDiscards):
            return super().apply(action)
        seat = self.actor()
        if not legal.contains(action):
            raise IllegalActionError(seat, action, legal)  # type: ignore[arg-type]
        (card,) = action.cards
        self._discarded[seat] = card
        self._kept[seat] = tuple(c for c in legal.cards if c != card)
        full = frozenset(TO_PK[c] for c in legal.cards)
        self._hand_type.kept[full] = tuple(TO_PK[c] for c in self._kept[seat])
        self._history.append(ActionRecord(seat, self.DISCARD_STREET, ActionKind.DISCARD, None, (card,)))
        self._decisions += 1
        self._legal = None
        self._advance()


def make_crazy_pineapple_hand_type() -> type[pk.StandardHighHand]:
    """A per-hand PokerKit hand type: 3-card holes evaluate only the kept 2.

    Showdown before a registered discard is a bug and raises.
    """
    kept: dict[frozenset[pk.Card], tuple[pk.Card, ...]] = {}

    class CrazyPineappleHandType(pk.StandardHighHand):
        @classmethod
        def from_game(cls, hole_cards: Any, board_cards: Any = ()) -> pk.StandardHighHand:
            hole = tuple(pk.Card.clean(hole_cards))
            if len(hole) == 3:
                key = frozenset(hole)
                if key not in kept:
                    raise RuntimeError("Crazy Pineapple showdown before discard")
                hole = kept[key]
            return pk.StandardHighHand.from_game(hole, board_cards)

    CrazyPineappleHandType.kept = kept  # type: ignore[attr-defined]
    return CrazyPineappleHandType


# ================================================================== adapters
class PokerKitBoardAdapter:
    """Base adapter: No-Limit Hold'em (variant ``nlhe``)."""

    variant = "nlhe"
    hand_class: type[PokerKitBoardHand] = PokerKitBoardHand
    hole_cards = 2
    showdown = "holdem"

    def __init__(self, config: GameConfig) -> None:
        if config.variant != self.variant:
            raise ValueError(f"{type(self).__name__} cannot run {config.variant!r}")
        self.config = config
        self._validate_options(dict(config.options))
        self.phh_game = self._make_game()

    def _validate_options(self, options: dict[str, Any]) -> None:
        if options:
            raise ValueError(f"{self.variant} takes no options, got {sorted(options)}")

    @property
    def _blinds(self) -> tuple[int, ...]:
        c = self.config
        return (c.sb_chips, c.bb_chips) + (0,) * (c.player_count - 2)

    def _make_game(self) -> Any:
        c = self.config
        return pk.NoLimitTexasHoldem(
            AUTOMATIONS, True, c.ante_chips, self._blinds, c.bb_chips, mode=pk.Mode.CASH_GAME
        )

    def create_state(self, stacks: Sequence[int], **_: Any) -> pk.State:
        return self.phh_game(tuple(stacks), self.config.player_count)

    @property
    def deal_layout(self) -> str:
        return f"board-h{self.hole_cards}-k{self.config.player_count}"

    def cards_per_deal(self) -> int:
        return self.hole_cards * self.config.player_count + RUNOUT_CARDS

    def deal_from_deck(self, deck: Sequence[str]) -> Deal:
        k, h = self.config.player_count, self.hole_cards
        hole = tuple(tuple(deck[h * p : h * (p + 1)]) for p in range(k))
        start = h * k
        return Deal(hole=hole, runout=tuple(deck[start : start + RUNOUT_CARDS]), deck_order=tuple(deck))

    def new_hand(
        self,
        deal: Deal,
        starting_stacks: Sequence[int] | None = None,
        public_info: Mapping[str, Any] | None = None,
    ) -> PokerKitBoardHand:
        stacks = (
            tuple(starting_stacks)
            if starting_stacks is not None
            else (self.config.starting_stack_chips,) * self.config.player_count
        )
        return self.hand_class(self, deal, stacks, public_info)


class PotLimitOmahaAdapter(PokerKitBoardAdapter):
    """Pot-Limit Omaha: 4 hole cards, exactly 2 hole + 3 board at showdown."""

    variant = "plo"
    hole_cards = 4
    showdown = "omaha"

    def _make_game(self) -> Any:
        c = self.config
        return pk.PotLimitOmahaHoldem(
            AUTOMATIONS, True, c.ante_chips, self._blinds, c.bb_chips, mode=pk.Mode.CASH_GAME
        )


class AllInOrFoldAdapter(PokerKitBoardAdapter):
    """4-max AoF: NLHE engine, legal actions restricted to fold / all-in."""

    variant = "aof"
    hand_class = AoFHand


class BombPotAdapter(PokerKitBoardAdapter):
    """Single-board NLHE bomb pot.

    Every seat posts ``options.ante_bb`` big blinds as an ante; there are no
    blinds and no preflop betting. Street 0 deals the hole cards, burns, and deals
    the flop; the first strategic decision is on the flop, first to act = seat 0
    (the SB seat). Turn and river as in NLHE. Min bet = 1 BB.
    """

    variant = "bomb_pot"
    hand_class = BombPotHand

    def _validate_options(self, options: dict[str, Any]) -> None:
        unknown = set(options) - {"ante_bb"}
        if unknown:
            raise ValueError(f"bomb_pot options: unknown {sorted(unknown)}")
        ante_bb = float(options.get("ante_bb", 2.0))
        ante = ante_bb * self.config.bb_chips
        if ante != int(ante) or ante <= 0 or ante >= self.config.starting_stack_chips:
            raise ValueError("ante_bb must give a positive integer chip ante below the stack")
        if self.config.ante_chips:
            raise ValueError("bomb_pot uses options.ante_bb, not ante_chips")
        self.ante_chips = int(ante)

    def _make_game(self) -> Any:
        return None  # custom streets: no PHH variant

    def create_state(self, stacks: Sequence[int], **_: Any) -> pk.State:
        c = self.config
        bb = c.bb_chips
        streets = (
            pk.Street(True, (False, False), 3, False, pk.Opening.POSITION, bb, None),
            pk.Street(True, (), 1, False, pk.Opening.POSITION, bb, None),
            pk.Street(True, (), 1, False, pk.Opening.POSITION, bb, None),
        )
        return pk.State(
            AUTOMATIONS, pk.Deck.STANDARD, (pk.StandardHighHand,), streets,
            pk.BettingStructure.NO_LIMIT, True, self.ante_chips, 0, 0,
            tuple(stacks), c.player_count, mode=pk.Mode.CASH_GAME,
        )


class CrazyPineappleAdapter(PokerKitBoardAdapter):
    """Crazy Pineapple: 3 hole cards, discard 1 after the flop betting round."""

    variant = "crazy_pineapple"
    hand_class = CrazyPineappleHand
    hole_cards = 3

    def _make_game(self) -> Any:
        return None  # discard without replacement: no PHH variant

    def create_state(self, stacks: Sequence[int], hand_type: Any = None, **_: Any) -> pk.State:
        if hand_type is None:
            raise ValueError("Crazy Pineapple states need a per-hand hand type")
        c = self.config
        bb = c.bb_chips
        streets = (
            pk.Street(False, (False, False, False), 0, False, pk.Opening.POSITION, bb, None),
            pk.Street(True, (), 3, False, pk.Opening.POSITION, bb, None),
            pk.Street(True, (), 1, False, pk.Opening.POSITION, bb, None),
            pk.Street(True, (), 1, False, pk.Opening.POSITION, bb, None),
        )
        return pk.State(
            AUTOMATIONS, pk.Deck.STANDARD, (hand_type,), streets,
            pk.BettingStructure.NO_LIMIT, True, c.ante_chips, self._blinds, 0,
            tuple(stacks), c.player_count, mode=pk.Mode.CASH_GAME,
        )


ADAPTERS: dict[str, type[PokerKitBoardAdapter]] = {
    a.variant: a
    for a in (PokerKitBoardAdapter, PotLimitOmahaAdapter, AllInOrFoldAdapter, BombPotAdapter, CrazyPineappleAdapter)
}
