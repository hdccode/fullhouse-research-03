"""Fast evaluator: hand ordering must agree with PokerKit (independent oracle)."""

import pokerkit as pk
from hypothesis import given, settings
from hypothesis import strategies as st

from fhr3.games.base import STANDARD_DECK
from fhr3.games.evaluator import rank_holdem, rank_omaha
from fhr3.rng import KeyedStream


def _sign(x):
    return (x > 0) - (x < 0)


@settings(max_examples=400, deadline=None)
@given(seed=st.integers(0, 2**32), board_n=st.sampled_from([3, 4, 5]))
def test_holdem_ordering_matches_pokerkit(seed, board_n):
    cards = KeyedStream("ev-hold", seed).shuffle(STANDARD_DECK)
    board, h1, h2 = cards[:board_n], cards[5:7], cards[7:9]
    pk1 = pk.StandardHighHand.from_game("".join(h1), "".join(board))
    pk2 = pk.StandardHighHand.from_game("".join(h2), "".join(board))
    expected = 0 if pk1 == pk2 else (1 if pk1 > pk2 else -1)
    assert _sign(rank_holdem(h1, board) - rank_holdem(h2, board)) == expected


@settings(max_examples=150, deadline=None)
@given(seed=st.integers(0, 2**32))
def test_omaha_ordering_matches_pokerkit(seed):
    cards = KeyedStream("ev-omaha", seed).shuffle(STANDARD_DECK)
    board, h1, h2 = cards[:5], cards[5:9], cards[9:13]
    pk1 = pk.OmahaHoldemHand.from_game("".join(h1), "".join(board))
    pk2 = pk.OmahaHoldemHand.from_game("".join(h2), "".join(board))
    expected = 0 if pk1 == pk2 else (1 if pk1 > pk2 else -1)
    assert _sign(rank_omaha(h1, board) - rank_omaha(h2, board)) == expected


def test_omaha_exact_two_plus_three_fixtures():
    board = ("Ah", "Kh", "Qh", "Jh", "2c")
    # one heart in hand: flush in Hold'em, NOT in Omaha (needs two hearts from hand)
    one_heart = ("Th", "3c", "4d", "5s")
    two_hearts = ("Th", "9h", "4d", "5s")
    assert rank_omaha(two_hearts, board) > rank_omaha(one_heart, board)
    assert rank_holdem(("Th", "3c"), board) >> 20 == 8  # Hold'em: royal/straight flush with one heart
    assert rank_omaha(one_heart, board) >> 20 == 0  # Omaha: 2 hole + 3 board -> high card only
    # board full house plays in Hold'em; Omaha must use two hole cards -> only trips
    fh_board = ("As", "Ah", "Ad", "Ks", "Kh")
    hole = ("2c", "3d", "4h", "5s")
    assert rank_holdem(hole[:2], fh_board) >> 20 == 6  # full house (board plays)
    assert rank_omaha(hole, fh_board) >> 20 == 3  # trips aces + two hole kickers
    # straight needs exactly two hole cards: board 5-6-7 + hole 8-9 makes it
    assert rank_omaha(("8c", "9d", "Ks", "Kd"), ("5h", "6s", "7c", "Qd", "2h")) > rank_omaha(
        ("8c", "2d", "Ks", "Kd"), ("5h", "6s", "7c", "Qd", "2h")
    )


def test_wheel_and_steel_wheel():
    assert rank_holdem(("Ac", "2d"), ("3h", "4s", "5c")) > rank_holdem(("Kc", "Kd"), ("3h", "4s", "5c"))
    assert rank_holdem(("Ah", "2h"), ("3h", "4h", "5h")) > rank_holdem(("6d", "6c"), ("6h", "6s", "5h"))
