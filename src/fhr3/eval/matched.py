"""Matched-block protocols (the statistical unit of FHR3).

Common structure for a k-player game:

1. ``block_seed = derive_seed("fhr3-block", root_seed, block_id)``.
2. For each candidate seat s = 0..k-1 and side X in (A, B), the candidate X sits
   in table seat s, reference agent j (j = 0..k-2) sits in seat (s + 1 + j) mod k,
   and X_{X,s} (candidate's net result, BB) is recorded.
3. D_s = X_{A,s} - X_{B,s};  D = sum_s D_s  (block total, BB).

Protocols
---------
``fhr3-matched-v1`` (single hand per seat/side; all variants except Nit Game):
   One deck is shuffled from ``KeyedStream("chance", seed, salt_chance)`` and
   turned into one Deal (hole cards bound to seats; seat 0 = SB, seat k-1 =
   button). Each of the 2k hands is played on that Deal from full stacks.
   Decision streams:
     candidate: ("decision", seed, "candidate"[":A"|":B"], salt, s, ordinal)
     reference: ("decision", seed, "reference"[":A"|":B"], salt, s, seat, ordinal)

``fhr3-nit-round-v1`` (Nit Game; see docs/variants.md):
   Each seat/side plays one complete nit round (a sequence of hands with
   persistent nit-button state) starting from the empty state. Hand h of the
   round uses Deal ``KeyedStream("chance", seed, salt_chance, "hand", h)``; the
   dealer button rotates one seat per hand (table seat t sits in position
   (t - h) mod k). Decision keys append ("hand", h) and use table seats.
   A-side and B-side rounds for seat s share the Deal of every hand index, so
   they are matched hand-by-hand for as long as both rounds last.

Hands inside a block are never independent observations; only block-level
quantities leave this module (seat components are stored for diagnostics).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from fhr3.agents import Agent
from fhr3.configs.experiment import RNGConfig
from fhr3.games.base import STANDARD_DECK, Deal, GameAdapter, HandOutcome, IllegalActionError
from fhr3.rng import DecisionRNG, KeyedStream, derive_seed

MATCHED_PROTOCOL_VERSION = "fhr3-matched-v1"
NIT_PROTOCOL_VERSION = "fhr3-nit-round-v1"
SIDES = ("A", "B")


def block_seed(root_seed: int, block_id: int) -> int:
    return derive_seed("fhr3-block", root_seed, block_id)


def reference_seats(k: int, candidate_seat: int) -> list[int]:
    """Seat occupied by reference agent j when the candidate is in ``candidate_seat``."""
    return [(candidate_seat + 1 + j) % k for j in range(k - 1)]


def make_deal(adapter: GameAdapter, seed: int, chance_salt: int = 0, hand_index: int | None = None) -> Deal:
    if hand_index is None:
        stream = KeyedStream("chance", seed, chance_salt)
    else:
        stream = KeyedStream("chance", seed, chance_salt, "hand", hand_index)
    return adapter.deal_from_deck(stream.shuffle(STANDARD_DECK))


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
    hand_index: int = 0
    estimates_bb: dict[str, float] = field(default_factory=dict)
    allin_runout: bool = False  # an all-in snapshot (runout with no decisions left) exists


@dataclass
class MatchedBlockResult:
    block_id: int
    seed: int
    player_count: int
    valid: bool
    protocol: str = MATCHED_PROTOCOL_VERSION
    error_code: str | None = None
    error_detail: str | None = None
    seat_payoff_a: list[float] = field(default_factory=list)
    seat_payoff_b: list[float] = field(default_factory=list)
    # estimator name -> side -> per-seat estimates (BB); same estimand as payoff
    seat_estimates: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    hands: list[HandSummary] = field(default_factory=list)
    decision_count: int = 0
    runtime_ms: float = 0.0
    agent_ms: float = 0.0
    estimator_ms: float = 0.0
    traces: dict[str, str] = field(default_factory=dict)
    variant_info: dict[str, Any] = field(default_factory=dict)

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

    def estimator_D(self, name: str) -> float | None:
        est = self.seat_estimates.get(name)
        if not self.valid or est is None:
            return None
        return sum(est["A"]) - sum(est["B"])

    @property
    def played_hands(self) -> int:
        return len(self.hands)

    def hands_for(self, side: str) -> int:
        return sum(1 for h in self.hands if h.side == side)


class _Timer:
    __slots__ = ("total",)

    def __init__(self) -> None:
        self.total = 0.0


# ------------------------------------------------------------------ estimator hook
@dataclass
class DecisionEvent:
    seat: int
    observation: Any
    legal: Any
    action: Any
    agent: Agent


@dataclass
class HandContext:
    """Everything an estimator may use about one finished hand."""

    adapter: GameAdapter
    deal: Deal
    outcome: HandOutcome
    candidate_position: int
    seat_agents: Sequence[Agent]
    decisions: list[DecisionEvent]
    # Estimator randomness key: independent of the side (A/B) so identical
    # A/B hands get identical estimates (CRN for the estimator itself).
    key: tuple[Any, ...]


class HandEstimator(Protocol):
    name: str
    needs_decision_log: bool

    def estimate(self, ctx: HandContext) -> float:
        """Candidate's estimated payoff in chips (same estimand as realized)."""
        ...


