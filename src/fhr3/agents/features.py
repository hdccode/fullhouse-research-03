"""Cheap, transparent hand features for the heuristic policy family.

These are *agent features*, not rules: showdowns are always resolved by
PokerKit. ``made_category`` is cross-checked against PokerKit in the tests.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from functools import lru_cache
from itertools import combinations

from fhr3.games.base import RANKS, STANDARD_DECK

RANK_VALUE = {r: i for i, r in enumerate(RANKS)}  # 2 -> 0 ... A -> 12

# Category indices (same order as PokerKit's Label enum).
HIGH_CARD, ONE_PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)


# --------------------------------------------------------------------------- preflop
def chen_score(c1: str, c2: str) -> float:
    """Bill Chen's starting-hand formula (rounded up to integer)."""
    pts = {"A": 10.0, "K": 8.0, "Q": 7.0, "J": 6.0}
    r1, r2 = sorted((RANK_VALUE[c1[0]], RANK_VALUE[c2[0]]), reverse=True)
    hi = RANKS[r1]
    score = pts.get(hi, (r1 + 2) / 2.0)
    if r1 == r2:
        return float(max(5.0, score * 2))
    if c1[1] == c2[1]:
        score += 2
    gap = r1 - r2 - 1
    score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
    if gap <= 1 and r1 < RANK_VALUE["Q"]:
        score += 1
    return float(math.ceil(score))


def _preflop_key(c1: str, c2: str) -> tuple[float, int, int, int]:
    r1, r2 = sorted((RANK_VALUE[c1[0]], RANK_VALUE[c2[0]]), reverse=True)
    return (chen_score(c1, c2), r1, r2, int(c1[1] == c2[1]))


@lru_cache(maxsize=1)
def _preflop_table() -> dict[frozenset[str], float]:
    """Percentile (mid-rank CDF over all 1326 combos) of each starting hand."""
    combos = list(combinations(STANDARD_DECK, 2))
    keys = {frozenset(c): _preflop_key(*c) for c in combos}
    counts = Counter(keys.values())
    ordered = sorted(counts)
    below, cdf = 0, {}
    n = len(combos)
    for k in ordered:
        cdf[k] = (below + counts[k] / 2.0) / n
        below += counts[k]
    return {hand: cdf[k] for hand, k in keys.items()}


def preflop_percentile(hole: Sequence[str]) -> float:
    """0 = worst starting hand, ~1 = AA."""
    return _preflop_table()[frozenset(hole)]


# --------------------------------------------------------------------------- postflop
def _straight_high(rank_set: set[int]) -> int | None:
    ranks = set(rank_set)
    if 12 in ranks:
        ranks.add(-1)  # wheel ace
    for hi in range(12, 2, -1):  # hi=3 is the wheel (A-2-3-4-5)
        if all(r in ranks for r in range(hi - 4, hi + 1)):
            return hi
    return None


def made_category(cards: Sequence[str]) -> int:
    """Best category among ``cards`` (any count; straights/flushes need 5)."""
    ranks = [RANK_VALUE[c[0]] for c in cards]
    counts = sorted(Counter(ranks).values(), reverse=True)
    suit_counts = Counter(c[1] for c in cards)
    flush_suit = next((s for s, n in suit_counts.items() if n >= 5), None)
    if flush_suit is not None:
        fr = {RANK_VALUE[c[0]] for c in cards if c[1] == flush_suit}
        if _straight_high(fr) is not None:
            return STRAIGHT_FLUSH
    if counts[0] >= 4:
        return QUADS
    if counts[0] >= 3 and len(counts) > 1 and counts[1] >= 2:
        return FULL_HOUSE
    if flush_suit is not None:
        return FLUSH
    if _straight_high(set(ranks)) is not None:
        return STRAIGHT
    if counts[0] >= 3:
        return TRIPS
    if counts[0] == 2 and len(counts) > 1 and counts[1] == 2:
        return TWO_PAIR
    if counts[0] == 2:
        return ONE_PAIR
    return HIGH_CARD


def _straight_outs(rank_set: set[int]) -> set[int]:
    """Ranks that would complete a straight not already made."""
    if _straight_high(rank_set) is not None:
        return set()
    return {r for r in range(13) if r not in rank_set and _straight_high(rank_set | {r})}


def postflop_features(hole: Sequence[str], board: Sequence[str]) -> dict[str, float]:
    """Interpretable features used by ``HeuristicAgent``."""
    cards = list(hole) + list(board)
    cat = made_category(cards)
    board_cat = made_category(board)
    hole_r = sorted((RANK_VALUE[c[0]] for c in hole), reverse=True)
    board_r = sorted({RANK_VALUE[c[0]] for c in board}, reverse=True)
    board_counts = Counter(RANK_VALUE[c[0]] for c in board)

    # Draws (only meaningful before the river).
    flush_draw = 0.0
    if len(board) < 5:
        for s, n in Counter(c[1] for c in cards).items():
            if n == 4 and any(c[1] == s for c in hole) and cat < FLUSH:
                flush_draw = 1.0
    outs_all = _straight_outs({RANK_VALUE[c[0]] for c in cards})
    outs_board = _straight_outs(set(board_counts))
    straight_outs = len(outs_all - outs_board) if len(board) < 5 and cat < STRAIGHT else 0

    suit_max = max(Counter(c[1] for c in board).values())
    straighty = any(
        sum(1 for r in range(lo, lo + 5) if r in set(board_r) or (r == -1 and 12 in board_r))
        >= 3
        for lo in range(-1, 9)
    )
    return {
        "category": float(cat),
        "board_category": float(board_cat),
        "hole_improves": float(cat > board_cat),
        "hole_high": float(hole_r[0]),
        "hole_low": float(hole_r[-1]),
        "pocket_pair": float(hole_r[0] == hole_r[-1]),
        "board_high": float(board_r[0]),
        "board_ranks": tuple(board_r),  # type: ignore[dict-item]
        "board_paired": float(max(board_counts.values()) >= 2),
        "flush_draw": flush_draw,
        "straight_outs": float(straight_outs),
        "board_flushy": float(suit_max >= 3),
        "board_straighty": float(straighty),
    }
