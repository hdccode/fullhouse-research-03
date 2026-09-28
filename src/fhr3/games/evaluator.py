"""Fast pure-Python showdown evaluator for estimators (not used for rules).

Showdowns in play are resolved by PokerKit. This evaluator exists because the
all-in EV and AIVAT estimators evaluate thousands of hypothetical runouts, and
PokerKit's evaluator (~140 us/hand) would dominate runtime. Its *ordering* of
hands is cross-checked against PokerKit in ``tests/test_evaluator.py``.

Values are integers; larger is better; equal values tie.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
_R = {r: i for i, r in enumerate(RANKS)}
_S = {s: i for i, s in enumerate(SUITS)}
CARD_RANK = {r + s: _R[r] for r in RANKS for s in SUITS}
CARD_SUIT = {r + s: _S[s] for r in RANKS for s in SUITS}


def _pack(cat: int, ranks: Sequence[int]) -> int:
    v = cat
    for i in range(5):
        v = (v << 4) | (ranks[i] if i < len(ranks) else 0)
    return v


def _straight_high(mask: int) -> int:
    """mask bit (r+1) set for rank r; bit 0 set for a low ace. Returns high rank or -1."""
    for hi in range(12, 2, -1):
        if (mask >> (hi - 3)) & 0b11111 == 0b11111:
            return hi
    return -1


def rank_cards(cards: Sequence[str]) -> int:
    """Best 5-card high-hand value using any 5 of ``cards`` (5..7 cards)."""
    counts = [0] * 13
    suit_ranks: list[list[int]] = [[], [], [], []]
    mask = 0
    for c in cards:
        r = CARD_RANK[c]
        counts[r] += 1
        suit_ranks[CARD_SUIT[c]].append(r)
        mask |= 1 << (r + 1)
    if mask & (1 << 13):
        mask |= 1
    flush = next((sr for sr in suit_ranks if len(sr) >= 5), None)
    if flush is not None:
        fmask = 0
        for r in flush:
            fmask |= 1 << (r + 1)
        if fmask & (1 << 13):
            fmask |= 1
        sf = _straight_high(fmask)
        if sf >= 0:
            return _pack(8, [sf])
    quads = trips = -1
    trips2 = -1
    pairs: list[int] = []
    for r in range(12, -1, -1):
        n = counts[r]
        if n == 4:
            quads = r
        elif n == 3:
            if trips < 0:
                trips = r
            elif trips2 < 0:
                trips2 = r
        elif n == 2:
            pairs.append(r)
    if quads >= 0:
        kicker = max(r for r in range(13) if counts[r] and r != quads)
        return _pack(7, [quads, kicker])
    if trips >= 0 and (trips2 >= 0 or pairs):
        pair = max(trips2, pairs[0] if pairs else -1)
        return _pack(6, [trips, pair])
    if flush is not None:
        return _pack(5, sorted(flush, reverse=True)[:5])
    st = _straight_high(mask)
    if st >= 0:
        return _pack(4, [st])
    singles = [r for r in range(12, -1, -1) if counts[r] == 1]
    if trips >= 0:
        return _pack(3, [trips, *singles[:2]])
    if len(pairs) >= 2:
        kick = max([*singles, *pairs[2:]], default=0)
        return _pack(2, [pairs[0], pairs[1], kick])
    if pairs:
        return _pack(1, [pairs[0], *singles[:3]])
    return _pack(0, singles[:5])


def rank_holdem(hole: Sequence[str], board: Sequence[str]) -> int:
    return rank_cards(list(hole) + list(board))


def rank_omaha(hole: Sequence[str], board: Sequence[str]) -> int:
    """Exactly two hole cards and exactly three board cards."""
    best = -1
    boards = list(combinations(board, 3))
    for h in combinations(hole, 2):
        for b in boards:
            v = rank_cards(h + b)
            if v > best:
                best = v
    return best


EVALUATORS = {"holdem": rank_holdem, "omaha": rank_omaha}