# ------------------------------------------------------------------ hand loop
def play_hand(
    adapter: GameAdapter,
    deal: Deal,
    seat_agents: Sequence[Agent],
    rng_for: Callable[[int, int], DecisionRNG],
    timer: _Timer,
    trace_players: Sequence[str] | None = None,
    trace_extra: dict[str, Any] | None = None,
    public_info: Mapping[str, Any] | None = None,
    decision_log: list[DecisionEvent] | None = None,
) -> tuple[HandOutcome, tuple[str, str] | None]:
    """Play one hand. ``rng_for(acting_seat, ordinal) -> DecisionRNG``.

    Returns the outcome and, when tracing, ``(format, text)`` with format
    ``phh`` or ``json``.
    """
    hand = adapter.new_hand(deal, public_info=public_info) if public_info else adapter.new_hand(deal)
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
            if decision_log is not None:
                decision_log.append(DecisionEvent(seat, obs, legal, action, seat_agents[seat]))
            hand.apply(action)
    except Exception as exc:
        partial = None
        if trace_players is not None:
            try:
                partial = hand.to_trace(trace_players, (trace_extra or {}) | {"partial": True})
            except Exception:  # pragma: no cover - best effort on a failing hand
                partial = None
        raise HandError(exc, partial, getattr(hand, "trace_format", "phh")) from exc
    outcome = hand.outcome()
    if trace_players is None:
        return outcome, None
    return outcome, (hand.trace_format, hand.to_trace(trace_players, trace_extra or {}))


def _check_conservation(outcome: HandOutcome, label: str) -> None:
    if sum(outcome.payoffs_chips) != 0 or sum(outcome.final_stacks) != sum(outcome.starting_stacks):
        raise ChipConservationError(f"hand {label}: {outcome.payoffs_chips}")


def _label_rng(r: RNGConfig, side: str, candidate: bool) -> str:
    if candidate:
        return "candidate" if r.candidate_coupling == "shared" else f"candidate:{side}"
    return "reference" if r.reference_coupling == "shared" else f"reference:{side}"


