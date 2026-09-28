"""Transparent Omaha (4-card) features for the PLO heuristic family.

All postflop features respect the Omaha rule (exactly two hole cards and three
board cards). Showdowns are resolved by PokerKit; these are agent features only.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from collections.abc import Sequence
from functools import lru_cache
from itertools import combinations

from fhr3.agents.features import RANK_VALUE
from fhr3.games.base import STANDARD_DECK
from fhr3.games.evaluator import rank_omaha
from fhr3.rng import KeyedStream

PAIR_POINTS = {12: 18.0, 11: 16.0, 10: 14.0, 9: 12.0, 8: 10.0}


def omaha_preflop_score(hole: Sequence[str]) -> float:
    """Hutchison-style point score: pairs, suitedness, connectedness, high cards."""
    ranks = sorted((RANK_VALUE[c[0]] for c in hole), reverse=True)
    rc = Counter(ranks)
    score = 0.0
    for r, n in rc.items():
        if n == 2:
            score += PAIR_POINTS.get(r, 6.0 + r / 3.0)
        elif n >= 3:
            score -= 4.0  # trips are poor in Omaha
    suits = Counter(c[1] for c in hole)
    suited_groups = 0
    for s, n in suits.items():
        if n >= 2:
            top = max(RANK_VALUE[c[0]] for c in hole if c[1] == s)
            score += 2.0 + top / 2.0 + (2.0 if top == 12 else 0.0)
            suited_groups += 1
            if n >= 3:
                score -= 2.0
    if suited_groups == 2:
        score += 2.0  # double-suited
    distinct = sorted(set(ranks), reverse=True)
    if len(distinct) >= 2:
        best_run = 1
        for size in (4, 3, 2):
            for combo in combinations(distinct, size):
                if combo[0] - combo[-1] <= 4:
                    best_run = max(best_run, size)
                    break
            if best_run > 1:
                break
        score += {4: 12.0, 3: 7.0, 2: 2.0}.get(best_run, 0.0)
        if ranks[0] - ranks[-1] >= 9 and best_run < 3:
            score -= 3.0  # dangler
    score += sum(ranks) / 6.0
    return score


@lru_cache(maxsize=1)
def _score_cdf() -> list[float]:
    """Empirical score distribution over a fixed deterministic sample of hands."""
    s = KeyedStream("omaha-preflop-cdf", 1)
    scores = []
    for _ in range(20000):
        idx = set()
        while len(idx) < 4:
            idx.add(s.randbelow(52))
        scores.append(omaha_preflop_score([STANDARD_DECK[i] for i in idx]))
    return sorted(scores)


def omaha_preflop_percentile(hole: Sequence[str]) -> float:
    cdf = _score_cdf()
    x = omaha_preflop_score(hole)
    lo = bisect_left(cdf, x)
    hi = bisect_left(cdf, x + 1e-12)
    return (lo + (hi - lo) / 2.0) / len(cdf)


def _straight_outs(hole: Sequence[str], board: Sequence[str]) -> int:
    """Ranks r such that r on the board completes an Omaha straight (2 hole + 3 board)."""
    hole_r = sorted({RANK_VALUE[c[0]] for c in hole})
    board_r = sorted({RANK_VALUE[c[0]] for c in board})
    outs: set[int] = set()
    for a, b in combinations(hole_r, 2):
        for c, d in combinations(board_r, 2):
            four = {a, b, c, d}
            if len(four) < 4:
                continue
            for lo in range(-1, 9):
                window = {12 if r == -1 else r for r in range(lo, lo + 5)}
                if four <= window:
                    missing = window - four
                    if len(missing) == 1:
                        outs |= missing
    return len(outs)


def omaha_postflop_features(hole: Sequence[str], board: Sequence[str]) -> dict[str, float]:
    value = rank_omaha(hole, board) if len(board) >= 3 else 0
    cat = value >> 20
    top_rank = (value >> 16) & 0xF
    board_r = sorted((RANK_VALUE[c[0]] for c in board), reverse=True)
    board_suits = Counter(c[1] for c in board)
    hole_suits = Counter(c[1] for c in hole)
    flush_draw = nut_flush_draw = 0.0
    nut_flush = 0.0
    if len(board) < 5:
        for s, n in board_suits.items():
            if n == 2 and hole_suits.get(s, 0) >= 2:
                flush_draw = 1.0
                if any(c[0] == "A" and c[1] == s for c in hole):
                    nut_flush_draw = 1.0
    if cat == 5:
        fs = max(board_suits, key=board_suits.get)
        nut_flush = float(any(c[0] == "A" and c[1] == fs for c in hole))
    return {
        "category": float(cat),
        "top_rank": float(top_rank),
        "board_high": float(board_r[0]) if board_r else 0.0,
        "board_paired": float(len(set(board_r)) < len(board_r)),
        "board_flushy": float(max(board_suits.values(), default=0) >= 3),
        "flush_draw": flush_draw,
        "nut_flush_draw": nut_flush_draw,
        "nut_flush": nut_flush,
        "straight_outs": float(_straight_outs(hole, board)) if len(board) < 5 and cat < 4 else 0.0,
    }
