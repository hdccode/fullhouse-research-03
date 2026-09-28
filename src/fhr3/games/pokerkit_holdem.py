"""Backward-compatible names for the NLHE adapter (see pokerkit_board.py)."""

from fhr3.games.pokerkit_board import RUNOUT_CARDS, PokerKitBoardAdapter, PokerKitBoardHand

HOLE_CARDS = 2
PokerKitHoldemAdapter = PokerKitBoardAdapter
PokerKitHoldemHand = PokerKitBoardHand

__all__ = ["HOLE_CARDS", "RUNOUT_CARDS", "PokerKitHoldemAdapter", "PokerKitHoldemHand"]