@dataclass
class _Block:
    spec: MatchedBlockSpec
    adapter: GameAdapter
    candidates: dict[str, Agent]
    references: Sequence[Agent]
    trace: bool
    estimators: Sequence[HandEstimator]
    timer: _Timer
    result: MatchedBlockResult
    current: str = ""  # label of the hand being played (for error reports)

    @property
    def k(self) -> int:
        return self.adapter.config.player_count

    @property
    def bb(self) -> int:
        return self.adapter.config.bb_chips

    def table(self, side: str, s: int) -> list[Agent]:
        agents: list[Any] = [None] * self.k
        agents[s] = self.candidates[side]
        for j, seat in enumerate(reference_seats(self.k, s)):
            agents[seat] = self.references[j]
        return agents

    def trace_extra(self, side: str, s: int, protocol: str, **more: Any) -> dict[str, Any]:
        return {
            "fhr3_block_id": self.spec.block_id,
            "fhr3_seed": self.spec.seed,
            "fhr3_pairing_id": self.spec.pairing_id,
            "fhr3_candidate_seat": s,
            "fhr3_side": side,
            "fhr3_protocol": protocol,
        } | more

    def run_estimators(
        self, deal: Deal, outcome: HandOutcome, cand_pos: int, agents: Sequence[Agent],
        log: list[DecisionEvent] | None, key: tuple[Any, ...],
    ) -> dict[str, float]:
        if not self.estimators:
            return {}
        t0 = time.perf_counter()
        ctx = HandContext(self.adapter, deal, outcome, cand_pos, agents, log or [], key)
        out = {e.name: e.estimate(ctx) / self.bb for e in self.estimators}
        self.result.estimator_ms += (time.perf_counter() - t0) * 1000.0
        return out


class SingleHandProtocol:
    version = MATCHED_PROTOCOL_VERSION

    def play(self, blk: _Block, side: str, s: int, deal: Deal) -> tuple[float, dict[str, float]]:
        spec, seed = blk.spec, blk.spec.seed
        r = spec.rng
        agents = blk.table(side, s)

        def rng_for(acting: int, ordinal: int) -> DecisionRNG:
            if acting == s:
                return DecisionRNG("decision", seed, _label_rng(r, side, True), r.salts["candidate"], s, ordinal)
            return DecisionRNG("decision", seed, _label_rng(r, side, False), r.salts["reference"], s, acting, ordinal)

        players = [a.agent_id for a in agents] if blk.trace else None
        need_log = any(e.needs_decision_log for e in blk.estimators)
        log: list[DecisionEvent] | None = [] if need_log else None
        outcome, text = play_hand(
            blk.adapter, deal, agents, rng_for, blk.timer, players,
            blk.trace_extra(side, s, self.version), decision_log=log,
        )
        label = f"s{s}{side}"
        _check_conservation(outcome, label)
        if text is not None:
            blk.result.traces[f"{label}.{text[0]}"] = text[1]
        payoff = outcome.payoffs_chips[s] / blk.bb
        est = blk.run_estimators(deal, outcome, s, agents, log, ("hand", seed, s))
        blk.result.hands.append(
            HandSummary(side, s, payoff, outcome.total_pot / blk.bb, outcome.went_to_showdown,
                        outcome.had_all_in, outcome.decision_count, 0, est,
                        outcome.allin_snapshot is not None)
        )
        blk.result.decision_count += outcome.decision_count
        return payoff, est

    def run(self, blk: _Block) -> None:
        deal = make_deal(blk.adapter, blk.spec.seed, blk.spec.rng.salts["chance"])
        for s in range(blk.k):
            for side in SIDES:
                blk.current = f"s{s}{side}"
                payoff, est = self.play(blk, side, s, deal)
                _record(blk.result, side, payoff, est)


def nit_update_buttons(buttons: Sequence[bool], table_payoffs: Sequence[int]) -> list[bool]:
    """A player earns a nit button in a hand where its net chip result is positive."""
    return [b or p > 0 for b, p in zip(buttons, table_payoffs, strict=True)]


