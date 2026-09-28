"""All-in EV estimator: integrate out post-decision chance only.

When a hand reaches a point where no strategic decision remains but board cards
are still to come (``AllInSnapshot``: at most one live player still has chips,
and — in Crazy Pineapple — all discards are made), the candidate's realized
payoff is replaced by its expectation over the remaining runout:

    X_allin = E[ winnings_c(runout) ] - contributed_c

The expectation is over board completions drawn uniformly from the cards not
yet dealt (hole cards of *all* players incl. folded/discarded, board and burned
cards are excluded). This is the conditional expectation of the realized payoff
given everything dealt so far, so E[X_allin] = E[X] (tower property): the
estimand is unchanged. Decisions themselves are never re-evaluated.

Exact enumeration when the number of runouts is at most ``exact_max_combos``,
otherwise ``mc_samples`` Monte Carlo runouts from a dedicated keyed stream
("allin-ev", salt, <hand key>). The hand key does not include the side, so
identical A/B hands receive identical estimates.

Split pots replicate PokerKit exactly: ``divmod(amount, n_winners)`` with the
remainder going to the first winner in seat order.
"""

from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Any

from fhr3.eval.matched import HandContext
from fhr3.games.base import STANDARD_DECK, AllInSnapshot
from fhr3.games.evaluator import EVALUATORS
from fhr3.rng import KeyedStream

VERSION = "allin-ev-1"


def runout_payoff(snap: AllInSnapshot, board: tuple[str, ...], seat: int, evaluate: Any) -> int:
    values: dict[int, int] = {}
    won = 0
    for amount, eligible in snap.pots:
        contenders = [i for i in eligible if snap.live[i]]
        if not contenders:
            continue
        for i in contenders:
            if i not in values:
                values[i] = evaluate(snap.hole[i], board)
        best = max(values[i] for i in contenders)
        winners = [i for i in contenders if values[i] == best]
        if seat in winners:
            q, r = divmod(amount, len(winners))
            won += q + (r if seat == winners[0] else 0)
    return won - snap.contributed[seat]


def expected_payoff(
    snap: AllInSnapshot,
    seat: int,
    showdown: str,
    exact_max_combos: int,
    mc_samples: int,
    stream: KeyedStream | None,
) -> tuple[float, str]:
    """(expected chips, method) for ``seat`` from the snapshot."""
    evaluate = EVALUATORS[showdown]
    need = 5 - len(snap.board)
    pool = [c for c in STANDARD_DECK if c not in snap.dead]
    if comb(len(pool), need) <= exact_max_combos:
        total = n = 0
        for extra in combinations(pool, need):
            total += runout_payoff(snap, snap.board + extra, seat, evaluate)
            n += 1
        return total / n, "exact"
    if stream is None:
        raise ValueError("Monte Carlo all-in EV requires a stream")
    total = 0
    for _ in range(mc_samples):
        picks = list(pool)
        extra = []
        for j in range(need):  # partial Fisher-Yates: sample without replacement
            i = j + stream.randbelow(len(picks) - j)
            picks[j], picks[i] = picks[i], picks[j]
            extra.append(picks[j])
        total += runout_payoff(snap, snap.board + tuple(extra), seat, evaluate)
    return total / mc_samples, "mc"


class AllInEVEstimator:
    name = "allin_ev"
    needs_decision_log = False

    def __init__(self, showdown: str, mc_samples: int = 200, exact_max_combos: int = 1200, salt: int = 0) -> None:
        if showdown not in EVALUATORS:
            raise ValueError(f"no evaluator for showdown type {showdown!r}")
        if mc_samples < 1 or exact_max_combos < 1:
            raise ValueError("mc_samples and exact_max_combos must be positive")
        self.showdown, self.mc_samples, self.exact_max_combos, self.salt = (
            showdown, int(mc_samples), int(exact_max_combos), int(salt),
        )

    def estimate(self, ctx: HandContext) -> float:
        snap = ctx.outcome.allin_snapshot
        seat = ctx.candidate_position
        realized = float(ctx.outcome.payoffs_chips[seat])
        if snap is None or not snap.live[seat]:
            return realized
        stream = KeyedStream("allin-ev", VERSION, self.salt, *ctx.key)
        ev, _ = expected_payoff(snap, seat, self.showdown, self.exact_max_combos, self.mc_samples, stream)
        return ev
