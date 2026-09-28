"""Nit Game: NLHE hands inside a multi-hand nit round.

Persistent nit-button state lives in the block protocol
(``fhr3.eval.matched.NitRoundProtocol``), not in PokerKit state; the adapter is
plain NLHE plus option validation. Agents see the buttons through
``Observation.extra["nit_buttons"]`` (indexed by seat/position of that hand).
"""

from __future__ import annotations

from typing import Any

from fhr3.games.pokerkit_board import PokerKitBoardAdapter

NIT_OPTIONS = {"nit_penalty_bb", "max_hands"}


class NitGameAdapter(PokerKitBoardAdapter):
    variant = "nit_game"

    def _validate_options(self, options: dict[str, Any]) -> None:
        unknown = set(options) - NIT_OPTIONS
        if unknown:
            raise ValueError(f"nit_game options: unknown {sorted(unknown)}")
        if float(options.get("nit_penalty_bb", 5.0)) < 0:
            raise ValueError("nit_penalty_bb must be >= 0")
        if int(options.get("max_hands", 60)) < 1:
            raise ValueError("max_hands must be >= 1")
