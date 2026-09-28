from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any

import pytest

from fhr3.configs.experiment import ExperimentConfig, config_from_dict
from fhr3.games.base import STANDARD_DECK, Deal, GameConfig
from fhr3.games.pokerkit_holdem import PokerKitHoldemAdapter

TINY: dict[str, Any] = {
    "experiment_id": "test-exp",
    "root_seed": 12345,
    "game": {"variant": "nlhe", "player_count": 6, "stack_bb": 100},
    "rng": {"candidate_coupling": "shared", "reference_coupling": "shared"},
    "blocks": 8,
    "chunk_size": 4,
    "trace": {"rate": 0.0, "block_ids": [1]},
    "agents": {
        "neutral": {"kind": "heuristic", "style": "neutral"},
        "neutral_copy": {"kind": "heuristic", "style": "neutral"},
        "tight": {"kind": "heuristic", "style": "tight"},
        "aggr": {"kind": "heuristic", "style": "aggressive"},
        "loose": {"kind": "heuristic", "style": "loose"},
    },
    "reference_populations": {"mix": ["tight", "neutral", "loose", "aggr", "neutral"]},
    "pairings": [
        {"pairing_id": "ab", "candidate_a": "neutral", "candidate_b": "tight", "reference_population": "mix"},
        {"pairing_id": "self", "candidate_a": "neutral", "candidate_b": "neutral_copy", "reference_population": "mix"},
    ],
}


def make_cfg(**changes: Any) -> ExperimentConfig:
    raw = copy.deepcopy(TINY)
    for key, value in changes.items():
        node = raw
        parts = key.split(".")
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = value
    return config_from_dict(raw)


@pytest.fixture
def tiny_cfg() -> ExperimentConfig:
    return make_cfg()


def adapter(k: int = 6, stack_bb: float = 100) -> PokerKitHoldemAdapter:
    return PokerKitHoldemAdapter(GameConfig("nlhe", k, stack_bb))


def scripted_deal(ad: PokerKitHoldemAdapter, holes: Sequence[str], board: str) -> Deal:
    """holes: e.g. ["AsAh", "KsKh"]; board: 5 cards "2c3d7h9cJd". Burns are filler."""
    hole_cards = [h[i : i + 2] for h in holes for i in (0, 2)]
    b = [board[i : i + 2] for i in range(0, 10, 2)]
    used = set(hole_cards) | set(b)
    filler = [c for c in STANDARD_DECK if c not in used]
    runout = [filler[0], *b[:3], filler[1], b[3], filler[2], b[4]]
    deck = hole_cards + runout + filler[3:]
    return ad.deal_from_deck(deck)
