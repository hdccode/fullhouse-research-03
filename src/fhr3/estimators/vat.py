"""MIVAT / AIVAT estimators, built on PVAT (uoftcprg/pvat, pinned 0.0.0.dev2).

Each finished hand becomes a PVAT history over an FHR3 event sequence:

  chance events   flop (3 cards), turn, river, drawn uniformly from the cards not
                  yet dealt (all hole cards, earlier board and burn cards excluded)
  action events   every agent decision; the acting agent's policy is *known* when
                  it is a ``DistributionAgent`` (all FHR3 heuristic/AoF agents)

For any fixed value function v, each correction term

    E_{x ~ p(. | h)} [ v(h x) ] - v(h x_realized)

has zero conditional mean, so the estimate (realized payoff + corrections) has
the same expectation as the realized payoff: the estimand is unchanged (tested
statistically and on exact fixtures in tests/test_vat.py).

* MIVAT: chance corrections only (PVAT ``MIVAT``).
* AIVAT: chance + known-policy action corrections (PVAT ``AIVAT`` with full
  information, i.e. mapped histories = {h}; in simulation all cards are known).

Flop corrections average over ``flop_samples`` i.i.d. uniform flops from a keyed
estimator stream (an unbiased estimate of the exact expectation); turn and river
are enumerated exactly. Streams are keyed by the side-independent hand key, so
identical A/B hands receive identical estimates.

Value function: linear in the candidate-centric features of ``FEATURES`` (BB
units). Parameters are either the documented prior (``PRIOR_THETA``) or a JSON
file produced by ``fhr3 vat-fit`` on a *separate* root seed, pinned by sha256 in
the experiment config and refused if it was trained on the evaluation seed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from pvat import AIVAT, MIVAT, LinearValueFunction

from fhr3.agents.base import DistributionAgent
from fhr3.agents.features import preflop_percentile
from fhr3.eval.matched import HandContext
from fhr3.games.base import STANDARD_DECK, Action, ActionKind
from fhr3.games.evaluator import EVALUATORS
from fhr3.rng import KeyedStream

FEATURE_VERSION = "vat-features-1"
FEATURES = (
    "neg_contributed",
    "lead_pot_preflop", "lead_pot_flop", "lead_pot_turn", "lead_pot_river",
    "equal_share_pot",
    "alone_pot",
)
PRIOR_THETA = np.array([1.0, 0.35, 0.55, 0.75, 1.0, 0.0, 1.0])
CHANCE = "chance"
UNKNOWN = "unknown-policy"


# ------------------------------------------------------------------ betting state
@dataclass(frozen=True)
class TState:
    street: int
    board: tuple[str, ...]
    hole: tuple[tuple[str, ...], ...]
    active: tuple[bool, ...]
    contrib: tuple[int, ...]  # chips put in this hand (antes + blinds + bets)
    bets: tuple[int, ...]  # this street
    starting: tuple[int, ...]

    @property
    def pot(self) -> int:
        return sum(self.contrib)

    def stack(self, i: int) -> int:
        return self.starting[i] - self.contrib[i]


def initial_state(ctx: HandContext) -> TState:
    cfg = ctx.adapter.config
    k = cfg.player_count
    starting = ctx.outcome.starting_stacks
    if cfg.variant == "bomb_pot":
        ante = ctx.adapter.ante_chips  # type: ignore[attr-defined]
        contrib, bets, street = (ante,) * k, (0,) * k, 1
    else:
        blinds = [cfg.sb_chips, cfg.bb_chips] + [0] * (k - 2)
        contrib = tuple(cfg.ante_chips + b for b in blinds)
        bets, street = tuple(blinds), 0
    return TState(street, (), tuple(ctx.deal.hole), (True,) * k, contrib, bets, starting)


def apply_action(s: TState, seat: int, action: Action) -> TState:
    if action.kind is ActionKind.FOLD:
        active = list(s.active)
        active[seat] = False
        return replace(s, active=tuple(active))
    if action.kind is ActionKind.DISCARD:
        # discards happen after the flop betting round, whose bets are collected
        hole = list(s.hole)
        hole[seat] = tuple(c for c in s.hole[seat] if c not in action.cards)
        return replace(s, hole=tuple(hole), bets=(0,) * len(s.bets))
    if action.kind is ActionKind.CHECK_CALL:
        add = min(max(s.bets) - s.bets[seat], s.stack(seat))
    else:
        assert action.amount is not None
        add = action.amount - s.bets[seat]
    bets, contrib = list(s.bets), list(s.contrib)
    bets[seat] += add
    contrib[seat] += add
    return replace(s, bets=tuple(bets), contrib=tuple(contrib))


def apply_chance(s: TState, street: int, cards: tuple[str, ...]) -> TState:
    return replace(s, street=street, board=s.board + cards, bets=(0,) * len(s.bets))


# ------------------------------------------------------------------ features
def _hand_value(showdown: str, hole: tuple[str, ...], board: tuple[str, ...]) -> float:
    """Current strength: evaluator value once a board exists, else preflop percentile."""
    if len(board) >= 3:
        return float(EVALUATORS[showdown](hole, board))
    if len(hole) == 2:
        return preflop_percentile(hole)
    if len(hole) == 4:
        from fhr3.agents.omaha_features import omaha_preflop_percentile

        return omaha_preflop_percentile(hole)
    from fhr3.agents.pineapple import three_card_percentile

    return three_card_percentile(hole)


def features(s: TState, cand: int, showdown: str, bb: int) -> np.ndarray:
    live = [i for i, a in enumerate(s.active) if a]
    x = np.zeros(len(FEATURES))
    x[0] = -s.contrib[cand] / bb
    if not s.active[cand]:
        return x
    pot = s.pot / bb
    vals = {i: _hand_value(showdown, s.hole[i], s.board) for i in live}
    best = max(vals.values())
    winners = [i for i in live if vals[i] == best]
    lead = 1.0 / len(winners) if cand in winners else 0.0
    x[1 + min(s.street, 3)] = pot * lead
    x[5] = pot / len(live)
    x[6] = pot if len(live) == 1 else 0.0
    return x


# ------------------------------------------------------------------ hand -> PVAT histories
@dataclass
class Event:
    kind: str  # "chance" | "action"
    seat: int | None  # acting seat (None for chance)
    player: Any  # PVAT player id: CHANCE, the seat, or UNKNOWN (policy not known)
    street: int
    value: Any  # realized cards tuple / Action
    options: list[tuple[Any, float]]  # (outcome, probability); empty if uncorrectable


class HandTrace:
    def __init__(self, ctx: HandContext, flop_samples: int, salt: int) -> None:
        self.ctx = ctx
        self.cand = ctx.candidate_position
        adapter = ctx.adapter
        self.showdown, self.bb = adapter.showdown, adapter.config.bb_chips
        board, runout = ctx.outcome.board, ctx.deal.runout
        burns = (runout[0], runout[4], runout[6])
        dealt_hole = {c for h in ctx.deal.hole for c in h}
        by_street: dict[int, list[Any]] = {0: [], 1: [], 2: [], 3: []}
        for d in ctx.decisions:
            by_street[d.observation.street].append(d)
        stream = KeyedStream("vat", salt, *ctx.key)
        self.events: list[Event] = []
        for st in range(4):
            if st >= 1 and len(board) >= {1: 3, 2: 4, 3: 5}[st]:
                lo, hi = {1: (0, 3), 2: (3, 4), 3: (4, 5)}[st]
                dead = dealt_hole | set(board[:lo]) | set(burns[:st])
                pool = [c for c in STANDARD_DECK if c not in dead]
                n = hi - lo
                if n == 1:
                    outs = [(c,) for c in pool]
                else:
                    outs = []
                    for _ in range(flop_samples):
                        picks = list(pool)
                        for j in range(n):
                            i = j + stream.randbelow(len(picks) - j)
                            picks[j], picks[i] = picks[i], picks[j]
                        outs.append(tuple(sorted(picks[:n])))
                w = 1.0 / len(outs)
                self.events.append(Event("chance", None, CHANCE, st, tuple(sorted(board[lo:hi])), [(o, w) for o in outs]))
            for d in by_street[st]:
                if isinstance(d.agent, DistributionAgent):
                    dist = list(d.agent.action_distribution(d.observation, d.legal))
                    total = sum(p for _, p in dist)
                    self.events.append(Event("action", d.seat, d.seat, st, d.action, [(a, p / total) for a, p in dist if p > 0]))
                else:
                    self.events.append(Event("action", d.seat, UNKNOWN, st, d.action, []))
        # states before each event (validated against the engine's observations)
        self.states: list[TState] = []
        s = initial_state(ctx)
        obs_iter = iter(ctx.decisions)
        for ev in self.events:
            if ev.kind == "action" and ev.value.kind is ActionKind.DISCARD and any(s.bets):
                s = replace(s, bets=(0,) * len(s.bets))  # flop round over: bets collected
            self.states.append(s)
            if ev.kind == "action":
                obs = next(obs_iter).observation
                if s.pot != obs.pot or s.bets != obs.bets or s.active != obs.active:
                    raise RuntimeError(f"VAT state tracker diverged from engine at {ev}: {s} vs pot {obs.pot} bets {obs.bets}")
            s = self.advance(s, ev, ev.value)
        self.final = s
        self.realized_bb = ctx.outcome.payoffs_chips[self.cand] / self.bb

    def advance(self, s: TState, ev: Event, value: Any) -> TState:
        if ev.kind == "chance":
            return apply_chance(s, ev.street, value)
        assert ev.seat is not None
        return apply_action(s, ev.seat, value)


class H:
    """PVAT history: events[:i] followed by ``alt`` (None = prefix / terminal)."""

    __slots__ = ("t", "i", "alt")

    def __init__(self, t: HandTrace, i: int, alt: Any = None) -> None:
        self.t, self.i, self.alt = t, i, alt

    def state(self) -> TState:
        if self.alt is None:
            return self.t.states[self.i] if self.i < len(self.t.events) else self.t.final
        return self.t.advance(self.t.states[self.i], self.t.events[self.i], self.alt)


def _feature_extractor(h: H) -> np.ndarray:
    t = h.t
    return features(h.state(), t.cand, t.showdown, t.bb)


def _prob(h: H) -> float:
    """Probability of the last event of ``h`` given its prefix.

    Chance outcomes are uniform over the undealt cards, so a constant weight is
    exact (PVAT normalises weights). Actions use the known policy distribution;
    an action outside the support means the logged policy does not match.
    """
    ev = h.t.events[h.i]
    if ev.kind == "chance":
        return 1.0
    for o, p in ev.options:
        if o == h.alt:
            return p
    raise RuntimeError(f"action {h.alt} has zero probability under the logged policy at {ev}")


def _pvat_functions(corrected_actions: bool) -> dict[str, Any]:
    def prefixes(term: H) -> Any:
        for i, ev in enumerate(term.t.events):
            yield H(term.t, i), ev.value

    def player(h: H) -> Any:
        ev = h.t.events[h.i]
        return ev.player if ev.options else UNKNOWN

    return {
        "terminal_value_function": lambda term: term.t.realized_bb,
        "actions_function": lambda h: [o for o, _ in h.t.events[h.i].options],
        "probability_function": _prob,
        "made_function": lambda h, a: H(h.t, h.i, a),
        "prefixes_function": prefixes,
        "player_function": player,
    }


class _AllSeats:
    """Container of corrected players for AIVAT: chance + every known-policy seat."""

    def __contains__(self, p: Any) -> bool:
        return p != UNKNOWN


def make_pvat(kind: str) -> Any:
    f = _pvat_functions(kind == "aivat")
    if kind == "mivat":
        return MIVAT(chance=CHANCE, **f)
    return AIVAT(
        mapped_terminal_histories_function=lambda term: [term],
        terminal_probability_function=lambda term: 1.0,
        corrected_players=_AllSeats(),
        mapped_histories_function=lambda h: [h],
        **f,
    )


# ------------------------------------------------------------------ estimator
def load_value_function(path: str | Path, sha256: str | None) -> tuple[np.ndarray, dict[str, Any]]:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if sha256 is None or digest != sha256:
        raise ValueError(f"value function {path}: sha256 {digest} does not match the pinned value {sha256!r}")
    meta = json.loads(raw)
    if meta.get("feature_version") != FEATURE_VERSION or meta.get("features") != list(FEATURES):
        raise ValueError(f"value function {path} was fitted for different features")
    return np.asarray(meta["theta"], dtype=float), meta


class VATEstimator:
    needs_decision_log = True

    def __init__(self, kind: str, theta: np.ndarray, flop_samples: int = 16, salt: int = 0) -> None:
        if kind not in ("aivat", "mivat"):
            raise ValueError(kind)
        self.name, self.theta = kind, np.asarray(theta, dtype=float)
        self.flop_samples, self.salt = int(flop_samples), int(salt)
        self.pvat = make_pvat(kind)

    def terminal(self, ctx: HandContext) -> H:
        t = HandTrace(ctx, self.flop_samples, self.salt)
        return H(t, len(t.events))

    def estimate(self, ctx: HandContext) -> float:
        term = self.terminal(ctx)
        est = float(self.pvat.get_base_term(term)) + float(self.theta @ self.correction_features(term))
        return est * term.t.bb

    def correction_features(self, term: H) -> np.ndarray:
        """PVAT's correction sum evaluated in feature space.

        Equivalent to PVAT's own LinearValueFunction path (theta . corrections);
        computed explicitly because PVAT returns the integer 0 (not a vector)
        when a history has no corrected prefixes, which its linear path rejects.
        """
        c = self.pvat.get_correction_term_sum(_feature_extractor, term)
        return np.zeros(len(FEATURES)) if np.ndim(c) == 0 else np.asarray(c, dtype=float)


def build_vat_estimator(name: str, adapter: Any, opts: dict[str, Any], root_seed: int | None = None) -> VATEstimator:
    opts = dict(opts)
    vf = opts.pop("value_function", "prior")
    sha = opts.pop("value_function_sha256", None)
    if vf == "prior":
        theta = PRIOR_THETA
    else:
        theta, meta = load_value_function(vf, sha)
        if root_seed is not None and meta.get("training_root_seed") == root_seed:
            raise ValueError("value function was fitted on the evaluation root seed; refit on separate data")
    unknown = set(opts) - {"flop_samples", "salt"}
    if unknown:
        raise ValueError(f"{name}: unknown options {sorted(unknown)}")
    return VATEstimator(name, theta, **opts)


def fit_theta(estimator: VATEstimator, terminals: Sequence[H]) -> np.ndarray:
    """PVAT's variance-minimising linear fit on *training* histories."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)  # numpy rcond notice inside PVAT
        lvf = LinearValueFunction.learn(
            base_term_function=lambda term: term.t.realized_bb,
            correction_term_sum_function=lambda fe, term: estimator.correction_features(term),
            feature_extractor=_feature_extractor,
            terminal_histories=list(terminals),
        )
    return np.asarray(lvf.parameters, dtype=float)


__all__ = ["FEATURES", "FEATURE_VERSION", "PRIOR_THETA", "VATEstimator", "build_vat_estimator", "fit_theta"]
