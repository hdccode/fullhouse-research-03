"""Crazy Pineapple heuristic family.

Same decision skeleton and styles as the NLHE family, adapted to 3 hole cards:

* preflop strength = percentile (empirical CDF over a fixed deterministic sample
  of 3-card hands) of  best-pair percentile + 0.15 x second-best-pair percentile;
* flop betting with 3 cards: strength of the best 2-card subset (the one the
  agent would keep);
* discard: keep the pair maximising  s + (1 - s) * draw_equity  under the NLHE
  postflop features; ties broken by card order (deterministic);
* after the discard: plain NLHE postflop logic on the kept 2 cards.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import replace
from functools import lru_cache
from itertools import combinations

from fhr3.agents.features import preflop_percentile
from fhr3.agents.heuristic import HeuristicAgent
from fhr3.games.base import STANDARD_DECK, Action, LegalActions, LegalDiscards, Observation
from fhr3.rng import KeyedStream

CP_IMPL_VERSION = "cp-heuristic-1.0.0"


def three_card_score(hole: Sequence[str]) -> float:
    pcts = sorted((preflop_percentile(p) for p in combinations(hole, 2)), reverse=True)
    return pcts[0] + 0.15 * pcts[1]


@lru_cache(maxsize=1)
def _cdf() -> list[float]:
    s = KeyedStream("cp-preflop-cdf", 1)
    out = []
    for _ in range(20000):
        idx: set[int] = set()
        while len(idx) < 3:
            idx.add(s.randbelow(52))
        out.append(three_card_score([STANDARD_DECK[i] for i in sorted(idx)]))
    return sorted(out)


def three_card_percentile(hole: Sequence[str]) -> float:
    cdf, x = _cdf(), three_card_score(hole)
    lo, hi = bisect_left(cdf, x), bisect_left(cdf, x + 1e-12)
    return (lo + (hi - lo) / 2.0) / len(cdf)


class CrazyPineappleAgent(HeuristicAgent):
    IMPL = CP_IMPL_VERSION

    def preflop_strength(self, obs: Observation) -> float:
        if len(obs.hole_cards) == 3:
            return three_card_percentile(obs.hole_cards)
        return super().preflop_strength(obs)

    def _pair_value(self, obs: Observation, pair: tuple[str, ...]) -> float:
        s, draw = super().strength(replace(obs, hole_cards=pair))
        return s + (1.0 - s) * draw

    def best_pair(self, obs: Observation) -> tuple[str, ...]:
        pairs = list(combinations(obs.hole_cards, 2))
        return max(pairs, key=lambda p: (self._pair_value(obs, p), p))

    def strength(self, obs: Observation) -> tuple[float, float]:
        if len(obs.hole_cards) == 3:
            return super().strength(replace(obs, hole_cards=self.best_pair(obs)))
        return super().strength(obs)

    def action_distribution(
        self, observation: Observation, legal_actions: LegalActions | LegalDiscards
    ) -> Sequence[tuple[Action, float]]:
        if isinstance(legal_actions, LegalDiscards):
            keep = self.best_pair(observation)
            (discard,) = [c for c in observation.hole_cards if c not in keep]
            return [(Action.discard(discard), 1.0)]
        return super().action_distribution(observation, legal_actions)