def nit_resolution(buttons: Sequence[bool], penalty_bb: float) -> tuple[bool, int | None, list[float]]:
    """(round over?, nit seat or None, per-seat transfers in BB). Transfers sum to 0.

    The round is over when at most one player lacks a button. If exactly one
    lacks it, that player pays ``penalty_bb`` to every other player.
    """
    k = len(buttons)
    without = [t for t in range(k) if not buttons[t]]
    if len(without) > 1:
        return False, None, [0.0] * k
    if not without:
        return True, None, [0.0] * k
    nit = without[0]
    return True, nit, [-penalty_bb * (k - 1) if t == nit else penalty_bb for t in range(k)]


class NitRoundProtocol:
    """One complete nit round per seat/side, fresh state per block.

    Rules (``GameConfig.options``): ``nit_penalty_bb`` (default 5),
    ``max_hands`` (default 60). A player earns a nit button in a hand where its
    net chip result is positive. When at most one player lacks a button the
    round ends; if exactly one lacks it, that player pays ``nit_penalty_bb`` to
    every other player. If ``max_hands`` is reached first, the round ends with no
    nit payment (flagged as truncated).
    """

    version = NIT_PROTOCOL_VERSION

    def __init__(self, options: Mapping[str, Any]) -> None:
        self.penalty_bb = float(options.get("nit_penalty_bb", 5.0))
        self.max_hands = int(options.get("max_hands", 60))

    def play_round(self, blk: _Block, side: str, s: int) -> tuple[float, dict[str, float], dict[str, Any]]:
        spec, seed, k, bb = blk.spec, blk.spec.seed, blk.k, blk.bb
        r = spec.rng
        table = blk.table(side, s)
        buttons = [False] * k
        payoff_bb_total = 0.0
        est_total: dict[str, float] = {}
        truncated, nit_seat = False, None
        transfers = [0.0] * k
        h = 0
        need_log = any(e.needs_decision_log for e in blk.estimators)
        while True:
            deal = make_deal(blk.adapter, seed, r.salts["chance"], hand_index=h)
            # position p is occupied by table seat (p + h) mod k
            pos_agents = [table[(p + h) % k] for p in range(k)]
            cand_pos = (s - h) % k
            public = {
                "nit_buttons": tuple(buttons[(p + h) % k] for p in range(k)),
                "nit_hand_index": h,
                "nit_penalty_bb": self.penalty_bb,
            }

            def rng_for(acting_pos: int, ordinal: int, _h: int = h) -> DecisionRNG:
                t = (acting_pos + _h) % k
                if t == s:
                    return DecisionRNG("decision", seed, _label_rng(r, side, True), r.salts["candidate"], s, "hand", _h, ordinal)
                return DecisionRNG("decision", seed, _label_rng(r, side, False), r.salts["reference"], s, "hand", _h, t, ordinal)

            players = [a.agent_id for a in pos_agents] if blk.trace else None
            log: list[DecisionEvent] | None = [] if need_log else None
            outcome, text = play_hand(
                blk.adapter, deal, pos_agents, rng_for, blk.timer, players,
                blk.trace_extra(side, s, self.version, fhr3_hand_index=h), public_info=public, decision_log=log,
            )
            label = f"s{s}{side}h{h}"
            _check_conservation(outcome, label)
            if text is not None:
                blk.result.traces[f"{label}.{text[0]}"] = text[1]
            payoff = outcome.payoffs_chips[cand_pos] / bb
            payoff_bb_total += payoff
            est = blk.run_estimators(deal, outcome, cand_pos, pos_agents, log, ("hand", seed, s, h))
            for name, v in est.items():
                est_total[name] = est_total.get(name, 0.0) + v
            blk.result.hands.append(
                HandSummary(side, s, payoff, outcome.total_pot / bb, outcome.went_to_showdown,
                            outcome.had_all_in, outcome.decision_count, h, est,
                            outcome.allin_snapshot is not None)
            )
            blk.result.decision_count += outcome.decision_count
            table_payoffs = [outcome.payoffs_chips[(t - h) % k] for t in range(k)]
            buttons = nit_update_buttons(buttons, table_payoffs)
            h += 1
            over, nit_seat, transfers = nit_resolution(buttons, self.penalty_bb)
            if over:
                break
            if h >= self.max_hands:
                truncated, transfers = True, [0.0] * k
                break
        transfer = transfers[s]
        total = payoff_bb_total + transfer
        est_total = {n: v + transfer for n, v in est_total.items()}
        info = {"hands": h, "truncated": truncated, "nit_seat": nit_seat, "candidate_transfer_bb": transfer}
        return total, est_total, info

    def run(self, blk: _Block) -> None:
        rounds: dict[str, list[dict[str, Any]]] = {"A": [], "B": []}
        for s in range(blk.k):
            for side in SIDES:
                blk.current = f"s{s}{side}"
                payoff, est, info = self.play_round(blk, side, s)
                rounds[side].append(info)
                _record(blk.result, side, payoff, est)
        blk.result.variant_info["nit"] = {
            "round_hands": {sd: [x["hands"] for x in v] for sd, v in rounds.items()},
            "truncated": {sd: sum(x["truncated"] for x in v) for sd, v in rounds.items()},
            "candidate_was_nit": {sd: sum(x["nit_seat"] == s for s, x in enumerate(v)) for sd, v in rounds.items()},
            "candidate_transfer_bb": {sd: [x["candidate_transfer_bb"] for x in v] for sd, v in rounds.items()},
        }


