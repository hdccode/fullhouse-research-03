"""Matched-block protocol (the statistical unit of FHR3).

Protocol v1 (``MATCHED_PROTOCOL_VERSION``) for a k-player game:

1. ``block_seed = derive_seed("fhr3-block", root_seed, block_id)``.
   One deck is shuffled from the *chance* stream of that seed and turned into a
   single ``Deal``: hole cards are bound to seats/positions (seat 0 = SB, seat
   k-1 = button), plus a fixed burn/board runout. Decks do not depend on the
   pairing, agents or stack depth, so blocks with the same id are chance-matched
   across pairings and across stack configs sharing a root seed.
2. For each candidate seat s = 0..k-1, and for each side X in (A, B), one hand
   is played on that same Deal:
     * the candidate X sits in seat s (receives seat s's cards and position);
     * reference agent j (j = 0..k-2) sits in seat (s + 1 + j) mod k, i.e. the
       reference line-up *relative to the candidate* is identical in every hand;
     * every seat starts with the configured stack (cash-game reset).
   That is 2k played hands per block (12 for 6-max, 8 for 4-max).
3. X_{X,s} = candidate X's net result in seat s, in big blinds.
   D_s = X_{A,s} - X_{B,s}.   D = sum_s D_s  (block total, BB).
   Per candidate-hand, the BB/100 estimand is 100 * E[D] / k.

Randomness inside hands comes from keyed decision streams (see ``rng.py``):
  candidate: ("decision", seed, "candidate"[":A"|":B"], salt, s, ordinal)
  reference: ("decision", seed, "reference"[":A"|":B"], salt, s, seat, ordinal)
where ordinal is the acting seat's decision index within the hand. The
":A"/":B" suffix is present only under ``independent`` coupling.

Hands inside a block are *not* independent observations. Only the block-level
D (and its components, for diagnostics) leaves this module.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from fhr3.agents import Agent
from fhr3.configs.experiment import RNGConfig
from fhr3.games.base import STANDARD_DECK, Deal, GameAdapter, IllegalActionError
from fhr3.rng import DecisionRNG, KeyedStream, derive_seed

MATCHED_PROTOCOL_VERSION = "fhr3-matched-v1"
SIDES = ("A", "B")


def block_seed(root_seed: int, block_id: int) -> int:
    return derive_seed("fhr3-block", root_seed, block_id)


def reference_seats(k: int, candidate_seat: int) -> list[int]:
    """Seat occupied by reference agent j when the candidate is in ``candidate_seat``."""
    return [(candidate_seat + 1 + j) % k for j in range(k - 1)]


def make_deal(adapter: GameAdapter, seed: int, chance_salt: int = 0) -> Deal:
    deck = KeyedStream("chance", seed, chance_salt).shuffle(STANDARD_DECK)
    return adapter.deal_from_deck(deck)


@dataclass(frozen=True)
class MatchedBlockSpec:
    """Everything needed to reproduce one block exactly."""

    experiment_id: str
    config_hash: str
    pairing_id: str
    pairing_hash: str
    root_seed: int
    block_id: int
    rng: RNGConfig

    @property
    def seed(self) -> int:
        return block_seed(self.root_seed, self.block_id)


@dataclass
class HandSummary:
    side: str
    candidate_seat: int
    payoff_bb: float
    pot_bb: float
    showdown: bool
    all_in: bool
    decisions: int


@dataclass
class MatchedBlockResult:
    block_id: int
    seed: int
    player_count: int
    valid: bool
    error_code: str | None = None
    error_detail: str | None = None
    seat_payoff_a: list[float] = field(default_factory=list)
    seat_payoff_b: list[float] = field(default_factory=list)
    hands: list[HandSummary] = field(default_factory=list)
    decision_count: int = 0
    runtime_ms: float = 0.0
    agent_ms: float = 0.0
    traces: dict[str, str] = field(default_factory=dict)

    @property
    def seat_D(self) -> list[float]:
        return [a - b for a, b in zip(self.seat_payoff_a, self.seat_payoff_b, strict=True)]

    @property
    def block_payoff_a(self) -> float | None:
        return sum(self.seat_payoff_a) if self.valid else None

    @property
    def block_payoff_b(self) -> float | None:
        return sum(self.seat_payoff_b) if self.valid else None

    @property
    def D(self) -> float | None:
        return sum(self.seat_D) if self.valid else None

    @property
    def played_hands(self) -> int:
        return len(self.hands)


class _Timer:
    __slots__ = ("total",)

    def __init__(self) -> None:
        self.total = 0.0


def _decision_rng(
    spec: MatchedBlockSpec, seed: int, side: str, cand_seat: int, acting: int,
    is_candidate: bool, ordinal: int,
) -> DecisionRNG:
    r = spec.rng
    if is_candidate:
        label = "candidate" if r.candidate_coupling == "shared" else f"candidate:{side}"
        return DecisionRNG("decision", seed, label, r.salts["candidate"], cand_seat, ordinal)
    label = "reference" if r.reference_coupling == "shared" else f"reference:{side}"
    return DecisionRNG(
        "decision", seed, label, r.salts["reference"], cand_seat, acting, ordinal
    )


def play_hand(
    adapter: GameAdapter,
    deal: Deal,
    seat_agents: Sequence[Agent],
    rng_for: Any,
    timer: _Timer,
    trace_players: Sequence[str] | None = None,
    trace_extra: dict[str, Any] | None = None,
) -> tuple[Any, str | None]:
    """Play one hand. ``rng_for(acting_seat, ordinal) -> DecisionRNG``."""
    hand = adapter.new_hand(deal)
    ordinals = [0] * len(seat_agents)
    try:
        while not hand.is_terminal():
            seat = hand.actor()
            obs = hand.observation(seat)
            legal = hand.legal_actions()
            rng = rng_for(seat, ordinals[seat])
            ordinals[seat] += 1
            t0 = time.perf_counter()
            action = seat_agents[seat].act(obs, legal, rng)
            timer.total += time.perf_counter() - t0
            hand.apply(action)
    except Exception as exc:
        partial = None
        if trace_players is not None:
            try:
                partial = hand.to_phh(trace_players, (trace_extra or {}) | {"partial": True})
            except Exception:  # pragma: no cover - best effort on a failing hand
                partial = None
        raise HandError(exc, partial) from exc
    outcome = hand.outcome()
    phh = hand.to_phh(trace_players, trace_extra or {}) if trace_players is not None else None
    return outcome, phh


def run_matched_block(
    spec: MatchedBlockSpec,
    adapter: GameAdapter,
    candidate_a: Agent,
    candidate_b: Agent,
    references: Sequence[Agent],
    trace: bool = False,
) -> MatchedBlockResult:
    k = adapter.config.player_count
    if len(references) != k - 1:
        raise ValueError(f"need {k - 1} reference agents, got {len(references)}")
    bb = adapter.config.bb_chips
    seed = spec.seed
    t_start = time.perf_counter()
    timer = _Timer()
    result = MatchedBlockResult(block_id=spec.block_id, seed=seed, player_count=k, valid=True)
    deal = make_deal(adapter, seed, spec.rng.salts["chance"])
    candidates = {"A": candidate_a, "B": candidate_b}
    payoffs: dict[str, list[float]] = {"A": [], "B": []}
    current = ""
    try:
        for s in range(k):
            ref_seats = reference_seats(k, s)
            for side in SIDES:
                current = f"s{s}{side}"
                agents: list[Any] = [None] * k
                agents[s] = candidates[side]
                for j, seat in enumerate(ref_seats):
                    agents[seat] = references[j]

                def rng_for(acting: int, ordinal: int, _s: int = s, _side: str = side) -> DecisionRNG:
                    return _decision_rng(spec, seed, _side, _s, acting, acting == _s, ordinal)

                players = [f"{a.agent_id}" for a in agents] if trace else None
                extra = {
                    "fhr3_block_id": spec.block_id,
                    "fhr3_seed": seed,
                    "fhr3_pairing_id": spec.pairing_id,
                    "fhr3_candidate_seat": s,
                    "fhr3_side": side,
                    "fhr3_protocol": MATCHED_PROTOCOL_VERSION,
                }
                outcome, phh = play_hand(adapter, deal, agents, rng_for, timer, players, extra)
                if sum(outcome.payoffs_chips) != 0 or sum(outcome.final_stacks) != sum(
                    outcome.starting_stacks
                ):
                    raise ChipConservationError(f"hand {current}: {outcome.payoffs_chips}")
                if phh is not None:
                    result.traces[current] = phh
                payoffs[side].append(outcome.payoffs_chips[s] / bb)
                result.hands.append(
                    HandSummary(
                        side=side,
                        candidate_seat=s,
                        payoff_bb=outcome.payoffs_chips[s] / bb,
                        pot_bb=outcome.total_pot / bb,
                        showdown=outcome.went_to_showdown,
                        all_in=outcome.had_all_in,
                        decisions=outcome.decision_count,
                    )
                )
                result.decision_count += outcome.decision_count
    except Exception as exc:  # any failure invalidates the whole block
        if isinstance(exc, HandError):
            if exc.partial_phh is not None:
                result.traces[current + "-partial"] = exc.partial_phh
            exc = exc.original
        result.valid = False
        result.error_code = _error_code(exc)
        result.error_detail = f"{current}: {exc}"[:2000]
    result.seat_payoff_a = payoffs["A"] if result.valid else []
    result.seat_payoff_b = payoffs["B"] if result.valid else []
    result.runtime_ms = (time.perf_counter() - t_start) * 1000.0
    result.agent_ms = timer.total * 1000.0
    return result


class ChipConservationError(AssertionError):
    pass


class HandError(Exception):
    def __init__(self, original: BaseException, partial_phh: str | None) -> None:
        super().__init__(str(original))
        self.original, self.partial_phh = original, partial_phh


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, IllegalActionError):
        return "ILLEGAL_ACTION"
    if isinstance(exc, ChipConservationError):
        return "CHIP_CONSERVATION"
    return f"EXCEPTION:{type(exc).__name__}"