def _record(result: MatchedBlockResult, side: str, payoff: float, est: dict[str, float]) -> None:
    (result.seat_payoff_a if side == "A" else result.seat_payoff_b).append(payoff)
    for name, v in est.items():
        result.seat_estimates.setdefault(name, {"A": [], "B": []})[side].append(v)


def make_protocol(adapter: GameAdapter) -> SingleHandProtocol | NitRoundProtocol:
    if adapter.config.variant == "nit_game":
        return NitRoundProtocol(adapter.config.options)
    return SingleHandProtocol()


def run_matched_block(
    spec: MatchedBlockSpec,
    adapter: GameAdapter,
    candidate_a: Agent,
    candidate_b: Agent,
    references: Sequence[Agent],
    trace: bool = False,
    estimators: Sequence[HandEstimator] = (),
) -> MatchedBlockResult:
    k = adapter.config.player_count
    if len(references) != k - 1:
        raise ValueError(f"need {k - 1} reference agents, got {len(references)}")
    protocol = make_protocol(adapter)
    t_start = time.perf_counter()
    result = MatchedBlockResult(block_id=spec.block_id, seed=spec.seed, player_count=k, valid=True,
                                protocol=protocol.version)
    blk = _Block(spec, adapter, {"A": candidate_a, "B": candidate_b}, references, trace,
                 tuple(estimators), _Timer(), result)
    try:
        protocol.run(blk)
    except Exception as exc:  # any failure invalidates the whole block
        current = blk.current
        if isinstance(exc, HandError):
            if exc.partial_trace is not None:
                result.traces[f"{current}-partial.{exc.trace_format}"] = exc.partial_trace
            exc = exc.original
        result.valid = False
        result.error_code = _error_code(exc)
        result.error_detail = f"{current}: {exc}"[:2000]
        result.seat_payoff_a, result.seat_payoff_b, result.seat_estimates = [], [], {}
    result.runtime_ms = (time.perf_counter() - t_start) * 1000.0
    result.agent_ms = blk.timer.total * 1000.0
    return result


class ChipConservationError(AssertionError):
    pass


class HandError(Exception):
    def __init__(self, original: BaseException, partial_trace: str | None, trace_format: str = "phh") -> None:
        super().__init__(str(original))
        self.original, self.partial_trace, self.trace_format = original, partial_trace, trace_format


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, IllegalActionError):
        return "ILLEGAL_ACTION"
    if isinstance(exc, ChipConservationError):
        return "CHIP_CONSERVATION"
    return f"EXCEPTION:{type(exc).__name__}"
